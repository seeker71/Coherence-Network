// form_cuda_train_ptx_host.c — driver-only host for the LEARNING band as Form-emitted PTX.
// Loads form_affine_train_f32.ptx (Form recipe fptx-affine-train), JITs it through the driver at
// optimization level 0 (so explicit mul/add/sub stay two roundings), runs one SGD step, and gates
// BIT-EXACT on every updated W word, b word, and per-row loss word vs a CPU reference in the recipe's
// op order. Runtime deps: nvcuda.dll only. No nvcc/nvrtc/go/python/rust/shell/clang.
//
// Build:  gcc -O2 -ffp-contract=off -o form_cuda_train_ptx_host.exe form_cuda_train_ptx_host.c
// Run:    form_cuda_train_ptx_host.exe form_affine_train_f32.ptx [rows cols]   (defaults 128 128)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
typedef HMODULE drv_handle;
static drv_handle drv_open(const char *p) { return LoadLibraryA(p); }
static void *drv_sym(drv_handle l, const char *s) { return (void *)(uintptr_t)GetProcAddress(l, s); }
static const char *driver_lib(void) { return "nvcuda.dll"; }
#else
#include <dlfcn.h>
typedef void *drv_handle;
static drv_handle drv_open(const char *p) { return dlopen(p, RTLD_NOW | RTLD_LOCAL); }
static void *drv_sym(drv_handle l, const char *s) { return dlsym(l, s); }
static const char *driver_lib(void) { return "libcuda.so.1"; }
#endif

typedef int CUresult;
typedef int CUdevice;
typedef void *CUcontext;
typedef void *CUmodule;
typedef void *CUfunction;
typedef void *CUstream;
typedef unsigned long long CUdeviceptr;
#define CUDA_SUCCESS 0
#define CU_JIT_ERROR_LOG_BUFFER 5
#define CU_JIT_ERROR_LOG_BUFFER_SIZE_BYTES 6
#define CU_JIT_OPTIMIZATION_LEVEL 7

typedef CUresult (*pfn_cuInit)(unsigned int);
typedef CUresult (*pfn_cuDeviceGet)(CUdevice *, int);
typedef CUresult (*pfn_cuDeviceGetName)(char *, int, CUdevice);
typedef CUresult (*pfn_cuCtxCreate)(CUcontext *, unsigned int, CUdevice);
typedef CUresult (*pfn_cuModuleLoadDataEx)(CUmodule *, const void *, unsigned int, int *, void **);
typedef CUresult (*pfn_cuModuleGetFunction)(CUfunction *, CUmodule, const char *);
typedef CUresult (*pfn_cuMemAlloc)(CUdeviceptr *, size_t);
typedef CUresult (*pfn_cuMemcpyHtoD)(CUdeviceptr, const void *, size_t);
typedef CUresult (*pfn_cuMemcpyDtoH)(void *, CUdeviceptr, size_t);
typedef CUresult (*pfn_cuLaunchKernel)(CUfunction, unsigned, unsigned, unsigned,
                                       unsigned, unsigned, unsigned, unsigned,
                                       CUstream, void **, void **);
typedef CUresult (*pfn_cuCtxSynchronize)(void);
typedef CUresult (*pfn_cuMemFree)(CUdeviceptr);
typedef CUresult (*pfn_cuGetErrorString)(CUresult, const char **);

static pfn_cuInit cuInit_;
static pfn_cuDeviceGet cuDeviceGet_;
static pfn_cuDeviceGetName cuDeviceGetName_;
static pfn_cuCtxCreate cuCtxCreate_;
static pfn_cuModuleLoadDataEx cuModuleLoadDataEx_;
static pfn_cuModuleGetFunction cuModuleGetFunction_;
static pfn_cuMemAlloc cuMemAlloc_;
static pfn_cuMemcpyHtoD cuMemcpyHtoD_;
static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_;
static pfn_cuCtxSynchronize cuCtxSynchronize_;
static pfn_cuMemFree cuMemFree_;
static pfn_cuGetErrorString cuGetErrorString_;

static char jit_log[8192];
static void die(const char *what, CUresult r) {
    const char *msg = "?";
    if (cuGetErrorString_) cuGetErrorString_(r, &msg);
    fprintf(stderr, "FAIL  %s -> CUDA error %d (%s)\n", what, r, msg);
    if (jit_log[0]) fprintf(stderr, "JIT log: %s\n", jit_log);
    exit(1);
}
#define CK(call) do { CUresult _r = (call); if (_r != CUDA_SUCCESS) die(#call, _r); } while (0)
static void *resolve(drv_handle h, const char *name) {
    void *p = drv_sym(h, name);
    if (!p) { fprintf(stderr, "FAIL  driver symbol absent: %s\n", name); exit(1); }
    return p;
}
static float val(int n) { return (float)n / 256.0f; }
static int bitexact(const float *a, const float *b, size_t n, float *max_abs) {
    int eq = 0; *max_abs = 0.0f;
    for (size_t i = 0; i < n; i++) {
        uint32_t ua, ub; memcpy(&ua, &a[i], 4); memcpy(&ub, &b[i], 4);
        if (ua == ub) eq++;
        float d = a[i] - b[i]; if (d < 0) d = -d; if (d > *max_abs) *max_abs = d;
    }
    return eq;
}

int main(int argc, char **argv) {
    const char *ptx_path = (argc > 1) ? argv[1] : "form_affine_train_f32.ptx";
    int rows = (argc > 2) ? atoi(argv[2]) : 128;
    int cols = (argc > 3) ? atoi(argv[3]) : 128;
    if (rows <= 0 || cols <= 0) { fprintf(stderr, "FAIL  bad rows/cols\n"); return 1; }

    drv_handle drv = drv_open(driver_lib());
    if (!drv) { fprintf(stderr, "SKIP  %s not loadable\n", driver_lib()); return 2; }
    cuInit_ = (pfn_cuInit)resolve(drv, "cuInit");
    cuDeviceGet_ = (pfn_cuDeviceGet)resolve(drv, "cuDeviceGet");
    cuDeviceGetName_ = (pfn_cuDeviceGetName)resolve(drv, "cuDeviceGetName");
    cuCtxCreate_ = (pfn_cuCtxCreate)resolve(drv, "cuCtxCreate_v2");
    cuModuleLoadDataEx_ = (pfn_cuModuleLoadDataEx)resolve(drv, "cuModuleLoadDataEx");
    cuModuleGetFunction_ = (pfn_cuModuleGetFunction)resolve(drv, "cuModuleGetFunction");
    cuMemAlloc_ = (pfn_cuMemAlloc)resolve(drv, "cuMemAlloc_v2");
    cuMemcpyHtoD_ = (pfn_cuMemcpyHtoD)resolve(drv, "cuMemcpyHtoD_v2");
    cuMemcpyDtoH_ = (pfn_cuMemcpyDtoH)resolve(drv, "cuMemcpyDtoH_v2");
    cuLaunchKernel_ = (pfn_cuLaunchKernel)resolve(drv, "cuLaunchKernel");
    cuCtxSynchronize_ = (pfn_cuCtxSynchronize)resolve(drv, "cuCtxSynchronize");
    cuMemFree_ = (pfn_cuMemFree)resolve(drv, "cuMemFree_v2");
    cuGetErrorString_ = (pfn_cuGetErrorString)drv_sym(drv, "cuGetErrorString");

    CK(cuInit_(0));
    CUdevice dev; CK(cuDeviceGet_(&dev, 0));
    char devname[256] = {0}; cuDeviceGetName_(devname, sizeof(devname), dev);
    CUcontext ctx; CK(cuCtxCreate_(&ctx, 0, dev));

    FILE *f = fopen(ptx_path, "rb");
    if (!f) { fprintf(stderr, "FAIL  cannot open ptx %s\n", ptx_path); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    char *ptx = malloc((size_t)sz + 1);
    if (fread(ptx, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "FAIL  short read\n"); return 1; }
    ptx[sz] = '\0'; fclose(f);

    int opts[3] = {CU_JIT_OPTIMIZATION_LEVEL, CU_JIT_ERROR_LOG_BUFFER, CU_JIT_ERROR_LOG_BUFFER_SIZE_BYTES};
    void *vals[3] = {(void *)(uintptr_t)0, jit_log, (void *)(uintptr_t)sizeof(jit_log)};
    CUmodule mod; CK(cuModuleLoadDataEx_(&mod, ptx, 3, opts, vals));
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, "form_affine_train_f32"));

    size_t nW = (size_t)rows * cols;
    float lr = 1.0f / 256.0f;
    float *w0 = malloc(nW * sizeof(float)), *b0 = malloc((size_t)rows * sizeof(float));
    float *x = malloc((size_t)cols * sizeof(float)), *t = malloc((size_t)rows * sizeof(float));
    float *wr = malloc(nW * sizeof(float)), *br = malloc((size_t)rows * sizeof(float)), *lossr = malloc((size_t)rows * sizeof(float));
    float *wg = malloc(nW * sizeof(float)), *bg = malloc((size_t)rows * sizeof(float)), *lg = malloc((size_t)rows * sizeof(float));
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) w0[(size_t)i * cols + j] = val((i * 31 + j * 17) % 1000 - 500);
        b0[i] = val((i * 7) % 1000 - 500);
        t[i] = val((i * 53) % 1000 - 500);
    }
    for (int j = 0; j < cols; j++) x[j] = val((j * 13) % 1000 - 500);

    memcpy(wr, w0, nW * sizeof(float));
    memcpy(br, b0, (size_t)rows * sizeof(float));
    for (int i = 0; i < rows; i++) {
        float acc = 0.0f;
        for (int j = cols; j > 0;) { j -= 1; float p = wr[(size_t)i * cols + j] * x[j]; acc = p + acc; }
        float y = acc + br[i];
        float d = y - t[i];
        lossr[i] = d * d;
        float g = 2.0f * d;
        for (int k = cols; k > 0;) { k -= 1; wr[(size_t)i * cols + k] = wr[(size_t)i * cols + k] - lr * g * x[k]; }
        br[i] = br[i] - lr * g;
    }

    CUdeviceptr dW, dB, dX, dT, dL;
    CK(cuMemAlloc_(&dW, nW * sizeof(float)));
    CK(cuMemAlloc_(&dB, (size_t)rows * sizeof(float)));
    CK(cuMemAlloc_(&dX, (size_t)cols * sizeof(float)));
    CK(cuMemAlloc_(&dT, (size_t)rows * sizeof(float)));
    CK(cuMemAlloc_(&dL, (size_t)rows * sizeof(float)));
    CK(cuMemcpyHtoD_(dW, w0, nW * sizeof(float)));
    CK(cuMemcpyHtoD_(dB, b0, (size_t)rows * sizeof(float)));
    CK(cuMemcpyHtoD_(dX, x, (size_t)cols * sizeof(float)));
    CK(cuMemcpyHtoD_(dT, t, (size_t)rows * sizeof(float)));
    unsigned urows = (unsigned)rows, ucols = (unsigned)cols;
    void *params[] = {&dW, &dB, &dX, &dT, &dL, &urows, &ucols, &lr};
    unsigned block = 256, grid = (urows + block - 1) / block;
    CK(cuLaunchKernel_(fn, grid, 1, 1, block, 1, 1, 0, NULL, params, NULL));
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(wg, dW, nW * sizeof(float)));
    CK(cuMemcpyDtoH_(bg, dB, (size_t)rows * sizeof(float)));
    CK(cuMemcpyDtoH_(lg, dL, (size_t)rows * sizeof(float)));

    float mw, mb, ml;
    int ew = bitexact(wg, wr, nW, &mw), eb = bitexact(bg, br, (size_t)rows, &mb), el = bitexact(lg, lossr, (size_t)rows, &ml);
    printf("device=%s\n", devname[0] ? devname : "(unknown)");
    printf("kernel=form_affine_train_f32 module=%s (%ld bytes PTX, driver JIT -O0)\n", ptx_path, sz);
    printf("parity_bitexact W=%d/%zu b=%d/%d loss=%d/%d\n", ew, nW, eb, rows, el, rows);
    printf("max_abs_diff W=%g b=%g loss=%g\n", (double)mw, (double)mb, (double)ml);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    cuMemFree_(dW); cuMemFree_(dB); cuMemFree_(dX); cuMemFree_(dT); cuMemFree_(dL);
    int ok = (ew == (int)nW) && (eb == rows) && (el == rows);
    if (!ok) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — the Form-emitted PTX LEARNING kernel, JITed by the driver alone, equals the recipe to the last bit\n");
    return 0;
}

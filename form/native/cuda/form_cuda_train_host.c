// form_cuda_train_host.c — native CUDA presence for the LEARNING band: one affine
// SGD step (y = W·x + b) on the real GPU with nothing but the OS driver. Sibling of
// form_cuda_host.c; runs the minted cell form/native/cuda/form_affine_train_f32.cubin
// (sm_89 SASS, --fmad=false) whose source is the Form recipe jte-affine-train-cuda
// (form-stdlib/jit-tensor-emit.fk; algorithm transformer-backprop.fk tbp-step).
// One GPU thread per output row updates its row of W and its b in place; the gate is
// BIT-EXACT on every updated W word, every b word, and every per-row loss word vs a
// CPU reference in the recipe's own op order. No go/python/rust/shell/clang at runtime.
//
// Build:  gcc -O2 -ffp-contract=off -o form_cuda_train_host.exe form_cuda_train_host.c
// Run:    form_cuda_train_host.exe form_affine_train_f32.cubin [rows cols]   (defaults 128 128)

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

typedef CUresult (*pfn_cuInit)(unsigned int);
typedef CUresult (*pfn_cuDeviceGet)(CUdevice *, int);
typedef CUresult (*pfn_cuDeviceGetName)(char *, int, CUdevice);
typedef CUresult (*pfn_cuCtxCreate)(CUcontext *, unsigned int, CUdevice);
typedef CUresult (*pfn_cuModuleLoadData)(CUmodule *, const void *);
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
static pfn_cuModuleLoadData cuModuleLoadData_;
static pfn_cuModuleGetFunction cuModuleGetFunction_;
static pfn_cuMemAlloc cuMemAlloc_;
static pfn_cuMemcpyHtoD cuMemcpyHtoD_;
static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_;
static pfn_cuCtxSynchronize cuCtxSynchronize_;
static pfn_cuMemFree cuMemFree_;
static pfn_cuGetErrorString cuGetErrorString_;

static void die(const char *what, CUresult r) {
    const char *msg = "?";
    if (cuGetErrorString_) cuGetErrorString_(r, &msg);
    fprintf(stderr, "FAIL  %s -> CUDA error %d (%s)\n", what, r, msg);
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
    int eq = 0;
    *max_abs = 0.0f;
    for (size_t i = 0; i < n; i++) {
        uint32_t ua, ub;
        memcpy(&ua, &a[i], 4);
        memcpy(&ub, &b[i], 4);
        if (ua == ub) eq++;
        float d = a[i] - b[i];
        if (d < 0) d = -d;
        if (d > *max_abs) *max_abs = d;
    }
    return eq;
}

int main(int argc, char **argv) {
    const char *cubin_path = (argc > 1) ? argv[1] : "form_affine_train_f32.cubin";
    int rows = (argc > 2) ? atoi(argv[2]) : 128;
    int cols = (argc > 3) ? atoi(argv[3]) : 128;
    if (rows <= 0 || cols <= 0) { fprintf(stderr, "FAIL  bad rows/cols\n"); return 1; }

    drv_handle drv = drv_open(driver_lib());
    if (!drv) { fprintf(stderr, "SKIP  %s not loadable — no NVIDIA driver on this host\n", driver_lib()); return 2; }
    cuInit_ = (pfn_cuInit)resolve(drv, "cuInit");
    cuDeviceGet_ = (pfn_cuDeviceGet)resolve(drv, "cuDeviceGet");
    cuDeviceGetName_ = (pfn_cuDeviceGetName)resolve(drv, "cuDeviceGetName");
    cuCtxCreate_ = (pfn_cuCtxCreate)resolve(drv, "cuCtxCreate_v2");
    cuModuleLoadData_ = (pfn_cuModuleLoadData)resolve(drv, "cuModuleLoadData");
    cuModuleGetFunction_ = (pfn_cuModuleGetFunction)resolve(drv, "cuModuleGetFunction");
    cuMemAlloc_ = (pfn_cuMemAlloc)resolve(drv, "cuMemAlloc_v2");
    cuMemcpyHtoD_ = (pfn_cuMemcpyHtoD)resolve(drv, "cuMemcpyHtoD_v2");
    cuMemcpyDtoH_ = (pfn_cuMemcpyDtoH)resolve(drv, "cuMemcpyDtoH_v2");
    cuLaunchKernel_ = (pfn_cuLaunchKernel)resolve(drv, "cuLaunchKernel");
    cuCtxSynchronize_ = (pfn_cuCtxSynchronize)resolve(drv, "cuCtxSynchronize");
    cuMemFree_ = (pfn_cuMemFree)resolve(drv, "cuMemFree_v2");
    cuGetErrorString_ = (pfn_cuGetErrorString)drv_sym(drv, "cuGetErrorString");

    CK(cuInit_(0));
    CUdevice dev;
    CK(cuDeviceGet_(&dev, 0));
    char devname[256] = {0};
    cuDeviceGetName_(devname, sizeof(devname), dev);
    CUcontext ctx;
    CK(cuCtxCreate_(&ctx, 0, dev));

    FILE *f = fopen(cubin_path, "rb");
    if (!f) { fprintf(stderr, "FAIL  cannot open cubin %s\n", cubin_path); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    void *image = malloc((size_t)sz);
    if (fread(image, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "FAIL  short read on cubin\n"); return 1; }
    fclose(f);
    CUmodule mod;
    CK(cuModuleLoadData_(&mod, image));
    CUfunction fn;
    CK(cuModuleGetFunction_(&fn, mod, "form_affine_train_f32"));

    size_t nW = (size_t)rows * cols;
    float lr = 1.0f / 256.0f; // exactly representable
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

    // CPU reference — the recipe's own op order, two roundings (-ffp-contract=off)
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

    // GPU — fresh device copies (kernel updates W, b in place)
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
    int ew = bitexact(wg, wr, nW, &mw);
    int eb = bitexact(bg, br, (size_t)rows, &mb);
    int el = bitexact(lg, lossr, (size_t)rows, &ml);

    printf("device=%s\n", devname[0] ? devname : "(unknown)");
    printf("kernel=form_affine_train_f32 cell=%s (%ld bytes sm_89 SASS, --fmad=false)\n", cubin_path, sz);
    printf("parity_bitexact W=%d/%zu b=%d/%d loss=%d/%d\n", ew, nW, eb, rows, el, rows);
    printf("max_abs_diff W=%g b=%g loss=%g\n", (double)mw, (double)mb, (double)ml);
    printf("runtime_deps=%s only (no go/python/rust/shell/clang)\n", driver_lib());

    cuMemFree_(dW); cuMemFree_(dB); cuMemFree_(dX); cuMemFree_(dT); cuMemFree_(dL);
    int ok = (ew == (int)nW) && (eb == rows) && (el == rows);
    if (!ok) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — the Form-minted LEARNING kernel ran on the driver alone and equals the recipe to the last bit\n");
    return 0;
}

// form_cuda_ptx_gelu_host.c — driver-only host proving the Form-emitted gelu PTX bit-exact.
// The CPU oracle replicates the recipe's tanh-gelu (jte-mlp fgelu / transformer-numerics tn-gelu)
// op-for-op in fp32 (build -ffp-contract=off), so the GPU's explicit Taylor (JIT -O0) matches to the
// last bit. This is the reusable transcendental the FFN, block, and softmax/attention carriers need.
// Runtime deps: nvcuda.dll only. No nvcc/nvrtc/go/python/rust/shell/clang.
//
// Build:  gcc -O2 -ffp-contract=off -o form_cuda_ptx_gelu_host.exe form_cuda_ptx_gelu_host.c
// Run:    form_cuda_ptx_gelu_host.exe form_gelu_f32.ptx [n]   (default 1024)

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

// CPU oracle — the recipe's tanh-gelu, op-for-op in fp32 (matches jte-mlp fgelu / tn-gelu)
static float fexp_small(float x) {
    float n = 1.0f, term = 1.0f, acc = 1.0f;
    while (n <= 14.0f) { term = term * (x / n); acc = acc + term; n = n + 1.0f; }
    return acc;
}
static float fexp(float x) {
    int k = 0;
    while ((x < 0.0f ? -x : x) > 0.5f) { x = x / 2.0f; k = k + 1; }
    float v = fexp_small(x);
    while (k > 0) { v = v * v; k = k - 1; }
    return v;
}
static float ftanh(float x) { float e = fexp(2.0f * x); return (e - 1.0f) / (e + 1.0f); }
static float fgelu(float x) {
    float z = 0.7978845608028654f * (x + 0.044715f * (x * (x * x)));
    return (0.5f * x) * (1.0f + ftanh(z));
}

int main(int argc, char **argv) {
    const char *ptx_path = (argc > 1) ? argv[1] : "form_gelu_f32.ptx";
    int n = (argc > 2) ? atoi(argv[2]) : 1024;
    if (n <= 0) { fprintf(stderr, "FAIL  bad n\n"); return 1; }

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
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, "form_gelu_f32"));

    float *x = malloc((size_t)n * 4), *ref = malloc((size_t)n * 4), *yg = malloc((size_t)n * 4);
    for (int i = 0; i < n; i++) {
        x[i] = (float)(i - n / 2) / 128.0f;   // moderate range [-n/256, n/256), exercises reduce+square
        ref[i] = fgelu(x[i]);
    }
    CUdeviceptr dX, dY;
    CK(cuMemAlloc_(&dX, (size_t)n * 4));
    CK(cuMemAlloc_(&dY, (size_t)n * 4));
    CK(cuMemcpyHtoD_(dX, x, (size_t)n * 4));
    unsigned un = (unsigned)n;
    void *params[] = {&dX, &dY, &un};
    unsigned block = 256, grid = (un + block - 1) / block;
    CK(cuLaunchKernel_(fn, grid, 1, 1, block, 1, 1, 0, NULL, params, NULL));
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(yg, dY, (size_t)n * 4));

    int exact = 0;
    float max_abs = 0.0f;
    for (int i = 0; i < n; i++) {
        uint32_t a, b;
        memcpy(&a, &yg[i], 4); memcpy(&b, &ref[i], 4);
        if (a == b) exact++;
        float d = yg[i] - ref[i]; if (d < 0) d = -d; if (d > max_abs) max_abs = d;
    }
    printf("device=%s\n", devname[0] ? devname : "(unknown)");
    printf("kernel=form_gelu_f32 module=%s (%ld bytes PTX, driver JIT -O0)\n", ptx_path, sz);
    printf("parity_bitexact=%d/%d max_abs_diff=%g\n", exact, n, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    cuMemFree_(dX); cuMemFree_(dY);
    if (exact != n) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-emitted Taylor gelu PTX, JITed by the driver alone, equals the recipe to the last bit\n");
    return 0;
}

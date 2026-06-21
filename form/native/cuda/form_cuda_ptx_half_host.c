// form_cuda_ptx_half_host.c — driver-only host for the f16 / bf16 matvec as Form-emitted PTX.
// storage is the lane format (2 bytes); the kernel widens to fp32, right-folds (two roundings), and
// does ONE round-to-nearest store back to the lane. The CPU oracle uses the SAME conversion chain:
//   f16  -> F16C hardware cvt (RNE), matches the GPU's cvt.rn.f16.f32
//   bf16 -> exact widen (b<<16) and RNE narrow (+0x7FFF+lsb), matches cvt.rn.bf16.f32
// Inputs are integer-derived and EXACTLY representable in the lane (f16: |n|<=500; bf16: |n|<=128),
// so the chain starts at identical bits on both sides. Gate is BIT-EXACT on the 16-bit output words.
// Runtime deps: nvcuda.dll only. JIT at -O0 so the explicit mul/add are not fused.
//
// Build:  gcc -O2 -mf16c -ffp-contract=off -o form_cuda_ptx_half_host.exe form_cuda_ptx_half_host.c
// Run:    form_cuda_ptx_half_host.exe <form_matvec_f16.ptx|...bf16.ptx> <f16|bf16> [rows cols]

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <immintrin.h>
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

// lane conversions matching the GPU cvt.rn
static int IS_BF16;
static uint16_t f32_to_lane(float f) {
    if (IS_BF16) {
        uint32_t x; memcpy(&x, &f, 4);
        uint32_t lsb = (x >> 16) & 1u;
        return (uint16_t)((x + 0x7fffu + lsb) >> 16);
    }
    return _cvtss_sh(f, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
}
static float lane_to_f32(uint16_t h) {
    if (IS_BF16) { uint32_t x = (uint32_t)h << 16; float f; memcpy(&f, &x, 4); return f; }
    return _cvtsh_ss(h);
}
static float val(int n) { return (float)n / 256.0f; }

int main(int argc, char **argv) {
    const char *ptx_path = (argc > 1) ? argv[1] : "form_matvec_f16.ptx";
    const char *lane = (argc > 2) ? argv[2] : "f16";
    int rows = (argc > 3) ? atoi(argv[3]) : 256;
    int cols = (argc > 4) ? atoi(argv[4]) : 256;
    IS_BF16 = (strcmp(lane, "bf16") == 0);
    int span = IS_BF16 ? 128 : 500;       // |n| bound so val(n) is exact in the lane
    int modulus = IS_BF16 ? 256 : 1000;
    char entry[64];
    snprintf(entry, sizeof(entry), "form_matvec_%s", lane);
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
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, entry));

    size_t nW = (size_t)rows * cols;
    uint16_t *w = malloc(nW * 2), *x = malloc((size_t)cols * 2);
    uint16_t *ref = malloc((size_t)rows * 2), *yg = malloc((size_t)rows * 2);
    for (int i = 0; i < rows; i++)
        for (int j = 0; j < cols; j++) w[(size_t)i * cols + j] = f32_to_lane(val((i * 31 + j * 17) % modulus - span));
    for (int j = 0; j < cols; j++) x[j] = f32_to_lane(val((j * 13) % modulus - span));
    for (int i = 0; i < rows; i++) {
        float acc = 0.0f;
        for (int j = cols; j > 0;) {
            j -= 1;
            float p = lane_to_f32(w[(size_t)i * cols + j]) * lane_to_f32(x[j]);
            acc = p + acc;
        }
        ref[i] = f32_to_lane(acc);          // one RNE store at the boundary
    }

    CUdeviceptr dW, dX, dY;
    CK(cuMemAlloc_(&dW, nW * 2));
    CK(cuMemAlloc_(&dX, (size_t)cols * 2));
    CK(cuMemAlloc_(&dY, (size_t)rows * 2));
    CK(cuMemcpyHtoD_(dW, w, nW * 2));
    CK(cuMemcpyHtoD_(dX, x, (size_t)cols * 2));
    unsigned urows = (unsigned)rows, ucols = (unsigned)cols;
    void *params[] = {&dW, &dX, &dY, &urows, &ucols};
    unsigned block = 256, grid = (urows + block - 1) / block;
    CK(cuLaunchKernel_(fn, grid, 1, 1, block, 1, 1, 0, NULL, params, NULL));
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(yg, dY, (size_t)rows * 2));

    int exact = 0;
    float max_abs = 0.0f;
    for (int i = 0; i < rows; i++) {
        if (yg[i] == ref[i]) exact++;
        float d = lane_to_f32(yg[i]) - lane_to_f32(ref[i]);
        if (d < 0) d = -d;
        if (d > max_abs) max_abs = d;
    }
    printf("device=%s\n", devname[0] ? devname : "(unknown)");
    printf("kernel=%s module=%s (%ld bytes PTX, driver JIT -O0)\n", entry, ptx_path, sz);
    printf("lane=%s parity_bitexact_rows=%d/%d max_abs_diff=%g\n", lane, exact, rows, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    cuMemFree_(dW); cuMemFree_(dX); cuMemFree_(dY);
    if (exact != rows) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-emitted %s PTX, JITed by the driver alone, equals the recipe to the last bit\n", lane);
    return 0;
}

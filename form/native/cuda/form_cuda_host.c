// form_cuda_host.c — a native CUDA presence: run a Form-minted GPU kernel on the
// real device with NOTHING but the OS GPU driver. No Go, no Python, no Rust, no
// shell, no clang, no CUDA toolkit. Built once by gcc; at runtime it loads only
// nvcuda.dll (the NVIDIA driver — intrinsic to having the GPU) via the same
// LoadLibrary/dlopen surface the presence host uses, JITs nothing, and launches a
// minted cubin cell.
//
// The cell: form/native/cuda/form_matvec_f32.cubin — sm_89 SASS compiled with
// --fmad=false (mul-then-add stays two roundings), whose source is authored by the
// Form recipe jte-matvec-cuda (form-stdlib/jit-tensor-emit.fk) and certified
// byte-identical three-way by tests/jit-tensor-cuda-emit-band.fk (verdict 15).
// This host is pure mechanism: load the driver, load the cell, launch one thread
// per output row, copy back, and gate it BIT-EXACT against a CPU right-fold in the
// recipe's own op order. A row counts only when its output word equals the CPU word.
//
// Build (gcc only — no clang, no toolkit headers; the driver API is declared here):
//   gcc -O2 -ffp-contract=off -o form_cuda_host.exe form_cuda_host.c
// Run:
//   form_cuda_host.exe form_matvec_f32.cubin [rows cols]      (defaults 256 256)

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

// ── minimal CUDA Driver API surface (no cuda.h) ──────────────────────────────
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

// deterministic inputs, exactly representable in f32 (matches the bit-exact audits)
static float val(int n) { return (float)n / 256.0f; }

int main(int argc, char **argv) {
    const char *cubin_path = (argc > 1) ? argv[1] : "form_matvec_f32.cubin";
    int rows = (argc > 2) ? atoi(argv[2]) : 256;
    int cols = (argc > 3) ? atoi(argv[3]) : 256;
    if (rows <= 0 || cols <= 0) { fprintf(stderr, "FAIL  bad rows/cols\n"); return 1; }

    // 1. the OS GPU driver — the only runtime dependency
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
    cuGetErrorString_ = (pfn_cuGetErrorString)drv_sym(drv, "cuGetErrorString"); // optional

    CK(cuInit_(0));
    CUdevice dev;
    CK(cuDeviceGet_(&dev, 0));
    char devname[256] = {0};
    cuDeviceGetName_(devname, sizeof(devname), dev);
    CUcontext ctx;
    CK(cuCtxCreate_(&ctx, 0, dev));

    // 2. load the minted cell (cubin: sm_89 SASS, --fmad=false)
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
    CK(cuModuleGetFunction_(&fn, mod, "form_matvec_f32"));

    // 3. inputs + CPU right-fold oracle (the recipe's own op order, two roundings)
    size_t nW = (size_t)rows * cols;
    float *w = (float *)malloc(nW * sizeof(float));
    float *x = (float *)malloc((size_t)cols * sizeof(float));
    float *ref = (float *)malloc((size_t)rows * sizeof(float));
    float *yg = (float *)malloc((size_t)rows * sizeof(float));
    for (int i = 0; i < rows; i++)
        for (int j = 0; j < cols; j++)
            w[(size_t)i * cols + j] = val((i * 31 + j * 17) % 1000 - 500);
    for (int j = 0; j < cols; j++)
        x[j] = val((j * 13) % 1000 - 500);
    for (int i = 0; i < rows; i++) {
        float acc = 0.0f;
        for (int j = cols; j > 0;) {
            j -= 1;
            float p = w[(size_t)i * cols + j] * x[j];
            acc = p + acc; // -ffp-contract=off keeps this two roundings, like --fmad=false
        }
        ref[i] = acc;
    }

    // 4. device buffers, launch one thread per row, copy back
    CUdeviceptr dW, dX, dY;
    CK(cuMemAlloc_(&dW, nW * sizeof(float)));
    CK(cuMemAlloc_(&dX, (size_t)cols * sizeof(float)));
    CK(cuMemAlloc_(&dY, (size_t)rows * sizeof(float)));
    CK(cuMemcpyHtoD_(dW, w, nW * sizeof(float)));
    CK(cuMemcpyHtoD_(dX, x, (size_t)cols * sizeof(float)));
    unsigned urows = (unsigned)rows, ucols = (unsigned)cols;
    void *params[] = {&dW, &dX, &dY, &urows, &ucols};
    unsigned block = 256, grid = (urows + block - 1) / block;
    CK(cuLaunchKernel_(fn, grid, 1, 1, block, 1, 1, 0, NULL, params, NULL));
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(yg, dY, (size_t)rows * sizeof(float)));

    // 5. bit-exact gate
    int exact = 0;
    float max_abs = 0.0f;
    for (int i = 0; i < rows; i++) {
        uint32_t a, b;
        memcpy(&a, &yg[i], 4);
        memcpy(&b, &ref[i], 4);
        if (a == b) exact++;
        float d = yg[i] - ref[i];
        if (d < 0) d = -d;
        if (d > max_abs) max_abs = d;
    }
    printf("device=%s\n", devname[0] ? devname : "(unknown)");
    printf("kernel=form_matvec_f32 cell=%s (%ld bytes sm_89 SASS, --fmad=false)\n", cubin_path, sz);
    printf("parity_bitexact_rows=%d/%d max_abs_diff=%g\n", exact, rows, (double)max_abs);
    printf("runtime_deps=%s only (no go/python/rust/shell/clang)\n", driver_lib());

    cuMemFree_(dW); cuMemFree_(dX); cuMemFree_(dY);
    free(image); free(w); free(x); free(ref); free(yg);
    if (exact != rows) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — the Form-minted GPU kernel ran on the driver alone and equals the recipe to the last bit\n");
    return 0;
}

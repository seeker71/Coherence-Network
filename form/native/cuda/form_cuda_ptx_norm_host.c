// form_cuda_ptx_norm_host.c — driver-only host proving layernorm / rmsnorm / residual PTX bit-exact.
// CPU oracle matches tn-layernorm / ln-rmsnorm / tb-vec-add op-for-op fp32 (-ffp-contract=off),
// incl. tn-sqrt's Newton-50 (g0=v; g=0.5*(g+v/g)). Runtime deps: nvcuda.dll only.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_norm_host.exe form_cuda_ptx_norm_host.c
// Run:   form_cuda_ptx_norm_host.exe <ptx> <layernorm|rmsnorm|residual> [rows cols]   (default 256 256)

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

typedef int CUresult; typedef int CUdevice;
typedef void *CUcontext; typedef void *CUmodule; typedef void *CUfunction; typedef void *CUstream;
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
typedef CUresult (*pfn_cuLaunchKernel)(CUfunction, unsigned, unsigned, unsigned, unsigned, unsigned, unsigned, unsigned, CUstream, void **, void **);
typedef CUresult (*pfn_cuCtxSynchronize)(void);
typedef CUresult (*pfn_cuMemFree)(CUdeviceptr);
typedef CUresult (*pfn_cuGetErrorString)(CUresult, const char **);

static pfn_cuInit cuInit_; static pfn_cuDeviceGet cuDeviceGet_; static pfn_cuDeviceGetName cuDeviceGetName_;
static pfn_cuCtxCreate cuCtxCreate_; static pfn_cuModuleLoadDataEx cuModuleLoadDataEx_;
static pfn_cuModuleGetFunction cuModuleGetFunction_; static pfn_cuMemAlloc cuMemAlloc_;
static pfn_cuMemcpyHtoD cuMemcpyHtoD_; static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_; static pfn_cuCtxSynchronize cuCtxSynchronize_;
static pfn_cuMemFree cuMemFree_; static pfn_cuGetErrorString cuGetErrorString_;

static char jit_log[8192];
static void die(const char *what, CUresult r) {
    const char *msg = "?"; if (cuGetErrorString_) cuGetErrorString_(r, &msg);
    fprintf(stderr, "FAIL  %s -> CUDA error %d (%s)\n", what, r, msg);
    if (jit_log[0]) fprintf(stderr, "JIT log: %s\n", jit_log); exit(1);
}
#define CK(call) do { CUresult _r = (call); if (_r != CUDA_SUCCESS) die(#call, _r); } while (0)
static void *resolve(drv_handle h, const char *name) {
    void *p = drv_sym(h, name); if (!p) { fprintf(stderr, "FAIL symbol absent: %s\n", name); exit(1); } return p;
}
static float val(int n) { return (float)n / 256.0f; }
static float fsqrt_newton(float v){ if (v<=0.0f) return 0.0f; float g=v; for(int i=0;i<50;i++) g=0.5f*(g+v/g); return g; }

static drv_handle drv;
static CUfunction load_fn(const char *ptx, const char *entry, long *sz_out) {
    FILE *f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    char *src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz){fprintf(stderr,"FAIL read\n");exit(1);}
    src[sz]='\0'; fclose(f); *sz_out=sz;
    int opts[3]={CU_JIT_OPTIMIZATION_LEVEL,CU_JIT_ERROR_LOG_BUFFER,CU_JIT_ERROR_LOG_BUFFER_SIZE_BYTES};
    void *vals[3]={(void*)(uintptr_t)0,jit_log,(void*)(uintptr_t)sizeof(jit_log)};
    CUmodule mod; CK(cuModuleLoadDataEx_(&mod, src, 3, opts, vals));
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, entry)); return fn;
}

int main(int argc, char **argv) {
    const char *ptx = (argc > 1) ? argv[1] : "form_layernorm_f32.ptx";
    const char *mode = (argc > 2) ? argv[2] : "layernorm";
    int rows = (argc > 3) ? atoi(argv[3]) : 256;
    int cols = (argc > 4) ? atoi(argv[4]) : 256;
    int is_ln = !strcmp(mode,"layernorm"), is_rms = !strcmp(mode,"rmsnorm"), is_res = !strcmp(mode,"residual");
    if (!is_ln && !is_rms && !is_res) { fprintf(stderr,"FAIL mode\n"); return 1; }
    float eps = 1e-5f;

    drv = drv_open(driver_lib());
    if (!drv) { fprintf(stderr, "SKIP %s not loadable\n", driver_lib()); return 2; }
    cuInit_=(pfn_cuInit)resolve(drv,"cuInit"); cuDeviceGet_=(pfn_cuDeviceGet)resolve(drv,"cuDeviceGet");
    cuDeviceGetName_=(pfn_cuDeviceGetName)resolve(drv,"cuDeviceGetName"); cuCtxCreate_=(pfn_cuCtxCreate)resolve(drv,"cuCtxCreate_v2");
    cuModuleLoadDataEx_=(pfn_cuModuleLoadDataEx)resolve(drv,"cuModuleLoadDataEx");
    cuModuleGetFunction_=(pfn_cuModuleGetFunction)resolve(drv,"cuModuleGetFunction");
    cuMemAlloc_=(pfn_cuMemAlloc)resolve(drv,"cuMemAlloc_v2"); cuMemcpyHtoD_=(pfn_cuMemcpyHtoD)resolve(drv,"cuMemcpyHtoD_v2");
    cuMemcpyDtoH_=(pfn_cuMemcpyDtoH)resolve(drv,"cuMemcpyDtoH_v2"); cuLaunchKernel_=(pfn_cuLaunchKernel)resolve(drv,"cuLaunchKernel");
    cuCtxSynchronize_=(pfn_cuCtxSynchronize)resolve(drv,"cuCtxSynchronize"); cuMemFree_=(pfn_cuMemFree)resolve(drv,"cuMemFree_v2");
    cuGetErrorString_=(pfn_cuGetErrorString)drv_sym(drv,"cuGetErrorString");
    CK(cuInit_(0));
    CUdevice dev; CK(cuDeviceGet_(&dev, 0));
    char devname[256]={0}; cuDeviceGetName_(devname, sizeof(devname), dev);
    CUcontext ctx; CK(cuCtxCreate_(&ctx, 0, dev));

    long sz;
    const char *entry = is_ln?"form_layernorm_f32":(is_rms?"form_rmsnorm_f32":"form_residual_f32");
    CUfunction fn = load_fn(ptx, entry, &sz);

    size_t n=(size_t)rows*cols;
    float *x=malloc(n*4), *g=malloc(n*4), *yref=malloc(n*4), *yg=malloc(n*4), *bb=malloc(n*4);
    for (size_t i=0;i<n;i++) x[i]=val(((int)(i*31+7))%1000-500);
    for (size_t i=0;i<n;i++) g[i]=val(((int)(i*7+3))%256-128);   // rmsnorm gain
    for (size_t i=0;i<n;i++) bb[i]=val(((int)(i*13+5))%1000-500); // residual b

    if (is_res) {
        for (size_t i=0;i<n;i++) yref[i]=x[i]+bb[i];
    } else {
        for (int r=0;r<rows;r++){
            double flen=(double)cols; float fl=(float)cols;
            (void)flen;
            if (is_ln) {
                float s=0.0f; for(int j=0;j<cols;j++) s=s+x[(size_t)r*cols+j];
                float mean=s/fl;
                float v=0.0f; for(int j=0;j<cols;j++){ float d=x[(size_t)r*cols+j]-mean; v=v+d*d; }
                float var=v/fl; float sd=var+eps; float gg=fsqrt_newton(sd); float inv=1.0f/gg;
                for(int j=0;j<cols;j++) yref[(size_t)r*cols+j]=(x[(size_t)r*cols+j]-mean)*inv;
            } else {
                float ss=0.0f; for(int j=0;j<cols;j++){ float xv=x[(size_t)r*cols+j]; ss=ss+xv*xv; }
                float meansq=ss/fl; float sd=meansq+eps; float rms=fsqrt_newton(sd); float rr=1.0f/rms;
                for(int j=0;j<cols;j++) yref[(size_t)r*cols+j]=(x[(size_t)r*cols+j]*rr)*g[(size_t)r*cols+j];
            }
        }
    }

    CUdeviceptr dX,dG,dY,dB;
    CK(cuMemAlloc_(&dX,n*4)); CK(cuMemAlloc_(&dY,n*4)); CK(cuMemcpyHtoD_(dX,x,n*4));
    unsigned ur=(unsigned)rows, uc=(unsigned)cols, un=(unsigned)n;
    unsigned block=256, grid;
    if (is_res) {
        CK(cuMemAlloc_(&dB,n*4)); CK(cuMemcpyHtoD_(dB,bb,n*4));
        void *params[]={&dX,&dB,&dY,&un}; grid=(un+block-1)/block;
        CK(cuLaunchKernel_(fn, grid,1,1, block,1,1, 0, NULL, params, NULL));
    } else if (is_rms) {
        CK(cuMemAlloc_(&dG,n*4)); CK(cuMemcpyHtoD_(dG,g,n*4));
        void *params[]={&dX,&dG,&dY,&ur,&uc,&eps}; grid=(ur+block-1)/block;
        CK(cuLaunchKernel_(fn, grid,1,1, block,1,1, 0, NULL, params, NULL));
    } else {
        void *params[]={&dX,&dY,&ur,&uc,&eps}; grid=(ur+block-1)/block;
        CK(cuLaunchKernel_(fn, grid,1,1, block,1,1, 0, NULL, params, NULL));
    }
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(yg, dY, n*4));

    int exact=0; float max_abs=0.0f;
    for (size_t i=0;i<n;i++){
        uint32_t a,b; memcpy(&a,&yg[i],4); memcpy(&b,&yref[i],4);
        if (a==b) exact++;
        float dd=yg[i]-yref[i]; if(dd<0)dd=-dd; if(dd>max_abs)max_abs=dd;
    }
    printf("device=%s\n", devname[0]?devname:"(unknown)");
    printf("kernel=%s module=%s (%ld bytes PTX, driver JIT -O0)  rows=%d cols=%d\n", entry, ptx, sz, rows, cols);
    printf("parity_bitexact=%d/%zu max_abs_diff=%g\n", exact, n, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    if (exact!=(int)n) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-emitted %s PTX, JITed by the driver alone, equals the recipe to the last bit\n", mode);
    return 0;
}

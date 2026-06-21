// form_cuda_ptx_attention_host.c — driver-only host proving the Form-emitted attention PTX bit-exact.
// CPU oracle = tb-attend-one op-for-op fp32 (-ffp-contract=off): downward-right-fold dot * scale,
// tn-softmax (forward max, Taylor fexp, forward sum, *1/s), forward weighted-sum of V. Matches GPU
// (JIT -O0). Runtime deps: nvcuda.dll only.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_attention_host.exe form_cuda_ptx_attention_host.c
// Run:   form_cuda_ptx_attention_host.exe form_attention_f32.ptx [nq nk d]   (default 8 8 16, scale=1/sqrt(d))

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
static float fexp_small(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }

int main(int argc, char **argv) {
    const char *ptx = (argc > 1) ? argv[1] : "form_attention_f32.ptx";
    int nq = (argc > 2) ? atoi(argv[2]) : 8;
    int nk = (argc > 3) ? atoi(argv[3]) : 8;
    int d  = (argc > 4) ? atoi(argv[4]) : 16;
    if (nq<=0||nk<=0||d<=0) { fprintf(stderr,"FAIL bad dims\n"); return 1; }
    // scale = 1/sqrt(d) computed in fp32 the simple way (a constant on both sides)
    float scale = 1.0f; { float g=(float)d; for(int it=0;it<60;it++) g=0.5f*(g+(float)d/g); scale=1.0f/g; }

    drv_handle drv = drv_open(driver_lib());
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

    FILE *f = fopen(ptx, "rb"); if (!f) { fprintf(stderr,"FAIL open %s\n",ptx); return 1; }
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    char *src=malloc((size_t)sz+1); if (fread(src,1,(size_t)sz,f)!=(size_t)sz){fprintf(stderr,"FAIL read\n");return 1;}
    src[sz]='\0'; fclose(f);
    int opts[3]={CU_JIT_OPTIMIZATION_LEVEL,CU_JIT_ERROR_LOG_BUFFER,CU_JIT_ERROR_LOG_BUFFER_SIZE_BYTES};
    void *vals[3]={(void*)(uintptr_t)0,jit_log,(void*)(uintptr_t)sizeof(jit_log)};
    CUmodule mod; CK(cuModuleLoadDataEx_(&mod, src, 3, opts, vals));
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, "form_attention_f32"));

    float *Q=malloc((size_t)nq*d*4), *K=malloc((size_t)nk*d*4), *V=malloc((size_t)nk*d*4);
    float *out=malloc((size_t)nq*d*4), *ref=malloc((size_t)nq*d*4), *sc=malloc((size_t)nq*nk*4);
    for (int i=0;i<nq;i++) for(int l=0;l<d;l++) Q[(size_t)i*d+l]=val((i*31+l*17)%256-128);
    for (int j=0;j<nk;j++) for(int l=0;l<d;l++) K[(size_t)j*d+l]=val((j*29+l*13)%256-128);
    for (int j=0;j<nk;j++) for(int m=0;m<d;m++) V[(size_t)j*d+m]=val((j*23+m*11)%256-128);

    // CPU oracle: tb-attend-one per query
    for (int i=0;i<nq;i++){
        // scores
        for (int j=0;j<nk;j++){
            float acc=0.0f; for(int l=d;l>0;){ l--; float p=Q[(size_t)i*d+l]*K[(size_t)j*d+l]; acc=p+acc; }
            sc[(size_t)i*nk+j]=acc*scale;
        }
        // softmax
        float m=sc[(size_t)i*nk+0]; for(int j=1;j<nk;j++){ float v=sc[(size_t)i*nk+j]; if(v>m)m=v; }
        float s=0.0f; for(int j=0;j<nk;j++){ float e=fexpf_(sc[(size_t)i*nk+j]-m); sc[(size_t)i*nk+j]=e; s=s+e; }
        float r=1.0f/s; for(int j=0;j<nk;j++) sc[(size_t)i*nk+j]=sc[(size_t)i*nk+j]*r;
        // weighted sum (forward)
        for (int mm=0;mm<d;mm++){
            float acc=0.0f; for(int j=0;j<nk;j++){ float p=V[(size_t)j*d+mm]*sc[(size_t)i*nk+j]; acc=acc+p; }
            ref[(size_t)i*d+mm]=acc;
        }
    }

    CUdeviceptr dQ,dK,dV,dOut,dSc;
    CK(cuMemAlloc_(&dQ,(size_t)nq*d*4)); CK(cuMemAlloc_(&dK,(size_t)nk*d*4)); CK(cuMemAlloc_(&dV,(size_t)nk*d*4));
    CK(cuMemAlloc_(&dOut,(size_t)nq*d*4)); CK(cuMemAlloc_(&dSc,(size_t)nq*nk*4));
    CK(cuMemcpyHtoD_(dQ,Q,(size_t)nq*d*4)); CK(cuMemcpyHtoD_(dK,K,(size_t)nk*d*4)); CK(cuMemcpyHtoD_(dV,V,(size_t)nk*d*4));
    unsigned unq=(unsigned)nq, unk=(unsigned)nk, ud=(unsigned)d;
    void *params[]={&dQ,&dK,&dV,&dOut,&dSc,&unq,&unk,&ud,&scale};
    unsigned block=256, grid=(unq+block-1)/block;
    CK(cuLaunchKernel_(fn, grid,1,1, block,1,1, 0, NULL, params, NULL));
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(out, dOut, (size_t)nq*d*4));

    int exact=0; float max_abs=0.0f; size_t n=(size_t)nq*d;
    for (size_t i=0;i<n;i++){
        uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4);
        if (a==b) exact++;
        float dd=out[i]-ref[i]; if(dd<0)dd=-dd; if(dd>max_abs)max_abs=dd;
    }
    printf("device=%s\n", devname[0]?devname:"(unknown)");
    printf("kernel=form_attention_f32 module=%s (%ld bytes PTX, driver JIT -O0)  nq=%d nk=%d d=%d scale=%g\n", ptx, sz, nq, nk, d, (double)scale);
    printf("parity_bitexact_out=%d/%zu max_abs_diff=%g\n", exact, n, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    cuMemFree_(dQ);cuMemFree_(dK);cuMemFree_(dV);cuMemFree_(dOut);cuMemFree_(dSc);
    if (exact!=(int)n) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-emitted scaled dot-product attention ran on the driver alone, bit-exact to the recipe\n");
    return 0;
}

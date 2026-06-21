// form_cuda_ptx_ffn_host.c — driver-only host proving the Form-emitted FFN forward PTX bit-exact.
// y = W2 . gelu(W1.x + b1) + b2, one CUDA block, one token. CPU oracle runs both phases op-for-op
// in fp32 (-ffp-contract=off), gelu = the recipe's Taylor fgelu, so the GPU (JIT -O0) matches to the
// last bit. Inputs scaled to [-0.5,0.5) so the gelu argument never overflows fp32 exp.
// Runtime deps: nvcuda.dll only. No nvcc/nvrtc/go/python/rust/shell/clang.
//
// Build:  gcc -O2 -ffp-contract=off -o form_cuda_ptx_ffn_host.exe form_cuda_ptx_ffn_host.c
// Run:    form_cuda_ptx_ffn_host.exe form_ffn_fwd_f32.ptx [indim hid outd]   (default 16 64 8)

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
    void *p = drv_sym(h, name); if (!p) { fprintf(stderr, "FAIL  symbol absent: %s\n", name); exit(1); } return p;
}
static float val(int n) { return (float)n / 256.0f; }

// CPU oracle gelu — the recipe's Taylor tanh-gelu, op-for-op fp32 (matches jte-mlp fgelu)
static float fexp_small(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float ftanh(float x){ float e=fexpf_(2.0f*x); return (e-1.0f)/(e+1.0f); }
static float fgelu(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); return (0.5f*x)*(1.0f+ftanh(z)); }

int main(int argc, char **argv) {
    const char *ptx = (argc > 1) ? argv[1] : "form_ffn_fwd_f32.ptx";
    int indim = (argc > 2) ? atoi(argv[2]) : 16;
    int hid   = (argc > 3) ? atoi(argv[3]) : 64;
    int outd  = (argc > 4) ? atoi(argv[4]) : 8;
    if (indim <= 0 || hid <= 0 || outd <= 0) { fprintf(stderr, "FAIL bad dims\n"); return 1; }

    drv_handle drv = drv_open(driver_lib());
    if (!drv) { fprintf(stderr, "SKIP  %s not loadable\n", driver_lib()); return 2; }
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
    CUfunction fn; CK(cuModuleGetFunction_(&fn, mod, "form_ffn_fwd_f32"));

    size_t nW1=(size_t)hid*indim, nW2=(size_t)outd*hid;
    float *w1=malloc(nW1*4), *b1=malloc((size_t)hid*4), *w2=malloc(nW2*4), *b2=malloc((size_t)outd*4);
    float *x=malloc((size_t)indim*4), *a=malloc((size_t)hid*4), *yref=malloc((size_t)outd*4), *yg=malloc((size_t)outd*4);
    // inputs in [-0.5,0.5) so the gelu argument stays well within fp32 exp range
    for (int k=0;k<hid;k++){ for(int j=0;j<indim;j++) w1[(size_t)k*indim+j]=val((k*31+j*17)%256-128); b1[k]=val((k*7)%256-128); }
    for (int j=0;j<indim;j++) x[j]=val((j*13)%256-128);
    for (int i=0;i<outd;i++){ for(int k=0;k<hid;k++) w2[(size_t)i*hid+k]=val((i*23+k*11)%256-128); b2[i]=val((i*5)%256-128); }

    // CPU reference (two phases, serial right-folds)
    for (int k=0;k<hid;k++){
        float acc=0.0f; for(int j=indim;j>0;){ j--; float p=w1[(size_t)k*indim+j]*x[j]; acc=p+acc; }
        float hk=acc+b1[k]; a[k]=fgelu(hk);
    }
    for (int i=0;i<outd;i++){
        float acc=0.0f; for(int k=hid;k>0;){ k--; float p=w2[(size_t)i*hid+k]*a[k]; acc=p+acc; }
        yref[i]=acc+b2[i];
    }

    CUdeviceptr dW1,dB1,dW2,dB2,dX,dY,dA;
    CK(cuMemAlloc_(&dW1,nW1*4)); CK(cuMemAlloc_(&dB1,(size_t)hid*4)); CK(cuMemAlloc_(&dW2,nW2*4));
    CK(cuMemAlloc_(&dB2,(size_t)outd*4)); CK(cuMemAlloc_(&dX,(size_t)indim*4)); CK(cuMemAlloc_(&dY,(size_t)outd*4));
    CK(cuMemAlloc_(&dA,(size_t)hid*4));
    CK(cuMemcpyHtoD_(dW1,w1,nW1*4)); CK(cuMemcpyHtoD_(dB1,b1,(size_t)hid*4)); CK(cuMemcpyHtoD_(dW2,w2,nW2*4));
    CK(cuMemcpyHtoD_(dB2,b2,(size_t)outd*4)); CK(cuMemcpyHtoD_(dX,x,(size_t)indim*4));
    unsigned ui=(unsigned)indim, uh=(unsigned)hid, uo=(unsigned)outd;
    void *params[]={&dW1,&dB1,&dW2,&dB2,&dX,&dY,&dA,&ui,&uh,&uo};
    CK(cuLaunchKernel_(fn, 1,1,1, 256,1,1, 0, NULL, params, NULL));   // one block, one token
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(yg,dY,(size_t)outd*4));

    int exact=0; float max_abs=0.0f;
    for (int i=0;i<outd;i++){
        uint32_t ga,gb; memcpy(&ga,&yg[i],4); memcpy(&gb,&yref[i],4);
        if (ga==gb) exact++;
        float d=yg[i]-yref[i]; if(d<0)d=-d; if(d>max_abs)max_abs=d;
    }
    printf("device=%s\n", devname[0]?devname:"(unknown)");
    printf("kernel=form_ffn_fwd_f32 module=%s (%ld bytes PTX, driver JIT -O0)  indim=%d hid=%d outd=%d\n", ptx, sz, indim, hid, outd);
    printf("parity_bitexact_y=%d/%d max_abs_diff=%g\n", exact, outd, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    cuMemFree_(dW1);cuMemFree_(dB1);cuMemFree_(dW2);cuMemFree_(dB2);cuMemFree_(dX);cuMemFree_(dY);cuMemFree_(dA);
    if (exact!=outd){ printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-emitted FFN (matvec+gelu+matvec) ran on the driver alone, bit-exact to the recipe\n");
    return 0;
}

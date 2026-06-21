// form_cuda_ptx_block_host.c — a FULL pre-LN transformer block running end-to-end on the GPU by
// COMPOSING the proven form-ptx kernels (the kernel-graph): for a sequence x[seq x d],
//   ln1 = layernorm(x);  attn = attention(ln1,ln1,ln1,scale);  r1 = x + attn;
//   ln2 = layernorm(r1);  ffn = FFN(ln2)   (per token);        out = r1 + ffn
// Each stage is a separate kernel launch through intermediate device buffers (resident across the
// graph). The CPU oracle chains the SAME ops (each already proven bit-exact vs its recipe), so the
// whole block is bit-exact. Self-attention, no projections/gamma-beta (those are just more matvecs;
// addable later). Runtime deps: nvcuda.dll only.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_block_host.exe form_cuda_ptx_block_host.c
// Run:   form_cuda_ptx_block_host.exe <dir-with-the-.ptx> [seq d hid]   (default 8 16 32)

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
typedef CUresult (*pfn_cuGetErrorString)(CUresult, const char **);

static pfn_cuInit cuInit_; static pfn_cuDeviceGet cuDeviceGet_; static pfn_cuDeviceGetName cuDeviceGetName_;
static pfn_cuCtxCreate cuCtxCreate_; static pfn_cuModuleLoadDataEx cuModuleLoadDataEx_;
static pfn_cuModuleGetFunction cuModuleGetFunction_; static pfn_cuMemAlloc cuMemAlloc_;
static pfn_cuMemcpyHtoD cuMemcpyHtoD_; static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_; static pfn_cuCtxSynchronize cuCtxSynchronize_;
static pfn_cuGetErrorString cuGetErrorString_;

static void die(const char *what, CUresult r) {
    const char *msg = "?"; if (cuGetErrorString_) cuGetErrorString_(r, &msg);
    fprintf(stderr, "FAIL  %s -> CUDA error %d (%s)\n", what, r, msg); exit(1);
}
#define CK(call) do { CUresult _r=(call); if(_r!=CUDA_SUCCESS) die(#call,_r);} while(0)
static void *resolve(drv_handle h, const char *n){ void*p=drv_sym(h,n); if(!p){fprintf(stderr,"FAIL sym %s\n",n);exit(1);} return p; }
static float val(int n){ return (float)n/256.0f; }
static float fexp_small(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float fgelu(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float e=fexpf_(2.0f*z); float th=(e-1.0f)/(e+1.0f); return (0.5f*x)*(1.0f+th); }
static float fsqrtn(float v){ if(v<=0.0f) return 0.0f; float g=v; for(int i=0;i<50;i++) g=0.5f*(g+v/g); return g; }

static char g_jit[4096];
static CUfunction load(const char *dir, const char *file, const char *entry){
    char path[1024]; snprintf(path,sizeof(path),"%s/%s",dir,file);
    FILE *f=fopen(path,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",path);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    char *src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz){fprintf(stderr,"FAIL read\n");exit(1);} src[sz]='\0'; fclose(f);
    int o[1]={CU_JIT_OPTIMIZATION_LEVEL}; void *v[1]={(void*)(uintptr_t)0};
    CUmodule m; CK(cuModuleLoadDataEx_(&m,src,1,o,v)); CUfunction fn; CK(cuModuleGetFunction_(&fn,m,entry)); free(src); return fn;
}

int main(int argc, char **argv){
    const char *dir = (argc>1)?argv[1]:".";
    int seq=(argc>2)?atoi(argv[2]):8, d=(argc>3)?atoi(argv[3]):16, hid=(argc>4)?atoi(argv[4]):32;
    float eps=1e-5f; float scale; { float g=(float)d; for(int i=0;i<60;i++) g=0.5f*(g+(float)d/g); scale=1.0f/g; }

    drv_handle drv=drv_open(driver_lib()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(pfn_cuInit)resolve(drv,"cuInit"); cuDeviceGet_=(pfn_cuDeviceGet)resolve(drv,"cuDeviceGet");
    cuDeviceGetName_=(pfn_cuDeviceGetName)resolve(drv,"cuDeviceGetName"); cuCtxCreate_=(pfn_cuCtxCreate)resolve(drv,"cuCtxCreate_v2");
    cuModuleLoadDataEx_=(pfn_cuModuleLoadDataEx)resolve(drv,"cuModuleLoadDataEx"); cuModuleGetFunction_=(pfn_cuModuleGetFunction)resolve(drv,"cuModuleGetFunction");
    cuMemAlloc_=(pfn_cuMemAlloc)resolve(drv,"cuMemAlloc_v2"); cuMemcpyHtoD_=(pfn_cuMemcpyHtoD)resolve(drv,"cuMemcpyHtoD_v2");
    cuMemcpyDtoH_=(pfn_cuMemcpyDtoH)resolve(drv,"cuMemcpyDtoH_v2"); cuLaunchKernel_=(pfn_cuLaunchKernel)resolve(drv,"cuLaunchKernel");
    cuCtxSynchronize_=(pfn_cuCtxSynchronize)resolve(drv,"cuCtxSynchronize"); cuGetErrorString_=(pfn_cuGetErrorString)drv_sym(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dev; CK(cuDeviceGet_(&dev,0)); char dn[256]={0}; cuDeviceGetName_(dn,sizeof(dn),dev);
    CUcontext ctx; CK(cuCtxCreate_(&ctx,0,dev));

    CUfunction k_ln=load(dir,"form_layernorm_f32.ptx","form_layernorm_f32");
    CUfunction k_at=load(dir,"form_attention_f32.ptx","form_attention_f32");
    CUfunction k_re=load(dir,"form_residual_f32.ptx","form_residual_f32");
    CUfunction k_ff=load(dir,"form_ffn_fwd_f32.ptx","form_ffn_fwd_f32");

    size_t sd=(size_t)seq*d;
    float *x=malloc(sd*4), *W1=malloc((size_t)hid*d*4), *b1=malloc((size_t)hid*4), *W2=malloc((size_t)d*hid*4), *b2=malloc((size_t)d*4);
    float *out=malloc(sd*4), *ref=malloc(sd*4);
    for(size_t i=0;i<sd;i++) x[i]=val(((int)(i*31+7))%256-128);
    for(int k=0;k<hid;k++){ for(int j=0;j<d;j++) W1[(size_t)k*d+j]=val((k*13+j*7)%256-128); b1[k]=val((k*5)%256-128); }
    for(int i=0;i<d;i++){ for(int k=0;k<hid;k++) W2[(size_t)i*hid+k]=val((i*11+k*3)%256-128); b2[i]=val((i*9)%256-128); }

    // ---- CPU oracle: the same block ----
    {
        float *ln1=malloc(sd*4), *att=malloc(sd*4), *r1=malloc(sd*4), *ln2=malloc(sd*4), *ffn=malloc(sd*4), *sc=malloc((size_t)seq*seq*4), *h=malloc((size_t)hid*4);
        for(int t=0;t<seq;t++){ // ln1
            float s=0; for(int j=0;j<d;j++) s=s+x[(size_t)t*d+j]; float mean=s/(float)d;
            float v=0; for(int j=0;j<d;j++){ float dd=x[(size_t)t*d+j]-mean; v=v+dd*dd; } float var=v/(float)d;
            float inv=1.0f/fsqrtn(var+eps); for(int j=0;j<d;j++) ln1[(size_t)t*d+j]=(x[(size_t)t*d+j]-mean)*inv;
        }
        for(int i=0;i<seq;i++){ // attention(ln1,ln1,ln1)
            for(int j=0;j<seq;j++){ float acc=0; for(int l=d;l>0;){ l--; float p=ln1[(size_t)i*d+l]*ln1[(size_t)j*d+l]; acc=p+acc; } sc[(size_t)i*seq+j]=acc*scale; }
            float m=sc[(size_t)i*seq+0]; for(int j=1;j<seq;j++){ float vv=sc[(size_t)i*seq+j]; if(vv>m)m=vv; }
            float ss=0; for(int j=0;j<seq;j++){ float e=fexpf_(sc[(size_t)i*seq+j]-m); sc[(size_t)i*seq+j]=e; ss=ss+e; }
            float r=1.0f/ss; for(int j=0;j<seq;j++) sc[(size_t)i*seq+j]=sc[(size_t)i*seq+j]*r;
            for(int mm=0;mm<d;mm++){ float acc=0; for(int j=0;j<seq;j++){ float p=ln1[(size_t)j*d+mm]*sc[(size_t)i*seq+j]; acc=acc+p; } att[(size_t)i*d+mm]=acc; }
        }
        for(size_t i=0;i<sd;i++) r1[i]=x[i]+att[i]; // residual
        for(int t=0;t<seq;t++){ // ln2
            float s=0; for(int j=0;j<d;j++) s=s+r1[(size_t)t*d+j]; float mean=s/(float)d;
            float v=0; for(int j=0;j<d;j++){ float dd=r1[(size_t)t*d+j]-mean; v=v+dd*dd; } float var=v/(float)d;
            float inv=1.0f/fsqrtn(var+eps); for(int j=0;j<d;j++) ln2[(size_t)t*d+j]=(r1[(size_t)t*d+j]-mean)*inv;
        }
        for(int t=0;t<seq;t++){ // FFN per token (indim=d, outd=d)
            for(int k=0;k<hid;k++){ float acc=0; for(int j=d;j>0;){ j--; float p=W1[(size_t)k*d+j]*ln2[(size_t)t*d+j]; acc=p+acc; } h[k]=fgelu(acc+b1[k]); }
            for(int i=0;i<d;i++){ float acc=0; for(int k=hid;k>0;){ k--; float p=W2[(size_t)i*hid+k]*h[k]; acc=p+acc; } ffn[(size_t)t*d+i]=acc+b2[i]; }
        }
        for(size_t i=0;i<sd;i++) ref[i]=r1[i]+ffn[i]; // residual
        free(ln1);free(att);free(r1);free(ln2);free(ffn);free(sc);free(h);
    }

    // ---- GPU kernel-graph ----
    CUdeviceptr dX,dLn1,dAtt,dR1,dLn2,dFfn,dOut,dSc,dW1,dB1,dW2,dB2,dA;
    CK(cuMemAlloc_(&dX,sd*4)); CK(cuMemAlloc_(&dLn1,sd*4)); CK(cuMemAlloc_(&dAtt,sd*4)); CK(cuMemAlloc_(&dR1,sd*4));
    CK(cuMemAlloc_(&dLn2,sd*4)); CK(cuMemAlloc_(&dFfn,sd*4)); CK(cuMemAlloc_(&dOut,sd*4)); CK(cuMemAlloc_(&dSc,(size_t)seq*seq*4));
    CK(cuMemAlloc_(&dW1,(size_t)hid*d*4)); CK(cuMemAlloc_(&dB1,(size_t)hid*4)); CK(cuMemAlloc_(&dW2,(size_t)d*hid*4)); CK(cuMemAlloc_(&dB2,(size_t)d*4)); CK(cuMemAlloc_(&dA,(size_t)hid*4));
    CK(cuMemcpyHtoD_(dX,x,sd*4)); CK(cuMemcpyHtoD_(dW1,W1,(size_t)hid*d*4)); CK(cuMemcpyHtoD_(dB1,b1,(size_t)hid*4)); CK(cuMemcpyHtoD_(dW2,W2,(size_t)d*hid*4)); CK(cuMemcpyHtoD_(dB2,b2,(size_t)d*4));
    unsigned useq=seq,ud=d,uhid=hid,usd=(unsigned)sd; unsigned B=256;
    // 1. ln1 = layernorm(x)  (rows=seq, cols=d)
    { void *p[]={&dX,&dLn1,&useq,&ud,&eps}; CK(cuLaunchKernel_(k_ln,(useq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    // 2. attn = attention(ln1,ln1,ln1)
    { void *p[]={&dLn1,&dLn1,&dLn1,&dAtt,&dSc,&useq,&useq,&ud,&scale}; CK(cuLaunchKernel_(k_at,(useq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    // 3. r1 = x + attn
    { void *p[]={&dX,&dAtt,&dR1,&usd}; CK(cuLaunchKernel_(k_re,(usd+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    // 4. ln2 = layernorm(r1)
    { void *p[]={&dR1,&dLn2,&useq,&ud,&eps}; CK(cuLaunchKernel_(k_ln,(useq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    // 5. ffn = FFN(ln2) per token
    for(int t=0;t<seq;t++){
        CUdeviceptr xin=dLn2+(CUdeviceptr)t*d*4, yout=dFfn+(CUdeviceptr)t*d*4;
        void *p[]={&dW1,&dB1,&dW2,&dB2,&xin,&yout,&dA,&ud,&uhid,&ud};
        CK(cuLaunchKernel_(k_ff,1,1,1,256,1,1,0,NULL,p,NULL));
    }
    // 6. out = r1 + ffn
    { void *p[]={&dR1,&dFfn,&dOut,&usd}; CK(cuLaunchKernel_(k_re,(usd+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(out,dOut,sd*4));

    int exact=0; float max_abs=0.0f;
    for(size_t i=0;i<sd;i++){ uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)exact++; float dd=out[i]-ref[i]; if(dd<0)dd=-dd; if(dd>max_abs)max_abs=dd; }
    printf("device=%s\n", dn[0]?dn:"(unknown)");
    printf("transformer block (pre-LN self-attn): ln->attn->resid->ln->ffn->resid, %d kernel launches\n", 4+seq);
    printf("seq=%d d=%d hid=%d scale=%g\n", seq, d, hid, (double)scale);
    printf("parity_bitexact_out=%d/%zu max_abs_diff=%g\n", exact, sd, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX kernel-graph; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    if(exact!=(int)sd){ printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — a FULL transformer block ran end-to-end on the GPU, bit-exact to the composed recipe\n");
    return 0;
}

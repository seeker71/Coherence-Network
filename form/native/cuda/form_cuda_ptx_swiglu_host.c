// form_cuda_ptx_swiglu_host.c — proves SwiGLU elementwise PTX bit-exact vs ln-swiglu (llama-numerics).
// out[j] = (g[j]*sigmoid(g[j]))*u[j], sigmoid(x)=1/(1+fexp(-x)), fexp = recipe's 14-term Taylor.
// Runtime deps: nvcuda.dll only. Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_swiglu_host.exe form_cuda_ptx_swiglu_host.c
// Run: form_cuda_ptx_swiglu_host.exe template_swiglu.ptx [n]

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#undef IN
#undef OUT
typedef HMODULE H; static H O(const char*p){return LoadLibraryA(p);} static void*S(H h,const char*s){return (void*)(uintptr_t)GetProcAddress(h,s);} static const char*LIB(){return "nvcuda.dll";}
#else
#include <dlfcn.h>
typedef void*H; static H O(const char*p){return dlopen(p,RTLD_NOW|RTLD_LOCAL);} static void*S(H h,const char*s){return dlsym(h,s);} static const char*LIB(){return "libcuda.so.1";}
#endif
typedef int CUresult; typedef int CUdevice; typedef void*CUcontext,*CUmodule,*CUfunction,*CUstream; typedef unsigned long long CUdeviceptr;
#define OKr 0
#define J7 7
typedef CUresult(*Fi)(unsigned); typedef CUresult(*Fdg)(CUdevice*,int); typedef CUresult(*Fdn)(char*,int,CUdevice); typedef CUresult(*Fcc)(CUcontext*,unsigned,CUdevice);
typedef CUresult(*Fld)(CUmodule*,const void*,unsigned,int*,void**); typedef CUresult(*Fgf)(CUfunction*,CUmodule,const char*); typedef CUresult(*Fma)(CUdeviceptr*,size_t);
typedef CUresult(*Fh)(CUdeviceptr,const void*,size_t); typedef CUresult(*Fd)(void*,CUdeviceptr,size_t); typedef CUresult(*Flk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**); typedef CUresult(*Fsy)(void); typedef CUresult(*Fes)(CUresult,const char**);
static Fi cuInit_; static Fdg cuDG_; static Fdn cuDN_; static Fcc cuCC_; static Fld cuLD_; static Fgf cuGF_; static Fma cuMA_; static Fh cuH_; static Fd cuD_; static Flk cuLK_; static Fsy cuSY_; static Fes cuES_;
static char jl[4096];
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); if(jl[0])fprintf(stderr,"JIT: %s\n",jl); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OKr)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}
static float val(int n){return (float)n/256.0f;}
static float fexs(float x){float n=1,t=1,a=1; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0?-x:x)>0.5f){x=x/2.0f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
static float sigm(float x){return 1.0f/(1.0f+fex(0.0f-x));}
static float swiglu(float g,float u){return (g*sigm(g))*u;}

int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"template_swiglu.ptx";
    int n=(argc>2)?atoi(argv[2]):2048;
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_swiglu_f32"));

    float*g=malloc(n*4),*u=malloc(n*4),*out=malloc(n*4),*ref=malloc(n*4);
    for(int i=0;i<n;i++){g[i]=val(((i*37+11)%1024)-512);  u[i]=val(((i*23+7)%1024)-512);}  // ~[-2,2)
    for(int i=0;i<n;i++)ref[i]=swiglu(g[i],u[i]);

    CUdeviceptr dg,du,dout;
    CK(cuMA_(&dg,n*4)); CK(cuMA_(&du,n*4)); CK(cuMA_(&dout,n*4));
    CK(cuH_(dg,g,n*4)); CK(cuH_(du,u,n*4));
    unsigned un=n,B=256; void*p[]={&dg,&du,&dout,&un};
    CK(cuLK_(fn,(n+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_()); CK(cuD_(out,dout,n*4));

    int ex=0; float ma=0; for(int i=0;i<n;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
    printf("device=%s\nkernel=form_swiglu_f32  n=%d  (silu(g)*u, sigmoid via recipe fexp)\n",dn,n);
    printf("parity_bitexact=%d/%d max_abs_diff=%g\nruntime_deps=%s only\n",ex,n,(double)ma,LIB());
    if(ex!=n){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — SwiGLU ran on the GPU, bit-exact to ln-swiglu (llama FFN nonlinearity)\n");
    return 0;
}

// form_cuda_ptx_rope_host.c — proves the Form-emitted RoPE PTX bit-exact vs `rope` (form-stdlib/rope.fk)
// composed over form-stdlib/trig.fk. The CPU oracle replicates rope.fk + trig.fk op-for-op in fp32:
//   fln  via frexp-style split (ln-exponent/ln-mantissa) + the 14-term atanh ln-m series + LN2,
//   fexp via the recipe's 14-term Taylor (halving-reduce + square-back) standing in for math_exp,
//   fsin via range-reduce (round half-away-from-zero) + the 10-term sin-acc Taylor, fcos=fsin(a+HALF_PI),
//   fpow(b,e)=fexp(e*fln(b)), rope-freq=fpow(10000,(-1*hd)/HD), a=pos*freq, planar rotation of each pair.
// NOT libm sinf/cosf/powf/expf, NOT sin.approx/ex2.approx/lg2.approx — the recipe's own series only.
// build -ffp-contract=off + driver JIT -O0 keep every mul/add as TWO roundings, so GPU == oracle to the bit.
// Runtime deps: nvcuda.dll only. No nvcc/nvrtc/go/python/rust/shell/clang.
//
// Build:  gcc -O2 -ffp-contract=off -o form_cuda_ptx_rope_host.exe form_cuda_ptx_rope_host.c
// Run:    form_cuda_ptx_rope_host.exe template_rope.ptx [n HD pos]   (defaults 16 16 3)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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

// ---------- CPU oracle: rope.fk + trig.fk, op-for-op in fp32 ----------
// trunc toward zero (no libm): drop the fractional part of a finite float.
static float ftrunc(float x){ long long t=(long long)x; return (float)t; }

// fln(x) for x>=1 region (base=10000): ln-exponent up + ln-mantissa + ln-m atanh series + LN2.
static float c_fln(float x){
    float a=x; int e2=0;
    while(a>=2.0f){ a=a*0.5f; e2++; }            // ln-exponent up (x>=1)
    float m=x;
    while(m>=2.0f) m=m*0.5f;                       // ln-mantissa
    while(m<1.0f)  m=m*2.0f;
    float z=(m-1.0f)/(m+1.0f);                     // ln-m: z=(m-1)/(m+1)
    float z2=z*z, zpow=z, acc=0.0f;
    for(int j=0;j<14;j++){                          // ln-ser: 14 terms
        float num=zpow*z2;
        int d=2*(j+1)+1;                            // odd denominator (exact int)
        acc=acc+(num/(float)d);
        zpow=num;
    }
    float lnm=2.0f*(z+acc);
    return ((float)e2)*0.6931471805599453f + lnm;   // e2*LN2 + ln-m
}
// fexp via the recipe's 14-term Taylor (halving-reduce + square-back) — stands in for math_exp.
static float c_fexp_small(float x){ float n=1.0f,term=1.0f,acc=1.0f; while(n<=14.0f){ term=term*(x/n); acc=acc+term; n=n+1.0f; } return acc; }
static float c_fexp(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x*0.5f; k++; } float v=c_fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float c_fpow(float b,float e){ if(b<=0.0f) return 0.0f; return c_fexp(e*c_fln(b)); }

// range-reduce: r = x - TAU*round(x/TAU), round = half-away-from-zero (Go math.Round semantics).
static float c_rangered(float x){
    const float TAU=6.283185307179586f;
    float q=x/TAU;
    float half = (q<0.0f) ? -0.5f : 0.5f;
    float rnd = ftrunc(q+half);
    return x - TAU*rnd;
}
// fsin: 10-term sin-acc Taylor over the reduced angle.
static float c_fsin(float x){
    float r=c_rangered(x);
    float x2=r*r, term=r, acc=0.0f;
    for(int k=0;k<10;k++){
        acc=acc+term;
        float t=term*(-1.0f)*x2;
        int d=(2*(k+1))*(2*(k+1)+1);                // exact int denominator
        term=t/(float)d;
    }
    return acc;
}
static float c_fcos(float x){ const float HP=1.5707963267948966f; return c_fsin(x+HP); }

// rope on one vector of length n (even) at absolute position pos, head-dim HD.
static void c_rope(const float*q,float*out,int n,int HD,int pos){
    for(int t=0;t<n/2;t++){
        int i=2*t, hd=i%HD;
        float e=(-1.0f*(float)hd)/((float)HD*1.0f);
        float freq=c_fpow(10000.0f,e);
        float a=((float)pos*1.0f)*freq;
        float c=c_fcos(a), s=c_fsin(a);
        float q0=q[i], q1=q[i+1];
        out[i]   = q0*c - q1*s;
        out[i+1] = q0*s + q1*c;
    }
}

static float val(int n){return (float)n/256.0f;}

int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"template_rope.ptx";
    int n  =(argc>2)?atoi(argv[2]):16;
    int HD =(argc>3)?atoi(argv[3]):16;
    int pos=(argc>4)?atoi(argv[4]):3;
    if(n<=0||(n&1)||HD<=0){fprintf(stderr,"FAIL bad dims (n even>0, HD>0)\n");return 1;}

    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_rope_f32"));

    float*qv=malloc((size_t)n*4),*out=malloc((size_t)n*4),*ref=malloc((size_t)n*4);
    for(int i=0;i<n;i++) qv[i]=val(((i*53+11)%1024)-512);   // ~[-2,2)
    c_rope(qv,ref,n,HD,pos);

    CUdeviceptr dq,dout;
    CK(cuMA_(&dq,(size_t)n*4)); CK(cuMA_(&dout,(size_t)n*4));
    CK(cuH_(dq,qv,(size_t)n*4));
    unsigned upos=(unsigned)pos,uHD=(unsigned)HD,un=(unsigned)n,B=128,npairs=(unsigned)(n/2);
    void*p[]={&dq,&dout,&upos,&uHD,&un};
    CK(cuLK_(fn,(npairs+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_()); CK(cuD_(out,dout,(size_t)n*4));

    int ex=0; float ma=0; for(int i=0;i<n;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
    printf("device=%s\nkernel=form_rope_f32  n=%d HD=%d pos=%d  (rope.fk over trig.fk fln/fexp/fsin/fcos)\n",dn,n,HD,pos);
    printf("parity_bitexact=%d/%d max_abs_diff=%g\nruntime_deps=%s only\n",ex,n,(double)ma,LIB());
    if(ex!=n){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — RoPE ran on the GPU, bit-exact to rope (the llama block rotation floor)\n");
    return 0;
}

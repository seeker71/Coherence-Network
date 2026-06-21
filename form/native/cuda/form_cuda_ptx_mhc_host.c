// form_cuda_ptx_mhc_host.c — proves causal multi-head attention PTX bit-exact (tb-mh + tb-attn-causal-i).
// CPU oracle: per (query i, head h): scores over keys j in [0..i] on the hd-slice, softmax (Taylor
// fexp), forward weighted-sum of V. scale = 1/sqrt(hd). Runtime deps: nvcuda.dll only.
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_mhc_host.exe form_cuda_ptx_mhc_host.c
// Run:   form_cuda_ptx_mhc_host.exe form_attention_mhc_f32.ptx [seq d nheads]   (default 8 16 4)

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
static float val(int n){return (float)n/256.0f;}
static float fexs(float x){float n=1,t=1,a=1; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0?-x:x)>0.5f){x=x/2.0f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}

int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"form_attention_mhc_f32.ptx";
    int seq=(argc>2)?atoi(argv[2]):8, d=(argc>3)?atoi(argv[3]):16, nh=(argc>4)?atoi(argv[4]):4;
    if(seq<=0||d<=0||nh<=0||d%nh){fprintf(stderr,"FAIL dims (nheads must divide d)\n");return 1;}
    int hd=d/nh; float scale; {float g=(float)hd; for(int i=0;i<60;i++)g=0.5f*(g+(float)hd/g); scale=1.0f/g;}
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_attention_mhc_f32"));

    size_t sd=(size_t)seq*d;
    float*Q=malloc(sd*4),*K=malloc(sd*4),*V=malloc(sd*4),*out=malloc(sd*4),*ref=malloc(sd*4),*sc=malloc((size_t)seq*nh*seq*4);
    for(int i=0;i<seq;i++)for(int l=0;l<d;l++)Q[(size_t)i*d+l]=val((i*31+l*17)%256-128);
    for(int j=0;j<seq;j++)for(int l=0;l<d;l++)K[(size_t)j*d+l]=val((j*29+l*13)%256-128);
    for(int j=0;j<seq;j++)for(int mm=0;mm<d;mm++)V[(size_t)j*d+mm]=val((j*23+mm*11)%256-128);

    // CPU oracle: causal multi-head
    for(int i=0;i<seq;i++)for(int h=0;h<nh;h++){int hoff=h*hd, nk=i+1; float*s=malloc((size_t)nk*4);
        for(int j=0;j<nk;j++){float a=0; for(int l=hd;l>0;){l--; float p=Q[(size_t)i*d+hoff+l]*K[(size_t)j*d+hoff+l]; a=p+a;} s[j]=a*scale;}
        float mx=s[0]; for(int j=1;j<nk;j++){if(s[j]>mx)mx=s[j];} float ss=0; for(int j=0;j<nk;j++){float e=fex(s[j]-mx); s[j]=e; ss=ss+e;} float r=1.0f/ss; for(int j=0;j<nk;j++)s[j]=s[j]*r;
        for(int mm=0;mm<hd;mm++){float a=0; for(int j=0;j<nk;j++){float p=V[(size_t)j*d+hoff+mm]*s[j]; a=a+p;} ref[(size_t)i*d+hoff+mm]=a;}
        free(s);
    }

    CUdeviceptr dQ,dK,dV,dO,dS;
    CK(cuMA_(&dQ,sd*4)); CK(cuMA_(&dK,sd*4)); CK(cuMA_(&dV,sd*4)); CK(cuMA_(&dO,sd*4)); CK(cuMA_(&dS,(size_t)seq*nh*seq*4));
    CK(cuH_(dQ,Q,sd*4)); CK(cuH_(dK,K,sd*4)); CK(cuH_(dV,V,sd*4));
    unsigned us=seq,ud=d,un=nh,tot=(unsigned)seq*nh,B=256; void*p[]={&dQ,&dK,&dV,&dO,&dS,&us,&us,&ud,&un,&scale};
    CK(cuLK_(fn,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_()); CK(cuD_(out,dO,sd*4));

    int ex=0; float ma=0; for(size_t i=0;i<sd;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float dd=out[i]-ref[i]; if(dd<0)dd=-dd; if(dd>ma)ma=dd;}
    printf("device=%s\nkernel=form_attention_mhc_f32 (causal multi-head) seq=%d d=%d nheads=%d hd=%d scale=%g\n",dn,seq,d,nh,hd,(double)scale);
    printf("parity_bitexact_out=%d/%zu max_abs_diff=%g\n",ex,sd,(double)ma);
    printf("runtime_deps=%s only\n",LIB());
    if(ex!=(int)sd){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — causal multi-head attention ran on the GPU, bit-exact to tb-mh/tb-attn-causal-i\n");
    return 0;
}

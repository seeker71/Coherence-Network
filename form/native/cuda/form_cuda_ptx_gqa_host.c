// form_cuda_ptx_gqa_host.c — proves grouped-query causal attention PTX bit-exact (real llama3.2 shape).
// CPU oracle: per (query i, q-head h): kvh=h/n_rep; scores over keys [0..i] on the hd-slice (Q head h,
// K/V head kvh); softmax (Taylor fexp); forward weighted-sum. Runtime deps: nvcuda.dll only.
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_gqa_host.exe form_cuda_ptx_gqa_host.c
// Run:   form_cuda_ptx_gqa_host.exe template_attention_gqa.ptx [seq hd nhq nhkv]   (default 8 4 6 2)

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
    const char*ptx=(argc>1)?argv[1]:"template_attention_gqa.ptx";
    int seq=(argc>2)?atoi(argv[2]):8, hd=(argc>3)?atoi(argv[3]):4, nhq=(argc>4)?atoi(argv[4]):6, nhkv=(argc>5)?atoi(argv[5]):2;
    if(seq<=0||hd<=0||nhq<=0||nhkv<=0||nhq%nhkv){fprintf(stderr,"FAIL dims (nhq%%nhkv must be 0)\n");return 1;}
    int nrep=nhq/nhkv, dq=nhq*hd, dkv=nhkv*hd; float scale; {float g=(float)hd; for(int i=0;i<60;i++)g=0.5f*(g+(float)hd/g); scale=1.0f/g;}
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_attention_gqa_f32"));

    size_t sq=(size_t)seq*dq, sk=(size_t)seq*dkv;
    float*Q=malloc(sq*4),*K=malloc(sk*4),*V=malloc(sk*4),*out=malloc(sq*4),*ref=malloc(sq*4);
    for(int i=0;i<seq;i++)for(int l=0;l<dq;l++)Q[(size_t)i*dq+l]=val((i*31+l*17)%256-128);
    for(int j=0;j<seq;j++)for(int l=0;l<dkv;l++)K[(size_t)j*dkv+l]=val((j*29+l*13)%256-128);
    for(int j=0;j<seq;j++)for(int l=0;l<dkv;l++)V[(size_t)j*dkv+l]=val((j*23+l*11)%256-128);

    for(int i=0;i<seq;i++)for(int h=0;h<nhq;h++){int kvh=h/nrep,hoq=h*hd,hok=kvh*hd,nk=i+1; float*s=malloc((size_t)nk*4);
        for(int j=0;j<nk;j++){float a=0; for(int l=hd;l>0;){l--; float p=Q[(size_t)i*dq+hoq+l]*K[(size_t)j*dkv+hok+l]; a=p+a;} s[j]=a*scale;}
        float mx=s[0]; for(int j=1;j<nk;j++)if(s[j]>mx)mx=s[j]; float ss=0; for(int j=0;j<nk;j++){float e=fex(s[j]-mx); s[j]=e; ss=ss+e;} float r=1.0f/ss; for(int j=0;j<nk;j++)s[j]=s[j]*r;
        for(int mm=0;mm<hd;mm++){float a=0; for(int j=0;j<nk;j++){float p=V[(size_t)j*dkv+hok+mm]*s[j]; a=a+p;} ref[(size_t)i*dq+hoq+mm]=a;}
        free(s);
    }

    CUdeviceptr dQ,dK,dV,dO,dS;
    CK(cuMA_(&dQ,sq*4)); CK(cuMA_(&dK,sk*4)); CK(cuMA_(&dV,sk*4)); CK(cuMA_(&dO,sq*4)); CK(cuMA_(&dS,(size_t)seq*nhq*seq*4));
    CK(cuH_(dQ,Q,sq*4)); CK(cuH_(dK,K,sk*4)); CK(cuH_(dV,V,sk*4));
    unsigned useq=seq,uhd=hd,unhq=nhq,unhkv=nhkv,tot=(unsigned)seq*nhq,B=256; void*p[]={&dQ,&dK,&dV,&dO,&dS,&useq,&useq,&uhd,&unhq,&unhkv,&scale};
    CK(cuLK_(fn,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_()); CK(cuD_(out,dO,sq*4));

    int ex=0; float ma=0; for(size_t i=0;i<sq;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
    printf("device=%s\nkernel=form_attention_gqa_f32  seq=%d hd=%d nhq=%d nhkv=%d (GQA %dx) scale=%g\n",dn,seq,hd,nhq,nhkv,nrep,(double)scale);
    printf("parity_bitexact_out=%d/%zu max_abs_diff=%g\nruntime_deps=%s only\n",ex,sq,(double)ma,LIB());
    if(ex!=(int)sq){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — grouped-query causal attention ran on the GPU, bit-exact (real llama3.2 GQA shape)\n");
    return 0;
}

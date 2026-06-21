// form_cuda_ptx_ffn_train_host.c — proves the FFN/MLP training-step PTX bit-exact vs jte-mlp-train.
// One SGD step over y=W2·gelu(W1·x+b1)+b2; CPU oracle mirrors the 5 phases (fwd downward folds, dh1
// FORWARD fold reading the ORIGINAL w2, gelu/gelu' = recipe's own Taylor). Compares every updated
// buffer (w1,b1,w2,b2) + intermediates (h1,a,gy,dh1,loss) bit-for-bit. Runtime deps: nvcuda.dll only.
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_ffn_train_host.exe form_cuda_ptx_ffn_train_host.c
// Run: form_cuda_ptx_ffn_train_host.exe template_ffn_train.ptx [indim hid outd]

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
static char jl[8192];
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); if(jl[0])fprintf(stderr,"JIT: %s\n",jl); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OKr)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}
static float val(int n){return (float)n/256.0f;}
static float fexs(float x){float n=1,t=1,a=1; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0?-x:x)>0.5f){x=x/2.0f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
static float ftanh(float x){float e=fex(2.0f*x); return (e-1.0f)/(e+1.0f);}
static float fgelu(float x){float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); return (0.5f*x)*(1.0f+ftanh(z));}
static float fgelud(float x){float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float th=ftanh(z); return (0.5f*(1.0f+th))+((0.5f*x)*((1.0f-th*th)*(0.7978845608028654f*(1.0f+0.134145f*(x*x)))));}

int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"template_ffn_train.ptx";
    int IN=(argc>2)?atoi(argv[2]):8, HID=(argc>3)?atoi(argv[3]):16, OUT=(argc>4)?atoi(argv[4]):4;
    float lr=0.013f;
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_ffn_train_f32"));

    int nw1=HID*IN,nw2=OUT*HID;
    float*w1=malloc(nw1*4),*b1=malloc(HID*4),*w2=malloc(nw2*4),*b2=malloc(OUT*4),*x=malloc(IN*4),*t=malloc(OUT*4);
    float*loss=malloc(OUT*4),*h1=malloc(HID*4),*a=malloc(HID*4),*gy=malloc(OUT*4),*dh1=malloc(HID*4);
    // originals (also keep copies for oracle)
    float*W1=malloc(nw1*4),*B1=malloc(HID*4),*W2=malloc(nw2*4),*B2=malloc(OUT*4);
    for(int i=0;i<nw1;i++)w1[i]=W1[i]=val((i*37+11)%256-128);
    for(int i=0;i<HID;i++)b1[i]=B1[i]=val((i*17+3)%256-128);
    for(int i=0;i<nw2;i++)w2[i]=W2[i]=val((i*23+7)%256-128);
    for(int i=0;i<OUT;i++)b2[i]=B2[i]=val((i*41+5)%256-128);
    for(int i=0;i<IN;i++)x[i]=val((i*29+9)%256-128);
    for(int i=0;i<OUT;i++)t[i]=val((i*53+13)%256-128);

    // ---- CPU oracle (operates on W1/B1/W2/B2 copies) ----
    float*oh1=malloc(HID*4),*oa=malloc(HID*4),*ogy=malloc(OUT*4),*odh1=malloc(HID*4),*oloss=malloc(OUT*4);
    for(int k=0;k<HID;k++){float acc=0; for(int j=IN;j>0;){j--; acc=W1[k*IN+j]*x[j]+acc;} float hk=acc+B1[k]; oh1[k]=hk; oa[k]=fgelu(hk);}
    for(int i=0;i<OUT;i++){float acc=0; for(int k=HID;k>0;){k--; acc=W2[i*HID+k]*oa[k]+acc;} float yi=acc+B2[i]; float d=yi-t[i]; oloss[i]=d*d; ogy[i]=2.0f*d;}
    for(int k=0;k<HID;k++){float s=0; for(int i=0;i<OUT;i++){s=s+ogy[i]*W2[i*HID+k];} odh1[k]=s*fgelud(oh1[k]);}   // reads ORIGINAL W2
    for(int i=0;i<OUT;i++){for(int k=HID;k>0;){k--; W2[i*HID+k]=W2[i*HID+k]-lr*ogy[i]*oa[k];} B2[i]=B2[i]-lr*ogy[i];}
    for(int k=0;k<HID;k++){for(int j=IN;j>0;){j--; W1[k*IN+j]=W1[k*IN+j]-lr*odh1[k]*x[j];} B1[k]=B1[k]-lr*odh1[k];}

    CUdeviceptr dw1,db1,dw2,db2,dx,dt,dloss,dh1d,da,dgy,ddh1;
    CK(cuMA_(&dw1,nw1*4));CK(cuMA_(&db1,HID*4));CK(cuMA_(&dw2,nw2*4));CK(cuMA_(&db2,OUT*4));CK(cuMA_(&dx,IN*4));CK(cuMA_(&dt,OUT*4));
    CK(cuMA_(&dloss,OUT*4));CK(cuMA_(&dh1d,HID*4));CK(cuMA_(&da,HID*4));CK(cuMA_(&dgy,OUT*4));CK(cuMA_(&ddh1,HID*4));
    CK(cuH_(dw1,w1,nw1*4));CK(cuH_(db1,b1,HID*4));CK(cuH_(dw2,w2,nw2*4));CK(cuH_(db2,b2,OUT*4));CK(cuH_(dx,x,IN*4));CK(cuH_(dt,t,OUT*4));
    unsigned uin=IN,uhid=HID,uout=OUT,B=256;
    void*p[]={&dw1,&db1,&dw2,&db2,&dx,&dt,&dloss,&dh1d,&da,&dgy,&ddh1,&uin,&uhid,&uout,&lr};
    CK(cuLK_(fn,1,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_());   // ONE workgroup
    CK(cuD_(w1,dw1,nw1*4));CK(cuD_(b1,db1,HID*4));CK(cuD_(w2,dw2,nw2*4));CK(cuD_(b2,db2,OUT*4));
    CK(cuD_(loss,dloss,OUT*4));CK(cuD_(h1,dh1d,HID*4));CK(cuD_(a,da,HID*4));CK(cuD_(gy,dgy,OUT*4));CK(cuD_(dh1,ddh1,HID*4));

    int ex=0,tot=0; float ma=0;
    #define CMP(g,r,n) do{for(int _i=0;_i<(n);_i++){tot++; uint32_t _a,_b; memcpy(&_a,&(g)[_i],4); memcpy(&_b,&(r)[_i],4); if(_a==_b)ex++; float _d=(g)[_i]-(r)[_i]; if(_d<0)_d=-_d; if(_d>ma)ma=_d;}}while(0)
    CMP(w1,W1,nw1); CMP(b1,B1,HID); CMP(w2,W2,nw2); CMP(b2,B2,OUT);
    CMP(h1,oh1,HID); CMP(a,oa,HID); CMP(gy,ogy,OUT); CMP(dh1,odh1,HID); CMP(loss,oloss,OUT);
    printf("device=%s\nkernel=form_ffn_train_f32  indim=%d hid=%d outd=%d lr=%g  (5-phase single-workgroup SGD step)\n",dn,IN,HID,OUT,(double)lr);
    printf("parity_bitexact=%d/%d max_abs_diff=%g  (w1,b1,w2,b2 updated + h1,a,gy,dh1,loss)\n",ex,tot,(double)ma);
    printf("runtime_deps=%s only\n",LIB());
    if(ex!=tot){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — FFN backprop/SGD ran on the GPU, bit-exact to jte-mlp-train (gelu' = recipe's own)\n");
    return 0;
}

// form_cuda_ptx_conv2d_host.c — proves conv2d PTX bit-exact vs cv2d-conv (form-stdlib/conv2d.fk).
// CPU oracle replicates the recipe's nested right-folds: ky down (cv2d-window-dot), kx down
// (cv-window-dot), ic down (tb-dot), nested accumulators td/wd/acc, + bias; zero-pad = 0 contribution.
// Runtime deps: nvcuda.dll only. Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_conv2d_host.exe form_cuda_ptx_conv2d_host.c
// Run: form_cuda_ptx_conv2d_host.exe template_conv2d.ptx [IC OC H W kh kw pad stride]

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

int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"template_conv2d.ptx";
    int IC=(argc>2)?atoi(argv[2]):2, OC=(argc>3)?atoi(argv[3]):3, Hh=(argc>4)?atoi(argv[4]):5, Wd=(argc>5)?atoi(argv[5]):5;
    int kh=(argc>6)?atoi(argv[6]):3, kw=(argc>7)?atoi(argv[7]):3, pad=(argc>8)?atoi(argv[8]):1, stride=(argc>9)?atoi(argv[9]):1;
    int outH=(Hh+2*pad-kh)/stride+1, outW=(Wd+2*pad-kw)/stride+1;
    if(outH<=0||outW<=0){fprintf(stderr,"FAIL bad dims\n");return 1;}
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);return 1;} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*src=malloc((size_t)sz+1); if(fread(src,1,(size_t)sz,f)!=(size_t)sz)return 1; src[sz]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,src,3,o,v)); CUfunction fn; CK(cuGF_(&fn,m,"form_conv2d_f32"));

    size_t nW=(size_t)OC*kh*kw*IC, nIn=(size_t)Hh*Wd*IC, nOut=(size_t)outH*outW*OC;
    float*W=malloc(nW*4),*b=malloc((size_t)OC*4),*in=malloc(nIn*4),*out=malloc(nOut*4),*ref=malloc(nOut*4);
    for(size_t i=0;i<nW;i++)W[i]=val((int)((i*37+11)%256)-128);
    for(int i=0;i<OC;i++)b[i]=val((i*53+7)%256-128);
    for(size_t i=0;i<nIn;i++)in[i]=val((int)((i*29+5)%256)-128);

    // CPU oracle = cv2d-conv exact nested fold
    for(int oc=0;oc<OC;oc++)for(int oy=0;oy<outH;oy++)for(int ox=0;ox<outW;ox++){
        float acc=0.0f;
        for(int ky=kh;ky>0;){ky--; int iy=oy*stride+ky-pad; float wd=0.0f;
            for(int kx=kw;kx>0;){kx--; int ix=ox*stride+kx-pad; float td=0.0f;
                if(iy>=0&&iy<Hh&&ix>=0&&ix<Wd){
                    for(int ic=IC;ic>0;){ic--; float p=W[(((size_t)(oc*kh+ky)*kw+kx)*IC)+ic]*in[(((size_t)iy*Wd+ix)*IC)+ic]; td=p+td;}
                }
                wd=td+wd;
            }
            acc=wd+acc;
        }
        ref[(((size_t)oy*outW+ox)*OC)+oc]=acc+b[oc];
    }

    CUdeviceptr dW,db,dIn,dOut;
    CK(cuMA_(&dW,nW*4)); CK(cuMA_(&db,(size_t)OC*4)); CK(cuMA_(&dIn,nIn*4)); CK(cuMA_(&dOut,nOut*4));
    CK(cuH_(dW,W,nW*4)); CK(cuH_(db,b,(size_t)OC*4)); CK(cuH_(dIn,in,nIn*4));
    unsigned uic=IC,uh=Hh,uw=Wd,uoc=OC,ukh=kh,ukw=kw,upad=pad,ust=stride,B=128,tot=(unsigned)nOut;
    void*p[]={&dW,&db,&dIn,&dOut,&uic,&uh,&uw,&uoc,&ukh,&ukw,&upad,&ust};
    CK(cuLK_(fn,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_()); CK(cuD_(out,dOut,nOut*4));

    int ex=0; float ma=0; for(size_t i=0;i<nOut;i++){uint32_t a,c; memcpy(&a,&out[i],4); memcpy(&c,&ref[i],4); if(a==c)ex++; float dd=out[i]-ref[i]; if(dd<0)dd=-dd; if(dd>ma)ma=dd;}
    printf("device=%s\nkernel=form_conv2d_f32  IC=%d OC=%d in=%dx%d k=%dx%d pad=%d stride=%d -> out=%dx%dx%d\n",dn,IC,OC,Hh,Wd,kh,kw,pad,stride,outH,outW,OC);
    printf("parity_bitexact_out=%d/%zu max_abs_diff=%g\n",ex,nOut,(double)ma);
    printf("runtime_deps=%s only\n",LIB());
    if(ex!=(int)nOut){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — conv2d ran on the GPU, bit-exact to cv2d-conv (diffusion stem on metal)\n");
    return 0;
}

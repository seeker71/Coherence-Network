// form_cuda_ptx_proj_host.c — proves the projection (matvec+bias) and gamma/beta affine kernels
// bit-exact vs CPU oracles (tb-affine / tb-ln-seq's *gamma+beta). Runtime deps: nvcuda.dll only.
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_proj_host.exe form_cuda_ptx_proj_host.c
// Run:   form_cuda_ptx_proj_host.exe <ptx> <proj|gb> [a b cdim]

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
#define OK 0
#define JOPT 7
typedef CUresult(*F_i)(unsigned); typedef CUresult(*F_dg)(CUdevice*,int); typedef CUresult(*F_dn)(char*,int,CUdevice);
typedef CUresult(*F_cc)(CUcontext*,unsigned,CUdevice); typedef CUresult(*F_ld)(CUmodule*,const void*,unsigned,int*,void**);
typedef CUresult(*F_gf)(CUfunction*,CUmodule,const char*); typedef CUresult(*F_ma)(CUdeviceptr*,size_t);
typedef CUresult(*F_h2d)(CUdeviceptr,const void*,size_t); typedef CUresult(*F_d2h)(void*,CUdeviceptr,size_t);
typedef CUresult(*F_lk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**);
typedef CUresult(*F_sy)(void); typedef CUresult(*F_es)(CUresult,const char**);
static F_i cuInit_; static F_dg cuDeviceGet_; static F_dn cuName_; static F_cc cuCtx_; static F_ld cuLoad_; static F_gf cuGet_;
static F_ma cuMA_; static F_h2d cuH2D_; static F_d2h cuD2H_; static F_lk cuLK_; static F_sy cuSync_; static F_es cuErr_;
static void die(const char*w,CUresult r){const char*m="?"; if(cuErr_)cuErr_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OK)die(#c,_r);}while(0)
static void*R(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL sym %s\n",n);exit(1);} return p;}
static float val(int n){return (float)n/256.0f;}
static char gl[2048];
static CUfunction load(const char*ptx,const char*ent){
    FILE*f=fopen(ptx,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",ptx);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*s=malloc((size_t)sz+1); if(fread(s,1,(size_t)sz,f)!=(size_t)sz)exit(1); s[sz]='\0'; fclose(f);
    int o[1]={JOPT}; void*v[1]={(void*)(uintptr_t)0}; CUmodule m; CK(cuLoad_(&m,s,1,o,v)); CUfunction fn; CK(cuGet_(&fn,m,ent)); return fn;
}
int main(int argc,char**argv){
    const char*ptx=(argc>1)?argv[1]:"form_proj_f32.ptx"; const char*mode=(argc>2)?argv[2]:"proj";
    int is_proj=!strcmp(mode,"proj");
    int A=(argc>3)?atoi(argv[3]):12, Bd=(argc>4)?atoi(argv[4]):16, C=(argc>5)?atoi(argv[5]):24; // proj: ntok,ind,outd ; gb: rows,cols,(unused)
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(F_i)R(drv,"cuInit"); cuDeviceGet_=(F_dg)R(drv,"cuDeviceGet"); cuName_=(F_dn)R(drv,"cuDeviceGetName"); cuCtx_=(F_cc)R(drv,"cuCtxCreate_v2");
    cuLoad_=(F_ld)R(drv,"cuModuleLoadDataEx"); cuGet_=(F_gf)R(drv,"cuModuleGetFunction"); cuMA_=(F_ma)R(drv,"cuMemAlloc_v2");
    cuH2D_=(F_h2d)R(drv,"cuMemcpyHtoD_v2"); cuD2H_=(F_d2h)R(drv,"cuMemcpyDtoH_v2"); cuLK_=(F_lk)R(drv,"cuLaunchKernel"); cuSync_=(F_sy)R(drv,"cuCtxSynchronize"); cuErr_=(F_es)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dev; CK(cuDeviceGet_(&dev,0)); char dn[256]={0}; cuName_(dn,sizeof(dn),dev); CUcontext ctx; CK(cuCtx_(&ctx,0,dev));

    if(is_proj){
        int ntok=A, ind=Bd, outd=C; size_t nW=(size_t)outd*ind, nX=(size_t)ntok*ind, nY=(size_t)ntok*outd;
        float*W=malloc(nW*4),*b=malloc((size_t)outd*4),*X=malloc(nX*4),*Y=malloc(nY*4),*ref=malloc(nY*4);
        for(size_t i=0;i<nW;i++)W[i]=val(((int)(i*7+1))%256-128);
        for(int o=0;o<outd;o++)b[o]=val((o*5)%256-128);
        for(size_t i=0;i<nX;i++)X[i]=val(((int)(i*13+3))%256-128);
        for(int t=0;t<ntok;t++)for(int o=0;o<outd;o++){ float a=0; for(int l=ind;l>0;){l--; float p=W[(size_t)o*ind+l]*X[(size_t)t*ind+l]; a=p+a;} ref[(size_t)t*outd+o]=a+b[o]; }
        CUfunction fn=load(ptx,"form_proj_f32");
        CUdeviceptr dW,dB,dX,dY; CK(cuMA_(&dW,nW*4)); CK(cuMA_(&dB,(size_t)outd*4)); CK(cuMA_(&dX,nX*4)); CK(cuMA_(&dY,nY*4));
        CK(cuH2D_(dW,W,nW*4)); CK(cuH2D_(dB,b,(size_t)outd*4)); CK(cuH2D_(dX,X,nX*4));
        unsigned un=ntok,uo=outd,ui=ind,tot=(unsigned)nY,B=256; void*p[]={&dW,&dB,&dX,&dY,&un,&uo,&ui};
        CK(cuLK_(fn,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSync_()); CK(cuD2H_(Y,dY,nY*4));
        int ex=0; float ma=0; for(size_t i=0;i<nY;i++){uint32_t x,y; memcpy(&x,&Y[i],4); memcpy(&y,&ref[i],4); if(x==y)ex++; float d=Y[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
        printf("device=%s\nkernel=form_proj_f32 ntok=%d ind=%d outd=%d\nparity_bitexact=%d/%zu max_abs_diff=%g\n",dn,ntok,ind,outd,ex,nY,(double)ma);
        printf("%s\n", ex==(int)nY?"ok — projection (matvec+bias) bit-exact":"FAIL not bit-exact"); return ex==(int)nY?0:1;
    } else {
        int rows=A, cols=Bd; size_t n=(size_t)rows*cols;
        float*x=malloc(n*4),*g=malloc((size_t)cols*4),*be=malloc((size_t)cols*4),*Y=malloc(n*4),*ref=malloc(n*4);
        for(size_t i=0;i<n;i++)x[i]=val(((int)(i*17+5))%256-128);
        for(int j=0;j<cols;j++){g[j]=val((j*7+1)%256-128); be[j]=val((j*11+3)%256-128);}
        for(int i=0;i<rows;i++)for(int j=0;j<cols;j++)ref[(size_t)i*cols+j]=x[(size_t)i*cols+j]*g[j]+be[j];
        CUfunction fn=load(ptx,"form_affine_gb_f32");
        CUdeviceptr dX,dG,dBe,dY; CK(cuMA_(&dX,n*4)); CK(cuMA_(&dG,(size_t)cols*4)); CK(cuMA_(&dBe,(size_t)cols*4)); CK(cuMA_(&dY,n*4));
        CK(cuH2D_(dX,x,n*4)); CK(cuH2D_(dG,g,(size_t)cols*4)); CK(cuH2D_(dBe,be,(size_t)cols*4));
        unsigned ur=rows,uc=cols,tot=(unsigned)n,B=256; void*p[]={&dX,&dG,&dBe,&dY,&ur,&uc};
        CK(cuLK_(fn,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSync_()); CK(cuD2H_(Y,dY,n*4));
        int ex=0; float ma=0; for(size_t i=0;i<n;i++){uint32_t a,bb; memcpy(&a,&Y[i],4); memcpy(&bb,&ref[i],4); if(a==bb)ex++; float d=Y[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
        printf("device=%s\nkernel=form_affine_gb_f32 rows=%d cols=%d\nparity_bitexact=%d/%zu max_abs_diff=%g\n",dn,rows,cols,ex,n,(double)ma);
        printf("%s\n", ex==(int)n?"ok — gamma/beta affine bit-exact":"FAIL not bit-exact"); return ex==(int)n?0:1;
    }
}

// form_cuda_ptx_exact_block_host.c — the EXACT tb-block (whisper-shaped) end-to-end on the GPU,
// composing all the proven kernels including Q/K/V/O projections and gamma/beta. Matches tb-block:
//   h1 = ln-seq(x,eps,g1,be1) = affine_gb(layernorm(x), g1, be1)
//   Q=proj(Wq,bq,h1) K=proj(Wk,bk,h1) V=proj(Wv,bv,h1);  attn=attention(Q,K,V,scale)
//   r1 = x + proj(Wo,bo,attn)                              (residual)
//   h2 = ln-seq(r1,eps,g2,be2);  ffn = tb-ffn(W1,c1,W2,c2,h2) per token;  out = r1 + ffn
// CPU oracle chains the same ops (each already proven bit-exact). Runtime deps: nvcuda.dll only.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_exact_block_host.exe form_cuda_ptx_exact_block_host.c
// Run:   form_cuda_ptx_exact_block_host.exe <dir-with-.ptx> [seq d hid]   (default 8 16 32)

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
typedef CUresult(*Fi)(unsigned); typedef CUresult(*Fdg)(CUdevice*,int); typedef CUresult(*Fdn)(char*,int,CUdevice); typedef CUresult(*Fcc)(CUcontext*,unsigned,CUdevice);
typedef CUresult(*Fld)(CUmodule*,const void*,unsigned,int*,void**); typedef CUresult(*Fgf)(CUfunction*,CUmodule,const char*); typedef CUresult(*Fma)(CUdeviceptr*,size_t);
typedef CUresult(*Fh)(CUdeviceptr,const void*,size_t); typedef CUresult(*Fd)(void*,CUdeviceptr,size_t); typedef CUresult(*Flk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**); typedef CUresult(*Fsy)(void); typedef CUresult(*Fes)(CUresult,const char**);
static Fi cuInit_; static Fdg cuDG_; static Fdn cuDN_; static Fcc cuCC_; static Fld cuLD_; static Fgf cuGF_; static Fma cuMA_; static Fh cuH_; static Fd cuD_; static Flk cuLK_; static Fsy cuSY_; static Fes cuES_;
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OK)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}
static float val(int n){return (float)n/256.0f;}
static float fexs(float x){float n=1,t=1,a=1; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0?-x:x)>0.5f){x=x/2.0f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
static float fge(float x){float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float e=fex(2.0f*z); float th=(e-1.0f)/(e+1.0f); return (0.5f*x)*(1.0f+th);}
static float fsq(float v){if(v<=0)return 0; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g;}
static H drv;
static CUfunction load(const char*dir,const char*fn,const char*ent){char p[1024]; snprintf(p,sizeof(p),"%s/%s",dir,fn); FILE*f=fopen(p,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",p);exit(1);} fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*s=malloc((size_t)sz+1); if(fread(s,1,(size_t)sz,f)!=(size_t)sz)exit(1); s[sz]='\0'; fclose(f); int o[1]={JOPT}; void*v[1]={(void*)(uintptr_t)0}; CUmodule m; CK(cuLD_(&m,s,1,o,v)); CUfunction k; CK(cuGF_(&k,m,ent)); free(s); return k;}

static int SEQ,D,HID; static float EPS,SCALE;
static CUfunction K_ln,K_gb,K_pr,K_at,K_re,K_ff;
// gpu helpers
static void g_ln(CUdeviceptr in,CUdeviceptr out){unsigned s=SEQ,d=D,B=256; void*p[]={&in,&out,&s,&d,&EPS}; CK(cuLK_(K_ln,(s+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
static void g_gb(CUdeviceptr in,CUdeviceptr g,CUdeviceptr be,CUdeviceptr out){unsigned s=SEQ,d=D,n=(unsigned)SEQ*D,B=256; void*p[]={&in,&g,&be,&out,&s,&d}; CK(cuLK_(K_gb,(n+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
static void g_proj(CUdeviceptr W,CUdeviceptr b,CUdeviceptr X,CUdeviceptr Y){unsigned nt=SEQ,od=D,id=D,tot=(unsigned)SEQ*D,B=256; void*p[]={&W,&b,&X,&Y,&nt,&od,&id}; CK(cuLK_(K_pr,(tot+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
static void g_re(CUdeviceptr a,CUdeviceptr b,CUdeviceptr o){unsigned n=(unsigned)SEQ*D,B=256; void*p[]={&a,&b,&o,&n}; CK(cuLK_(K_re,(n+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}

// cpu helpers
static void c_ln(const float*in,float*out){for(int t=0;t<SEQ;t++){float s=0;for(int j=0;j<D;j++)s=s+in[(size_t)t*D+j];float me=s/(float)D;float v=0;for(int j=0;j<D;j++){float dd=in[(size_t)t*D+j]-me;v=v+dd*dd;}float iv=1.0f/fsq(v/(float)D+EPS);for(int j=0;j<D;j++)out[(size_t)t*D+j]=(in[(size_t)t*D+j]-me)*iv;}}
static void c_gb(const float*in,const float*g,const float*be,float*out){for(int i=0;i<SEQ;i++)for(int j=0;j<D;j++)out[(size_t)i*D+j]=in[(size_t)i*D+j]*g[j]+be[j];}
static void c_proj(const float*W,const float*b,const float*X,float*Y){for(int t=0;t<SEQ;t++)for(int o=0;o<D;o++){float a=0;for(int l=D;l>0;){l--;float p=W[(size_t)o*D+l]*X[(size_t)t*D+l];a=p+a;}Y[(size_t)t*D+o]=a+b[o];}}

int main(int argc,char**argv){
    const char*dir=(argc>1)?argv[1]:".";
    SEQ=(argc>2)?atoi(argv[2]):8; D=(argc>3)?atoi(argv[3]):16; HID=(argc>4)?atoi(argv[4]):32; EPS=1e-5f;
    {float g=(float)D; for(int i=0;i<60;i++)g=0.5f*(g+(float)D/g); SCALE=1.0f/g;}
    drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    K_ln=load(dir,"form_layernorm_f32.ptx","form_layernorm_f32"); K_gb=load(dir,"form_affine_gb_f32.ptx","form_affine_gb_f32"); K_pr=load(dir,"form_proj_f32.ptx","form_proj_f32");
    K_at=load(dir,"form_attention_f32.ptx","form_attention_f32"); K_re=load(dir,"form_residual_f32.ptx","form_residual_f32"); K_ff=load(dir,"form_ffn_fwd_f32.ptx","form_ffn_fwd_f32");

    size_t sd=(size_t)SEQ*D;
    float *x=malloc(sd*4),*g1=malloc((size_t)D*4),*be1=malloc((size_t)D*4),*g2=malloc((size_t)D*4),*be2=malloc((size_t)D*4);
    float *Wq=malloc((size_t)D*D*4),*bq=malloc((size_t)D*4),*Wk=malloc((size_t)D*D*4),*bk=malloc((size_t)D*4),*Wv=malloc((size_t)D*D*4),*bv=malloc((size_t)D*4),*Wo=malloc((size_t)D*D*4),*bo=malloc((size_t)D*4);
    float *W1=malloc((size_t)HID*D*4),*c1=malloc((size_t)HID*4),*W2=malloc((size_t)D*HID*4),*c2=malloc((size_t)D*4),*out=malloc(sd*4),*ref=malloc(sd*4);
    for(size_t i=0;i<sd;i++)x[i]=val(((int)(i*17+3))%256-128);
    for(int j=0;j<D;j++){g1[j]=val((j*3+1)%256-128);be1[j]=val((j*5+2)%256-128);g2[j]=val((j*7+1)%256-128);be2[j]=val((j*9+2)%256-128);bq[j]=val((j*2)%256-128);bk[j]=val((j*4)%256-128);bv[j]=val((j*6)%256-128);bo[j]=val((j*8)%256-128);c2[j]=val((j*3)%256-128);}
    for(int o=0;o<D;o++)for(int l=0;l<D;l++){Wq[(size_t)o*D+l]=val((o*7+l*3)%256-128);Wk[(size_t)o*D+l]=val((o*5+l*11)%256-128);Wv[(size_t)o*D+l]=val((o*13+l*2)%256-128);Wo[(size_t)o*D+l]=val((o*3+l*9)%256-128);}
    for(int k=0;k<HID;k++){for(int j=0;j<D;j++)W1[(size_t)k*D+j]=val((k*5+j*3)%256-128);c1[k]=val((k*2)%256-128);}
    for(int o=0;o<D;o++)for(int k=0;k<HID;k++)W2[(size_t)o*HID+k]=val((o*7+k*3)%256-128);

    // ---- CPU oracle (tb-block) ----
    {float*ln=malloc(sd*4),*h1=malloc(sd*4),*Q=malloc(sd*4),*Kk=malloc(sd*4),*V=malloc(sd*4),*att=malloc(sd*4),*sc=malloc((size_t)SEQ*SEQ*4),*ao=malloc(sd*4),*r1=malloc(sd*4),*h2=malloc(sd*4),*ff=malloc(sd*4),*hh=malloc((size_t)HID*4);
     c_ln(x,ln); c_gb(ln,g1,be1,h1); c_proj(Wq,bq,h1,Q); c_proj(Wk,bk,h1,Kk); c_proj(Wv,bv,h1,V);
     for(int i=0;i<SEQ;i++){for(int j=0;j<SEQ;j++){float a=0;for(int l=D;l>0;){l--;float p=Q[(size_t)i*D+l]*Kk[(size_t)j*D+l];a=p+a;}sc[(size_t)i*SEQ+j]=a*SCALE;}
        float m=sc[(size_t)i*SEQ+0];for(int j=1;j<SEQ;j++){float vv=sc[(size_t)i*SEQ+j];if(vv>m)m=vv;}float ss=0;for(int j=0;j<SEQ;j++){float e=fex(sc[(size_t)i*SEQ+j]-m);sc[(size_t)i*SEQ+j]=e;ss=ss+e;}float r=1.0f/ss;for(int j=0;j<SEQ;j++)sc[(size_t)i*SEQ+j]=sc[(size_t)i*SEQ+j]*r;
        for(int mm=0;mm<D;mm++){float a=0;for(int j=0;j<SEQ;j++){float p=V[(size_t)j*D+mm]*sc[(size_t)i*SEQ+j];a=a+p;}att[(size_t)i*D+mm]=a;}}
     c_proj(Wo,bo,att,ao); for(int i=0;i<(int)sd;i++)r1[i]=x[i]+ao[i]; c_ln(r1,ln); c_gb(ln,g2,be2,h2);
     for(int t=0;t<SEQ;t++){for(int k=0;k<HID;k++){float a=0;for(int j=D;j>0;){j--;float p=W1[(size_t)k*D+j]*h2[(size_t)t*D+j];a=p+a;}hh[k]=fge(a+c1[k]);}for(int o=0;o<D;o++){float a=0;for(int k=HID;k>0;){k--;float p=W2[(size_t)o*HID+k]*hh[k];a=p+a;}ff[(size_t)t*D+o]=a+c2[o];}}
     for(int i=0;i<(int)sd;i++)ref[i]=r1[i]+ff[i];
     free(ln);free(h1);free(Q);free(Kk);free(V);free(att);free(sc);free(ao);free(r1);free(h2);free(ff);free(hh);}

    // ---- GPU kernel-graph ----
    CUdeviceptr dX,dLn,dH1,dQ,dK,dV,dAt,dSc,dAo,dR1,dH2,dFf,dOut,dA, gWq,gbq,gWk,gbk,gWv,gbv,gWo,gbo,gg1,gbe1,gg2,gbe2,gW1,gc1,gW2,gc2;
    #define A(p,sz) CK(cuMA_(&p,(size_t)(sz)*4))
    A(dX,sd);A(dLn,sd);A(dH1,sd);A(dQ,sd);A(dK,sd);A(dV,sd);A(dAt,sd);A(dSc,(size_t)SEQ*SEQ);A(dAo,sd);A(dR1,sd);A(dH2,sd);A(dFf,sd);A(dOut,sd);A(dA,HID);
    A(gWq,(size_t)D*D);A(gbq,D);A(gWk,(size_t)D*D);A(gbk,D);A(gWv,(size_t)D*D);A(gbv,D);A(gWo,(size_t)D*D);A(gbo,D);A(gg1,D);A(gbe1,D);A(gg2,D);A(gbe2,D);A(gW1,(size_t)HID*D);A(gc1,HID);A(gW2,(size_t)D*HID);A(gc2,D);
    #define U(p,src,sz) CK(cuH_(p,src,(size_t)(sz)*4))
    U(dX,x,sd);U(gWq,Wq,(size_t)D*D);U(gbq,bq,D);U(gWk,Wk,(size_t)D*D);U(gbk,bk,D);U(gWv,Wv,(size_t)D*D);U(gbv,bv,D);U(gWo,Wo,(size_t)D*D);U(gbo,bo,D);U(gg1,g1,D);U(gbe1,be1,D);U(gg2,g2,D);U(gbe2,be2,D);U(gW1,W1,(size_t)HID*D);U(gc1,c1,HID);U(gW2,W2,(size_t)D*HID);U(gc2,c2,D);
    g_ln(dX,dLn); g_gb(dLn,gg1,gbe1,dH1); g_proj(gWq,gbq,dH1,dQ); g_proj(gWk,gbk,dH1,dK); g_proj(gWv,gbv,dH1,dV);
    {unsigned s=SEQ,d=D,B=256; void*p[]={&dQ,&dK,&dV,&dAt,&dSc,&s,&s,&d,&SCALE}; CK(cuLK_(K_at,(s+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
    g_proj(gWo,gbo,dAt,dAo); g_re(dX,dAo,dR1); g_ln(dR1,dLn); g_gb(dLn,gg2,gbe2,dH2);
    for(int t=0;t<SEQ;t++){CUdeviceptr xi=dH2+(CUdeviceptr)t*D*4,yo=dFf+(CUdeviceptr)t*D*4; unsigned d=D,h=HID; void*p[]={&gW1,&gc1,&gW2,&gc2,&xi,&yo,&dA,&d,&h,&d}; CK(cuLK_(K_ff,1,1,1,256,1,1,0,NULL,p,NULL));}
    g_re(dR1,dFf,dOut);
    CK(cuSY_()); CK(cuD_(out,dOut,sd*4));

    int ex=0; float ma=0; for(size_t i=0;i<sd;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
    printf("device=%s\nEXACT tb-block (ln-seq[g/be] -> QKVO proj -> attn -> +res -> ln-seq -> ffn -> +res), %d launches\n", dn, 11+SEQ);
    printf("seq=%d d=%d hid=%d  parity_bitexact_out=%d/%zu max_abs_diff=%g\n", SEQ,D,HID,ex,sd,(double)ma);
    printf("runtime_deps=%s only\n", LIB());
    if(ex!=(int)sd){printf("FAIL not bit-exact\n");return 1;}
    printf("ok — the EXACT tb-block (projections + gamma/beta) ran end-to-end on the GPU, bit-exact to the recipe\n");
    return 0;
}

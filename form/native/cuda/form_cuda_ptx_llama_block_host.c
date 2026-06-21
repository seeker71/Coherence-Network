// form_cuda_ptx_llama_block_host.c — the FULL llama decoder block (lblk-block-causal,
// form-stdlib/llama-block.fk lines 56-85) end-to-end on the GPU as a PTX multi-launch
// kernel-graph, bit-exact (uint32-identical) to the CPU recipe oracle, driver-only.
//
// COMPOSES the already-proven template kernels through resident device buffers — no kernel
// is rewritten. The graph mirrors form_cuda_ptx_exact_block_host.c's structure, swapping
// the whisper numerics for the llama ones:
//   n1 = RMSNorm(x, g1, eps)                               (template_rmsnorm.ptx, per-channel gain)
//   q  = RoPE(Wq*n1, pos, HD); k = RoPE(Wk*n1, pos, HD); v = Wv*n1   (bias-free matvec; q/k roped, v not)
//   attn = causal_attention(q, k, v, scale)                (template_attention_mhc.ptx, nheads=1)
//   h  = x + Wo*attn                                        (residual)
//   n2 = RMSNorm(h, g2, eps)
//   y  = h + Wd*SwiGLU(Wg*n2, Wu*n2)                        (residual; SwiGLU = silu(gate)*up)
// pos = token index; HD = head dim; bias-free projections = template_matvec.ptx (one launch/token).
//
// The CPU oracle replicates lblk-block-causal op-for-op in fp32, reusing the proven fragments:
//   RMSNorm meansq + Newton-50 sqrt; bias-free matvec = downward right-fold (tb-dot);
//   RoPE = rope.fk over trig.fk (fln frexp-split + atanh series, fpow=Taylor fexp,
//   fsin range-reduce+10-term, fcos=fsin(a+pi/2)); causal attention forward folds + Taylor-fexp
//   softmax; SwiGLU sigmoid = 1/(1+fexp(-x)). NO hardware transcendentals, NO fma (separate
//   mul.f32/add.f32), div.rn, JIT at CU_JIT_OPTIMIZATION_LEVEL=0.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_llama_block_host.exe form_cuda_ptx_llama_block_host.c
// Run:   form_cuda_ptx_llama_block_host.exe <dir-with-template-.ptx> [seq d HD hid]   (default 4 16 16 32)

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
#define OK 0
#define JOPT 7
typedef CUresult(*Fi)(unsigned); typedef CUresult(*Fdg)(CUdevice*,int); typedef CUresult(*Fdn)(char*,int,CUdevice); typedef CUresult(*Fcc)(CUcontext*,unsigned,CUdevice);
typedef CUresult(*Fld)(CUmodule*,const void*,unsigned,int*,void**); typedef CUresult(*Fgf)(CUfunction*,CUmodule,const char*); typedef CUresult(*Fma)(CUdeviceptr*,size_t);
typedef CUresult(*Fh)(CUdeviceptr,const void*,size_t); typedef CUresult(*Fd)(void*,CUdeviceptr,size_t); typedef CUresult(*Flk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**); typedef CUresult(*Fsy)(void); typedef CUresult(*Fes)(CUresult,const char**);
static Fi cuInit_; static Fdg cuDG_; static Fdn cuDN_; static Fcc cuCC_; static Fld cuLD_; static Fgf cuGF_; static Fma cuMA_; static Fh cuH_; static Fd cuD_; static Flk cuLK_; static Fsy cuSY_; static Fes cuES_;
static char jl[8192];
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); if(jl[0])fprintf(stderr,"JIT: %s\n",jl); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OK)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}
static float val(int n){return (float)n/256.0f;}

// ---------- shared fp32 helpers (recipe-exact; no libm transcendentals) ----------
// Newton-50 sqrt (tn-sqrt): g0=v; g=0.5*(g+v/g).
static float fsq(float v){if(v<=0.0f)return 0.0f; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g;}
// fexp = recipe 14-term Taylor + halving-reduce + square-back (matches attention/swiglu PTX fexp).
static float fexs(float x){float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0.0f?-x:x)>0.5f){x=x*0.5f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
// sigmoid / silu / swiglu (ln-swiglu): silu(g)=g/(1+e^-g); swiglu=(g*sigmoid(g))*u.
static float sigm(float x){return 1.0f/(1.0f+fex(0.0f-x));}
static float swiglu(float g,float u){return (g*sigm(g))*u;}

// ---------- RoPE oracle: rope.fk over trig.fk, op-for-op (from form_cuda_ptx_rope_host.c) ----------
static float ftrunc(float x){ long long t=(long long)x; return (float)t; }
static float c_fln(float x){
    int e2=0; { float a=x; while(a>=2.0f){ a=a*0.5f; e2++; } }
    float m=x; while(m>=2.0f) m=m*0.5f; while(m<1.0f) m=m*2.0f;
    float z=(m-1.0f)/(m+1.0f); float z2=z*z, zpow=z, acc=0.0f;
    for(int j=0;j<14;j++){ float num=zpow*z2; int d=2*(j+1)+1; acc=acc+(num/(float)d); zpow=num; }
    float lnm=2.0f*(z+acc);
    return ((float)e2)*0.6931471805599453f + lnm;
}
static float c_fpow(float b,float e){ if(b<=0.0f) return 0.0f; return fex(e*c_fln(b)); }
static float c_rangered(float x){ const float TAU=6.283185307179586f; float q=x/TAU; float half=(q<0.0f)?-0.5f:0.5f; float rnd=ftrunc(q+half); return x - TAU*rnd; }
static float c_fsin(float x){ float r=c_rangered(x); float x2=r*r, term=r, acc=0.0f; for(int k=0;k<10;k++){ acc=acc+term; float t=term*(-1.0f)*x2; int d=(2*(k+1))*(2*(k+1)+1); term=t/(float)d; } return acc; }
static float c_fcos(float x){ const float HP=1.5707963267948966f; return c_fsin(x+HP); }
// rope one vector of length n (even) at absolute position pos, head-dim HD.
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

static int SEQ,D,HD,HID; static float EPS,SCALE;

// ---------- CPU oracle pieces (each matches its PTX kernel op-for-op) ----------
// RMSNorm: per-channel gain g (length D), broadcast to every token. meansq + Newton sqrt.
static void c_rms(const float*in,const float*g,float*out){
    for(int t=0;t<SEQ;t++){
        float ss=0.0f; for(int j=0;j<D;j++){ float xv=in[(size_t)t*D+j]; ss=ss+xv*xv; }
        float meansq=ss/(float)D; float rms=fsq(meansq+EPS); float r=1.0f/rms;
        for(int j=0;j<D;j++) out[(size_t)t*D+j]=(in[(size_t)t*D+j]*r)*g[j];
    }
}
// bias-free matvec per token: y[t] = W * x[t], W is outd x ind, downward right-fold (tb-dot).
static void c_matvec_seq(const float*W,const float*X,float*Y,int outd,int ind){
    for(int t=0;t<SEQ;t++)for(int o=0;o<outd;o++){ float a=0.0f; for(int l=ind;l>0;){ l--; float p=W[(size_t)o*ind+l]*X[(size_t)t*ind+l]; a=p+a; } Y[(size_t)t*outd+o]=a; }
}
// RoPE each token by its absolute position (token index).
static void c_rope_seq(const float*X,float*Y){ for(int t=0;t<SEQ;t++) c_rope(X+(size_t)t*D, Y+(size_t)t*D, D, HD, t); }
// causal single-head attention over the full D (tb-attn-seq-causal): query i attends keys [0..i].
static void c_attn_causal(const float*Q,const float*Kk,const float*V,float*att){
    float*s=malloc((size_t)SEQ*4);
    for(int i=0;i<SEQ;i++){
        int nk=i+1;
        for(int j=0;j<nk;j++){ float a=0.0f; for(int l=D;l>0;){ l--; float p=Q[(size_t)i*D+l]*Kk[(size_t)j*D+l]; a=p+a; } s[j]=a*SCALE; }
        float m=s[0]; for(int j=1;j<nk;j++){ if(s[j]>m)m=s[j]; }
        float ss=0.0f; for(int j=0;j<nk;j++){ float e=fex(s[j]-m); s[j]=e; ss=ss+e; }
        float r=1.0f/ss; for(int j=0;j<nk;j++) s[j]=s[j]*r;
        for(int mm=0;mm<D;mm++){ float a=0.0f; for(int j=0;j<nk;j++){ float p=V[(size_t)j*D+mm]*s[j]; a=a+p; } att[(size_t)i*D+mm]=a; }
    }
    free(s);
}

// ---------- GPU kernel handles + launch helpers ----------
static CUfunction K_rms,K_mv,K_rope,K_at,K_re,K_sg;
static CUfunction load(const char*dir,const char*fn,const char*ent){
    char p[1024]; snprintf(p,sizeof(p),"%s/%s",dir,fn);
    FILE*f=fopen(p,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",p);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); char*s=malloc((size_t)sz+1); if(fread(s,1,(size_t)sz,f)!=(size_t)sz)exit(1); s[sz]='\0'; fclose(f);
    int o[3]={JOPT,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,s,3,o,v)); CUfunction k; CK(cuGF_(&k,m,ent)); free(s); return k;
}
// RMSNorm: grid over SEQ rows; gain buffer is SEQ*D (per-channel gain broadcast — PTX indexes g[row*cols+j]).
static void g_rms(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){unsigned r=SEQ,c=D,B=256; void*p[]={&in,&g,&out,&r,&c,&EPS}; CK(cuLK_(K_rms,(r+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
// bias-free projection: one matvec launch per token (W: outd x ind, grid over outd rows).
static void g_matvec_seq(CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256;
    for(int t=0;t<SEQ;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*ind*4, yo=Y+(CUdeviceptr)t*outd*4; void*p[]={&W,&xi,&yo,&rows,&cols}; CK(cuLK_(K_mv,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
// RoPE each token by its position (one launch per token; grid over D/2 pairs).
static void g_rope_seq(CUdeviceptr X,CUdeviceptr Y){
    unsigned uHD=(unsigned)HD,un=(unsigned)D,B=128,npairs=(unsigned)(D/2);
    for(int t=0;t<SEQ;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*D*4, yo=Y+(CUdeviceptr)t*D*4; unsigned pos=(unsigned)t; void*p[]={&xi,&yo,&pos,&uHD,&un}; CK(cuLK_(K_rope,(npairs+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
static void g_re(CUdeviceptr a,CUdeviceptr b,CUdeviceptr o){unsigned n=(unsigned)SEQ*D,B=256; void*p[]={&a,&b,&o,&n}; CK(cuLK_(K_re,(n+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}

int main(int argc,char**argv){
    const char*dir=(argc>1)?argv[1]:".";
    SEQ=(argc>2)?atoi(argv[2]):4; D=(argc>3)?atoi(argv[3]):16; HD=(argc>4)?atoi(argv[4]):16; HID=(argc>5)?atoi(argv[5]):32; EPS=1e-5f;
    if(D&1){fprintf(stderr,"FAIL d must be even (RoPE rotates pairs)\n");return 1;}
    // scale = 1/sqrt(D) via the body's own Newton sqrt (no host sqrt smuggled). Match the band: 1/tn-sqrt(attn dim).
    {float g=(float)D; for(int i=0;i<60;i++)g=0.5f*(g+(float)D/g); SCALE=1.0f/g;}

    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));

    K_rms =load(dir,"template_rmsnorm.ptx","form_rmsnorm_f32");
    K_mv  =load(dir,"template_matvec.ptx","form_matvec_f32");
    K_rope=load(dir,"template_rope.ptx","form_rope_f32");
    K_at  =load(dir,"template_attention_mhc.ptx","form_attention_mhc_f32");
    K_re  =load(dir,"template_residual.ptx","form_residual_f32");
    K_sg  =load(dir,"template_swiglu.ptx","form_swiglu_f32");

    size_t sd=(size_t)SEQ*D, sh=(size_t)SEQ*HID;
    float *x=malloc(sd*4),*g1=malloc((size_t)D*4),*g2=malloc((size_t)D*4);
    float *Wq=malloc((size_t)D*D*4),*Wk=malloc((size_t)D*D*4),*Wv=malloc((size_t)D*D*4),*Wo=malloc((size_t)D*D*4);
    float *Wg=malloc((size_t)HID*D*4),*Wu=malloc((size_t)HID*D*4),*Wd=malloc((size_t)D*HID*4);
    float *out=malloc(sd*4),*ref=malloc(sd*4);
    // gain buffers broadcast to SEQ*D for the rmsnorm kernel's g[row*cols+j] indexing.
    float *G1=malloc(sd*4),*G2=malloc(sd*4);

    for(size_t i=0;i<sd;i++)x[i]=val(((int)(i*17+3))%256-128);
    for(int j=0;j<D;j++){ g1[j]=val((j*3+1)%256-128); g2[j]=val((j*7+1)%256-128); }
    for(int o=0;o<D;o++)for(int l=0;l<D;l++){Wq[(size_t)o*D+l]=val((o*7+l*3)%256-128);Wk[(size_t)o*D+l]=val((o*5+l*11)%256-128);Wv[(size_t)o*D+l]=val((o*13+l*2)%256-128);Wo[(size_t)o*D+l]=val((o*3+l*9)%256-128);}
    for(int k=0;k<HID;k++)for(int j=0;j<D;j++){Wg[(size_t)k*D+j]=val((k*5+j*3)%256-128);Wu[(size_t)k*D+j]=val((k*9+j*7)%256-128);}
    for(int o=0;o<D;o++)for(int k=0;k<HID;k++)Wd[(size_t)o*HID+k]=val((o*7+k*3)%256-128);
    for(int t=0;t<SEQ;t++)for(int j=0;j<D;j++){G1[(size_t)t*D+j]=g1[j];G2[(size_t)t*D+j]=g2[j];}

    // ---- CPU oracle: lblk-block-causal, op-for-op ----
    {
        float*n1=malloc(sd*4),*Q=malloc(sd*4),*Kk=malloc(sd*4),*V=malloc(sd*4),*Qr=malloc(sd*4),*Kr=malloc(sd*4);
        float*att=malloc(sd*4),*ao=malloc(sd*4),*h=malloc(sd*4),*n2=malloc(sd*4);
        float*gg=malloc(sh*4),*uu=malloc(sh*4),*sg=malloc(sh*4),*ff=malloc(sd*4);
        c_rms(x,g1,n1);
        c_matvec_seq(Wq,n1,Q,D,D); c_matvec_seq(Wk,n1,Kk,D,D); c_matvec_seq(Wv,n1,V,D,D);
        c_rope_seq(Q,Qr); c_rope_seq(Kk,Kr);            // q,k roped; v NOT
        c_attn_causal(Qr,Kr,V,att);
        c_matvec_seq(Wo,att,ao,D,D);
        for(size_t i=0;i<sd;i++)h[i]=x[i]+ao[i];        // residual
        c_rms(h,g2,n2);
        c_matvec_seq(Wg,n2,gg,HID,D); c_matvec_seq(Wu,n2,uu,HID,D);
        for(size_t i=0;i<sh;i++)sg[i]=swiglu(gg[i],uu[i]);
        c_matvec_seq(Wd,sg,ff,D,HID);
        for(size_t i=0;i<sd;i++)ref[i]=h[i]+ff[i];      // residual
        free(n1);free(Q);free(Kk);free(V);free(Qr);free(Kr);free(att);free(ao);free(h);free(n2);free(gg);free(uu);free(sg);free(ff);
    }

    // ---- GPU kernel-graph: resident buffers, composed launches ----
    CUdeviceptr dX,dN1,dQ,dK,dV,dQr,dKr,dAt,dSc,dAo,dH,dN2,dGg,dUu,dSg,dFf,dOut;
    CUdeviceptr gG1,gG2,gWq,gWk,gWv,gWo,gWg,gWu,gWd;
    #define A(p,sz) CK(cuMA_(&p,(size_t)(sz)*4))
    A(dX,sd);A(dN1,sd);A(dQ,sd);A(dK,sd);A(dV,sd);A(dQr,sd);A(dKr,sd);A(dAt,sd);A(dSc,(size_t)SEQ*SEQ);A(dAo,sd);A(dH,sd);A(dN2,sd);A(dGg,sh);A(dUu,sh);A(dSg,sh);A(dFf,sd);A(dOut,sd);
    A(gG1,sd);A(gG2,sd);A(gWq,(size_t)D*D);A(gWk,(size_t)D*D);A(gWv,(size_t)D*D);A(gWo,(size_t)D*D);A(gWg,(size_t)HID*D);A(gWu,(size_t)HID*D);A(gWd,(size_t)D*HID);
    #define U(p,src,sz) CK(cuH_(p,src,(size_t)(sz)*4))
    U(dX,x,sd);U(gG1,G1,sd);U(gG2,G2,sd);U(gWq,Wq,(size_t)D*D);U(gWk,Wk,(size_t)D*D);U(gWv,Wv,(size_t)D*D);U(gWo,Wo,(size_t)D*D);U(gWg,Wg,(size_t)HID*D);U(gWu,Wu,(size_t)HID*D);U(gWd,Wd,(size_t)D*HID);

    // n1 = RMSNorm(x,g1)
    g_rms(dX,gG1,dN1);
    // q=Wq*n1, k=Wk*n1, v=Wv*n1 (bias-free); then RoPE(q),RoPE(k)
    g_matvec_seq(gWq,dN1,dQ,D,D); g_matvec_seq(gWk,dN1,dK,D,D); g_matvec_seq(gWv,dN1,dV,D,D);
    g_rope_seq(dQ,dQr); g_rope_seq(dK,dKr);
    // attn = causal_attention(qr,kr,v,scale)  (single head: nheads=1)
    {unsigned nq=SEQ,nk=SEQ,d=D,nh=1,B=256; void*p[]={&dQr,&dKr,&dV,&dAt,&dSc,&nq,&nk,&d,&nh,&SCALE}; CK(cuLK_(K_at,(nq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
    // ao = Wo*attn;  h = x + ao
    g_matvec_seq(gWo,dAt,dAo,D,D); g_re(dX,dAo,dH);
    // n2 = RMSNorm(h,g2)
    g_rms(dH,gG2,dN2);
    // gate=Wg*n2, up=Wu*n2; sg=SwiGLU(gate,up); ff=Wd*sg;  y = h + ff
    g_matvec_seq(gWg,dN2,dGg,HID,D); g_matvec_seq(gWu,dN2,dUu,HID,D);
    {unsigned n=(unsigned)sh,B=256; void*p[]={&dGg,&dUu,&dSg,&n}; CK(cuLK_(K_sg,(n+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));}
    g_matvec_seq(gWd,dSg,dFf,D,HID); g_re(dH,dFf,dOut);

    CK(cuSY_()); CK(cuD_(out,dOut,sd*4));

    int ex=0; float ma=0; for(size_t i=0;i<sd;i++){uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d;}
    int launches = 1 /*rms1*/ + 3*SEQ /*qkv proj*/ + 2*SEQ /*rope q,k*/ + 1 /*attn*/ + SEQ /*Wo proj*/ + 1 /*res*/ + 1 /*rms2*/ + 2*SEQ /*gate,up proj*/ + 1 /*swiglu*/ + SEQ /*Wd proj*/ + 1 /*res*/;
    printf("device=%s\n", dn);
    printf("FULL llama decoder block (lblk-block-causal): RMSNorm -> QKV proj -> RoPE(q,k) -> causal attn -> Wo+res -> RMSNorm -> SwiGLU FFN(Wg,Wu,Wd)+res, %d launches\n", launches);
    printf("seq=%d d=%d HD=%d hid=%d scale=%g eps=%g  parity_bitexact=%d/%zu max_abs_diff=%g\n", SEQ,D,HD,HID,(double)SCALE,(double)EPS,ex,sd,(double)ma);
    printf("runtime_deps=%s only (Form-emitted PTX templates, driver JIT -O0; no nvcc/nvrtc/go/python/rust/shell/clang)\n", LIB());
    if(ex!=(int)sd){printf("FAIL not bit-exact\n");return 1;}
    printf("ok - the FULL llama decoder block ran end-to-end on the GPU, bit-exact to the lblk-block-causal recipe\n");
    return 0;
}

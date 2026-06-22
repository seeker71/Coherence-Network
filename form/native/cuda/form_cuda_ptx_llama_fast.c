// form_cuda_ptx_llama_fast.c — REAL llama3.2:3b on the Form-emitted GPU PTX kernels, FAST: the
// QUANTIZED weights stay RESIDENT on the GPU (~2.1GB) and are dequanted INSIDE the matvec kernel,
// still bit-exact to the recipe. Driver-only (nvcuda.dll). NO go/rust/clang/nvcc/nvrtc/python/shell.
//
// vs the streaming baseline (form_cuda_ptx_llama_real.c / _gen.c, ~19s/token): that path dequants all
// 28 layers to ~12GB of f32 on the CPU and re-uploads them EVERY token. Here we upload the raw Q4_K/Q6_K
// superblock bytes ONCE at startup and run the whole forward with the in-kernel-dequant matvec kernels
// (template_matvec_q4k.ptx / template_matvec_q6k.ptx), proven bit-exact in STAGE 1.
//
// Per-tensor quant (real llama3.2:3b): attn_q/k/output, ffn_gate/up = Q4_K ; attn_v, ffn_down,
// token_embd(tied head) = Q6_K ; norms = F32.
//
// STAGE 2 (this file's default): full 28-block forward + tied LM head over the prompt, resident weights.
//   GATE: predicts the SAME token as the streaming path (" Paris", id 12366) and the final residual
//   stream is bit-exact (uint32) to the CPU oracle (== form_cuda_ptx_llama_real.c). Reports tok/s.
// STAGE 3 ([--gen N] or [--kv N]): KV-cache incremental decode — see gen path below.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_llama_fast.exe form_cuda_ptx_llama_fast.c -lm
// Run:   form_cuda_ptx_llama_fast.exe <gguf-blob> [prompt] [--gen N] [--no-oracle]

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#undef IN
#undef OUT
typedef HMODULE H; static H O(const char*p){return LoadLibraryA(p);} static void*S(H h,const char*s){return (void*)(uintptr_t)GetProcAddress(h,s);} static const char*LIB(){return "nvcuda.dll";}
static double now_s(void){ LARGE_INTEGER f,c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c); return (double)c.QuadPart/(double)f.QuadPart; }
#else
#include <dlfcn.h>
typedef void*H; static H O(const char*p){return dlopen(p,RTLD_NOW|RTLD_LOCAL);} static void*S(H h,const char*s){return dlsym(h,s);} static const char*LIB(){return "libcuda.so.1";}
static double now_s(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec*1e-9; }
#endif
typedef int CUresult; typedef int CUdevice; typedef void*CUcontext,*CUmodule,*CUfunction,*CUstream; typedef unsigned long long CUdeviceptr;
#define OKr 0
#define J7 7
typedef CUresult(*Fi)(unsigned); typedef CUresult(*Fdg)(CUdevice*,int); typedef CUresult(*Fdn)(char*,int,CUdevice); typedef CUresult(*Fcc)(CUcontext*,unsigned,CUdevice);
typedef CUresult(*Fld)(CUmodule*,const void*,unsigned,int*,void**); typedef CUresult(*Fgf)(CUfunction*,CUmodule,const char*); typedef CUresult(*Fma)(CUdeviceptr*,size_t); typedef CUresult(*Ffr)(CUdeviceptr);
typedef CUresult(*Fh)(CUdeviceptr,const void*,size_t); typedef CUresult(*Fd)(void*,CUdeviceptr,size_t); typedef CUresult(*Flk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**); typedef CUresult(*Fsy)(void); typedef CUresult(*Fes)(CUresult,const char**);
typedef CUresult(*Fmi)(size_t*,size_t*);
typedef CUresult(*Fdd)(CUdeviceptr,CUdeviceptr,size_t);
static Fi cuInit_; static Fdg cuDG_; static Fdn cuDN_; static Fcc cuCC_; static Fld cuLD_; static Fgf cuGF_; static Fma cuMA_; static Ffr cuFR_; static Fh cuH_; static Fd cuD_; static Flk cuLK_; static Fsy cuSY_; static Fes cuES_; static Fmi cuMI_; static Fdd cuDD_;
static char jl[8192];
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); if(jl[0])fprintf(stderr,"JIT: %s\n",jl); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OKr)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}

// ====================================================================================
// GGUF reader + dequant — verbatim from gguf_dequant.c / the proven real.c.
// ====================================================================================
static FILE* F;
static uint32_t ru32(void){uint32_t v;fread(&v,4,1,F);return v;}
static uint64_t ru64(void){uint64_t v;fread(&v,8,1,F);return v;}
static char* rstr(uint64_t*o){uint64_t n=ru64();char*s=malloc(n+1);if(n)fread(s,1,n,F);s[n]=0;if(o)*o=n;return s;}
enum{T_U8,T_I8,T_U16,T_I16,T_U32,T_I32,T_F32,T_BOOL,T_STR,T_ARR,T_U64,T_I64,T_F64};
static int sz(uint32_t t){switch(t){case T_U8:case T_I8:case T_BOOL:return 1;case T_U16:case T_I16:return 2;case T_U32:case T_I32:case T_F32:return 4;case T_U64:case T_I64:case T_F64:return 8;default:return -1;}}
typedef struct { char name[96]; uint32_t nd; uint64_t dims[4]; uint32_t type; uint64_t off; } Tensor;
#define GGML_F32 0
#define GGML_F16 1
#define GGML_Q4_K 12
#define GGML_Q6_K 14
static float f16_to_f32(uint16_t h){
    uint32_t s=(h>>15)&1, e=(h>>10)&0x1F, m=h&0x3FF, bits;
    if(e==0){ if(m==0) bits=s<<31; else { e=127-15+1; while(!(m&0x400)){m<<=1;e--;} m&=0x3FF; bits=(s<<31)|(e<<23)|(m<<13);} }
    else if(e==0x1F) bits=(s<<31)|(0xFF<<23)|(m<<13);
    else bits=(s<<31)|((e-15+127)<<23)|(m<<13);
    float f; memcpy(&f,&bits,4); return f;
}
static void deq_q4k(const uint8_t*b,float*out){
    float d=f16_to_f32(*(const uint16_t*)b), dmin=f16_to_f32(*(const uint16_t*)(b+2));
    const uint8_t*scales=b+4, *qs=b+16;
    for(int i=0;i<256;i++){
        int c=i/64, within=i%64, half=within/32, l=within%32, j=2*c+half;
        int sc,mn;
        if(j<4){ sc=scales[j]&63; mn=scales[j+4]&63; }
        else   { sc=(scales[j+4]&0xF)|((scales[j-4]>>6)<<4); mn=(scales[j+4]>>4)|((scales[j]>>6)<<4); }
        uint8_t qb=qs[c*32+l]; int nib=(half==0)?(qb&0xF):(qb>>4);
        out[i]=(d*sc)*nib-(dmin*mn);
    }
}
static void deq_q6k(const uint8_t*b,float*out){
    const uint8_t*ql=b, *qh=b+128; const int8_t*scales=(const int8_t*)(b+192);
    float d=f16_to_f32(*(const uint16_t*)(b+208));
    for(int i=0;i<256;i++){
        int h=i/128, wi=i%128, l=wi%32, g=wi/32, is=l/16;
        int qlidx=h*64 + l + (g%2)*32;
        int nib=(g/2==0)?(ql[qlidx]&0xF):(ql[qlidx]>>4);
        int hi=(qh[h*32+l]>>(2*g))&3;
        int q=(nib|(hi<<4))-32;
        int scale=scales[h*8 + is + 2*g];
        out[i]=d*scale*q;
    }
}
static long tensor_data_start; static Tensor* TENS; static uint64_t NT;
static Tensor* find_tensor(const char*name){ for(uint64_t i=0;i<NT;i++) if(!strcmp(TENS[i].name,name)) return &TENS[i]; return NULL; }
static uint64_t numel(Tensor*t){ uint64_t n=1; for(uint32_t k=0;k<t->nd;k++) n*=t->dims[k]; return n; }
static int blocksize(uint32_t type){ return type==GGML_Q4_K?144:type==GGML_Q6_K?210:-1; }
static float* load_tensor_f32(Tensor*t){
    uint64_t n=numel(t); float*out=malloc(n*sizeof(float));
    long abs_off=tensor_data_start + (long)t->off; fseek(F,abs_off,SEEK_SET);
    if(t->type==GGML_F32){ fread(out,4,n,F); }
    else if(t->type==GGML_F16){ uint16_t*tmp=malloc(n*2); fread(tmp,2,n,F); for(uint64_t i=0;i<n;i++)out[i]=f16_to_f32(tmp[i]); free(tmp); }
    else if(t->type==GGML_Q4_K){ uint64_t nb=n/256; uint8_t blk[144]; for(uint64_t b=0;b<nb;b++){ fread(blk,1,144,F); deq_q4k(blk,out+b*256);} }
    else if(t->type==GGML_Q6_K){ uint64_t nb=n/256; uint8_t blk[210]; for(uint64_t b=0;b<nb;b++){ fread(blk,1,210,F); deq_q6k(blk,out+b*256);} }
    else { fprintf(stderr,"unsupported type %u\n",t->type); exit(1); }
    return out;
}
// read RAW quantized superblock bytes (no dequant): nb*blocksize bytes (caller frees).
static uint8_t* load_tensor_raw(Tensor*t,size_t*nbytes){
    uint64_t n=numel(t); uint64_t nb=n/256; int bs=blocksize(t->type);
    if(bs<0){fprintf(stderr,"load_tensor_raw: %s type %u not k-quant\n",t->name,t->type);exit(1);}
    size_t total=(size_t)nb*bs; uint8_t*raw=malloc(total);
    long abs_off=tensor_data_start+(long)t->off; fseek(F,abs_off,SEEK_SET);
    if(fread(raw,1,total,F)!=total){fprintf(stderr,"raw read short for %s\n",t->name);exit(1);}
    *nbytes=total; return raw;
}
static char** VOCAB; static uint64_t VOCAB_N;
static int64_t vocab_id(const char*s){ for(uint64_t i=0;i<VOCAB_N;i++) if(!strcmp(VOCAB[i],s)) return (int64_t)i; return -1; }

// ====================================================================================
// recipe-exact fp32 math — IDENTICAL to llama_forward.c / the proven real.c (the bit-exact oracle).
// ====================================================================================
static float fsq(float v){if(v<=0.0f)return 0.0f; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g;}
static float fexs(float x){float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0.0f?-x:x)>0.5f){x=x*0.5f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
static float sigm(float x){return 1.0f/(1.0f+fex(0.0f-x));}
static float swiglu(float g,float u){return (g*sigm(g))*u;}
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

// ====================================================================================
// model config (real llama3.2:3b)
// ====================================================================================
#define N_LAYERS   28
#define D_MODEL    3072
#define N_HEADS    24
#define N_KV_HEADS 8
#define HEAD_DIM   128
#define FFN_HIDDEN 8192
#define VOCAB_SIZE 128256
static float ROPE_BASE = 500000.0f;
static float RMS_EPS   = 1e-5f;
static const int Q_DIM  = N_HEADS*HEAD_DIM;     // 3072
static const int KV_DIM = N_KV_HEADS*HEAD_DIM;  // 1024
static float SCALE;                              // 1/sqrt(HEAD_DIM)

// ---- CPU oracle pieces (op-for-op == the proven real.c == the PTX kernels) — used only for the GATE ----
static void matvec(const float*W,const float*x,float*y,int outd,int ind){
    for(int o=0;o<outd;o++){ float a=0.0f; for(int l=ind;l>0;){ l--; float p=W[(size_t)o*ind+l]*x[l]; a=p+a; } y[o]=a; }
}
static void rmsnorm(const float*x,const float*g,float*out,int d){
    float ss=0.0f; for(int j=0;j<d;j++){ float xv=x[j]; ss=ss+xv*xv; }
    float meansq=ss/(float)d; float rms=fsq(meansq+RMS_EPS); float r=1.0f/rms;
    for(int j=0;j<d;j++) out[j]=(x[j]*r)*g[j];
}
static void rope_head(float*v,int pos){
    int HD=HEAD_DIM;
    for(int t=0;t<HD/2;t++){
        int hd=2*t; float e=(-1.0f*(float)hd)/((float)HD*1.0f); float freq=c_fpow(ROPE_BASE,e);
        float a=((float)pos*1.0f)*freq; float c=c_fcos(a), s=c_fsin(a);
        int i0=2*t, i1=2*t+1; float x0=v[i0], x1=v[i1];
        v[i0]=x0*c - x1*s; v[i1]=x0*s + x1*c;
    }
}
typedef struct { float *attn_norm,*ffn_norm,*Wq,*Wk,*Wv,*Wo,*Wg,*Wu,*Wd; } CpuBlock;
static void cpu_block(CpuBlock*B,float*x,int T,
                      float*n1,float*Kc,float*Vc,float*q,float*att,float*ao,
                      float*n2,float*gg,float*uu,float*sgv,float*ff,float*scores){
    for(int t=0;t<T;t++){
        float*xt=x+(size_t)t*D_MODEL; rmsnorm(xt,B->attn_norm,n1,D_MODEL);
        float*kt=Kc+(size_t)t*KV_DIM, *vt=Vc+(size_t)t*KV_DIM;
        matvec(B->Wk,n1,kt,KV_DIM,D_MODEL); matvec(B->Wv,n1,vt,KV_DIM,D_MODEL);
        for(int h=0;h<N_KV_HEADS;h++) rope_head(kt+h*HEAD_DIM, t);
    }
    for(int t=0;t<T;t++){
        float*xt=x+(size_t)t*D_MODEL; rmsnorm(xt,B->attn_norm,n1,D_MODEL);
        matvec(B->Wq,n1,q,Q_DIM,D_MODEL);
        for(int h=0;h<N_HEADS;h++) rope_head(q+h*HEAD_DIM, t);
        for(int h=0;h<N_HEADS;h++){
            int kvh=h/(N_HEADS/N_KV_HEADS); float*qh=q+h*HEAD_DIM; int nk=t+1;
            for(int j=0;j<nk;j++){ float*kj=Kc+(size_t)j*KV_DIM + kvh*HEAD_DIM; float a=0.0f; for(int l=HEAD_DIM;l>0;){ l--; float p=qh[l]*kj[l]; a=p+a; } scores[j]=a*SCALE; }
            float m=scores[0]; for(int j=1;j<nk;j++){ if(scores[j]>m)m=scores[j]; }
            float ssum=0.0f; for(int j=0;j<nk;j++){ float e=fex(scores[j]-m); scores[j]=e; ssum=ssum+e; }
            float rs=1.0f/ssum; for(int j=0;j<nk;j++) scores[j]=scores[j]*rs;
            float*oh=att+h*HEAD_DIM;
            for(int dmm=0;dmm<HEAD_DIM;dmm++){ float a=0.0f; for(int j=0;j<nk;j++){ float*vj=Vc+(size_t)j*KV_DIM + kvh*HEAD_DIM; float p=vj[dmm]*scores[j]; a=a+p; } oh[dmm]=a; }
        }
        matvec(B->Wo,att,ao,D_MODEL,Q_DIM);
        for(int j=0;j<D_MODEL;j++) xt[j]=xt[j]+ao[j];
        rmsnorm(xt,B->ffn_norm,n2,D_MODEL);
        matvec(B->Wg,n2,gg,FFN_HIDDEN,D_MODEL); matvec(B->Wu,n2,uu,FFN_HIDDEN,D_MODEL);
        for(int j=0;j<FFN_HIDDEN;j++) sgv[j]=swiglu(gg[j],uu[j]);
        matvec(B->Wd,sgv,ff,D_MODEL,FFN_HIDDEN);
        for(int j=0;j<D_MODEL;j++) xt[j]=xt[j]+ff[j];
    }
}

// ====================================================================================
// GPU kernels: the 6 proven Form-emitted PTX kernels + the 2 new in-kernel-dequant matvecs.
// ====================================================================================
static CUfunction K_rms,K_rope,K_gqa,K_gqad,K_re,K_sg,K_mvf32,K_mvq4k,K_mvq6k;
static CUfunction load_ptx(const char*dir,const char*fn,const char*ent){
    char p[1024]; snprintf(p,sizeof(p),"%s/%s",dir,fn);
    FILE*f=fopen(p,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",p);exit(1);}
    fseek(f,0,SEEK_END); long s=ftell(f); fseek(f,0,SEEK_SET); char*buf=malloc((size_t)s+1); if(fread(buf,1,(size_t)s,f)!=(size_t)s)exit(1); buf[s]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,buf,3,o,v)); CUfunction k; CK(cuGF_(&k,m,ent)); free(buf); return k;
}

// ---- RESIDENT quantized weight buffers: one device pointer per (layer, tensor) ----
// llama3.2:3b is MIXED-quant (Q4_K_M): attn_v / ffn_down are Q6_K on SOME layers and Q4_K on others.
// So the quant type is read PER TENSOR from the GGUF directory and the matching kernel is dispatched —
// never assumed. (tq/tk/.../td carry GGML_Q4_K or GGML_Q6_K for the layer's projections/FFN.)
typedef struct { CUdeviceptr Wq,Wk,Wv,Wo,Wg,Wu,Wd,G1,G2;
                 uint32_t tq,tk,tv,to,tg,tu,td; } DevBlock;  // W* raw quant bytes; t* = GGML type; G* f32 norms
static DevBlock DBLK[N_LAYERS];
static CUdeviceptr dEmbRaw; static uint32_t tEmb;  // token_embd raw bytes (tied LM head) + its quant type
static CUdeviceptr dGo;       // output_norm f32 resident
// per-layer RESIDENT K/V cache for STAGE 3 incremental decode: [SEQMAX x KV_DIM] each.
static CUdeviceptr dKcache[N_LAYERS], dVcache[N_LAYERS];
// activation buffers (resident across layers): dX is the residual stream [T*D].
static CUdeviceptr dX,dN1,dQ,dQr,dK,dKr,dV,dAtt,dSc,dAo,dN2,dGg,dUu,dSg,dFf,dXn,dLogits;
// decode-step single-row scratch (STAGE 3): one token through the stack.
static CUdeviceptr dx1,dn1_1,dq1,dqr1,dk1,dkr1,dv1,datt1,dsc1,dao1,dn2_1,dgg1,duu1,dsg1,dff1;
static int gT;

static void g_rms(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){
    unsigned rows=1,cols=D_MODEL,B=256;
    for(int t=0;t<gT;t++){ CUdeviceptr xi=in+(CUdeviceptr)t*D_MODEL*4, yo=out+(CUdeviceptr)t*D_MODEL*4;
        void*p[]={&xi,&g,&yo,&rows,&cols,&RMS_EPS}; CK(cuLK_(K_rms,1,1,1,B,1,1,0,NULL,p,NULL)); }
}
static void g_rms_one(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){
    unsigned rows=1,cols=D_MODEL,B=256; void*p[]={&in,&g,&out,&rows,&cols,&RMS_EPS}; CK(cuLK_(K_rms,1,1,1,B,1,1,0,NULL,p,NULL));
}
// in-kernel-dequant matvec over a resident QUANTIZED weight, per token: Y[t] = dequant(W) * X[t].
static void g_matvec_qk_seq(CUfunction K,CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256;
    for(int t=0;t<gT;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*ind*4, yo=Y+(CUdeviceptr)t*outd*4;
        void*p[]={&W,&xi,&yo,&rows,&cols}; CK(cuLK_(K,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
// single-vector in-kernel-dequant matvec: Y = dequant(W) * X. (LM head.)
static void g_matvec_qk_one(CUfunction K,CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256; void*p[]={&W,&X,&Y,&rows,&cols}; CK(cuLK_(K,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
static void g_rope_seq(CUdeviceptr X,CUdeviceptr Y,int dim){
    unsigned uHD=HEAD_DIM,un=(unsigned)dim,B=128,npairs=(unsigned)(dim/2);
    for(int t=0;t<gT;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*dim*4, yo=Y+(CUdeviceptr)t*dim*4; unsigned pos=(unsigned)t;
        void*p[]={&xi,&yo,&pos,&uHD,&un,&ROPE_BASE}; CK(cuLK_(K_rope,(npairs+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
static void g_residual(CUdeviceptr a,CUdeviceptr b,CUdeviceptr o,int n){
    unsigned un=(unsigned)n,B=256; void*p[]={&a,&b,&o,&un}; CK(cuLK_(K_re,(un+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
// pick the in-kernel-dequant matvec for a tensor's GGUF quant type.
static CUfunction kern_for(uint32_t type){
    if(type==GGML_Q4_K) return K_mvq4k;
    if(type==GGML_Q6_K) return K_mvq6k;
    fprintf(stderr,"FAIL no in-kernel-dequant matvec for quant type %u\n",type); exit(1);
}

// one decoder block on the GPU over resident dX [T*D], weights already RESIDENT (DBLK[L]).
// Mirrors the proven real.c gpu_block op-for-op — but the projections/FFN use the in-kernel-dequant
// matvec over the resident quantized bytes (NO per-layer upload).
static void gpu_block(DevBlock*B){
    g_rms(dX,B->G1,dN1);
    g_matvec_qk_seq(kern_for(B->tk),B->Wk,dN1,dK,KV_DIM,D_MODEL);   // attn_k
    g_matvec_qk_seq(kern_for(B->tv),B->Wv,dN1,dV,KV_DIM,D_MODEL);   // attn_v (Q4_K or Q6_K per layer)
    g_rope_seq(dK,dKr,KV_DIM);
    g_rms(dX,B->G1,dN1);
    g_matvec_qk_seq(kern_for(B->tq),B->Wq,dN1,dQ,Q_DIM,D_MODEL);    // attn_q
    g_rope_seq(dQ,dQr,Q_DIM);
    {
        unsigned unq=(unsigned)gT,unk=(unsigned)gT,uhd=HEAD_DIM,unhq=N_HEADS,unhkv=N_KV_HEADS;
        unsigned tot=(unsigned)gT*N_HEADS,Bk=256;
        void*p[]={&dQr,&dKr,&dV,&dAtt,&dSc,&unq,&unk,&uhd,&unhq,&unhkv,&SCALE};
        CK(cuLK_(K_gqa,(tot+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL));
    }
    g_matvec_qk_seq(kern_for(B->to),B->Wo,dAtt,dAo,D_MODEL,Q_DIM);  // attn_output
    g_residual(dX,dAo,dX,gT*D_MODEL);
    g_rms(dX,B->G2,dN2);
    g_matvec_qk_seq(kern_for(B->tg),B->Wg,dN2,dGg,FFN_HIDDEN,D_MODEL);  // ffn_gate
    g_matvec_qk_seq(kern_for(B->tu),B->Wu,dN2,dUu,FFN_HIDDEN,D_MODEL);  // ffn_up
    { unsigned n=(unsigned)gT*FFN_HIDDEN,Bk=256; void*p[]={&dGg,&dUu,&dSg,&n}; CK(cuLK_(K_sg,(n+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL)); }
    g_matvec_qk_seq(kern_for(B->td),B->Wd,dSg,dFf,D_MODEL,FFN_HIDDEN);  // ffn_down (Q4_K or Q6_K per layer)
    g_residual(dX,dFf,dX,gT*D_MODEL);
}

// ============================ STAGE 3: KV-cache incremental decode ============================
// PREFILL block for layer L: identical arithmetic to gpu_block over the prompt (gT=T0), but it ALSO
// persists this layer's roped-K and un-roped-V for every prompt position into dKcache[L]/dVcache[L].
// (The cached bytes are uint32-identical to what a re-forward would produce, so decode == streaming.)
static void gpu_block_prefill(DevBlock*B,int L){
    g_rms(dX,B->G1,dN1);
    g_matvec_qk_seq(kern_for(B->tk),B->Wk,dN1,dK,KV_DIM,D_MODEL);
    g_matvec_qk_seq(kern_for(B->tv),B->Wv,dN1,dV,KV_DIM,D_MODEL);
    g_rope_seq(dK,dKr,KV_DIM);
    // persist prompt K(roped)/V into this layer's cache (positions 0..T0-1).
    CK(cuDD_(dKcache[L],dKr,(size_t)gT*KV_DIM*4));
    CK(cuDD_(dVcache[L],dV ,(size_t)gT*KV_DIM*4));
    g_rms(dX,B->G1,dN1);
    g_matvec_qk_seq(kern_for(B->tq),B->Wq,dN1,dQ,Q_DIM,D_MODEL);
    g_rope_seq(dQ,dQr,Q_DIM);
    {   // prefill attention over the cache (== gpu_block's, but K/V from cache for clarity)
        unsigned unq=(unsigned)gT,unk=(unsigned)gT,uhd=HEAD_DIM,unhq=N_HEADS,unhkv=N_KV_HEADS;
        unsigned tot=(unsigned)gT*N_HEADS,Bk=256;
        void*p[]={&dQr,&dKcache[L],&dVcache[L],&dAtt,&dSc,&unq,&unk,&uhd,&unhq,&unhkv,&SCALE};
        CK(cuLK_(K_gqa,(tot+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL));
    }
    g_matvec_qk_seq(kern_for(B->to),B->Wo,dAtt,dAo,D_MODEL,Q_DIM);
    g_residual(dX,dAo,dX,gT*D_MODEL);
    g_rms(dX,B->G2,dN2);
    g_matvec_qk_seq(kern_for(B->tg),B->Wg,dN2,dGg,FFN_HIDDEN,D_MODEL);
    g_matvec_qk_seq(kern_for(B->tu),B->Wu,dN2,dUu,FFN_HIDDEN,D_MODEL);
    { unsigned n=(unsigned)gT*FFN_HIDDEN,Bk=256; void*p[]={&dGg,&dUu,&dSg,&n}; CK(cuLK_(K_sg,(n+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL)); }
    g_matvec_qk_seq(kern_for(B->td),B->Wd,dSg,dFf,D_MODEL,FFN_HIDDEN);
    g_residual(dX,dFf,dX,gT*D_MODEL);
}

// single-row helpers for the decode step (gT-independent; operate on one token).
static void g1_rms(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){
    unsigned rows=1,cols=D_MODEL,B=256; void*p[]={&in,&g,&out,&rows,&cols,&RMS_EPS}; CK(cuLK_(K_rms,1,1,1,B,1,1,0,NULL,p,NULL));
}
static void g1_matvec_qk(CUfunction K,CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256; void*p[]={&W,&X,&Y,&rows,&cols}; CK(cuLK_(K,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
static void g1_rope(CUdeviceptr X,CUdeviceptr Y,int dim,int pos){
    unsigned uHD=HEAD_DIM,un=(unsigned)dim,B=128,npairs=(unsigned)(dim/2),upos=(unsigned)pos;
    void*p[]={&X,&Y,&upos,&uHD,&un,&ROPE_BASE}; CK(cuLK_(K_rope,(npairs+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
static void g1_residual(CUdeviceptr a,CUdeviceptr b,CUdeviceptr o,int n){
    unsigned un=(unsigned)n,B=256; void*p[]={&a,&b,&o,&un}; CK(cuLK_(K_re,(un+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
// DECODE block for layer L at absolute position pos: forward the SINGLE new token (resident dx1),
// appending its K/V to the cache at slot pos and attending over the cached prefix [0..pos].
static void gpu_block_decode(DevBlock*B,int L,int pos){
    g1_rms(dx1,B->G1,dn1_1);
    g1_matvec_qk(kern_for(B->tk),B->Wk,dn1_1,dk1,KV_DIM,D_MODEL);
    g1_matvec_qk(kern_for(B->tv),B->Wv,dn1_1,dv1,KV_DIM,D_MODEL);
    g1_rope(dk1,dkr1,KV_DIM,pos);
    // append K_new(roped)/V_new at slot pos in the cache.
    CK(cuDD_(dKcache[L]+(CUdeviceptr)pos*KV_DIM*4, dkr1, (size_t)KV_DIM*4));
    CK(cuDD_(dVcache[L]+(CUdeviceptr)pos*KV_DIM*4, dv1 , (size_t)KV_DIM*4));
    g1_rms(dx1,B->G1,dn1_1);
    g1_matvec_qk(kern_for(B->tq),B->Wq,dn1_1,dq1,Q_DIM,D_MODEL);
    g1_rope(dq1,dqr1,Q_DIM,pos);
    {   // decode attention: single query at pos over cached K/V[0..pos]; one thread per q-head.
        unsigned uqpos=(unsigned)pos,uhd=HEAD_DIM,unhq=N_HEADS,unhkv=N_KV_HEADS,Bk=256;
        void*p[]={&dqr1,&dKcache[L],&dVcache[L],&datt1,&dsc1,&uqpos,&uhd,&unhq,&unhkv,&SCALE};
        CK(cuLK_(K_gqad,(N_HEADS+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL));
    }
    g1_matvec_qk(kern_for(B->to),B->Wo,datt1,dao1,D_MODEL,Q_DIM);
    g1_residual(dx1,dao1,dx1,D_MODEL);
    g1_rms(dx1,B->G2,dn2_1);
    g1_matvec_qk(kern_for(B->tg),B->Wg,dn2_1,dgg1,FFN_HIDDEN,D_MODEL);
    g1_matvec_qk(kern_for(B->tu),B->Wu,dn2_1,duu1,FFN_HIDDEN,D_MODEL);
    { unsigned n=(unsigned)FFN_HIDDEN,Bk=256; void*p[]={&dgg1,&duu1,&dsg1,&n}; CK(cuLK_(K_sg,(n+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL)); }
    g1_matvec_qk(kern_for(B->td),B->Wd,dsg1,dff1,D_MODEL,FFN_HIDDEN);
    g1_residual(dx1,dff1,dx1,D_MODEL);
}

static void decode_token(const char*s,char*out,int cap){
    int o=0; const unsigned char*p=(const unsigned char*)s;
    while(*p && o<cap-1){ if(p[0]==0xC4&&p[1]==0xA0){out[o++]=' ';p+=2;} else if(p[0]==0xC4&&p[1]==0x8A){out[o++]='\\';if(o<cap-1)out[o++]='n';p+=2;} else {out[o++]=(char)*p;p++;} }
    out[o]=0;
}
static void decode_token_raw(const char*s,char*out,int cap){
    int o=0; const unsigned char*p=(const unsigned char*)s;
    while(*p && o<cap-1){ if(p[0]==0xC4&&p[1]==0xA0){out[o++]=' ';p+=2;} else if(p[0]==0xC4&&p[1]==0x8A){out[o++]='\n';p+=2;} else {out[o++]=(char)*p;p++;} }
    out[o]=0;
}

// full prompt forward on RESIDENT weights, GPU tied LM head, argmax last position. Returns token id.
static int fast_forward_argmax(const int*seq,int T,const float*token_embd,float*logit_out){
    size_t sd=(size_t)T*D_MODEL;
    float*x=malloc(sd*4);
    for(int t=0;t<T;t++) memcpy(x+(size_t)t*D_MODEL, token_embd+(size_t)seq[t]*D_MODEL, D_MODEL*sizeof(float));
    gT=T; CK(cuH_(dX,x,sd*4));
    for(int L=0;L<N_LAYERS;L++) gpu_block(&DBLK[L]);
    CUdeviceptr dXlast=dX+(CUdeviceptr)(T-1)*D_MODEL*4;
    g_rms_one(dXlast,dGo,dXn);
    g_matvec_qk_one(kern_for(tEmb),dEmbRaw,dXn,dLogits,VOCAB_SIZE,D_MODEL);  // tied head, in-kernel dequant
    CK(cuSY_());
    CK(cuD_(logit_out,dLogits,(size_t)VOCAB_SIZE*4));
    int best=-1; float bestv=-1e30f; for(int v=0;v<VOCAB_SIZE;v++){ if(logit_out[v]>bestv){bestv=logit_out[v];best=v;} }
    free(x); return best;
}

// argmax of dLogits (already computed on GPU) into host logit_out; returns token id.
static int head_argmax(float*logit_out){
    CK(cuD_(logit_out,dLogits,(size_t)VOCAB_SIZE*4));
    int best=-1; float bestv=-1e30f; for(int v=0;v<VOCAB_SIZE;v++){ if(logit_out[v]>bestv){bestv=logit_out[v];best=v;} }
    return best;
}
// STAGE 3: KV-cache PREFILL — forward the whole prompt once, persisting each layer's K/V, then the
// tied head over the last position. Fills the caches for positions 0..T0-1. Returns the first token id.
static int kv_prefill(const int*seq,int T0,const float*token_embd,float*logit_out){
    size_t sd=(size_t)T0*D_MODEL; float*x=malloc(sd*4);
    for(int t=0;t<T0;t++) memcpy(x+(size_t)t*D_MODEL, token_embd+(size_t)seq[t]*D_MODEL, D_MODEL*sizeof(float));
    gT=T0; CK(cuH_(dX,x,sd*4));
    for(int L=0;L<N_LAYERS;L++) gpu_block_prefill(&DBLK[L],L);
    CUdeviceptr dXlast=dX+(CUdeviceptr)(T0-1)*D_MODEL*4;
    g_rms_one(dXlast,dGo,dXn);
    g_matvec_qk_one(kern_for(tEmb),dEmbRaw,dXn,dLogits,VOCAB_SIZE,D_MODEL);
    CK(cuSY_());
    free(x); return head_argmax(logit_out);
}
// STAGE 3: KV-cache DECODE step — forward ONLY the new token (id `tok`) at absolute position `pos`
// through all 28 blocks (appending to the cache), final norm + tied head, argmax. Returns next id.
static int kv_decode_step(int tok,int pos,const float*token_embd,float*logit_out){
    // embed the single new token into dx1.
    CK(cuH_(dx1, token_embd+(size_t)tok*D_MODEL, (size_t)D_MODEL*4));
    for(int L=0;L<N_LAYERS;L++) gpu_block_decode(&DBLK[L],L,pos);
    g_rms_one(dx1,dGo,dXn);
    g_matvec_qk_one(kern_for(tEmb),dEmbRaw,dXn,dLogits,VOCAB_SIZE,D_MODEL);
    CK(cuSY_());
    return head_argmax(logit_out);
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf> [prompt] [--gen N] [--kv N] [--no-oracle]\n",argv[0]);return 1;}
    const char*prompt="The capital of France is"; int n_generate=0; int n_kv=0; int do_oracle=1;
    for(int i=2;i<argc;i++){
        if(!strcmp(argv[i],"--gen")&&i+1<argc){ n_generate=atoi(argv[++i]); }
        else if(!strcmp(argv[i],"--kv")&&i+1<argc){ n_kv=atoi(argv[++i]); }
        else if(!strcmp(argv[i],"--no-oracle")){ do_oracle=0; }
        else prompt=argv[i];
    }

    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open failed\n");return 1;}
    char magic[4]; fread(magic,1,4,F); if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    ru32(); NT=ru64(); uint64_t nkv=ru64(); uint32_t alignment=32;
    for(uint64_t i=0;i<nkv;i++){ uint64_t kl; char*k=rstr(&kl); uint32_t vt=ru32();
        if(vt==T_STR){uint64_t sl;char*s=rstr(&sl);free(s);}
        else if(vt==T_ARR){uint32_t et=ru32();uint64_t cnt=ru64();
            if(et==T_STR && !strcmp(k,"tokenizer.ggml.tokens")){ VOCAB_N=cnt; VOCAB=malloc(cnt*sizeof(char*)); for(uint64_t j=0;j<cnt;j++){uint64_t sl;VOCAB[j]=rstr(&sl);} }
            else if(et==T_STR){ for(uint64_t j=0;j<cnt;j++){uint64_t sl;char*s=rstr(&sl);free(s);} }
            else fseek(F,(long)(sz(et)*cnt),SEEK_CUR);
        } else { if(!strcmp(k,"general.alignment")){uint32_t v=ru32();alignment=v;} else fseek(F,sz(vt),SEEK_CUR); }
        free(k);
    }
    TENS=malloc(NT*sizeof(Tensor));
    for(uint64_t i=0;i<NT;i++){ uint64_t nl; char*tn=rstr(&nl); strncpy(TENS[i].name,tn,95);TENS[i].name[95]=0;free(tn);
        TENS[i].nd=ru32(); for(uint32_t k=0;k<4;k++)TENS[i].dims[k]=1; for(uint32_t k=0;k<TENS[i].nd;k++)TENS[i].dims[k]=ru64();
        TENS[i].type=ru32(); TENS[i].off=ru64(); }
    long pos=ftell(F); tensor_data_start=((pos+alignment-1)/alignment)*alignment;
    if(!VOCAB){fprintf(stderr,"FAIL no tokenizer.ggml.tokens\n");return 1;}

    #define SEQMAX 256
    int seq[SEQMAX]; int T=0; seq[T++]=128000;
    { const char*p=prompt; char word[256]; int first=1;
      while(*p){ while(*p==' ')p++; if(!*p)break; int wl=0; while(*p&&*p!=' '&&wl<250)word[wl++]=*p++; word[wl]=0;
        char tok[260]; if(first)strcpy(tok,word); else {tok[0]=(char)0xC4;tok[1]=(char)0xA0;strcpy(tok+2,word);} first=0;
        int64_t id=vocab_id(tok); if(id<0){fprintf(stderr,"FAIL no vocab token for \"%s\"\n",word);return 1;}
        if(T>=SEQMAX){fprintf(stderr,"FAIL prompt too long\n");return 1;} seq[T++]=(int)id; } }
    int T0=T;
    if(T0+n_generate>SEQMAX) n_generate=SEQMAX-T0;
    if(T0+n_kv>SEQMAX) n_kv=SEQMAX-T0;
    int prompt_seq[SEQMAX]; for(int i=0;i<T0;i++) prompt_seq[i]=seq[i];  // snapshot for --kv

    printf("=== form_cuda_ptx_llama_fast — REAL llama3.2:3b, RESIDENT quantized weights, in-kernel dequant ===\n");
    printf("vocab=%llu rope_base=%.0f rms_eps=%g  config: %d blocks d=%d nh=%d nkv=%d hd=%d ffn=%d\n",
        (unsigned long long)VOCAB_N,ROPE_BASE,RMS_EPS,N_LAYERS,D_MODEL,N_HEADS,N_KV_HEADS,HEAD_DIM,FFN_HIDDEN);
    printf("prompt=\"%s\"  prompt tokens(%d): ",prompt,T);
    for(int i=0;i<T;i++){ char d[300]; if(seq[i]==128000)strcpy(d,"<BOS>"); else decode_token(VOCAB[seq[i]],d,sizeof(d)); printf("[%d:'%s'] ",seq[i],d); }
    printf("\n");

    { float g=(float)HEAD_DIM; for(int i=0;i<60;i++)g=0.5f*(g+(float)HEAD_DIM/g); SCALE=1.0f/g; }

    // ---- driver bootstrap ----
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuFR_=(Ffr)RS(drv,"cuMemFree_v2");
    cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString"); cuMI_=(Fmi)S(drv,"cuMemGetInfo_v2"); cuDD_=(Fdd)RS(drv,"cuMemcpyDtoD_v2");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    printf("device=%s  runtime_deps=%s only\n",dn,LIB());

    const char*dir=".";
    K_rms   =load_ptx(dir,"template_rmsnorm.ptx","form_rmsnorm_f32");
    K_rope  =load_ptx(dir,"template_rope_llama.ptx","form_rope_llama_f32");
    K_gqa   =load_ptx(dir,"template_attention_gqa.ptx","form_attention_gqa_f32");
    K_gqad  =load_ptx(dir,"template_attention_gqa_decode.ptx","form_attention_gqa_decode_f32");
    K_re    =load_ptx(dir,"template_residual.ptx","form_residual_f32");
    K_sg    =load_ptx(dir,"template_swiglu.ptx","form_swiglu_f32");
    K_mvf32 =load_ptx(dir,"template_matvec.ptx","form_matvec_f32");
    K_mvq4k =load_ptx(dir,"template_matvec_q4k.ptx","form_matvec_q4k_f32");
    K_mvq6k =load_ptx(dir,"template_matvec_q6k.ptx","form_matvec_q6k_f32");
    printf("loaded 9 Form-emitted PTX kernels (rmsnorm,rope_llama,attention_gqa,attention_gqa_decode,residual,swiglu,matvec_f32,matvec_q4k,matvec_q6k)\n");

    // ================= UPLOAD: all quantized weights RESIDENT, once =================
    printf("\n--- uploading all 28 layers' RAW quantized weights to the GPU (resident, once) ---\n");
    double t_up0=now_s();
    size_t resident_bytes=0;
    char nm[64];
    // upload a quantized tensor RAW and capture its GGUF quant type into a type slot.
    #define UPL_Q(devp,typ,fmt) do{ snprintf(nm,sizeof(nm),fmt,L); Tensor*t=find_tensor(nm); if(!t){fprintf(stderr,"FAIL missing %s\n",nm);return 1;} (typ)=t->type; size_t nb; uint8_t*raw=load_tensor_raw(t,&nb); CK(cuMA_(&(devp),nb)); CK(cuH_(devp,raw,nb)); free(raw); resident_bytes+=nb; }while(0)
    #define UPL_F32(devp,fmt) do{ snprintf(nm,sizeof(nm),fmt,L); Tensor*t=find_tensor(nm); if(!t){fprintf(stderr,"FAIL missing %s\n",nm);return 1;} float*a=load_tensor_f32(t); size_t nb=(size_t)numel(t)*4; CK(cuMA_(&(devp),nb)); CK(cuH_(devp,a,nb)); free(a); resident_bytes+=nb; }while(0)
    int n_q6k=0,n_q4k=0;
    for(int L=0;L<N_LAYERS;L++){
        UPL_F32(DBLK[L].G1,"blk.%d.attn_norm.weight");
        UPL_F32(DBLK[L].G2,"blk.%d.ffn_norm.weight");
        UPL_Q(DBLK[L].Wq,DBLK[L].tq,"blk.%d.attn_q.weight");
        UPL_Q(DBLK[L].Wk,DBLK[L].tk,"blk.%d.attn_k.weight");
        UPL_Q(DBLK[L].Wv,DBLK[L].tv,"blk.%d.attn_v.weight");        // Q4_K or Q6_K per layer
        UPL_Q(DBLK[L].Wo,DBLK[L].to,"blk.%d.attn_output.weight");
        UPL_Q(DBLK[L].Wg,DBLK[L].tg,"blk.%d.ffn_gate.weight");
        UPL_Q(DBLK[L].Wu,DBLK[L].tu,"blk.%d.ffn_up.weight");
        UPL_Q(DBLK[L].Wd,DBLK[L].td,"blk.%d.ffn_down.weight");      // Q4_K or Q6_K per layer
        uint32_t ts[7]={DBLK[L].tq,DBLK[L].tk,DBLK[L].tv,DBLK[L].to,DBLK[L].tg,DBLK[L].tu,DBLK[L].td};
        for(int z=0;z<7;z++){ if(ts[z]==GGML_Q6_K)n_q6k++; else if(ts[z]==GGML_Q4_K)n_q4k++; }
        fprintf(stderr,"  uploaded layer %d/%d  (attn_v=%s ffn_down=%s)\r",L+1,N_LAYERS,
            DBLK[L].tv==GGML_Q6_K?"Q6_K":"Q4_K", DBLK[L].td==GGML_Q6_K?"Q6_K":"Q4_K"); fflush(stderr);
    }
    fprintf(stderr,"\n");
    // tied LM head (token_embd, Q6_K) raw resident; output_norm f32 resident.
    { Tensor*te=find_tensor("token_embd.weight"); if(!te){fprintf(stderr,"FAIL no token_embd\n");return 1;} tEmb=te->type; size_t nb; uint8_t*raw=load_tensor_raw(te,&nb); CK(cuMA_(&dEmbRaw,nb)); CK(cuH_(dEmbRaw,raw,nb)); free(raw); resident_bytes+=nb; }
    { Tensor*on=find_tensor("output_norm.weight"); float*a=load_tensor_f32(on); CK(cuMA_(&dGo,(size_t)D_MODEL*4)); CK(cuH_(dGo,a,(size_t)D_MODEL*4)); free(a); resident_bytes+=(size_t)D_MODEL*4; }
    printf("mixed quant: %d Q4_K + %d Q6_K projection/FFN tensors across %d layers; tied head = %s\n",
        n_q4k,n_q6k,N_LAYERS,tEmb==GGML_Q6_K?"Q6_K":"Q4_K");
    double t_up1=now_s();
    printf("resident quantized weights = %.3f GB   upload time = %.2fs\n",resident_bytes/1e9,t_up1-t_up0);
    if(cuMI_){ size_t fr=0,tot=0; if(cuMI_(&fr,&tot)==OKr) printf("GPU memory: %.2f GB free / %.2f GB total after upload\n",fr/1e9,tot/1e9); }

    // ---- token_embd as f32 on host for the initial residual embedding + the CPU oracle (matches real.c) ----
    Tensor*te=find_tensor("token_embd.weight"); float*token_embd=load_tensor_f32(te);
    Tensor*on=find_tensor("output_norm.weight"); float*output_norm=load_tensor_f32(on);

    // ---- allocate activation buffers (sized to max sequence) ----
    int TMAX=T0; if(T0+n_generate>TMAX)TMAX=T0+n_generate; if(T0+n_kv>TMAX)TMAX=T0+n_kv;
    size_t sd=(size_t)TMAX*D_MODEL, skv=(size_t)TMAX*KV_DIM, sh=(size_t)TMAX*FFN_HIDDEN;
    CK(cuMA_(&dX,sd*4)); CK(cuMA_(&dN1,sd*4)); CK(cuMA_(&dQ,sd*4)); CK(cuMA_(&dQr,sd*4));
    CK(cuMA_(&dK,skv*4)); CK(cuMA_(&dKr,skv*4)); CK(cuMA_(&dV,skv*4));
    CK(cuMA_(&dAtt,sd*4)); CK(cuMA_(&dSc,(size_t)TMAX*N_HEADS*TMAX*4)); CK(cuMA_(&dAo,sd*4));
    CK(cuMA_(&dN2,sd*4)); CK(cuMA_(&dGg,sh*4)); CK(cuMA_(&dUu,sh*4)); CK(cuMA_(&dSg,sh*4)); CK(cuMA_(&dFf,sd*4));
    CK(cuMA_(&dXn,(size_t)D_MODEL*4)); CK(cuMA_(&dLogits,(size_t)VOCAB_SIZE*4));
    // per-layer K/V cache (resident, [TMAX x KV_DIM]) + single-token decode scratch (STAGE 3).
    for(int L=0;L<N_LAYERS;L++){ CK(cuMA_(&dKcache[L],(size_t)TMAX*KV_DIM*4)); CK(cuMA_(&dVcache[L],(size_t)TMAX*KV_DIM*4)); }
    CK(cuMA_(&dx1,(size_t)D_MODEL*4)); CK(cuMA_(&dn1_1,(size_t)D_MODEL*4)); CK(cuMA_(&dq1,(size_t)Q_DIM*4)); CK(cuMA_(&dqr1,(size_t)Q_DIM*4));
    CK(cuMA_(&dk1,(size_t)KV_DIM*4)); CK(cuMA_(&dkr1,(size_t)KV_DIM*4)); CK(cuMA_(&dv1,(size_t)KV_DIM*4));
    CK(cuMA_(&datt1,(size_t)Q_DIM*4)); CK(cuMA_(&dsc1,(size_t)N_HEADS*TMAX*4)); CK(cuMA_(&dao1,(size_t)D_MODEL*4));
    CK(cuMA_(&dn2_1,(size_t)D_MODEL*4)); CK(cuMA_(&dgg1,(size_t)FFN_HIDDEN*4)); CK(cuMA_(&duu1,(size_t)FFN_HIDDEN*4)); CK(cuMA_(&dsg1,(size_t)FFN_HIDDEN*4)); CK(cuMA_(&dff1,(size_t)D_MODEL*4));

    // ================= STAGE 2: full-prompt forward on resident weights =================
    printf("\n--- STAGE 2: full %d-block forward on RESIDENT weights (in-kernel dequant), tied LM head ---\n",N_LAYERS);
    float*logits=malloc((size_t)VOCAB_SIZE*4);
    // warm + timed forward
    double t_f0=now_s();
    int next=fast_forward_argmax(seq,T,token_embd,logits);
    double t_f1=now_s();
    char dec[300]; decode_token(VOCAB[next],dec,sizeof(dec));
    printf("predicted next token id=%d  string=\"%s\"  logit=%.4f\n",next,dec,logits[next]);
    printf("expected (ollama greedy / streaming baseline): \" Paris\" (id 12366)\n");
    printf("forward time (prompt, T=%d) = %.3fs   => %.3f tok/s for a full-prompt forward\n",T,t_f1-t_f0,1.0/(t_f1-t_f0));
    if(next==12366) printf("MATCH — resident-quantized in-kernel-dequant forward predicts \" Paris\".\n");
    else printf("MISMATCH — predicted id=%d not 12366 (reported honestly).\n",next);

    // ---- GATE: final residual stream bit-exact vs the CPU oracle (== form_cuda_ptx_llama_real.c) ----
    if(do_oracle){
        printf("\n--- GATE: final residual stream (28 blocks) bit-exact vs CPU oracle ---\n");
        // pull the GPU residual stream (before final norm/head)
        size_t sdT=(size_t)T*D_MODEL; float*xf=malloc(sdT*4); CK(cuD_(xf,dX,sdT*4));
        // CPU oracle: same 28 blocks on dequant-to-f32 weights
        float*xc=malloc(sdT*4);
        for(int t=0;t<T;t++) memcpy(xc+(size_t)t*D_MODEL, token_embd+(size_t)seq[t]*D_MODEL, D_MODEL*sizeof(float));
        float*n1=malloc(D_MODEL*4),*Kc=malloc((size_t)T*KV_DIM*4),*Vc=malloc((size_t)T*KV_DIM*4),*q=malloc(Q_DIM*4),*att=malloc(Q_DIM*4),*ao=malloc(D_MODEL*4);
        float*n2=malloc(D_MODEL*4),*gg=malloc(FFN_HIDDEN*4),*uu=malloc(FFN_HIDDEN*4),*sgv=malloc(FFN_HIDDEN*4),*ff=malloc(D_MODEL*4),*scores=malloc((size_t)T*4);
        for(int L=0;L<N_LAYERS;L++){
            CpuBlock bc; char nmc[64];
            #define LDC(field,fmt) snprintf(nmc,sizeof(nmc),fmt,L); { Tensor*t=find_tensor(nmc); bc.field=load_tensor_f32(t); }
            LDC(attn_norm,"blk.%d.attn_norm.weight"); LDC(ffn_norm,"blk.%d.ffn_norm.weight");
            LDC(Wq,"blk.%d.attn_q.weight"); LDC(Wk,"blk.%d.attn_k.weight"); LDC(Wv,"blk.%d.attn_v.weight"); LDC(Wo,"blk.%d.attn_output.weight");
            LDC(Wg,"blk.%d.ffn_gate.weight"); LDC(Wu,"blk.%d.ffn_up.weight"); LDC(Wd,"blk.%d.ffn_down.weight");
            #undef LDC
            cpu_block(&bc,xc,T,n1,Kc,Vc,q,att,ao,n2,gg,uu,sgv,ff,scores);
            free(bc.attn_norm);free(bc.ffn_norm);free(bc.Wq);free(bc.Wk);free(bc.Wv);free(bc.Wo);free(bc.Wg);free(bc.Wu);free(bc.Wd);
        }
        int exf=0; float maf=0; int fdt=-1,fdj=-1;
        for(size_t i=0;i<sdT;i++){uint32_t a,b; memcpy(&a,&xf[i],4); memcpy(&b,&xc[i],4); if(a==b)exf++; else if(fdt<0){fdt=(int)(i/D_MODEL);fdj=(int)(i%D_MODEL);} float d2=xf[i]-xc[i]; if(d2<0)d2=-d2; if(d2>maf)maf=d2;}
        printf("residual-stream parity (resident-fast GPU vs CPU oracle): %d/%zu bit-exact   max_abs_diff=%g\n",exf,sdT,(double)maf);
        if(exf==(int)sdT) printf("  -> the resident-quantized in-kernel-dequant forward is bit-exact (uint32) to the oracle at every position.\n");
        else printf("  -> named-epsilon: first diff at token %d dim %d, max_abs_diff=%g.\n",fdt,fdj,(double)maf);
        free(xf);free(xc);free(n1);free(Kc);free(Vc);free(q);free(att);free(ao);free(n2);free(gg);free(uu);free(sgv);free(ff);free(scores);
    }

    // ================= STAGE 3-lite here: naive resident generation (no KV-cache) for tok/s =================
    // (Full KV-cache incremental decode is in the --kv path; this --gen re-forwards the whole sequence
    //  each step but with RESIDENT weights, so it already crushes the streaming baseline. It also lets us
    //  show the text matches before the KV-cache step.)
    if(n_generate>0){
        printf("\n--- generating %d tokens (resident weights, full re-forward per token, greedy) ---\n",n_generate);
        char cont[8192]; int cl=0; cont[0]=0; int first_gen=-1;
        double tg0=now_s();
        for(int g=0;g<n_generate;g++){
            int nx=fast_forward_argmax(seq,T,token_embd,logits);
            if(g==0)first_gen=nx;
            seq[T++]=nx; char d[300]; decode_token_raw(VOCAB[nx],d,sizeof(d));
            for(int q=0;d[q]&&cl<(int)sizeof(cont)-1;q++) cont[cl++]=d[q]; cont[cl]=0;
            printf("%s",d); fflush(stdout);
        }
        double tg1=now_s();
        printf("\n");
        char ptext[2048]; int pl=0; ptext[0]=0;
        for(int i=1;i<T0;i++){ char d[300]; decode_token_raw(VOCAB[seq[i]],d,sizeof(d)); for(int q=0;d[q]&&pl<(int)sizeof(ptext)-1;q++) ptext[pl++]=d[q]; } ptext[pl]=0;
        const char*pd=ptext; if(pd[0]==' ')pd++;
        printf("full text: \"%s%s\"\n",pd,cont);
        printf("generation: %d tokens in %.2fs => %.3f tok/s (resident, no KV-cache)\n",n_generate,tg1-tg0,n_generate/(tg1-tg0));
        char fd[300]; decode_token(VOCAB[first_gen],fd,sizeof(fd));
        printf("first generated token: id=%d \"%s\"  %s\n",first_gen,fd, first_gen==12366?"(MATCH \" Paris\")":"(reported honestly)");
    }

    // ================= STAGE 3: KV-cache incremental decode =================
    if(n_kv>0){
        printf("\n--- STAGE 3: KV-cache incremental decode of %d tokens (forward only the NEW token/step) ---\n",n_kv);
        int kseq[SEQMAX]; for(int i=0;i<T0;i++) kseq[i]=prompt_seq[i]; int kT=T0;
        char cont[8192]; int cl=0; cont[0]=0; int first_gen=-1;
        // prefill (whole prompt once) — also fills the K/V caches for positions 0..T0-1.
        double tp0=now_s();
        int nx=kv_prefill(kseq,T0,token_embd,logits);
        double tp1=now_s();
        printf("prefill (%d prompt tokens) = %.3fs\n",T0,tp1-tp0);
        // incremental decode loop: each step forwards ONLY the new token at its absolute position.
        double td0=now_s();
        for(int g=0;g<n_kv;g++){
            if(g==0)first_gen=nx;
            kseq[kT++]=nx; char d[300]; decode_token_raw(VOCAB[nx],d,sizeof(d));
            for(int q=0;d[q]&&cl<(int)sizeof(cont)-1;q++) cont[cl++]=d[q]; cont[cl]=0;
            printf("%s",d); fflush(stdout);
            if(g==n_kv-1) break;                 // stop after emitting the n_kv-th token
            // decode the just-appended token at position kT-1 to get the NEXT token.
            nx=kv_decode_step(kseq[kT-1], kT-1, token_embd, logits);
        }
        double td1=now_s();
        printf("\n");
        char ptext[2048]; int pl=0; ptext[0]=0;
        for(int i=1;i<T0;i++){ char d[300]; decode_token_raw(VOCAB[prompt_seq[i]],d,sizeof(d)); for(int q=0;d[q]&&pl<(int)sizeof(ptext)-1;q++) ptext[pl++]=d[q]; } ptext[pl]=0;
        const char*pd=ptext; if(pd[0]==' ')pd++;
        printf("full text: \"%s%s\"\n",pd,cont);
        printf("KV-cache decode: %d tokens, decode %.3fs (%.3f tok/s decode), prefill %.3fs, total %.3fs => %.3f tok/s overall\n",
            n_kv, td1-td0, n_kv/(td1-td0), tp1-tp0, (td1-td0)+(tp1-tp0), n_kv/((td1-td0)+(tp1-tp0)));
        char fd[300]; decode_token(VOCAB[first_gen],fd,sizeof(fd));
        printf("first generated token: id=%d \"%s\"  %s\n",first_gen,fd, first_gen==12366?"(MATCH \" Paris\")":"(reported honestly)");
        // ---- GATE: KV-cache text must equal the naive resident re-forward (= streaming) text ----
        if(do_oracle){
            printf("\n--- GATE: KV-cache generated ids vs naive resident re-forward (== streaming) ids ---\n");
            int rseq[SEQMAX]; for(int i=0;i<T0;i++) rseq[i]=prompt_seq[i]; int rT=T0; int match=1,firstdiff=-1;
            for(int g=0;g<n_kv;g++){
                int rnx=fast_forward_argmax(rseq,rT,token_embd,logits);
                rseq[rT++]=rnx;
                if(rnx!=kseq[T0+g]){ match=0; if(firstdiff<0)firstdiff=g; }
            }
            printf("KV ids: "); for(int g=0;g<n_kv;g++)printf("%d ",kseq[T0+g]); printf("\n");
            printf("ref ids: "); for(int g=0;g<n_kv;g++)printf("%d ",rseq[T0+g]); printf("\n");
            if(match) printf("GATE PASS — KV-cache decode produces the IDENTICAL token sequence as the full re-forward (== streaming).\n");
            else printf("GATE FAIL — first divergence at generated token %d (KV=%d ref=%d).\n",firstdiff,kseq[T0+firstdiff],rseq[T0+firstdiff]);
        }
    }

    printf("\n=== form_cuda_ptx_llama_fast done ===\n");
    return 0;
}

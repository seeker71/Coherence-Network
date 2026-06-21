// form_cuda_ptx_llama_gen.c — the REAL llama3.2:3b WRITING a continuation, end-to-end on the
// Form-EMITTED GPU PTX kernels (driver-only nvcuda.dll). NO go/rust/clang/nvcc/nvrtc/python/shell.
//
// Built directly on the proven form_cuda_ptx_llama_real.c (block-0 bit-exact 18432/18432, full
// 28-block forward predicting " Paris" id 12366). Reuses its GGUF reader, dequant, recipe-exact
// fp32 oracle math, weight-streaming, and the SIX Form-emitted PTX kernels wholesale.
//
// TWO additions over the proven forward:
//   1. The TIED LM-head matvec (logits[v] = token_embd[v] · final_hidden, 128256 x 3072) now runs
//      on the GPU via template_matvec.ptx (form_matvec_f32) — one thread per output row, exactly
//      like every other projection. So the ENTIRE forward incl. the head runs on the PTX kernels.
//      (The final-position RMSNorm also runs on the GPU rmsnorm kernel.)
//   2. Autoregressive GENERATION: tokenize the prompt -> full GPU forward -> argmax last position ->
//      next token id -> APPEND -> re-forward. Repeat N times (default 8). No KV-cache yet: each token
//      is a full 28-block forward re-streaming all 3B params, so it is SLOW (minutes/token) by design
//      — correctness/coherence over speed. After each token we detokenize and print so progress shows.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_llama_gen.exe form_cuda_ptx_llama_gen.c -lm
// Run:   form_cuda_ptx_llama_gen.exe <gguf-blob> [prompt] [n_generate]
//        default prompt "The capital of France is", n_generate=8.
//        Expect first generated token " Paris" (id 12366), then a coherent continuation.

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
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
typedef CUresult(*Fld)(CUmodule*,const void*,unsigned,int*,void**); typedef CUresult(*Fgf)(CUfunction*,CUmodule,const char*); typedef CUresult(*Fma)(CUdeviceptr*,size_t); typedef CUresult(*Ffr)(CUdeviceptr);
typedef CUresult(*Fh)(CUdeviceptr,const void*,size_t); typedef CUresult(*Fd)(void*,CUdeviceptr,size_t); typedef CUresult(*Flk)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**); typedef CUresult(*Fsy)(void); typedef CUresult(*Fes)(CUresult,const char**);
static Fi cuInit_; static Fdg cuDG_; static Fdn cuDN_; static Fcc cuCC_; static Fld cuLD_; static Fgf cuGF_; static Fma cuMA_; static Ffr cuFR_; static Fh cuH_; static Fd cuD_; static Flk cuLK_; static Fsy cuSY_; static Fes cuES_;
static char jl[8192];
static void die(const char*w,CUresult r){const char*m="?"; if(cuES_)cuES_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); if(jl[0])fprintf(stderr,"JIT: %s\n",jl); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=OKr)die(#c,_r);}while(0)
static void*RS(H h,const char*n){void*p=S(h,n); if(!p){fprintf(stderr,"FAIL %s\n",n);exit(1);} return p;}

// ====================================================================================
// GGUF reader + dequant — reused verbatim from gguf_dequant.c / llama_forward.c / the proven real.c.
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
static float* load_tensor_f32(Tensor*t){
    uint64_t n=numel(t); float*out=malloc(n*sizeof(float));
    long abs_off=tensor_data_start + (long)t->off;
    fseek(F,abs_off,SEEK_SET);
    if(t->type==GGML_F32){ fread(out,4,n,F); }
    else if(t->type==GGML_F16){ uint16_t*tmp=malloc(n*2); fread(tmp,2,n,F); for(uint64_t i=0;i<n;i++)out[i]=f16_to_f32(tmp[i]); free(tmp); }
    else if(t->type==GGML_Q4_K){ uint64_t nb=n/256; uint8_t blk[144]; for(uint64_t b=0;b<nb;b++){ fread(blk,1,144,F); deq_q4k(blk,out+b*256);} }
    else if(t->type==GGML_Q6_K){ uint64_t nb=n/256; uint8_t blk[210]; for(uint64_t b=0;b<nb;b++){ fread(blk,1,210,F); deq_q6k(blk,out+b*256);} }
    else { fprintf(stderr,"unsupported type %u for %s\n",t->type,t->name); exit(1); }
    return out;
}
static char** VOCAB; static uint64_t VOCAB_N;
static int64_t vocab_id(const char*s){ for(uint64_t i=0;i<VOCAB_N;i++) if(!strcmp(VOCAB[i],s)) return (int64_t)i; return -1; }

// ====================================================================================
// recipe-exact fp32 math — IDENTICAL to llama_forward.c (the bit-exact oracle).
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

typedef struct {
    float *attn_norm, *ffn_norm;       // [D_MODEL]
    float *Wq, *Wk, *Wv, *Wo;          // Wq [Q_DIM x D], Wk/Wv [KV_DIM x D], Wo [D x Q_DIM]
    float *Wg, *Wu, *Wd;               // Wg/Wu [FFN_HIDDEN x D], Wd [D x FFN_HIDDEN]
} Block;

// ====================================================================================
// GPU side: load the 6 Form-emitted PTX templates; stream weights per layer; run the block.
// (Identical dispatch math to the proven real.c — no kernel is rewritten.)
// ====================================================================================
static CUfunction K_rms,K_mv,K_rope,K_gqa,K_re,K_sg;
static CUfunction load_ptx(const char*dir,const char*fn,const char*ent){
    char p[1024]; snprintf(p,sizeof(p),"%s/%s",dir,fn);
    FILE*f=fopen(p,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",p);exit(1);}
    fseek(f,0,SEEK_END); long s=ftell(f); fseek(f,0,SEEK_SET); char*buf=malloc((size_t)s+1); if(fread(buf,1,(size_t)s,f)!=(size_t)s)exit(1); buf[s]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,buf,3,o,v)); CUfunction k; CK(cuGF_(&k,m,ent)); free(buf); return k;
}
// device weight buffers (one set, reused per layer via streaming).
static CUdeviceptr dWq,dWk,dWv,dWo,dWg,dWu,dWd,dG1,dG2;
// activation buffers (resident across layers, sized to MAX seq len): dX is the residual stream [T*D].
static CUdeviceptr dX,dN1,dQ,dQr,dK,dKr,dV,dAtt,dSc,dAo,dN2,dGg,dUu,dSg,dFf;
// LM-head device buffers: dEmb is token_embd resident on GPU [VOCAB_SIZE x D]; dXn is the
// final-position RMSNorm output [D]; dLogits is the head output [VOCAB_SIZE].
static CUdeviceptr dEmb,dXn,dLogits,dGo;
static int gT; // current sequence length (set per forward; the dispatch helpers read it)

static void g_rms(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){
    // one launch per token: grid 1 row, cols=D. (g is a single [D] gain row.)
    unsigned rows=1,cols=D_MODEL,B=256;
    for(int t=0;t<gT;t++){ CUdeviceptr xi=in+(CUdeviceptr)t*D_MODEL*4, yo=out+(CUdeviceptr)t*D_MODEL*4;
        void*p[]={&xi,&g,&yo,&rows,&cols,&RMS_EPS}; CK(cuLK_(K_rms,1,1,1,B,1,1,0,NULL,p,NULL)); }
}
// bias-free projection per token: Y[t] = W * X[t], W is [outd x ind].
static void g_matvec_seq(CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256;
    for(int t=0;t<gT;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*ind*4, yo=Y+(CUdeviceptr)t*outd*4;
        void*p[]={&W,&xi,&yo,&rows,&cols}; CK(cuLK_(K_mv,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
// single-vector matvec (no per-token sequencing): Y = W * X, W is [outd x ind]. Used for the LM head.
static void g_matvec_one(CUdeviceptr W,CUdeviceptr X,CUdeviceptr Y,int outd,int ind){
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256;
    void*p[]={&W,&X,&Y,&rows,&cols}; CK(cuLK_(K_mv,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}
// single-vector RMSNorm: out = rmsnorm(in,g), in/out are [D]. Used for the final-position norm.
static void g_rms_one(CUdeviceptr in,CUdeviceptr g,CUdeviceptr out){
    unsigned rows=1,cols=D_MODEL,B=256; void*p[]={&in,&g,&out,&rows,&cols,&RMS_EPS}; CK(cuLK_(K_rms,1,1,1,B,1,1,0,NULL,p,NULL));
}
// RoPE each token by its position; dim = number of heads*HEAD_DIM (Q_DIM or KV_DIM).
static void g_rope_seq(CUdeviceptr X,CUdeviceptr Y,int dim){
    unsigned uHD=HEAD_DIM,un=(unsigned)dim,B=128,npairs=(unsigned)(dim/2);
    for(int t=0;t<gT;t++){ CUdeviceptr xi=X+(CUdeviceptr)t*dim*4, yo=Y+(CUdeviceptr)t*dim*4; unsigned pos=(unsigned)t;
        void*p[]={&xi,&yo,&pos,&uHD,&un,&ROPE_BASE}; CK(cuLK_(K_rope,(npairs+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
static void g_residual(CUdeviceptr a,CUdeviceptr b,CUdeviceptr o,int n){
    unsigned un=(unsigned)n,B=256; void*p[]={&a,&b,&o,&un}; CK(cuLK_(K_re,(un+B-1)/B,1,1,B,1,1,0,NULL,p,NULL));
}

// Run one decoder block on the GPU over resident dX [T*D], streaming this layer's weights in first.
// Mirrors the proven real.c gpu_block op-for-op.
static void gpu_block(Block*B){
    size_t WqN=(size_t)Q_DIM*D_MODEL, WkN=(size_t)KV_DIM*D_MODEL, WoN=(size_t)D_MODEL*Q_DIM;
    size_t WgN=(size_t)FFN_HIDDEN*D_MODEL, WdN=(size_t)D_MODEL*FFN_HIDDEN;
    CK(cuH_(dWq,B->Wq,WqN*4)); CK(cuH_(dWk,B->Wk,WkN*4)); CK(cuH_(dWv,B->Wv,WkN*4)); CK(cuH_(dWo,B->Wo,WoN*4));
    CK(cuH_(dWg,B->Wg,WgN*4)); CK(cuH_(dWu,B->Wu,WgN*4)); CK(cuH_(dWd,B->Wd,WdN*4));
    CK(cuH_(dG1,B->attn_norm,(size_t)D_MODEL*4)); CK(cuH_(dG2,B->ffn_norm,(size_t)D_MODEL*4));

    // pass 1: n1=RMSNorm(x,attn_norm); K=Wk*n1; V=Wv*n1; RoPE(K)
    g_rms(dX,dG1,dN1);
    g_matvec_seq(dWk,dN1,dK,KV_DIM,D_MODEL);
    g_matvec_seq(dWv,dN1,dV,KV_DIM,D_MODEL);
    g_rope_seq(dK,dKr,KV_DIM);                // K roped -> dKr ; V left un-roped in dV
    // pass 2: n1=RMSNorm(x,attn_norm); Q=Wq*n1; RoPE(Q)
    g_rms(dX,dG1,dN1);
    g_matvec_seq(dWq,dN1,dQ,Q_DIM,D_MODEL);
    g_rope_seq(dQ,dQr,Q_DIM);                 // Q roped -> dQr
    // GQA causal attention(Qr, Kr, V) -> att  (24 q / 8 kv heads, hd=128)
    {
        unsigned unq=(unsigned)gT,unk=(unsigned)gT,uhd=HEAD_DIM,unhq=N_HEADS,unhkv=N_KV_HEADS;
        unsigned tot=(unsigned)gT*N_HEADS,Bk=256;
        void*p[]={&dQr,&dKr,&dV,&dAtt,&dSc,&unq,&unk,&uhd,&unhq,&unhkv,&SCALE};
        CK(cuLK_(K_gqa,(tot+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL));
    }
    // ao=Wo*att; x += ao
    g_matvec_seq(dWo,dAtt,dAo,D_MODEL,Q_DIM);
    g_residual(dX,dAo,dX,gT*D_MODEL);
    // n2=RMSNorm(x,ffn_norm); g=Wg*n2; u=Wu*n2; sg=SwiGLU(g,u); ff=Wd*sg; x += ff
    g_rms(dX,dG2,dN2);
    g_matvec_seq(dWg,dN2,dGg,FFN_HIDDEN,D_MODEL);
    g_matvec_seq(dWu,dN2,dUu,FFN_HIDDEN,D_MODEL);
    {
        unsigned n=(unsigned)gT*FFN_HIDDEN,Bk=256; void*p[]={&dGg,&dUu,&dSg,&n};
        CK(cuLK_(K_sg,(n+Bk-1)/Bk,1,1,Bk,1,1,0,NULL,p,NULL));
    }
    g_matvec_seq(dWd,dSg,dFf,D_MODEL,FFN_HIDDEN);
    g_residual(dX,dFf,dX,gT*D_MODEL);
    CK(cuSY_());
}

// decode a vocab string for printing: Ġ (0xC4 0xA0) -> space, Ċ -> \n; else raw.
static void decode_token(const char*s,char*out,int cap){
    int o=0; const unsigned char*p=(const unsigned char*)s;
    while(*p && o<cap-1){
        if(p[0]==0xC4 && p[1]==0xA0){ out[o++]=' '; p+=2; }
        else if(p[0]==0xC4 && p[1]==0x8A){ out[o++]='\\'; if(o<cap-1)out[o++]='n'; p+=2; }
        else { out[o++]=(char)*p; p++; }
    }
    out[o]=0;
}
// like decode_token but emits a real newline for Ċ (used when streaming the continuation to stdout).
static void decode_token_raw(const char*s,char*out,int cap){
    int o=0; const unsigned char*p=(const unsigned char*)s;
    while(*p && o<cap-1){
        if(p[0]==0xC4 && p[1]==0xA0){ out[o++]=' '; p+=2; }
        else if(p[0]==0xC4 && p[1]==0x8A){ out[o++]='\n'; p+=2; }
        else { out[o++]=(char)*p; p++; }
    }
    out[o]=0;
}

// Forward the whole sequence (T tokens) through all 28 GPU blocks streaming weights, then the GPU
// tied LM head, returning the argmax token id over the LAST position. The entire forward incl. the
// head runs on the Form-emitted PTX kernels. token_embd + output_norm are passed in (host copies),
// dEmb already holds token_embd resident on the GPU.
static int forward_argmax(const int*seq,int T,const float*token_embd,const float*output_norm,
                          float*logit_out){
    size_t sd=(size_t)T*D_MODEL;
    // build the initial residual stream from token embeddings (host) and upload to dX.
    float*x=malloc(sd*4);
    for(int t=0;t<T;t++) memcpy(x+(size_t)t*D_MODEL, token_embd+(size_t)seq[t]*D_MODEL, D_MODEL*sizeof(float));
    gT=T;
    CK(cuH_(dX,x,sd*4));
    // 28 decoder blocks, streaming each layer's real weights fresh.
    for(int L=0;L<N_LAYERS;L++){
        Block b; char nm[64];
        #define LDL(field,fmt) snprintf(nm,sizeof(nm),fmt,L); { Tensor*t=find_tensor(nm); if(!t){fprintf(stderr,"FAIL missing %s\n",nm);exit(1);} b.field=load_tensor_f32(t); }
        LDL(attn_norm,"blk.%d.attn_norm.weight"); LDL(ffn_norm,"blk.%d.ffn_norm.weight");
        LDL(Wq,"blk.%d.attn_q.weight"); LDL(Wk,"blk.%d.attn_k.weight"); LDL(Wv,"blk.%d.attn_v.weight"); LDL(Wo,"blk.%d.attn_output.weight");
        LDL(Wg,"blk.%d.ffn_gate.weight"); LDL(Wu,"blk.%d.ffn_up.weight"); LDL(Wd,"blk.%d.ffn_down.weight");
        #undef LDL
        gpu_block(&b);
        free(b.attn_norm);free(b.ffn_norm);free(b.Wq);free(b.Wk);free(b.Wv);free(b.Wo);free(b.Wg);free(b.Wu);free(b.Wd);
        fprintf(stderr,"    layer %d/%d\r",L+1,N_LAYERS); fflush(stderr);
    }
    // --- GPU tied LM head on the LAST position ---
    // pull the last residual row, upload it as the head input, RMSNorm on GPU, then matvec on GPU.
    CUdeviceptr dXlast = dX + (CUdeviceptr)(T-1)*D_MODEL*4;
    // final-position RMSNorm with output_norm gain (dGo holds output_norm, resident).
    g_rms_one(dXlast, dGo, dXn);
    // logits[v] = token_embd[v] · xn  — 128256 x 3072 matvec on the GPU PTX kernel.
    g_matvec_one(dEmb, dXn, dLogits, VOCAB_SIZE, D_MODEL);
    CK(cuSY_());
    // copy logits back and argmax on host (the math that produced them is all GPU).
    CK(cuD_(logit_out, dLogits, (size_t)VOCAB_SIZE*4));
    int best=-1; float bestv=-1e30f;
    for(int v=0;v<VOCAB_SIZE;v++){ if(logit_out[v]>bestv){ bestv=logit_out[v]; best=v; } }
    free(x);
    (void)output_norm;
    return best;
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf> [prompt] [n_generate]\n",argv[0]);return 1;}
    const char*prompt="The capital of France is"; int n_generate=8;
    if(argc>=3) prompt=argv[2];
    if(argc>=4) n_generate=atoi(argv[3]);
    if(n_generate<1) n_generate=1;

    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open failed\n");return 1;}
    char magic[4]; fread(magic,1,4,F); if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    ru32(); NT=ru64(); uint64_t nkv=ru64(); uint32_t alignment=32;
    for(uint64_t i=0;i<nkv;i++){ uint64_t kl; char*k=rstr(&kl); uint32_t vt=ru32();
        if(vt==T_STR){uint64_t sl;char*s=rstr(&sl);free(s);}
        else if(vt==T_ARR){uint32_t et=ru32();uint64_t cnt=ru64();
            if(et==T_STR && !strcmp(k,"tokenizer.ggml.tokens")){ VOCAB_N=cnt; VOCAB=malloc(cnt*sizeof(char*)); for(uint64_t j=0;j<cnt;j++){uint64_t sl;VOCAB[j]=rstr(&sl);} }
            else if(et==T_STR){ for(uint64_t j=0;j<cnt;j++){uint64_t sl;char*s=rstr(&sl);free(s);} }
            else fseek(F,(long)(sz(et)*cnt),SEEK_CUR);
        }
        else { if(!strcmp(k,"general.alignment")){uint32_t v=ru32();alignment=v;} else fseek(F,sz(vt),SEEK_CUR); }
        free(k);
    }
    TENS=malloc(NT*sizeof(Tensor));
    for(uint64_t i=0;i<NT;i++){ uint64_t nl; char*tn=rstr(&nl); strncpy(TENS[i].name,tn,95);TENS[i].name[95]=0;free(tn);
        TENS[i].nd=ru32(); for(uint32_t k=0;k<4;k++)TENS[i].dims[k]=1; for(uint32_t k=0;k<TENS[i].nd;k++)TENS[i].dims[k]=ru64();
        TENS[i].type=ru32(); TENS[i].off=ru64(); }
    long pos=ftell(F); tensor_data_start=((pos+alignment-1)/alignment)*alignment;
    if(!VOCAB){fprintf(stderr,"FAIL no tokenizer.ggml.tokens\n");return 1;}

    // ---- tokenize the prompt (BOS + whole-word vocab match; leading space = Ġ) ----
    // (same exact-match tokenizer as the proven real.c / llama_forward.c)
    #define SEQMAX 256
    int seq[SEQMAX]; int T=0; seq[T++]=128000;
    {
        const char*p=prompt; char word[256]; int first=1;
        while(*p){ while(*p==' ')p++; if(!*p)break; int wl=0; while(*p&&*p!=' '&&wl<250)word[wl++]=*p++; word[wl]=0;
            char tok[260]; if(first)strcpy(tok,word); else {tok[0]=(char)0xC4;tok[1]=(char)0xA0;strcpy(tok+2,word);} first=0;
            int64_t id=vocab_id(tok); if(id<0){fprintf(stderr,"FAIL no vocab token for \"%s\"\n",word);return 1;}
            if(T>=SEQMAX){fprintf(stderr,"FAIL prompt too long\n");return 1;} seq[T++]=(int)id; }
    }
    int T0=T; // prompt length (incl BOS)
    if(T0+n_generate>SEQMAX){ n_generate=SEQMAX-T0; }

    printf("=== form_cuda_ptx_llama_gen — REAL llama3.2:3b GENERATING on Form-emitted GPU PTX kernels ===\n");
    printf("vocab=%llu rope_base=%.0f rms_eps=%g  config: %d blocks d=%d nh=%d nkv=%d hd=%d ffn=%d\n",
        (unsigned long long)VOCAB_N,ROPE_BASE,RMS_EPS,N_LAYERS,D_MODEL,N_HEADS,N_KV_HEADS,HEAD_DIM,FFN_HIDDEN);
    printf("prompt=\"%s\"  n_generate=%d\n",prompt,n_generate);
    printf("prompt tokens(%d): ",T);
    for(int i=0;i<T;i++){ char dec[300]; if(seq[i]==128000)strcpy(dec,"<BOS>"); else decode_token(VOCAB[seq[i]],dec,sizeof(dec)); printf("[%d:'%s'] ",seq[i],dec); }
    printf("\n");

    // scale = 1/sqrt(HEAD_DIM) via the body's own Newton sqrt.
    { float g=(float)HEAD_DIM; for(int i=0;i<60;i++)g=0.5f*(g+(float)HEAD_DIM/g); SCALE=1.0f/g; }

    // ---- driver bootstrap ----
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuFR_=(Ffr)S(drv,"cuMemFree_v2");
    cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    printf("device=%s  runtime_deps=%s only\n",dn,LIB());

    const char*dir="."; // template PTX files live alongside this exe
    K_rms =load_ptx(dir,"template_rmsnorm.ptx","form_rmsnorm_f32");
    K_mv  =load_ptx(dir,"template_matvec.ptx","form_matvec_f32");
    K_rope=load_ptx(dir,"template_rope_llama.ptx","form_rope_llama_f32");
    K_gqa =load_ptx(dir,"template_attention_gqa.ptx","form_attention_gqa_f32");
    K_re  =load_ptx(dir,"template_residual.ptx","form_residual_f32");
    K_sg  =load_ptx(dir,"template_swiglu.ptx","form_swiglu_f32");
    printf("loaded 6 Form-emitted PTX kernels (rmsnorm,matvec,rope_llama[base param],attention_gqa,residual,swiglu)\n");

    // ---- allocate device weight buffers (largest of each shape) + activation buffers sized to MAX seq ----
    int TMAX=T0+n_generate;
    CK(cuMA_(&dWq,(size_t)Q_DIM*D_MODEL*4)); CK(cuMA_(&dWk,(size_t)KV_DIM*D_MODEL*4)); CK(cuMA_(&dWv,(size_t)KV_DIM*D_MODEL*4)); CK(cuMA_(&dWo,(size_t)D_MODEL*Q_DIM*4));
    CK(cuMA_(&dWg,(size_t)FFN_HIDDEN*D_MODEL*4)); CK(cuMA_(&dWu,(size_t)FFN_HIDDEN*D_MODEL*4)); CK(cuMA_(&dWd,(size_t)D_MODEL*FFN_HIDDEN*4));
    CK(cuMA_(&dG1,(size_t)D_MODEL*4)); CK(cuMA_(&dG2,(size_t)D_MODEL*4));
    size_t sd=(size_t)TMAX*D_MODEL, skv=(size_t)TMAX*KV_DIM, sh=(size_t)TMAX*FFN_HIDDEN;
    CK(cuMA_(&dX,sd*4)); CK(cuMA_(&dN1,sd*4)); CK(cuMA_(&dQ,sd*4)); CK(cuMA_(&dQr,sd*4));
    CK(cuMA_(&dK,skv*4)); CK(cuMA_(&dKr,skv*4)); CK(cuMA_(&dV,skv*4));
    CK(cuMA_(&dAtt,sd*4)); CK(cuMA_(&dSc,(size_t)TMAX*N_HEADS*TMAX*4)); CK(cuMA_(&dAo,sd*4));
    CK(cuMA_(&dN2,sd*4)); CK(cuMA_(&dGg,sh*4)); CK(cuMA_(&dUu,sh*4)); CK(cuMA_(&dSg,sh*4)); CK(cuMA_(&dFf,sd*4));
    // LM-head buffers: token_embd resident on GPU, single-row xn, full logits row.
    CK(cuMA_(&dEmb,(size_t)VOCAB_SIZE*D_MODEL*4)); CK(cuMA_(&dXn,(size_t)D_MODEL*4)); CK(cuMA_(&dLogits,(size_t)VOCAB_SIZE*4)); CK(cuMA_(&dGo,(size_t)D_MODEL*4));

    // ---- load embeddings (tied head matrix) + output norm; upload to the GPU once ----
    Tensor*te=find_tensor("token_embd.weight"); printf("loading token_embd (%llu el) -> GPU resident head matrix...\n",(unsigned long long)numel(te));
    float*token_embd=load_tensor_f32(te);
    Tensor*on=find_tensor("output_norm.weight"); float*output_norm=load_tensor_f32(on);
    CK(cuH_(dEmb,token_embd,(size_t)VOCAB_SIZE*D_MODEL*4));   // tied LM-head weight resident on GPU
    CK(cuH_(dGo,output_norm,(size_t)D_MODEL*4));              // final norm gain resident on GPU

    // ================= AUTOREGRESSIVE GENERATION =================
    printf("\n--- generating %d tokens greedily (full %d-block GPU forward per token, no KV-cache; slow by design) ---\n",n_generate,N_LAYERS);
    float*logits=malloc((size_t)VOCAB_SIZE*4);
    printf("\ncontinuation: ");
    char contbuf[8192]; int contlen=0; contbuf[0]=0;
    int first_gen_id=-1;
    for(int g=0;g<n_generate;g++){
        int next=forward_argmax(seq,T,token_embd,output_norm,logits);
        if(g==0) first_gen_id=next;
        // append + detokenize + show progress
        seq[T++]=next;
        char dec[300]; decode_token_raw(VOCAB[next],dec,sizeof(dec));
        // accumulate into the running continuation and echo this token immediately.
        for(int q=0;dec[q]&&contlen<(int)sizeof(contbuf)-1;q++) contbuf[contlen++]=dec[q];
        contbuf[contlen]=0;
        // top logit for this step (the argmax value) for an honest readout.
        float lv=logits[next];
        // honest top-3 logit race at this step (so a near-tie vs a confident win is visible).
        int t3[3]; float t3v[3]; for(int k=0;k<3;k++){t3[k]=-1;t3v[k]=-1e30f;}
        for(int v=0;v<VOCAB_SIZE;v++){ float l=logits[v]; for(int k=0;k<3;k++){ if(l>t3v[k]){ for(int m=2;m>k;m--){t3v[m]=t3v[m-1];t3[m]=t3[m-1];} t3v[k]=l; t3[k]=v; break; } } }
        fprintf(stderr,"\n  [tok %d/%d] id=%d  \"%s\"  logit=%.4f   top3:",g+1,n_generate,next,dec,lv);
        for(int k=0;k<3;k++){ char d3[300]; decode_token(VOCAB[t3[k]],d3,sizeof(d3)); fprintf(stderr," (id=%d \"%s\" %.4f)",t3[k],d3,t3v[k]); }
        fprintf(stderr,"\n");
        printf("%s",dec); fflush(stdout);
    }
    printf("\n");

    // ---- final readout: prompt + continuation ----
    printf("\n=== RESULT ===\n");
    // rebuild the human-readable prompt text from its tokens (spaces from Ġ).
    char ptext[2048]; int pl=0; ptext[0]=0;
    for(int i=1;i<T0;i++){ char d[300]; decode_token_raw(VOCAB[seq[i]],d,sizeof(d)); for(int q=0;d[q]&&pl<(int)sizeof(ptext)-1;q++) ptext[pl++]=d[q]; }
    ptext[pl]=0;
    // strip a single leading space for tidy display of the prompt.
    const char*pdisp=ptext; if(pdisp[0]==' ')pdisp++;
    printf("full text: \"%s%s\"\n",pdisp,contbuf);
    printf("generated token ids: ");
    for(int i=T0;i<T;i++) printf("%d ",seq[i]);
    printf("\n");

    {
        char dec[300]; decode_token(VOCAB[first_gen_id],dec,sizeof(dec));
        printf("first generated token: id=%d  string=\"%s\"\n",first_gen_id,dec);
        if(first_gen_id==12366) printf("MATCH — first generated token is \" Paris\" (id 12366); the REAL llama3.2:3b WROTE on Form-emitted GPU PTX kernels (incl. the tied LM head).\n");
        else printf("NOTE — first generated token id=%d not 12366. (Reported honestly; no faked Paris.)\n",first_gen_id);
    }
    return 0;
}

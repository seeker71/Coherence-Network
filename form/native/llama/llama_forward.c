// llama_forward.c — the FULL forward pass of the REAL llama3.2:3b model in C, on its actual GGUF
// weights, computed with the project's recipe-own math (Taylor/Newton, no hardware transcendentals).
// This is the CPU oracle the CUDA/PTX kernels mirror, scaled from the toy llama-block to real dims:
//   28 blocks, d_model=3072, n_heads=24, n_kv_heads=8 (GQA 3x), head_dim=128, ffn_hidden=8192,
//   rope_base=500000, rms_eps=1e-5, vocab=128256, LM head TIED to token_embd.
//
// Recipe math mirrored op-for-op (so this == the GPU kernels' oracle):
//   RMSNorm = x/sqrt(meansq+eps)*g, Newton-50 sqrt, eps=1e-5           (ln-rmsnorm)
//   matvec  = downward right-fold dot  y[o]=sum_i W[o*in+i]*x[i]        (tb-dot)
//   RoPE    = rope.fk over trig.fk: fln frexp-split + atanh series, fpow=Taylor fexp,
//             fsin range-reduce+10-term, fcos=fsin(a+pi/2); BASE=500000, HD=128, adjacent pairs
//   SwiGLU  = silu(g)*u, silu(x)=x/(1+fexp(-x)), fexp=14-term Taylor + halving/square-back
//   softmax = max-shift then the same fexp
// NO libm sinf/cosf/powf/expf — the recipe's own series only.
//
// Tokenization: exact string match against tokenizer.ggml.tokens (GPT-2 byte-level BPE); a leading
// space is 'Ġ' (U+0120, UTF-8 0xC4 0xA0). Prepend BOS 128000. After the forward, decode Ġ->space.
//
// Build: gcc -O2 -ffp-contract=off -o llama_forward.exe llama_forward.c -lm
//   -ffp-contract=off is load-bearing: it forbids the compiler from fusing each mul-then-add into a
//   single-rounding FMA, so every mul/add rounds TWICE — the same two-rounding shape the PTX kernels
//   use (separate mul.f32/add.f32, no fma). That is what makes this CPU forward bit-identical to the
//   GPU kernels it is the oracle for (matches form_cuda_ptx_*_host.c, all built -ffp-contract=off).
// Run:   llama_forward.exe <gguf-blob> ["prompt"]
//        default prompt: "The capital of France is"  (expect next token " Paris", matching ollama)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// ====================================================================================
// GGUF reader + dequant — reused verbatim from gguf_dequant.c (the proven loader),
// extended to capture tokenizer.ggml.tokens (the vocab string array).
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

// ---- tokenizer vocab (captured from tokenizer.ggml.tokens) ----
static char** VOCAB; static uint64_t VOCAB_N;
// lookup a vocab id by exact string; returns id or -1.
static int64_t vocab_id(const char*s){ for(uint64_t i=0;i<VOCAB_N;i++) if(!strcmp(VOCAB[i],s)) return (int64_t)i; return -1; }

// ====================================================================================
// recipe-exact fp32 math — mirrored op-for-op from the proven llama-block CUDA oracle.
// NO hardware transcendentals.
// ====================================================================================
// Newton-50 sqrt (tn-sqrt): g0=v; g=0.5*(g+v/g).
static float fsq(float v){if(v<=0.0f)return 0.0f; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g;}
// fexp = 14-term Taylor + halving-reduce + square-back.
static float fexs(float x){float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){t=t*(x/n);a=a+t;n=n+1.0f;} return a;}
static float fex(float x){int k=0; while((x<0.0f?-x:x)>0.5f){x=x*0.5f;k++;} float v=fexs(x); while(k>0){v=v*v;k--;} return v;}
static float sigm(float x){return 1.0f/(1.0f+fex(0.0f-x));}
static float swiglu(float g,float u){return (g*sigm(g))*u;}

// RoPE oracle: rope.fk over trig.fk, op-for-op. BASE=500000 for llama3.2.
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
static int   ROPE_NEOX = 0;   // 0 = adjacent-pair (recipe rope.fk); 1 = NEOX split-half (llama.cpp llama3)

// per-block weight pointers (dequanted f32)
typedef struct {
    float *attn_norm, *ffn_norm;       // [D_MODEL]
    float *Wq, *Wk, *Wv, *Wo;          // Wq [N_HEADS*HEAD_DIM x D], Wk/Wv [N_KV_HEADS*HEAD_DIM x D], Wo [D x D]
    float *Wg, *Wu, *Wd;               // Wg/Wu [FFN_HIDDEN x D], Wd [D x FFN_HIDDEN]
} Block;

// matvec: y[o] = sum_i W[o*ind + i] * x[i], downward right-fold (tb-dot) for bit-identity to the recipe.
static void matvec(const float*W,const float*x,float*y,int outd,int ind){
    for(int o=0;o<outd;o++){ float a=0.0f; for(int l=ind;l>0;){ l--; float p=W[(size_t)o*ind+l]*x[l]; a=p+a; } y[o]=a; }
}
// RMSNorm in place-ish: out[j]=(x[j]/sqrt(meansq+eps))*g[j].
static void rmsnorm(const float*x,const float*g,float*out,int d){
    float ss=0.0f; for(int j=0;j<d;j++){ float xv=x[j]; ss=ss+xv*xv; }
    float meansq=ss/(float)d; float rms=fsq(meansq+RMS_EPS); float r=1.0f/rms;
    for(int j=0;j<d;j++) out[j]=(x[j]*r)*g[j];
}
// RoPE a single head vector (length HEAD_DIM) at absolute position pos.
// Adjacent-pair (recipe): rotate (2t, 2t+1), hd=2t, freq=base^(-hd/HD).
// NEOX (llama.cpp llama3): rotate (t, t+HD/2), hd=2t, freq=base^(-hd/HD).
static void rope_head(float*v,int pos){
    int HD=HEAD_DIM;
    for(int t=0;t<HD/2;t++){
        int hd=2*t;
        float e=(-1.0f*(float)hd)/((float)HD*1.0f);
        float freq=c_fpow(ROPE_BASE,e);
        float a=((float)pos*1.0f)*freq;
        float c=c_fcos(a), s=c_fsin(a);
        int i0, i1;
        if(ROPE_NEOX){ i0=t; i1=t+HD/2; } else { i0=2*t; i1=2*t+1; }
        float x0=v[i0], x1=v[i1];
        v[i0]=x0*c - x1*s;
        v[i1]=x0*s + x1*c;
    }
}

// ====================================================================================
// forward pass over a prompt of `T` token ids -> logits over vocab for the LAST position.
// Keeps per-layer K and V cache for all positions (a token attends to all earlier tokens).
// ====================================================================================
static float SCALE; // 1/sqrt(HEAD_DIM) via Newton sqrt
static const int Q_DIM  = N_HEADS*HEAD_DIM;     // 3072
static const int KV_DIM = N_KV_HEADS*HEAD_DIM;  // 1024

static void forward(Block*blocks, float*token_embd, float*output_norm,
                    const int*tokens, int T, float*logits_out){
    // residual stream for every position: x[t*D + j]
    float *x = malloc((size_t)T*D_MODEL*sizeof(float));
    for(int t=0;t<T;t++){
        // embed = token_embd row[id].  token_embd is [D x VOCAB] stored row-major as [vocab][? ] ?
        // GGUF token_embd dims=[3072,128256]=[in,out]=[d_model,vocab], stored row-major as [out][in]=[vocab][d_model].
        // So row for token id is token_embd + id*D_MODEL.
        int id=tokens[t];
        memcpy(x+(size_t)t*D_MODEL, token_embd+(size_t)id*D_MODEL, D_MODEL*sizeof(float));
    }
    // K/V cache per layer: [T * KV_DIM]
    float *Kc = malloc((size_t)T*KV_DIM*sizeof(float));
    float *Vc = malloc((size_t)T*KV_DIM*sizeof(float));
    // scratch
    float *n1=malloc(D_MODEL*4), *n2=malloc(D_MODEL*4);
    float *q =malloc(Q_DIM*4);
    float *att=malloc(Q_DIM*4);     // concat of heads -> 3072
    float *ao =malloc(D_MODEL*4);
    float *gg=malloc(FFN_HIDDEN*4), *uu=malloc(FFN_HIDDEN*4), *sgv=malloc(FFN_HIDDEN*4), *ff=malloc(D_MODEL*4);
    float *scores=malloc((size_t)T*4);

    for(int L=0;L<N_LAYERS;L++){
        Block*B=&blocks[L];
        // ---- compute K,V for every position into the cache (RoPE applied to K) ----
        for(int t=0;t<T;t++){
            float*xt=x+(size_t)t*D_MODEL;
            rmsnorm(xt,B->attn_norm,n1,D_MODEL);
            float*kt=Kc+(size_t)t*KV_DIM;
            float*vt=Vc+(size_t)t*KV_DIM;
            matvec(B->Wk,n1,kt,KV_DIM,D_MODEL);
            matvec(B->Wv,n1,vt,KV_DIM,D_MODEL);
            // RoPE each of the 8 KV heads at position t
            for(int h=0;h<N_KV_HEADS;h++) rope_head(kt+h*HEAD_DIM, t);
        }
        // ---- per position: Q, RoPE(Q), causal attention over cached K/V, Wo, residual, FFN, residual ----
        for(int t=0;t<T;t++){
            float*xt=x+(size_t)t*D_MODEL;
            rmsnorm(xt,B->attn_norm,n1,D_MODEL);
            matvec(B->Wq,n1,q,Q_DIM,D_MODEL);
            for(int h=0;h<N_HEADS;h++) rope_head(q+h*HEAD_DIM, t);
            // causal attention per query head h; KV head = h/(N_HEADS/N_KV_HEADS)=h/3
            for(int h=0;h<N_HEADS;h++){
                int kvh = h/(N_HEADS/N_KV_HEADS);
                float*qh=q+h*HEAD_DIM;
                int nk=t+1; // attend positions [0..t]
                // scores
                for(int j=0;j<nk;j++){
                    float*kj=Kc+(size_t)j*KV_DIM + kvh*HEAD_DIM;
                    float a=0.0f; for(int l=HEAD_DIM;l>0;){ l--; float p=qh[l]*kj[l]; a=p+a; }
                    scores[j]=a*SCALE;
                }
                // softmax (max-shift + recipe fexp)
                float m=scores[0]; for(int j=1;j<nk;j++){ if(scores[j]>m)m=scores[j]; }
                float ssum=0.0f; for(int j=0;j<nk;j++){ float e=fex(scores[j]-m); scores[j]=e; ssum=ssum+e; }
                float rs=1.0f/ssum; for(int j=0;j<nk;j++) scores[j]=scores[j]*rs;
                // weighted sum of V -> head output
                float*oh=att+h*HEAD_DIM;
                for(int dmm=0;dmm<HEAD_DIM;dmm++){
                    float a=0.0f;
                    for(int j=0;j<nk;j++){ float*vj=Vc+(size_t)j*KV_DIM + kvh*HEAD_DIM; float p=vj[dmm]*scores[j]; a=a+p; }
                    oh[dmm]=a;
                }
            }
            // o = Wo*concat(heads);  x = x + o
            matvec(B->Wo,att,ao,D_MODEL,Q_DIM);
            for(int j=0;j<D_MODEL;j++) xt[j]=xt[j]+ao[j];
            // n2 = RMSNorm(x, ffn_norm); g=Wg*n2, u=Wu*n2; swi=silu(g)*u; d=Wd*swi; x=x+d
            rmsnorm(xt,B->ffn_norm,n2,D_MODEL);
            matvec(B->Wg,n2,gg,FFN_HIDDEN,D_MODEL);
            matvec(B->Wu,n2,uu,FFN_HIDDEN,D_MODEL);
            for(int j=0;j<FFN_HIDDEN;j++) sgv[j]=swiglu(gg[j],uu[j]);
            matvec(B->Wd,sgv,ff,D_MODEL,FFN_HIDDEN);
            for(int j=0;j<D_MODEL;j++) xt[j]=xt[j]+ff[j];
        }
        fprintf(stderr,"  layer %d/%d done\n",L+1,N_LAYERS);
    }
    // final norm on last position, then logits = token_embd row[v] . x_last  (tied head)
    float*xlast=x+(size_t)(T-1)*D_MODEL;
    float*xn=malloc(D_MODEL*4);
    rmsnorm(xlast,output_norm,xn,D_MODEL);
    for(int v=0;v<VOCAB_SIZE;v++){
        float*row=token_embd+(size_t)v*D_MODEL;
        float a=0.0f; for(int l=D_MODEL;l>0;){ l--; float p=row[l]*xn[l]; a=p+a; }
        logits_out[v]=a;
    }
    free(xn);
    free(x);free(Kc);free(Vc);free(n1);free(n2);free(q);free(att);free(ao);free(gg);free(uu);free(sgv);free(ff);free(scores);
}

// decode a vocab string for printing: Ġ (0xC4 0xA0) -> space, Ċ (0xC4 0x8A) -> newline; else raw byte.
static void decode_token(const char*s,char*out,int cap){
    int o=0; const unsigned char*p=(const unsigned char*)s;
    while(*p && o<cap-1){
        if(p[0]==0xC4 && p[1]==0xA0){ out[o++]=' '; p+=2; }
        else if(p[0]==0xC4 && p[1]==0x8A){ out[o++]='\\'; if(o<cap-1)out[o++]='n'; p+=2; }
        else { out[o++]=(char)*p; p++; }
    }
    out[o]=0;
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf> [prompt] [--neox]\n",argv[0]);return 1;}
    const char*prompt="The capital of France is";
    for(int i=2;i<argc;i++){ if(!strcmp(argv[i],"--neox")) ROPE_NEOX=1; else prompt=argv[i]; }

    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open failed\n");return 1;}
    char magic[4]; fread(magic,1,4,F); if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    ru32(); NT=ru64(); uint64_t nkv=ru64(); uint32_t alignment=32;
    // metadata: capture general.alignment + tokenizer.ggml.tokens (the vocab)
    for(uint64_t i=0;i<nkv;i++){ uint64_t kl; char*k=rstr(&kl); uint32_t vt=ru32();
        if(vt==T_STR){uint64_t sl;char*s=rstr(&sl);free(s);}
        else if(vt==T_ARR){uint32_t et=ru32();uint64_t cnt=ru64();
            if(et==T_STR && !strcmp(k,"tokenizer.ggml.tokens")){
                VOCAB_N=cnt; VOCAB=malloc(cnt*sizeof(char*));
                for(uint64_t j=0;j<cnt;j++){uint64_t sl;VOCAB[j]=rstr(&sl);}
            } else if(et==T_STR){ for(uint64_t j=0;j<cnt;j++){uint64_t sl;char*s=rstr(&sl);free(s);} }
            else fseek(F,(long)(sz(et)*cnt),SEEK_CUR);
        }
        else { if(!strcmp(k,"general.alignment")){uint32_t v=ru32();alignment=v;} else fseek(F,sz(vt),SEEK_CUR); }
        free(k);
    }
    // tensor directory
    TENS=malloc(NT*sizeof(Tensor));
    for(uint64_t i=0;i<NT;i++){ uint64_t nl; char*tn=rstr(&nl); strncpy(TENS[i].name,tn,95);TENS[i].name[95]=0;free(tn);
        TENS[i].nd=ru32(); for(uint32_t k=0;k<4;k++)TENS[i].dims[k]=1; for(uint32_t k=0;k<TENS[i].nd;k++)TENS[i].dims[k]=ru64();
        TENS[i].type=ru32(); TENS[i].off=ru64(); }
    long pos=ftell(F); tensor_data_start=((pos+alignment-1)/alignment)*alignment;

    if(!VOCAB){fprintf(stderr,"FAIL no tokenizer.ggml.tokens in metadata\n");return 1;}
    printf("vocab=%llu  rope_neox=%d  rope_base=%.1f\n",(unsigned long long)VOCAB_N,ROPE_NEOX,ROPE_BASE);

    // ---- tokenize the prompt: BOS + per-word vocab match (GPT-2 byte-level: leading space = Ġ) ----
    // Split the prompt on spaces; first word matched bare, subsequent words prefixed with Ġ (0xC4 0xA0).
    // (Exact whole-word match against the vocab — the task's deliberate stand-in for a full BPE; pick a
    //  short prompt whose words are each a single vocab token. Capped at TOKMAX to keep the oracle short.)
    #define TOKMAX 64
    int tokens[TOKMAX]; int T=0;
    tokens[T++]=128000; // <|begin_of_text|>
    {
        const char*p=prompt; char word[256];
        int first=1;
        while(*p){
            while(*p==' ')p++;
            if(!*p)break;
            int wl=0; while(*p && *p!=' ' && wl<250) word[wl++]=*p++;
            word[wl]=0;
            char tok[260];
            if(first){ strcpy(tok,word); }
            else { tok[0]=(char)0xC4; tok[1]=(char)0xA0; strcpy(tok+2,word); }
            first=0;
            int64_t id=vocab_id(tok);
            if(id<0){
                char dec[300]; decode_token(tok,dec,sizeof(dec));
                fprintf(stderr,"FAIL no vocab token for \"%s\" (decoded \"%s\") — pick a prompt whose words are each one vocab token\n",word,dec);
                return 1;
            }
            if(T>=TOKMAX){ fprintf(stderr,"FAIL prompt too long (>%d tokens) — keep the oracle prompt short\n",TOKMAX); return 1; }
            tokens[T++]=(int)id;
        }
    }
    printf("prompt=\"%s\"\nprompt_tokens (%d): ",prompt,T);
    for(int i=0;i<T;i++){ char dec[300]; if(tokens[i]==128000) strcpy(dec,"<|begin_of_text|>"); else decode_token(VOCAB[tokens[i]],dec,sizeof(dec)); printf("[%d:'%s'] ",tokens[i],dec); }
    printf("\n\nloading weights (28 blocks + embed + norm)...\n");

    // ---- load all weights ----
    char nm[64];
    Tensor*te=find_tensor("token_embd.weight"); float*token_embd=load_tensor_f32(te);
    Tensor*on=find_tensor("output_norm.weight"); float*output_norm=load_tensor_f32(on);
    Block*blocks=malloc(N_LAYERS*sizeof(Block));
    for(int L=0;L<N_LAYERS;L++){
        Block*B=&blocks[L];
        #define LD(field,fmt) snprintf(nm,sizeof(nm),fmt,L); { Tensor*t=find_tensor(nm); if(!t){fprintf(stderr,"FAIL missing %s\n",nm);return 1;} B->field=load_tensor_f32(t); }
        LD(attn_norm,"blk.%d.attn_norm.weight");
        LD(ffn_norm, "blk.%d.ffn_norm.weight");
        LD(Wq,"blk.%d.attn_q.weight");
        LD(Wk,"blk.%d.attn_k.weight");
        LD(Wv,"blk.%d.attn_v.weight");
        LD(Wo,"blk.%d.attn_output.weight");
        LD(Wg,"blk.%d.ffn_gate.weight");
        LD(Wu,"blk.%d.ffn_up.weight");
        LD(Wd,"blk.%d.ffn_down.weight");
        #undef LD
    }
    printf("weights loaded.\n");

    // scale = 1/sqrt(HEAD_DIM) via the body's own Newton sqrt.
    { float g=(float)HEAD_DIM; for(int i=0;i<60;i++)g=0.5f*(g+(float)HEAD_DIM/g); SCALE=1.0f/g; }

    // ---- forward ----
    float*logits=malloc((size_t)VOCAB_SIZE*sizeof(float));
    fprintf(stderr,"running forward (%d tokens, %d layers)...\n",T,N_LAYERS);
    forward(blocks,token_embd,output_norm,tokens,T,logits);

    // ---- argmax + top-5 ----
    int top[5]; float topv[5];
    for(int k=0;k<5;k++){ top[k]=-1; topv[k]=-1e30f; }
    for(int v=0;v<VOCAB_SIZE;v++){
        float lv=logits[v];
        for(int k=0;k<5;k++){ if(lv>topv[k]){ for(int m=4;m>k;m--){topv[m]=topv[m-1];top[m]=top[m-1];} topv[k]=lv; top[k]=v; break; } }
    }
    char dec[300];
    decode_token(VOCAB[top[0]],dec,sizeof(dec));
    printf("\n=== RESULT ===\n");
    printf("predicted next token id=%d  string=\"%s\"  logit=%.4f\n",top[0],dec,topv[0]);
    printf("top-5:\n");
    for(int k=0;k<5;k++){ decode_token(VOCAB[top[k]],dec,sizeof(dec)); printf("  %d. id=%-6d logit=%+.4f  \"%s\"\n",k+1,top[k],topv[k],dec); }
    printf("\nollama (raw, greedy) next token: \" Paris\"  ->  match if predicted string == \" Paris\"\n");
    return 0;
}

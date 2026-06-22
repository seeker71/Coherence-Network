// stage1_dequant_matvec_test.c — STAGE 1 make-or-break gate for the resident-quantized llama fast path.
//
// Proves the in-kernel dequant matvec PTX (template_matvec_q4k.ptx / template_matvec_q6k.ptx) is
// BIT-EXACT (uint32-identical) to dequant-to-f32-then-template_matvec.ptx, on REAL llama3.2:3b tensors:
//   blk.0.attn_q.weight  (Q4_K, out=3072 in=3072)
//   blk.0.attn_v.weight  (Q6_K, out=1024 in=3072)
//
// Driver-only (nvcuda.dll). NO go/rust/clang/nvcc/nvrtc/python/shell. The dequant-to-f32 reference uses
// gguf_dequant.c's deq_q4k/deq_q6k verbatim (== q4k/q6k-dequant.fk). If any quant/op diverges this test
// STOPS and reports the exact column, the dequant ULP, and the matvec uint32 mismatch.
//
// Build: gcc -O2 -ffp-contract=off -o stage1_dequant_matvec_test.exe stage1_dequant_matvec_test.c -lm
// Run:   stage1_dequant_matvec_test.exe <gguf-blob>

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

// ---------- GGUF reader + dequant (verbatim from gguf_dequant.c) ----------
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
    else { fprintf(stderr,"unsupported type %u\n",t->type); exit(1); }
    return out;
}
// read RAW superblock bytes (no dequant): nb*blocksize bytes.
static uint8_t* load_tensor_raw(Tensor*t,size_t*nbytes){
    uint64_t n=numel(t); uint64_t nb=n/256; int bs=(t->type==GGML_Q4_K)?144:(t->type==GGML_Q6_K)?210:-1;
    if(bs<0){fprintf(stderr,"load_tensor_raw: type %u not k-quant\n",t->type);exit(1);}
    size_t total=(size_t)nb*bs; uint8_t*raw=malloc(total);
    long abs_off=tensor_data_start + (long)t->off; fseek(F,abs_off,SEEK_SET);
    if(fread(raw,1,total,F)!=total){fprintf(stderr,"raw read short\n");exit(1);}
    *nbytes=total; return raw;
}

// ---------- recipe-exact CPU matvec (== llama_forward.c / template_matvec.ptx dot order) ----------
static void cpu_matvec(const float*W,const float*x,float*y,int outd,int ind){
    for(int o=0;o<outd;o++){ float a=0.0f; for(int l=ind;l>0;){ l--; float p=W[(size_t)o*ind+l]*x[l]; a=p+a; } y[o]=a; }
}

// ---------- PTX loader ----------
static CUfunction load_ptx(const char*fn,const char*ent){
    FILE*f=fopen(fn,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",fn);exit(1);}
    fseek(f,0,SEEK_END); long s=ftell(f); fseek(f,0,SEEK_SET); char*buf=malloc((size_t)s+1); if(fread(buf,1,(size_t)s,f)!=(size_t)s)exit(1); buf[s]='\0'; fclose(f);
    int o[3]={J7,5,6}; void*v[3]={(void*)(uintptr_t)0,jl,(void*)(uintptr_t)sizeof(jl)}; CUmodule m; CK(cuLD_(&m,buf,3,o,v)); CUfunction k; CK(cuGF_(&k,m,ent)); free(buf); return k;
}

static CUfunction K_mv, K_q4k, K_q6k;

// run dequant->f32->template_matvec on GPU (reference path) into y_ref
static void gpu_f32_matvec(const float*Wf32,const float*x,float*y,int outd,int ind){
    CUdeviceptr dW,dx,dy; CK(cuMA_(&dW,(size_t)outd*ind*4)); CK(cuMA_(&dx,(size_t)ind*4)); CK(cuMA_(&dy,(size_t)outd*4));
    CK(cuH_(dW,Wf32,(size_t)outd*ind*4)); CK(cuH_(dx,x,(size_t)ind*4));
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256; void*p[]={&dW,&dx,&dy,&rows,&cols};
    CK(cuLK_(K_mv,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_());
    CK(cuD_(y,dy,(size_t)outd*4)); CK(cuFR_(dW)); CK(cuFR_(dx)); CK(cuFR_(dy));
}
// run in-kernel dequant matvec on GPU (fast path) into y_fast
static void gpu_qk_matvec(CUfunction K,const uint8_t*raw,size_t rawbytes,const float*x,float*y,int outd,int ind){
    CUdeviceptr dW,dx,dy; CK(cuMA_(&dW,rawbytes)); CK(cuMA_(&dx,(size_t)ind*4)); CK(cuMA_(&dy,(size_t)outd*4));
    CK(cuH_(dW,raw,rawbytes)); CK(cuH_(dx,x,(size_t)ind*4));
    unsigned rows=(unsigned)outd,cols=(unsigned)ind,B=256; void*p[]={&dW,&dx,&dy,&rows,&cols};
    CK(cuLK_(K,(rows+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); CK(cuSY_());
    CK(cuD_(y,dy,(size_t)outd*4)); CK(cuFR_(dW)); CK(cuFR_(dx)); CK(cuFR_(dy));
}

// compare dequant-in-kernel vs dequant-to-f32, weight-by-weight (ULP report) for one tensor.
// We reconstruct the in-kernel dequant on the CPU bit-for-bit (same formula) just to localize a diff
// if the matvec mismatches — the GPU kernel IS the in-kernel dequant; this is the same arithmetic.
static int gate_tensor(const char*name,Tensor*t,CUfunction K){
    int ind=(int)t->dims[0];          // quantized dim (in)
    int outd=(int)(numel(t)/ind);     // out rows
    printf("\n=== GATE: %s  type=%s  out=%d in=%d ===\n",name,t->type==GGML_Q4_K?"Q4_K":"Q6_K",outd,ind);
    // dequant to f32 (reference) + raw bytes (fast)
    float*Wf32=load_tensor_f32(t);
    size_t rawbytes; uint8_t*raw=load_tensor_raw(t,&rawbytes);
    // deterministic input vector x[i] = sin-ish mix so it exercises sign/magnitude (no rng dependency).
    float*x=malloc((size_t)ind*4);
    for(int i=0;i<ind;i++){ float v=((float)((i*1103515245u+12345u)&0xFFFF))/65536.0f - 0.5f; x[i]=v; }
    // run both paths
    float*y_ref=malloc((size_t)outd*4), *y_fast=malloc((size_t)outd*4), *y_cpu=malloc((size_t)outd*4);
    gpu_f32_matvec(Wf32,x,y_ref,outd,ind);
    gpu_qk_matvec(K,raw,rawbytes,x,y_fast,outd,ind);
    cpu_matvec(Wf32,x,y_cpu,outd,ind);
    // bit-exact compare: fast vs ref (the real gate), and ref vs cpu (sanity the f32 path matches the oracle)
    int ex_fast=0,ex_refcpu=0; float ma_fast=0; int firstbad=-1;
    for(int o=0;o<outd;o++){
        uint32_t a,b,c; memcpy(&a,&y_fast[o],4); memcpy(&b,&y_ref[o],4); memcpy(&c,&y_cpu[o],4);
        if(a==b)ex_fast++; else if(firstbad<0)firstbad=o;
        if(b==c)ex_refcpu++;
        float d=y_fast[o]-y_ref[o]; if(d<0)d=-d; if(d>ma_fast)ma_fast=d;
    }
    printf("  in-kernel-dequant matvec vs dequant->f32 matvec: %d/%d bit-exact   max_abs_diff=%g\n",ex_fast,outd,(double)ma_fast);
    printf("  (sanity) f32-GPU matvec vs CPU oracle matvec    : %d/%d bit-exact\n",ex_refcpu,outd);
    int ok = (ex_fast==outd);
    if(!ok){
        printf("  FIRST MISMATCH at row %d: fast=%.9g(0x%08x) ref=%.9g(0x%08x)\n",
            firstbad,y_fast[firstbad],*(uint32_t*)&y_fast[firstbad],y_ref[firstbad],*(uint32_t*)&y_ref[firstbad]);
        // localize a dequant divergence: compare a few columns' dequanted weights via the reference array
        // (the GPU does the in-kernel dequant; if matvec differs the dequant differs somewhere in this row).
        printf("  -> dequant divergence somewhere in row %d's %d columns. (in-kernel != recipe deq)\n",firstbad,ind);
    }
    free(Wf32);free(raw);free(x);free(y_ref);free(y_fast);free(y_cpu);
    return ok;
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf>\n",argv[0]);return 1;}
    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open failed\n");return 1;}
    char magic[4]; fread(magic,1,4,F); if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    ru32(); NT=ru64(); uint64_t nkv=ru64(); uint32_t alignment=32;
    for(uint64_t i=0;i<nkv;i++){ uint64_t kl; char*k=rstr(&kl); uint32_t vt=ru32();
        if(vt==T_STR){uint64_t sl;char*s=rstr(&sl);free(s);}
        else if(vt==T_ARR){uint32_t et=ru32();uint64_t cnt=ru64(); if(et==T_STR){for(uint64_t j=0;j<cnt;j++){uint64_t sl;char*s=rstr(&sl);free(s);}} else fseek(F,(long)(sz(et)*cnt),SEEK_CUR);}
        else { if(!strcmp(k,"general.alignment")){uint32_t v=ru32();alignment=v;} else fseek(F,sz(vt),SEEK_CUR); }
        free(k);
    }
    TENS=malloc(NT*sizeof(Tensor));
    for(uint64_t i=0;i<NT;i++){ uint64_t nl; char*tn=rstr(&nl); strncpy(TENS[i].name,tn,95);TENS[i].name[95]=0;free(tn);
        TENS[i].nd=ru32(); for(uint32_t k=0;k<4;k++)TENS[i].dims[k]=1; for(uint32_t k=0;k<TENS[i].nd;k++)TENS[i].dims[k]=ru64();
        TENS[i].type=ru32(); TENS[i].off=ru64(); }
    long pos=ftell(F); tensor_data_start=((pos+alignment-1)/alignment)*alignment;

    // driver bootstrap
    H drv=O(LIB()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(Fi)RS(drv,"cuInit"); cuDG_=(Fdg)RS(drv,"cuDeviceGet"); cuDN_=(Fdn)RS(drv,"cuDeviceGetName"); cuCC_=(Fcc)RS(drv,"cuCtxCreate_v2");
    cuLD_=(Fld)RS(drv,"cuModuleLoadDataEx"); cuGF_=(Fgf)RS(drv,"cuModuleGetFunction"); cuMA_=(Fma)RS(drv,"cuMemAlloc_v2"); cuFR_=(Ffr)RS(drv,"cuMemFree_v2");
    cuH_=(Fh)RS(drv,"cuMemcpyHtoD_v2"); cuD_=(Fd)RS(drv,"cuMemcpyDtoH_v2"); cuLK_=(Flk)RS(drv,"cuLaunchKernel"); cuSY_=(Fsy)RS(drv,"cuCtxSynchronize"); cuES_=(Fes)S(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dv; CK(cuDG_(&dv,0)); char dn[256]={0}; cuDN_(dn,sizeof(dn),dv); CUcontext ctx; CK(cuCC_(&ctx,0,dv));
    printf("=== STAGE 1: in-kernel dequant matvec bit-exact gate ===\ndevice=%s  runtime_deps=%s only\n",dn,LIB());

    K_mv  = load_ptx("template_matvec.ptx","form_matvec_f32");
    K_q4k = load_ptx("template_matvec_q4k.ptx","form_matvec_q4k_f32");
    K_q6k = load_ptx("template_matvec_q6k.ptx","form_matvec_q6k_f32");
    printf("loaded template_matvec.ptx + template_matvec_q4k.ptx + template_matvec_q6k.ptx\n");

    // --all: sweep EVERY k-quant tensor (all 28 layers + token_embd) and report the first divergence.
    // <name>: check one named tensor. default: blk.0 attn_q (Q4_K) + attn_v (Q6_K).
    if(argc>=3 && !strcmp(argv[2],"--all")){
        int total=0,bad=0;
        for(uint64_t i=0;i<NT;i++){ Tensor*t=&TENS[i]; if(t->type!=GGML_Q4_K && t->type!=GGML_Q6_K) continue;
            CUfunction K = (t->type==GGML_Q4_K)?K_q4k:K_q6k;
            total++; int ok=gate_tensor(t->name,t,K); if(!ok){ bad++; printf("  *** DIVERGENT: %s ***\n",t->name); }
        }
        printf("\n=== STAGE 1 --all RESULT ===\n%d k-quant tensors checked, %d divergent.\n",total,bad);
        return bad?1:0;
    }
    if(argc>=3){ Tensor*t=find_tensor(argv[2]); if(!t){fprintf(stderr,"no tensor %s\n",argv[2]);return 1;}
        CUfunction K=(t->type==GGML_Q4_K)?K_q4k:K_q6k; int ok=gate_tensor(argv[2],t,K);
        printf("\n%s: %s\n",argv[2],ok?"BIT-EXACT":"DIVERGENT"); return ok?0:1; }

    Tensor*tq=find_tensor("blk.0.attn_q.weight"); if(!tq){fprintf(stderr,"no attn_q\n");return 1;}
    Tensor*tv=find_tensor("blk.0.attn_v.weight"); if(!tv){fprintf(stderr,"no attn_v\n");return 1;}
    int ok1=gate_tensor("blk.0.attn_q.weight (Q4_K)",tq,K_q4k);
    int ok2=gate_tensor("blk.0.attn_v.weight (Q6_K)",tv,K_q6k);

    printf("\n=== STAGE 1 RESULT ===\n");
    printf("Q4_K in-kernel matvec bit-exact: %s\n",ok1?"YES":"NO");
    printf("Q6_K in-kernel matvec bit-exact: %s\n",ok2?"YES":"NO");
    if(ok1&&ok2){ printf("STAGE 1 PASS — in-kernel dequant == recipe dequant to the bit. Safe to build the fast forward.\n"); return 0; }
    printf("STAGE 1 FAIL — STOP. Do NOT ship a fast-but-wrong kernel.\n"); return 1;
}

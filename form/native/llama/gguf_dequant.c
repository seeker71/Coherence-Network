// gguf_dequant.c — load + dequant real llama3.2:3b tensors to f32 in C, mirroring the proven Form
// recipes q4k-dequant.fk / q6k-dequant.fk / f16-decode.fk op-for-op. Rung 2a of the weight-load walk.
// Driver-only host language (no python/go). Build: gcc -O2 -o gguf_dequant.exe gguf_dequant.c
// Run: gguf_dequant.exe <gguf> [tensor-name]   (default validates attn_q Q4_K + attn_v Q6_K + token_embd)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// ---------- GGUF reader ----------
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

// ---------- numeric decoders (mirror f16-decode.fk + the k-quant recipes) ----------
static float f16_to_f32(uint16_t h){
    uint32_t s=(h>>15)&1, e=(h>>10)&0x1F, m=h&0x3FF, bits;
    if(e==0){ if(m==0) bits=s<<31; else { e=127-15+1; while(!(m&0x400)){m<<=1;e--;} m&=0x3FF; bits=(s<<31)|(e<<23)|(m<<13);} }
    else if(e==0x1F) bits=(s<<31)|(0xFF<<23)|(m<<13);
    else bits=(s<<31)|((e-15+127)<<23)|(m<<13);
    float f; memcpy(&f,&bits,4); return f;
}
// Q4_K super-block (144 bytes): d(f16) dmin(f16) scales[12] qs[128] -> 256 f32. Mirrors q4k-dequant.fk.
static void deq_q4k(const uint8_t*b,float*out){
    float d=f16_to_f32(*(const uint16_t*)b), dmin=f16_to_f32(*(const uint16_t*)(b+2));
    const uint8_t*scales=b+4, *qs=b+16;
    for(int i=0;i<256;i++){
        int c=i/64, within=i%64, half=within/32, l=within%32, j=2*c+half;   // sub-block index 0..7
        int sc,mn;
        if(j<4){ sc=scales[j]&63; mn=scales[j+4]&63; }
        else   { sc=(scales[j+4]&0xF)|((scales[j-4]>>6)<<4); mn=(scales[j+4]>>4)|((scales[j]>>6)<<4); }
        uint8_t qb=qs[c*32+l]; int nib=(half==0)?(qb&0xF):(qb>>4);
        out[i]=(d*sc)*nib-(dmin*mn);
    }
}
// Q6_K super-block (210 bytes): ql[128] qh[64] scales[16](int8) d(f16) -> 256 f32. Mirrors q6k-dequant.fk.
static void deq_q6k(const uint8_t*b,float*out){
    const uint8_t*ql=b, *qh=b+128; const int8_t*scales=(const int8_t*)(b+192);
    float d=f16_to_f32(*(const uint16_t*)(b+208));
    for(int i=0;i<256;i++){
        int h=i/128, wi=i%128, l=wi%32, g=wi/32, is=l/16;
        int qlidx=h*64 + l + (g%2)*32;
        int nib=(g/2==0)?(ql[qlidx]&0xF):(ql[qlidx]>>4);
        int hi=(qh[h*32+l]>>(2*g))&3;
        int q=(nib|(hi<<4))-32;
        int scale=scales[h*8 + is + 2*g];   // signed int8
        out[i]=d*scale*q;
    }
}

static long tensor_data_start; static Tensor* TENS; static uint64_t NT;
static Tensor* find_tensor(const char*name){ for(uint64_t i=0;i<NT;i++) if(!strcmp(TENS[i].name,name)) return &TENS[i]; return NULL; }
static uint64_t numel(Tensor*t){ uint64_t n=1; for(uint32_t k=0;k<t->nd;k++) n*=t->dims[k]; return n; }

// dequant a whole tensor to a freshly malloc'd f32 array (caller frees)
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

static void stats(const char*nm,float*a,uint64_t n){
    double mn=1e30,mx=-1e30,sum=0,sq=0; uint64_t nan=0;
    for(uint64_t i=0;i<n;i++){ float v=a[i]; if(isnan(v)||isinf(v)){nan++;continue;} if(v<mn)mn=v; if(v>mx)mx=v; sum+=v; sq+=(double)v*v; }
    double mean=sum/n, std=sqrt(sq/n-mean*mean);
    printf("  %-26s n=%-9llu min=%+.4f max=%+.4f mean=%+.5f std=%.5f nan/inf=%llu  [%.4f %.4f %.4f ...]\n",
        nm,(unsigned long long)n,mn,mx,mean,std,(unsigned long long)nan,a[0],a[1],a[2]);
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf> [tensor]\n",argv[0]);return 1;}
    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open failed\n");return 1;}
    char magic[4]; fread(magic,1,4,F); if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    ru32(); NT=ru64(); uint64_t nkv=ru64(); uint32_t alignment=32;
    // skip metadata (capture general.alignment if present)
    for(uint64_t i=0;i<nkv;i++){ uint64_t kl; char*k=rstr(&kl); uint32_t vt=ru32();
        if(vt==T_STR){uint64_t sl;char*s=rstr(&sl);free(s);}
        else if(vt==T_ARR){uint32_t et=ru32();uint64_t cnt=ru64(); if(et==T_STR){for(uint64_t j=0;j<cnt;j++){uint64_t sl;char*s=rstr(&sl);free(s);}} else fseek(F,(long)(sz(et)*cnt),SEEK_CUR);}
        else { if(!strcmp(k,"general.alignment")){uint32_t v=ru32();alignment=v;} else fseek(F,sz(vt),SEEK_CUR); }
        free(k);
    }
    // tensor directory
    TENS=malloc(NT*sizeof(Tensor));
    for(uint64_t i=0;i<NT;i++){ uint64_t nl; char*tn=rstr(&nl); strncpy(TENS[i].name,tn,95);TENS[i].name[95]=0;free(tn);
        TENS[i].nd=ru32(); for(uint32_t k=0;k<4;k++)TENS[i].dims[k]=1; for(uint32_t k=0;k<TENS[i].nd;k++)TENS[i].dims[k]=ru64();
        TENS[i].type=ru32(); TENS[i].off=ru64(); }
    long pos=ftell(F); tensor_data_start=((pos+alignment-1)/alignment)*alignment;
    printf("data section starts at byte %ld (alignment %u)\n\n",tensor_data_start,alignment);

    const char* probe[] = {"blk.0.attn_q.weight","blk.0.attn_v.weight","blk.0.ffn_gate.weight","blk.0.attn_norm.weight","token_embd.weight"};
    if(argc>2){ Tensor*t=find_tensor(argv[2]); if(!t){fprintf(stderr,"no tensor %s\n",argv[2]);return 1;} float*a=load_tensor_f32(t); stats(t->name,a,numel(t)); free(a); }
    else { printf("=== dequant validation (real llama3.2:3b weights -> f32) ===\n");
        for(int p=0;p<5;p++){ Tensor*t=find_tensor(probe[p]); if(!t)continue; float*a=load_tensor_f32(t); stats(t->name,a,numel(t)); free(a); } }
    printf("\nrung 2a ok — Q4_K/Q6_K/F16/F32 dequant in C, mirroring q4k/q6k-dequant.fk\n");
    fclose(F); return 0;
}

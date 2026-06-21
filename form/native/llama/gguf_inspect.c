// gguf_inspect.c — read a real GGUF (llama3.2:3b) in C: header, metadata config, tensor directory.
// Rung 1 of the weight-load walk (form-native-models.form): prove the driver-only host can read a
// real public model's structure with no python/go. No deps; reads the file sequentially.
// Build: gcc -O2 -o gguf_inspect.exe gguf_inspect.c
// Run:   gguf_inspect.exe <path-to-gguf-blob>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static FILE* F;
static uint32_t ru32(void){ uint32_t v; if(fread(&v,4,1,F)!=1){fprintf(stderr,"EOF u32\n");exit(1);} return v; }
static uint64_t ru64(void){ uint64_t v; if(fread(&v,8,1,F)!=1){fprintf(stderr,"EOF u64\n");exit(1);} return v; }
static float   rf32(void){ float v; if(fread(&v,4,1,F)!=1){fprintf(stderr,"EOF f32\n");exit(1);} return v; }
// gguf string: u64 len + bytes (not null-terminated). caller frees.
static char* rstr(uint64_t*outlen){ uint64_t n=ru64(); char*s=malloc(n+1); if(n&&fread(s,1,n,F)!=n){fprintf(stderr,"EOF str\n");exit(1);} s[n]='\0'; if(outlen)*outlen=n; return s; }

enum { T_U8,T_I8,T_U16,T_I16,T_U32,T_I32,T_F32,T_BOOL,T_STR,T_ARR,T_U64,T_I64,T_F64 };
static const char* GGML_TYPE[]={"F32","F16","Q4_0","Q4_1","?4","?5","Q5_0","Q5_1","Q8_0","Q8_1","Q2_K","Q3_K","Q4_K","Q5_K","Q6_K","Q8_K","IQ2_XXS","IQ2_XS","IQ3_XXS","IQ1_S","IQ4_NL","IQ3_S","IQ2_S","IQ4_XS","I8","I16","I32","I64","F64","IQ1_M","BF16"};
static int scalar_size(uint32_t t){ switch(t){case T_U8:case T_I8:case T_BOOL:return 1;case T_U16:case T_I16:return 2;case T_U32:case T_I32:case T_F32:return 4;case T_U64:case T_I64:case T_F64:return 8;default:return -1;} }

// read one scalar value of type t into a double (for printing) + capture u64; returns 1 if numeric
static int read_scalar(uint32_t t,double*d,uint64_t*u){
    switch(t){
        case T_U8:{uint8_t v;fread(&v,1,1,F);*d=v;*u=v;return 1;}
        case T_I8:{int8_t v;fread(&v,1,1,F);*d=v;*u=(uint64_t)(int64_t)v;return 1;}
        case T_U16:{uint16_t v;fread(&v,2,1,F);*d=v;*u=v;return 1;}
        case T_I16:{int16_t v;fread(&v,2,1,F);*d=v;*u=(uint64_t)(int64_t)v;return 1;}
        case T_U32:{uint32_t v=ru32();*d=v;*u=v;return 1;}
        case T_I32:{int32_t v;fread(&v,4,1,F);*d=v;*u=(uint64_t)(int64_t)v;return 1;}
        case T_F32:{float v=rf32();*d=v;*u=0;return 1;}
        case T_BOOL:{uint8_t v;fread(&v,1,1,F);*d=v;*u=v;return 1;}
        case T_U64:{uint64_t v=ru64();*d=(double)v;*u=v;return 1;}
        case T_I64:{int64_t v;fread(&v,8,1,F);*d=(double)v;*u=(uint64_t)v;return 1;}
        case T_F64:{double v;fread(&v,8,1,F);*d=v;*u=0;return 1;}
        default:return 0;
    }
}

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s <gguf>\n",argv[0]);return 1;}
    F=fopen(argv[1],"rb"); if(!F){fprintf(stderr,"open %s failed\n",argv[1]);return 1;}
    char magic[4]; fread(magic,1,4,F);
    if(memcmp(magic,"GGUF",4)){fprintf(stderr,"not GGUF\n");return 1;}
    uint32_t ver=ru32(); uint64_t n_tensors=ru64(); uint64_t n_kv=ru64();
    printf("GGUF v%u  tensors=%llu  metadata_kv=%llu\n",ver,(unsigned long long)n_tensors,(unsigned long long)n_kv);

    // ---- metadata: capture the llama config keys ----
    char arch[64]="?", name[128]="?";
    uint64_t blocks=0,embd=0,ffl=0,nhead=0,nkv=0,ctx=0,vocab=0,rope_dim=0; double rms_eps=0,rope_base=0;
    for(uint64_t i=0;i<n_kv;i++){
        uint64_t kl; char*key=rstr(&kl); uint32_t vt=ru32();
        double d=0; uint64_t u=0;
        if(vt==T_STR){ uint64_t sl; char*s=rstr(&sl);
            if(!strcmp(key,"general.architecture")) strncpy(arch,s,63);
            else if(!strcmp(key,"general.name")) strncpy(name,s,127);
            free(s);
        } else if(vt==T_ARR){ uint32_t et=ru32(); uint64_t cnt=ru64();
            if(!strcmp(key,"tokenizer.ggml.tokens")) vocab=cnt;   // vocab size = token list length
            // skip the array body
            if(et==T_STR){ for(uint64_t j=0;j<cnt;j++){ uint64_t sl; char*s=rstr(&sl); free(s);} }
            else { int ss=scalar_size(et); if(ss<0){fprintf(stderr,"nested array @%s\n",key);return 1;} fseek(F,(long)(ss*cnt),SEEK_CUR); }
        } else { read_scalar(vt,&d,&u);
            if(!strcmp(key,"llama.block_count")) blocks=u;
            else if(!strcmp(key,"llama.embedding_length")) embd=u;
            else if(!strcmp(key,"llama.feed_forward_length")) ffl=u;
            else if(!strcmp(key,"llama.attention.head_count")) nhead=u;
            else if(!strcmp(key,"llama.attention.head_count_kv")) nkv=u;
            else if(!strcmp(key,"llama.context_length")) ctx=u;
            else if(!strcmp(key,"llama.vocab_size")) vocab=u;
            else if(!strcmp(key,"llama.rope.dimension_count")) rope_dim=u;
            else if(!strcmp(key,"llama.attention.layer_norm_rms_epsilon")) rms_eps=d;
            else if(!strcmp(key,"llama.rope.freq_base")) rope_base=d;
        }
        free(key);
    }
    printf("\n=== CONFIG ===\narch=%s name=%s\n",arch,name);
    printf("blocks=%llu  d_model=%llu  ffn_hidden=%llu  heads=%llu  kv_heads=%llu (GQA %llux)\n",
        (unsigned long long)blocks,(unsigned long long)embd,(unsigned long long)ffl,
        (unsigned long long)nhead,(unsigned long long)nkv,(unsigned long long)(nkv?nhead/nkv:0));
    printf("head_dim=%llu  ctx=%llu  vocab=%llu  rope_dim=%llu  rope_base=%.1f  rms_eps=%g\n",
        (unsigned long long)(nhead?embd/nhead:0),(unsigned long long)ctx,(unsigned long long)vocab,
        (unsigned long long)rope_dim,rope_base,rms_eps);

    // ---- tensor directory: print block-0 + the embed/head tensors with quant types ----
    printf("\n=== TENSORS (block 0 + embed/head) ===\n");
    long data_off=0;
    for(uint64_t i=0;i<n_tensors;i++){
        uint64_t nl; char*tn=rstr(&nl); uint32_t nd=ru32(); uint64_t dims[8]={1,1,1,1,1,1,1,1};
        for(uint32_t k=0;k<nd;k++) dims[k]=ru64();
        uint32_t tt=ru32(); uint64_t off=ru64();
        int show = (strstr(tn,"blk.0.")!=NULL) || !strcmp(tn,"token_embd.weight") || !strcmp(tn,"output_norm.weight") || !strcmp(tn,"output.weight");
        if(show){
            const char*tname=(tt<sizeof(GGML_TYPE)/sizeof(GGML_TYPE[0]))?GGML_TYPE[tt]:"?";
            printf("  %-28s [", tn);
            for(uint32_t k=0;k<nd;k++) printf("%s%llu", k?"x":"", (unsigned long long)dims[k]);
            printf("] %s  off=%llu\n", tname, (unsigned long long)off);
        }
        free(tn);
    }
    printf("\nrung 1 ok — read the real llama3.2:3b structure in C (driver-only host language; no python/go)\n");
    fclose(F);
    return 0;
}

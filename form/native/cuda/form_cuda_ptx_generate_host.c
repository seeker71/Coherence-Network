// form_cuda_ptx_generate_host.c — AUTOREGRESSIVE GREEDY GENERATION on the GPU, end-to-end,
// by reusing the already-proven FORM-emitted .ptx kernels (NO new kernels, NO modified files).
//
// We start from a short prompt of token IDs and grow it one token at a time:
//   embed(tokens) -> [seq x d]        (host-side gather from a deterministic embed table [vocab x d])
//   for L in 0..nlayers-1:  x = block_L(x)   (pre-LN self-attn block, per-layer FFN weights)
//   x = layernorm(x)                          (final norm)
//   logits[t] = matvec(W_out, x[t])  per token -> [seq x vocab]
//   next = argmax(logits[seq-1])              (greedy: take the LAST row)
//   tokens.append(next); seq += 1; repeat for G steps
//
// The whole forward is a kernel-graph over the proven kernels (form_layernorm_f32.ptx,
// form_attention_f32.ptx, form_residual_f32.ptx, form_ffn_fwd_f32.ptx, form_matvec_f32.ptx).
// A CPU oracle runs the IDENTICAL loop (same block_cpu + a CPU argmax). We assert the GPU token-id
// sequence EQUALS the CPU oracle sequence exactly, AND that the final-step logits are bit-exact
// (uint32 compare) as a stronger check. Runtime deps: nvcuda.dll only.
//
// seq grows each step, so we re-alloc + re-run the full forward every step (correctness over speed).
// Scratch that grows: per-row/elementwise buffers [seq x d], the attention scores buffer [seq x seq],
// logits [seq x vocab]. We size every device buffer to the current seq each step.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_generate_host.exe form_cuda_ptx_generate_host.c
// Run:   form_cuda_ptx_generate_host.exe <dir-with-.ptx> [d hid nlayers vocab G]   (default 16 32 3 24 8)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
typedef HMODULE drv_handle;
static drv_handle drv_open(const char *p){ return LoadLibraryA(p); }
static void *drv_sym(drv_handle l,const char*s){ return (void*)(uintptr_t)GetProcAddress(l,s); }
static const char *driver_lib(void){ return "nvcuda.dll"; }
#else
#include <dlfcn.h>
typedef void *drv_handle;
static drv_handle drv_open(const char*p){ return dlopen(p,RTLD_NOW|RTLD_LOCAL); }
static void *drv_sym(drv_handle l,const char*s){ return dlsym(l,s); }
static const char *driver_lib(void){ return "libcuda.so.1"; }
#endif

typedef int CUresult; typedef int CUdevice; typedef void *CUcontext,*CUmodule,*CUfunction,*CUstream;
typedef unsigned long long CUdeviceptr;
#define CUDA_SUCCESS 0
#define CU_JIT_OPTIMIZATION_LEVEL 7
typedef CUresult (*pfn_cuInit)(unsigned);
typedef CUresult (*pfn_cuDeviceGet)(CUdevice*,int);
typedef CUresult (*pfn_cuDeviceGetName)(char*,int,CUdevice);
typedef CUresult (*pfn_cuCtxCreate)(CUcontext*,unsigned,CUdevice);
typedef CUresult (*pfn_cuModuleLoadDataEx)(CUmodule*,const void*,unsigned,int*,void**);
typedef CUresult (*pfn_cuModuleGetFunction)(CUfunction*,CUmodule,const char*);
typedef CUresult (*pfn_cuMemAlloc)(CUdeviceptr*,size_t);
typedef CUresult (*pfn_cuMemFree)(CUdeviceptr);
typedef CUresult (*pfn_cuMemcpyHtoD)(CUdeviceptr,const void*,size_t);
typedef CUresult (*pfn_cuMemcpyDtoH)(void*,CUdeviceptr,size_t);
typedef CUresult (*pfn_cuLaunchKernel)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**);
typedef CUresult (*pfn_cuCtxSynchronize)(void);
typedef CUresult (*pfn_cuGetErrorString)(CUresult,const char**);
static pfn_cuInit cuInit_; static pfn_cuDeviceGet cuDeviceGet_; static pfn_cuDeviceGetName cuDeviceGetName_;
static pfn_cuCtxCreate cuCtxCreate_; static pfn_cuModuleLoadDataEx cuModuleLoadDataEx_; static pfn_cuModuleGetFunction cuModuleGetFunction_;
static pfn_cuMemAlloc cuMemAlloc_; static pfn_cuMemFree cuMemFree_; static pfn_cuMemcpyHtoD cuMemcpyHtoD_; static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_; static pfn_cuCtxSynchronize cuCtxSynchronize_; static pfn_cuGetErrorString cuGetErrorString_;
static void die(const char*w,CUresult r){ const char*m="?"; if(cuGetErrorString_)cuGetErrorString_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=CUDA_SUCCESS)die(#c,_r);}while(0)
static void *res(drv_handle h,const char*n){ void*p=drv_sym(h,n); if(!p){fprintf(stderr,"FAIL sym %s\n",n);exit(1);} return p; }
static float val(int n){ return (float)n/256.0f; }
static float fexp_small(float x){ float n=1,t=1,a=1; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float fgelu(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float e=fexpf_(2.0f*z); float th=(e-1.0f)/(e+1.0f); return (0.5f*x)*(1.0f+th); }
static float fsqrtn(float v){ if(v<=0)return 0; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g; }

static CUfunction load(const char*dir,const char*file,const char*entry){
    char path[1024]; snprintf(path,sizeof(path),"%s/%s",dir,file);
    FILE*f=fopen(path,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",path);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    char*s=malloc((size_t)sz+1); if(fread(s,1,(size_t)sz,f)!=(size_t)sz){exit(1);} s[sz]='\0'; fclose(f);
    int o[1]={CU_JIT_OPTIMIZATION_LEVEL}; void*v[1]={(void*)(uintptr_t)0};
    CUmodule m; CK(cuModuleLoadDataEx_(&m,s,1,o,v)); CUfunction fn; CK(cuModuleGetFunction_(&fn,m,entry)); free(s); return fn;
}

// kernel handles + dims, shared by the block step (same structure as form_cuda_ptx_model_host.c)
static CUfunction K_ln,K_at,K_re,K_ff,K_mv;
static int g_seq,g_d,g_hid; static float g_eps,g_scale;
static CUdeviceptr B_ln1,B_at,B_sc,B_r1,B_ln2,B_ff,B_a;

// one pre-LN self-attn block: out = blk(in) using per-layer FFN weights — verbatim from model host
static void block_gpu(CUdeviceptr in, CUdeviceptr out, CUdeviceptr W1,CUdeviceptr b1,CUdeviceptr W2,CUdeviceptr b2){
    unsigned seq=g_seq,d=g_d,hid=g_hid,sd=(unsigned)seq*d,B=256;
    { void*p[]={&in,&B_ln1,&seq,&d,&g_eps}; CK(cuLaunchKernel_(K_ln,(seq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    { void*p[]={&B_ln1,&B_ln1,&B_ln1,&B_at,&B_sc,&seq,&seq,&d,&g_scale}; CK(cuLaunchKernel_(K_at,(seq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    { void*p[]={&in,&B_at,&B_r1,&sd}; CK(cuLaunchKernel_(K_re,(sd+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    { void*p[]={&B_r1,&B_ln2,&seq,&d,&g_eps}; CK(cuLaunchKernel_(K_ln,(seq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    for(unsigned t=0;t<seq;t++){ CUdeviceptr xi=B_ln2+(CUdeviceptr)t*d*4, yo=B_ff+(CUdeviceptr)t*d*4;
        void*p[]={&W1,&b1,&W2,&b2,&xi,&yo,&B_a,&d,&hid,&d}; CK(cuLaunchKernel_(K_ff,1,1,1,256,1,1,0,NULL,p,NULL)); }
    { void*p[]={&B_r1,&B_ff,&out,&sd}; CK(cuLaunchKernel_(K_re,(sd+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
}
static void block_cpu(const float*in,float*out,const float*W1,const float*b1,const float*W2,const float*b2,
                      float*ln1,float*att,float*sc,float*r1,float*ln2,float*ff,float*h){
    int seq=g_seq,d=g_d,hid=g_hid; float eps=g_eps,scale=g_scale;
    for(int t=0;t<seq;t++){ float s=0; for(int j=0;j<d;j++)s=s+in[(size_t)t*d+j]; float me=s/(float)d; float v=0; for(int j=0;j<d;j++){float dd=in[(size_t)t*d+j]-me; v=v+dd*dd;} float iv=1.0f/fsqrtn(v/(float)d+eps); for(int j=0;j<d;j++)ln1[(size_t)t*d+j]=(in[(size_t)t*d+j]-me)*iv; }
    for(int i=0;i<seq;i++){ for(int j=0;j<seq;j++){ float a=0; for(int l=d;l>0;){l--; float p=ln1[(size_t)i*d+l]*ln1[(size_t)j*d+l]; a=p+a;} sc[(size_t)i*seq+j]=a*scale; }
        float m=sc[(size_t)i*seq+0]; for(int j=1;j<seq;j++){float vv=sc[(size_t)i*seq+j]; if(vv>m)m=vv;} float ss=0; for(int j=0;j<seq;j++){float e=fexpf_(sc[(size_t)i*seq+j]-m); sc[(size_t)i*seq+j]=e; ss=ss+e;} float r=1.0f/ss; for(int j=0;j<seq;j++)sc[(size_t)i*seq+j]=sc[(size_t)i*seq+j]*r;
        for(int mm=0;mm<d;mm++){ float a=0; for(int j=0;j<seq;j++){float p=ln1[(size_t)j*d+mm]*sc[(size_t)i*seq+j]; a=a+p;} att[(size_t)i*d+mm]=a; } }
    for(int i=0;i<seq*d;i++)r1[i]=in[i]+att[i];
    for(int t=0;t<seq;t++){ float s=0; for(int j=0;j<d;j++)s=s+r1[(size_t)t*d+j]; float me=s/(float)d; float v=0; for(int j=0;j<d;j++){float dd=r1[(size_t)t*d+j]-me; v=v+dd*dd;} float iv=1.0f/fsqrtn(v/(float)d+eps); for(int j=0;j<d;j++)ln2[(size_t)t*d+j]=(r1[(size_t)t*d+j]-me)*iv; }
    for(int t=0;t<seq;t++){ for(int k=0;k<hid;k++){ float a=0; for(int j=d;j>0;){j--; float p=W1[(size_t)k*d+j]*ln2[(size_t)t*d+j]; a=p+a;} h[k]=fgelu(a+b1[k]); }
        for(int i=0;i<d;i++){ float a=0; for(int k=hid;k>0;){k--; float p=W2[(size_t)i*hid+k]*h[k]; a=p+a;} ff[(size_t)t*d+i]=a+b2[i]; } }
    for(int i=0;i<seq*d;i++)out[i]=r1[i]+ff[i];
}

// deterministic embedding table [vocab x d]: row=token id, exactly-representable val() entries
static void embed_row(const float*table,int tok,int d,float*dst){ memcpy(dst,&table[(size_t)tok*d],(size_t)d*4); }

// CPU argmax over a vocab-length logits row (ties -> lowest index), matching a simple GPU readback argmax
static int argmax_row(const float*row,int vocab){ int best=0; float bv=row[0]; for(int v=1;v<vocab;v++){ if(row[v]>bv){bv=row[v]; best=v;} } return best; }

int main(int argc,char**argv){
    const char*dir=(argc>1)?argv[1]:".";
    int d=(argc>2)?atoi(argv[2]):16, hid=(argc>3)?atoi(argv[3]):32, NL=(argc>4)?atoi(argv[4]):3, vocab=(argc>5)?atoi(argv[5]):24, G=(argc>6)?atoi(argv[6]):8;
    g_d=d; g_hid=hid; g_eps=1e-5f; { float gg=(float)d; for(int i=0;i<60;i++)gg=0.5f*(gg+(float)d/gg); g_scale=1.0f/gg; }

    // ---- deterministic model weights (identical scheme to form_cuda_ptx_model_host.c) ----
    float *embed=malloc((size_t)vocab*d*4), *Wout=malloc((size_t)vocab*d*4);
    float **W1=malloc(NL*sizeof(float*)),**B1=malloc(NL*sizeof(float*)),**W2=malloc(NL*sizeof(float*)),**B2=malloc(NL*sizeof(float*));
    for(int v=0;v<vocab;v++) for(int j=0;j<d;j++) embed[(size_t)v*d+j]=val((v*9+j*7)%256-128);   // embed table [vocab x d]
    for(int v=0;v<vocab;v++) for(int j=0;j<d;j++) Wout[(size_t)v*d+j]=val((v*13+j*5)%256-128);    // output head [vocab x d]
    for(int L=0;L<NL;L++){ W1[L]=malloc((size_t)hid*d*4); B1[L]=malloc((size_t)hid*4); W2[L]=malloc((size_t)d*hid*4); B2[L]=malloc((size_t)d*4);
        for(int k=0;k<hid;k++){ for(int j=0;j<d;j++)W1[L][(size_t)k*d+j]=val((L*7+k*13+j*3)%256-128); B1[L][k]=val((L*5+k*2)%256-128); }
        for(int i=0;i<d;i++){ for(int k=0;k<hid;k++)W2[L][(size_t)i*hid+k]=val((L*11+i*5+k*3)%256-128); B2[L][i]=val((L*3+i*7)%256-128); } }

    // ---- driver bring-up ----
    drv_handle drv=drv_open(driver_lib()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(pfn_cuInit)res(drv,"cuInit"); cuDeviceGet_=(pfn_cuDeviceGet)res(drv,"cuDeviceGet"); cuDeviceGetName_=(pfn_cuDeviceGetName)res(drv,"cuDeviceGetName");
    cuCtxCreate_=(pfn_cuCtxCreate)res(drv,"cuCtxCreate_v2"); cuModuleLoadDataEx_=(pfn_cuModuleLoadDataEx)res(drv,"cuModuleLoadDataEx"); cuModuleGetFunction_=(pfn_cuModuleGetFunction)res(drv,"cuModuleGetFunction");
    cuMemAlloc_=(pfn_cuMemAlloc)res(drv,"cuMemAlloc_v2"); cuMemFree_=(pfn_cuMemFree)res(drv,"cuMemFree_v2"); cuMemcpyHtoD_=(pfn_cuMemcpyHtoD)res(drv,"cuMemcpyHtoD_v2"); cuMemcpyDtoH_=(pfn_cuMemcpyDtoH)res(drv,"cuMemcpyDtoH_v2");
    cuLaunchKernel_=(pfn_cuLaunchKernel)res(drv,"cuLaunchKernel"); cuCtxSynchronize_=(pfn_cuCtxSynchronize)res(drv,"cuCtxSynchronize"); cuGetErrorString_=(pfn_cuGetErrorString)drv_sym(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dev; CK(cuDeviceGet_(&dev,0)); char dn[256]={0}; cuDeviceGetName_(dn,sizeof(dn),dev); CUcontext ctx; CK(cuCtxCreate_(&ctx,0,dev));
    K_ln=load(dir,"form_layernorm_f32.ptx","form_layernorm_f32"); K_at=load(dir,"form_attention_f32.ptx","form_attention_f32");
    K_re=load(dir,"form_residual_f32.ptx","form_residual_f32"); K_ff=load(dir,"form_ffn_fwd_f32.ptx","form_ffn_fwd_f32"); K_mv=load(dir,"form_matvec_f32.ptx","form_matvec_f32");

    // per-layer FFN weights live on the device for the whole run (fixed sizes)
    CUdeviceptr Bwo; CK(cuMemAlloc_(&Bwo,(size_t)vocab*d*4)); CK(cuMemcpyHtoD_(Bwo,Wout,(size_t)vocab*d*4));
    CUdeviceptr dW1[64],dB1[64],dW2[64],dB2[64];
    for(int L=0;L<NL;L++){ CK(cuMemAlloc_(&dW1[L],(size_t)hid*d*4)); CK(cuMemAlloc_(&dB1[L],(size_t)hid*4)); CK(cuMemAlloc_(&dW2[L],(size_t)d*hid*4)); CK(cuMemAlloc_(&dB2[L],(size_t)d*4));
        CK(cuMemcpyHtoD_(dW1[L],W1[L],(size_t)hid*d*4)); CK(cuMemcpyHtoD_(dB1[L],B1[L],(size_t)hid*4)); CK(cuMemcpyHtoD_(dW2[L],W2[L],(size_t)d*hid*4)); CK(cuMemcpyHtoD_(dB2[L],B2[L],(size_t)d*4)); }
    CK(cuMemAlloc_(&B_a,(size_t)hid*4));   // FFN per-token hidden scratch (size hid, seq-independent)

    // ---- prompt ----
    int prompt[3]={1,2,3}, plen=3;
    int cap=plen+G+1;
    int *tok_gpu=malloc((size_t)cap*sizeof(int)), *tok_cpu=malloc((size_t)cap*sizeof(int));
    for(int i=0;i<plen;i++){ tok_gpu[i]=prompt[i]; tok_cpu[i]=prompt[i]; }

    // last-step bit-exact logits capture (full vocab logits row of the LAST token at the final step)
    float *last_logits_gpu=malloc((size_t)vocab*4), *last_logits_cpu=malloc((size_t)vocab*4);

    // =================== GPU autoregressive greedy loop ===================
    for(int step=0; step<G; step++){
        int seq=plen+step; g_seq=seq;
        size_t sd=(size_t)seq*d, sv=(size_t)seq*vocab;
        // host-side embedding gather -> [seq x d]
        float *emb=malloc(sd*4);
        for(int t=0;t<seq;t++) embed_row(embed,tok_gpu[t],d,&emb[(size_t)t*d]);
        // device buffers sized to the current seq (re-alloc each step; scores grows seq x seq)
        CUdeviceptr Bx,By,Bf,Blog;
        CK(cuMemAlloc_(&Bx,sd*4)); CK(cuMemAlloc_(&By,sd*4)); CK(cuMemAlloc_(&Bf,sd*4)); CK(cuMemAlloc_(&Blog,sv*4));
        CK(cuMemAlloc_(&B_ln1,sd*4)); CK(cuMemAlloc_(&B_at,sd*4)); CK(cuMemAlloc_(&B_sc,(size_t)seq*seq*4)); CK(cuMemAlloc_(&B_r1,sd*4)); CK(cuMemAlloc_(&B_ln2,sd*4)); CK(cuMemAlloc_(&B_ff,sd*4));
        CK(cuMemcpyHtoD_(Bx,emb,sd*4));
        // N blocks
        CUdeviceptr cur=Bx, nxt=By;
        for(int L=0;L<NL;L++){ block_gpu(cur,nxt,dW1[L],dB1[L],dW2[L],dB2[L]); CUdeviceptr t=cur;cur=nxt;nxt=t; }
        // final layernorm -> Bf
        { unsigned useq=seq,ud=d,B=256; void*p[]={&cur,&Bf,&useq,&ud,&g_eps}; CK(cuLaunchKernel_(K_ln,(useq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
        // logits[t] = matvec(Wout[vocab x d], fln[t]) per token -> [seq x vocab]
        for(int t=0;t<seq;t++){ CUdeviceptr xt=Bf+(CUdeviceptr)t*d*4, lt=Blog+(CUdeviceptr)t*vocab*4; unsigned uv=vocab,ud=d;
            void*p[]={&Bwo,&xt,&lt,&uv,&ud}; CK(cuLaunchKernel_(K_mv,1,1,1,256,1,1,0,NULL,p,NULL)); }
        CK(cuCtxSynchronize_());
        // read back the LAST token's logits, argmax -> next token
        float *lastrow=malloc((size_t)vocab*4);
        CK(cuMemcpyDtoH_(lastrow,Blog+(CUdeviceptr)(seq-1)*vocab*4,(size_t)vocab*4));
        int next=argmax_row(lastrow,vocab);
        tok_gpu[seq]=next;
        if(step==G-1) memcpy(last_logits_gpu,lastrow,(size_t)vocab*4);
        free(lastrow); free(emb);
        cuMemFree_(Bx); cuMemFree_(By); cuMemFree_(Bf); cuMemFree_(Blog);
        cuMemFree_(B_ln1); cuMemFree_(B_at); cuMemFree_(B_sc); cuMemFree_(B_r1); cuMemFree_(B_ln2); cuMemFree_(B_ff);
    }

    // =================== CPU oracle: identical autoregressive greedy loop ===================
    for(int step=0; step<G; step++){
        int seq=plen+step; g_seq=seq;
        size_t sd=(size_t)seq*d;
        float *emb=malloc(sd*4),*cur=malloc(sd*4),*nxt=malloc(sd*4),
              *ln1=malloc(sd*4),*att=malloc(sd*4),*sc=malloc((size_t)seq*seq*4),*r1=malloc(sd*4),*ln2=malloc(sd*4),*ff=malloc(sd*4),
              *h=malloc((size_t)hid*4),*fln=malloc(sd*4),*lrow=malloc((size_t)vocab*4);
        for(int t=0;t<seq;t++) embed_row(embed,tok_cpu[t],d,&emb[(size_t)t*d]);
        memcpy(cur,emb,sd*4);
        for(int L=0;L<NL;L++){ block_cpu(cur,nxt,W1[L],B1[L],W2[L],B2[L],ln1,att,sc,r1,ln2,ff,h); float*tmp=cur;cur=nxt;nxt=tmp; }
        // final layernorm
        for(int t=0;t<seq;t++){ float s=0; for(int j=0;j<d;j++)s=s+cur[(size_t)t*d+j]; float me=s/(float)d; float v=0; for(int j=0;j<d;j++){float dd=cur[(size_t)t*d+j]-me; v=v+dd*dd;} float iv=1.0f/fsqrtn(v/(float)d+g_eps); for(int j=0;j<d;j++)fln[(size_t)t*d+j]=(cur[(size_t)t*d+j]-me)*iv; }
        // logits of the LAST token only (that is what greedy needs), then argmax
        int lt=seq-1; for(int v=0;v<vocab;v++){ float a=0; for(int j=d;j>0;){j--; float p=Wout[(size_t)v*d+j]*fln[(size_t)lt*d+j]; a=p+a;} lrow[v]=a; }
        int next=argmax_row(lrow,vocab);
        tok_cpu[seq]=next;
        if(step==G-1) memcpy(last_logits_cpu,lrow,(size_t)vocab*4);
        free(emb);free(cur);free(nxt);free(ln1);free(att);free(sc);free(r1);free(ln2);free(ff);free(h);free(fln);free(lrow);
    }

    // =================== compare ===================
    int total=plen+G;
    printf("device=%s\n", dn[0]?dn:"(unknown)");
    printf("autoregressive greedy generation: embed -> %d x block -> final-ln -> logits -> argmax(last)\n", NL);
    printf("d=%d hid=%d nlayers=%d vocab=%d  prompt_len=%d  generate=%d new tokens (seq grows %d..%d)\n",
           d,hid,NL,vocab,plen,G,plen,total-1);
    printf("prompt tokens : "); for(int i=0;i<plen;i++) printf("%d ",tok_gpu[i]); printf("\n");
    printf("GPU generated : "); for(int i=plen;i<total;i++) printf("%d ",tok_gpu[i]); printf("\n");
    printf("CPU generated : "); for(int i=plen;i<total;i++) printf("%d ",tok_cpu[i]); printf("\n");
    printf("full GPU seq  : "); for(int i=0;i<total;i++) printf("%d ",tok_gpu[i]); printf("\n");

    int seq_match=1; for(int i=0;i<total;i++) if(tok_gpu[i]!=tok_cpu[i]) seq_match=0;
    int exact=0; float max_abs=0.0f;
    for(int v=0;v<vocab;v++){ uint32_t a,b; memcpy(&a,&last_logits_gpu[v],4); memcpy(&b,&last_logits_cpu[v],4); if(a==b)exact++; float dd=last_logits_gpu[v]-last_logits_cpu[v]; if(dd<0)dd=-dd; if(dd>max_abs)max_abs=dd; }
    printf("token_id_sequence_match=%s (%d ids)\n", seq_match?"YES":"NO", total);
    printf("final_step_logits_bitexact=%d/%d max_abs_diff=%g\n", exact, vocab, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX kernel-graph; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());

    if(!seq_match){ printf("FAIL  token-id sequences differ\n"); return 1; }
    if(exact!=vocab){ printf("FAIL  final-step logits not bit-exact\n"); return 1; }
    printf("MATCH — GPU autoregressive greedy generation is bit-exact to the CPU oracle (token ids + final logits)\n");
    return 0;
}

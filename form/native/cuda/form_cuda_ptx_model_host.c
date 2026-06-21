// form_cuda_ptx_model_host.c — a tiny FORM-NATIVE TRANSFORMER forward pass, end-to-end on the GPU,
// by composing the proven form-ptx kernels into a kernel-graph:
//   x = embedded tokens [seq x d]   (embedding gather is a host-side lookup, not compute)
//   for L in 0..nlayers-1:  x = block_L(x)        (pre-LN self-attn block, per-layer FFN weights)
//   x = layernorm(x)                              (final norm)
//   logits[t] = matvec(W_out, x[t])  per token    -> [seq x vocab]
// Every compute op is a proven kernel; the CPU oracle chains the same ops, so the whole forward is
// bit-exact. Runtime deps: nvcuda.dll only. No nvcc/nvrtc/go/python/rust/shell/clang.
//
// Build: gcc -O2 -ffp-contract=off -o form_cuda_ptx_model_host.exe form_cuda_ptx_model_host.c
// Run:   form_cuda_ptx_model_host.exe <dir-with-.ptx> [seq d hid nlayers vocab]   (default 6 16 32 3 24)

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
typedef CUresult (*pfn_cuMemcpyHtoD)(CUdeviceptr,const void*,size_t);
typedef CUresult (*pfn_cuMemcpyDtoH)(void*,CUdeviceptr,size_t);
typedef CUresult (*pfn_cuLaunchKernel)(CUfunction,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,CUstream,void**,void**);
typedef CUresult (*pfn_cuCtxSynchronize)(void);
typedef CUresult (*pfn_cuGetErrorString)(CUresult,const char**);
static pfn_cuInit cuInit_; static pfn_cuDeviceGet cuDeviceGet_; static pfn_cuDeviceGetName cuDeviceGetName_;
static pfn_cuCtxCreate cuCtxCreate_; static pfn_cuModuleLoadDataEx cuModuleLoadDataEx_; static pfn_cuModuleGetFunction cuModuleGetFunction_;
static pfn_cuMemAlloc cuMemAlloc_; static pfn_cuMemcpyHtoD cuMemcpyHtoD_; static pfn_cuMemcpyDtoH cuMemcpyDtoH_;
static pfn_cuLaunchKernel cuLaunchKernel_; static pfn_cuCtxSynchronize cuCtxSynchronize_; static pfn_cuGetErrorString cuGetErrorString_;
static void die(const char*w,CUresult r){ const char*m="?"; if(cuGetErrorString_)cuGetErrorString_(r,&m); fprintf(stderr,"FAIL %s -> %d (%s)\n",w,r,m); exit(1);}
#define CK(c) do{CUresult _r=(c); if(_r!=CUDA_SUCCESS)die(#c,_r);}while(0)
static void *res(drv_handle h,const char*n){ void*p=drv_sym(h,n); if(!p){fprintf(stderr,"FAIL sym %s\n",n);exit(1);} return p; }
static float val(int n){ return (float)n/256.0f; }
static float fexp_small(float x){ float n=1,t=1,a=1; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float fgelu(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float e=fexpf_(2.0f*z); float th=(e-1.0f)/(e+1.0f); return (0.5f*x)*(1.0f+th); }
static float fsqrtn(float v){ if(v<=0)return 0; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g; }

static char g[4096];
static CUfunction load(const char*dir,const char*file,const char*entry){
    char path[1024]; snprintf(path,sizeof(path),"%s/%s",dir,file);
    FILE*f=fopen(path,"rb"); if(!f){fprintf(stderr,"FAIL open %s\n",path);exit(1);}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    char*s=malloc((size_t)sz+1); if(fread(s,1,(size_t)sz,f)!=(size_t)sz){exit(1);} s[sz]='\0'; fclose(f);
    int o[1]={CU_JIT_OPTIMIZATION_LEVEL}; void*v[1]={(void*)(uintptr_t)0};
    CUmodule m; CK(cuModuleLoadDataEx_(&m,s,1,o,v)); CUfunction fn; CK(cuModuleGetFunction_(&fn,m,entry)); free(s); return fn;
}

// kernel handles + dims, shared by the block step
static CUfunction K_ln,K_at,K_re,K_ff,K_mv;
static int g_seq,g_d,g_hid; static float g_eps,g_scale;
static CUdeviceptr B_ln1,B_at,B_sc,B_r1,B_ln2,B_ff,B_a;

// one pre-LN self-attn block: out = blk(in) using per-layer FFN weights
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

int main(int argc,char**argv){
    const char*dir=(argc>1)?argv[1]:".";
    int seq=(argc>2)?atoi(argv[2]):6, d=(argc>3)?atoi(argv[3]):16, hid=(argc>4)?atoi(argv[4]):32, NL=(argc>5)?atoi(argv[5]):3, vocab=(argc>6)?atoi(argv[6]):24;
    g_seq=seq; g_d=d; g_hid=hid; g_eps=1e-5f; { float gg=(float)d; for(int i=0;i<60;i++)gg=0.5f*(gg+(float)d/gg); g_scale=1.0f/gg; }
    drv_handle drv=drv_open(driver_lib()); if(!drv){fprintf(stderr,"SKIP no driver\n");return 2;}
    cuInit_=(pfn_cuInit)res(drv,"cuInit"); cuDeviceGet_=(pfn_cuDeviceGet)res(drv,"cuDeviceGet"); cuDeviceGetName_=(pfn_cuDeviceGetName)res(drv,"cuDeviceGetName");
    cuCtxCreate_=(pfn_cuCtxCreate)res(drv,"cuCtxCreate_v2"); cuModuleLoadDataEx_=(pfn_cuModuleLoadDataEx)res(drv,"cuModuleLoadDataEx"); cuModuleGetFunction_=(pfn_cuModuleGetFunction)res(drv,"cuModuleGetFunction");
    cuMemAlloc_=(pfn_cuMemAlloc)res(drv,"cuMemAlloc_v2"); cuMemcpyHtoD_=(pfn_cuMemcpyHtoD)res(drv,"cuMemcpyHtoD_v2"); cuMemcpyDtoH_=(pfn_cuMemcpyDtoH)res(drv,"cuMemcpyDtoH_v2");
    cuLaunchKernel_=(pfn_cuLaunchKernel)res(drv,"cuLaunchKernel"); cuCtxSynchronize_=(pfn_cuCtxSynchronize)res(drv,"cuCtxSynchronize"); cuGetErrorString_=(pfn_cuGetErrorString)drv_sym(drv,"cuGetErrorString");
    CK(cuInit_(0)); CUdevice dev; CK(cuDeviceGet_(&dev,0)); char dn[256]={0}; cuDeviceGetName_(dn,sizeof(dn),dev); CUcontext ctx; CK(cuCtxCreate_(&ctx,0,dev));
    K_ln=load(dir,"form_layernorm_f32.ptx","form_layernorm_f32"); K_at=load(dir,"form_attention_f32.ptx","form_attention_f32");
    K_re=load(dir,"form_residual_f32.ptx","form_residual_f32"); K_ff=load(dir,"form_ffn_fwd_f32.ptx","form_ffn_fwd_f32"); K_mv=load(dir,"form_matvec_f32.ptx","form_matvec_f32");

    size_t sd=(size_t)seq*d, sv=(size_t)seq*vocab;
    float *x=malloc(sd*4), *Wout=malloc((size_t)vocab*d*4), *logits=malloc(sv*4), *ref=malloc(sv*4);
    float **W1=malloc(NL*sizeof(float*)),**B1=malloc(NL*sizeof(float*)),**W2=malloc(NL*sizeof(float*)),**B2=malloc(NL*sizeof(float*));
    for(size_t i=0;i<sd;i++) x[i]=val(((int)(i*17+3))%256-128);   // post-embedding activations
    for(int v=0;v<vocab;v++) for(int j=0;j<d;j++) Wout[(size_t)v*d+j]=val((v*13+j*5)%256-128);
    for(int L=0;L<NL;L++){ W1[L]=malloc((size_t)hid*d*4); B1[L]=malloc((size_t)hid*4); W2[L]=malloc((size_t)d*hid*4); B2[L]=malloc((size_t)d*4);
        for(int k=0;k<hid;k++){ for(int j=0;j<d;j++)W1[L][(size_t)k*d+j]=val((L*7+k*13+j*3)%256-128); B1[L][k]=val((L*5+k*2)%256-128); }
        for(int i=0;i<d;i++){ for(int k=0;k<hid;k++)W2[L][(size_t)i*hid+k]=val((L*11+i*5+k*3)%256-128); B2[L][i]=val((L*3+i*7)%256-128); } }

    // ---- CPU oracle ----
    { float *cur=malloc(sd*4),*nxt=malloc(sd*4),*ln1=malloc(sd*4),*att=malloc(sd*4),*sc=malloc((size_t)seq*seq*4),*r1=malloc(sd*4),*ln2=malloc(sd*4),*ff=malloc(sd*4),*h=malloc((size_t)hid*4),*fln=malloc(sd*4);
      memcpy(cur,x,sd*4);
      for(int L=0;L<NL;L++){ block_cpu(cur,nxt,W1[L],B1[L],W2[L],B2[L],ln1,att,sc,r1,ln2,ff,h); float*tmp=cur;cur=nxt;nxt=tmp; }
      for(int t=0;t<seq;t++){ float s=0; for(int j=0;j<d;j++)s=s+cur[(size_t)t*d+j]; float me=s/(float)d; float v=0; for(int j=0;j<d;j++){float dd=cur[(size_t)t*d+j]-me; v=v+dd*dd;} float iv=1.0f/fsqrtn(v/(float)d+g_eps); for(int j=0;j<d;j++)fln[(size_t)t*d+j]=(cur[(size_t)t*d+j]-me)*iv; }
      for(int t=0;t<seq;t++) for(int v=0;v<vocab;v++){ float a=0; for(int j=d;j>0;){j--; float p=Wout[(size_t)v*d+j]*fln[(size_t)t*d+j]; a=p+a;} ref[(size_t)t*vocab+v]=a; }
      free(cur);free(nxt);free(ln1);free(att);free(sc);free(r1);free(ln2);free(ff);free(h);free(fln);
    }

    // ---- GPU forward ----
    CUdeviceptr Bx,By,Bf,Bwo,Blog; CUdeviceptr dW1[64],dB1[64],dW2[64],dB2[64];
    CK(cuMemAlloc_(&Bx,sd*4)); CK(cuMemAlloc_(&By,sd*4)); CK(cuMemAlloc_(&Bf,sd*4)); CK(cuMemAlloc_(&Bwo,(size_t)vocab*d*4)); CK(cuMemAlloc_(&Blog,sv*4));
    CK(cuMemAlloc_(&B_ln1,sd*4)); CK(cuMemAlloc_(&B_at,sd*4)); CK(cuMemAlloc_(&B_sc,(size_t)seq*seq*4)); CK(cuMemAlloc_(&B_r1,sd*4)); CK(cuMemAlloc_(&B_ln2,sd*4)); CK(cuMemAlloc_(&B_ff,sd*4)); CK(cuMemAlloc_(&B_a,(size_t)hid*4));
    CK(cuMemcpyHtoD_(Bx,x,sd*4)); CK(cuMemcpyHtoD_(Bwo,Wout,(size_t)vocab*d*4));
    for(int L=0;L<NL;L++){ CK(cuMemAlloc_(&dW1[L],(size_t)hid*d*4)); CK(cuMemAlloc_(&dB1[L],(size_t)hid*4)); CK(cuMemAlloc_(&dW2[L],(size_t)d*hid*4)); CK(cuMemAlloc_(&dB2[L],(size_t)d*4));
        CK(cuMemcpyHtoD_(dW1[L],W1[L],(size_t)hid*d*4)); CK(cuMemcpyHtoD_(dB1[L],B1[L],(size_t)hid*4)); CK(cuMemcpyHtoD_(dW2[L],W2[L],(size_t)d*hid*4)); CK(cuMemcpyHtoD_(dB2[L],B2[L],(size_t)d*4)); }
    CUdeviceptr cur=Bx, nxt=By;
    for(int L=0;L<NL;L++){ block_gpu(cur,nxt,dW1[L],dB1[L],dW2[L],dB2[L]); CUdeviceptr t=cur;cur=nxt;nxt=t; }
    // final layernorm -> Bf
    { unsigned useq=seq,ud=d,B=256; void*p[]={&cur,&Bf,&useq,&ud,&g_eps}; CK(cuLaunchKernel_(K_ln,(useq+B-1)/B,1,1,B,1,1,0,NULL,p,NULL)); }
    // logits[t] = matvec(Wout[vocab x d], fln[t])  per token
    for(int t=0;t<seq;t++){ CUdeviceptr xt=Bf+(CUdeviceptr)t*d*4, lt=Blog+(CUdeviceptr)t*vocab*4; unsigned uv=vocab,ud=d;
        void*p[]={&Bwo,&xt,&lt,&uv,&ud}; CK(cuLaunchKernel_(K_mv,1,1,1,256,1,1,0,NULL,p,NULL)); }
    CK(cuCtxSynchronize_());
    CK(cuMemcpyDtoH_(logits,Blog,sv*4));

    int exact=0; float max_abs=0.0f;
    for(size_t i=0;i<sv;i++){ uint32_t a,b; memcpy(&a,&logits[i],4); memcpy(&b,&ref[i],4); if(a==b)exact++; float dd=logits[i]-ref[i]; if(dd<0)dd=-dd; if(dd>max_abs)max_abs=dd; }
    printf("device=%s\n", dn[0]?dn:"(unknown)");
    printf("tiny transformer forward: embed -> %d x block -> final-ln -> logits[seq x vocab]\n", NL);
    printf("seq=%d d=%d hid=%d nlayers=%d vocab=%d  (%d kernel launches/layer + head)\n", seq,d,hid,NL,vocab, 4+seq);
    printf("parity_bitexact_logits=%d/%zu max_abs_diff=%g\n", exact, sv, (double)max_abs);
    printf("runtime_deps=%s only (Form-emitted PTX kernel-graph; no nvcc/nvrtc/go/python/rust/shell/clang)\n", driver_lib());
    if(exact!=(int)sv){ printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — a tiny FORM-NATIVE TRANSFORMER did a forward pass to logits on the GPU, bit-exact to the recipe\n");
    return 0;
}

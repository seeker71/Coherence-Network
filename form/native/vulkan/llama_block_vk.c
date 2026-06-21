/* llama_block_vk.c — the FULL llama decoder block (lblk-block-causal, form-stdlib/llama-block.fk)
 * end-to-end on the RTX 4070's Vulkan ICD as a MULTI-DISPATCH kernel-graph, bit-exact (uint32) to the
 * CPU recipe oracle. This is the Vulkan twin of form_cuda_ptx_llama_block_host.c (the PTX 42-launch
 * graph): it composes the SAME stages over resident device buffers, swapping the PTX launches for
 * vkCmdDispatch nodes with a vkCmdPipelineBarrier (COMPUTE->COMPUTE, SHADER_WRITE->SHADER_READ)
 * between every dependent stage, then a SINGLE submit. It ports the PTX host's CPU oracle op-for-op and
 * the SAME val(n) input seeds for the bit-gate.
 *
 * lblk-block-causal (each stage four-way / PTX-proven):
 *   n1 = RMSNorm(x, g1, eps)                                  (rmsnorm.comp; per-channel gain g1)
 *   q  = RoPE(Wq*n1, pos); k = RoPE(Wk*n1, pos); v = Wv*n1    (bias-free proj.comp; q/k roped, v not)
 *   attn = causal_attention(q, k, v, scale)                   (attention_mhc.comp, nheads=1)
 *   h  = x + Wo*attn                                           (residual.comp)
 *   n2 = RMSNorm(h, g2, eps)
 *   y  = h + Wd*SwiGLU(Wg*n2, Wu*n2)                           (swiglu.comp; SwiGLU = silu(gate)*up)
 * pos = token index; HD = head dim. bias-free projections reuse proj.comp with a zero bias buffer.
 *
 * Three NEW Form-minted .spv added here (rmsnorm/swiglu/rope), composed with three already-proven
 * (proj/attention_mhc/residual). The rope/rmsnorm/swiglu shaders divide -> each carries
 * RoundingModeRTE via SPV_KHR_float_controls, built --target-env vulkan1.1.
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no Vulkan.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include llama_block_vk.c -o llama_block_vk.exe
 * Run:
 *   llama_block_vk.exe [seq d HD hid]   (defaults 4 16 16 32; also exercised at 8 32 32 64)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>

#if defined(_WIN32)
  #include <windows.h>
  #define VKLIB      "vulkan-1.dll"
  #define DLOPEN(n)  ((void*)LoadLibraryA(n))
  #define DLSYM(h,n) ((void*)GetProcAddress((HMODULE)(h),(n)))
  #define DLCLOSE(h) FreeLibrary((HMODULE)(h))
#else
  #include <dlfcn.h>
  #define VKLIB      "libvulkan.so"
  #define DLOPEN(n)  dlopen((n), RTLD_NOW|RTLD_LOCAL)
  #define DLSYM(h,n) dlsym((h),(n))
  #define DLCLOSE(h) dlclose(h)
#endif

#define VKCHECK(expr) do { VkResult _r=(expr); if (_r!=VK_SUCCESS){ \
  fprintf(stderr,"%s failed: VkResult=%d (line %d)\n",#expr,(int)_r,__LINE__); exit(2);} } while(0)
#define DIE(msg) do { fprintf(stderr,"%s\n",(msg)); exit(2);} while(0)

static PFN_vkGetInstanceProcAddr vkGetInstanceProcAddr;
static PFN_vkCreateInstance vkCreateInstance;
static PFN_vkDestroyInstance vkDestroyInstance;
static PFN_vkEnumeratePhysicalDevices vkEnumeratePhysicalDevices;
static PFN_vkGetPhysicalDeviceProperties vkGetPhysicalDeviceProperties;
static PFN_vkGetPhysicalDeviceQueueFamilyProperties vkGetPhysicalDeviceQueueFamilyProperties;
static PFN_vkGetPhysicalDeviceMemoryProperties vkGetPhysicalDeviceMemoryProperties;
static PFN_vkCreateDevice vkCreateDevice;
static PFN_vkDestroyDevice vkDestroyDevice;
static PFN_vkGetDeviceQueue vkGetDeviceQueue;
static PFN_vkCreateBuffer vkCreateBuffer;
static PFN_vkDestroyBuffer vkDestroyBuffer;
static PFN_vkGetBufferMemoryRequirements vkGetBufferMemoryRequirements;
static PFN_vkAllocateMemory vkAllocateMemory;
static PFN_vkFreeMemory vkFreeMemory;
static PFN_vkBindBufferMemory vkBindBufferMemory;
static PFN_vkMapMemory vkMapMemory;
static PFN_vkUnmapMemory vkUnmapMemory;
static PFN_vkCreateDescriptorSetLayout vkCreateDescriptorSetLayout;
static PFN_vkDestroyDescriptorSetLayout vkDestroyDescriptorSetLayout;
static PFN_vkCreateDescriptorPool vkCreateDescriptorPool;
static PFN_vkDestroyDescriptorPool vkDestroyDescriptorPool;
static PFN_vkAllocateDescriptorSets vkAllocateDescriptorSets;
static PFN_vkUpdateDescriptorSets vkUpdateDescriptorSets;
static PFN_vkCreatePipelineLayout vkCreatePipelineLayout;
static PFN_vkDestroyPipelineLayout vkDestroyPipelineLayout;
static PFN_vkCreateShaderModule vkCreateShaderModule;
static PFN_vkDestroyShaderModule vkDestroyShaderModule;
static PFN_vkCreateComputePipelines vkCreateComputePipelines;
static PFN_vkDestroyPipeline vkDestroyPipeline;
static PFN_vkCreateCommandPool vkCreateCommandPool;
static PFN_vkDestroyCommandPool vkDestroyCommandPool;
static PFN_vkAllocateCommandBuffers vkAllocateCommandBuffers;
static PFN_vkBeginCommandBuffer vkBeginCommandBuffer;
static PFN_vkEndCommandBuffer vkEndCommandBuffer;
static PFN_vkCmdBindPipeline vkCmdBindPipeline;
static PFN_vkCmdBindDescriptorSets vkCmdBindDescriptorSets;
static PFN_vkCmdPushConstants vkCmdPushConstants;
static PFN_vkCmdDispatch vkCmdDispatch;
static PFN_vkCmdPipelineBarrier vkCmdPipelineBarrier;
static PFN_vkQueueSubmit vkQueueSubmit;
static PFN_vkQueueWaitIdle vkQueueWaitIdle;

#define LOAD_I(inst,name) do { name=(PFN_##name)vkGetInstanceProcAddr((inst),#name); \
  if(!name) DIE("missing entry point: " #name); } while(0)

static uint32_t find_mem_type(const VkPhysicalDeviceMemoryProperties *mp, uint32_t typeBits, VkMemoryPropertyFlags flags) {
    for (uint32_t i = 0; i < mp->memoryTypeCount; ++i)
        if ((typeBits & (1u << i)) && (mp->memoryTypes[i].propertyFlags & flags) == flags) return i;
    DIE("no HOST_VISIBLE|HOST_COHERENT memory type"); return 0;
}
static void make_buffer(VkDevice dev, const VkPhysicalDeviceMemoryProperties *mp, VkDeviceSize size, VkBuffer *buf, VkDeviceMemory *mem) {
    VkBufferCreateInfo bci = {0};
    bci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO; bci.size = size ? size : 4;
    bci.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT; bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    VKCHECK(vkCreateBuffer(dev, &bci, NULL, buf));
    VkMemoryRequirements req; vkGetBufferMemoryRequirements(dev, *buf, &req);
    VkMemoryAllocateInfo mai = {0};
    mai.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO; mai.allocationSize = req.size;
    mai.memoryTypeIndex = find_mem_type(mp, req.memoryTypeBits,
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VKCHECK(vkAllocateMemory(dev, &mai, NULL, mem));
    VKCHECK(vkBindBufferMemory(dev, *buf, *mem, 0));
}
static uint32_t *read_spv(const char *path, size_t *out_bytes) {
    FILE *f = fopen(path, "rb"); if (!f) { fprintf(stderr,"cannot open %s\n",path); exit(2);}
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    if (n <= 0 || (n & 3)) DIE(".spv size invalid");
    uint32_t *code = malloc((size_t)n);
    if (fread(code, 1, (size_t)n, f) != (size_t)n) DIE(".spv read short");
    fclose(f);
    if (code[0] != 0x07230203u) DIE(".spv bad magic");
    *out_bytes = (size_t)n; return code;
}
static float val(int n) { return (float)n / 256.0f; }
static uint32_t f2u(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

/* ============================================================================
 * CPU oracle — lblk-block-causal, op-for-op with form_cuda_ptx_llama_block_host.c
 * (recipe-exact fp32; no libm transcendentals, no fma).
 * ============================================================================ */
static int SEQ,D,HD,HID; static float EPS,SCALE;

/* Newton-50 sqrt (tn-sqrt): g0=v; g=0.5*(g+v/g). */
static float fsq(float v){ if(v<=0.0f)return 0.0f; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g; }
/* fexp = recipe 14-term Taylor + halving-reduce + square-back. */
static float fexs(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fex(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x*0.5f; k++; } float v=fexs(x); while(k>0){ v=v*v; k--; } return v; }
/* sigmoid / silu / swiglu. */
static float sigm(float x){ return 1.0f/(1.0f+fex(0.0f-x)); }
static float swiglu(float g,float u){ return (g*sigm(g))*u; }

/* RoPE oracle: rope.fk over trig.fk, op-for-op. */
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
static void c_rope(const float*q,float*out,int n,int HDp,int pos){
    for(int t=0;t<n/2;t++){
        int i=2*t, hd=i%HDp;
        float e=(-1.0f*(float)hd)/((float)HDp*1.0f);
        float freq=c_fpow(10000.0f,e);
        float a=((float)pos*1.0f)*freq;
        float c=c_fcos(a), s=c_fsin(a);
        float q0=q[i], q1=q[i+1];
        out[i]   = q0*c - q1*s;
        out[i+1] = q0*s + q1*c;
    }
}
/* RMSNorm: per-channel gain g (length D), broadcast to every token. meansq + Newton sqrt. */
static void c_rms(const float*in,const float*g,float*out){
    for(int t=0;t<SEQ;t++){
        float ss=0.0f; for(int j=0;j<D;j++){ float xv=in[(size_t)t*D+j]; ss=ss+xv*xv; }
        float meansq=ss/(float)D; float rms=fsq(meansq+EPS); float r=1.0f/rms;
        for(int j=0;j<D;j++) out[(size_t)t*D+j]=(in[(size_t)t*D+j]*r)*g[j];
    }
}
/* bias-free matvec per token: y[t] = W * x[t], W is outd x ind, downward right-fold (tb-dot). */
static void c_matvec_seq(const float*W,const float*X,float*Y,int outd,int ind){
    for(int t=0;t<SEQ;t++)for(int o=0;o<outd;o++){ float a=0.0f; for(int l=ind;l>0;){ l--; float p=W[(size_t)o*ind+l]*X[(size_t)t*ind+l]; a=p+a; } Y[(size_t)t*outd+o]=a; }
}
static void c_rope_seq(const float*X,float*Y){ for(int t=0;t<SEQ;t++) c_rope(X+(size_t)t*D, Y+(size_t)t*D, D, HD, t); }
/* causal single-head attention over the full D (tb-attn-seq-causal): query i attends keys [0..i]. */
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

/* ============================================================================
 * pipeline registry — one descriptor-set-layout / pipeline per distinct shader
 * ============================================================================ */
enum { SH_RMS=0, SH_PROJ, SH_ROPE, SH_ATT, SH_RES, SH_SWIGLU, NSHADER };
static const char *SH_SPV[NSHADER]   = {"rmsnorm.spv","proj.spv","rope.spv","attention_mhc.spv","residual.spv","swiglu.spv"};
static const int   SH_BINDS[NSHADER] = { 3,           4,         2,         5,                  3,             3            };
static const uint32_t SH_PCSZ[NSHADER]={ 12u,         12u,       12u,       20u,                8u,            4u           };
/* local_size_x baked into each .comp — group count = ceil(work / lsx). */
static const uint32_t SH_LSX[NSHADER]= { 64u,         256u,      64u,       256u,               64u,           256u         };

static VkDevice              DEV;
static VkDescriptorSetLayout SH_DSL[NSHADER];
static VkPipelineLayout      SH_PL[NSHADER];
static VkPipeline            SH_PIPE[NSHADER];
static VkShaderModule        SH_MOD[NSHADER];

/* a dispatch node: which shader, bound buffers (binding order), push consts, group count.
 * boff/brange (>0) override a binding's descriptor offset/range for per-token slice views
 * (rope binds Qin/Out at the token's float offset, like the PTX g_rope_seq launch). */
typedef struct {
    int shader;
    VkBuffer bufs[8];
    uint32_t pc[5];
    uint32_t groups;
    int      slice_binding0;  /* binding index to slice (rope: 0 and 1), or -1 */
    int      slice_binding1;
    VkDeviceSize slice_off;   /* byte offset for the sliced bindings */
    VkDeviceSize slice_range; /* byte range for the sliced bindings */
} Node;

static Node NODES[256];
static int  NNODE = 0;
static int  NBARRIER[256];

/* basic node: group = ceil(work / lsx); no slice. */
static void node(int shader, uint32_t work, const VkBuffer *bufs, const uint32_t *pc, int barrier_after) {
    Node *n = &NODES[NNODE];
    uint32_t lsx = SH_LSX[shader];
    n->shader = shader; n->groups = (work + lsx - 1) / lsx;
    for (int i=0;i<SH_BINDS[shader];++i) n->bufs[i]=bufs[i];
    int npc = (int)(SH_PCSZ[shader]/4);
    for (int i=0;i<npc;++i) n->pc[i]=pc[i];
    n->slice_binding0 = -1; n->slice_binding1 = -1; n->slice_off = 0; n->slice_range = 0;
    NBARRIER[NNODE] = barrier_after;
    NNODE++;
}

int main(int argc, char **argv) {
    SEQ = (argc>1)?atoi(argv[1]):4;
    D   = (argc>2)?atoi(argv[2]):16;
    HD  = (argc>3)?atoi(argv[3]):16;
    HID = (argc>4)?atoi(argv[4]):32;
    EPS = 1e-5f;
    if (D & 1) DIE("d must be even (RoPE rotates pairs)");
    /* scale = 1/sqrt(D) via the body's own Newton sqrt (60 iters), matching the PTX llama host. */
    { float g=(float)D; for(int i=0;i<60;i++)g=0.5f*(g+(float)D/g); SCALE=1.0f/g; }

    void *lib = DLOPEN(VKLIB); if (!lib) DIE("cannot dlopen " VKLIB);
    vkGetInstanceProcAddr = (PFN_vkGetInstanceProcAddr)DLSYM(lib, "vkGetInstanceProcAddr");
    if (!vkGetInstanceProcAddr) DIE("no vkGetInstanceProcAddr");
    vkCreateInstance = (PFN_vkCreateInstance)vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkCreateInstance");
    if (!vkCreateInstance) DIE("no vkCreateInstance");

    VkApplicationInfo app = {0};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO; app.pApplicationName = "form-kernel";
    app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo ici = {0};
    ici.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO; ici.pApplicationInfo = &app;
    VkInstance inst = VK_NULL_HANDLE; VKCHECK(vkCreateInstance(&ici, NULL, &inst));

    LOAD_I(inst, vkDestroyInstance); LOAD_I(inst, vkEnumeratePhysicalDevices);
    LOAD_I(inst, vkGetPhysicalDeviceProperties);
    LOAD_I(inst, vkGetPhysicalDeviceQueueFamilyProperties);
    LOAD_I(inst, vkGetPhysicalDeviceMemoryProperties);
    LOAD_I(inst, vkCreateDevice); LOAD_I(inst, vkDestroyDevice); LOAD_I(inst, vkGetDeviceQueue);
    LOAD_I(inst, vkCreateBuffer); LOAD_I(inst, vkDestroyBuffer); LOAD_I(inst, vkGetBufferMemoryRequirements);
    LOAD_I(inst, vkAllocateMemory); LOAD_I(inst, vkFreeMemory); LOAD_I(inst, vkBindBufferMemory);
    LOAD_I(inst, vkMapMemory); LOAD_I(inst, vkUnmapMemory);
    LOAD_I(inst, vkCreateDescriptorSetLayout); LOAD_I(inst, vkDestroyDescriptorSetLayout);
    LOAD_I(inst, vkCreateDescriptorPool); LOAD_I(inst, vkDestroyDescriptorPool);
    LOAD_I(inst, vkAllocateDescriptorSets); LOAD_I(inst, vkUpdateDescriptorSets);
    LOAD_I(inst, vkCreatePipelineLayout); LOAD_I(inst, vkDestroyPipelineLayout);
    LOAD_I(inst, vkCreateShaderModule); LOAD_I(inst, vkDestroyShaderModule);
    LOAD_I(inst, vkCreateComputePipelines); LOAD_I(inst, vkDestroyPipeline);
    LOAD_I(inst, vkCreateCommandPool); LOAD_I(inst, vkDestroyCommandPool);
    LOAD_I(inst, vkAllocateCommandBuffers); LOAD_I(inst, vkBeginCommandBuffer); LOAD_I(inst, vkEndCommandBuffer);
    LOAD_I(inst, vkCmdBindPipeline); LOAD_I(inst, vkCmdBindDescriptorSets);
    LOAD_I(inst, vkCmdPushConstants); LOAD_I(inst, vkCmdDispatch); LOAD_I(inst, vkCmdPipelineBarrier);
    LOAD_I(inst, vkQueueSubmit); LOAD_I(inst, vkQueueWaitIdle);

    uint32_t pdCount = 0; VKCHECK(vkEnumeratePhysicalDevices(inst, &pdCount, NULL));
    if (!pdCount) DIE("no Vulkan devices");
    VkPhysicalDevice *pds = malloc(pdCount * sizeof(*pds));
    VKCHECK(vkEnumeratePhysicalDevices(inst, &pdCount, pds));
    VkPhysicalDevice phys = VK_NULL_HANDLE; uint32_t qfam = UINT32_MAX;
    for (uint32_t dd = 0; dd < pdCount && phys == VK_NULL_HANDLE; ++dd) {
        uint32_t qfc = 0; vkGetPhysicalDeviceQueueFamilyProperties(pds[dd], &qfc, NULL);
        VkQueueFamilyProperties *qfp = malloc(qfc * sizeof(*qfp));
        vkGetPhysicalDeviceQueueFamilyProperties(pds[dd], &qfc, qfp);
        for (uint32_t q = 0; q < qfc; ++q)
            if (qfp[q].queueFlags & VK_QUEUE_COMPUTE_BIT) { phys = pds[dd]; qfam = q; break; }
        free(qfp);
    }
    free(pds); if (phys == VK_NULL_HANDLE) DIE("no compute queue family");
    VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(phys, &props);
    VkPhysicalDeviceMemoryProperties memProps; vkGetPhysicalDeviceMemoryProperties(phys, &memProps);

    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = {0};
    qci.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO; qci.queueFamilyIndex = qfam;
    qci.queueCount = 1; qci.pQueuePriorities = &prio;
    VkDeviceCreateInfo dci = {0};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO; dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &qci;
    VkDevice dev = VK_NULL_HANDLE; VKCHECK(vkCreateDevice(phys, &dci, NULL, &dev)); DEV = dev;
    VkQueue queue = VK_NULL_HANDLE; vkGetDeviceQueue(dev, qfam, 0, &queue);

    /* ---- build all six pipelines (one descriptor-set-layout per shader) ---- */
    for (int s=0;s<NSHADER;++s) {
        VkDescriptorSetLayoutBinding binds[8] = {0};
        for (int i=0;i<SH_BINDS[s];++i) {
            binds[i].binding=(uint32_t)i; binds[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
            binds[i].descriptorCount=1; binds[i].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
        }
        VkDescriptorSetLayoutCreateInfo dslci={0};
        dslci.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO; dslci.bindingCount=(uint32_t)SH_BINDS[s]; dslci.pBindings=binds;
        VKCHECK(vkCreateDescriptorSetLayout(dev,&dslci,NULL,&SH_DSL[s]));

        VkPushConstantRange pcr={0};
        pcr.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT; pcr.offset=0; pcr.size=SH_PCSZ[s];
        VkPipelineLayoutCreateInfo plci={0};
        plci.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO; plci.setLayoutCount=1; plci.pSetLayouts=&SH_DSL[s];
        plci.pushConstantRangeCount=1; plci.pPushConstantRanges=&pcr;
        VKCHECK(vkCreatePipelineLayout(dev,&plci,NULL,&SH_PL[s]));

        size_t sb=0; uint32_t *spv=read_spv(SH_SPV[s],&sb);
        VkShaderModuleCreateInfo smci={0};
        smci.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO; smci.codeSize=sb; smci.pCode=spv;
        VKCHECK(vkCreateShaderModule(dev,&smci,NULL,&SH_MOD[s])); free(spv);

        VkPipelineShaderStageCreateInfo stage={0};
        stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO; stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;
        stage.module=SH_MOD[s]; stage.pName="main";
        VkComputePipelineCreateInfo cpci={0};
        cpci.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO; cpci.stage=stage; cpci.layout=SH_PL[s]; cpci.basePipelineIndex=-1;
        VKCHECK(vkCreateComputePipelines(dev,VK_NULL_HANDLE,1,&cpci,NULL,&SH_PIPE[s]));
    }

    /* ---- host data + CPU oracle (same val(n) seeds as the PTX llama host) ---- */
    size_t sd=(size_t)SEQ*D, sh=(size_t)SEQ*HID;
    float *x=malloc(sd*4),*g1=malloc((size_t)D*4),*g2=malloc((size_t)D*4);
    float *Wq=malloc((size_t)D*D*4),*Wk=malloc((size_t)D*D*4),*Wv=malloc((size_t)D*D*4),*Wo=malloc((size_t)D*D*4);
    float *Wg=malloc((size_t)HID*D*4),*Wu=malloc((size_t)HID*D*4),*Wd=malloc((size_t)D*HID*4);
    float *ref=malloc(sd*4);
    /* gain buffers broadcast to SEQ*D for rmsnorm's g[row*cols+j] indexing. */
    float *G1=malloc(sd*4),*G2=malloc(sd*4);
    /* zero bias buffers so proj.comp (Y = W.X + b) computes bias-free matvec (b == 0). */
    float *ZD=malloc((size_t)D*4),*ZHID=malloc((size_t)HID*4);

    for(size_t i=0;i<sd;i++)x[i]=val(((int)(i*17+3))%256-128);
    for(int j=0;j<D;j++){ g1[j]=val((j*3+1)%256-128); g2[j]=val((j*7+1)%256-128); }
    for(int o=0;o<D;o++)for(int l=0;l<D;l++){Wq[(size_t)o*D+l]=val((o*7+l*3)%256-128);Wk[(size_t)o*D+l]=val((o*5+l*11)%256-128);Wv[(size_t)o*D+l]=val((o*13+l*2)%256-128);Wo[(size_t)o*D+l]=val((o*3+l*9)%256-128);}
    for(int k=0;k<HID;k++)for(int j=0;j<D;j++){Wg[(size_t)k*D+j]=val((k*5+j*3)%256-128);Wu[(size_t)k*D+j]=val((k*9+j*7)%256-128);}
    for(int o=0;o<D;o++)for(int k=0;k<HID;k++)Wd[(size_t)o*HID+k]=val((o*7+k*3)%256-128);
    for(int t=0;t<SEQ;t++)for(int j=0;j<D;j++){G1[(size_t)t*D+j]=g1[j];G2[(size_t)t*D+j]=g2[j];}
    for(int j=0;j<D;j++)ZD[j]=0.0f; for(int k=0;k<HID;k++)ZHID[k]=0.0f;

    /* ---- CPU oracle: lblk-block-causal, op-for-op ---- */
    {
        float*n1=malloc(sd*4),*Q=malloc(sd*4),*Kk=malloc(sd*4),*V=malloc(sd*4),*Qr=malloc(sd*4),*Kr=malloc(sd*4);
        float*att=malloc(sd*4),*ao=malloc(sd*4),*h=malloc(sd*4),*n2=malloc(sd*4);
        float*gg=malloc(sh*4),*uu=malloc(sh*4),*sg=malloc(sh*4),*ff=malloc(sd*4);
        c_rms(x,g1,n1);
        c_matvec_seq(Wq,n1,Q,D,D); c_matvec_seq(Wk,n1,Kk,D,D); c_matvec_seq(Wv,n1,V,D,D);
        c_rope_seq(Q,Qr); c_rope_seq(Kk,Kr);            /* q,k roped; v NOT */
        c_attn_causal(Qr,Kr,V,att);
        c_matvec_seq(Wo,att,ao,D,D);
        for(size_t i=0;i<sd;i++)h[i]=x[i]+ao[i];        /* residual */
        c_rms(h,g2,n2);
        c_matvec_seq(Wg,n2,gg,HID,D); c_matvec_seq(Wu,n2,uu,HID,D);
        for(size_t i=0;i<sh;i++)sg[i]=swiglu(gg[i],uu[i]);
        c_matvec_seq(Wd,sg,ff,D,HID);
        for(size_t i=0;i<sd;i++)ref[i]=h[i]+ff[i];      /* residual */
        free(n1);free(Q);free(Kk);free(V);free(Qr);free(Kr);free(att);free(ao);free(h);free(n2);free(gg);free(uu);free(sg);free(ff);
    }

    /* ---- resident device buffers (shared across the whole dispatch graph) ---- */
    VkBuffer dX,dN1,dQ,dK,dV,dQr,dKr,dAt,dSc,dAo,dH,dN2,dGg,dUu,dSg,dFf,dOut;
    VkDeviceMemory mX,mN1,mQ,mK,mV,mQr,mKr,mAt,mSc,mAo,mH,mN2,mGg,mUu,mSg,mFf,mOut;
    VkBuffer gG1,gG2,gWq,gWk,gWv,gWo,gWg,gWu,gWd,gZD,gZHID;
    VkDeviceMemory wG1,wG2,wWq,wWk,wWv,wWo,wWg,wWu,wWd,wZD,wZHID;
    #define MK(buf,mem,n) make_buffer(dev,&memProps,(VkDeviceSize)(n)*4,&buf,&mem)
    MK(dX,mX,sd);MK(dN1,mN1,sd);MK(dQ,mQ,sd);MK(dK,mK,sd);MK(dV,mV,sd);MK(dQr,mQr,sd);MK(dKr,mKr,sd);
    MK(dAt,mAt,sd);MK(dSc,mSc,(size_t)SEQ*SEQ);MK(dAo,mAo,sd);MK(dH,mH,sd);MK(dN2,mN2,sd);
    MK(dGg,mGg,sh);MK(dUu,mUu,sh);MK(dSg,mSg,sh);MK(dFf,mFf,sd);MK(dOut,mOut,sd);
    MK(gG1,wG1,sd);MK(gG2,wG2,sd);
    MK(gWq,wWq,(size_t)D*D);MK(gWk,wWk,(size_t)D*D);MK(gWv,wWv,(size_t)D*D);MK(gWo,wWo,(size_t)D*D);
    MK(gWg,wWg,(size_t)HID*D);MK(gWu,wWu,(size_t)HID*D);MK(gWd,wWd,(size_t)D*HID);
    MK(gZD,wZD,D);MK(gZHID,wZHID,HID);

    /* ---- upload inputs ---- */
    void *p;
    #define UP(mem,src,n) do{ VKCHECK(vkMapMemory(dev,mem,0,(VkDeviceSize)(n)*4,0,&p)); memcpy(p,src,(size_t)(n)*4); vkUnmapMemory(dev,mem);}while(0)
    UP(mX,x,sd);
    UP(wG1,G1,sd);UP(wG2,G2,sd);
    UP(wWq,Wq,(size_t)D*D);UP(wWk,Wk,(size_t)D*D);UP(wWv,Wv,(size_t)D*D);UP(wWo,Wo,(size_t)D*D);
    UP(wWg,Wg,(size_t)HID*D);UP(wWu,Wu,(size_t)HID*D);UP(wWd,Wd,(size_t)D*HID);
    UP(wZD,ZD,D);UP(wZHID,ZHID,HID);

    /* ---- assemble the dispatch graph (mirrors the PTX llama host launch order) ---- */
    uint32_t w_rows = (uint32_t)SEQ;       /* rmsnorm: one work item per row */
    uint32_t w_elemD = (uint32_t)sd;       /* proj(outd=D)/residual: one item per element (SEQ*D) */
    uint32_t w_elemH = (uint32_t)sh;       /* proj(outd=HID)/swiglu: one item per element (SEQ*HID) */
    uint32_t w_q     = (uint32_t)SEQ;      /* attention: one work item per query */
    uint32_t w_pair  = (uint32_t)(D/2);    /* rope: one work item per adjacent pair, per token */

    uint32_t pc_rms[3] = { (uint32_t)SEQ, (uint32_t)D, f2u(EPS) };          /* {rows,cols,eps_bits} */
    uint32_t pc_prD[3] = { (uint32_t)SEQ, (uint32_t)D, (uint32_t)D };       /* {ntok,outd=D,ind=D} */
    uint32_t pc_prG[3] = { (uint32_t)SEQ, (uint32_t)HID, (uint32_t)D };     /* {ntok,outd=HID,ind=D} (Wg/Wu) */
    uint32_t pc_prD2[3]= { (uint32_t)SEQ, (uint32_t)D, (uint32_t)HID };     /* {ntok,outd=D,ind=HID} (Wd) */
    uint32_t pc_at[5]  = { (uint32_t)SEQ, (uint32_t)SEQ, (uint32_t)D, 1u, f2u(SCALE) }; /* {nq,nk,d,nheads=1,scale_bits} */
    uint32_t pc_re[2]  = { (uint32_t)sd, 0u };                              /* {n,pad} */
    uint32_t pc_sg[1]  = { (uint32_t)sh };                                  /* {n} */

    /* per-token rope node: slices Qin(binding0)/Out(binding1) at the token's float offset, pos=t. */
    #define ROPE_NODE(srcbuf,dstbuf,tok) do { \
        Node *nd=&NODES[NNODE]; nd->shader=SH_ROPE; nd->groups=(w_pair+SH_LSX[SH_ROPE]-1)/SH_LSX[SH_ROPE]; \
        nd->bufs[0]=(srcbuf); nd->bufs[1]=(dstbuf); \
        nd->pc[0]=(uint32_t)(tok); nd->pc[1]=(uint32_t)HD; nd->pc[2]=(uint32_t)D; \
        nd->slice_binding0=0; nd->slice_binding1=1; \
        nd->slice_off=(VkDeviceSize)(tok)*(VkDeviceSize)D*4; nd->slice_range=(VkDeviceSize)D*4; \
        NBARRIER[NNODE]=1; NNODE++; \
    } while(0)

    /* 1: n1 = RMSNorm(x, g1) */
    node(SH_RMS, w_rows, (VkBuffer[]){dX,gG1,dN1}, pc_rms, 1);
    /* 2: q = Wq*n1, k = Wk*n1, v = Wv*n1  (bias-free: zero bias gZD). Independent reads of n1;
     *    barrier only after the last. */
    node(SH_PROJ, w_elemD, (VkBuffer[]){gWq,gZD,dN1,dQ}, pc_prD, 0);
    node(SH_PROJ, w_elemD, (VkBuffer[]){gWk,gZD,dN1,dK}, pc_prD, 0);
    node(SH_PROJ, w_elemD, (VkBuffer[]){gWv,gZD,dN1,dV}, pc_prD, 1);
    /* 3: RoPE(q)->Qr, RoPE(k)->Kr per token by position; v not roped. Each token's rope writes a
     *    distinct D-slice of Qr/Kr; barrier after each (mirrors the PTX one-launch-per-token + sync). */
    for (int t=0;t<SEQ;t++) ROPE_NODE(dQ,dQr,t);
    for (int t=0;t<SEQ;t++) ROPE_NODE(dK,dKr,t);
    /* 4: attn = causal_attention(Qr,Kr,v,scale)  (single head, scratch dSc) */
    node(SH_ATT, w_q, (VkBuffer[]){dQr,dKr,dV,dAt,dSc}, pc_at, 1);
    /* 5: ao = Wo*attn (bias-free);  h = x + ao */
    node(SH_PROJ, w_elemD, (VkBuffer[]){gWo,gZD,dAt,dAo}, pc_prD, 1);
    node(SH_RES,  w_elemD, (VkBuffer[]){dX,dAo,dH},       pc_re, 1);
    /* 6: n2 = RMSNorm(h, g2) */
    node(SH_RMS, w_rows, (VkBuffer[]){dH,gG2,dN2}, pc_rms, 1);
    /* 7: gate = Wg*n2, up = Wu*n2 (bias-free, outd=HID); sg = SwiGLU(gate,up); ff = Wd*sg (outd=D) */
    node(SH_PROJ, w_elemH, (VkBuffer[]){gWg,gZHID,dN2,dGg}, pc_prG, 0);
    node(SH_PROJ, w_elemH, (VkBuffer[]){gWu,gZHID,dN2,dUu}, pc_prG, 1);
    node(SH_SWIGLU, w_elemH, (VkBuffer[]){dGg,dUu,dSg}, pc_sg, 1);
    node(SH_PROJ, w_elemD, (VkBuffer[]){gWd,gZD,dSg,dFf}, pc_prD2, 1);
    /* 8: y = h + ff */
    node(SH_RES, w_elemD, (VkBuffer[]){dH,dFf,dOut}, pc_re, 0);

    /* ---- one descriptor pool sized for all nodes; one set per node ---- */
    uint32_t total_desc = 0;
    for (int i=0;i<NNODE;++i) total_desc += (uint32_t)SH_BINDS[NODES[i].shader];
    VkDescriptorPoolSize psize={0};
    psize.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; psize.descriptorCount=total_desc;
    VkDescriptorPoolCreateInfo dpci={0};
    dpci.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO; dpci.maxSets=(uint32_t)NNODE; dpci.poolSizeCount=1; dpci.pPoolSizes=&psize;
    VkDescriptorPool pool=VK_NULL_HANDLE; VKCHECK(vkCreateDescriptorPool(dev,&dpci,NULL,&pool));

    VkDescriptorSet *dset = malloc(sizeof(VkDescriptorSet) * NNODE);
    for (int i=0;i<NNODE;++i) {
        int s=NODES[i].shader;
        VkDescriptorSetAllocateInfo dsai={0};
        dsai.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO; dsai.descriptorPool=pool; dsai.descriptorSetCount=1; dsai.pSetLayouts=&SH_DSL[s];
        VKCHECK(vkAllocateDescriptorSets(dev,&dsai,&dset[i]));
        VkDescriptorBufferInfo dbi[8];
        VkWriteDescriptorSet wr[8]={0};
        for (int b=0;b<SH_BINDS[s];++b) {
            dbi[b].buffer=NODES[i].bufs[b]; dbi[b].offset=0; dbi[b].range=VK_WHOLE_SIZE;
            /* rope per-token slice: bind Qin/Out at the token's float offset (matches PTX g_rope_seq). */
            if (b==NODES[i].slice_binding0 || b==NODES[i].slice_binding1) {
                dbi[b].offset = NODES[i].slice_off;
                dbi[b].range  = NODES[i].slice_range;
            }
            wr[b].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; wr[b].dstSet=dset[i];
            wr[b].dstBinding=(uint32_t)b; wr[b].descriptorCount=1;
            wr[b].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; wr[b].pBufferInfo=&dbi[b];
        }
        vkUpdateDescriptorSets(dev,(uint32_t)SH_BINDS[s],wr,0,NULL);
    }

    /* ---- record ONE command buffer: all NNODE dispatches + barriers ---- */
    VkCommandPoolCreateInfo cpoolci={0};
    cpoolci.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO; cpoolci.queueFamilyIndex=qfam;
    VkCommandPool cpool=VK_NULL_HANDLE; VKCHECK(vkCreateCommandPool(dev,&cpoolci,NULL,&cpool));
    VkCommandBufferAllocateInfo cbai={0};
    cbai.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO; cbai.commandPool=cpool;
    cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount=1;
    VkCommandBuffer cmd=VK_NULL_HANDLE; VKCHECK(vkAllocateCommandBuffers(dev,&cbai,&cmd));

    VkCommandBufferBeginInfo cbbi={0};
    cbbi.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO; cbbi.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    VKCHECK(vkBeginCommandBuffer(cmd,&cbbi));

    VkMemoryBarrier mb={0};
    mb.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER;
    mb.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;
    mb.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;

    int nbar=0;
    for (int i=0;i<NNODE;++i) {
        int s=NODES[i].shader;
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, SH_PIPE[s]);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, SH_PL[s], 0, 1, &dset[i], 0, NULL);
        vkCmdPushConstants(cmd, SH_PL[s], VK_SHADER_STAGE_COMPUTE_BIT, 0, SH_PCSZ[s], NODES[i].pc);
        vkCmdDispatch(cmd, NODES[i].groups, 1, 1);
        if (NBARRIER[i]) {
            vkCmdPipelineBarrier(cmd,
                VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                0, 1, &mb, 0, NULL, 0, NULL);
            nbar++;
        }
    }
    VKCHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si={0};
    si.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO; si.commandBufferCount=1; si.pCommandBuffers=&cmd;
    VKCHECK(vkQueueSubmit(queue,1,&si,VK_NULL_HANDLE));
    VKCHECK(vkQueueWaitIdle(queue));

    /* ---- read back dOut, gate bit-exact (uint32) vs the oracle ---- */
    float *out=malloc(sd*4);
    VKCHECK(vkMapMemory(dev,mOut,0,sd*4,0,&p)); memcpy(out,p,sd*4); vkUnmapMemory(dev,mOut);

    int ex=0; float ma=0;
    for(size_t i=0;i<sd;i++){ uint32_t a,b; memcpy(&a,&out[i],4); memcpy(&b,&ref[i],4); if(a==b)ex++; float d=out[i]-ref[i]; if(d<0)d=-d; if(d>ma)ma=d; }

    printf("device=%s (Vulkan, MULTI-DISPATCH kernel-graph)\n", props.deviceName);
    printf("FULL llama decoder block (lblk-block-causal): RMSNorm -> QKV proj -> RoPE(q,k) -> causal attn -> Wo+res -> RMSNorm -> SwiGLU FFN(Wg,Wu,Wd)+res\n");
    printf("nodes=%d (dispatches) barriers=%d (COMPUTE->COMPUTE, shaderWrite->shaderRead), single submit\n", NNODE, nbar);
    printf("seq=%d d=%d HD=%d hid=%d scale=%g eps=%g  parity_bitexact=%d/%zu max_abs_diff=%g\n", SEQ,D,HD,HID,(double)SCALE,(double)EPS,ex,sd,(double)ma);
    printf("runtime_deps=%s only (six Form-minted .spv: rmsnorm/proj/rope/attention_mhc/residual/swiglu) -- same .spv run on Adreno/Mali\n", VKLIB);

    int fail = (ex != (int)sd);

    free(out); free(dset);
    vkDestroyCommandPool(dev,cpool,NULL);
    vkDestroyDescriptorPool(dev,pool,NULL);
    for (int s=0;s<NSHADER;++s) {
        vkDestroyPipeline(dev,SH_PIPE[s],NULL); vkDestroyShaderModule(dev,SH_MOD[s],NULL);
        vkDestroyPipelineLayout(dev,SH_PL[s],NULL); vkDestroyDescriptorSetLayout(dev,SH_DSL[s],NULL);
    }
    #define FB(buf,mem) do{ vkDestroyBuffer(dev,buf,NULL); vkFreeMemory(dev,mem,NULL);}while(0)
    FB(dX,mX);FB(dN1,mN1);FB(dQ,mQ);FB(dK,mK);FB(dV,mV);FB(dQr,mQr);FB(dKr,mKr);FB(dAt,mAt);FB(dSc,mSc);
    FB(dAo,mAo);FB(dH,mH);FB(dN2,mN2);FB(dGg,mGg);FB(dUu,mUu);FB(dSg,mSg);FB(dFf,mFf);FB(dOut,mOut);
    FB(gG1,wG1);FB(gG2,wG2);FB(gWq,wWq);FB(gWk,wWk);FB(gWv,wWv);FB(gWo,wWo);FB(gWg,wWg);FB(gWu,wWu);FB(gWd,wWd);FB(gZD,wZD);FB(gZHID,wZHID);
    vkDestroyDevice(dev,NULL); vkDestroyInstance(inst,NULL); DLCLOSE(lib);

    if (fail) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok -- the FULL llama decoder block ran as a MULTI-DISPATCH Vulkan kernel-graph, bit-exact to the lblk-block-causal recipe (Android-portable)\n");
    return 0;
}

/* block_vk.c — the EXACT tb-block (whisper-shaped) as a MULTI-DISPATCH Vulkan kernel-graph
 * (Android lane, prototyped on RTX). This is the first multi-dispatch Vulkan carrier here: prior
 * carriers (kernel_vk.c .. kernel_vk4.c) each record ONE compute dispatch; this records N dispatches
 * into ONE command buffer over a shared set of resident device buffers, with vkCmdPipelineBarrier
 * (COMPUTE_SHADER -> COMPUTE_SHADER, SHADER_WRITE -> SHADER_READ) between every dependent stage, then
 * a SINGLE submit. It mirrors form_cuda_ptx_exact_block_host.c op-for-op and gates BIT-EXACT (uint32)
 * vs the SAME CPU oracle and the SAME val(n) input seeds the PTX block passes.
 *
 * tb-block (each stage already four-way / PTX-proven):
 *   h1 = ln-seq(x)        = affine_gb(layernorm(x), g1, be1)
 *   Q  = proj(Wq,bq,h1)   K = proj(Wk,bk,h1)   V = proj(Wv,bv,h1)
 *   attn = attention(Q,K,V,scale)                 (single-head SDPA, full keys)
 *   r1 = x + proj(Wo,bo,attn)                      (residual)
 *   h2 = ln-seq(r1)       = affine_gb(layernorm(r1), g2, be2)
 *   ffn = tb-ffn(W1,c1,W2,c2,h2) per token         (gelu hidden)
 *   out = r1 + ffn                                 (residual)
 *
 * Six distinct Form-minted .spv pipelines, all proven single-dispatch already, composed here:
 *   layernorm.spv  affine_gb.spv  proj.spv  attention.spv  ffn.spv  residual.spv
 * Each shader keeps its own bindings/push-constant; one descriptor set is allocated PER dispatch node
 * (a node binds specific resident buffers), so the same proj pipeline serves Q/K/V/O on different
 * buffers. Dependent nodes are separated by a global SHADER_WRITE->SHADER_READ memory barrier so the
 * single compute queue's read-then-write is deterministic; independent nodes (the three QKV projs,
 * which all read h1 and write distinct buffers) share one barrier.
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no Vulkan.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include block_vk.c -o block_vk.exe
 * Build (Android, NDK arm64):
 *   aarch64-linux-android24-clang -O2 -I Vulkan-Headers/include block_vk.c -o block_vk -ldl
 * Run:
 *   block_vk.exe [seq d hid]      (defaults 8 16 32; also exercised at 16 32 64)
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

/* ---- CPU oracle (op-for-op with the PTX block host) ---- */
static float fexs(float x){ float n=1,t=1,a=1; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fex(float x){ int k=0; while((x<0?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexs(x); while(k>0){ v=v*v; k--; } return v; }
static float fge(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float e=fex(2.0f*z); float th=(e-1.0f)/(e+1.0f); return (0.5f*x)*(1.0f+th); }
static float fsq(float v){ if(v<=0)return 0; float g=v; for(int i=0;i<50;i++)g=0.5f*(g+v/g); return g; }

static int SEQ,D,HID; static float EPS,SCALE;
static void c_ln(const float*in,float*out){for(int t=0;t<SEQ;t++){float s=0;for(int j=0;j<D;j++)s=s+in[(size_t)t*D+j];float me=s/(float)D;float v=0;for(int j=0;j<D;j++){float dd=in[(size_t)t*D+j]-me;v=v+dd*dd;}float iv=1.0f/fsq(v/(float)D+EPS);for(int j=0;j<D;j++)out[(size_t)t*D+j]=(in[(size_t)t*D+j]-me)*iv;}}
static void c_gb(const float*in,const float*g,const float*be,float*out){for(int i=0;i<SEQ;i++)for(int j=0;j<D;j++)out[(size_t)i*D+j]=in[(size_t)i*D+j]*g[j]+be[j];}
static void c_proj(const float*W,const float*b,const float*X,float*Y){for(int t=0;t<SEQ;t++)for(int o=0;o<D;o++){float a=0;for(int l=D;l>0;){l--;float p=W[(size_t)o*D+l]*X[(size_t)t*D+l];a=p+a;}Y[(size_t)t*D+o]=a+b[o];}}

/* ---- pipeline + per-shader descriptor-set-layout ---- */
enum { SH_LN=0, SH_GB, SH_PROJ, SH_ATT, SH_FFN, SH_RES, NSHADER };
static const char *SH_SPV[NSHADER]  = {"layernorm.spv","affine_gb.spv","proj.spv","attention.spv","ffn.spv","residual.spv"};
static const int   SH_BINDS[NSHADER]= { 2,              4,             4,         5,              7,        3            };
static const uint32_t SH_PCSZ[NSHADER]={ 12u,           8u,            12u,       16u,            12u,      8u           }; /* push-const bytes */
/* local_size_x baked into each .comp -- MUST match the shader source so group-count = ceil(work/lsx)
 * is right. ln/att are 64 (per row/query); gb/proj are 256 (per element); res is 64 (per element);
 * ffn is 256 but dispatched as a single workgroup. Getting this wrong silently under-dispatches and
 * leaves the tail of element-parallel buffers unwritten (residual at 64 vs 256 was exactly that). */
static const uint32_t SH_LSX[NSHADER]= { 64u,           256u,          256u,      64u,            256u,     64u          };

static VkDevice           DEV;
static VkDescriptorSetLayout SH_DSL[NSHADER];
static VkPipelineLayout      SH_PL[NSHADER];
static VkPipeline            SH_PIPE[NSHADER];
static VkShaderModule        SH_MOD[NSHADER];

/* a dispatch node: which shader, its bound buffers (in binding order), push constants, group count */
typedef struct {
    int shader;
    VkBuffer bufs[8];
    uint32_t pc[4];
    uint32_t groups;
} Node;

static Node    NODES[64];
static int     NNODE = 0;
/* barrier after this node (1 = insert a global SHADER_WRITE->SHADER_READ barrier before the NEXT node) */
static int     NBARRIER[64];

/* `work` = number of work items (rows / queries / elements). groups = ceil(work / local_size_x),
 * using the shader's own baked local_size_x so the dispatch always covers every work item. */
static void node(int shader, uint32_t work, const VkBuffer *bufs, const uint32_t *pc, int barrier_after) {
    Node *n = &NODES[NNODE];
    uint32_t lsx = SH_LSX[shader];
    n->shader = shader; n->groups = (work + lsx - 1) / lsx;
    for (int i=0;i<SH_BINDS[shader];++i) n->bufs[i]=bufs[i];
    int npc = (int)(SH_PCSZ[shader]/4);
    for (int i=0;i<npc;++i) n->pc[i]=pc[i];
    NBARRIER[NNODE] = barrier_after;
    NNODE++;
}

int main(int argc, char **argv) {
    SEQ = (argc>1)?atoi(argv[1]):8;
    D   = (argc>2)?atoi(argv[2]):16;
    HID = (argc>3)?atoi(argv[3]):32;
    EPS = 1e-5f;
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

    /* ---- host data + CPU oracle (same seeds as the PTX block host) ---- */
    size_t sd=(size_t)SEQ*D;
    float *x=malloc(sd*4),*g1=malloc((size_t)D*4),*be1=malloc((size_t)D*4),*g2=malloc((size_t)D*4),*be2=malloc((size_t)D*4);
    float *Wq=malloc((size_t)D*D*4),*bq=malloc((size_t)D*4),*Wk=malloc((size_t)D*D*4),*bk=malloc((size_t)D*4),*Wv=malloc((size_t)D*D*4),*bv=malloc((size_t)D*4),*Wo=malloc((size_t)D*D*4),*bo=malloc((size_t)D*4);
    float *W1=malloc((size_t)HID*D*4),*c1=malloc((size_t)HID*4),*W2=malloc((size_t)D*HID*4),*c2=malloc((size_t)D*4),*ref=malloc(sd*4);
    for(size_t i=0;i<sd;i++)x[i]=val(((int)(i*17+3))%256-128);
    for(int j=0;j<D;j++){g1[j]=val((j*3+1)%256-128);be1[j]=val((j*5+2)%256-128);g2[j]=val((j*7+1)%256-128);be2[j]=val((j*9+2)%256-128);bq[j]=val((j*2)%256-128);bk[j]=val((j*4)%256-128);bv[j]=val((j*6)%256-128);bo[j]=val((j*8)%256-128);c2[j]=val((j*3)%256-128);}
    for(int o=0;o<D;o++)for(int l=0;l<D;l++){Wq[(size_t)o*D+l]=val((o*7+l*3)%256-128);Wk[(size_t)o*D+l]=val((o*5+l*11)%256-128);Wv[(size_t)o*D+l]=val((o*13+l*2)%256-128);Wo[(size_t)o*D+l]=val((o*3+l*9)%256-128);}
    for(int k=0;k<HID;k++){for(int j=0;j<D;j++)W1[(size_t)k*D+j]=val((k*5+j*3)%256-128);c1[k]=val((k*2)%256-128);}
    for(int o=0;o<D;o++)for(int k=0;k<HID;k++)W2[(size_t)o*HID+k]=val((o*7+k*3)%256-128);

    {float*ln=malloc(sd*4),*h1=malloc(sd*4),*Q=malloc(sd*4),*Kk=malloc(sd*4),*V=malloc(sd*4),*att=malloc(sd*4),*sc=malloc((size_t)SEQ*SEQ*4),*ao=malloc(sd*4),*r1=malloc(sd*4),*h2=malloc(sd*4),*ff=malloc(sd*4),*hh=malloc((size_t)HID*4);
     c_ln(x,ln); c_gb(ln,g1,be1,h1); c_proj(Wq,bq,h1,Q); c_proj(Wk,bk,h1,Kk); c_proj(Wv,bv,h1,V);
     for(int i=0;i<SEQ;i++){for(int j=0;j<SEQ;j++){float a=0;for(int l=D;l>0;){l--;float p=Q[(size_t)i*D+l]*Kk[(size_t)j*D+l];a=p+a;}sc[(size_t)i*SEQ+j]=a*SCALE;}
        float m=sc[(size_t)i*SEQ+0];for(int j=1;j<SEQ;j++){float vv=sc[(size_t)i*SEQ+j];if(vv>m)m=vv;}float ss=0;for(int j=0;j<SEQ;j++){float e=fex(sc[(size_t)i*SEQ+j]-m);sc[(size_t)i*SEQ+j]=e;ss=ss+e;}float r=1.0f/ss;for(int j=0;j<SEQ;j++)sc[(size_t)i*SEQ+j]=sc[(size_t)i*SEQ+j]*r;
        for(int mm=0;mm<D;mm++){float a=0;for(int j=0;j<SEQ;j++){float p=V[(size_t)j*D+mm]*sc[(size_t)i*SEQ+j];a=a+p;}att[(size_t)i*D+mm]=a;}}
     c_proj(Wo,bo,att,ao); for(int i=0;i<(int)sd;i++)r1[i]=x[i]+ao[i]; c_ln(r1,ln); c_gb(ln,g2,be2,h2);
     for(int t=0;t<SEQ;t++){for(int k=0;k<HID;k++){float a=0;for(int j=D;j>0;){j--;float p=W1[(size_t)k*D+j]*h2[(size_t)t*D+j];a=p+a;}hh[k]=fge(a+c1[k]);}for(int o=0;o<D;o++){float a=0;for(int k=HID;k>0;){k--;float p=W2[(size_t)o*HID+k]*hh[k];a=p+a;}ff[(size_t)t*D+o]=a+c2[o];}}
     for(int i=0;i<(int)sd;i++)ref[i]=r1[i]+ff[i];
     free(ln);free(h1);free(Q);free(Kk);free(V);free(att);free(sc);free(ao);free(r1);free(h2);free(ff);free(hh);}

    /* ---- resident device buffers (shared across the whole dispatch graph) ---- */
    /* data buffers */
    VkBuffer dX,dLn,dH1,dQ,dK,dV,dAt,dSc,dAo,dR1,dH2,dFf,dOut,dA;
    VkDeviceMemory mX,mLn,mH1,mQ,mK,mV,mAt,mSc,mAo,mR1,mH2,mFf,mOut,mA;
    /* weights/params */
    VkBuffer gWq,gbq,gWk,gbk,gWv,gbv,gWo,gbo,gg1,gbe1,gg2,gbe2,gW1,gc1,gW2,gc2;
    VkDeviceMemory wWq,wbq,wWk,wbk,wWv,wbv,wWo,wbo,wg1,wbe1,wg2,wbe2,wW1,wc1,wW2,wc2;
    #define MK(buf,mem,n) make_buffer(dev,&memProps,(VkDeviceSize)(n)*4,&buf,&mem)
    MK(dX,mX,sd);MK(dLn,mLn,sd);MK(dH1,mH1,sd);MK(dQ,mQ,sd);MK(dK,mK,sd);MK(dV,mV,sd);MK(dAt,mAt,sd);
    MK(dSc,mSc,(size_t)SEQ*SEQ);MK(dAo,mAo,sd);MK(dR1,mR1,sd);MK(dH2,mH2,sd);MK(dFf,mFf,sd);MK(dOut,mOut,sd);MK(dA,mA,HID);
    MK(gWq,wWq,(size_t)D*D);MK(gbq,wbq,D);MK(gWk,wWk,(size_t)D*D);MK(gbk,wbk,D);MK(gWv,wWv,(size_t)D*D);MK(gbv,wbv,D);
    MK(gWo,wWo,(size_t)D*D);MK(gbo,wbo,D);MK(gg1,wg1,D);MK(gbe1,wbe1,D);MK(gg2,wg2,D);MK(gbe2,wbe2,D);
    MK(gW1,wW1,(size_t)HID*D);MK(gc1,wc1,HID);MK(gW2,wW2,(size_t)D*HID);MK(gc2,wc2,D);

    /* upload inputs */
    void *p;
    #define UP(mem,src,n) do{ VKCHECK(vkMapMemory(dev,mem,0,(VkDeviceSize)(n)*4,0,&p)); memcpy(p,src,(size_t)(n)*4); vkUnmapMemory(dev,mem);}while(0)
    UP(mX,x,sd);
    UP(wWq,Wq,(size_t)D*D);UP(wbq,bq,D);UP(wWk,Wk,(size_t)D*D);UP(wbk,bk,D);UP(wWv,Wv,(size_t)D*D);UP(wbv,bv,D);
    UP(wWo,Wo,(size_t)D*D);UP(wbo,bo,D);UP(wg1,g1,D);UP(wbe1,be1,D);UP(wg2,g2,D);UP(wbe2,be2,D);
    UP(wW1,W1,(size_t)HID*D);UP(wc1,c1,HID);UP(wW2,W2,(size_t)D*HID);UP(wc2,c2,D);

    /* ---- assemble the dispatch graph (mirrors the PTX block host launch order) ---- */
    /* node() takes WORK-ITEM counts and derives group counts per-shader from SH_LSX, so the dispatch
     * always covers the tail (ln/att are 64-wide per row/query; gb/proj/res are element-parallel). */
    uint32_t w_rows = (uint32_t)SEQ;        /* one work item per row     (ln) */
    uint32_t w_elem = (uint32_t)sd;         /* one work item per element (gb, proj, res) */
    uint32_t w_q    = (uint32_t)SEQ;        /* one work item per query   (att) */
    /* push-constant payloads */
    uint32_t pc_ln[3]  = { (uint32_t)SEQ, (uint32_t)D, f2u(EPS) };   /* {rows,cols,eps} */
    uint32_t pc_gb[2]  = { (uint32_t)SEQ, (uint32_t)D };             /* {rows,cols} */
    uint32_t pc_pr[3]  = { (uint32_t)SEQ, (uint32_t)D, (uint32_t)D };/* {ntok,outd,ind} */
    uint32_t pc_at[4]  = { (uint32_t)SEQ, (uint32_t)SEQ, (uint32_t)D, f2u(SCALE) }; /* {nq,nk,d,scale_bits} */
    uint32_t pc_re[2]  = { (uint32_t)sd, 0u };                       /* {n,pad} */
    uint32_t pc_ff[3]  = { (uint32_t)D, (uint32_t)HID, (uint32_t)D };/* {indim,hid,outd} */

    /* 1: ln(dX)->dLn   2: gb(dLn,g1,be1)->dH1 */
    node(SH_LN, w_rows, (VkBuffer[]){dX,dLn},               pc_ln, 1);
    node(SH_GB, w_elem, (VkBuffer[]){dLn,gg1,gbe1,dH1},     pc_gb, 1);
    /* 3: Q=proj K=proj V=proj  (all read dH1, write distinct -> independent; barrier only after V) */
    node(SH_PROJ, w_elem, (VkBuffer[]){gWq,gbq,dH1,dQ},     pc_pr, 0);
    node(SH_PROJ, w_elem, (VkBuffer[]){gWk,gbk,dH1,dK},     pc_pr, 0);
    node(SH_PROJ, w_elem, (VkBuffer[]){gWv,gbv,dH1,dV},     pc_pr, 1);
    /* 4: attn(Q,K,V)->dAt (scratch dSc) */
    node(SH_ATT, w_q,    (VkBuffer[]){dQ,dK,dV,dAt,dSc},    pc_at, 1);
    /* 5: ao=proj(Wo,bo,att)->dAo   6: r1 = x + ao -> dR1 */
    node(SH_PROJ, w_elem, (VkBuffer[]){gWo,gbo,dAt,dAo},    pc_pr, 1);
    node(SH_RES,  w_elem, (VkBuffer[]){dX,dAo,dR1},         pc_re, 1);
    /* 7: ln(r1)->dLn   8: gb(dLn,g2,be2)->dH2 */
    node(SH_LN, w_rows, (VkBuffer[]){dR1,dLn},              pc_ln, 1);
    node(SH_GB, w_elem, (VkBuffer[]){dLn,gg2,gbe2,dH2},     pc_gb, 1);
    /* 9: ffn per token: K_ff on dH2 slice -> dFf slice, ONE workgroup each (shared scratch dA -> barrier between) */
    for (int t=0;t<SEQ;t++) {
        /* per-token sub-buffer views are not used; instead the shader reads the whole H2/Ff and we
         * encode the token offset by binding distinct ranges is overkill -- the PTX host instead
         * launches with X=dH2+t*D, Y=dFf+t*D. We mirror that with VkDescriptorBufferInfo offsets via
         * a per-token descriptor set built at record time (see record loop below). The node carries the
         * token index in pc[3] (unused by the shader) so the record loop can compute the offset. */
        Node *nd=&NODES[NNODE];
        nd->shader=SH_FFN; nd->groups=1;
        nd->bufs[0]=gW1; nd->bufs[1]=gc1; nd->bufs[2]=gW2; nd->bufs[3]=gc2; nd->bufs[4]=dH2; nd->bufs[5]=dFf; nd->bufs[6]=dA;
        nd->pc[0]=pc_ff[0]; nd->pc[1]=pc_ff[1]; nd->pc[2]=pc_ff[2]; nd->pc[3]=(uint32_t)t;
        NBARRIER[NNODE]=1;   /* shared scratch dA + serial Ff writes -> barrier between every token */
        NNODE++;
    }
    /* 10: out = r1 + ff -> dOut  (no barrier after the last node) */
    node(SH_RES, w_elem, (VkBuffer[]){dR1,dFf,dOut},        pc_re, 0);

    /* ---- one descriptor pool sized for all nodes; one set per node ---- */
    uint32_t total_desc = 0;
    for (int i=0;i<NNODE;++i) total_desc += (uint32_t)SH_BINDS[NODES[i].shader];
    VkDescriptorPoolSize psize={0};
    psize.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; psize.descriptorCount=total_desc;
    VkDescriptorPoolCreateInfo dpci={0};
    dpci.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO; dpci.maxSets=(uint32_t)NNODE; dpci.poolSizeCount=1; dpci.pPoolSizes=&psize;
    VkDescriptorPool pool=VK_NULL_HANDLE; VKCHECK(vkCreateDescriptorPool(dev,&dpci,NULL,&pool));

    VkDescriptorSet dset[64];
    for (int i=0;i<NNODE;++i) {
        int s=NODES[i].shader;
        VkDescriptorSetAllocateInfo dsai={0};
        dsai.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO; dsai.descriptorPool=pool; dsai.descriptorSetCount=1; dsai.pSetLayouts=&SH_DSL[s];
        VKCHECK(vkAllocateDescriptorSets(dev,&dsai,&dset[i]));
        VkDescriptorBufferInfo dbi[8];
        VkWriteDescriptorSet wr[8]={0};
        for (int b=0;b<SH_BINDS[s];++b) {
            dbi[b].buffer=NODES[i].bufs[b]; dbi[b].offset=0; dbi[b].range=VK_WHOLE_SIZE;
            /* FFN token offset: bind H2 (binding 4) and Ff (binding 5) at the token's float offset.
             * Per-token slice has D elements; matches the PTX host's dH2+t*D / dFf+t*D launch. */
            if (s==SH_FFN && (b==4 || b==5)) {
                uint32_t t = NODES[i].pc[3];
                dbi[b].offset = (VkDeviceSize)t * (VkDeviceSize)D * 4;
                dbi[b].range  = (VkDeviceSize)D * 4;
            }
            wr[b].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; wr[b].dstSet=dset[i];
            wr[b].dstBinding=(uint32_t)b; wr[b].descriptorCount=1;
            wr[b].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; wr[b].pBufferInfo=&dbi[b];
        }
        vkUpdateDescriptorSets(dev,(uint32_t)SH_BINDS[s],wr,0,NULL);
    }

    /* ---- record ONE command buffer: all NNODE dispatches + barriers between dependent stages ---- */
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

    /* global SHADER_WRITE -> SHADER_READ barrier, COMPUTE_SHADER -> COMPUTE_SHADER */
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
    printf("EXACT tb-block (ln-seq[g/be] -> QKVO proj -> attn -> +res -> ln-seq -> ffn -> +res)\n");
    printf("nodes=%d (dispatches) barriers=%d (COMPUTE->COMPUTE, shaderWrite->shaderRead), single submit\n", NNODE, nbar);
    printf("seq=%d d=%d hid=%d  parity_bitexact=%d/%zu max_abs_diff=%g\n", SEQ,D,HID,ex,sd,(double)ma);
    printf("runtime_deps=%s only (six Form-minted .spv: layernorm/affine_gb/proj/attention/ffn/residual) -- same .spv run on Adreno/Mali\n", VKLIB);

    int fail = (ex != (int)sd);

    free(out);
    vkDestroyCommandPool(dev,cpool,NULL);
    vkDestroyDescriptorPool(dev,pool,NULL);
    for (int s=0;s<NSHADER;++s) {
        vkDestroyPipeline(dev,SH_PIPE[s],NULL); vkDestroyShaderModule(dev,SH_MOD[s],NULL);
        vkDestroyPipelineLayout(dev,SH_PL[s],NULL); vkDestroyDescriptorSetLayout(dev,SH_DSL[s],NULL);
    }
    #define FB(buf,mem) do{ vkDestroyBuffer(dev,buf,NULL); vkFreeMemory(dev,mem,NULL);}while(0)
    FB(dX,mX);FB(dLn,mLn);FB(dH1,mH1);FB(dQ,mQ);FB(dK,mK);FB(dV,mV);FB(dAt,mAt);FB(dSc,mSc);FB(dAo,mAo);FB(dR1,mR1);FB(dH2,mH2);FB(dFf,mFf);FB(dOut,mOut);FB(dA,mA);
    FB(gWq,wWq);FB(gbq,wbq);FB(gWk,wWk);FB(gbk,wbk);FB(gWv,wWv);FB(gbv,wbv);FB(gWo,wWo);FB(gbo,wbo);FB(gg1,wg1);FB(gbe1,wbe1);FB(gg2,wg2);FB(gbe2,wbe2);FB(gW1,wW1);FB(gc1,wc1);FB(gW2,wW2);FB(gc2,wc2);
    vkDestroyDevice(dev,NULL); vkDestroyInstance(inst,NULL); DLCLOSE(lib);

    if (fail) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok -- the EXACT tb-block ran as a MULTI-DISPATCH Vulkan kernel-graph, bit-exact to the recipe (Android-portable)\n");
    return 0;
}

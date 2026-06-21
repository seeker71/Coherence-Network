/* kernel_vk2.c — headless Vulkan compute carrier (Android lane, prototyped on RTX), parameterized
 * for two more Form-minted kernels: softmax (one row per invocation) and ffn (ONE workgroup per
 * token, two phases with a barrier()). Companion to kernel_vk.c (residual/layernorm/gelu); same
 * driver-only bootstrap, same precise/RoundingModeRTE bit-exactness, generalized to N storage
 * buffers and a 12-byte push constant block.
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no
 * Vulkan. Runs a Form-minted .spv bit-exact vs a CPU oracle that mirrors the proven PTX op-for-op
 * (same val(n) inputs as form_cuda_ptx_softmax_host.c / form_cuda_ptx_ffn_host.c). The same .spv +
 * call sequence is the Android compute path.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include kernel_vk2.c -o kernel_vk2.exe
 * Build (Android, NDK arm64):
 *   aarch64-linux-android24-clang -O2 -I Vulkan-Headers/include kernel_vk2.c -o kernel_vk2 -ldl
 * Run:
 *   kernel_vk2.exe softmax softmax.spv [rows cols]        (defaults 256 256)
 *   kernel_vk2.exe ffn     ffn.spv     [indim hid outd]   (defaults 16 64 8)
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

#define MAX_BUFS 7

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
static PFN_vkQueueSubmit vkQueueSubmit;
static PFN_vkQueueWaitIdle vkQueueWaitIdle;

#define LOAD_I(inst,name) do { name=(PFN_##name)vkGetInstanceProcAddr((inst),#name); \
  if(!name) DIE("missing entry point: " #name); } while(0)

/* Push constant block: softmax uses {rows,cols}; ffn uses {indim,hid,outd}. 12 bytes covers both. */
typedef struct { uint32_t a; uint32_t b; uint32_t c; } PushC;

static uint32_t find_mem_type(const VkPhysicalDeviceMemoryProperties *mp, uint32_t typeBits, VkMemoryPropertyFlags flags) {
    for (uint32_t i = 0; i < mp->memoryTypeCount; ++i)
        if ((typeBits & (1u << i)) && (mp->memoryTypes[i].propertyFlags & flags) == flags) return i;
    DIE("no HOST_VISIBLE|HOST_COHERENT memory type"); return 0;
}
static void make_buffer(VkDevice dev, const VkPhysicalDeviceMemoryProperties *mp, VkDeviceSize size, VkBuffer *buf, VkDeviceMemory *mem) {
    VkBufferCreateInfo bci = {0};
    bci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO; bci.size = size;
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
    FILE *f = fopen(path, "rb"); if (!f) DIE("cannot open .spv");
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    if (n <= 0 || (n & 3)) DIE(".spv size invalid");
    uint32_t *code = malloc((size_t)n);
    if (fread(code, 1, (size_t)n, f) != (size_t)n) DIE(".spv read short");
    fclose(f);
    if (code[0] != 0x07230203u) DIE(".spv bad magic");
    *out_bytes = (size_t)n; return code;
}
static float val(int n) { return (float)n / 256.0f; }

/* ---- CPU oracles (op-for-op with the PTX, same as the cuda hosts) ---- */
static float fexp_small(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float ftanh(float x){ float e=fexpf_(2.0f*x); return (e-1.0f)/(e+1.0f); }
static float fgelu(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); return (0.5f*x)*(1.0f+ftanh(z)); }

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s <softmax|ffn> <spv> [dims...]\n", argv[0]); return 2; }
    const char *mode = argv[1];
    const char *spv_path = argv[2];
    int is_sm  = !strcmp(mode, "softmax");
    int is_ffn = !strcmp(mode, "ffn");
    if (!is_sm && !is_ffn) { fprintf(stderr, "bad mode %s\n", mode); return 2; }

    /* dims */
    uint32_t rows=0, cols=0, indim=0, hid=0, outd=0;
    if (is_sm) {
        rows = (argc > 3) ? (uint32_t)atoi(argv[3]) : 256;
        cols = (argc > 4) ? (uint32_t)atoi(argv[4]) : 256;
        if (!rows || !cols) DIE("bad dims");
    } else {
        indim = (argc > 3) ? (uint32_t)atoi(argv[3]) : 16;
        hid   = (argc > 4) ? (uint32_t)atoi(argv[4]) : 64;
        outd  = (argc > 5) ? (uint32_t)atoi(argv[5]) : 8;
        if (!indim || !hid || !outd) DIE("bad dims");
    }

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
    LOAD_I(inst, vkCmdPushConstants); LOAD_I(inst, vkCmdDispatch);
    LOAD_I(inst, vkQueueSubmit); LOAD_I(inst, vkQueueWaitIdle);

    uint32_t pdCount = 0; VKCHECK(vkEnumeratePhysicalDevices(inst, &pdCount, NULL));
    if (!pdCount) DIE("no Vulkan devices");
    VkPhysicalDevice *pds = malloc(pdCount * sizeof(*pds));
    VKCHECK(vkEnumeratePhysicalDevices(inst, &pdCount, pds));
    VkPhysicalDevice phys = VK_NULL_HANDLE; uint32_t qfam = UINT32_MAX;
    for (uint32_t d = 0; d < pdCount && phys == VK_NULL_HANDLE; ++d) {
        uint32_t qfc = 0; vkGetPhysicalDeviceQueueFamilyProperties(pds[d], &qfc, NULL);
        VkQueueFamilyProperties *qfp = malloc(qfc * sizeof(*qfp));
        vkGetPhysicalDeviceQueueFamilyProperties(pds[d], &qfc, qfp);
        for (uint32_t q = 0; q < qfc; ++q)
            if (qfp[q].queueFlags & VK_QUEUE_COMPUTE_BIT) { phys = pds[d]; qfam = q; break; }
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
    VkDevice dev = VK_NULL_HANDLE; VKCHECK(vkCreateDevice(phys, &dci, NULL, &dev));
    VkQueue queue = VK_NULL_HANDLE; vkGetDeviceQueue(dev, qfam, 0, &queue);

    /* ---- host data + oracle ----
     * Per-buffer host pointers + element counts; bound 0..nbufs-1 in descriptor order.
     * The output buffer index is tracked so we can read it back at the end. */
    int nbufs;
    size_t elems[MAX_BUFS] = {0};     /* element count per binding */
    float *host[MAX_BUFS] = {0};      /* upload source per binding (NULL => zero-init) */
    int out_idx;                      /* which binding holds the result we compare */
    size_t out_elems;                 /* element count of the result */
    float *ref = NULL;                /* CPU oracle result */
    uint32_t work;                    /* invocations needed (softmax: rows; ffn: 1 token) */
    uint32_t local_x;                 /* local_size_x baked into the shader */

    if (is_sm) {
        /* bindings: 0=x (rows*cols), 1=y (rows*cols, written then re-read) */
        nbufs = 2; out_idx = 1; local_x = 64;
        size_t n = (size_t)rows * cols;
        elems[0] = n; elems[1] = n; out_elems = n;
        float *x = malloc(n*4); ref = malloc(n*4);
        for (uint32_t i=0;i<rows;i++) for (uint32_t j=0;j<cols;j++)
            x[(size_t)i*cols+j] = val(((int)(i*31+j*17))%1000-500);
        /* oracle per row: forward max, Taylor fexp, forward sum, r=1/s, y=e*r */
        for (uint32_t i=0;i<rows;i++){
            float m = x[(size_t)i*cols+0];
            for (uint32_t j=1;j<cols;j++){ float v=x[(size_t)i*cols+j]; if (v>m) m=v; }
            float s=0.0f;
            for (uint32_t j=0;j<cols;j++){ float e=fexpf_(x[(size_t)i*cols+j]-m); ref[(size_t)i*cols+j]=e; s=s+e; }
            float r=1.0f/s;
            for (uint32_t j=0;j<cols;j++) ref[(size_t)i*cols+j]=ref[(size_t)i*cols+j]*r;
        }
        host[0] = x; host[1] = NULL;   /* y zero-init */
        work = rows;
    } else {
        /* bindings: 0=w1, 1=b1, 2=w2, 3=b2, 4=x, 5=y, 6=a(scratch) */
        nbufs = 7; out_idx = 5; local_x = 256;
        size_t nW1=(size_t)hid*indim, nW2=(size_t)outd*hid;
        elems[0]=nW1; elems[1]=hid; elems[2]=nW2; elems[3]=outd; elems[4]=indim; elems[5]=outd; elems[6]=hid;
        out_elems = outd;
        float *w1=malloc(nW1*4), *b1=malloc((size_t)hid*4), *w2=malloc(nW2*4), *b2=malloc((size_t)outd*4);
        float *x=malloc((size_t)indim*4); ref=malloc((size_t)outd*4);
        float *a=malloc((size_t)hid*4);
        /* inputs in [-0.5,0.5) so the gelu argument stays in fp32 exp range (same seeds as the cuda host) */
        for (uint32_t k=0;k<hid;k++){ for(uint32_t j=0;j<indim;j++) w1[(size_t)k*indim+j]=val(((int)(k*31+j*17))%256-128); b1[k]=val(((int)(k*7))%256-128); }
        for (uint32_t j=0;j<indim;j++) x[j]=val(((int)(j*13))%256-128);
        for (uint32_t i=0;i<outd;i++){ for(uint32_t k=0;k<hid;k++) w2[(size_t)i*hid+k]=val(((int)(i*23+k*11))%256-128); b2[i]=val(((int)(i*5))%256-128); }
        /* CPU reference (two phases, serial right-folds) */
        for (uint32_t k=0;k<hid;k++){
            float acc=0.0f; for(int j=(int)indim;j>0;){ j--; float p=w1[(size_t)k*indim+j]*x[j]; acc=p+acc; }
            float hk=acc+b1[k]; a[k]=fgelu(hk);
        }
        for (uint32_t i=0;i<outd;i++){
            float acc=0.0f; for(int k=(int)hid;k>0;){ k--; float p=w2[(size_t)i*hid+k]*a[k]; acc=p+acc; }
            ref[i]=acc+b2[i];
        }
        free(a);
        host[0]=w1; host[1]=b1; host[2]=w2; host[3]=b2; host[4]=x; host[5]=NULL; host[6]=NULL;
        work = 1;   /* one workgroup, one token */
    }

    /* ---- GPU buffers ---- */
    VkBuffer buf[MAX_BUFS] = {0}; VkDeviceMemory mem[MAX_BUFS] = {0};
    void *p;
    for (int i = 0; i < nbufs; ++i) {
        size_t bytes = elems[i] * 4;
        make_buffer(dev, &memProps, bytes, &buf[i], &mem[i]);
        VKCHECK(vkMapMemory(dev, mem[i], 0, bytes, 0, &p));
        if (host[i]) memcpy(p, host[i], bytes); else memset(p, 0, bytes);
        vkUnmapMemory(dev, mem[i]);
    }

    /* ---- descriptor set layout ---- */
    VkDescriptorSetLayoutBinding binds[MAX_BUFS] = {0};
    for (int i = 0; i < nbufs; ++i) {
        binds[i].binding = (uint32_t)i; binds[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        binds[i].descriptorCount = 1; binds[i].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    }
    VkDescriptorSetLayoutCreateInfo dslci = {0};
    dslci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO; dslci.bindingCount = (uint32_t)nbufs; dslci.pBindings = binds;
    VkDescriptorSetLayout dsl = VK_NULL_HANDLE; VKCHECK(vkCreateDescriptorSetLayout(dev, &dslci, NULL, &dsl));

    VkDescriptorPoolSize psize = {0};
    psize.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; psize.descriptorCount = (uint32_t)nbufs;
    VkDescriptorPoolCreateInfo dpci = {0};
    dpci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO; dpci.maxSets = 1; dpci.poolSizeCount = 1; dpci.pPoolSizes = &psize;
    VkDescriptorPool pool = VK_NULL_HANDLE; VKCHECK(vkCreateDescriptorPool(dev, &dpci, NULL, &pool));
    VkDescriptorSetAllocateInfo dsai = {0};
    dsai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO; dsai.descriptorPool = pool; dsai.descriptorSetCount = 1; dsai.pSetLayouts = &dsl;
    VkDescriptorSet dset = VK_NULL_HANDLE; VKCHECK(vkAllocateDescriptorSets(dev, &dsai, &dset));

    VkDescriptorBufferInfo dbi[MAX_BUFS];
    for (int i = 0; i < nbufs; ++i) { dbi[i].buffer = buf[i]; dbi[i].offset = 0; dbi[i].range = VK_WHOLE_SIZE; }
    VkWriteDescriptorSet writes[MAX_BUFS] = {0};
    for (int i = 0; i < nbufs; ++i) {
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; writes[i].dstSet = dset;
        writes[i].dstBinding = (uint32_t)i; writes[i].descriptorCount = 1;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; writes[i].pBufferInfo = &dbi[i];
    }
    vkUpdateDescriptorSets(dev, (uint32_t)nbufs, writes, 0, NULL);

    /* push constant range: 8 bytes (softmax {rows,cols}) or 12 bytes (ffn {indim,hid,outd}) */
    uint32_t pcsize = is_ffn ? (uint32_t)sizeof(PushC) : 8u;
    VkPushConstantRange pcr = {0};
    pcr.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT; pcr.offset = 0; pcr.size = pcsize;
    VkPipelineLayoutCreateInfo plci = {0};
    plci.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO; plci.setLayoutCount = 1; plci.pSetLayouts = &dsl;
    plci.pushConstantRangeCount = 1; plci.pPushConstantRanges = &pcr;
    VkPipelineLayout playout = VK_NULL_HANDLE; VKCHECK(vkCreatePipelineLayout(dev, &plci, NULL, &playout));

    size_t spvBytes = 0; uint32_t *spv = read_spv(spv_path, &spvBytes);
    VkShaderModuleCreateInfo smci = {0};
    smci.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO; smci.codeSize = spvBytes; smci.pCode = spv;
    VkShaderModule shader = VK_NULL_HANDLE; VKCHECK(vkCreateShaderModule(dev, &smci, NULL, &shader));

    VkPipelineShaderStageCreateInfo stage = {0};
    stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO; stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    stage.module = shader; stage.pName = "main";
    VkComputePipelineCreateInfo cpci = {0};
    cpci.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO; cpci.stage = stage; cpci.layout = playout;
    cpci.basePipelineIndex = -1;
    VkPipeline pipe = VK_NULL_HANDLE; VKCHECK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpci, NULL, &pipe));

    VkCommandPoolCreateInfo cpoolci = {0};
    cpoolci.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO; cpoolci.queueFamilyIndex = qfam;
    VkCommandPool cpool = VK_NULL_HANDLE; VKCHECK(vkCreateCommandPool(dev, &cpoolci, NULL, &cpool));
    VkCommandBufferAllocateInfo cbai = {0};
    cbai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO; cbai.commandPool = cpool;
    cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE; VKCHECK(vkAllocateCommandBuffers(dev, &cbai, &cmd));

    VkCommandBufferBeginInfo cbbi = {0};
    cbbi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO; cbbi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    VKCHECK(vkBeginCommandBuffer(cmd, &cbbi));
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, playout, 0, 1, &dset, 0, NULL);

    /* push constants + dispatch:
     *   softmax = 1 thread per row, local_size_x=64 -> ceil(rows/64) groups
     *   ffn     = ONE workgroup per token, local_size_x=256 -> exactly 1 group (work==1) */
    PushC pcv = {0};
    if (is_sm) { pcv.a = rows;  pcv.b = cols; pcv.c = 0; }
    else       { pcv.a = indim; pcv.b = hid;  pcv.c = outd; }
    vkCmdPushConstants(cmd, playout, VK_SHADER_STAGE_COMPUTE_BIT, 0, pcsize, &pcv);
    uint32_t groups = (work + local_x - 1) / local_x;
    vkCmdDispatch(cmd, groups, 1, 1);
    VKCHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si = {0};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO; si.commandBufferCount = 1; si.pCommandBuffers = &cmd;
    VKCHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VKCHECK(vkQueueWaitIdle(queue));

    float *yg = malloc(out_elems * 4);
    VKCHECK(vkMapMemory(dev, mem[out_idx], 0, out_elems * 4, 0, &p)); memcpy(yg, p, out_elems * 4); vkUnmapMemory(dev, mem[out_idx]);

    int exact = 0; float max_abs = 0.0f;
    for (size_t i = 0; i < out_elems; i++) {
        uint32_t a, b; memcpy(&a, &yg[i], 4); memcpy(&b, &ref[i], 4);
        if (a == b) exact++;
        float d = yg[i] - ref[i]; if (d < 0) d = -d; if (d > max_abs) max_abs = d;
    }
    printf("device=%s (Vulkan)\n", props.deviceName);
    printf("kernel=form_%s module=%s (%zu bytes SPIR-V)", mode, spv_path, spvBytes);
    if (is_sm) printf("  rows=%u cols=%u\n", rows, cols);
    else       printf("  indim=%u hid=%u outd=%u\n", indim, hid, outd);
    printf("parity_bitexact=%d/%zu max_abs_diff=%g\n", exact, out_elems, (double)max_abs);
    printf("runtime_deps=%s only (Form-minted SPIR-V; no nvcc/nvrtc/go/python/rust/shell/clang) -- same .spv runs on Adreno/Mali\n", VKLIB);

    free(spv); free(yg);
    vkDestroyCommandPool(dev, cpool, NULL); vkDestroyPipeline(dev, pipe, NULL);
    vkDestroyShaderModule(dev, shader, NULL); vkDestroyPipelineLayout(dev, playout, NULL);
    vkDestroyDescriptorPool(dev, pool, NULL); vkDestroyDescriptorSetLayout(dev, dsl, NULL);
    for (int i = 0; i < nbufs; ++i) { vkDestroyBuffer(dev, buf[i], NULL); vkFreeMemory(dev, mem[i], NULL); }
    vkDestroyDevice(dev, NULL); vkDestroyInstance(inst, NULL); DLCLOSE(lib);
    if (exact != (int)out_elems) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-minted SPIR-V %s ran on the Vulkan driver alone, bit-exact to the recipe (Android-portable)\n", mode);
    return 0;
}

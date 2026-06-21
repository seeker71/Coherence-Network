/* kernel_vk.c — headless Vulkan compute carrier (Android lane, prototyped on RTX), parameterized
 * for three Form-minted kernels: residual (y=a+b), layernorm (Newton-50), gelu (14-term Taylor).
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no
 * Vulkan. Runs a Form-minted .spv bit-exact vs a CPU oracle that mirrors the proven PTX op-for-op
 * (same val(n) inputs as the cuda hosts). The same .spv + call sequence is the Android compute path.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include kernel_vk.c -o kernel_vk.exe
 * Build (Android, NDK arm64):
 *   aarch64-linux-android24-clang -O2 -I Vulkan-Headers/include kernel_vk.c -o kernel_vk -ldl
 * Run:
 *   kernel_vk.exe residual  residual.spv  [rows cols]   (defaults 256 256)
 *   kernel_vk.exe layernorm layernorm.spv [rows cols]   (defaults 256 256)
 *   kernel_vk.exe gelu      gelu.spv      [n]           (default 1024)
 *
 * Carrier design (struct-by-struct init, two-wave proc-addr bootstrap, precise/NoContraction
 * bit-exactness) carried over from matvec_vk.c.
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
static PFN_vkQueueSubmit vkQueueSubmit;
static PFN_vkQueueWaitIdle vkQueueWaitIdle;

#define LOAD_I(inst,name) do { name=(PFN_##name)vkGetInstanceProcAddr((inst),#name); \
  if(!name) DIE("missing entry point: " #name); } while(0)

/* Push constant layouts. residual/gelu use {n,pad}; layernorm uses {rows,cols,eps}. */
typedef struct { uint32_t a; uint32_t b; float eps; } PushC; /* 12 bytes, covers all three */

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

/* ---- CPU oracles (op-for-op with the PTX) ---- */
static float fsqrt_newton(float v) {
    if (v <= 0.0f) return 0.0f;
    float g = v;
    for (int i = 0; i < 50; i++) g = 0.5f * (g + v / g);
    return g;
}
static float fexp_small(float x) {
    float n = 1.0f, term = 1.0f, acc = 1.0f;
    while (n <= 14.0f) { term = term * (x / n); acc = acc + term; n = n + 1.0f; }
    return acc;
}
static float fexp_(float x) {
    int k = 0;
    while ((x < 0.0f ? -x : x) > 0.5f) { x = x / 2.0f; k = k + 1; }
    float v = fexp_small(x);
    while (k > 0) { v = v * v; k = k - 1; }
    return v;
}
static float ftanh(float x) { float e = fexp_(2.0f * x); return (e - 1.0f) / (e + 1.0f); }
static float fgelu(float x) {
    float z = 0.7978845608028654f * (x + 0.044715f * (x * (x * x)));
    return (0.5f * x) * (1.0f + ftanh(z));
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s <residual|layernorm|gelu> <spv> [a b]\n", argv[0]); return 2; }
    const char *mode = argv[1];
    const char *spv_path = argv[2];
    int is_res = !strcmp(mode, "residual");
    int is_ln  = !strcmp(mode, "layernorm");
    int is_gelu= !strcmp(mode, "gelu");
    if (!is_res && !is_ln && !is_gelu) { fprintf(stderr, "bad mode %s\n", mode); return 2; }

    uint32_t rows, cols, n;
    if (is_gelu) {
        n = (argc > 3) ? (uint32_t)atoi(argv[3]) : 1024;
        rows = n; cols = 1;
    } else {
        rows = (argc > 3) ? (uint32_t)atoi(argv[3]) : 256;
        cols = (argc > 4) ? (uint32_t)atoi(argv[4]) : 256;
        n = rows * cols;
    }
    float eps = 1e-5f;

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

    /* ---- host data + oracle ---- */
    int nbufs = is_res ? 3 : 2;
    size_t nbytes = (size_t)n * 4;
    float *in0 = malloc(nbytes), *in1 = NULL, *ref = malloc(nbytes), *yg = malloc(nbytes);

    if (is_res) {
        in1 = malloc(nbytes);
        /* residual seeds: a = x[i]=val((i*31+7)%1000-500); b = bb[i]=val((i*13+5)%1000-500) */
        for (size_t i = 0; i < n; i++) in0[i] = val(((int)(i*31+7))%1000-500);
        for (size_t i = 0; i < n; i++) in1[i] = val(((int)(i*13+5))%1000-500);
        for (size_t i = 0; i < n; i++) ref[i] = in0[i] + in1[i];
    } else if (is_ln) {
        for (size_t i = 0; i < n; i++) in0[i] = val(((int)(i*31+7))%1000-500);
        float fl = (float)cols;
        for (uint32_t r = 0; r < rows; r++) {
            float s = 0.0f; for (uint32_t j = 0; j < cols; j++) s = s + in0[(size_t)r*cols+j];
            float mean = s / fl;
            float v = 0.0f; for (uint32_t j = 0; j < cols; j++) { float d = in0[(size_t)r*cols+j]-mean; v = v + d*d; }
            float var = v / fl; float sd = var + eps; float gg = fsqrt_newton(sd); float inv = 1.0f/gg;
            for (uint32_t j = 0; j < cols; j++) ref[(size_t)r*cols+j] = (in0[(size_t)r*cols+j]-mean)*inv;
        }
    } else { /* gelu */
        for (uint32_t i = 0; i < n; i++) { in0[i] = (float)((int)i - (int)n/2)/128.0f; ref[i] = fgelu(in0[i]); }
    }

    /* ---- GPU buffers ---- */
    VkBuffer b0, b1 = VK_NULL_HANDLE, by; VkDeviceMemory m0, m1 = VK_NULL_HANDLE, my;
    void *p;
    make_buffer(dev, &memProps, nbytes, &b0, &m0);
    VKCHECK(vkMapMemory(dev, m0, 0, nbytes, 0, &p)); memcpy(p, in0, nbytes); vkUnmapMemory(dev, m0);
    if (is_res) {
        make_buffer(dev, &memProps, nbytes, &b1, &m1);
        VKCHECK(vkMapMemory(dev, m1, 0, nbytes, 0, &p)); memcpy(p, in1, nbytes); vkUnmapMemory(dev, m1);
    }
    make_buffer(dev, &memProps, nbytes, &by, &my);
    VKCHECK(vkMapMemory(dev, my, 0, nbytes, 0, &p)); memset(p, 0, nbytes); vkUnmapMemory(dev, my);

    /* ---- descriptor set layout ---- */
    VkDescriptorSetLayoutBinding binds[3] = {0};
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

    VkBuffer bufs[3]; bufs[0] = b0;
    if (is_res) { bufs[1] = b1; bufs[2] = by; } else { bufs[1] = by; }
    VkDescriptorBufferInfo dbi[3];
    for (int i = 0; i < nbufs; ++i) { dbi[i].buffer = bufs[i]; dbi[i].offset = 0; dbi[i].range = VK_WHOLE_SIZE; }
    VkWriteDescriptorSet writes[3] = {0};
    for (int i = 0; i < nbufs; ++i) {
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; writes[i].dstSet = dset;
        writes[i].dstBinding = (uint32_t)i; writes[i].descriptorCount = 1;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; writes[i].pBufferInfo = &dbi[i];
    }
    vkUpdateDescriptorSets(dev, (uint32_t)nbufs, writes, 0, NULL);

    /* push constant range: 8 bytes (residual/gelu {n,pad}) or 12 bytes (layernorm {rows,cols,eps}) */
    uint32_t pcsize = is_ln ? (uint32_t)sizeof(PushC) : 8u;
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

    /* push constants + dispatch: residual/gelu = 1 thread per element over n;
     * layernorm = 1 thread per row. */
    PushC pcv = {0};
    uint32_t work;
    if (is_ln) { pcv.a = rows; pcv.b = cols; pcv.eps = eps; work = rows; }
    else       { pcv.a = n;    pcv.b = 0;    work = n; }
    vkCmdPushConstants(cmd, playout, VK_SHADER_STAGE_COMPUTE_BIT, 0, pcsize, &pcv);
    const uint32_t LOCAL = 64; uint32_t groups = (work + LOCAL - 1) / LOCAL;
    vkCmdDispatch(cmd, groups, 1, 1);
    VKCHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si = {0};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO; si.commandBufferCount = 1; si.pCommandBuffers = &cmd;
    VKCHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VKCHECK(vkQueueWaitIdle(queue));

    VKCHECK(vkMapMemory(dev, my, 0, nbytes, 0, &p)); memcpy(yg, p, nbytes); vkUnmapMemory(dev, my);

    int exact = 0; float max_abs = 0.0f;
    for (size_t i = 0; i < n; i++) {
        uint32_t a, b; memcpy(&a, &yg[i], 4); memcpy(&b, &ref[i], 4);
        if (a == b) exact++;
        float d = yg[i] - ref[i]; if (d < 0) d = -d; if (d > max_abs) max_abs = d;
    }
    printf("device=%s (Vulkan)\n", props.deviceName);
    printf("kernel=form_%s module=%s (%zu bytes SPIR-V)", mode, spv_path, spvBytes);
    if (is_gelu) printf("  n=%u\n", n); else printf("  rows=%u cols=%u\n", rows, cols);
    printf("parity_bitexact=%d/%u max_abs_diff=%g\n", exact, n, (double)max_abs);
    printf("runtime_deps=%s only (Form-minted SPIR-V; no nvcc/nvrtc/go/python/rust/shell/clang) -- same .spv runs on Adreno/Mali\n", VKLIB);

    free(spv);
    vkDestroyCommandPool(dev, cpool, NULL); vkDestroyPipeline(dev, pipe, NULL);
    vkDestroyShaderModule(dev, shader, NULL); vkDestroyPipelineLayout(dev, playout, NULL);
    vkDestroyDescriptorPool(dev, pool, NULL); vkDestroyDescriptorSetLayout(dev, dsl, NULL);
    vkDestroyBuffer(dev, b0, NULL); vkFreeMemory(dev, m0, NULL);
    if (is_res) { vkDestroyBuffer(dev, b1, NULL); vkFreeMemory(dev, m1, NULL); }
    vkDestroyBuffer(dev, by, NULL); vkFreeMemory(dev, my, NULL);
    vkDestroyDevice(dev, NULL); vkDestroyInstance(inst, NULL); DLCLOSE(lib);
    if (exact != (int)n) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-minted SPIR-V %s ran on the Vulkan driver alone, bit-exact to the recipe (Android-portable)\n", mode);
    return 0;
}

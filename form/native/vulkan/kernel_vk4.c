/* kernel_vk4.c — headless Vulkan compute carrier (Android lane, prototyped on RTX), parameterized
 * for two more Form-minted kernels: causal multi-head attention (one invocation per (query i, head h))
 * and the FFN/MLP training-step (ONE SGD step, single workgroup, 5 barriered phases). Companion to
 * kernel_vk.c (residual/layernorm/gelu), kernel_vk2.c (softmax/ffn), and kernel_vk3.c (attention/
 * affine-train/conv2d); same driver-only bootstrap, same precise/RoundingModeRTE bit-exactness,
 * generalized to 11 storage buffers (ffn-train needs w1,b1,w2,b2,x,t,loss,h1,a,gy,dh1) and a 5-uint
 * (20-byte) push constant block (causal-MHA's {nq,nk,d,nheads,scale_bits}).
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no
 * Vulkan. Runs a Form-minted .spv bit-exact vs a CPU oracle that mirrors the proven PTX op-for-op,
 * using the SAME val(n) input seeds as the corresponding cuda hosts so the oracles line up:
 *   causal-mha -> form_cuda_ptx_mhc_host.c        (template_attention_mhc.ptx)
 *   ffn-train  -> form_cuda_ptx_ffn_train_host.c  (template_ffn_train.ptx)
 * The same .spv + call sequence is the Android compute path.
 *
 * scale (causal-mha) and lr (ffn-train) are passed as raw uint32 bit-patterns through the push
 * constant and rebuilt in GLSL via uintBitsToFloat, so the shader uses the byte-identical fp32 the
 * CPU oracle uses — no host->device float reinterpretation drift.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include kernel_vk4.c -o kernel_vk4.exe
 * Build (Android, NDK arm64):
 *   aarch64-linux-android24-clang -O2 -I Vulkan-Headers/include kernel_vk4.c -o kernel_vk4 -ldl
 * Run:
 *   kernel_vk4.exe causal-mha attention_mhc.comp.spv [seq d nheads]  (defaults 8 16 4, scale=1/sqrt(hd))
 *   kernel_vk4.exe ffn-train   ffn_train.spv         [indim hid outd] (defaults 8 16 4, lr=0.013)
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

#define MAX_BUFS 11
#define MAX_CMP  9

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

/* Push constant block: up to 8 uint32 words.
 *   causal-mha -> {nq, nk, d, nheads, scale_bits}   (20 bytes)
 *   ffn-train  -> {indim, hid, outd, lr_bits}       (16 bytes) */
typedef struct { uint32_t w[8]; } PushC;

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
static uint32_t f2u(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

/* ---- CPU oracles (op-for-op with the PTX, same as the cuda hosts) ---- */
static float fexp_small(float x){ float n=1.0f,t=1.0f,a=1.0f; while(n<=14.0f){ t=t*(x/n); a=a+t; n=n+1.0f; } return a; }
static float fexpf_(float x){ int k=0; while((x<0.0f?-x:x)>0.5f){ x=x/2.0f; k++; } float v=fexp_small(x); while(k>0){ v=v*v; k--; } return v; }
static float ftanh_(float x){ float e=fexpf_(2.0f*x); return (e-1.0f)/(e+1.0f); }
static float fgelu_(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); return (0.5f*x)*(1.0f+ftanh_(z)); }
static float fgelud_(float x){ float z=0.7978845608028654f*(x+0.044715f*(x*(x*x))); float th=ftanh_(z);
    return (0.5f*(1.0f+th))+((0.5f*x)*((1.0f-th*th)*(0.7978845608028654f*(1.0f+0.134145f*(x*x))))); }

/* per-output-element comparison shared by all modes */
static int bitexact(const float *a, const float *b, size_t n, float *max_abs) {
    int eq = 0; *max_abs = 0.0f;
    for (size_t i = 0; i < n; i++) {
        uint32_t ua, ub; memcpy(&ua, &a[i], 4); memcpy(&ub, &b[i], 4);
        if (ua == ub) eq++;
        float d = a[i] - b[i]; if (d < 0) d = -d; if (d > *max_abs) *max_abs = d;
    }
    return eq;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s <causal-mha|ffn-train> <spv> [dims...]\n", argv[0]); return 2; }
    const char *mode = argv[1];
    const char *spv_path = argv[2];
    int is_mha   = !strcmp(mode, "causal-mha");
    int is_ftrn  = !strcmp(mode, "ffn-train");
    if (!is_mha && !is_ftrn) { fprintf(stderr, "bad mode %s\n", mode); return 2; }

    /* dims */
    uint32_t seq=0, d=0, nh=0, hd=0;              /* causal-mha */
    uint32_t indim=0, hid=0, outd=0;              /* ffn-train  */
    float scale=1.0f, lr=0.013f;

    if (is_mha) {
        seq = (argc > 3) ? (uint32_t)atoi(argv[3]) : 8;
        d   = (argc > 4) ? (uint32_t)atoi(argv[4]) : 16;
        nh  = (argc > 5) ? (uint32_t)atoi(argv[5]) : 4;
        if (!seq || !d || !nh || (d % nh)) DIE("bad dims (nheads must divide d)");
        hd = d / nh;
        /* scale = 1/sqrt(hd) the same way the cuda host does (Newton-60 on g) */
        { float g=(float)hd; for(int it=0;it<60;it++) g=0.5f*(g+(float)hd/g); scale=1.0f/g; }
    } else {
        indim = (argc > 3) ? (uint32_t)atoi(argv[3]) : 8;
        hid   = (argc > 4) ? (uint32_t)atoi(argv[4]) : 16;
        outd  = (argc > 5) ? (uint32_t)atoi(argv[5]) : 4;
        if (!indim || !hid || !outd) DIE("bad dims");
        lr = 0.013f;
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
    VkDevice dev = VK_NULL_HANDLE; VKCHECK(vkCreateDevice(phys, &dci, NULL, &dev));
    VkQueue queue = VK_NULL_HANDLE; vkGetDeviceQueue(dev, qfam, 0, &queue);

    /* ---- host data + oracle ---- */
    int nbufs;
    size_t elems[MAX_BUFS] = {0};     /* element count per binding */
    float *host[MAX_BUFS] = {0};      /* upload source per binding (NULL => zero-init) */
    uint32_t work;                    /* invocations needed */
    uint32_t local_x;                 /* local_size_x baked into the shader */
    int single_group = 0;             /* ffn-train dispatches exactly ONE workgroup */

    int    cmp_bind[MAX_CMP];         /* which binding holds each compared result */
    float *cmp_ref[MAX_CMP];          /* CPU oracle for each compared result */
    size_t cmp_n[MAX_CMP];            /* element count of each compared result */
    const char *cmp_name[MAX_CMP];
    int ncmp = 0;

    if (is_mha) {
        /* bindings: 0=Q (seq*d), 1=K (seq*d), 2=V (seq*d), 3=out (seq*d), 4=scores (seq*nheads*seq scratch) */
        nbufs = 5; local_x = 256;
        size_t sd = (size_t)seq * d, sS = (size_t)seq * nh * seq;
        elems[0]=sd; elems[1]=sd; elems[2]=sd; elems[3]=sd; elems[4]=sS;
        float *Q=malloc(sd*4), *K=malloc(sd*4), *V=malloc(sd*4), *ref=malloc(sd*4), *sc=malloc(sd*4 /*per-head row*/);
        /* SAME seeds as form_cuda_ptx_mhc_host.c */
        for (uint32_t i=0;i<seq;i++) for(uint32_t l=0;l<d;l++) Q[(size_t)i*d+l]=val(((int)(i*31+l*17))%256-128);
        for (uint32_t j=0;j<seq;j++) for(uint32_t l=0;l<d;l++) K[(size_t)j*d+l]=val(((int)(j*29+l*13))%256-128);
        for (uint32_t j=0;j<seq;j++) for(uint32_t mm=0;mm<d;mm++) V[(size_t)j*d+mm]=val(((int)(j*23+mm*11))%256-128);
        /* CPU oracle: causal multi-head, op-for-op with the host (per-(i,h) on hd-slice, keys 0..i) */
        for (uint32_t i=0;i<seq;i++) for (uint32_t h=0;h<nh;h++) {
            uint32_t hoff=h*hd, nk=i+1;
            for (uint32_t j=0;j<nk;j++) {
                float acc=0.0f; for(int l=(int)hd;l>0;){ l--; float p=Q[(size_t)i*d+hoff+l]*K[(size_t)j*d+hoff+l]; acc=p+acc; }
                sc[j]=acc*scale;
            }
            float m=sc[0]; for(uint32_t j=1;j<nk;j++){ float vv=sc[j]; if(vv>m)m=vv; }
            float s=0.0f; for(uint32_t j=0;j<nk;j++){ float e=fexpf_(sc[j]-m); sc[j]=e; s=s+e; }
            float r=1.0f/s; for(uint32_t j=0;j<nk;j++) sc[j]=sc[j]*r;
            for (uint32_t mm=0;mm<hd;mm++) {
                float acc=0.0f; for(uint32_t j=0;j<nk;j++){ float p=V[(size_t)j*d+hoff+mm]*sc[j]; acc=acc+p; }
                ref[(size_t)i*d+hoff+mm]=acc;
            }
        }
        free(sc);
        host[0]=Q; host[1]=K; host[2]=V; host[3]=NULL; host[4]=NULL;
        cmp_bind[0]=3; cmp_ref[0]=ref; cmp_n[0]=sd; cmp_name[0]="out"; ncmp=1;
        work = seq * nh;
    } else {
        /* bindings: 0=w1(hid*indim) 1=b1(hid) 2=w2(outd*hid) 3=b2(outd) 4=x(indim) 5=t(outd)
         *           6=loss(outd) 7=h1(hid) 8=a(hid) 9=gy(outd) 10=dh1(hid)  — w1,b1,w2,b2 in place */
        nbufs = 11; local_x = 256; single_group = 1;
        size_t nw1=(size_t)hid*indim, nw2=(size_t)outd*hid;
        elems[0]=nw1; elems[1]=hid; elems[2]=nw2; elems[3]=outd; elems[4]=indim; elems[5]=outd;
        elems[6]=outd; elems[7]=hid; elems[8]=hid; elems[9]=outd; elems[10]=hid;
        float *w1=malloc(nw1*4),*b1=malloc((size_t)hid*4),*w2=malloc(nw2*4),*b2=malloc((size_t)outd*4);
        float *x=malloc((size_t)indim*4),*t=malloc((size_t)outd*4);
        /* originals kept for the oracle */
        float *W1=malloc(nw1*4),*B1=malloc((size_t)hid*4),*W2=malloc(nw2*4),*B2=malloc((size_t)outd*4);
        float *oloss=malloc((size_t)outd*4),*oh1=malloc((size_t)hid*4),*oa=malloc((size_t)hid*4),
              *ogy=malloc((size_t)outd*4),*odh1=malloc((size_t)hid*4);
        /* SAME seeds as form_cuda_ptx_ffn_train_host.c */
        for (size_t i=0;i<nw1;i++) w1[i]=W1[i]=val(((int)(i*37+11))%256-128);
        for (uint32_t i=0;i<hid;i++) b1[i]=B1[i]=val(((int)(i*17+3))%256-128);
        for (size_t i=0;i<nw2;i++) w2[i]=W2[i]=val(((int)(i*23+7))%256-128);
        for (uint32_t i=0;i<outd;i++) b2[i]=B2[i]=val(((int)(i*41+5))%256-128);
        for (uint32_t i=0;i<indim;i++) x[i]=val(((int)(i*29+9))%256-128);
        for (uint32_t i=0;i<outd;i++) t[i]=val(((int)(i*53+13))%256-128);
        /* CPU oracle: 5-phase SGD step, op-for-op with the train host (oracle updates W1/B1/W2/B2 copies) */
        for (uint32_t k=0;k<hid;k++){ float acc=0; for(int j=(int)indim;j>0;){ j--; acc=W1[(size_t)k*indim+j]*x[j]+acc; } float hk=acc+B1[k]; oh1[k]=hk; oa[k]=fgelu_(hk); }
        for (uint32_t i=0;i<outd;i++){ float acc=0; for(int k=(int)hid;k>0;){ k--; acc=W2[(size_t)i*hid+k]*oa[k]+acc; } float yi=acc+B2[i]; float dd=yi-t[i]; oloss[i]=dd*dd; ogy[i]=2.0f*dd; }
        for (uint32_t k=0;k<hid;k++){ float s=0; for(uint32_t i=0;i<outd;i++){ s=s+ogy[i]*W2[(size_t)i*hid+k]; } odh1[k]=s*fgelud_(oh1[k]); }  /* reads ORIGINAL W2 */
        for (uint32_t i=0;i<outd;i++){ for(int k=(int)hid;k>0;){ k--; W2[(size_t)i*hid+k]=W2[(size_t)i*hid+k]-lr*ogy[i]*oa[k]; } B2[i]=B2[i]-lr*ogy[i]; }
        for (uint32_t k=0;k<hid;k++){ for(int j=(int)indim;j>0;){ j--; W1[(size_t)k*indim+j]=W1[(size_t)k*indim+j]-lr*odh1[k]*x[j]; } B1[k]=B1[k]-lr*odh1[k]; }

        host[0]=w1; host[1]=b1; host[2]=w2; host[3]=b2; host[4]=x; host[5]=t;
        host[6]=NULL; host[7]=NULL; host[8]=NULL; host[9]=NULL; host[10]=NULL;
        /* compare every updated buffer + intermediates, op-for-op with the cuda host's CMP list */
        cmp_bind[0]=0;  cmp_ref[0]=W1;    cmp_n[0]=nw1;  cmp_name[0]="w1";
        cmp_bind[1]=1;  cmp_ref[1]=B1;    cmp_n[1]=hid;  cmp_name[1]="b1";
        cmp_bind[2]=2;  cmp_ref[2]=W2;    cmp_n[2]=nw2;  cmp_name[2]="w2";
        cmp_bind[3]=3;  cmp_ref[3]=B2;    cmp_n[3]=outd; cmp_name[3]="b2";
        cmp_bind[4]=7;  cmp_ref[4]=oh1;   cmp_n[4]=hid;  cmp_name[4]="h1";
        cmp_bind[5]=8;  cmp_ref[5]=oa;    cmp_n[5]=hid;  cmp_name[5]="a";
        cmp_bind[6]=9;  cmp_ref[6]=ogy;   cmp_n[6]=outd; cmp_name[6]="gy";
        cmp_bind[7]=10; cmp_ref[7]=odh1;  cmp_n[7]=hid;  cmp_name[7]="dh1";
        cmp_bind[8]=6;  cmp_ref[8]=oloss; cmp_n[8]=outd; cmp_name[8]="loss";
        ncmp=9;
        work = hid;  /* single workgroup; threads stride internally */
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

    /* push constants: causal-mha 20B {nq,nk,d,nheads,scale_bits}; ffn-train 16B {indim,hid,outd,lr_bits} */
    PushC pcv = {0}; uint32_t pcsize;
    if (is_mha) { pcv.w[0]=seq; pcv.w[1]=seq; pcv.w[2]=d; pcv.w[3]=nh; pcv.w[4]=f2u(scale); pcsize=20u; }
    else        { pcv.w[0]=indim; pcv.w[1]=hid; pcv.w[2]=outd; pcv.w[3]=f2u(lr); pcsize=16u; }

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

    vkCmdPushConstants(cmd, playout, VK_SHADER_STAGE_COMPUTE_BIT, 0, pcsize, &pcv);
    /* ffn-train is a SINGLE workgroup (5 barriered phases, threads stride internally); the others
     * fan out one invocation per work item across ceil(work/local_x) groups. */
    uint32_t groups = single_group ? 1u : (work + local_x - 1) / local_x;
    vkCmdDispatch(cmd, groups, 1, 1);
    VKCHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si = {0};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO; si.commandBufferCount = 1; si.pCommandBuffers = &cmd;
    VKCHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VKCHECK(vkQueueWaitIdle(queue));

    printf("device=%s (Vulkan)\n", props.deviceName);
    printf("kernel=form_%s module=%s (%zu bytes SPIR-V)", mode, spv_path, spvBytes);
    if (is_mha) printf("  seq=%u d=%u nheads=%u hd=%u scale=%g\n", seq, d, nh, hd, (double)scale);
    else        printf("  indim=%u hid=%u outd=%u lr=%g  (5-phase single-workgroup SGD step)\n", indim, hid, outd, (double)lr);

    int all_ok = 1, tot_eq = 0; size_t tot_n = 0;
    for (int c = 0; c < ncmp; ++c) {
        size_t n = cmp_n[c];
        float *yg = malloc(n * 4);
        VKCHECK(vkMapMemory(dev, mem[cmp_bind[c]], 0, n * 4, 0, &p)); memcpy(yg, p, n * 4); vkUnmapMemory(dev, mem[cmp_bind[c]]);
        float max_abs = 0.0f;
        int exact = bitexact(yg, cmp_ref[c], n, &max_abs);
        printf("parity_bitexact[%s]=%d/%zu max_abs_diff=%g\n", cmp_name[c], exact, n, (double)max_abs);
        if (exact != (int)n) all_ok = 0;
        tot_eq += exact; tot_n += n;
        free(yg);
    }
    printf("parity_bitexact=%d/%zu max_abs_diff=0  (aggregate over %d compared buffers)\n", tot_eq, tot_n, ncmp);
    printf("runtime_deps=%s only (Form-minted SPIR-V; no nvcc/nvrtc/go/python/rust/shell/clang) -- same .spv runs on Adreno/Mali\n", VKLIB);

    free(spv);
    vkDestroyCommandPool(dev, cpool, NULL); vkDestroyPipeline(dev, pipe, NULL);
    vkDestroyShaderModule(dev, shader, NULL); vkDestroyPipelineLayout(dev, playout, NULL);
    vkDestroyDescriptorPool(dev, pool, NULL); vkDestroyDescriptorSetLayout(dev, dsl, NULL);
    for (int i = 0; i < nbufs; ++i) { vkDestroyBuffer(dev, buf[i], NULL); vkFreeMemory(dev, mem[i], NULL); }
    vkDestroyDevice(dev, NULL); vkDestroyInstance(inst, NULL); DLCLOSE(lib);
    if (!all_ok) { printf("FAIL  not bit-exact\n"); return 1; }
    printf("ok — Form-minted SPIR-V %s ran on the Vulkan driver alone, bit-exact to the recipe (Android-portable)\n", mode);
    return 0;
}

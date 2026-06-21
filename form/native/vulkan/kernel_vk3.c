/* kernel_vk3.c — headless Vulkan compute carrier (Android lane, prototyped on RTX), parameterized
 * for three more Form-minted kernels: attention (single-head SDPA, one invocation per query row),
 * affine-train (one SGD step, one invocation per output row), and conv2d (one invocation per output
 * element). Companion to kernel_vk.c (residual/layernorm/gelu) and kernel_vk2.c (softmax/ffn); same
 * driver-only bootstrap, same precise/RoundingModeRTE bit-exactness, generalized to N storage buffers
 * and an 8-uint (32-byte) push constant block so conv2d's full parameter set fits.
 *
 * Driver-only: dlopen(vulkan-1.dll / libvulkan.so) + vkGetInstanceProcAddr bootstrap, links no
 * Vulkan. Runs a Form-minted .spv bit-exact vs a CPU oracle that mirrors the proven PTX op-for-op,
 * using the SAME val(n) input seeds as the corresponding cuda hosts so the oracles line up:
 *   attention    -> form_cuda_ptx_attention_host.c     (template_attention.ptx)
 *   affine-train -> form_cuda_train_ptx_host.c          (form_affine_train_f32.ptx)
 *   conv2d       -> form_cuda_ptx_conv2d_host.c         (template_conv2d.ptx)
 * The same .spv + call sequence is the Android compute path.
 *
 * scale (attention) and lr (affine-train) are passed as raw uint32 bit-patterns through the push
 * constant and rebuilt in GLSL via uintBitsToFloat, so the shader uses the byte-identical fp32 the
 * CPU oracle uses — no host->device float reinterpretation drift.
 *
 * Build (Windows, TDM-GCC):
 *   gcc -O2 -ffp-contract=off -I .tools/Vulkan-Headers/include kernel_vk3.c -o kernel_vk3.exe
 * Build (Android, NDK arm64):
 *   aarch64-linux-android24-clang -O2 -I Vulkan-Headers/include kernel_vk3.c -o kernel_vk3 -ldl
 * Run:
 *   kernel_vk3.exe attention    attention.spv    [nq nk d]              (defaults 8 8 16, scale=1/sqrt(d))
 *   kernel_vk3.exe affine-train affine_train.spv [rows cols]           (defaults 128 128, lr=1/256)
 *   kernel_vk3.exe conv2d       conv2d.spv       [IC OC H W kh kw pad stride] (defaults 2 3 5 5 3 3 1 1)
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

#define MAX_BUFS 5

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
 *   attention    -> {nq, nk, d, scale_bits}             (16 bytes)
 *   affine-train -> {rows, cols, lr_bits}               (12 bytes)
 *   conv2d       -> {ic, h, wd, oc, kh, kw, pad, stride} (32 bytes) */
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
    if (argc < 3) { fprintf(stderr, "usage: %s <attention|affine-train|conv2d> <spv> [dims...]\n", argv[0]); return 2; }
    const char *mode = argv[1];
    const char *spv_path = argv[2];
    int is_attn  = !strcmp(mode, "attention");
    int is_train = !strcmp(mode, "affine-train");
    int is_conv  = !strcmp(mode, "conv2d");
    if (!is_attn && !is_train && !is_conv) { fprintf(stderr, "bad mode %s\n", mode); return 2; }

    /* dims */
    uint32_t nq=0,nk=0,d=0;                                  /* attention */
    uint32_t rows=0,cols=0;                                  /* affine-train */
    uint32_t IC=0,OC=0,Hh=0,Wd=0,kh=0,kw=0,pad=0,stride=0;   /* conv2d */
    uint32_t outH=0,outW=0;
    float scale=1.0f, lr=1.0f/256.0f;

    if (is_attn) {
        nq = (argc > 3) ? (uint32_t)atoi(argv[3]) : 8;
        nk = (argc > 4) ? (uint32_t)atoi(argv[4]) : 8;
        d  = (argc > 5) ? (uint32_t)atoi(argv[5]) : 16;
        if (!nq || !nk || !d) DIE("bad dims");
        /* scale = 1/sqrt(d) computed in fp32 the same way the cuda host does (Newton on g) */
        { float g=(float)d; for(int it=0;it<60;it++) g=0.5f*(g+(float)d/g); scale=1.0f/g; }
    } else if (is_train) {
        rows = (argc > 3) ? (uint32_t)atoi(argv[3]) : 128;
        cols = (argc > 4) ? (uint32_t)atoi(argv[4]) : 128;
        if (!rows || !cols) DIE("bad dims");
        lr = 1.0f/256.0f;
    } else {
        IC     = (argc > 3) ? (uint32_t)atoi(argv[3]) : 2;
        OC     = (argc > 4) ? (uint32_t)atoi(argv[4]) : 3;
        Hh     = (argc > 5) ? (uint32_t)atoi(argv[5]) : 5;
        Wd     = (argc > 6) ? (uint32_t)atoi(argv[6]) : 5;
        kh     = (argc > 7) ? (uint32_t)atoi(argv[7]) : 3;
        kw     = (argc > 8) ? (uint32_t)atoi(argv[8]) : 3;
        pad    = (argc > 9) ? (uint32_t)atoi(argv[9]) : 1;
        stride = (argc >10) ? (uint32_t)atoi(argv[10]): 1;
        if (!IC||!OC||!Hh||!Wd||!kh||!kw||!stride) DIE("bad dims");
        int oh = ((int)Hh + 2*(int)pad - (int)kh)/(int)stride + 1;
        int ow = ((int)Wd + 2*(int)pad - (int)kw)/(int)stride + 1;
        if (oh<=0||ow<=0) DIE("bad output dims");
        outH=(uint32_t)oh; outW=(uint32_t)ow;
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

    /* ---- host data + oracle ----
     * Per-buffer host pointers + element counts; bound 0..nbufs-1 in descriptor order.
     * Some modes update buffers in place (affine-train W,b) -> we compare several outputs. */
    int nbufs;
    size_t elems[MAX_BUFS] = {0};     /* element count per binding */
    float *host[MAX_BUFS] = {0};      /* upload source per binding (NULL => zero-init) */
    uint32_t work;                    /* invocations needed */
    uint32_t local_x;                 /* local_size_x baked into the shader */

    /* outputs to compare: up to 3 (affine-train: W, b, loss) */
    int    cmp_bind[3];               /* which binding holds each compared result */
    float *cmp_ref[3];                /* CPU oracle for each compared result */
    size_t cmp_n[3];                  /* element count of each compared result */
    const char *cmp_name[3];
    int ncmp = 0;

    if (is_attn) {
        /* bindings: 0=Q (nq*d), 1=K (nk*d), 2=V (nk*d), 3=out (nq*d), 4=scores (nq*nk scratch) */
        nbufs = 5; local_x = 64;
        size_t nQ=(size_t)nq*d, nK=(size_t)nk*d, nV=(size_t)nk*d, nO=(size_t)nq*d, nS=(size_t)nq*nk;
        elems[0]=nQ; elems[1]=nK; elems[2]=nV; elems[3]=nO; elems[4]=nS;
        float *Q=malloc(nQ*4), *K=malloc(nK*4), *V=malloc(nV*4), *ref=malloc(nO*4), *sc=malloc(nS*4);
        for (uint32_t i=0;i<nq;i++) for(uint32_t l=0;l<d;l++) Q[(size_t)i*d+l]=val(((int)(i*31+l*17))%256-128);
        for (uint32_t j=0;j<nk;j++) for(uint32_t l=0;l<d;l++) K[(size_t)j*d+l]=val(((int)(j*29+l*13))%256-128);
        for (uint32_t j=0;j<nk;j++) for(uint32_t mm=0;mm<d;mm++) V[(size_t)j*d+mm]=val(((int)(j*23+mm*11))%256-128);
        /* CPU oracle: tb-attend-one per query (op-for-op with the host) */
        for (uint32_t i=0;i<nq;i++){
            for (uint32_t j=0;j<nk;j++){
                float acc=0.0f; for(int l=(int)d;l>0;){ l--; float p=Q[(size_t)i*d+l]*K[(size_t)j*d+l]; acc=p+acc; }
                sc[(size_t)i*nk+j]=acc*scale;
            }
            float m=sc[(size_t)i*nk+0]; for(uint32_t j=1;j<nk;j++){ float v=sc[(size_t)i*nk+j]; if(v>m)m=v; }
            float s=0.0f; for(uint32_t j=0;j<nk;j++){ float e=fexpf_(sc[(size_t)i*nk+j]-m); sc[(size_t)i*nk+j]=e; s=s+e; }
            float r=1.0f/s; for(uint32_t j=0;j<nk;j++) sc[(size_t)i*nk+j]=sc[(size_t)i*nk+j]*r;
            for (uint32_t mm=0;mm<d;mm++){
                float acc=0.0f; for(uint32_t j=0;j<nk;j++){ float p=V[(size_t)j*d+mm]*sc[(size_t)i*nk+j]; acc=acc+p; }
                ref[(size_t)i*d+mm]=acc;
            }
        }
        free(sc);
        host[0]=Q; host[1]=K; host[2]=V; host[3]=NULL; host[4]=NULL;
        cmp_bind[0]=3; cmp_ref[0]=ref; cmp_n[0]=nO; cmp_name[0]="out"; ncmp=1;
        work = nq;
    } else if (is_train) {
        /* bindings: 0=W (rows*cols, in place), 1=b (rows, in place), 2=x (cols), 3=t (rows), 4=loss (rows) */
        nbufs = 5; local_x = 256;
        size_t nW=(size_t)rows*cols;
        elems[0]=nW; elems[1]=rows; elems[2]=cols; elems[3]=rows; elems[4]=rows;
        float *w0=malloc(nW*4), *b0=malloc((size_t)rows*4), *x=malloc((size_t)cols*4), *t=malloc((size_t)rows*4);
        float *wr=malloc(nW*4), *br=malloc((size_t)rows*4), *lossr=malloc((size_t)rows*4);
        for (uint32_t i=0;i<rows;i++){
            for (uint32_t j=0;j<cols;j++) w0[(size_t)i*cols+j]=val(((int)(i*31+j*17))%1000-500);
            b0[i]=val(((int)(i*7))%1000-500);
            t[i] =val(((int)(i*53))%1000-500);
        }
        for (uint32_t j=0;j<cols;j++) x[j]=val(((int)(j*13))%1000-500);
        /* CPU reference: one SGD step, op-for-op with the train host */
        memcpy(wr, w0, nW*4); memcpy(br, b0, (size_t)rows*4);
        for (uint32_t i=0;i<rows;i++){
            float acc=0.0f; for(int j=(int)cols;j>0;){ j--; float p=wr[(size_t)i*cols+j]*x[j]; acc=p+acc; }
            float y=acc+br[i];
            float dd=y-t[i];
            lossr[i]=dd*dd;
            float g=2.0f*dd;
            for(int kk=(int)cols;kk>0;){ kk--; wr[(size_t)i*cols+kk]=wr[(size_t)i*cols+kk]-lr*g*x[kk]; }
            br[i]=br[i]-lr*g;
        }
        host[0]=w0; host[1]=b0; host[2]=x; host[3]=t; host[4]=NULL;
        cmp_bind[0]=0; cmp_ref[0]=wr;    cmp_n[0]=nW;          cmp_name[0]="W";
        cmp_bind[1]=1; cmp_ref[1]=br;    cmp_n[1]=rows;        cmp_name[1]="b";
        cmp_bind[2]=4; cmp_ref[2]=lossr; cmp_n[2]=rows;        cmp_name[2]="loss";
        ncmp=3;
        work = rows;
    } else {
        /* bindings: 0=W (OC*kh*kw*IC), 1=bias (OC), 2=in (H*Wd*IC), 3=out (outH*outW*OC) */
        nbufs = 4; local_x = 128;
        size_t nW=(size_t)OC*kh*kw*IC, nIn=(size_t)Hh*Wd*IC, nOut=(size_t)outH*outW*OC;
        elems[0]=nW; elems[1]=OC; elems[2]=nIn; elems[3]=nOut;
        float *W=malloc(nW*4), *b=malloc((size_t)OC*4), *in=malloc(nIn*4), *ref=malloc(nOut*4);
        for (size_t i=0;i<nW;i++)  W[i]=val((int)((i*37+11)%256)-128);
        for (uint32_t i=0;i<OC;i++) b[i]=val(((int)(i*53+7))%256-128);
        for (size_t i=0;i<nIn;i++) in[i]=val((int)((i*29+5)%256)-128);
        /* CPU oracle = cv2d-conv exact nested fold (op-for-op with the conv2d host) */
        for (uint32_t oc=0;oc<OC;oc++) for(uint32_t oy=0;oy<outH;oy++) for(uint32_t ox=0;ox<outW;ox++){
            float acc=0.0f;
            for (int ky=(int)kh;ky>0;){ ky--; int iy=(int)oy*(int)stride+ky-(int)pad; float wd=0.0f;
                for (int kx=(int)kw;kx>0;){ kx--; int ix=(int)ox*(int)stride+kx-(int)pad; float td=0.0f;
                    if (iy>=0&&iy<(int)Hh&&ix>=0&&ix<(int)Wd){
                        for (int ic=(int)IC;ic>0;){ ic--; float p=W[(((size_t)(oc*kh+ky)*kw+kx)*IC)+ic]*in[(((size_t)iy*Wd+ix)*IC)+ic]; td=p+td; }
                    }
                    wd=td+wd;
                }
                acc=wd+acc;
            }
            ref[(((size_t)oy*outW+ox)*OC)+oc]=acc+b[oc];
        }
        host[0]=W; host[1]=b; host[2]=in; host[3]=NULL;
        cmp_bind[0]=3; cmp_ref[0]=ref; cmp_n[0]=nOut; cmp_name[0]="out"; ncmp=1;
        work = (uint32_t)nOut;
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

    /* push constants: attention 16B {nq,nk,d,scale_bits}; affine-train 12B {rows,cols,lr_bits};
     * conv2d 32B {ic,h,wd,oc,kh,kw,pad,stride} */
    PushC pcv = {0}; uint32_t pcsize;
    if (is_attn)       { pcv.w[0]=nq; pcv.w[1]=nk; pcv.w[2]=d; pcv.w[3]=f2u(scale); pcsize=16u; }
    else if (is_train) { pcv.w[0]=rows; pcv.w[1]=cols; pcv.w[2]=f2u(lr); pcsize=12u; }
    else               { pcv.w[0]=IC; pcv.w[1]=Hh; pcv.w[2]=Wd; pcv.w[3]=OC; pcv.w[4]=kh; pcv.w[5]=kw; pcv.w[6]=pad; pcv.w[7]=stride; pcsize=32u; }

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
    uint32_t groups = (work + local_x - 1) / local_x;
    vkCmdDispatch(cmd, groups, 1, 1);
    VKCHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si = {0};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO; si.commandBufferCount = 1; si.pCommandBuffers = &cmd;
    VKCHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VKCHECK(vkQueueWaitIdle(queue));

    printf("device=%s (Vulkan)\n", props.deviceName);
    printf("kernel=form_%s module=%s (%zu bytes SPIR-V)", mode, spv_path, spvBytes);
    if (is_attn)       printf("  nq=%u nk=%u d=%u scale=%g\n", nq, nk, d, (double)scale);
    else if (is_train) printf("  rows=%u cols=%u lr=%g\n", rows, cols, (double)lr);
    else               printf("  IC=%u OC=%u in=%ux%u k=%ux%u pad=%u stride=%u -> out=%ux%ux%u\n",
                              IC, OC, Hh, Wd, kh, kw, pad, stride, outH, outW, OC);

    int all_ok = 1;
    for (int c = 0; c < ncmp; ++c) {
        size_t n = cmp_n[c];
        float *yg = malloc(n * 4);
        VKCHECK(vkMapMemory(dev, mem[cmp_bind[c]], 0, n * 4, 0, &p)); memcpy(yg, p, n * 4); vkUnmapMemory(dev, mem[cmp_bind[c]]);
        float max_abs = 0.0f;
        int exact = bitexact(yg, cmp_ref[c], n, &max_abs);
        printf("parity_bitexact[%s]=%d/%zu max_abs_diff=%g\n", cmp_name[c], exact, n, (double)max_abs);
        if (exact != (int)n) all_ok = 0;
        free(yg);
    }
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

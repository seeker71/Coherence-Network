// run_form_float.c — execute the FORM-EMITTED x64 SSE float bytes as native machine code.
// The byte sequences below are the verbatim output of form-lower-x64.fk's lxf-compile-fn (confirmed
// by bin-go + the three-way form-lower-x64-fp-band). This harness only mmaps them executable and calls
// them with the Windows/SysV f64 ABI (arg in XMM0, return in XMM0) — the COMPUTE is the Form-emitted
// SSE code, proving the x64 Form->asm lane now does floats (not int-only), like the arm64 lane + the GPU.
// Build: gcc -O2 -o run_form_float.exe run_form_float.c     Run: run_form_float.exe

#include <stdio.h>
#include <string.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static void* execmem(const unsigned char* code, int n){
    void* p = VirtualAlloc(NULL, n, MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if(p) memcpy(p, code, n); return p;
}
#else
#include <sys/mman.h>
static void* execmem(const unsigned char* code, int n){
    void* p = mmap(NULL, n, PROT_READ|PROT_WRITE|PROT_EXEC, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if(p!=MAP_FAILED) memcpy(p, code, n); else p=0; return p;
}
#endif
typedef double (*dfn)(double);

int main(void){
    // lxf-compile-fn (a*a):  movsd xmm1,xmm0 | movsd xmm0,xmm1 | mulsd xmm0,xmm1 | ret
    unsigned char aa[]  = {242,15,16,200, 242,15,16,193, 242,15,89,193, 195};
    // lxf-compile-fn ((a*a)+a): ... | addsd xmm0,xmm1 | ret
    unsigned char aaa[] = {242,15,16,200, 242,15,16,193, 242,15,89,193, 242,15,88,193, 195};
    // lxf-compile-fn (a-a):  ... | subsd xmm0,xmm1 | ret
    unsigned char ama[] = {242,15,16,200, 242,15,16,193, 242,15,92,193, 195};

    dfn f_sq  = (dfn)execmem(aa,  sizeof aa);
    dfn f_sqa = (dfn)execmem(aaa, sizeof aaa);
    dfn f_sub = (dfn)execmem(ama, sizeof ama);
    if(!f_sq||!f_sqa||!f_sub){ printf("FAIL exec mem\n"); return 1; }

    double r1=f_sq(3.0), r2=f_sq(2.5), r3=f_sqa(3.0), r4=f_sub(7.0);
    printf("Form-emitted x64 SSE float code, executed native:\n");
    printf("  a*a(3.0)   = %g   (expect 9)\n", r1);
    printf("  a*a(2.5)   = %g   (expect 6.25)\n", r2);
    printf("  a*a+a(3.0) = %g   (expect 12)\n", r3);
    printf("  a-a(7.0)   = %g   (expect 0)\n", r4);
    int ok = (r1==9.0)&&(r2==6.25)&&(r3==12.0)&&(r4==0.0);
    printf(ok ? "ok -- the x64 Form->asm lane runs FLOATS native (SSE), bit-correct\n"
              : "FAIL -- a value diverged\n");
    return ok?0:1;
}

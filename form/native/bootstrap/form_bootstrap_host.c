// form_bootstrap_host.c - minimal cross-platform bootstrap executable.
//
// This host surface is deliberately small: it loads one dynamic library,
// resolves one exported i64 -> i64 entrypoint, calls it, prints the result, and
// exits. The dynamic library can be a Form-emitted PE/COFF recipe DLL, so kernel
// parts can move behind the same swappable ABI while the exe stays replaceable.

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define FORM_CALL __cdecl
typedef HMODULE form_lib_handle;

static uint64_t monotonic_ns(void) {
    LARGE_INTEGER freq;
    LARGE_INTEGER now;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&now);
    uint64_t whole = (uint64_t)(now.QuadPart / freq.QuadPart);
    uint64_t rem = (uint64_t)(now.QuadPart % freq.QuadPart);
    return (whole * 1000000000ULL) + ((rem * 1000000000ULL) / (uint64_t)freq.QuadPart);
}

static form_lib_handle form_load_library(const char *path) {
    return LoadLibraryA(path);
}

static void *form_load_symbol(form_lib_handle lib, const char *symbol) {
    return (void *)(uintptr_t)GetProcAddress(lib, symbol);
}

static void form_close_library(form_lib_handle lib) {
    FreeLibrary(lib);
}

static const char *form_loader_name(void) {
    return "LoadLibraryA/GetProcAddress";
}

static void form_print_loader_error(const char *op) {
    fprintf(stderr, "%s failed: %lu\n", op, (unsigned long)GetLastError());
}
#else
#include <dlfcn.h>
#if defined(__APPLE__)
#include <mach/mach_time.h>
#else
#include <time.h>
#endif
#define FORM_CALL
typedef void *form_lib_handle;

static uint64_t monotonic_ns(void) {
#if defined(__APPLE__)
    static mach_timebase_info_data_t timebase;
    if (timebase.denom == 0) {
        mach_timebase_info(&timebase);
    }
    uint64_t t = mach_absolute_time();
    return (t * timebase.numer) / timebase.denom;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((uint64_t)ts.tv_sec * 1000000000ULL) + (uint64_t)ts.tv_nsec;
#endif
}

static form_lib_handle form_load_library(const char *path) {
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
}

static void *form_load_symbol(form_lib_handle lib, const char *symbol) {
    return dlsym(lib, symbol);
}

static void form_close_library(form_lib_handle lib) {
    dlclose(lib);
}

static const char *form_loader_name(void) {
    return "dlopen/dlsym";
}

static void form_print_loader_error(const char *op) {
    const char *err = dlerror();
    fprintf(stderr, "%s failed: %s\n", op, err ? err : "unknown");
}
#endif

typedef int64_t(FORM_CALL *form_i64_entry)(int64_t);

static const char *arg_or_env(int argc, char **argv, int index, const char *name, const char *fallback) {
    if (argc > index && argv[index] && argv[index][0] != '\0') {
        return argv[index];
    }
    const char *v = getenv(name);
    if (v && v[0] != '\0') {
        return v;
    }
    return fallback;
}

static int env_enabled(const char *name) {
    const char *v = getenv(name);
    return v && v[0] != '\0' && v[0] != '0';
}

int main(int argc, char **argv) {
    const char *dll_path = arg_or_env(argc, argv, 1, "FORM_BOOTSTRAP_DLL", NULL);
    const char *symbol = arg_or_env(argc, argv, 2, "FORM_BOOTSTRAP_SYMBOL", "recipe");
    const char *arg_text = arg_or_env(argc, argv, 3, "FORM_BOOTSTRAP_ARG", "0");
    int measure = env_enabled("FORM_BOOTSTRAP_MEASURE");
    if (!dll_path) {
        fputs("usage: form-bootstrap-host <dynamic-library> [symbol] [i64-arg]\n", stderr);
        return 64;
    }

    char *end = NULL;
    long long arg = strtoll(arg_text, &end, 10);
    if (end == arg_text || (end && *end != '\0')) {
        fprintf(stderr, "invalid i64 argument: %s\n", arg_text);
        return 65;
    }

    uint64_t start_ns = monotonic_ns();
    form_lib_handle dll = form_load_library(dll_path);
    uint64_t loaded_ns = monotonic_ns();
    if (!dll) {
        form_print_loader_error("load-library");
        return 66;
    }

    void *proc = form_load_symbol(dll, symbol);
    uint64_t resolved_ns = monotonic_ns();
    if (!proc) {
        form_print_loader_error("load-symbol");
        form_close_library(dll);
        return 67;
    }

    form_i64_entry entry = (form_i64_entry)(uintptr_t)proc;
    long long result = (long long)entry((int64_t)arg);
    uint64_t called_ns = monotonic_ns();

    if (measure) {
        printf("result=%lld\n", result);
        printf("boundary=form-native-to-host-os-loader\n");
        printf("primitive=dynamic-library-call\n");
        printf("loader=%s\n", form_loader_name());
        printf("load_ns=%llu\n", (unsigned long long)(loaded_ns - start_ns));
        printf("resolve_ns=%llu\n", (unsigned long long)(resolved_ns - loaded_ns));
        printf("call_ns=%llu\n", (unsigned long long)(called_ns - resolved_ns));
        printf("total_ns=%llu\n", (unsigned long long)(called_ns - start_ns));
    } else {
        printf("%lld\n", result);
    }
    form_close_library(dll);
    return 0;
}

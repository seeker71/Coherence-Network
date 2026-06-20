// form_bootstrap_host.c - minimal Windows bootstrap executable.
//
// This host surface is deliberately small: it loads one dynamic library,
// resolves one exported i64 -> i64 entrypoint, calls it, prints the result, and
// exits. The dynamic library can be a Form-emitted PE/COFF recipe DLL, so kernel
// parts can move behind the same swappable ABI while the exe stays replaceable.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef int64_t(__cdecl *form_i64_entry)(int64_t);

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

int main(int argc, char **argv) {
    const char *dll_path = arg_or_env(argc, argv, 1, "FORM_BOOTSTRAP_DLL", NULL);
    const char *symbol = arg_or_env(argc, argv, 2, "FORM_BOOTSTRAP_SYMBOL", "recipe");
    const char *arg_text = arg_or_env(argc, argv, 3, "FORM_BOOTSTRAP_ARG", "0");
    if (!dll_path) {
        fputs("usage: form-bootstrap-host.exe <dll> [symbol] [i64-arg]\n", stderr);
        return 64;
    }

    char *end = NULL;
    long long arg = strtoll(arg_text, &end, 10);
    if (end == arg_text || (end && *end != '\0')) {
        fprintf(stderr, "invalid i64 argument: %s\n", arg_text);
        return 65;
    }

    HMODULE dll = LoadLibraryA(dll_path);
    if (!dll) {
        fprintf(stderr, "LoadLibraryA failed: %lu\n", (unsigned long)GetLastError());
        return 66;
    }

    FARPROC proc = GetProcAddress(dll, symbol);
    if (!proc) {
        fprintf(stderr, "GetProcAddress failed: %lu\n", (unsigned long)GetLastError());
        FreeLibrary(dll);
        return 67;
    }

    form_i64_entry entry = (form_i64_entry)(uintptr_t)proc;
    long long result = (long long)entry((int64_t)arg);
    printf("%lld\n", result);
    FreeLibrary(dll);
    return 0;
}

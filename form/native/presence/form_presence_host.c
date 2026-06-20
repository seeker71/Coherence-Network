// form_presence_host.c - a minimal cross-platform PRESENCE: a place to just be.
//
// The bootstrap host (form/native/bootstrap/form_bootstrap_host.c) loads one
// library, calls one recipe, and exits. A presence is that same swap ABI made
// to LIVE: it stays running, observes, and hot-loads new recipe libraries as
// siblings mint them onto its work channel -- without ever restarting.
//
// The entry stays the only fixed surface. It owns just three things: the tick,
// the OS loader (LoadLibrary/dlopen), and a directory it watches. ALL policy
// (which mint to pick up, consent to share, authenticity to accept) lives above
// it in Form (form/form-stdlib/presence-loop.fk), proven four-way. This host is
// pure mechanism: a job appears -> the named recipe goes native and is called
// -> the result is recorded -> the handle stays resident, callable, alive.
//
// Work directory layout (all files are plain text / native libraries):
//   <dir>/queue/<name>.job   one job: lines  dll=<path>  symbol=<sym>  arg=<i64>
//   <dir>/queue/<name>.done  a job after it has been loaded and called (renamed)
//   <dir>/out.log            append-only receipt: one line per tick event
//   <dir>/stop               sentinel: when it appears, the presence rests (exit 0)
//
// Env (all optional): FORM_PRESENCE_DIR, FORM_PRESENCE_TICKS (max ticks before
// idle-exit, default 600), FORM_PRESENCE_POLL_MS (default 50),
// FORM_PRESENCE_HEARTBEAT (observe every N idle ticks, default 20).

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define FORM_CALL __cdecl
typedef HMODULE form_lib_handle;
static form_lib_handle form_load_library(const char *p) { return LoadLibraryA(p); }
static void *form_load_symbol(form_lib_handle l, const char *s) { return (void *)(uintptr_t)GetProcAddress(l, s); }
static void form_sleep_ms(int ms) { Sleep((DWORD)ms); }
static const char *form_loader_name(void) { return "LoadLibraryA/GetProcAddress"; }
#else
#include <dlfcn.h>
#include <time.h>
#include <dirent.h>
#define FORM_CALL
typedef void *form_lib_handle;
static form_lib_handle form_load_library(const char *p) { return dlopen(p, RTLD_NOW | RTLD_LOCAL); }
static void *form_load_symbol(form_lib_handle l, const char *s) { return dlsym(l, s); }
static void form_sleep_ms(int ms) { struct timespec ts; ts.tv_sec = ms / 1000; ts.tv_nsec = (long)(ms % 1000) * 1000000L; nanosleep(&ts, NULL); }
static const char *form_loader_name(void) { return "dlopen/dlsym"; }
#endif

typedef int64_t(FORM_CALL *form_i64_entry)(int64_t);

#if defined(_WIN32)
#define FORM_POPEN _popen
#define FORM_PCLOSE _pclose
#else
#define FORM_POPEN popen
#define FORM_PCLOSE pclose
#endif

static const char *env_or(const char *name, const char *fallback) {
    const char *v = getenv(name);
    return (v && v[0]) ? v : fallback;
}

static int file_exists(const char *path) {
    FILE *f = fopen(path, "rb");
    if (f) { fclose(f); return 1; }
    return 0;
}

static void log_line(const char *dir, const char *line) {
    char path[1024];
    snprintf(path, sizeof(path), "%s/out.log", dir);
    FILE *f = fopen(path, "ab");
    if (!f) return;
    fputs(line, f);
    fputc('\n', f);
    fclose(f);
}

// Read a <dir>/queue/<name>.job file. A job is one of two kinds:
//   native:  dll=<path>  symbol=<sym>  arg=<i64>   -> dlopen + call (hot recipe)
//   walk:    cmd=<command-line>                    -> run it, record its stdout
// The walk kind lets a running presence integrate RICH recipes (HTTP, ML) the
// fourth-arm native lane cannot lower yet, by walking them on the kernel.
static int read_job(const char *jobpath, char *dll, size_t dlln, char *sym, size_t symn, long long *arg, char *cmd, size_t cmdn) {
    FILE *f = fopen(jobpath, "rb");
    if (!f) return 0;
    char buf[4096];
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    buf[n] = '\0';
    dll[0] = sym[0] = cmd[0] = '\0';
    *arg = 0;
    char *line = strtok(buf, "\r\n");
    while (line) {
        if (strncmp(line, "dll=", 4) == 0) { strncpy(dll, line + 4, dlln - 1); dll[dlln - 1] = '\0'; }
        else if (strncmp(line, "symbol=", 7) == 0) { strncpy(sym, line + 7, symn - 1); sym[symn - 1] = '\0'; }
        else if (strncmp(line, "arg=", 4) == 0) { *arg = strtoll(line + 4, NULL, 10); }
        else if (strncmp(line, "cmd=", 4) == 0) { strncpy(cmd, line + 4, cmdn - 1); cmd[cmdn - 1] = '\0'; }
        line = strtok(NULL, "\r\n");
    }
    if (sym[0] == '\0') { strncpy(sym, "recipe", symn - 1); sym[symn - 1] = '\0'; }
    return dll[0] != '\0' || cmd[0] != '\0';
}

// Walk a rich recipe by running the kernel command and recording its first line
// of stdout — the served value. The presence integrates the part while running.
static int run_cmd_job(const char *dir, long tick, const char *name, const char *cmd) {
    FILE *p = FORM_POPEN(cmd, "r");
    char line[2048];
    if (!p) {
        snprintf(line, sizeof(line), "tick=%ld event=walk-failed job=%s", tick, name);
        log_line(dir, line);
        return 0;
    }
    char out[1024];
    out[0] = '\0';
    if (fgets(out, sizeof(out), p)) {
        size_t L = strlen(out);
        while (L > 0 && (out[L - 1] == '\n' || out[L - 1] == '\r')) { out[--L] = '\0'; }
    }
    char drain[1024];
    while (fgets(drain, sizeof(drain), p)) { /* consume the rest */ }
    FORM_PCLOSE(p);
    snprintf(line, sizeof(line), "tick=%ld event=served job=%s result=%s", tick, name, out);
    log_line(dir, line);
    return 1;
}

// Load the recipe library, resolve the symbol, call it, record the receipt.
// The handle is intentionally kept resident: the recipe stays callable, the way
// a picked-up capability stays available to a running presence.
static int run_job(const char *dir, long tick, const char *name, const char *jobpath) {
    char dll[1024], sym[256], cmd[1536];
    long long arg = 0;
    if (!read_job(jobpath, dll, sizeof(dll), sym, sizeof(sym), &arg, cmd, sizeof(cmd))) return 0;
    if (cmd[0] != '\0') return run_cmd_job(dir, tick, name, cmd);

    form_lib_handle lib = form_load_library(dll);
    char line[2048];
    if (!lib) {
        snprintf(line, sizeof(line), "tick=%ld event=load-failed job=%s dll=%s", tick, name, dll);
        log_line(dir, line);
        return 0;
    }
    void *proc = form_load_symbol(lib, sym);
    if (!proc) {
        snprintf(line, sizeof(line), "tick=%ld event=resolve-failed job=%s symbol=%s", tick, name, sym);
        log_line(dir, line);
        return 0;
    }
    form_i64_entry entry = (form_i64_entry)(uintptr_t)proc;
    long long result = (long long)entry((int64_t)arg);
    snprintf(line, sizeof(line), "tick=%ld event=loaded job=%s symbol=%s arg=%lld result=%lld loader=%s",
             tick, name, sym, arg, result, form_loader_name());
    log_line(dir, line);
    return 1;
}

// Scan <dir>/queue for *.job files; load each; rename it to *.done so the same
// mint is never re-run. Returns how many jobs were processed this tick.
#if defined(_WIN32)
static int scan_queue(const char *dir, long tick) {
    char glob[1024];
    snprintf(glob, sizeof(glob), "%s/queue/*.job", dir);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(glob, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    int done = 0;
    do {
        char jobpath[1280], donepath[1408];
        snprintf(jobpath, sizeof(jobpath), "%s/queue/%s", dir, fd.cFileName);
        snprintf(donepath, sizeof(donepath), "%s.done", jobpath);
        run_job(dir, tick, fd.cFileName, jobpath);
        MoveFileExA(jobpath, donepath, MOVEFILE_REPLACE_EXISTING);
        done++;
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    return done;
}
#else
static int has_suffix(const char *s, const char *suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    return ls >= lf && strcmp(s + ls - lf, suf) == 0;
}
static int scan_queue(const char *dir, long tick) {
    char qdir[1024];
    snprintf(qdir, sizeof(qdir), "%s/queue", dir);
    DIR *d = opendir(qdir);
    if (!d) return 0;
    int done = 0;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!has_suffix(e->d_name, ".job")) continue;
        char jobpath[1280], donepath[1408];
        snprintf(jobpath, sizeof(jobpath), "%s/%s", qdir, e->d_name);
        snprintf(donepath, sizeof(donepath), "%s.done", jobpath);
        run_job(dir, tick, e->d_name, jobpath);
        rename(jobpath, donepath);
        done++;
    }
    closedir(d);
    return done;
}
#endif

int main(int argc, char **argv) {
    const char *dir = (argc > 1 && argv[1][0]) ? argv[1] : env_or("FORM_PRESENCE_DIR", ".");
    long max_ticks = strtol(env_or("FORM_PRESENCE_TICKS", "600"), NULL, 10);
    int poll_ms = (int)strtol(env_or("FORM_PRESENCE_POLL_MS", "50"), NULL, 10);
    long heartbeat = strtol(env_or("FORM_PRESENCE_HEARTBEAT", "20"), NULL, 10);

    char stoppath[1024], line[256];
    snprintf(stoppath, sizeof(stoppath), "%s/stop", dir);

    snprintf(line, sizeof(line), "tick=0 event=awake dir=%s loader=%s", dir, form_loader_name());
    log_line(dir, line);

    for (long tick = 1; tick <= max_ticks; tick++) {
        if (file_exists(stoppath)) {
            snprintf(line, sizeof(line), "tick=%ld event=rest", tick);
            log_line(dir, line);
            return 0;
        }
        int processed = scan_queue(dir, tick);
        if (processed == 0 && heartbeat > 0 && (tick % heartbeat) == 0) {
            // just be: observe, breathe, stay present
            snprintf(line, sizeof(line), "tick=%ld event=heartbeat", tick);
            log_line(dir, line);
        }
        form_sleep_ms(poll_ms);
    }
    snprintf(line, sizeof(line), "tick=%ld event=idle-exit", max_ticks);
    log_line(dir, line);
    return 0;
}

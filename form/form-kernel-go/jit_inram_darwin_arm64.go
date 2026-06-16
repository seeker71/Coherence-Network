//go:build darwin && arm64 && cgo

// jit_inram_darwin_arm64.go — the in-RAM JIT executor: run a Form-emitted
// arm64 leaf image (from lo-compile-fn) IN-PROCESS, with zero `go build`,
// zero plugin .so, and a ~20-byte image instead of a 4.8MB Go plugin.
//
// This is the north-star JIT backend the Go-plugin path (jit.go) composts
// toward for the pure-i64 leaf subset: lo-compile-fn IS the executable
// backend, so the same recipe that proves four-way (Go/Rust/TS/fkwu) is the
// one that runs natively here. No parallel emitter — one engine.
//
// Apple Silicon enforces W^X: a page is never writable and executable at the
// same instant. MAP_JIT pages are the sanctioned exception — allocated once,
// then toggled per-thread between writable and executable via
// pthread_jit_write_protect_np. We write the image under write-protect-off,
// flip to executable, clear the i-cache for the range, call it as
// int64 f(int64), and unmap. The toggle is a libsystem call, so this file is
// cgo + darwin/arm64 only; every other target uses the no-op stub
// (jit_inram_other.go) and Form callers fall back to the Go-plugin path.
//
// Two host-native doors live here, both Form-callable:
//   • `jit_leaf_inram` (image, arg) — run an arm64 leaf image IN-RAM via MAP_JIT
//     (ephemeral, this process).
//   • `dylib_call` (path, sym, arg) — dlopen a DURABLE recipe binary (a Mach-O
//     dylib that form-macho emits + `ld -dylib` signs), dlsym the recipe symbol,
//     and call it. The dylib carries ONLY the recipe (~16KB vs the 4.8MB Go
//     plugin); it survives process restarts, so it is the on-disk counterpart
//     to the in-RAM path — the durable, content-addressable JIT cache.

package main

/*
#cgo LDFLAGS: -ldl
#include <sys/mman.h>
#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <dlfcn.h>

// form_run_leaf — map a MAP_JIT page, write the image while jit-write-protect
// is off, flip to executable, clear the instruction cache, call f(arg), unmap.
// *ok is 0 on mmap refusal (the result is then meaningless), 1 on a real call.
static long form_run_leaf(unsigned char *code, int n, long arg, int *ok) {
    *ok = 0;
    if (n <= 0 || n > 4096) return 0;
    void *mem = mmap(NULL, 4096, PROT_READ | PROT_WRITE | PROT_EXEC,
                     MAP_PRIVATE | MAP_ANON | MAP_JIT, -1, 0);
    if (mem == MAP_FAILED) return 0;
    pthread_jit_write_protect_np(0);            // page writable on this thread
    memcpy(mem, code, n);
    pthread_jit_write_protect_np(1);            // page executable on this thread
    __builtin___clear_cache((char *)mem, (char *)mem + n);
    long (*fn)(long) = (long (*)(long))mem;
    long r = fn(arg);
    munmap(mem, 4096);
    *ok = 1;
    return r;
}

// form_dylib_call — dlopen a recipe dylib, dlsym the symbol, call it as
// long f(long), dlclose. *ok is 0 if the library or symbol could not be
// resolved (the result is then meaningless), 1 on a real call.
static long form_dylib_call(const char *path, const char *sym, long arg, int *ok) {
    *ok = 0;
    void *h = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!h) return 0;
    long (*fn)(long) = (long (*)(long))dlsym(h, sym);
    if (!fn) { dlclose(h); return 0; }
    long r = fn(arg);
    dlclose(h);
    *ok = 1;
    return r;
}
*/
import "C"
import "unsafe"

// runLeafInRAM — execute an arm64 leaf image as int64 f(int64) in-process.
// Returns (result, true) on a real call, (0, false) if the input is out of
// range or the JIT page could not be mapped.
func runLeafInRAM(code []byte, arg int64) (int64, bool) {
	if len(code) == 0 || len(code) > 4096 {
		return 0, false
	}
	var ok C.int
	r := C.form_run_leaf(
		(*C.uchar)(unsafe.Pointer(&code[0])),
		C.int(len(code)),
		C.long(arg),
		&ok,
	)
	return int64(r), ok != 0
}

// dylibCall — load a recipe dylib at path, resolve sym, call it as int64
// f(int64). Returns (result, true) on a real call, (0, false) if the library
// or symbol could not be resolved.
func dylibCall(path, sym string, arg int64) (int64, bool) {
	cpath := C.CString(path)
	defer C.free(unsafe.Pointer(cpath))
	csym := C.CString(sym)
	defer C.free(unsafe.Pointer(csym))
	var ok C.int
	r := C.form_dylib_call(cpath, csym, C.long(arg), &ok)
	return int64(r), ok != 0
}

// registerInRAMJIT — bind the host-native execution doors. `jit_leaf_inram`
// runs an image in-RAM; `dylib_call` loads a durable recipe dylib and calls it.
// Present only where the host can execute them; the stub registers nothing and
// Form callers fall back to the Go-plugin path or the walker.
func (k *Kernel) registerInRAMJIT() {
	k.registerNative("jit_leaf_inram", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 2 || args[0].Kind != VList || args[1].Kind != VInt {
			return Value{Kind: VNull}
		}
		code := make([]byte, len(args[0].List))
		for i, b := range args[0].List {
			if b.Kind != VInt || b.Int < 0 || b.Int > 255 {
				return Value{Kind: VNull}
			}
			code[i] = byte(b.Int)
		}
		r, ok := runLeafInRAM(code, args[1].Int)
		if !ok {
			return Value{Kind: VNull}
		}
		return Value{Kind: VInt, Int: r}
	})
	// dylib_call (path, sym, arg) — dlopen a recipe binary and call its symbol.
	k.registerNative("dylib_call", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 3 || args[0].Kind != VStr || args[1].Kind != VStr || args[2].Kind != VInt {
			return Value{Kind: VNull}
		}
		r, ok := dylibCall(args[0].Str, args[1].Str, args[2].Int)
		if !ok {
			return Value{Kind: VNull}
		}
		return Value{Kind: VInt, Int: r}
	})
}

//go:build windows

// jit_inram_windows.go - Windows dynamic recipe loader.
//
// Windows does not share the Darwin MAP_JIT in-RAM path, but it can load a
// durable recipe DLL. The Form side emits a PE/COFF x64 object; lld-link/link is
// the host linker carrier; this file keeps LoadLibrary/GetProcAddress as the
// small runtime carrier and exposes the same Form-level dylib_call surface used
// by the macOS recipe-dylib floor.

package main

import "syscall"

func dylibCall(path, sym string, arg int64) (int64, bool) {
	dll, err := syscall.LoadDLL(path)
	if err != nil {
		return 0, false
	}
	defer dll.Release()

	proc, err := dll.FindProc(sym)
	if err != nil {
		return 0, false
	}

	r, _, _ := proc.Call(uintptr(arg))
	return int64(r), true
}

func (k *Kernel) registerInRAMJIT() {
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

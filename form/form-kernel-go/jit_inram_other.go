//go:build !(darwin && arm64 && cgo)

// jit_inram_other.go — the in-RAM JIT executor is darwin/arm64 + cgo only
// (it needs MAP_JIT + pthread_jit_write_protect_np). On every other target the
// `jit_leaf_inram` native is simply absent: Form callers fall back to the
// Go-plugin JIT path (jit.go) or the walker — same answer, no native fast lane.
// This keeps the kernel pure-Go and cross-buildable on Linux (CI, the VPS).

package main

// registerInRAMJIT — no-op: no in-process arm64 executor on this target.
func (k *Kernel) registerInRAMJIT() {}

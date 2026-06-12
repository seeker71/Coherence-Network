// jit_race.go — marks the binary as race-instrumented so JIT plugin builds
// mirror the mode (a non-race plugin can't load into a race host).

//go:build race

package main

func init() { jitHostRaceEnabled = true }

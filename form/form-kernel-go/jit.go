// jit.go — Form recipe → host-native Go via `go build -buildmode=plugin`.
//
// The shape (Urs):
//   "we want just primitives in the kernel. and form native code to
//    host native assembly using JIT to have generic cross kernel
//    functions with host native performance for channel protocol and
//    other core support"
//
// Architecture:
//
//   (jit_compile "name")
//        │  env-aware native looks up the closure under `name`
//        ▼
//   jitCompileClosureGo(k, cl)
//        │  emits Go source for cl.Params + cl.Body
//        │  writes /tmp/form-jit-XXXX/main.go
//        ▼
//   exec.Command("go", "build", "-buildmode=plugin", "-o", "plugin.so")
//        │  invokes the host's Go toolchain
//        ▼
//   plugin.Open("plugin.so")  +  plugin.Lookup("Fn")
//        │  loads the symbol as func([]int64) int64
//        ▼
//   k.jitCompiledGo[bodyKey] = fn
//        │  bodyKey content-addresses the recipe body
//        ▼
//   FNCALL closure dispatch checks the map on every call.
//
// The supported subset (the rest falls back to walker — same answer):
//   • Arithmetic int64: add, sub, mul, div, mod
//   • Comparisons: eq, ne, lt, le, gt, ge
//   • Conditionals: if / if-else
//   • Let-bindings of integer values
//   • Parameter references
//   • Recursive free-function calls (the closure's own name)
//
// Out of scope by design (refuse to compile, walker keeps running):
//   • Lists, strings, floats, closures-over-outer-state
//   • Native calls inside the compiled body
//   • Multi-type signatures beyond int64 → int64
//
// Plugin caching: keyed by the body's NodeID-tuple string ("0.2.99.42").
// Same recipe shape → same .so reused. The cache survives for the
// lifetime of the kernel process; rebuilding only happens on a fresh
// run.

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"plugin"
	"runtime"
	"strconv"
	"strings"
)

// runtimeVersionRaw — thin indirection so readHostGoVersion can be tested.
func runtimeVersionRaw() string { return runtime.Version() }

// nodeIDKey — canonical string key for a NodeID (matches the shape TS uses
// for k.jitCompiled). Used to index k.jitCompiledGo.
func nodeIDKey(n NodeID) string {
	return fmt.Sprintf("%d.%d.%d.%d", n.Pkg, n.Level, n.Type, n.Inst)
}

// readHostGoVersion — return a `go X.Y.Z` directive matching the toolchain
// that produced this kernel binary, so the plugin's go.mod can ride the
// same toolchain. Plugin ABI compatibility requires byte-identical
// toolchain across host and plugin; the runtime version is the most
// honest answer because it's baked into the binary itself. (Reading
// form-kernel-go/go.mod would only be right when the cwd is favorable,
// and would drift away from the actual toolchain over time.)
func readHostGoVersion() string {
	v := runtimeVersionRaw()
	v = strings.TrimPrefix(v, "go")
	return v
}

// goCompileScope — name resolution context during emission. Maps Form
// NameIDs to generated Go variable names. Maps recursive-self references
// to the generated Go function name.
type goCompileScope struct {
	// vars: parameter and let-binding NameID → Go identifier.
	vars map[NameID]string
	// selfName: the Form name this body is the recipe for (so recursive
	// calls resolve to the generated function). Empty when emitting at
	// the top level (no recursion needed).
	selfName  NameID
	selfFn    string
	// uid for fresh-name generation.
	uid *int
}

func newGoCompileScope(selfName NameID, selfFn string) *goCompileScope {
	n := 0
	return &goCompileScope{
		vars:     map[NameID]string{},
		selfName: selfName,
		selfFn:   selfFn,
		uid:      &n,
	}
}

func (s *goCompileScope) child() *goCompileScope {
	cp := newGoCompileScope(s.selfName, s.selfFn)
	for k, v := range s.vars {
		cp.vars[k] = v
	}
	cp.uid = s.uid
	return cp
}

func (s *goCompileScope) fresh(hint string) string {
	*s.uid++
	safe := sanitizeIdent(hint)
	if safe == "" {
		safe = "v"
	}
	return fmt.Sprintf("%s_%d", safe, *s.uid)
}

func sanitizeIdent(s string) string {
	out := strings.Builder{}
	for i, r := range s {
		if r == '_' || (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') {
			out.WriteRune(r)
			continue
		}
		if i > 0 && r >= '0' && r <= '9' {
			out.WriteRune(r)
			continue
		}
		out.WriteRune('_')
	}
	return out.String()
}

// jitCompileError — the emitter raises this when it hits a recipe shape
// it can't lower to the supported subset. The native catches it and
// returns 0 from jit_compile (honest fallback).
type jitCompileError struct {
	reason string
}

func (e *jitCompileError) Error() string { return e.reason }

func unsupported(reason string) error { return &jitCompileError{reason: reason} }

// jitCompileClosureGo — the entry point. Given a closure, emits a Go
// program that defines a function of (n int64 args) → int64, writes it
// to disk, invokes `go build -buildmode=plugin`, loads the .so, and
// returns the loaded function. Any failure surfaces as a non-nil error;
// the caller maps that to `jit_compile → 0`.
func jitCompileClosureGo(k *Kernel, cl *Closure) (func([]int64) int64, error) {
	// Closure over outer state — the emitter only handles params + the
	// closure's own recursive self-reference. Any IDENT that doesn't
	// resolve to a param surfaces as unsupported during emission.
	selfFn := "fn_self"
	scope := newGoCompileScope(cl.Name, selfFn)

	// Bind parameters to generated Go names. Use `p0, p1, ...` for clarity
	// in the generated code.
	paramNames := make([]string, len(cl.Params))
	for i, p := range cl.Params {
		gn := fmt.Sprintf("p%d", i)
		scope.vars[p] = gn
		paramNames[i] = gn
	}

	// Emit the body expression. Errors propagate out as unsupported.
	bodySrc, err := emitGoExpr(k, cl.Body, scope)
	if err != nil {
		return nil, err
	}

	// Build the full Go source. The plugin exports a single `Fn` symbol
	// with the contract: takes []int64, returns int64. We dispatch through
	// a thin shim that unpacks the slice into the recursive function's
	// arity-fixed signature.
	paramSig := strings.Builder{}
	for i := range cl.Params {
		if i > 0 {
			paramSig.WriteString(", ")
		}
		paramSig.WriteString(fmt.Sprintf("p%d int64", i))
	}

	callArgs := strings.Builder{}
	for i := range cl.Params {
		if i > 0 {
			callArgs.WriteString(", ")
		}
		callArgs.WriteString(fmt.Sprintf("args[%d]", i))
	}

	var src strings.Builder
	src.WriteString("// Generated by form-kernel-go JIT — Form recipe → Go source.\n")
	src.WriteString("// Body NodeID: " + nodeIDKey(cl.Body) + "\n")
	src.WriteString("// Closure name: " + k.nameStr(cl.Name) + "\n")
	src.WriteString("//\n")
	src.WriteString("// The recipe stays canonical truth in the Form substrate; this file is a\n")
	src.WriteString("// throwaway expression of it for one execution. Compiles to plugin.so via\n")
	src.WriteString("// `go build -buildmode=plugin`, loaded via plugin.Open + plugin.Lookup.\n\n")
	src.WriteString("package main\n\n")
	src.WriteString(fmt.Sprintf("func %s(%s) int64 {\n", selfFn, paramSig.String()))
	src.WriteString("\treturn ")
	src.WriteString(bodySrc)
	src.WriteString("\n}\n\n")
	src.WriteString("// Fn — the exported entry point. Plugin.Lookup loads this symbol.\n")
	src.WriteString(fmt.Sprintf("func Fn(args []int64) int64 {\n"))
	src.WriteString(fmt.Sprintf("\tif len(args) != %d {\n", len(cl.Params)))
	src.WriteString("\t\tpanic(\"form-jit: arity mismatch\")\n")
	src.WriteString("\t}\n")
	if len(cl.Params) == 0 {
		src.WriteString(fmt.Sprintf("\treturn %s()\n", selfFn))
	} else {
		src.WriteString(fmt.Sprintf("\treturn %s(%s)\n", selfFn, callArgs.String()))
	}
	src.WriteString("}\n")

	// Write to a temp directory, run `go build -buildmode=plugin`.
	dir, err := os.MkdirTemp("", "form-jit-")
	if err != nil {
		return nil, fmt.Errorf("mkdtemp: %w", err)
	}
	// Keep the dir for the lifetime of the kernel process — the .so is
	// mmap'd by the runtime and shouldn't be removed under it. The OS
	// reclaims /tmp on reboot; no leak in practice.
	srcPath := filepath.Join(dir, "main.go")
	if err := os.WriteFile(srcPath, []byte(src.String()), 0o644); err != nil {
		return nil, fmt.Errorf("write source: %w", err)
	}
	// Pin the plugin's go.mod to match the host kernel's module so the
	// Go toolchain selects the same compiler version. Without this, a
	// plugin built under a different toolchain (e.g. system go 1.24 vs
	// kernel's go.mod 1.26.3) triggers `runtime: no plugin module data`
	// when plugin.Open inspects the .so. The kernel's own go.mod is the
	// reference; we read it once and mirror the `go` directive.
	hostGoVersion := readHostGoVersion()
	modContents := fmt.Sprintf("module form_jit\n\ngo %s\n", hostGoVersion)
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), []byte(modContents), 0o644); err != nil {
		return nil, fmt.Errorf("write go.mod: %w", err)
	}
	soPath := filepath.Join(dir, "plugin.so")

	// Run go build with cmd.Dir = temp dir so the plugin's go.mod is the
	// one in effect (not the calling shell's). Any error (toolchain
	// missing, source rejected, plugin mode unavailable, ABI mismatch)
	// surfaces as a build failure → unsupported → walker fallback.
	cmd := exec.Command("go", "build", "-buildmode=plugin", "-o", soPath, srcPath)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GOFLAGS=") // strip user GOFLAGS that might inject -mod=vendor etc.
	if out, err := cmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("go build failed: %v\n%s", err, string(out))
	}

	p, err := plugin.Open(soPath)
	if err != nil {
		return nil, fmt.Errorf("plugin.Open: %w", err)
	}
	sym, err := p.Lookup("Fn")
	if err != nil {
		return nil, fmt.Errorf("plugin.Lookup: %w", err)
	}
	fn, ok := sym.(func([]int64) int64)
	if !ok {
		return nil, fmt.Errorf("plugin.Lookup: Fn has wrong type %T", sym)
	}
	return fn, nil
}

// emitGoExpr — recipe NodeID → Go source string. Returns an `int64`-typed
// expression. Errors propagate as unsupported when the recipe leaves the
// emitter's subset.
func emitGoExpr(k *Kernel, node NodeID, scope *goCompileScope) (string, error) {
	if node.Level == LevelTrivial {
		return emitGoTrivial(k, node)
	}
	cat := k.category(node)
	kids := k.children(node)

	switch cat.Type {
	case RBasicIdent:
		id := k.identID(node)
		if g, ok := scope.vars[id]; ok {
			return g, nil
		}
		// Self-reference is fine if it's the closure's own name; that
		// only occurs in FNCALL position though, not as a bare IDENT.
		return "", unsupported(fmt.Sprintf("jit: unbound identifier %q in body", k.nameStr(id)))

	case RBasicMath:
		return emitGoMath(k, cat.Inst, kids, scope)

	case RBasicCompare:
		return emitGoCompare(k, cat.Inst, kids, scope)

	case RBasicCond:
		return emitGoCond(k, cat.Inst, kids, scope)

	case RBasicBlock:
		return emitGoBlock(k, cat.Inst, kids, scope)

	case RBasicFnCall:
		return emitGoFnCall(k, kids, scope)

	case RBasicLogic:
		return "", unsupported("jit: logic ops not in subset")

	case RBasicList:
		return "", unsupported("jit: list construction not in subset")

	case RBasicFnDef:
		return "", unsupported("jit: nested defn not in subset")
	}
	return "", unsupported(fmt.Sprintf("jit: unsupported arm type %d", cat.Type))
}

func emitGoTrivial(k *Kernel, node NodeID) (string, error) {
	switch node.Type {
	case TrivInt:
		// Sign-extend the 32-bit instance back to int64.
		v := int64(int32(node.Inst))
		return strconv.FormatInt(v, 10), nil
	case TrivBool:
		if node.Inst != 0 {
			return "int64(1)", nil
		}
		return "int64(0)", nil
	}
	return "", unsupported(fmt.Sprintf("jit: trivial type %d not in subset", node.Type))
}

func emitGoMath(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	if len(kids) != 2 {
		return "", unsupported("jit: math expects 2 args")
	}
	a, err := emitGoExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	b, err := emitGoExpr(k, kids[1], scope)
	if err != nil {
		return "", err
	}
	var opStr string
	switch op {
	case RMathPlus:
		opStr = "+"
	case RMathMinus:
		opStr = "-"
	case RMathMultiply:
		opStr = "*"
	case RMathDivide:
		opStr = "/"
	case RMathModulo:
		opStr = "%"
	default:
		return "", unsupported(fmt.Sprintf("jit: math op %d", op))
	}
	return fmt.Sprintf("(%s %s %s)", a, opStr, b), nil
}

func emitGoCompare(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	if len(kids) != 2 {
		return "", unsupported("jit: compare expects 2 args")
	}
	a, err := emitGoExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	b, err := emitGoExpr(k, kids[1], scope)
	if err != nil {
		return "", err
	}
	var opStr string
	switch op {
	case RCompareEq:
		opStr = "=="
	case RCompareNe:
		opStr = "!="
	case RCompareLt:
		opStr = "<"
	case RCompareLe:
		opStr = "<="
	case RCompareGt:
		opStr = ">"
	case RCompareGe:
		opStr = ">="
	default:
		return "", unsupported(fmt.Sprintf("jit: compare op %d", op))
	}
	// Form's compare arm returns a bool-shaped int64 (1 / 0) when used in
	// arithmetic / conditional position. Walker keeps it as a VBool; the
	// JIT path lowers it to int64 (1/0) so it composes cleanly with the
	// surrounding integer expressions. The COND emitter knows to read it
	// as truthy when != 0.
	return fmt.Sprintf("(func() int64 { if (%s %s %s) { return 1 }; return 0 }())", a, opStr, b), nil
}

func emitGoCond(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	if len(kids) < 2 {
		return "", unsupported("jit: cond expects at least 2 kids")
	}
	cond, err := emitGoExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	then, err := emitGoExpr(k, kids[1], scope)
	if err != nil {
		return "", err
	}
	var els string
	if op == RCondIfThenElse && len(kids) >= 3 {
		var elsErr error
		els, elsErr = emitGoExpr(k, kids[2], scope)
		if elsErr != nil {
			return "", elsErr
		}
	} else {
		els = "int64(0)" // if-without-else returns null in walker; JIT subset returns 0
	}
	// Go has no ternary; use an IIFE.
	return fmt.Sprintf("(func() int64 { if (%s) != 0 { return (%s) }; return (%s) }())", cond, then, els), nil
}

func emitGoBlock(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	switch op {
	case RBlockLet:
		if len(kids) != 2 {
			return "", unsupported("jit: let expects 2 kids")
		}
		nameNode := kids[0]
		if nameNode.Level != LevelTrivial || nameNode.Type != TrivString {
			return "", unsupported("jit: let name must be string trivial")
		}
		valSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		nid := NameID(nameNode.Inst)
		varName := scope.fresh(fmt.Sprintf("let_%s", k.nameStr(nid)))
		scope.vars[nid] = varName
		// Block.LET evaluates to the bound value (per walker semantics).
		return fmt.Sprintf("(func() int64 { %s := int64(%s); _ = %s; return %s }())", varName, valSrc, varName, varName), nil
	case RBlockDo, RBlockSequence:
		// Walker semantics: evaluate each child, return the last. For a
		// pure JIT, we need to thread let bindings across siblings. The
		// safest shape is an IIFE with sequential statements; we wrap the
		// last as a `return` expression. Bindings introduced by inner LET
		// blocks won't leak (they live in their own IIFEs), so block-do
		// at the top level is only useful when it contains a single expr.
		if len(kids) == 0 {
			return "int64(0)", nil
		}
		if len(kids) == 1 {
			return emitGoExpr(k, kids[0], scope)
		}
		// Multi-child block — emit as IIFE with statements. Each
		// intermediate result is discarded.
		var b strings.Builder
		b.WriteString("(func() int64 {\n")
		child := scope.child()
		for i, c := range kids {
			isLast := i == len(kids)-1
			expr, err := emitGoExpr(k, c, child)
			if err != nil {
				return "", err
			}
			if isLast {
				b.WriteString(fmt.Sprintf("\treturn (%s)\n", expr))
			} else {
				b.WriteString(fmt.Sprintf("\t_ = (%s)\n", expr))
			}
		}
		b.WriteString("}())")
		return b.String(), nil
	}
	return "", unsupported(fmt.Sprintf("jit: block op %d not in subset", op))
}

func emitGoFnCall(k *Kernel, kids []NodeID, scope *goCompileScope) (string, error) {
	if len(kids) < 1 {
		return "", unsupported("jit: fncall has no callee")
	}
	callee := kids[0]
	var nameID NameID
	if callee.Level == LevelTrivial && callee.Type == TrivString {
		nameID = NameID(callee.Inst)
	} else {
		cat := k.category(callee)
		if cat.Type == RBasicIdent {
			nameID = k.identID(callee)
		} else {
			return "", unsupported("jit: dynamic callee not in subset")
		}
	}

	// Math/Compare/Cond may also appear as fncalls in the parser sugar
	// (e.g. `(add a b)` is RBasic.MATH in the body, but `(eq n 0)` might
	// be too — the recipe is already lowered). At this point the only
	// fncalls we should see are user-defined Form functions (recursive
	// self) or natives. Natives we don't support in the compiled body —
	// fall back to walker.
	name := k.nameStr(nameID)
	// Recursive self-call?
	if nameID == scope.selfName {
		args := make([]string, 0, len(kids)-1)
		for i := 1; i < len(kids); i++ {
			a, err := emitGoExpr(k, kids[i], scope)
			if err != nil {
				return "", err
			}
			args = append(args, fmt.Sprintf("int64(%s)", a))
		}
		return fmt.Sprintf("%s(%s)", scope.selfFn, strings.Join(args, ", ")), nil
	}
	// Check if it's a math/compare/cond operator name (the parser may
	// have produced a generic FNCALL with these names if the body uses
	// the s-expression form). Lower to the corresponding operator.
	switch name {
	case "add", "sub", "mul", "div", "mod":
		op := map[string]uint32{
			"add": RMathPlus, "sub": RMathMinus, "mul": RMathMultiply,
			"div": RMathDivide, "mod": RMathModulo,
		}[name]
		return emitGoMath(k, op, kids[1:], scope)
	case "eq", "ne", "lt", "le", "gt", "ge":
		op := map[string]uint32{
			"eq": RCompareEq, "ne": RCompareNe, "lt": RCompareLt,
			"le": RCompareLe, "gt": RCompareGt, "ge": RCompareGe,
		}[name]
		return emitGoCompare(k, op, kids[1:], scope)
	case "if":
		// (if cond then) or (if cond then else)
		op := RCondIfThen
		if len(kids[1:]) >= 3 {
			op = RCondIfThenElse
		}
		return emitGoCond(k, op, kids[1:], scope)
	}
	return "", unsupported(fmt.Sprintf("jit: unsupported call %q (only self-recursion + arithmetic primitives in subset)", name))
}

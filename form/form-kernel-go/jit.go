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

	"form-kernel-go/jitabi"
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

func formKernelModuleDir() string {
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		return "."
	}
	return filepath.Dir(file)
}

type goJITABI string

const (
	goJITABIi64   goJITABI = "i64"
	goJITABIf64   goJITABI = "f64"
	goJITABIValue goJITABI = "value"
)

type goCompileScope struct {
	vars     map[NameID]string
	selfName NameID
	selfFn   string
	uid      *int
	abi      goJITABI
	env      *Frame
	plan     *goCompilePlan
}

type goCompilePlan struct {
	abi       goJITABI
	helpers   map[NameID]string
	emitted   map[NameID]bool
	emitting  map[NameID]bool
	helperSrc strings.Builder
}

func newGoCompilePlan(abi goJITABI) *goCompilePlan {
	return &goCompilePlan{
		abi:      abi,
		helpers:  map[NameID]string{},
		emitted:  map[NameID]bool{},
		emitting: map[NameID]bool{},
	}
}

func newGoCompileScope(selfName NameID, selfFn string, abi goJITABI, env *Frame, plan *goCompilePlan) *goCompileScope {
	n := 0
	if plan == nil {
		plan = newGoCompilePlan(abi)
	}
	return &goCompileScope{
		vars:     map[NameID]string{},
		selfName: selfName,
		selfFn:   selfFn,
		uid:      &n,
		abi:      abi,
		env:      env,
		plan:     plan,
	}
}

func (s *goCompileScope) child() *goCompileScope {
	cp := newGoCompileScope(s.selfName, s.selfFn, s.abi, s.env, s.plan)
	for k, v := range s.vars {
		cp.vars[k] = v
	}
	cp.uid = s.uid
	return cp
}

func (s *goCompileScope) scalarType() string {
	if s.abi == goJITABIValue {
		return "jitabi.Value"
	}
	if s.abi == goJITABIf64 {
		return "float64"
	}
	return "int64"
}

func (s *goCompileScope) scalarZero() string {
	if s.abi == goJITABIValue {
		return "jitabi.Null()"
	}
	if s.abi == goJITABIf64 {
		return "float64(0)"
	}
	return "int64(0)"
}

func (s *goCompileScope) scalarOne() string {
	if s.abi == goJITABIValue {
		return "jitabi.Int(1)"
	}
	if s.abi == goJITABIf64 {
		return "float64(1)"
	}
	return "int64(1)"
}

func (s *goCompileScope) cast(expr string) string {
	if s.abi == goJITABIValue {
		return expr
	}
	return fmt.Sprintf("%s(%s)", s.scalarType(), expr)
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

type jitCompileError struct {
	reason string
}

func (e *jitCompileError) Error() string { return e.reason }

func unsupported(reason string) error { return &jitCompileError{reason: reason} }

func jitCompileClosureGo(k *Kernel, cl *Closure) (*GoJITCompiled, error) {
	type abiBuild struct {
		abi string
		src string
		err error
	}
	builds := []abiBuild{}
	firstErr := error(nil)
	valueErr := error(nil)
	abis := []goJITABI{goJITABIi64, goJITABIf64, goJITABIValue}
	if jitRecipeNeedsValueABI(k, cl.Body) {
		abis = []goJITABI{goJITABIValue}
	}
	for _, abi := range abis {
		src, err := emitGoPluginABI(k, cl, abi)
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			if abi == goJITABIValue {
				valueErr = err
			}
			continue
		}
		builds = append(builds, abiBuild{abi: string(abi), src: src})
	}
	if len(builds) == 0 {
		if valueErr != nil {
			return nil, valueErr
		}
		if firstErr == nil {
			firstErr = unsupported("jit: no ABI emitted")
		}
		return nil, firstErr
	}

	var src strings.Builder
	src.WriteString("// Generated by form-kernel-go JIT — Form recipe → Go source.\n")
	src.WriteString("// Body NodeID: " + nodeIDKey(cl.Body) + "\n")
	src.WriteString("// Closure name: " + k.nameStr(cl.Name) + "\n\n")
	src.WriteString("package main\n\n")
	for _, build := range builds {
		if build.abi == string(goJITABIValue) {
			src.WriteString("import \"form-kernel-go/jitabi\"\n\n")
			break
		}
	}
	for _, build := range builds {
		src.WriteString(build.src)
		src.WriteString("\n")
	}

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
	modContents := fmt.Sprintf(
		"module form_jit\n\ngo %s\n\nrequire form-kernel-go v0.0.0\nreplace form-kernel-go => %s\n",
		hostGoVersion,
		formKernelModuleDir(),
	)
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
	out := &GoJITCompiled{}
	for _, build := range builds {
		switch build.abi {
		case string(goJITABIi64):
			sym, err := p.Lookup("FnI64")
			if err != nil {
				return nil, fmt.Errorf("plugin.Lookup FnI64: %w", err)
			}
			fn, ok := sym.(func([]int64) int64)
			if !ok {
				return nil, fmt.Errorf("plugin.Lookup: FnI64 has wrong type %T", sym)
			}
			out.I64 = fn
		case string(goJITABIf64):
			sym, err := p.Lookup("FnF64")
			if err != nil {
				return nil, fmt.Errorf("plugin.Lookup FnF64: %w", err)
			}
			fn, ok := sym.(func([]float64) float64)
			if !ok {
				return nil, fmt.Errorf("plugin.Lookup: FnF64 has wrong type %T", sym)
			}
			out.F64 = fn
		case string(goJITABIValue):
			sym, err := p.Lookup("FnValue")
			if err != nil {
				return nil, fmt.Errorf("plugin.Lookup FnValue: %w", err)
			}
			fn, ok := sym.(func([]jitabi.Value) jitabi.Value)
			if !ok {
				return nil, fmt.Errorf("plugin.Lookup: FnValue has wrong type %T", sym)
			}
			out.Value = fn
		}
	}
	return out, nil
}

func emitGoPluginABI(k *Kernel, cl *Closure, abi goJITABI) (string, error) {
	selfFn := "fn_" + string(abi)
	plan := newGoCompilePlan(abi)
	plan.helpers[cl.Name] = selfFn
	plan.emitted[cl.Name] = true
	scope := newGoCompileScope(cl.Name, selfFn, abi, cl.Env, plan)
	for i, p := range cl.Params {
		scope.vars[p] = fmt.Sprintf("p%d", i)
	}
	bodySrc, err := emitGoExpr(k, cl.Body, scope)
	if err != nil {
		return "", err
	}
	scalar := scope.scalarType()
	exported := "FnI64"
	if abi == goJITABIf64 {
		exported = "FnF64"
	} else if abi == goJITABIValue {
		exported = "FnValue"
	}
	var paramSig strings.Builder
	var callArgs strings.Builder
	for i := range cl.Params {
		if i > 0 {
			paramSig.WriteString(", ")
			callArgs.WriteString(", ")
		}
		paramSig.WriteString(fmt.Sprintf("p%d %s", i, scalar))
		callArgs.WriteString(fmt.Sprintf("args[%d]", i))
	}
	var src strings.Builder
	src.WriteString(plan.helperSrc.String())
	src.WriteString(fmt.Sprintf("func %s(%s) %s {\n", selfFn, paramSig.String(), scalar))
	src.WriteString("\treturn ")
	src.WriteString(scope.cast(bodySrc))
	src.WriteString("\n}\n\n")
	src.WriteString(fmt.Sprintf("func %s(args []%s) %s {\n", exported, scalar, scalar))
	src.WriteString(fmt.Sprintf("\tif len(args) != %d { panic(\"form-jit: arity mismatch\") }\n", len(cl.Params)))
	if len(cl.Params) == 0 {
		src.WriteString(fmt.Sprintf("\treturn %s()\n", selfFn))
	} else {
		src.WriteString(fmt.Sprintf("\treturn %s(%s)\n", selfFn, callArgs.String()))
	}
	src.WriteString("}\n")
	return src.String(), nil
}

func emitGoExpr(k *Kernel, node NodeID, scope *goCompileScope) (string, error) {
	if node.Level == LevelTrivial {
		return emitGoTrivial(k, node, scope)
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
		if len(kids) == 0 {
			if scope.abi == goJITABIValue {
				return "jitabi.List()", nil
			}
			return "[]" + scope.scalarType() + "{}", nil
		}
		var elems []string
		for _, kid := range kids {
			s, err := emitGoExpr(k, kid, scope)
			if err != nil {
				return "", err
			}
			if scope.abi == goJITABIValue {
				elems = append(elems, s)
			} else {
				elems = append(elems, scope.cast(s))
			}
		}
		if scope.abi == goJITABIValue {
			return "jitabi.List(" + strings.Join(elems, ", ") + ")", nil
		}
		return "[]" + scope.scalarType() + "{" + strings.Join(elems, ", ") + "}", nil

	case RBasicFnDef:
		return "", unsupported("jit: nested defn not in subset")
	}
	return "", unsupported(fmt.Sprintf("jit: unsupported arm type %d", cat.Type))
}

func emitGoTrivial(k *Kernel, node NodeID, scope *goCompileScope) (string, error) {
	switch node.Type {
	case TrivInt:
		v := int64(int32(node.Inst))
		if scope.abi == goJITABIValue {
			return fmt.Sprintf("jitabi.Int(%s)", strconv.FormatInt(v, 10)), nil
		}
		if scope.abi == goJITABIf64 {
			return fmt.Sprintf("float64(%s)", strconv.FormatInt(v, 10)), nil
		}
		return fmt.Sprintf("int64(%s)", strconv.FormatInt(v, 10)), nil
	case TrivBool:
		if scope.abi == goJITABIValue {
			return fmt.Sprintf("jitabi.Bool(%t)", node.Inst != 0), nil
		}
		if node.Inst != 0 {
			return scope.scalarOne(), nil
		}
		return scope.scalarZero(), nil
	case TrivString:
		if scope.abi == goJITABIValue {
			return "jitabi.Str(" + strconv.Quote(k.nameStr(NameID(node.Inst))) + ")", nil
		}
		return "", unsupported("jit: string literal requires value ABI")
	case TrivFloat32:
		if scope.abi == goJITABIValue {
			return fmt.Sprintf("jitabi.Float(%s)", strconv.FormatFloat(float64(k.decodeFloat32(node.Inst)), 'g', -1, 64)), nil
		}
		if scope.abi != goJITABIf64 {
			return "", unsupported("jit: float literal requires f64 ABI")
		}
		return strconv.FormatFloat(float64(k.decodeFloat32(node.Inst)), 'g', -1, 64), nil
	case TrivFloat64:
		if scope.abi == goJITABIValue {
			return fmt.Sprintf("jitabi.Float(%s)", strconv.FormatFloat(k.decodeFloat64(node.Inst), 'g', -1, 64)), nil
		}
		if scope.abi != goJITABIf64 {
			return "", unsupported("jit: float literal requires f64 ABI")
		}
		return strconv.FormatFloat(k.decodeFloat64(node.Inst), 'g', -1, 64), nil
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
	var valueOp string
	switch op {
	case RMathPlus:
		opStr = "+"
		valueOp = "jitabi.Add"
	case RMathMinus:
		opStr = "-"
		valueOp = "jitabi.Sub"
	case RMathMultiply:
		opStr = "*"
		valueOp = "jitabi.Mul"
	case RMathDivide:
		opStr = "/"
		valueOp = "jitabi.Div"
	case RMathModulo:
		opStr = "%"
		valueOp = "jitabi.Mod"
	default:
		return "", unsupported(fmt.Sprintf("jit: math op %d", op))
	}
	if scope.abi == goJITABIValue {
		return fmt.Sprintf("%s(%s, %s)", valueOp, a, b), nil
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
	var valueOp string
	switch op {
	case RCompareEq:
		opStr = "=="
		valueOp = "jitabi.Eq"
	case RCompareNe:
		opStr = "!="
		valueOp = "jitabi.Ne"
	case RCompareLt:
		opStr = "<"
		valueOp = "jitabi.Lt"
	case RCompareLe:
		opStr = "<="
		valueOp = "jitabi.Le"
	case RCompareGt:
		opStr = ">"
		valueOp = "jitabi.Gt"
	case RCompareGe:
		opStr = ">="
		valueOp = "jitabi.Ge"
	default:
		return "", unsupported(fmt.Sprintf("jit: compare op %d", op))
	}
	if scope.abi == goJITABIValue {
		return fmt.Sprintf("%s(%s, %s)", valueOp, a, b), nil
	}
	scalar := scope.scalarType()
	return fmt.Sprintf("(func() %s { if (%s %s %s) { return %s }; return %s }())",
		scalar, a, opStr, b, scope.scalarOne(), scope.scalarZero()), nil
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
		els = scope.scalarZero() // if-without-else returns null in walker; JIT subset returns 0
	}
	scalar := scope.scalarType()
	if scope.abi == goJITABIValue {
		return fmt.Sprintf("(func() %s { if jitabi.Truthy(%s) { return %s }; return %s }())",
			scalar, cond, then, els), nil
	}
	return fmt.Sprintf("(func() %s { if (%s) != 0 { return %s }; return %s }())",
		scalar, cond, scope.cast(then), scope.cast(els)), nil
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
		return fmt.Sprintf("(func() %s { %s := %s; _ = %s; return %s }())",
			scope.scalarType(), varName, scope.cast(valSrc), varName, varName), nil
	case RBlockDo, RBlockSequence:
		// Walker semantics: evaluate each child, return the last. For a
		// pure JIT, we need to thread let bindings across siblings. The
		// safest shape is an IIFE with sequential statements; we wrap the
		// last as a `return` expression. Bindings introduced by inner LET
		// blocks won't leak (they live in their own IIFEs), so block-do
		// at the top level is only useful when it contains a single expr.
		if len(kids) == 0 {
			return scope.scalarZero(), nil
		}
		if len(kids) == 1 {
			return emitGoExpr(k, kids[0], scope)
		}
		var b strings.Builder
		b.WriteString("(func() " + scope.scalarType() + " {\n")
		child := scope.child()
		for i, c := range kids {
			isLast := i == len(kids)-1
			if k.category(c).Type == RBasicBlock && k.category(c).Inst == RBlockLet {
				letKids := k.children(c)
				if len(letKids) == 2 && letKids[0].Level == LevelTrivial && letKids[0].Type == TrivString {
					valSrc, err := emitGoExpr(k, letKids[1], child)
					if err != nil {
						return "", err
					}
					name := NameID(letKids[0].Inst)
					varName := child.fresh(fmt.Sprintf("let_%s", k.nameStr(name)))
					child.vars[name] = varName
					b.WriteString(fmt.Sprintf("\t%s := %s\n", varName, child.cast(valSrc)))
					if isLast {
						b.WriteString(fmt.Sprintf("\treturn %s\n", varName))
					}
					continue
				}
			}
			expr, err := emitGoExpr(k, c, child)
			if err != nil {
				return "", err
			}
			if isLast {
				b.WriteString(fmt.Sprintf("\treturn %s\n", child.cast(expr)))
			} else {
				b.WriteString(fmt.Sprintf("\t_ = (%s)\n", expr))
			}
		}
		b.WriteString("}())")
		return b.String(), nil
	}
	return "", unsupported(fmt.Sprintf("jit: block op %d not in subset", op))
}

func emitGoHelperCall(k *Kernel, nameID NameID, kids []NodeID, scope *goCompileScope) (string, error) {
	if scope.env == nil || scope.plan == nil {
		return "", unsupported(fmt.Sprintf("jit: unsupported call %q (no compile env)", k.nameStr(nameID)))
	}
	v, ok := scope.env.Lookup(nameID)
	if !ok || v.Kind != VClosure {
		return "", unsupported(fmt.Sprintf("jit: unsupported call %q (only static Form helpers in compile env)", k.nameStr(nameID)))
	}
	cl := v.Cl
	if len(kids)-1 != len(cl.Params) {
		return "", unsupported(fmt.Sprintf("jit: helper %q wants %d args, got %d", k.nameStr(nameID), len(cl.Params), len(kids)-1))
	}
	fn, err := emitGoHelperFunction(k, cl, scope)
	if err != nil {
		return "", err
	}
	args := make([]string, 0, len(kids)-1)
	for i := 1; i < len(kids); i++ {
		a, err := emitGoExpr(k, kids[i], scope)
		if err != nil {
			return "", err
		}
		args = append(args, scope.cast(a))
	}
	return fmt.Sprintf("%s(%s)", fn, strings.Join(args, ", ")), nil
}

func emitGoHelperFunction(k *Kernel, cl *Closure, parent *goCompileScope) (string, error) {
	plan := parent.plan
	if fn, ok := plan.helpers[cl.Name]; ok {
		if plan.emitted[cl.Name] || plan.emitting[cl.Name] {
			return fn, nil
		}
	}
	fn := fmt.Sprintf("fn_%s_helper_%d", string(parent.abi), cl.Name)
	plan.helpers[cl.Name] = fn
	if plan.emitting[cl.Name] {
		return fn, nil
	}
	plan.emitting[cl.Name] = true

	scope := newGoCompileScope(cl.Name, fn, parent.abi, cl.Env, plan)
	for i, p := range cl.Params {
		scope.vars[p] = fmt.Sprintf("p%d", i)
	}
	bodySrc, err := emitGoExpr(k, cl.Body, scope)
	if err != nil {
		delete(plan.emitting, cl.Name)
		return "", err
	}

	scalar := scope.scalarType()
	var paramSig strings.Builder
	for i := range cl.Params {
		if i > 0 {
			paramSig.WriteString(", ")
		}
		paramSig.WriteString(fmt.Sprintf("p%d %s", i, scalar))
	}
	plan.helperSrc.WriteString(fmt.Sprintf("func %s(%s) %s {\n", fn, paramSig.String(), scalar))
	plan.helperSrc.WriteString("\treturn ")
	plan.helperSrc.WriteString(scope.cast(bodySrc))
	plan.helperSrc.WriteString("\n}\n\n")
	plan.emitted[cl.Name] = true
	delete(plan.emitting, cl.Name)
	return fn, nil
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
			args = append(args, scope.cast(a))
		}
		return fmt.Sprintf("%s(%s)", scope.selfFn, strings.Join(args, ", ")), nil
	}
	// Check if it's a math/compare/cond operator name (the parser may
	// have produced a generic FNCALL with these names if the body uses
	// the s-expression form). Lower to the corresponding operator.
	switch name {
	case "add", "_plus", "sub", "mul", "div", "mod":
		op := map[string]uint32{
			"add": RMathPlus, "_plus": RMathPlus, "sub": RMathMinus, "mul": RMathMultiply,
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

	// List primitives for vector recipes in recipelib (head/tail/len/concat).
	// Used by vector_add, dot_product etc. Emitted using Go slice ops.
	if name == "list" {
		args := make([]string, 0, len(kids)-1)
		for i := 1; i < len(kids); i++ {
			a, err := emitGoExpr(k, kids[i], scope)
			if err != nil {
				return "", err
			}
			if scope.abi == goJITABIValue {
				args = append(args, a)
			} else {
				args = append(args, scope.cast(a))
			}
		}
		if scope.abi == goJITABIValue {
			return "jitabi.List(" + strings.Join(args, ", ") + ")", nil
		}
		return "[]" + scope.scalarType() + "{" + strings.Join(args, ", ") + "}", nil
	}
	if name == "empty" {
		if scope.abi == goJITABIValue {
			return "jitabi.List()", nil
		}
		return "[]" + scope.scalarType() + "{}", nil
	}
	if name == "nil?" {
		if len(kids) < 2 {
			return "", unsupported("jit: nil? expects list arg")
		}
		argSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		if scope.abi == goJITABIValue {
			return "jitabi.Bool(jitabi.Len(" + argSrc + ") == 0)", nil
		}
		if !jitNodeIsListExpr(k, kids[1]) {
			return "", unsupported("jit: nil? over list-valued parameters needs a list ABI")
		}
		return fmt.Sprintf("(func() %s { if len(%s) == 0 { return %s }; return %s }())",
			scope.scalarType(), argSrc, scope.scalarOne(), scope.scalarZero()), nil
	}
	if name == "len" {
		if len(kids) < 2 {
			return "", unsupported("jit: len expects list arg")
		}
		if scope.abi == goJITABIValue {
			listSrc, err := emitGoExpr(k, kids[1], scope)
			if err != nil {
				return "", err
			}
			return "jitabi.Int(jitabi.Len(" + listSrc + "))", nil
		}
		if !jitNodeIsListExpr(k, kids[1]) {
			return "", unsupported("jit: len over list-valued parameters needs a list ABI")
		}
		listSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		if scope.abi == goJITABIf64 {
			return "float64(len(" + listSrc + "))", nil
		}
		return "int64(len(" + listSrc + "))", nil
	}
	if name == "head" {
		if len(kids) < 2 {
			return "", unsupported("jit: head expects list arg")
		}
		if scope.abi == goJITABIValue {
			listSrc, err := emitGoExpr(k, kids[1], scope)
			if err != nil {
				return "", err
			}
			return "jitabi.Head(" + listSrc + ")", nil
		}
		if !jitNodeIsListExpr(k, kids[1]) {
			return "", unsupported("jit: head over list-valued parameters needs a list ABI")
		}
		listSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		return listSrc + "[0]", nil
	}
	if name == "tail" {
		if len(kids) < 2 {
			return "", unsupported("jit: tail expects list arg")
		}
		if scope.abi == goJITABIValue {
			listSrc, err := emitGoExpr(k, kids[1], scope)
			if err != nil {
				return "", err
			}
			return "jitabi.Tail(" + listSrc + ")", nil
		}
		if !jitNodeIsListExpr(k, kids[1]) {
			return "", unsupported("jit: tail over list-valued parameters needs a list ABI")
		}
		listSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		return listSrc + "[1:]", nil
	}
	if name == "concat" {
		if len(kids) < 3 {
			return "", unsupported("jit: concat expects two list args")
		}
		if scope.abi == goJITABIValue {
			aSrc, err := emitGoExpr(k, kids[1], scope)
			if err != nil {
				return "", err
			}
			bSrc, err := emitGoExpr(k, kids[2], scope)
			if err != nil {
				return "", err
			}
			return "jitabi.Concat(" + aSrc + ", " + bSrc + ")", nil
		}
		if !jitNodeIsListExpr(k, kids[1]) || !jitNodeIsListExpr(k, kids[2]) {
			return "", unsupported("jit: concat over list-valued parameters needs a list ABI")
		}
		aSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		bSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		elemType := scope.scalarType()
		return "append(append([]" + elemType + "{}, " + aSrc + "...), " + bSrc + "...)", nil
	}
	if name == "cons" {
		if len(kids) < 3 {
			return "", unsupported("jit: cons expects head and tail")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: cons requires value ABI")
		}
		headSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		tailSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.Cons(" + headSrc + ", " + tailSrc + ")", nil
	}
	if name == "nth" {
		if len(kids) < 3 {
			return "", unsupported("jit: nth expects list and index")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: nth requires value ABI")
		}
		listSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		idxSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.Nth(" + listSrc + ", " + idxSrc + ")", nil
	}
	if name == "str_len" {
		if len(kids) < 2 {
			return "", unsupported("jit: str_len expects string arg")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: str_len requires value ABI")
		}
		argSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.StrLen(" + argSrc + ")", nil
	}
	if name == "str_concat" {
		if len(kids) < 3 {
			return "", unsupported("jit: str_concat expects two string args")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: str_concat requires value ABI")
		}
		aSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		bSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.StrConcat(" + aSrc + ", " + bSrc + ")", nil
	}
	if name == "str_eq" {
		if len(kids) < 3 {
			return "", unsupported("jit: str_eq expects two string args")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: str_eq requires value ABI")
		}
		aSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		bSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.StrEq(" + aSrc + ", " + bSrc + ")", nil
	}
	if name == "substring" {
		if len(kids) < 4 {
			return "", unsupported("jit: substring expects string, start, end")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: substring requires value ABI")
		}
		sSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		startSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		endSrc, err := emitGoExpr(k, kids[3], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.Substring(" + sSrc + ", " + startSrc + ", " + endSrc + ")", nil
	}
	if name == "char_at" {
		if len(kids) < 3 {
			return "", unsupported("jit: char_at expects string and index")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: char_at requires value ABI")
		}
		sSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		idxSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.CharAt(" + sSrc + ", " + idxSrc + ")", nil
	}
	if name == "ord" {
		if len(kids) < 2 {
			return "", unsupported("jit: ord expects string arg")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: ord requires value ABI")
		}
		argSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.Ord(" + argSrc + ")", nil
	}
	if name == "byte_to_str" {
		if len(kids) < 2 {
			return "", unsupported("jit: byte_to_str expects int arg")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: byte_to_str requires value ABI")
		}
		argSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.ByteToStr(" + argSrc + ")", nil
	}
	if name == "scan_run" {
		if len(kids) < 4 {
			return "", unsupported("jit: scan_run expects string, from, class")
		}
		if scope.abi != goJITABIValue {
			return "", unsupported("jit: scan_run requires value ABI")
		}
		sSrc, err := emitGoExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		fromSrc, err := emitGoExpr(k, kids[2], scope)
		if err != nil {
			return "", err
		}
		classSrc, err := emitGoExpr(k, kids[3], scope)
		if err != nil {
			return "", err
		}
		return "jitabi.ScanRun(" + sSrc + ", " + fromSrc + ", " + classSrc + ")", nil
	}

	if scope.env != nil {
		if v, ok := scope.env.Lookup(nameID); ok && v.Kind == VClosure {
			return emitGoHelperCall(k, nameID, kids, scope)
		}
	}

	return "", unsupported(fmt.Sprintf("jit: unsupported call %q (only self-recursion + arithmetic primitives in subset)", name))
}

func jitNodeIsListExpr(k *Kernel, node NodeID) bool {
	if node.Level == LevelTrivial {
		return false
	}
	return k.category(node).Type == RBasicList
}

func jitRecipeNeedsValueABI(k *Kernel, node NodeID) bool {
	if node.Level == LevelTrivial {
		return node.Type == TrivString
	}
	cat := k.category(node)
	if cat.Type == RBasicList {
		return true
	}
	kids := k.children(node)
	if cat.Type == RBasicFnCall && len(kids) > 0 {
		if name, ok := jitStaticCallName(k, kids[0]); ok {
			switch name {
			case "list", "empty", "cons", "head", "tail", "len", "nil?", "concat", "nth",
				"str_len", "str_concat", "str_eq", "substring", "char_at", "ord",
				"byte_to_str", "scan_run":
				return true
			}
		}
	}
	for _, kid := range kids {
		if jitRecipeNeedsValueABI(k, kid) {
			return true
		}
	}
	return false
}

func jitStaticCallName(k *Kernel, callee NodeID) (string, bool) {
	if callee.Level == LevelTrivial && callee.Type == TrivString {
		return k.nameStr(NameID(callee.Inst)), true
	}
	if callee.Level != LevelTrivial {
		cat := k.category(callee)
		if cat.Type == RBasicIdent {
			return k.nameStr(k.identID(callee)), true
		}
	}
	return "", false
}

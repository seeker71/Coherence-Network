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
//   • Logic: and, or, not (0/1 int results over truthy inputs; matches walker int-subset convention)
//   • Conditionals: if / if-else
//   • Let-bindings of integer values
//   • Parameter references
//   • Recursive free-function calls (the closure's own name)
//   • Nested capture-free defns in statement position (lifted as sibling helpers)
//
// Out of scope by design (refuse to compile, walker keeps running):
//   • Lists, strings, floats (in pure i64 leg), closures-over-outer-state
//     (a nested defn that captures an outer local refuses with its name)
//   • Native calls inside the compiled body (Value leg or dispatch handles)
//   • Multi-type signatures beyond the supported ABIs
//
// Plugin caching: in-memory keyed by the body's NodeID-tuple string
// ("0.2.99.42") for the lifetime of the kernel process, and durably on disk
// under $XDG_CACHE_HOME/form-jit (default ~/.cache/form-jit) keyed by content:
// bodyKey + Go toolchain + race mode + the on-disk kernel sources the plugin's
// go.mod `replace` points at + the generated source itself. A warm key loads
// the existing .so via plugin.Open without invoking `go build`.

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"plugin"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"

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

// goLocalFn — a nested defn lifted to a plan-level sibling helper. Calls
// resolve by name within the defining scope and its children; the helper
// shadows any compile-env closure of the same name.
type goLocalFn struct {
	fn    string
	arity int
}

type goCompileScope struct {
	vars     map[NameID]string
	localFns map[NameID]goLocalFn
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
		localFns: map[NameID]goLocalFn{},
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
	for k, v := range s.localFns {
		cp.localFns[k] = v
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

// jitGoBuildCount — `go build` invocations this process has paid. The durable
// plugin cache's proof handle: a warm key loads the artifact without growing it.
var jitGoBuildCount atomic.Uint64

// jitHostRaceEnabled — true when this binary carries the race detector
// (set by jit_race.go's build-tagged init). Plugin ABI compatibility
// requires the plugin to carry it too.
var jitHostRaceEnabled = false

// goJITEmitted — the kernel-free remainder of a compile: everything
// jitBuildAndLoadGo needs after jitEmitClosureGo has finished reading the
// recipe store, so the build can run on another goroutine without touching
// kernel state.
type goJITEmitted struct {
	abis     []goJITABI
	src      string
	cacheKey string // "" disables the durable cache (kernel sources unreadable)
}

func jitCompileClosureGo(k *Kernel, cl *Closure) (*GoJITCompiled, error) {
	em, err := jitEmitClosureGo(k, cl)
	if err != nil {
		return nil, err
	}
	return jitBuildAndLoadGo(em)
}

func jitEmitClosureGo(k *Kernel, cl *Closure) (*goJITEmitted, error) {
	type abiBuild struct {
		abi goJITABI
		src string
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
		builds = append(builds, abiBuild{abi: abi, src: src})
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
		if build.abi == goJITABIValue {
			src.WriteString("import \"form-kernel-go/jitabi\"\n\n")
			break
		}
	}
	for _, build := range builds {
		src.WriteString(build.src)
		src.WriteString("\n")
	}

	em := &goJITEmitted{src: src.String()}
	for _, build := range builds {
		em.abis = append(em.abis, build.abi)
	}
	em.cacheKey = jitPluginCacheKey(nodeIDKey(cl.Body), em.src)
	return em, nil
}

var (
	jitKernelSrcOnce sync.Once
	jitKernelSrcHash string
	jitKernelSrcErr  error
)

// jitKernelSourceHash — content hash of the kernel files a plugin build
// compiles in: the jitabi package (the only kernel import generated code
// uses) plus go.mod (toolchain directives). The plugin's go.mod `replace`
// points at this source tree, so a cached .so is only valid while these
// bytes are — a stale artifact over an edited jitabi would be a silent
// chimera. Hashed once per process; the tree doesn't move under a running
// kernel.
func jitKernelSourceHash() (string, error) {
	jitKernelSrcOnce.Do(func() {
		dir := formKernelModuleDir()
		paths, err := filepath.Glob(filepath.Join(dir, "jitabi", "*.go"))
		if err != nil || len(paths) == 0 {
			jitKernelSrcErr = fmt.Errorf("jit cache: no jitabi sources under %s", dir)
			return
		}
		paths = append(paths, filepath.Join(dir, "go.mod"))
		h := sha256.New()
		for _, p := range paths {
			data, err := os.ReadFile(p)
			if err != nil {
				jitKernelSrcErr = err
				return
			}
			h.Write([]byte(filepath.Base(p)))
			h.Write([]byte{0})
			h.Write(data)
			h.Write([]byte{0})
		}
		jitKernelSrcHash = hex.EncodeToString(h.Sum(nil))
	})
	return jitKernelSrcHash, jitKernelSrcErr
}

// jitPluginCacheKey — content address for the durable artifact. The key moves
// when ANY input to the .so moves: the recipe body (bodyKey + the generated
// source), the Go toolchain (plugin ABI requires a byte-identical toolchain),
// race mode, and the on-disk kernel sources the plugin compiles against.
// "" disables the cache when the kernel sources can't be attested.
func jitPluginCacheKey(bodyKey, src string) string {
	kernelHash, err := jitKernelSourceHash()
	if err != nil {
		return ""
	}
	h := sha256.New()
	for _, part := range []string{bodyKey, runtimeVersionRaw(), fmt.Sprintf("race=%t", jitHostRaceEnabled), kernelHash, src} {
		h.Write([]byte(part))
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}

// jitPluginCachePath — durable artifact location for a cache key. Respects
// XDG_CACHE_HOME; "" disables the cache (no key, or no resolvable home).
func jitPluginCachePath(key string) string {
	if key == "" {
		return ""
	}
	root := os.Getenv("XDG_CACHE_HOME")
	if root == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return ""
		}
		root = filepath.Join(home, ".cache")
	}
	return filepath.Join(root, "form-jit", key, "plugin.so")
}

// jitPersistPlugin — write-temp-then-rename in the cache dir so no process
// (this one or a sibling) ever observes a half-written .so at the cache path.
func jitPersistPlugin(builtSo, cacheSo string) error {
	if err := os.MkdirAll(filepath.Dir(cacheSo), 0o755); err != nil {
		return err
	}
	data, err := os.ReadFile(builtSo)
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(cacheSo), "plugin.so.tmp-")
	if err != nil {
		return err
	}
	tmpPath := tmp.Name()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		os.Remove(tmpPath)
		return err
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmpPath)
		return err
	}
	if err := os.Chmod(tmpPath, 0o755); err != nil {
		os.Remove(tmpPath)
		return err
	}
	return os.Rename(tmpPath, cacheSo)
}

// jitBuildAndLoadGo — the kernel-free half: cache probe, `go build`, atomic
// persist, plugin load. Touches no kernel state, so jitAsyncKick can run it
// off the walker goroutine.
func jitBuildAndLoadGo(em *goJITEmitted) (*GoJITCompiled, error) {
	cacheSo := jitPluginCachePath(em.cacheKey)
	if cacheSo != "" {
		if _, err := os.Stat(cacheSo); err == nil {
			if p, err := plugin.Open(cacheSo); err == nil {
				return jitLookupPluginSymbols(p, em.abis)
			}
			// unreadable artifact — rebuild and rename over it below
		}
	}

	// Write to a temp directory, run `go build -buildmode=plugin`.
	dir, err := os.MkdirTemp("", "form-jit-")
	if err != nil {
		return nil, fmt.Errorf("mkdtemp: %w", err)
	}
	srcPath := filepath.Join(dir, "main.go")
	if err := os.WriteFile(srcPath, []byte(em.src), 0o644); err != nil {
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
	buildArgs := []string{"build", "-buildmode=plugin"}
	if jitHostRaceEnabled {
		// A non-race plugin can't load into a race host (package version
		// mismatch on runtime internals); mirror the host's mode.
		buildArgs = append(buildArgs, "-race")
	}
	buildArgs = append(buildArgs, "-o", soPath, srcPath)
	cmd := exec.Command("go", buildArgs...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GOFLAGS=") // strip user GOFLAGS that might inject -mod=vendor etc.
	jitGoBuildCount.Add(1)
	if out, err := cmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("go build failed: %v\n%s", err, string(out))
	}

	if cacheSo != "" {
		if err := jitPersistPlugin(soPath, cacheSo); err == nil {
			if p, err := plugin.Open(cacheSo); err == nil {
				// The .so the runtime mmap'd lives at the cache path now;
				// the temp build dir can go.
				os.RemoveAll(dir)
				return jitLookupPluginSymbols(p, em.abis)
			}
		}
	}
	// No durable cache — keep the dir for the lifetime of the kernel
	// process: the .so is mmap'd by the runtime and shouldn't be removed
	// under it. The OS reclaims /tmp on reboot; no leak in practice.
	p, err := plugin.Open(soPath)
	if err != nil {
		return nil, fmt.Errorf("plugin.Open: %w", err)
	}
	return jitLookupPluginSymbols(p, em.abis)
}

func jitLookupPluginSymbols(p *plugin.Plugin, abis []goJITABI) (*GoJITCompiled, error) {
	out := &GoJITCompiled{}
	for _, abi := range abis {
		switch abi {
		case goJITABIi64:
			sym, err := p.Lookup("FnI64")
			if err != nil {
				return nil, fmt.Errorf("plugin.Lookup FnI64: %w", err)
			}
			fn, ok := sym.(func([]int64) int64)
			if !ok {
				return nil, fmt.Errorf("plugin.Lookup: FnI64 has wrong type %T", sym)
			}
			out.I64 = fn
		case goJITABIf64:
			sym, err := p.Lookup("FnF64")
			if err != nil {
				return nil, fmt.Errorf("plugin.Lookup FnF64: %w", err)
			}
			fn, ok := sym.(func([]float64) float64)
			if !ok {
				return nil, fmt.Errorf("plugin.Lookup: FnF64 has wrong type %T", sym)
			}
			out.F64 = fn
		case goJITABIValue:
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
		return emitGoLogic(k, cat.Inst, kids, scope)

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
		// A defn's value is a closure — representable only where the block
		// emitter discards it (statement position; see emitGoBlock).
		return "", unsupported("jit: nested defn in value position not in subset")
	}
	return "", unsupported(fmt.Sprintf("jit: unsupported arm type %d", cat.Type))
}

// emitGoNestedDefn — lift a capture-free nested defn into a plan-level
// sibling helper and register it in the defining scope so later siblings
// resolve calls by name. A defn that captures an outer local is the
// documented closures-over-outer limit and refuses with the captured name.
func emitGoNestedDefn(k *Kernel, node NodeID, scope *goCompileScope) error {
	kids := k.children(node)
	if len(kids) != 3 {
		return unsupported("jit: nested defn expects name, params, body")
	}
	name := k.identID(kids[0])
	paramKids := k.children(kids[1])
	params := make([]NameID, len(paramKids))
	for i, p := range paramKids {
		params[i] = NameID(p.Inst)
	}
	bound := map[NameID]bool{name: true}
	for _, p := range params {
		bound[p] = true
	}
	if capID, captured := jitNestedDefnCapture(k, kids[2], bound, scope); captured {
		return unsupported(fmt.Sprintf("jit: nested defn %q captures outer local %q (closures-over-outer not in subset)",
			k.nameStr(name), k.nameStr(capID)))
	}
	fn := scope.fresh(fmt.Sprintf("fn_%s_nested_%s", string(scope.abi), k.nameStr(name)))
	inner := newGoCompileScope(name, fn, scope.abi, scope.env, scope.plan)
	inner.uid = scope.uid
	for n, lf := range scope.localFns {
		inner.localFns[n] = lf
	}
	for i, p := range params {
		inner.vars[p] = fmt.Sprintf("p%d", i)
	}
	bodySrc, err := emitGoExpr(k, kids[2], inner)
	if err != nil {
		return err
	}
	scalar := inner.scalarType()
	var paramSig strings.Builder
	for i := range params {
		if i > 0 {
			paramSig.WriteString(", ")
		}
		paramSig.WriteString(fmt.Sprintf("p%d %s", i, scalar))
	}
	plan := scope.plan
	plan.helperSrc.WriteString(fmt.Sprintf("func %s(%s) %s {\n", fn, paramSig.String(), scalar))
	plan.helperSrc.WriteString("\treturn ")
	plan.helperSrc.WriteString(inner.cast(bodySrc))
	plan.helperSrc.WriteString("\n}\n\n")
	scope.localFns[name] = goLocalFn{fn: fn, arity: len(params)}
	return nil
}

// jitNestedDefnCapture — first outer-local name the inner body reads. Bound
// names accumulate structurally (params, lets, nested defns) as an
// over-approximation; a slip-through never miscompiles, because the inner
// body is emitted against a fresh scope and a real capture that evades this
// walk still refuses as an unbound identifier. This walk exists to name the
// refusal honestly.
func jitNestedDefnCapture(k *Kernel, node NodeID, bound map[NameID]bool, outer *goCompileScope) (NameID, bool) {
	if node.Level == LevelTrivial {
		return 0, false
	}
	cat := k.category(node)
	kids := k.children(node)
	switch cat.Type {
	case RBasicIdent:
		id := k.identID(node)
		if !bound[id] {
			if _, isOuterLocal := outer.vars[id]; isOuterLocal {
				return id, true
			}
		}
		return 0, false
	case RBasicBlock:
		if cat.Inst == RBlockLet && len(kids) == 2 {
			if capID, captured := jitNestedDefnCapture(k, kids[1], bound, outer); captured {
				return capID, true
			}
			if kids[0].Level == LevelTrivial && kids[0].Type == TrivString {
				bound[NameID(kids[0].Inst)] = true
			}
			return 0, false
		}
	case RBasicFnDef:
		if len(kids) == 3 {
			bound[k.identID(kids[0])] = true
			for _, p := range k.children(kids[1]) {
				bound[NameID(p.Inst)] = true
			}
			return jitNestedDefnCapture(k, kids[2], bound, outer)
		}
	case RBasicFnCall:
		if len(kids) > 0 {
			rest := kids
			if _, ok := jitStaticCallName(k, kids[0]); ok {
				rest = kids[1:] // the callee slot is a name, not a value read
			}
			for _, kid := range rest {
				if capID, captured := jitNestedDefnCapture(k, kid, bound, outer); captured {
					return capID, true
				}
			}
			return 0, false
		}
	}
	for _, kid := range kids {
		if capID, captured := jitNestedDefnCapture(k, kid, bound, outer); captured {
			return capID, true
		}
	}
	return 0, false
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
		if scope.abi == goJITABIf64 {
			// Go has no float %, and the walker's float mod is floor-mod —
			// the f64 leg refuses so the combined plugin build stays clean
			// while the i64 and Value legs carry the shape.
			return "", unsupported("jit: float mod not in f64 subset")
		}
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

func emitGoLogic(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	if op == RLogicNot {
		if len(kids) != 1 {
			return "", unsupported("jit: not expects 1 arg")
		}
		a, err := emitGoExpr(k, kids[0], scope)
		if err != nil {
			return "", err
		}
		if scope.abi == goJITABIValue {
			return fmt.Sprintf("jitabi.Int( jitabi.Truthy(%s) ? 0 : 1 )", a), nil
		}
		scalar := scope.scalarType()
		one := scope.scalarOne()
		zero := scope.scalarZero()
		return fmt.Sprintf("(func() %s { if (%s != 0) { return %s }; return %s }())", scalar, a, zero, one), nil
	}
	// and / or — binary (emitter convention for the int subset)
	if len(kids) != 2 {
		return "", unsupported("jit: and/or expect 2 args")
	}
	a, err := emitGoExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	b, err := emitGoExpr(k, kids[1], scope)
	if err != nil {
		return "", err
	}
	var cond string
	if op == RLogicAnd {
		cond = fmt.Sprintf("((%s != 0) && (%s != 0))", a, b)
	} else if op == RLogicOr {
		cond = fmt.Sprintf("((%s != 0) || (%s != 0))", a, b)
	} else {
		return "", unsupported(fmt.Sprintf("jit: logic op %d", op))
	}
	if scope.abi == goJITABIValue {
		return fmt.Sprintf("jitabi.Int( %s ? 1 : 0 )", cond), nil
	}
	scalar := scope.scalarType()
	one := scope.scalarOne()
	zero := scope.scalarZero()
	return fmt.Sprintf("(func() %s { if (%s) { return %s }; return %s }())", scalar, cond, one, zero), nil
}

func emitGoCond(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	if len(kids) < 2 {
		return "", unsupported("jit: cond expects at least 2 kids")
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
	if scope.abi != goJITABIValue {
		// Direct-comparison condition emits as a raw Go boolean — skips the
		// bool→scalar→!=0 round trip so the native branch matches what a
		// hand-written Go function would compile to.
		if boolSrc, ok, err := emitGoCondBool(k, kids[0], scope); err != nil {
			return "", err
		} else if ok {
			return fmt.Sprintf("(func() %s { if %s { return %s }; return %s }())",
				scalar, boolSrc, scope.cast(then), scope.cast(els)), nil
		}
	}
	cond, err := emitGoExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	if scope.abi == goJITABIValue {
		return fmt.Sprintf("(func() %s { if jitabi.Truthy(%s) { return %s }; return %s }())",
			scalar, cond, then, els), nil
	}
	return fmt.Sprintf("(func() %s { if (%s) != 0 { return %s }; return %s }())",
		scalar, cond, scope.cast(then), scope.cast(els)), nil
}

// emitGoCondBool — when a condition node is a direct comparison (either the
// lowered RBasicCompare arm or the FNCALL sugar eq/ne/lt/le/gt/ge), emit it
// as a native Go boolean expression. Returns ok=false for any other shape so
// the caller falls back to the scalar-truthiness path.
func emitGoCondBool(k *Kernel, node NodeID, scope *goCompileScope) (string, bool, error) {
	if node.Level == LevelTrivial {
		return "", false, nil
	}
	cat := k.category(node)
	var op uint32
	var operands []NodeID
	switch {
	case cat.Type == RBasicCompare:
		op = cat.Inst
		operands = k.children(node)
	case cat.Type == RBasicFnCall:
		kids := k.children(node)
		if len(kids) != 3 {
			return "", false, nil
		}
		name, ok := jitStaticCallName(k, kids[0])
		if !ok {
			return "", false, nil
		}
		mapped, ok := map[string]uint32{
			"eq": RCompareEq, "ne": RCompareNe, "lt": RCompareLt,
			"le": RCompareLe, "gt": RCompareGt, "ge": RCompareGe,
		}[name]
		if !ok {
			return "", false, nil
		}
		op = mapped
		operands = kids[1:]
	default:
		return "", false, nil
	}
	if len(operands) != 2 {
		return "", false, nil
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
		return "", false, nil
	}
	a, err := emitGoExpr(k, operands[0], scope)
	if err != nil {
		return "", false, err
	}
	b, err := emitGoExpr(k, operands[1], scope)
	if err != nil {
		return "", false, err
	}
	return fmt.Sprintf("(%s %s %s)", a, opStr, b), true, nil
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
			if k.category(c).Type == RBasicFnDef {
				if isLast {
					// Walker returns the closure here; no scalar carries that.
					return "", unsupported("jit: nested defn as block value not in subset")
				}
				if err := emitGoNestedDefn(k, c, child); err != nil {
					return "", err
				}
				continue
			}
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

	// Nested defns lifted by emitGoNestedDefn resolve before the compile
	// env: an inner name shadows an outer Form helper of the same name.
	if lf, ok := scope.localFns[nameID]; ok {
		if len(kids)-1 != lf.arity {
			return "", unsupported(fmt.Sprintf("jit: nested %q wants %d args, got %d", name, lf.arity, len(kids)-1))
		}
		args := make([]string, 0, len(kids)-1)
		for i := 1; i < len(kids); i++ {
			a, err := emitGoExpr(k, kids[i], scope)
			if err != nil {
				return "", err
			}
			args = append(args, scope.cast(a))
		}
		return fmt.Sprintf("%s(%s)", lf.fn, strings.Join(args, ", ")), nil
	}

	if scope.env != nil {
		if v, ok := scope.env.Lookup(nameID); ok && v.Kind == VClosure {
			return emitGoHelperCall(k, nameID, kids, scope)
		}
	}

	return "", unsupported(fmt.Sprintf("jit: unsupported call %q (only self-recursion + arithmetic primitives in subset)", name))
}

// --- async hot-threshold builds ---------------------------------------------
//
// The FNCALL dispatch arm promotes a closure at the hot threshold. The build
// (~1.3s of `go build`) must not stall the crossing call, so the emit half
// runs inline — it reads the recipe store, which only the walker goroutine
// may touch — and the build half runs in a goroutine. Results land in the
// mutex-guarded zone (k.jitAsyncMu and the two maps under it); the walker
// adopts them into jitCompiledGo on a later call, so the artifact map itself
// stays single-goroutine.

type jitAsyncResult struct {
	jc     *GoJITCompiled // nil when the build failed
	reason string
}

// jitAsyncTake — adoption poll for the dispatch arm. Returns the landed
// result (removing it) or building=true while the goroutine is still out.
func (k *Kernel) jitAsyncTake(bodyKey string) (*jitAsyncResult, bool) {
	k.jitAsyncMu.Lock()
	defer k.jitAsyncMu.Unlock()
	if res, ok := k.jitAsyncLanded[bodyKey]; ok {
		delete(k.jitAsyncLanded, bodyKey)
		return res, false
	}
	return nil, k.jitAsyncBuilding[bodyKey]
}

// jitAsyncKick — start at most one background build per bodyKey. The emit
// half runs on the caller's (walker) goroutine; an emit refusal returns
// immediately so the caller can mark the body failed without a goroutine
// round-trip. A build failure lands as a jitAsyncResult with a reason, so
// adoption marks the body failed and it is never retried in a loop.
func (k *Kernel) jitAsyncKick(cl *Closure, bodyKey string) error {
	k.jitAsyncMu.Lock()
	if k.jitAsyncBuilding[bodyKey] {
		k.jitAsyncMu.Unlock()
		return nil
	}
	if _, landed := k.jitAsyncLanded[bodyKey]; landed {
		k.jitAsyncMu.Unlock()
		return nil
	}
	k.jitAsyncBuilding[bodyKey] = true
	k.jitAsyncMu.Unlock()

	em, err := jitEmitClosureGo(k, cl)
	if err != nil {
		k.jitAsyncMu.Lock()
		delete(k.jitAsyncBuilding, bodyKey)
		k.jitAsyncMu.Unlock()
		return err
	}
	go func() {
		jc, err := jitBuildAndLoadGo(em)
		res := &jitAsyncResult{jc: jc}
		if err != nil {
			res = &jitAsyncResult{reason: err.Error()}
		}
		k.jitAsyncMu.Lock()
		delete(k.jitAsyncBuilding, bodyKey)
		k.jitAsyncLanded[bodyKey] = res
		k.jitAsyncMu.Unlock()
	}()
	return nil
}

// --- install-as-named-callable-leaf ----------------------------------------
//
// The install protocol (form-stdlib/install-leaf.fk, proven three-way by
// tests/install-leaf-band.fk) carried onto the Go JIT lane: a jitted .so
// artifact becomes a NAMED callable in the kernel's own native table at
// runtime — the surface grows by offer, never by recompile. The ack follows
// axiom-5: the artifact's body NodeID (content-addressed, unforgeable) on
// bind, 0 on refusal (name collision / interface mismatch / no artifact),
// nothing when there is no closure to install.

// jitInstalledLeafFn — the callable a successful jit_install binds into
// k.natives. Mirrors the FNCALL closure jit-dispatch ABI guards; a call
// outside the offered interface (wrong arity, value shapes no ABI carries)
// acknowledges nothing — the leaf only ever answers the interface it
// offered, and the miss is observable.
func jitInstalledLeafFn(jc *GoJITCompiled, arity int, body NodeID) NativeFn {
	return func(k *Kernel, args []Value) Value {
		if len(args) != arity {
			k.observeJIT("observe/go/jit/installed-guard-miss", body, 1, uint32(len(args)))
			return Value{Kind: VNull}
		}
		allInt := true
		allNumeric := true
		hasFloat := false
		allJITValue := true
		intArgs := make([]int64, len(args))
		floatArgs := make([]float64, len(args))
		jitArgs := make([]jitabi.Value, len(args))
		for i, av := range args {
			if av.Kind != VInt {
				allInt = false
			}
			if jv, ok := valueToJIT(av); ok {
				jitArgs[i] = jv
			} else {
				allJITValue = false
			}
			switch av.Kind {
			case VInt:
				intArgs[i] = av.Int
				floatArgs[i] = float64(av.Int)
			case VFloat:
				hasFloat = true
				floatArgs[i] = av.Float
			default:
				allNumeric = false
			}
		}
		if allInt && jc.I64 != nil {
			k.jitDispatchHits[body]++
			k.observeJIT("observe/go/jit/installed-dispatch", body, 1, uint32(len(args)))
			return Value{Kind: VInt, Int: jc.I64(intArgs)}
		}
		if allNumeric && hasFloat && jc.F64 != nil {
			k.jitDispatchHits[body]++
			k.observeJIT("observe/go/jit/installed-dispatch", body, 2, uint32(len(args)))
			return Value{Kind: VFloat, Float: jc.F64(floatArgs)}
		}
		if allJITValue && jc.Value != nil {
			k.jitDispatchHits[body]++
			k.observeJIT("observe/go/jit/installed-dispatch", body, 3, uint32(len(args)))
			return valueFromJIT(jc.Value(jitArgs))
		}
		k.observeJIT("observe/go/jit/installed-guard-miss", body, 2, uint32(len(args)))
		return Value{Kind: VNull}
	}
}

// jitInstallLeaf — accept or refuse an install offer. Resolves the named
// closure in the caller's env, ensures a compiled artifact exists for its
// body (reusing the content-addressed plugin cache), and binds the artifact
// under installedName in the kernel's own native table. Refusal, not error:
// a refused offer leaves the table untouched.
func jitInstallLeaf(k *Kernel, env *Frame, closureName, installedName string, expectedArity int64) Value {
	closureID := k.internName(closureName)
	v, ok := env.Lookup(closureID)
	if !ok || v.Kind != VClosure {
		// nothing — there is no cell to install
		return Value{Kind: VNull}
	}
	cl := v.Cl
	installedID := k.internName(installedName)
	_, hasN := k.natives[installedID]
	_, hasE := k.envNatives[installedID]
	if hasN || hasE {
		// name collision — first-bind-wins, the table never rebinds
		k.observeJIT("observe/go/jit/install-refused", cl.Body, 1, 1)
		return Value{Kind: VInt, Int: 0}
	}
	if expectedArity != int64(len(cl.Params)) {
		// interface mismatch — the artifact cannot be bound through an
		// interface it does not carry
		k.observeJIT("observe/go/jit/install-refused", cl.Body, 2, 1)
		return Value{Kind: VInt, Int: 0}
	}
	bodyKey := nodeIDKey(cl.Body)
	jc, compiled := k.jitCompiledGo[bodyKey]
	if !compiled {
		fn, err := jitCompileClosureGo(k, cl)
		if err != nil {
			// no artifact — the recipe still walks under its own name;
			// nothing installs
			k.jitFailed[cl.Body] = true
			k.jitFailedReason[cl.Body] = err.Error()
			k.observeJIT("observe/go/jit/install-refused", cl.Body, 3, 1)
			return Value{Kind: VInt, Int: 0}
		}
		k.jitCompiledGo[bodyKey] = fn
		jc = fn
	}
	k.registerNative(installedName, catMethod(), jitInstalledLeafFn(jc, len(cl.Params), cl.Body))
	k.installedLeaves[installedID] = cl.Body
	k.observeJIT("observe/go/jit/install", cl.Body, uint32(len(cl.Params)), 1)
	// the node ack: the artifact's content-addressed identity
	return Value{Kind: VNodeID, Nid: cl.Body}
}

func jitNodeIsListExpr(k *Kernel, node NodeID) bool {
	if node.Level == LevelTrivial {
		return false
	}
	return k.category(node).Type == RBasicList
}

// jitRecipeNeedsValueABI — pre-filter deciding whether the typed i64/f64
// ABIs are even attempted. A TrivString counts as a runtime string value
// only in value position; the recipe's structural name slots — an IDENT's
// name child, an FNCALL's static callee, a LET's binding name — are the
// tree's shape, not data, and must not force the boxed Value-only ABI.
// The asymmetry that keeps this safe: a false negative costs nothing (the
// i64/f64 emitters still reject genuinely string-shaped bodies and the
// build loop skips them), while a false positive silently boxes every call
// — the typed natives are what give recursive int workloads native speed.
func jitRecipeNeedsValueABI(k *Kernel, node NodeID) bool {
	if node.Level == LevelTrivial {
		return node.Type == TrivString
	}
	cat := k.category(node)
	if cat.Type == RBasicList {
		return true
	}
	kids := k.children(node)
	switch cat.Type {
	case RBasicIdent:
		// The name child is structure, not a string value.
		return false
	case RBasicFnDef:
		if len(kids) == 3 {
			// kids[0] (name) and kids[1] (params) are structural name slots.
			return jitRecipeNeedsValueABI(k, kids[2])
		}
	case RBasicBlock:
		if cat.Inst == RBlockLet && len(kids) == 2 {
			// kids[0] is the binding-name slot; only the bound value is data.
			return jitRecipeNeedsValueABI(k, kids[1])
		}
	case RBasicFnCall:
		if len(kids) > 0 {
			if name, ok := jitStaticCallName(k, kids[0]); ok {
				switch name {
				case "list", "empty", "cons", "head", "tail", "len", "nil?", "concat", "nth",
					"str_len", "str_concat", "str_eq", "substring", "char_at", "ord",
					"byte_to_str", "scan_run":
					return true
				}
				// Static callee resolved — scan only the argument slots.
				for _, kid := range kids[1:] {
					if jitRecipeNeedsValueABI(k, kid) {
						return true
					}
				}
				return false
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

// quotient.go — QUOTIENT RBasic arm: canonicalization under equivalence.
//
// A recipe whose category is RBasic.QUOTIENT has the shape:
//
//   QUOTIENT[carrier-recipe, equivalence-recipe]
//
// Where `equivalence-recipe` is itself a substrate cell describing the
// equivalence relation. When a *value* of the quotient type is interned
// (via InternQuotientValue), the equivalence-recipe's canonicalize step
// runs first; the canonical form is what hits the intern table. Two
// values equivalent under the relation therefore receive the SAME
// NodeID — content-addressing IS the quotient.
//
// This generalizes the canonicalization the format library already
// performs (NaN → quiet, ±0 → +0). The shape: equivalence-recipes are
// SUBSTRATE CELLS, not hardcoded kernel logic. Adding a new equivalence
// is a substrate write — the kernel reads the cell and dispatches the
// CanonicalizeFn through the handler-name registry. The body grows;
// the kernel stays small.
//
// Decidability + cost policy:
//   - DecidableCheap → Eager canonicalize at intern, fast equality
//   - DecidableHeavy → Lazy canonicalize on equality query
//   - Undecidable    → Lazy (no eager option)
// Honest default: Eager unless the equivalence declares heavy/undecidable.
//
// Cross-kernel: handler names match the TS, Python, and Rust arms exactly
// (integer-from-nat-pair, rational-from-int-pair, commutative-pair,
// associative-left-fold). A Form program ingested into any kernel
// canonicalizes identically. New built-in equivalences are a cross-
// kernel coordination breath; Form-program-local ones need no
// coordination.

package main

import (
	"fmt"
	"sync"
)

// ---------------------------------------------------------------------------
// RBasic slot — QUOTIENT lives at type=70 across every kernel. The
// equivalence-cell sibling category uses slot 71. These constants are
// part of the cross-kernel contract; do not renumber without updating
// every kernel and the canonical JSON.
// ---------------------------------------------------------------------------

const (
	RBasicQuotient     uint32 = 70
	RBasicEquivalence  uint32 = 71
)

// ---------------------------------------------------------------------------
// Decidability + canonicalization-strategy metadata
// ---------------------------------------------------------------------------

// Decidability — classification of how (and whether) the equivalence
// can be effectively decided. Encoded as uint32 because the value
// appears in NodeID.Inst slots and in substrate cell children.
type Decidability uint32

const (
	// DecidableCheap — effective algorithm, cheap to run; canonicalize eagerly.
	DecidableCheap Decidability = 1
	// DecidableHeavy — effective algorithm, expensive (e.g. Knuth-Bendix); canonicalize lazily.
	DecidableHeavy Decidability = 2
	// Undecidable — no effective algorithm (e.g. function-equality, group iso in general).
	Undecidable Decidability = 3
)

// CanonStrategy — when to canonicalize. Eager merges at intern; Lazy
// defers to canonical_form / quotient_equal calls.
type CanonStrategy uint32

const (
	StrategyEager CanonStrategy = 1
	StrategyLazy  CanonStrategy = 2
)

// strategyFor — honest default: eager unless the equivalence declares
// heavy or undecidable.
func strategyFor(d Decidability) CanonStrategy {
	if d == DecidableCheap {
		return StrategyEager
	}
	return StrategyLazy
}

// CanonicalizeFn — per-equivalence canonicalization. Operates on a
// value's raw children (the carrier-shape representative) and returns
// the canonical-children tuple. Returning the same tuple-shape for any
// two equivalent inputs is the CanonicalizeFn's job; the kernel handles
// the content-addressing.
//
// Signature mirrors TS/Python/Rust: `(kernel, raw_children) -> canonical`.
type CanonicalizeFn func(k *Kernel, raw []NodeID) []NodeID

// ---------------------------------------------------------------------------
// EquivalenceRelation — the substrate-resident relation descriptor.
// In a Form program this is itself a recipe whose category is
// RBasicEquivalence (HandlerName resolves to a registered fn). We hold
// the Go side here as a thin wrapper; the substrate-cell projection (a
// recipe carrying name + decidability + strategy + handler-name as
// children) is interned in parallel for cross-kernel agreement.
// ---------------------------------------------------------------------------

type EquivalenceRelation struct {
	// Human-readable identifier ("integer-from-nat-pair").
	EquivalenceName string
	// Substrate cell projection — NodeID of the equivalence-recipe.
	NodeID NodeID
	// Decidability + algorithm-cost classification.
	Decidability uint32
	// Computed strategy honoring decidability + honest-defaults policy.
	Strategy uint32
	// IsDecidable — convenience flag; strategy already folds it in.
	IsDecidable bool
	// HandlerName — string-handle into the process-global registered table.
	HandlerName string
}

// ---------------------------------------------------------------------------
// Handler registry — name → CanonicalizeFn.
//
// Process-global so cross-Kernel testing (the QuotientLibrary builds
// against any Kernel) sees the same handlers. The same shape lives in
// the TS module-level Map, the Python module-level dict, and the Rust
// OnceLock<Mutex<HashMap>>.
//
// New equivalences arrive in two halves: a substrate write (the recipe,
// produced by MakeEquivalence) and a handler registration (the runtime,
// here). For purely-Form equivalences (CanonicalizeFn expressed AS a
// Form recipe), the handler would be a "walk-this-recipe" stub — that
// path is follow-up work.
// ---------------------------------------------------------------------------

var (
	handlerRegistryMu sync.RWMutex
	handlerRegistry   = make(map[string]CanonicalizeFn)
)

// RegisterHandler — register a canonicalize handler under a stable name.
// Idempotent — re-registering the same name replaces the existing
// handler (matches TS Map.set semantics).
func RegisterHandler(name string, fn CanonicalizeFn) {
	handlerRegistryMu.Lock()
	defer handlerRegistryMu.Unlock()
	handlerRegistry[name] = fn
}

// GetHandler — fetch a registered handler. Returns (nil, false) if absent.
func GetHandler(name string) (CanonicalizeFn, bool) {
	handlerRegistryMu.RLock()
	defer handlerRegistryMu.RUnlock()
	fn, ok := handlerRegistry[name]
	return fn, ok
}

// HasHandler — true if a handler is registered under this name.
func HasHandler(name string) bool {
	handlerRegistryMu.RLock()
	defer handlerRegistryMu.RUnlock()
	_, ok := handlerRegistry[name]
	return ok
}

// ---------------------------------------------------------------------------
// Substrate-cell projection: the equivalence-recipe.
//
// Stored shape (children, all substrate-resident):
//   [ name-trivial, decidability-int, strategy-int, handler-name-trivial ]
//
// The category instance is the decidability code so the NodeID inst
// already encodes the major axis without a child lookup. Two recipes
// with identical children intern to the SAME NodeID — equivalences are
// content-addressed like everything else.
// ---------------------------------------------------------------------------

func makeEquivalenceCell(
	k *Kernel,
	equivalenceName string,
	decidability uint32,
	strategy uint32,
	handlerName string,
) NodeID {
	category := NodeID{
		Pkg:   1,
		Level: LevelBasic,
		Type:  RBasicEquivalence,
		Inst:  decidability,
	}
	nameNid := k.internString(equivalenceName)
	decNid := k.internTrivialInt(int64(decidability))
	stratNid := k.internTrivialInt(int64(strategy))
	hnameNid := k.internString(handlerName)
	return k.intern(category, []NodeID{nameNid, decNid, stratNid, hnameNid})
}

// MakeEquivalence — register a new equivalence relation in the substrate.
// The handler must already be registered under handlerName via
// RegisterHandler. Returns the EquivalenceRelation handle (carrying the
// substrate cell NodeID).
func MakeEquivalence(
	k *Kernel,
	equivalenceName string,
	decidability Decidability,
	handlerName string,
) EquivalenceRelation {
	if !HasHandler(handlerName) {
		panic(fmt.Sprintf("quotient: handler %q is not registered", handlerName))
	}
	strategy := strategyFor(decidability)
	nid := makeEquivalenceCell(
		k,
		equivalenceName,
		uint32(decidability),
		uint32(strategy),
		handlerName,
	)
	return EquivalenceRelation{
		EquivalenceName: equivalenceName,
		NodeID:          nid,
		Decidability:    uint32(decidability),
		Strategy:        uint32(strategy),
		IsDecidable:     decidability != Undecidable,
		HandlerName:     handlerName,
	}
}

// ---------------------------------------------------------------------------
// QUOTIENT recipe construction.
//
//   MakeQuotientRecipe(k, carrier, equivalence) — intern a
//   QUOTIENT[carrier, equivalence] recipe. The carrier is the underlying
//   recipe whose values get quotiented; the equivalence-recipe carries
//   canonicalization rules. Same (carrier, equivalence) pair always
//   interns to the same NodeID (content-addressing).
// ---------------------------------------------------------------------------

func MakeQuotientRecipe(k *Kernel, carrier, equivalence NodeID) NodeID {
	category := NodeID{
		Pkg:   1,
		Level: LevelBasic,
		Type:  RBasicQuotient,
		Inst:  1, // recipe-form
	}
	return k.intern(category, []NodeID{carrier, equivalence})
}

// QuotientParts — inspect a QUOTIENT recipe: extract (carrier, equivalence).
func QuotientParts(k *Kernel, quotient NodeID) (NodeID, NodeID, error) {
	if quotient.Level != LevelBasic || quotient.Type != RBasicQuotient {
		return NodeID{}, NodeID{}, fmt.Errorf(
			"QuotientParts: @%d.%d.%d.%d is not a QUOTIENT recipe",
			quotient.Pkg, quotient.Level, quotient.Type, quotient.Inst,
		)
	}
	kids := k.children(quotient)
	if len(kids) != 2 {
		return NodeID{}, NodeID{}, fmt.Errorf(
			"QuotientParts: malformed QUOTIENT recipe (children=%d)", len(kids),
		)
	}
	return kids[0], kids[1], nil
}

// ResolveEquivalence — resolve the EquivalenceRelation handle from a
// substrate-cell NodeID. The equivalence-cell's children carry [name,
// decidability, strategy, handler-name]; we decode and look up the
// registered handler.
func ResolveEquivalence(k *Kernel, equiv NodeID) (EquivalenceRelation, bool) {
	kids := k.children(equiv)
	if len(kids) != 4 {
		return EquivalenceRelation{}, false
	}
	name, ok := readStringTrivial(k, kids[0])
	if !ok {
		return EquivalenceRelation{}, false
	}
	dec, ok := readIntTrivial(kids[1])
	if !ok {
		return EquivalenceRelation{}, false
	}
	strat, ok := readIntTrivial(kids[2])
	if !ok {
		return EquivalenceRelation{}, false
	}
	hname, ok := readStringTrivial(k, kids[3])
	if !ok {
		return EquivalenceRelation{}, false
	}
	if !HasHandler(hname) {
		return EquivalenceRelation{}, false
	}
	decU := uint32(dec)
	return EquivalenceRelation{
		EquivalenceName: name,
		NodeID:          equiv,
		Decidability:    decU,
		Strategy:        uint32(strat),
		IsDecidable:     Decidability(decU) != Undecidable,
		HandlerName:     hname,
	}, true
}

func readIntTrivial(n NodeID) (int64, bool) {
	if n.Level != LevelTrivial || n.Type != TrivInt {
		return 0, false
	}
	return int64(int32(n.Inst)), true
}

func readStringTrivial(k *Kernel, n NodeID) (string, bool) {
	if n.Level != LevelTrivial || n.Type != TrivString {
		return "", false
	}
	v := k.trivialValue(n)
	if v.Kind != VStr {
		return "", false
	}
	return v.Str, true
}

// ---------------------------------------------------------------------------
// Interning a value through a quotient.
//
//   InternQuotientValue(k, quotientRecipe, rawChildren)
//
// rawChildren are the carrier-shape children of the raw value (e.g.
// [int(3), int(1)] for an integer-from-nat-pair representative). The
// equivalence's CanonicalizeFn reduces them to canonical-children; the
// kernel then interns a recipe whose category is the QUOTIENT cell and
// whose children are [quotientRecipe, ...canonical-children]. Two
// equivalent raw values therefore produce the SAME NodeID — that's the
// quotient.
//
// Strategy = Eager: canonicalize NOW, then intern canonical form (inst=2).
// Strategy = Lazy:  intern raw form with a distinct inst=3 marker;
//                   CanonicalForm canonicalizes on demand and lands at
//                   the same inst=2 slot the eager path would have
//                   produced, so cross-strategy equality holds.
// ---------------------------------------------------------------------------

func InternQuotientValue(k *Kernel, quotientRecipe NodeID, rawChildren []NodeID) NodeID {
	_, equivNid, err := QuotientParts(k, quotientRecipe)
	if err != nil {
		panic("InternQuotientValue: " + err.Error())
	}
	eq, ok := ResolveEquivalence(k, equivNid)
	if !ok {
		panic("InternQuotientValue: cannot resolve equivalence")
	}

	if eq.Strategy == uint32(StrategyEager) {
		handler, ok := GetHandler(eq.HandlerName)
		if !ok {
			panic("InternQuotientValue: handler vanished mid-call")
		}
		canonical := handler(k, rawChildren)
		category := NodeID{
			Pkg:   1,
			Level: LevelBasic,
			Type:  RBasicQuotient,
			Inst:  2, // canonical-value form
		}
		children := make([]NodeID, 0, len(canonical)+1)
		children = append(children, quotientRecipe)
		children = append(children, canonical...)
		return k.intern(category, children)
	}

	// Lazy: intern the raw form with a distinct inst=3 marker so eager-
	// and lazy-shapes don't collide. The canonical form computed on
	// equality-query shares the inst=2 slot, so once forced both reach
	// the same NodeID.
	category := NodeID{
		Pkg:   1,
		Level: LevelBasic,
		Type:  RBasicQuotient,
		Inst:  3, // lazy raw form
	}
	children := make([]NodeID, 0, len(rawChildren)+1)
	children = append(children, quotientRecipe)
	children = append(children, rawChildren...)
	return k.intern(category, children)
}

// CanonicalForm — force-canonicalize a value (eager or lazy) and return
// its canonical NodeID. Used by equality queries and by callers that
// want to merge equivalent representatives explicitly.
func CanonicalForm(k *Kernel, value NodeID) NodeID {
	if value.Level != LevelBasic || value.Type != RBasicQuotient {
		panic(fmt.Sprintf(
			"CanonicalForm: @%d.%d.%d.%d is not a QUOTIENT value",
			value.Pkg, value.Level, value.Type, value.Inst,
		))
	}
	kids := k.children(value)
	if len(kids) == 0 {
		panic("CanonicalForm: malformed quotient value (no children)")
	}
	if value.Inst == 2 {
		// Already canonical.
		return value
	}
	// Lazy (inst=3) — canonicalize and re-intern as inst=2 form.
	quotientRecipe := kids[0]
	rest := make([]NodeID, len(kids)-1)
	copy(rest, kids[1:])
	_, equivNid, err := QuotientParts(k, quotientRecipe)
	if err != nil {
		panic("CanonicalForm: " + err.Error())
	}
	eq, ok := ResolveEquivalence(k, equivNid)
	if !ok {
		panic("CanonicalForm: cannot resolve equivalence")
	}
	handler, ok := GetHandler(eq.HandlerName)
	if !ok {
		panic("CanonicalForm: handler vanished mid-call")
	}
	canonical := handler(k, rest)
	category := NodeID{
		Pkg:   1,
		Level: LevelBasic,
		Type:  RBasicQuotient,
		Inst:  2,
	}
	children := make([]NodeID, 0, len(canonical)+1)
	children = append(children, quotientRecipe)
	children = append(children, canonical...)
	return k.intern(category, children)
}

// QuotientEqual — equality under the quotient. Two values are equal iff
// their canonical forms share a NodeID.
func QuotientEqual(k *Kernel, a, b NodeID) bool {
	ca := CanonicalForm(k, a)
	cb := CanonicalForm(k, b)
	return ca == cb
}

// ---------------------------------------------------------------------------
// Built-in equivalence relations.
//
// Each registers a handler under a stable name and constructs the
// substrate-resident equivalence-recipe. The names are part of the
// cross-kernel contract — TS / Python / Rust register the same handler
// names so a Form program ingested into any kernel canonicalizes
// identically.
// ---------------------------------------------------------------------------

// handlerIntegerFromNatPair — Integers as Z := (N × N) / ~ where
// (a,b) ~ (c,d) iff a+d = b+c. The canonical representative is (a-b, 0)
// — sign carried by the difference.
func handlerIntegerFromNatPair(k *Kernel, raw []NodeID) []NodeID {
	if len(raw) != 2 {
		panic(fmt.Sprintf("integer-from-nat-pair: expected 2 children, got %d", len(raw)))
	}
	av, ok := readIntTrivial(raw[0])
	if !ok {
		panic("integer-from-nat-pair: child 0 must be int trivial")
	}
	bv, ok := readIntTrivial(raw[1])
	if !ok {
		panic("integer-from-nat-pair: child 1 must be int trivial")
	}
	if av < 0 || bv < 0 {
		panic("integer-from-nat-pair: natural-number pair must be non-negative")
	}
	diff := av - bv
	return []NodeID{k.internTrivialInt(diff), k.internTrivialInt(0)}
}

// gcdInt — Euclidean gcd on signed ints; magnitude-only, never zero.
func gcdInt(a, b int64) int64 {
	if a < 0 {
		a = -a
	}
	if b < 0 {
		b = -b
	}
	for b != 0 {
		a, b = b, a%b
	}
	if a == 0 {
		return 1
	}
	return a
}

// handlerRationalFromIntPair — Rationals as Q := (Z × Z*) / ~ where
// (p,q) ~ (r,s) iff p*s = q*r. Canonical form: (p/gcd, q/gcd) with sign
// normalized into the numerator.
func handlerRationalFromIntPair(k *Kernel, raw []NodeID) []NodeID {
	if len(raw) != 2 {
		panic(fmt.Sprintf("rational-from-int-pair: expected 2 children, got %d", len(raw)))
	}
	p, ok := readIntTrivial(raw[0])
	if !ok {
		panic("rational-from-int-pair: child 0 must be int trivial")
	}
	q, ok := readIntTrivial(raw[1])
	if !ok {
		panic("rational-from-int-pair: child 1 must be int trivial")
	}
	if q == 0 {
		panic("rational-from-int-pair: zero denominator")
	}
	if q < 0 {
		p = -p
		q = -q
	}
	g := gcdInt(p, q)
	return []NodeID{k.internTrivialInt(p / g), k.internTrivialInt(q / g)}
}

// nodeOrderKey — total ordering on NodeIDs by packed (pkg, level, type, inst).
func nodeOrderKeyLess(a, b NodeID) bool {
	if a.Pkg != b.Pkg {
		return a.Pkg < b.Pkg
	}
	if a.Level != b.Level {
		return a.Level < b.Level
	}
	if a.Type != b.Type {
		return a.Type < b.Type
	}
	return a.Inst < b.Inst
}

// handlerCommutativePair — (a, b) ~ (b, a). Canonicalize by sorting on
// the NodeID's packed key.
func handlerCommutativePair(_ *Kernel, raw []NodeID) []NodeID {
	if len(raw) != 2 {
		panic(fmt.Sprintf("commutative-pair: expected 2 children, got %d", len(raw)))
	}
	a, b := raw[0], raw[1]
	if nodeOrderKeyLess(a, b) || a == b {
		return []NodeID{a, b}
	}
	return []NodeID{b, a}
}

// handlerAssociativeLeftFold — no-op flattening at the children-tuple
// layer for this proof-of-shape. Real left-fold canonicalization needs
// recipe-tree access; deferred to the symmetry-aware arm. We still
// return the children unchanged so structurally-equal inputs share a
// NodeID — the minimum the equivalence promises at this layer.
func handlerAssociativeLeftFold(_ *Kernel, raw []NodeID) []NodeID {
	out := make([]NodeID, len(raw))
	copy(out, raw)
	return out
}

// ---------------------------------------------------------------------------
// Bootstrap registration — runs once per process; returns the library
// of built-in EquivalenceRelations. Form code can register more via the
// handler-registry + MakeEquivalence path.
// ---------------------------------------------------------------------------

type QuotientLibrary struct {
	EquivIntegerFromNatPair  EquivalenceRelation
	EquivRationalFromIntPair EquivalenceRelation
	EquivCommutativePair     EquivalenceRelation
	EquivAssociativeLeftFold EquivalenceRelation
}

var bootstrapOnce sync.Once

func bootstrapHandlers() {
	bootstrapOnce.Do(func() {
		RegisterHandler("integer-from-nat-pair", handlerIntegerFromNatPair)
		RegisterHandler("rational-from-int-pair", handlerRationalFromIntPair)
		RegisterHandler("commutative-pair", handlerCommutativePair)
		RegisterHandler("associative-left-fold", handlerAssociativeLeftFold)
	})
}

// BuildQuotientLibrary — bootstrap the built-in equivalence handlers
// (once per process) and intern the four substrate-resident equivalence
// cells against the given Kernel. Repeated calls against the same
// Kernel return content-addressed-identical cells.
func BuildQuotientLibrary(k *Kernel) *QuotientLibrary {
	bootstrapHandlers()
	return &QuotientLibrary{
		EquivIntegerFromNatPair: MakeEquivalence(
			k, "integer-from-nat-pair", DecidableCheap, "integer-from-nat-pair",
		),
		EquivRationalFromIntPair: MakeEquivalence(
			k, "rational-from-int-pair", DecidableCheap, "rational-from-int-pair",
		),
		EquivCommutativePair: MakeEquivalence(
			k, "commutative-pair", DecidableCheap, "commutative-pair",
		),
		EquivAssociativeLeftFold: MakeEquivalence(
			k, "associative-left-fold", DecidableCheap, "associative-left-fold",
		),
	}
}

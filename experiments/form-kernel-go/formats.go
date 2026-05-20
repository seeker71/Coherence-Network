// formats.go — substrate-resident numeric format library for the Go kernel.
//
// Each format is a structural recipe describing semantic-kind, bit-width,
// encoding rules, and implementation hints (storage + arithmetic). The
// kernel reads these recipes at runtime; the Pass 1 handler cache caches
// per-(format, op) closures for monomorphized dispatch.
//
// The canonical bootstrap library is defined in
// docs/coherence-substrate/numeric-formats.canonical.json and read at
// runtime by BuildFormatLibrary. Drift between contract and Go source is
// prevented by reading the JSON instead of hardcoding the list.
//
// See docs/coherence-substrate/numeric-types-plan.md for the architecture
// and experiments/form-kernel-ts-numeric-comparison.md for the perf arc.

package main

import (
	"encoding/json"
	"fmt"
	"math"
	"math/big"
	"os"
	"path/filepath"
	"strconv"
)

// ---------------------------------------------------------------------------
// Canonical constants — must match docs/coherence-substrate/numeric-formats.canonical.json
// ---------------------------------------------------------------------------

// SemanticKind — small stable vocabulary for what a number MEANS.
const (
	SemKindCardinal    uint32 = 1
	SemKindInteger     uint32 = 2
	SemKindRational    uint32 = 3
	SemKindReal        uint32 = 4
	SemKindComplex     uint32 = 5
	SemKindBitPattern  uint32 = 6
	SemKindLogValue    uint32 = 7
	SemKindProbability uint32 = 8
	SemKindInterval    uint32 = 9
	SemKindOrdinal     uint32 = 10
	SemKindAmplitude   uint32 = 11
	SemKindPhase       uint32 = 12
	SemKindMeasure     uint32 = 13
)

// EncodingKind — encoding family. Each carries its own parameter shape.
const (
	EncTwosComplement uint32 = 1
	EncSignMagnitude  uint32 = 2
	EncUnsigned       uint32 = 3
	EncIEEE754        uint32 = 4
	EncPosit          uint32 = 5
	EncLookupTable    uint32 = 6
	EncBlockFP        uint32 = 7
	EncLogSpace       uint32 = 8
	EncRationalPair   uint32 = 9
	EncComplexPair    uint32 = 10
	EncRawBits        uint32 = 11
)

// ArithHintCode — projected from arithmetic-hint string at format
// creation time so the hot path switches on a u8, not a string.
const (
	ArithHintNativeFP             uint32 = 1
	ArithHintNativeInt            uint32 = 2
	ArithHintNativeIntNarrow      uint32 = 3
	ArithHintBigint               uint32 = 4
	ArithHintTableLookupViaFP32   uint32 = 5
	ArithHintDequantFP32ThenNative uint32 = 6
	ArithHintSoftwareFPViaFP32    uint32 = 7
	ArithHintSoftwarePosit        uint32 = 8
	ArithHintXorPopcount          uint32 = 9
	ArithHintLogaddexpLogsubexp   uint32 = 10
	ArithHintRationalBigint       uint32 = 11
)

// ArithOpCode — the five basic operators. Numeric so the inner switch
// is a jump table.
const (
	ArithOpAdd uint32 = 1
	ArithOpSub uint32 = 2
	ArithOpMul uint32 = 3
	ArithOpDiv uint32 = 4
	ArithOpMod uint32 = 5
)

// RBasic slot reservations for format-recipes (50) and numeric-values
// (51). Cross-kernel-coordinated via the canonical JSON.
const (
	RBasicFormat  uint32 = 50
	RBasicNumeric uint32 = 51
)

// ---------------------------------------------------------------------------
// Lookup tables for string → code projection
// ---------------------------------------------------------------------------

var semanticKindByName = map[string]uint32{
	"CARDINAL": SemKindCardinal, "INTEGER": SemKindInteger, "RATIONAL": SemKindRational,
	"REAL": SemKindReal, "COMPLEX": SemKindComplex, "BIT_PATTERN": SemKindBitPattern,
	"LOG_VALUE": SemKindLogValue, "PROBABILITY": SemKindProbability,
	"INTERVAL": SemKindInterval, "ORDINAL": SemKindOrdinal,
	"AMPLITUDE": SemKindAmplitude, "PHASE": SemKindPhase, "MEASURE": SemKindMeasure,
}

var encodingByName = map[string]uint32{
	"TWOS_COMPLEMENT": EncTwosComplement, "SIGN_MAGNITUDE": EncSignMagnitude,
	"UNSIGNED": EncUnsigned, "IEEE_754": EncIEEE754, "POSIT": EncPosit,
	"LOOKUP_TABLE": EncLookupTable, "BLOCK_FP": EncBlockFP,
	"LOG_SPACE": EncLogSpace, "RATIONAL_PAIR": EncRationalPair,
	"COMPLEX_PAIR": EncComplexPair, "RAW_BITS": EncRawBits,
}

var arithHintByName = map[string]uint32{
	"native-fp": ArithHintNativeFP, "native-int": ArithHintNativeInt,
	"native-int-narrow": ArithHintNativeIntNarrow, "bigint": ArithHintBigint,
	"table-lookup-via-fp32": ArithHintTableLookupViaFP32,
	"dequant-fp32-then-native": ArithHintDequantFP32ThenNative,
	"software-fp-via-fp32": ArithHintSoftwareFPViaFP32,
	"software-posit": ArithHintSoftwarePosit, "xor-popcount": ArithHintXorPopcount,
	"logaddexp-logsubexp": ArithHintLogaddexpLogsubexp,
	"rational-bigint": ArithHintRationalBigint,
}

var arithOpByName = map[string]uint32{
	"add": ArithOpAdd, "sub": ArithOpSub, "mul": ArithOpMul,
	"div": ArithOpDiv, "mod": ArithOpMod,
}

// ---------------------------------------------------------------------------
// FormatRecipe — interned format identity + cached parameters
// ---------------------------------------------------------------------------

// FormatRecipe mirrors the canonical JSON's format entry plus the kernel
// NodeID that identifies the interned recipe. Values are precomputed for
// fast in-kernel access without re-reading the substrate tree per op.
type FormatRecipe struct {
	NodeID         NodeID
	Name           string
	SemanticKind   uint32
	Encoding       uint32
	Bits           uint32
	StorageHint    string
	ArithmeticHint string
	ArithHintCode  uint32
	// Encoding-specific
	MantissaBits *uint32
	ExponentBits *uint32
	ExponentBias *uint32
	PositN       *uint32
	PositEs      *uint32
	LookupValues []float64
}

// ---------------------------------------------------------------------------
// Canonical JSON — on-disk contract
// ---------------------------------------------------------------------------

type canonicalFormat struct {
	Name           string    `json:"name"`
	SemanticKind   string    `json:"semantic_kind"`
	Encoding       string    `json:"encoding"`
	Bits           uint32    `json:"bits"`
	StorageHint    string    `json:"storage_hint"`
	ArithmeticHint string    `json:"arithmetic_hint"`
	MantissaBits   *uint32   `json:"mantissa_bits,omitempty"`
	ExponentBits   *uint32   `json:"exponent_bits,omitempty"`
	ExponentBias   *uint32   `json:"exponent_bias,omitempty"`
	PositN         *uint32   `json:"posit_n,omitempty"`
	PositEs        *uint32   `json:"posit_es,omitempty"`
	LookupValues   []float64 `json:"lookup_values,omitempty"`
}

type canonicalVector struct {
	Format   string      `json:"format"`
	Op       string      `json:"op"`
	A        interface{} `json:"a"`
	B        interface{} `json:"b"`
	Expected interface{} `json:"expected"`
	Note     string      `json:"$note,omitempty"`
}

type canonicalCanonVector struct {
	Format    string      `json:"format"`
	ValueA    interface{} `json:"value_a"`
	ValueB    interface{} `json:"value_b"`
	SameNode  bool        `json:"same_nodeid"`
}

type canonicalContract struct {
	Version uint32             `json:"version"`
	Formats []canonicalFormat  `json:"formats"`
	Conform struct {
		Vectors  []canonicalVector       `json:"vectors"`
		CanonVec []canonicalCanonVector  `json:"canonicalization_vectors"`
	} `json:"conformance_vectors"`
}

// LocateCanonicalJSON — find numeric-formats.canonical.json by walking
// up from the executable's working directory. Lets `go test` from the
// kernel directory and `--numeric-bench` from any cwd both succeed.
func LocateCanonicalJSON() (string, error) {
	candidates := []string{
		"../../docs/coherence-substrate/numeric-formats.canonical.json",
		"../docs/coherence-substrate/numeric-formats.canonical.json",
		"docs/coherence-substrate/numeric-formats.canonical.json",
	}
	cwd, _ := os.Getwd()
	for _, rel := range candidates {
		p := filepath.Join(cwd, rel)
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
	}
	// Walk up from cwd looking for docs/coherence-substrate/.
	dir := cwd
	for i := 0; i < 8; i++ {
		p := filepath.Join(dir, "docs", "coherence-substrate", "numeric-formats.canonical.json")
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "", fmt.Errorf("could not locate numeric-formats.canonical.json")
}

func loadCanonicalContract() (*canonicalContract, error) {
	p, err := LocateCanonicalJSON()
	if err != nil {
		return nil, err
	}
	b, err := os.ReadFile(p)
	if err != nil {
		return nil, fmt.Errorf("read canonical JSON: %w", err)
	}
	var c canonicalContract
	if err := json.Unmarshal(b, &c); err != nil {
		return nil, fmt.Errorf("parse canonical JSON: %w", err)
	}
	return &c, nil
}

// ---------------------------------------------------------------------------
// FormatLibrary — interned bootstrap formats keyed by name
// ---------------------------------------------------------------------------

type FormatLibrary struct {
	ByName  map[string]*FormatRecipe
	ByOrder []*FormatRecipe
	// Convenience accessors for hot formats — match the TS lib field names.
	FP64        *FormatRecipe
	FP32        *FormatRecipe
	BF16        *FormatRecipe
	FP8E4M3     *FormatRecipe
	FP8E5M2     *FormatRecipe
	FP4Uniform  *FormatRecipe
	NF4         *FormatRecipe
	INT8        *FormatRecipe
	INT16       *FormatRecipe
	INT32       *FormatRecipe
	INT64       *FormatRecipe
	UINT8       *FormatRecipe
	UINT16      *FormatRecipe
	UINT32      *FormatRecipe
	UINT64      *FormatRecipe
	INT4        *FormatRecipe
	Bitnet158   *FormatRecipe
	Bit1        *FormatRecipe
	LogProb     *FormatRecipe
}

// makeFormatRecipe — intern a format-recipe with children in the canonical
// order. Mirrors makeFormatRecipe() in formats.ts; the child-vector shape
// determines the content-addressed NodeID.
//
// Children laid out as (per $intern_order_comment in the JSON):
//   [0] semanticKind  (trivial int)
//   [1] encoding      (trivial int)
//   [2] bits          (trivial int)
//   [3] storageHint   (interned string)
//   [4] arithmeticHint(interned string)
// Then optional extras in this order (only those present):
//   mantissaBits, exponentBits, exponentBias, positN, positEs, lookupValues
//
// Lookup values: each float64 contributes TWO i32 children — low 32 bits
// of the IEEE 754 double, then high 32 bits, both as trivial-int with
// signed-32 reinterpretation matching the TS `... | 0` coercion.
func makeFormatRecipe(k *Kernel, cf canonicalFormat) (*FormatRecipe, error) {
	semKind, ok := semanticKindByName[cf.SemanticKind]
	if !ok {
		return nil, fmt.Errorf("unknown semantic_kind %q for format %q", cf.SemanticKind, cf.Name)
	}
	enc, ok := encodingByName[cf.Encoding]
	if !ok {
		return nil, fmt.Errorf("unknown encoding %q for format %q", cf.Encoding, cf.Name)
	}
	ahCode, ok := arithHintByName[cf.ArithmeticHint]
	if !ok {
		return nil, fmt.Errorf("unknown arithmetic_hint %q for format %q", cf.ArithmeticHint, cf.Name)
	}

	children := []NodeID{
		k.internTrivialInt(int64(semKind)),
		k.internTrivialInt(int64(enc)),
		k.internTrivialInt(int64(cf.Bits)),
		k.internString(cf.StorageHint),
		k.internString(cf.ArithmeticHint),
	}
	if cf.MantissaBits != nil {
		children = append(children, k.internTrivialInt(int64(*cf.MantissaBits)))
	}
	if cf.ExponentBits != nil {
		children = append(children, k.internTrivialInt(int64(*cf.ExponentBits)))
	}
	if cf.ExponentBias != nil {
		children = append(children, k.internTrivialInt(int64(*cf.ExponentBias)))
	}
	if cf.PositN != nil {
		children = append(children, k.internTrivialInt(int64(*cf.PositN)))
	}
	if cf.PositEs != nil {
		children = append(children, k.internTrivialInt(int64(*cf.PositEs)))
	}
	if len(cf.LookupValues) > 0 {
		for _, v := range cf.LookupValues {
			bits := math.Float64bits(v)
			lo := int32(bits & 0xffffffff)
			hi := int32(bits >> 32)
			children = append(children, k.internTrivialInt(int64(lo)))
			children = append(children, k.internTrivialInt(int64(hi)))
		}
	}

	cat := NodeID{Pkg: 1, Level: LevelBasic, Type: RBasicFormat, Inst: enc}
	nid := k.intern(cat, children)
	fr := &FormatRecipe{
		NodeID:         nid,
		Name:           cf.Name,
		SemanticKind:   semKind,
		Encoding:       enc,
		Bits:           cf.Bits,
		StorageHint:    cf.StorageHint,
		ArithmeticHint: cf.ArithmeticHint,
		ArithHintCode:  ahCode,
		MantissaBits:   cf.MantissaBits,
		ExponentBits:   cf.ExponentBits,
		ExponentBias:   cf.ExponentBias,
		PositN:         cf.PositN,
		PositEs:        cf.PositEs,
		LookupValues:   cf.LookupValues,
	}
	return fr, nil
}

// BuildFormatLibrary — read the canonical JSON, intern each format in
// listed order, populate the library by name and by ordered slot.
//
// The intern-order matters for cross-kernel content-addressing: two
// kernels interning the same recipes in the same sequence produce the
// same structural NodeIDs (modulo string-name-id alignment, which is
// kernel-local).
func BuildFormatLibrary(k *Kernel) (*FormatLibrary, error) {
	c, err := loadCanonicalContract()
	if err != nil {
		return nil, err
	}
	lib := &FormatLibrary{
		ByName: make(map[string]*FormatRecipe, len(c.Formats)),
	}
	for _, cf := range c.Formats {
		fr, err := makeFormatRecipe(k, cf)
		if err != nil {
			return nil, err
		}
		lib.ByName[cf.Name] = fr
		lib.ByOrder = append(lib.ByOrder, fr)
	}
	lib.FP64 = lib.ByName["fp64"]
	lib.FP32 = lib.ByName["fp32"]
	lib.BF16 = lib.ByName["bf16"]
	lib.FP8E4M3 = lib.ByName["fp8-e4m3"]
	lib.FP8E5M2 = lib.ByName["fp8-e5m2"]
	lib.FP4Uniform = lib.ByName["fp4-uniform"]
	lib.NF4 = lib.ByName["nf4"]
	lib.INT8 = lib.ByName["i8"]
	lib.INT16 = lib.ByName["i16"]
	lib.INT32 = lib.ByName["i32"]
	lib.INT64 = lib.ByName["i64"]
	lib.UINT8 = lib.ByName["u8"]
	lib.UINT16 = lib.ByName["u16"]
	lib.UINT32 = lib.ByName["u32"]
	lib.UINT64 = lib.ByName["u64"]
	lib.INT4 = lib.ByName["i4"]
	lib.Bitnet158 = lib.ByName["bitnet-158"]
	lib.Bit1 = lib.ByName["bit-1"]
	lib.LogProb = lib.ByName["log-prob"]
	return lib, nil
}

// ---------------------------------------------------------------------------
// Numeric value carrier — used by the bench and arithmetic dispatchers.
// ---------------------------------------------------------------------------

// NumValueKind discriminates the storage class of a numeric value held
// outside the substrate. Pass 0 / Pass 1 arithmetic both consume Values
// and return Values; the bigint path routes through math/big.Int because
// uint32 NodeID Inst can't carry 64-bit operands.
type NumValueKind uint8

const (
	NumF64 NumValueKind = iota
	NumI64
	NumBig
)

// NumValue — tagged carrier for cross-format arithmetic results. The
// existing kernel Value struct already covers int/float for trivials;
// this is the bench-and-test specific shape that adds big.Int for
// formats whose arithmetic-hint = "bigint". Documented routing: 64-bit
// integer values that don't fit NodeID.Inst (uint32) live as *big.Int.
type NumValue struct {
	Kind NumValueKind
	F    float64
	I    int64
	Big  *big.Int
}

func NV_F(f float64) NumValue          { return NumValue{Kind: NumF64, F: f} }
func NV_I(i int64) NumValue            { return NumValue{Kind: NumI64, I: i} }
func NV_Big(b *big.Int) NumValue       { return NumValue{Kind: NumBig, Big: b} }
func NV_BigFromInt64(i int64) NumValue { return NumValue{Kind: NumBig, Big: big.NewInt(i)} }

func (v NumValue) AsFloat() float64 {
	switch v.Kind {
	case NumF64:
		return v.F
	case NumI64:
		return float64(v.I)
	case NumBig:
		f, _ := new(big.Float).SetInt(v.Big).Float64()
		return f
	}
	return 0
}

func (v NumValue) AsInt64() int64 {
	switch v.Kind {
	case NumF64:
		return int64(v.F)
	case NumI64:
		return v.I
	case NumBig:
		return v.Big.Int64()
	}
	return 0
}

func (v NumValue) AsBig() *big.Int {
	switch v.Kind {
	case NumBig:
		return v.Big
	case NumI64:
		return big.NewInt(v.I)
	case NumF64:
		return big.NewInt(int64(v.F))
	}
	return big.NewInt(0)
}

func (v NumValue) String() string {
	switch v.Kind {
	case NumF64:
		return strconv.FormatFloat(v.F, 'g', -1, 64)
	case NumI64:
		return strconv.FormatInt(v.I, 10)
	case NumBig:
		return v.Big.String()
	}
	return "?"
}

// ---------------------------------------------------------------------------
// Pass 0 — generic arithmetic dispatcher (mirror of applyArith in TS)
// ---------------------------------------------------------------------------

// applyArith — Pass 0: switch on arithmetic-hint code, then on op code.
// Generic, no caching. Used by the walker for cold paths and as the
// baseline for the bench comparison.
func applyArith(fmt *FormatRecipe, op uint32, a, b NumValue) NumValue {
	switch fmt.ArithHintCode {
	case ArithHintNativeFP:
		fa, fb := a.AsFloat(), b.AsFloat()
		switch op {
		case ArithOpAdd:
			return NV_F(fa + fb)
		case ArithOpSub:
			return NV_F(fa - fb)
		case ArithOpMul:
			return NV_F(fa * fb)
		case ArithOpDiv:
			return NV_F(fa / fb)
		case ArithOpMod:
			return NV_F(fa - math.Floor(fa/fb)*fb)
		}
		return NV_F(0)
	case ArithHintNativeInt:
		ia, ib := int32(a.AsInt64()), int32(b.AsInt64())
		switch op {
		case ArithOpAdd:
			return NV_I(int64(int32(ia + ib)))
		case ArithOpSub:
			return NV_I(int64(int32(ia - ib)))
		case ArithOpMul:
			return NV_I(int64(int32(ia * ib)))
		case ArithOpDiv:
			if ib == 0 {
				return NV_I(0)
			}
			return NV_I(int64(int32(ia / ib)))
		case ArithOpMod:
			if ib == 0 {
				return NV_I(0)
			}
			return NV_I(int64(int32(ia - (ia/ib)*ib)))
		}
		return NV_I(0)
	case ArithHintNativeIntNarrow:
		ia, ib := int32(a.AsInt64()), int32(b.AsInt64())
		bits := fmt.Bits
		switch op {
		case ArithOpAdd:
			return NV_I(int64(narrowInt(ia+ib, bits)))
		case ArithOpSub:
			return NV_I(int64(narrowInt(ia-ib, bits)))
		case ArithOpMul:
			return NV_I(int64(narrowInt(ia*ib, bits)))
		case ArithOpDiv:
			if ib == 0 {
				return NV_I(0)
			}
			return NV_I(int64(narrowInt(ia/ib, bits)))
		case ArithOpMod:
			if ib == 0 {
				return NV_I(0)
			}
			return NV_I(int64(narrowInt(ia-(ia/ib)*ib, bits)))
		}
		return NV_I(0)
	case ArithHintBigint:
		ba, bb := a.AsBig(), b.AsBig()
		out := new(big.Int)
		switch op {
		case ArithOpAdd:
			out.Add(ba, bb)
		case ArithOpSub:
			out.Sub(ba, bb)
		case ArithOpMul:
			out.Mul(ba, bb)
		case ArithOpDiv:
			if bb.Sign() == 0 {
				return NV_Big(big.NewInt(0))
			}
			out.Quo(ba, bb)
		case ArithOpMod:
			if bb.Sign() == 0 {
				return NV_Big(big.NewInt(0))
			}
			out.Rem(ba, bb)
		}
		return NV_Big(out)
	case ArithHintTableLookupViaFP32, ArithHintDequantFP32ThenNative, ArithHintSoftwareFPViaFP32:
		fa, fb := a.AsFloat(), b.AsFloat()
		switch op {
		case ArithOpAdd:
			return NV_F(float64(float32(fa + fb)))
		case ArithOpSub:
			return NV_F(float64(float32(fa - fb)))
		case ArithOpMul:
			return NV_F(float64(float32(fa * fb)))
		case ArithOpDiv:
			return NV_F(float64(float32(fa / fb)))
		case ArithOpMod:
			return NV_F(float64(float32(fa - math.Floor(fa/fb)*fb)))
		}
		return NV_F(0)
	case ArithHintLogaddexpLogsubexp:
		la, lb := a.AsFloat(), b.AsFloat()
		switch op {
		case ArithOpAdd:
			m := math.Max(la, lb)
			return NV_F(m + math.Log1p(math.Exp(-math.Abs(la-lb))))
		case ArithOpSub:
			if lb >= la {
				return NV_F(math.Inf(-1))
			}
			return NV_F(la + math.Log1p(-math.Exp(lb-la)))
		case ArithOpMul:
			return NV_F(la + lb)
		case ArithOpDiv:
			return NV_F(la - lb)
		case ArithOpMod:
			panic("log-prob: mod not defined")
		}
		return NV_F(0)
	case ArithHintXorPopcount:
		ia, ib := int32(a.AsInt64()), int32(b.AsInt64())
		switch op {
		case ArithOpAdd, ArithOpSub:
			return NV_I(int64((ia ^ ib) & 1))
		case ArithOpMul:
			return NV_I(int64(ia & ib & 1))
		case ArithOpDiv, ArithOpMod:
			return NV_I(0)
		}
		return NV_I(0)
	case ArithHintSoftwarePosit, ArithHintRationalBigint:
		panic(fmt2("arithmetic-hint %s: not yet implemented", fmt.ArithmeticHint))
	}
	return NV_F(0)
}

func fmt2(f string, a ...any) string { return fmt.Sprintf(f, a...) }

// narrowInt — sign-extend an int32 result truncated to `bits` width.
// Mirror of narrowInt() in formats.ts.
func narrowInt(v int32, bits uint32) int32 {
	if bits >= 32 {
		return v
	}
	mask := int32((1 << bits) - 1)
	signBit := int32(1 << (bits - 1))
	u := v & mask
	if u&signBit != 0 {
		return u | ^mask
	}
	return u
}

// ---------------------------------------------------------------------------
// Canonicalization — collapse equivalent values to a single representation
// before content-addressing so two intern calls with the same logical
// value get the same NodeID.
// ---------------------------------------------------------------------------

func canonicalize(fmt *FormatRecipe, v NumValue) NumValue {
	switch fmt.ArithHintCode {
	case ArithHintNativeFP, ArithHintTableLookupViaFP32,
		ArithHintDequantFP32ThenNative, ArithHintSoftwareFPViaFP32,
		ArithHintLogaddexpLogsubexp:
		f := v.AsFloat()
		if math.IsNaN(f) {
			return NV_F(math.NaN())
		}
		if f == 0 {
			return NV_F(0) // collapses -0 → +0
		}
		return NV_F(f)
	}
	return v
}

// ---------------------------------------------------------------------------
// Pass 1 — per-(format, op) handler closures cached in FormatTable
// ---------------------------------------------------------------------------

// FormatTable — handle assignment + Pass 1 handler cache.
//
// Pass 1 efficiency: the cache produces a closure `func(NumValue, NumValue) NumValue`
// for each (format, op) on first request. The closure captures the
// format's arithmetic path WITHOUT the outer hint/op switches. Go's
// inliner monomorphizes these closures after a few invocations.
//
// Go's compiler is less aggressive at runtime than V8 JIT, so the win
// over Pass 0 here is smaller than in TS — but the abstraction shape is
// the same. Production hot paths route through the closure cache; cold
// paths use applyArith directly.
type FormatTable struct {
	byHandle []*FormatRecipe
	byNodeID map[NodeID]int
	handlers map[uint64]NumHandler
}

// NumHandler — per-(format, op) closure type.
type NumHandler func(a, b NumValue) NumValue

func NewFormatTable() *FormatTable {
	return &FormatTable{
		byNodeID: make(map[NodeID]int),
		handlers: make(map[uint64]NumHandler),
	}
}

func (t *FormatTable) Register(fmt *FormatRecipe) int {
	if h, ok := t.byNodeID[fmt.NodeID]; ok {
		return h
	}
	h := len(t.byHandle)
	t.byHandle = append(t.byHandle, fmt)
	t.byNodeID[fmt.NodeID] = h
	return h
}

func (t *FormatTable) Get(h int) *FormatRecipe {
	if h < 0 || h >= len(t.byHandle) {
		return nil
	}
	return t.byHandle[h]
}

// Handler — get-or-build the cached closure for (format-handle, op).
func (t *FormatTable) Handler(h int, op uint32) NumHandler {
	key := (uint64(h) << 8) | uint64(op)
	if fn, ok := t.handlers[key]; ok {
		return fn
	}
	fr := t.byHandle[h]
	fn := compileHandler(fr, op)
	t.handlers[key] = fn
	return fn
}

// RegisterAll — register every format in the library. Handle assignment
// follows ByOrder so handle indices are deterministic with respect to
// the canonical JSON.
func (t *FormatTable) RegisterAll(lib *FormatLibrary) {
	for _, fr := range lib.ByOrder {
		t.Register(fr)
	}
}

// compileHandler — emit a Go closure specialized to (format, op). The
// outer hint switch happens once; the returned closure does ONLY the op.
// Go's inliner/SSA can then specialize the closure's body when invoked
// repeatedly from a hot loop.
func compileHandler(fr *FormatRecipe, op uint32) NumHandler {
	switch fr.ArithHintCode {
	case ArithHintNativeFP:
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() + b.AsFloat()) }
		case ArithOpSub:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() - b.AsFloat()) }
		case ArithOpMul:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() * b.AsFloat()) }
		case ArithOpDiv:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() / b.AsFloat()) }
		case ArithOpMod:
			return func(a, b NumValue) NumValue {
				fa, fb := a.AsFloat(), b.AsFloat()
				return NV_F(fa - math.Floor(fa/fb)*fb)
			}
		}
	case ArithHintNativeInt:
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue { return NV_I(int64(int32(a.AsInt64()) + int32(b.AsInt64()))) }
		case ArithOpSub:
			return func(a, b NumValue) NumValue { return NV_I(int64(int32(a.AsInt64()) - int32(b.AsInt64()))) }
		case ArithOpMul:
			return func(a, b NumValue) NumValue { return NV_I(int64(int32(a.AsInt64()) * int32(b.AsInt64()))) }
		case ArithOpDiv:
			return func(a, b NumValue) NumValue {
				ib := int32(b.AsInt64())
				if ib == 0 {
					return NV_I(0)
				}
				return NV_I(int64(int32(a.AsInt64()) / ib))
			}
		case ArithOpMod:
			return func(a, b NumValue) NumValue {
				ia, ib := int32(a.AsInt64()), int32(b.AsInt64())
				if ib == 0 {
					return NV_I(0)
				}
				return NV_I(int64(ia - (ia/ib)*ib))
			}
		}
	case ArithHintNativeIntNarrow:
		bits := fr.Bits
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue {
				return NV_I(int64(narrowInt(int32(a.AsInt64())+int32(b.AsInt64()), bits)))
			}
		case ArithOpSub:
			return func(a, b NumValue) NumValue {
				return NV_I(int64(narrowInt(int32(a.AsInt64())-int32(b.AsInt64()), bits)))
			}
		case ArithOpMul:
			return func(a, b NumValue) NumValue {
				return NV_I(int64(narrowInt(int32(a.AsInt64())*int32(b.AsInt64()), bits)))
			}
		case ArithOpDiv:
			return func(a, b NumValue) NumValue {
				ib := int32(b.AsInt64())
				if ib == 0 {
					return NV_I(0)
				}
				return NV_I(int64(narrowInt(int32(a.AsInt64())/ib, bits)))
			}
		case ArithOpMod:
			return func(a, b NumValue) NumValue {
				ia, ib := int32(a.AsInt64()), int32(b.AsInt64())
				if ib == 0 {
					return NV_I(0)
				}
				return NV_I(int64(narrowInt(ia-(ia/ib)*ib, bits)))
			}
		}
	case ArithHintBigint:
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue { return NV_Big(new(big.Int).Add(a.AsBig(), b.AsBig())) }
		case ArithOpSub:
			return func(a, b NumValue) NumValue { return NV_Big(new(big.Int).Sub(a.AsBig(), b.AsBig())) }
		case ArithOpMul:
			return func(a, b NumValue) NumValue { return NV_Big(new(big.Int).Mul(a.AsBig(), b.AsBig())) }
		case ArithOpDiv:
			return func(a, b NumValue) NumValue {
				bb := b.AsBig()
				if bb.Sign() == 0 {
					return NV_Big(big.NewInt(0))
				}
				return NV_Big(new(big.Int).Quo(a.AsBig(), bb))
			}
		case ArithOpMod:
			return func(a, b NumValue) NumValue {
				bb := b.AsBig()
				if bb.Sign() == 0 {
					return NV_Big(big.NewInt(0))
				}
				return NV_Big(new(big.Int).Rem(a.AsBig(), bb))
			}
		}
	case ArithHintTableLookupViaFP32, ArithHintDequantFP32ThenNative, ArithHintSoftwareFPViaFP32:
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue { return NV_F(float64(float32(a.AsFloat() + b.AsFloat()))) }
		case ArithOpSub:
			return func(a, b NumValue) NumValue { return NV_F(float64(float32(a.AsFloat() - b.AsFloat()))) }
		case ArithOpMul:
			return func(a, b NumValue) NumValue { return NV_F(float64(float32(a.AsFloat() * b.AsFloat()))) }
		case ArithOpDiv:
			return func(a, b NumValue) NumValue { return NV_F(float64(float32(a.AsFloat() / b.AsFloat()))) }
		case ArithOpMod:
			return func(a, b NumValue) NumValue {
				fa, fb := a.AsFloat(), b.AsFloat()
				return NV_F(float64(float32(fa - math.Floor(fa/fb)*fb)))
			}
		}
	case ArithHintLogaddexpLogsubexp:
		switch op {
		case ArithOpAdd:
			return func(a, b NumValue) NumValue {
				la, lb := a.AsFloat(), b.AsFloat()
				m := math.Max(la, lb)
				return NV_F(m + math.Log1p(math.Exp(-math.Abs(la-lb))))
			}
		case ArithOpSub:
			return func(a, b NumValue) NumValue {
				la, lb := a.AsFloat(), b.AsFloat()
				if lb >= la {
					return NV_F(math.Inf(-1))
				}
				return NV_F(la + math.Log1p(-math.Exp(lb-la)))
			}
		case ArithOpMul:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() + b.AsFloat()) }
		case ArithOpDiv:
			return func(a, b NumValue) NumValue { return NV_F(a.AsFloat() - b.AsFloat()) }
		case ArithOpMod:
			return func(a, b NumValue) NumValue { panic("log-prob: mod not defined") }
		}
	case ArithHintXorPopcount:
		switch op {
		case ArithOpAdd, ArithOpSub:
			return func(a, b NumValue) NumValue {
				return NV_I(int64((int32(a.AsInt64()) ^ int32(b.AsInt64())) & 1))
			}
		case ArithOpMul:
			return func(a, b NumValue) NumValue {
				return NV_I(int64(int32(a.AsInt64()) & int32(b.AsInt64()) & 1))
			}
		case ArithOpDiv, ArithOpMod:
			return func(a, b NumValue) NumValue { return NV_I(0) }
		}
	}
	// Fallback: cache miss for an unsupported (hint, op) — defer to Pass 0.
	return func(a, b NumValue) NumValue {
		return applyArith(fr, op, a, b)
	}
}

// ---------------------------------------------------------------------------
// Overflow routing for values that don't fit NodeID.Inst (uint32)
// ---------------------------------------------------------------------------
//
// The substrate's NodeID.Inst is a uint32 — fine for int32 and most
// CPU-native ints. For 64-bit integers (i64/u64) and arbitrary floats
// (fp64), we route through the existing intern-string mechanism: format
// the value as a deterministic canonical string and intern it, then
// store the resulting NodeID alongside the format-recipe handle as a
// child trivial.
//
// This keeps the Go kernel's existing trivial-slot vocabulary unchanged
// while still letting numeric values participate in content-addressing.

func internOverflowFloat64(k *Kernel, v float64) NodeID {
	// Canonicalize NaN and -0 before stringifying so equivalent values
	// share a NodeID.
	if math.IsNaN(v) {
		return k.internString("f64:NaN")
	}
	if v == 0 {
		v = 0 // collapse -0 → +0
	}
	return k.internString("f64:" + strconv.FormatFloat(v, 'b', -1, 64))
}

func internOverflowInt64(k *Kernel, v int64) NodeID {
	return k.internString("i64:" + strconv.FormatInt(v, 10))
}

func internOverflowBig(k *Kernel, v *big.Int) NodeID {
	return k.internString("big:" + v.String())
}

// core/core.go — the kernel's shared value/recipe type cluster, extracted from
// package main so JIT-compiled plugins can import it. A Go plugin is itself
// package main and cannot import the kernel's main; putting Value/NodeID/Frame/
// Record/Closure here lets the kernel binary AND every JIT'd plugin share the
// same types. This is the foundation for compiling ANY recipe to a native
// plugin: the generated plugin operates on core.Value, calls natives, runs
// native — no walk-interpreter overhead. (Verified mechanism: a plugin importing
// a shared package took/returned shared Values + called shared funcs correctly.)
//
// The cluster is pure data + pure methods — no *Kernel coupling — which is what
// makes the extraction clean. Fields the kernel reaches externally are exported.
package core

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

// NodeID — a substrate coordinate (package, level, type, instance).
type NodeID struct{ Pkg, Level, Type, Inst uint32 }

// NameID — interned-string handle.
type NameID uint32

// ValueKind — the runtime value tag.
type ValueKind int

const (
	VNull ValueKind = iota
	VInt
	VStr
	VBool
	VList
	VClosure
	VNodeID
	VFloat
	VRecord
)

// recField — one (name, value) entry of a Record. Unexported type; exported
// fields so the kernel can read them via Record.Fields.
type recField struct {
	Name NameID
	Val  Value
}

// Record — a mutable struct/object. Blueprint tags its type; Fields is an
// ordered name→value map.
type Record struct {
	Blueprint NodeID
	Fields    []recField
}

func (r *Record) Get(name NameID) (Value, bool) {
	for i := len(r.Fields) - 1; i >= 0; i-- {
		if r.Fields[i].Name == name {
			return r.Fields[i].Val, true
		}
	}
	return Value{Kind: VNull}, false
}

func (r *Record) Set(name NameID, val Value) {
	for i := range r.Fields {
		if r.Fields[i].Name == name {
			r.Fields[i].Val = val
			return
		}
	}
	r.Fields = append(r.Fields, recField{Name: name, Val: val})
}

// Closure — a Form function value: params, body recipe, captured frame.
type Closure struct {
	Name   NameID
	Params []NameID
	Body   NodeID
	Env    *Frame
}

// binding — one (name, value) of a Frame. Unexported type, exported fields.
type binding struct {
	Name NameID
	Val  Value
}

// Frame — a lexical environment: bindings + parent link.
type Frame struct {
	Parent   *Frame
	Bindings []binding
}

func NewFrame(parent *Frame) *Frame { return &Frame{Parent: parent} }

// NewCallFrame — pre-sized for a function call with `arity` params.
func NewCallFrame(parent *Frame, arity int) *Frame {
	return &Frame{Parent: parent, Bindings: make([]binding, 0, arity)}
}

func (f *Frame) Bind(name NameID, v Value) {
	for i := range f.Bindings {
		if f.Bindings[i].Name == name {
			f.Bindings[i].Val = v
			return
		}
	}
	f.Bindings = append(f.Bindings, binding{name, v})
}

func (f *Frame) Lookup(name NameID) (Value, bool) {
	for cur := f; cur != nil; cur = cur.Parent {
		for i := range cur.Bindings {
			if cur.Bindings[i].Name == name {
				return cur.Bindings[i].Val, true
			}
		}
	}
	return Value{}, false
}

// Value — runtime tagged union. List and Closure carry pointers; the rest are
// inline. Flat struct so the hot path is allocation-free for ints and bools.
type Value struct {
	Kind  ValueKind
	Int   int64
	Float float64
	Str   string
	Bool  bool
	List  []Value
	Cl    *Closure
	Nid   NodeID
	Rec   *Record
}

func (v Value) String() string {
	switch v.Kind {
	case VNull:
		return "null"
	case VInt:
		return strconv.FormatInt(v.Int, 10)
	case VFloat:
		return FormatFloatJS(v.Float)
	case VStr:
		return v.Str
	case VBool:
		if v.Bool {
			return "true"
		}
		return "false"
	case VList:
		parts := make([]string, len(v.List))
		for i, x := range v.List {
			parts[i] = x.String()
		}
		return "[" + strings.Join(parts, ", ") + "]"
	case VClosure:
		return "<closure #" + strconv.FormatUint(uint64(v.Cl.Name), 10) + ">"
	case VNodeID:
		return fmt.Sprintf("@%d.%d.%d.%d", v.Nid.Pkg, v.Nid.Level, v.Nid.Type, v.Nid.Inst)
	case VRecord:
		return fmt.Sprintf("<record @%d.%d.%d.%d #%dfields>",
			v.Rec.Blueprint.Pkg, v.Rec.Blueprint.Level, v.Rec.Blueprint.Type,
			v.Rec.Blueprint.Inst, len(v.Rec.Fields))
	}
	return "?"
}

func (v Value) AsFloat() float64 {
	switch v.Kind {
	case VFloat:
		return v.Float
	case VInt:
		return float64(v.Int)
	case VBool:
		if v.Bool {
			return 1.0
		}
		return 0.0
	}
	panic(fmt.Sprintf("AsFloat: %v", v))
}

// AsNid — the NodeID-typed boundary: only a VNodeID passes. Reading .Nid
// raw on any other kind yields the zero NodeID — a silent false positive
// (two mistyped values "agree"); naming the violation is the honest answer.
// Sibling to Rust's as_nid and TS's argNodeID.
func (v Value) AsNid() NodeID {
	if v.Kind == VNodeID {
		return v.Nid
	}
	panic(fmt.Sprintf("as_nid: %v", v))
}

// AsInt — the integer lane's coercion: ints pass through, floats truncate,
// bools are the 0/1 states (axiom-1, core-axioms.form). Any other kind is a
// type-contract violation — str_eq, node_eq, and value_eq are the typed
// doors for those kinds. Sibling to Rust's as_int and the TS compare lane.
func (v Value) AsInt() int64 {
	switch v.Kind {
	case VInt:
		return v.Int
	case VFloat:
		return int64(v.Float)
	case VBool:
		if v.Bool {
			return 1
		}
		return 0
	}
	panic(fmt.Sprintf("as_int: %v", v))
}

// FormatFloatJS — JS String(number) semantics: shortest round-trippable form,
// NaN/Infinity spelled out.
func FormatFloatJS(f float64) string {
	if math.IsNaN(f) {
		return "NaN"
	}
	if math.IsInf(f, 1) {
		return "Infinity"
	}
	if math.IsInf(f, -1) {
		return "-Infinity"
	}
	return strconv.FormatFloat(f, 'g', -1, 64)
}

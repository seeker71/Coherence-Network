package jitabi

type Kind uint8

const (
	NullKind Kind = iota
	IntKind
	FloatKind
	StrKind
	BoolKind
	ListKind
	NodeKind
)

type NodeID struct {
	Pkg, Level, Type, Inst uint32
}

type Value struct {
	Kind  Kind
	Int   int64
	Float float64
	Str   string
	Bool  bool
	List  []Value
	Node  NodeID
}

func Null() Value            { return Value{Kind: NullKind} }
func Int(v int64) Value      { return Value{Kind: IntKind, Int: v} }
func Float(v float64) Value  { return Value{Kind: FloatKind, Float: v} }
func Str(v string) Value     { return Value{Kind: StrKind, Str: v} }
func Bool(v bool) Value      { return Value{Kind: BoolKind, Bool: v} }
func List(xs ...Value) Value { return Value{Kind: ListKind, List: xs} }
func Node(pkg, level, typ, inst uint32) Value {
	return Value{Kind: NodeKind, Node: NodeID{Pkg: pkg, Level: level, Type: typ, Inst: inst}}
}

func Truthy(v Value) bool {
	switch v.Kind {
	case BoolKind:
		return v.Bool
	case IntKind:
		return v.Int != 0
	case FloatKind:
		return v.Float != 0
	case NullKind:
		return false
	}
	return true
}

func Len(v Value) int64 {
	switch v.Kind {
	case ListKind:
		if isDict(v) {
			return int64((len(v.List) - 1) / 2)
		}
		return int64(len(v.List))
	case StrKind:
		return int64(len(v.Str))
	}
	return 0
}

func Head(v Value) Value {
	if v.Kind != ListKind || len(v.List) == 0 {
		return Null()
	}
	return v.List[0]
}

func Tail(v Value) Value {
	if v.Kind != ListKind || len(v.List) == 0 {
		return List()
	}
	out := append([]Value{}, v.List[1:]...)
	return List(out...)
}

func Nth(v Value, idx Value) Value {
	if v.Kind != ListKind || idx.Kind != IntKind || idx.Int < 0 || int(idx.Int) >= len(v.List) {
		return Null()
	}
	return v.List[int(idx.Int)]
}

func Cons(head, tail Value) Value {
	if tail.Kind != ListKind {
		return List(head)
	}
	out := make([]Value, 0, len(tail.List)+1)
	out = append(out, head)
	out = append(out, tail.List...)
	return List(out...)
}

func Concat(a, b Value) Value {
	if a.Kind == StrKind || b.Kind == StrKind {
		return Str(a.AsString() + b.AsString())
	}
	if a.Kind != ListKind || b.Kind != ListKind {
		return List()
	}
	out := make([]Value, 0, len(a.List)+len(b.List))
	out = append(out, a.List...)
	out = append(out, b.List...)
	return List(out...)
}

func StrLen(v Value) Value       { return Int(Len(v)) }
func StrConcat(a, b Value) Value { return Str(a.AsString() + b.AsString()) }
func StrEq(a, b Value) Value     { return boolInt(a.AsString() == b.AsString()) }

func Substring(s, start, end Value) Value {
	text := s.AsString()
	from := int(start.AsInt())
	to := int(end.AsInt())
	return Str(text[from:to])
}

func CharAt(s, idx Value) Value {
	text := s.AsString()
	i := int(idx.AsInt())
	return Str(string(text[i]))
}

func Ord(v Value) Value {
	text := v.AsString()
	if len(text) == 0 {
		return Int(-1)
	}
	return Int(int64(text[0]))
}

func ByteToStr(v Value) Value {
	n := v.AsInt()
	if n < 0 || n > 255 {
		return Str("")
	}
	return Str(string(byte(n)))
}

func ScanRun(s, from, classValue Value) Value {
	text := s.AsString()
	end := int(from.AsInt())
	if end < 0 {
		end = 0
	}
	n := len(text)
	class := int(classValue.AsInt())
	switch class {
	case 0:
		for end < n {
			c := text[end]
			if c != ' ' && c != '\t' && c != '\n' && c != '\r' {
				break
			}
			end++
		}
	case 1:
		for end < n && text[end] >= '0' && text[end] <= '9' {
			end++
		}
	case 2:
		for end < n {
			c := text[end]
			if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
				break
			}
			end++
		}
	case 3:
		for end < n {
			c := text[end]
			if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
				(c >= '0' && c <= '9') || c == '_' || c == '-') {
				break
			}
			end++
		}
	case 4:
		for end < n && text[end] != '"' && text[end] != '\\' {
			end++
		}
	case 5:
		for end < n && text[end] != '\n' {
			end++
		}
	case 6:
		for end < n && text[end] >= 0x20 && text[end] != '"' && text[end] != '\\' {
			end++
		}
	default:
		return Int(int64(end))
	}
	return Int(int64(end))
}

func Add(a, b Value) Value {
	if a.Kind == FloatKind || b.Kind == FloatKind {
		return Float(a.AsFloat() + b.AsFloat())
	}
	return Int(a.AsInt() + b.AsInt())
}

func Sub(a, b Value) Value {
	if a.Kind == FloatKind || b.Kind == FloatKind {
		return Float(a.AsFloat() - b.AsFloat())
	}
	return Int(a.AsInt() - b.AsInt())
}

func Mul(a, b Value) Value {
	if a.Kind == FloatKind || b.Kind == FloatKind {
		return Float(a.AsFloat() * b.AsFloat())
	}
	return Int(a.AsInt() * b.AsInt())
}

func Div(a, b Value) Value {
	if a.Kind == FloatKind || b.Kind == FloatKind {
		return Float(a.AsFloat() / b.AsFloat())
	}
	if b.AsInt() == 0 {
		return Int(0)
	}
	return Int(a.AsInt() / b.AsInt())
}

func Mod(a, b Value) Value {
	if b.AsInt() == 0 {
		return Int(0)
	}
	return Int(a.AsInt() % b.AsInt())
}

// Comparisons acknowledge with the 0/1 integer states (axiom-1) — mirrors
// the walker's RBasicCompare arm so JIT'd and walked answers are identical.
func boolInt(b bool) Value {
	if b {
		return Int(1)
	}
	return Int(0)
}

func Eq(a, b Value) Value { return boolInt(equal(a, b)) }
func Ne(a, b Value) Value { return boolInt(!equal(a, b)) }
func Lt(a, b Value) Value { return boolInt(compare(a, b) < 0) }
func Le(a, b Value) Value { return boolInt(compare(a, b) <= 0) }
func Gt(a, b Value) Value { return boolInt(compare(a, b) > 0) }
func Ge(a, b Value) Value { return boolInt(compare(a, b) >= 0) }

func (v Value) AsInt() int64 {
	switch v.Kind {
	case IntKind:
		return v.Int
	case FloatKind:
		return int64(v.Float)
	case BoolKind:
		if v.Bool {
			return 1
		}
	}
	return 0
}

func (v Value) AsFloat() float64 {
	switch v.Kind {
	case FloatKind:
		return v.Float
	case IntKind:
		return float64(v.Int)
	case BoolKind:
		if v.Bool {
			return 1
		}
	}
	return 0
}

func (v Value) AsString() string {
	switch v.Kind {
	case StrKind:
		return v.Str
	case BoolKind:
		if v.Bool {
			return "true"
		}
		return "false"
	case NullKind:
		return "null"
	}
	return ""
}

func isDict(v Value) bool {
	return v.Kind == ListKind &&
		len(v.List) > 0 &&
		v.List[0].Kind == StrKind &&
		v.List[0].Str == "__dict__"
}

func equal(a, b Value) bool {
	if a.Kind == FloatKind || b.Kind == FloatKind {
		return a.AsFloat() == b.AsFloat()
	}
	if a.Kind != b.Kind {
		return false
	}
	switch a.Kind {
	case NullKind:
		return true
	case IntKind:
		return a.Int == b.Int
	case StrKind:
		return a.Str == b.Str
	case BoolKind:
		return a.Bool == b.Bool
	case NodeKind:
		return a.Node == b.Node
	case ListKind:
		if len(a.List) != len(b.List) {
			return false
		}
		for i := range a.List {
			if !equal(a.List[i], b.List[i]) {
				return false
			}
		}
		return true
	}
	return false
}

func compare(a, b Value) int {
	if a.Kind == StrKind || b.Kind == StrKind {
		as := a.AsString()
		bs := b.AsString()
		if as < bs {
			return -1
		}
		if as > bs {
			return 1
		}
		return 0
	}
	af := a.AsFloat()
	bf := b.AsFloat()
	if af < bf {
		return -1
	}
	if af > bf {
		return 1
	}
	return 0
}

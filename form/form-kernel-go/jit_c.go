// jit_c.go — Form recipe → portable C source, for cross-ISA assembly.
//
// The Go JIT (jit.go) compiles a recipe to a plugin THIS host runs. This
// emitter lowers the same int64 subset to freestanding C so the host's
// LLVM can show the recipe as ANY registered target's assembly — Android
// CPU (aarch64), Android DSP (hexagon), Apple silicon / MLX host
// (arm64-apple), NVIDIA PTX, AMD GCN. The recipe stays canonical truth;
// the C is a projection surface, witnessed by scripts/jit_assembly_audit
// tooling rather than executed by the kernel itself.
//
// Subset (mirrors jit.go's i64 ABI): int literals, bools, params, let/do,
// add/sub/mul/div/mod, comparisons, if, self-recursion. Anything else
// returns unsupported and the caller receives "" — the walker remains
// the body.
//
// `let`/`do` lower to GNU statement expressions, which clang accepts on
// every target this projection drives.

package main

import (
	"fmt"
	"strconv"
	"strings"
)

func emitCExpr(k *Kernel, node NodeID, scope *goCompileScope) (string, error) {
	if node.Level == LevelTrivial {
		switch node.Type {
		case TrivInt:
			return fmt.Sprintf("(long long)%s", strconv.FormatInt(int64(int32(node.Inst)), 10)), nil
		case TrivBool:
			if node.Inst != 0 {
				return "1LL", nil
			}
			return "0LL", nil
		}
		return "", unsupported(fmt.Sprintf("jit-c: trivial type %d not in subset", node.Type))
	}
	cat := k.category(node)
	kids := k.children(node)

	switch cat.Type {
	case RBasicIdent:
		id := k.identID(node)
		if v, ok := scope.vars[id]; ok {
			return v, nil
		}
		return "", unsupported(fmt.Sprintf("jit-c: unbound identifier %q", k.nameStr(id)))

	case RBasicMath:
		return emitCBinary(k, cat.Inst, kids, scope, map[uint32]string{
			RMathPlus: "+", RMathMinus: "-", RMathMultiply: "*",
			RMathDivide: "/", RMathModulo: "%",
		}, false)

	case RBasicCompare:
		return emitCBinary(k, cat.Inst, kids, scope, map[uint32]string{
			RCompareEq: "==", RCompareNe: "!=", RCompareLt: "<",
			RCompareLe: "<=", RCompareGt: ">", RCompareGe: ">=",
		}, true)

	case RBasicCond:
		if len(kids) < 2 {
			return "", unsupported("jit-c: cond expects at least 2 kids")
		}
		cond, err := emitCExpr(k, kids[0], scope)
		if err != nil {
			return "", err
		}
		then, err := emitCExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		els := "0LL"
		if cat.Inst == RCondIfThenElse && len(kids) >= 3 {
			els, err = emitCExpr(k, kids[2], scope)
			if err != nil {
				return "", err
			}
		}
		return fmt.Sprintf("(((%s) != 0) ? (%s) : (%s))", cond, then, els), nil

	case RBasicBlock:
		return emitCBlock(k, cat.Inst, kids, scope)

	case RBasicFnCall:
		if len(kids) < 1 {
			return "", unsupported("jit-c: fncall has no callee")
		}
		callee := kids[0]
		var nameID NameID
		if callee.Level == LevelTrivial && callee.Type == TrivString {
			nameID = NameID(callee.Inst)
		} else if k.category(callee).Type == RBasicIdent {
			nameID = k.identID(callee)
		} else {
			return "", unsupported("jit-c: dynamic callee not in subset")
		}
		if nameID != scope.selfName {
			return "", unsupported(fmt.Sprintf("jit-c: call %q not in subset (self-recursion only)", k.nameStr(nameID)))
		}
		args := make([]string, 0, len(kids)-1)
		for i := 1; i < len(kids); i++ {
			a, err := emitCExpr(k, kids[i], scope)
			if err != nil {
				return "", err
			}
			args = append(args, a)
		}
		return fmt.Sprintf("%s(%s)", scope.selfFn, strings.Join(args, ", ")), nil
	}
	return "", unsupported(fmt.Sprintf("jit-c: unsupported arm type %d", cat.Type))
}

func emitCBinary(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope, ops map[uint32]string, boolResult bool) (string, error) {
	if len(kids) != 2 {
		return "", unsupported("jit-c: binary expects 2 args")
	}
	opStr, ok := ops[op]
	if !ok {
		return "", unsupported(fmt.Sprintf("jit-c: op %d", op))
	}
	a, err := emitCExpr(k, kids[0], scope)
	if err != nil {
		return "", err
	}
	b, err := emitCExpr(k, kids[1], scope)
	if err != nil {
		return "", err
	}
	if boolResult {
		return fmt.Sprintf("((%s %s %s) ? 1LL : 0LL)", a, opStr, b), nil
	}
	return fmt.Sprintf("(%s %s %s)", a, opStr, b), nil
}

func emitCBlock(k *Kernel, op uint32, kids []NodeID, scope *goCompileScope) (string, error) {
	switch op {
	case RBlockLet:
		if len(kids) != 2 {
			return "", unsupported("jit-c: let expects 2 kids")
		}
		if kids[0].Level != LevelTrivial || kids[0].Type != TrivString {
			return "", unsupported("jit-c: let name must be string trivial")
		}
		valSrc, err := emitCExpr(k, kids[1], scope)
		if err != nil {
			return "", err
		}
		nid := NameID(kids[0].Inst)
		varName := scope.fresh(fmt.Sprintf("let_%s", k.nameStr(nid)))
		scope.vars[nid] = varName
		return fmt.Sprintf("({ long long %s = %s; %s; })", varName, valSrc, varName), nil
	case RBlockDo, RBlockSequence:
		if len(kids) == 0 {
			return "0LL", nil
		}
		if len(kids) == 1 {
			return emitCExpr(k, kids[0], scope)
		}
		child := scope.child()
		var b strings.Builder
		b.WriteString("({ ")
		for i, c := range kids {
			isLast := i == len(kids)-1
			if k.category(c).Type == RBasicBlock && k.category(c).Inst == RBlockLet {
				letKids := k.children(c)
				if len(letKids) == 2 && letKids[0].Level == LevelTrivial && letKids[0].Type == TrivString {
					valSrc, err := emitCExpr(k, letKids[1], child)
					if err != nil {
						return "", err
					}
					name := NameID(letKids[0].Inst)
					varName := child.fresh(fmt.Sprintf("let_%s", k.nameStr(name)))
					child.vars[name] = varName
					b.WriteString(fmt.Sprintf("long long %s = %s; ", varName, valSrc))
					if isLast {
						b.WriteString(fmt.Sprintf("%s; ", varName))
					}
					continue
				}
			}
			expr, err := emitCExpr(k, c, child)
			if err != nil {
				return "", err
			}
			if isLast {
				b.WriteString(fmt.Sprintf("%s; ", expr))
			} else {
				b.WriteString(fmt.Sprintf("(void)(%s); ", expr))
			}
		}
		b.WriteString("})")
		return b.String(), nil
	}
	return "", unsupported(fmt.Sprintf("jit-c: block op %d not in subset", op))
}

// jitEmitCClosure — lower one closure to a freestanding C translation
// unit: the recipe's function plus nothing else. The function is named
// after the closure so the assembly symbol carries the recipe's name.
func jitEmitCClosure(k *Kernel, cl *Closure) (string, error) {
	fnName := "form_" + sanitizeCIdent(k.nameStr(cl.Name))
	scope := newGoCompileScope(cl.Name, fnName, goJITABIi64, cl.Env, nil)
	for i, p := range cl.Params {
		scope.vars[p] = fmt.Sprintf("p%d", i)
	}
	body, err := emitCExpr(k, cl.Body, scope)
	if err != nil {
		return "", err
	}
	var params []string
	for i := range cl.Params {
		params = append(params, fmt.Sprintf("long long p%d", i))
	}
	var src strings.Builder
	src.WriteString("/* Generated by form-kernel-go JIT — Form recipe → C source. */\n")
	src.WriteString("/* Body NodeID: " + nodeIDKey(cl.Body) + " */\n")
	src.WriteString("/* Closure name: " + k.nameStr(cl.Name) + " */\n\n")
	src.WriteString(fmt.Sprintf("long long %s(%s) {\n", fnName, strings.Join(params, ", ")))
	src.WriteString("\treturn " + body + ";\n")
	src.WriteString("}\n")
	return src.String(), nil
}

func sanitizeCIdent(s string) string {
	var b strings.Builder
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		} else {
			b.WriteRune('_')
		}
	}
	return b.String()
}

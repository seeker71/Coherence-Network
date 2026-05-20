// Minimal Go runner for shared Form conformance vectors.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type state struct {
	questions    map[string]map[string]any
	events       []map[string]any
	nextQuestion int
	nextEvent    int
}

func newState() *state {
	return &state{questions: map[string]map[string]any{}}
}

func (s *state) createQuestion(agentID string, question string, choices []string, context map[string]any) map[string]any {
	s.nextQuestion++
	id := fmt.Sprintf("question_go_%04d", s.nextQuestion)
	item := map[string]any{
		"id":          id,
		"agent_id":    agentID,
		"question":    question,
		"task_id":     contextString(context, "task_id"),
		"thread_id":   contextString(context, "thread_id"),
		"choices":     choices,
		"context":     context,
		"status":      "open",
		"answer":      nil,
		"answered_by": nil,
	}
	s.questions[id] = item
	s.emit("question_opened", item)
	return item
}

func (s *state) answerQuestion(questionID string, answer string, answeredBy string) error {
	item, ok := s.questions[questionID]
	if !ok {
		return fmt.Errorf("question %q not found", questionID)
	}
	item["answer"] = answer
	item["answered_by"] = answeredBy
	item["status"] = "answered"
	s.emit("question_answered", item)
	return nil
}

func (s *state) emit(eventType string, question map[string]any) {
	s.nextEvent++
	s.events = append(s.events, map[string]any{
		"id":          fmt.Sprintf("event_go_%04d", s.nextEvent),
		"sequence":    s.nextEvent,
		"event_type":  eventType,
		"question_id": question["id"],
		"question":    question,
	})
}

func (s *state) awaitAnswer(questionID string) (any, error) {
	item, ok := s.questions[questionID]
	if !ok {
		return nil, fmt.Errorf("question %q not found", questionID)
	}
	return item["answer"], nil
}

type env []map[string]any

func lookupBinding(bindings env, name string) (any, bool) {
	for i := len(bindings) - 1; i >= 0; i-- {
		if value, ok := bindings[i][name]; ok {
			return value, true
		}
	}
	return nil, false
}

func assignBinding(bindings env, name string, value any) (any, error) {
	for i := len(bindings) - 1; i >= 0; i-- {
		if _, ok := bindings[i][name]; ok {
			bindings[i][name] = value
			return value, nil
		}
	}
	return nil, fmt.Errorf("set %q has no enclosing binding", name)
}

func contextString(context map[string]any, key string) any {
	if value, ok := context[key].(string); ok {
		return value
	}
	return nil
}

func splitArgs(input string) []string {
	var args []string
	var current strings.Builder
	inString := false
	escape := false
	squareDepth := 0
	braceDepth := 0
	for _, ch := range input {
		if escape {
			current.WriteRune(ch)
			escape = false
			continue
		}
		if ch == '\\' && inString {
			current.WriteRune(ch)
			escape = true
			continue
		}
		if ch == '"' {
			inString = !inString
			current.WriteRune(ch)
			continue
		}
		if !inString {
			switch ch {
			case '[':
				squareDepth++
			case ']':
				squareDepth--
			case '{':
				braceDepth++
			case '}':
				braceDepth--
			case ',':
				if squareDepth == 0 && braceDepth == 0 {
					args = append(args, strings.TrimSpace(current.String()))
					current.Reset()
					continue
				}
			}
		}
		current.WriteRune(ch)
	}
	if strings.TrimSpace(current.String()) != "" {
		args = append(args, strings.TrimSpace(current.String()))
	}
	return args
}

func splitTopLevel(input string, separator byte) []string {
	var parts []string
	var current strings.Builder
	inString := false
	escape := false
	parenDepth := 0
	squareDepth := 0
	braceDepth := 0
	for i := 0; i < len(input); i++ {
		ch := input[i]
		if escape {
			current.WriteByte(ch)
			escape = false
			continue
		}
		if ch == '\\' && inString {
			current.WriteByte(ch)
			escape = true
			continue
		}
		if ch == '"' {
			inString = !inString
			current.WriteByte(ch)
			continue
		}
		if !inString {
			switch ch {
			case '(':
				parenDepth++
			case ')':
				parenDepth--
			case '[':
				squareDepth++
			case ']':
				squareDepth--
			case '{':
				braceDepth++
			case '}':
				braceDepth--
			default:
				if ch == separator && parenDepth == 0 && squareDepth == 0 && braceDepth == 0 {
					parts = append(parts, strings.TrimSpace(current.String()))
					current.Reset()
					continue
				}
			}
		}
		current.WriteByte(ch)
	}
	if strings.TrimSpace(current.String()) != "" {
		parts = append(parts, strings.TrimSpace(current.String()))
	}
	return parts
}

func findTopLevelKeyword(input string, keyword string) int {
	inString := false
	escape := false
	parenDepth := 0
	squareDepth := 0
	braceDepth := 0
	for i := 0; i < len(input); i++ {
		ch := input[i]
		if escape {
			escape = false
			continue
		}
		if ch == '\\' && inString {
			escape = true
			continue
		}
		if ch == '"' {
			inString = !inString
			continue
		}
		if inString {
			continue
		}
		switch ch {
		case '(':
			parenDepth++
		case ')':
			parenDepth--
		case '[':
			squareDepth++
		case ']':
			squareDepth--
		case '{':
			braceDepth++
		case '}':
			braceDepth--
		}
		if parenDepth == 0 && squareDepth == 0 && braceDepth == 0 && strings.HasPrefix(input[i:], keyword) {
			return i
		}
	}
	return -1
}

func splitHeadBody(input string) (string, string, error) {
	text := strings.TrimSpace(input)
	if !strings.HasSuffix(text, "}") {
		return "", "", fmt.Errorf("missing braced body in %q", input)
	}
	inString := false
	escape := false
	parenDepth := 0
	squareDepth := 0
	for i := 0; i < len(text); i++ {
		ch := text[i]
		if escape {
			escape = false
			continue
		}
		if ch == '\\' && inString {
			escape = true
			continue
		}
		if ch == '"' {
			inString = !inString
			continue
		}
		if inString {
			continue
		}
		switch ch {
		case '(':
			parenDepth++
		case ')':
			parenDepth--
		case '[':
			squareDepth++
		case ']':
			squareDepth--
		case '{':
			if parenDepth == 0 && squareDepth == 0 {
				return strings.TrimSpace(text[:i]), strings.TrimSpace(text[i+1 : len(text)-1]), nil
			}
		}
	}
	return "", "", fmt.Errorf("missing braced body in %q", input)
}

func parseString(raw string) (string, error) {
	var out string
	err := json.Unmarshal([]byte(strings.TrimSpace(raw)), &out)
	if err != nil {
		return "", fmt.Errorf("invalid string %q: %w", raw, err)
	}
	return out, nil
}

func parseArray(raw string) ([]any, error) {
	text := strings.TrimSpace(raw)
	if text == "[]" {
		return []any{}, nil
	}
	if !strings.HasPrefix(text, "[") || !strings.HasSuffix(text, "]") {
		return nil, fmt.Errorf("invalid list %q", raw)
	}
	inner := text[1 : len(text)-1]
	items := splitArgs(inner)
	out := make([]any, 0, len(items))
	for _, item := range items {
		value, err := parseValue(item)
		if err != nil {
			return nil, err
		}
		out = append(out, value)
	}
	return out, nil
}

func parseObject(raw string) (map[string]any, error) {
	text := strings.TrimSpace(raw)
	out := map[string]any{}
	if text == "{}" {
		return out, nil
	}
	if !strings.HasPrefix(text, "{") || !strings.HasSuffix(text, "}") {
		return nil, fmt.Errorf("invalid context %q", raw)
	}
	inner := text[1 : len(text)-1]
	for _, pair := range splitArgs(inner) {
		parts := strings.SplitN(pair, ":", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid context pair %q", pair)
		}
		key := strings.Trim(strings.TrimSpace(parts[0]), "\"")
		value, err := parseValue(parts[1])
		if err != nil {
			return nil, err
		}
		out[key] = value
	}
	return out, nil
}

func parseValue(raw string) (any, error) {
	text := strings.TrimSpace(raw)
	if strings.HasPrefix(text, "[") && strings.HasSuffix(text, "]") {
		return parseArray(text)
	}
	if strings.HasPrefix(text, "{") && strings.HasSuffix(text, "}") {
		return parseObject(text)
	}
	decoder := json.NewDecoder(bytes.NewBufferString(text))
	decoder.UseNumber()
	var out any
	if err := decoder.Decode(&out); err != nil {
		return nil, fmt.Errorf("unsupported literal %q: %w", raw, err)
	}
	return normalizeJSONNumbers(out), nil
}

func normalizeJSONNumbers(value any) any {
	switch typed := value.(type) {
	case json.Number:
		if strings.ContainsAny(typed.String(), ".eE") {
			f, _ := typed.Float64()
			return f
		}
		i, _ := typed.Int64()
		return i
	case []any:
		out := make([]any, 0, len(typed))
		for _, item := range typed {
			out = append(out, normalizeJSONNumbers(item))
		}
		return out
	case map[string]any:
		out := map[string]any{}
		for key, item := range typed {
			out[key] = normalizeJSONNumbers(item)
		}
		return out
	default:
		return value
	}
}

func callBody(form string, name string) (string, error) {
	trimmed := strings.TrimSpace(form)
	prefix := name + "("
	if !strings.HasPrefix(trimmed, prefix) || !strings.HasSuffix(trimmed, ")") {
		return "", fmt.Errorf("unsupported Form expression %q", form)
	}
	return trimmed[len(prefix) : len(trimmed)-1], nil
}

func callParts(form string) (string, []string, error) {
	trimmed := strings.TrimSpace(form)
	open := strings.Index(trimmed, "(")
	if open <= 0 || !strings.HasSuffix(trimmed, ")") {
		return "", nil, fmt.Errorf("unsupported Form expression %q", form)
	}
	name := strings.TrimSpace(trimmed[:open])
	for _, ch := range name {
		if ch != '_' && (ch < '0' || ch > '9') && (ch < 'A' || ch > 'Z') && (ch < 'a' || ch > 'z') {
			return "", nil, fmt.Errorf("unsupported Form call %q", form)
		}
	}
	return name, splitArgs(trimmed[open+1 : len(trimmed)-1]), nil
}

func asArray(value any, name string) ([]any, error) {
	items, ok := value.([]any)
	if !ok {
		return nil, fmt.Errorf("%s expects a list", name)
	}
	return items, nil
}

func asInt(value any, name string) (int64, error) {
	switch typed := value.(type) {
	case int64:
		return typed, nil
	case int:
		return int64(typed), nil
	case float64:
		if typed == float64(int64(typed)) {
			return int64(typed), nil
		}
	}
	return 0, fmt.Errorf("%s expects integer values", name)
}

func evalBuiltin(name string, args []any) (any, error) {
	switch name {
	case "len":
		if len(args) != 1 {
			return nil, fmt.Errorf("len expects 1 arg, got %d", len(args))
		}
		switch typed := args[0].(type) {
		case []any:
			return int64(len(typed)), nil
		case map[string]any:
			return int64(len(typed)), nil
		case string:
			return int64(len([]rune(typed))), nil
		default:
			return nil, fmt.Errorf("len expects a list, object, or string")
		}
	case "head":
		if len(args) != 1 {
			return nil, fmt.Errorf("head expects 1 arg, got %d", len(args))
		}
		items, err := asArray(args[0], "head")
		if err != nil {
			return nil, err
		}
		if len(items) == 0 {
			return nil, nil
		}
		return items[0], nil
	case "tail":
		if len(args) != 1 {
			return nil, fmt.Errorf("tail expects 1 arg, got %d", len(args))
		}
		items, err := asArray(args[0], "tail")
		if err != nil {
			return nil, err
		}
		if len(items) <= 1 {
			return []any{}, nil
		}
		return append([]any{}, items[1:]...), nil
	case "sum":
		if len(args) != 1 {
			return nil, fmt.Errorf("sum expects 1 arg, got %d", len(args))
		}
		items, err := asArray(args[0], "sum")
		if err != nil {
			return nil, err
		}
		var total int64
		for _, item := range items {
			value, err := asInt(item, "sum")
			if err != nil {
				return nil, err
			}
			total += value
		}
		return total, nil
	case "concat":
		if len(args) != 2 {
			return nil, fmt.Errorf("concat expects 2 args, got %d", len(args))
		}
		leftString, leftIsString := args[0].(string)
		rightString, rightIsString := args[1].(string)
		if leftIsString && rightIsString {
			return leftString + rightString, nil
		}
		leftItems, leftIsList := args[0].([]any)
		rightItems, rightIsList := args[1].([]any)
		if leftIsList && rightIsList {
			out := append([]any{}, leftItems...)
			out = append(out, rightItems...)
			return out, nil
		}
		return nil, fmt.Errorf("concat expects two strings or two lists")
	case "reverse":
		if len(args) != 1 {
			return nil, fmt.Errorf("reverse expects 1 arg, got %d", len(args))
		}
		if text, ok := args[0].(string); ok {
			runes := []rune(text)
			for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
				runes[i], runes[j] = runes[j], runes[i]
			}
			return string(runes), nil
		}
		items, err := asArray(args[0], "reverse")
		if err != nil {
			return nil, err
		}
		out := append([]any{}, items...)
		for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
			out[i], out[j] = out[j], out[i]
		}
		return out, nil
	default:
		return nil, fmt.Errorf("unsupported Form function %q", name)
	}
}

type exprToken struct {
	kind  string
	value any
	op    string
}

func tokenizeExpr(input string, bindings env) ([]exprToken, error) {
	var tokens []exprToken
	for pos := 0; pos < len(input); {
		ch := input[pos]
		if ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t' {
			pos++
			continue
		}
		if ch == '"' {
			start := pos
			pos++
			escape := false
			for pos < len(input) {
				current := input[pos]
				if escape {
					escape = false
				} else if current == '\\' {
					escape = true
				} else if current == '"' {
					pos++
					break
				}
				pos++
			}
			if pos > len(input) || input[pos-1] != '"' {
				return nil, fmt.Errorf("unterminated string literal")
			}
			value, err := parseString(input[start:pos])
			if err != nil {
				return nil, err
			}
			tokens = append(tokens, exprToken{kind: "value", value: value})
			continue
		}
		if ch >= '0' && ch <= '9' {
			start := pos
			pos++
			for pos < len(input) && input[pos] >= '0' && input[pos] <= '9' {
				pos++
			}
			raw := input[start:pos]
			value, err := strconv.ParseInt(raw, 10, 64)
			if err != nil {
				return nil, fmt.Errorf("invalid integer %q: %w", raw, err)
			}
			tokens = append(tokens, exprToken{kind: "value", value: value})
			continue
		}
		if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') {
			start := pos
			pos++
			for pos < len(input) && ((input[pos] >= 'a' && input[pos] <= 'z') || (input[pos] >= 'A' && input[pos] <= 'Z') || (input[pos] >= '0' && input[pos] <= '9') || input[pos] == '_') {
				pos++
			}
			raw := input[start:pos]
			switch raw {
			case "true":
				tokens = append(tokens, exprToken{kind: "value", value: true})
			case "false":
				tokens = append(tokens, exprToken{kind: "value", value: false})
			case "null":
				tokens = append(tokens, exprToken{kind: "value", value: nil})
			default:
				value, ok := lookupBinding(bindings, raw)
				if !ok {
					return nil, fmt.Errorf("unsupported identifier %q", raw)
				}
				tokens = append(tokens, exprToken{kind: "value", value: value})
			}
			continue
		}
		if ch == '(' {
			tokens = append(tokens, exprToken{kind: "lparen"})
			pos++
			continue
		}
		if ch == ')' {
			tokens = append(tokens, exprToken{kind: "rparen"})
			pos++
			continue
		}
		if pos+1 < len(input) {
			two := input[pos : pos+2]
			if two == "==" || two == "!=" || two == "<=" || two == ">=" || two == "&&" || two == "||" {
				tokens = append(tokens, exprToken{kind: "op", op: two})
				pos += 2
				continue
			}
		}
		if strings.ContainsRune("+-*/%<>!", rune(ch)) {
			tokens = append(tokens, exprToken{kind: "op", op: string(ch)})
			pos++
			continue
		}
		return nil, fmt.Errorf("unsupported expression character %q", ch)
	}
	return tokens, nil
}

type exprParser struct {
	tokens []exprToken
	pos    int
}

func (p *exprParser) parse() (any, error) {
	value, err := p.parseOr()
	if err != nil {
		return nil, err
	}
	if p.pos != len(p.tokens) {
		return nil, fmt.Errorf("unexpected token %#v", p.tokens[p.pos])
	}
	return value, nil
}

func (p *exprParser) takeOp(op string) bool {
	if p.pos < len(p.tokens) && p.tokens[p.pos].kind == "op" && p.tokens[p.pos].op == op {
		p.pos++
		return true
	}
	return false
}

func (p *exprParser) parseOr() (any, error) {
	left, err := p.parseAnd()
	if err != nil {
		return nil, err
	}
	for p.takeOp("||") {
		right, err := p.parseAnd()
		if err != nil {
			return nil, err
		}
		if !truthy(left) {
			left = right
		}
	}
	return left, nil
}

func (p *exprParser) parseAnd() (any, error) {
	left, err := p.parseCompare()
	if err != nil {
		return nil, err
	}
	for p.takeOp("&&") {
		right, err := p.parseCompare()
		if err != nil {
			return nil, err
		}
		if truthy(left) {
			left = right
		}
	}
	return left, nil
}

func (p *exprParser) parseCompare() (any, error) {
	left, err := p.parseAdd()
	if err != nil {
		return nil, err
	}
	for p.pos < len(p.tokens) && p.tokens[p.pos].kind == "op" {
		op := p.tokens[p.pos].op
		if op != "==" && op != "!=" && op != "<" && op != "<=" && op != ">" && op != ">=" {
			break
		}
		p.pos++
		right, err := p.parseAdd()
		if err != nil {
			return nil, err
		}
		left, err = applyCompare(op, left, right)
		if err != nil {
			return nil, err
		}
	}
	return left, nil
}

func (p *exprParser) parseAdd() (any, error) {
	left, err := p.parseMul()
	if err != nil {
		return nil, err
	}
	for {
		if p.takeOp("+") {
			right, err := p.parseMul()
			if err != nil {
				return nil, err
			}
			left, err = applyNumeric("+", left, right)
			if err != nil {
				return nil, err
			}
		} else if p.takeOp("-") {
			right, err := p.parseMul()
			if err != nil {
				return nil, err
			}
			left, err = applyNumeric("-", left, right)
			if err != nil {
				return nil, err
			}
		} else {
			return left, nil
		}
	}
}

func (p *exprParser) parseMul() (any, error) {
	left, err := p.parseUnary()
	if err != nil {
		return nil, err
	}
	for {
		if p.takeOp("*") {
			right, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left, err = applyNumeric("*", left, right)
			if err != nil {
				return nil, err
			}
		} else if p.takeOp("/") {
			right, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left, err = applyNumeric("/", left, right)
			if err != nil {
				return nil, err
			}
		} else if p.takeOp("%") {
			right, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left, err = applyNumeric("%", left, right)
			if err != nil {
				return nil, err
			}
		} else {
			return left, nil
		}
	}
}

func (p *exprParser) parseUnary() (any, error) {
	if p.takeOp("-") {
		value, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		item, err := asInt(value, "unary -")
		if err != nil {
			return nil, err
		}
		return -item, nil
	}
	if p.takeOp("!") {
		value, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return !truthy(value), nil
	}
	return p.parsePrimary()
}

func (p *exprParser) parsePrimary() (any, error) {
	if p.pos >= len(p.tokens) {
		return nil, fmt.Errorf("expected literal or parenthesized expression")
	}
	token := p.tokens[p.pos]
	switch token.kind {
	case "value":
		p.pos++
		return token.value, nil
	case "lparen":
		p.pos++
		value, err := p.parseOr()
		if err != nil {
			return nil, err
		}
		if p.pos >= len(p.tokens) || p.tokens[p.pos].kind != "rparen" {
			return nil, fmt.Errorf("missing closing ')'")
		}
		p.pos++
		return value, nil
	default:
		return nil, fmt.Errorf("expected literal or parenthesized expression, got %#v", token)
	}
}

func truthy(value any) bool {
	switch typed := value.(type) {
	case nil:
		return false
	case bool:
		return typed
	case int64:
		return typed != 0
	case int:
		return typed != 0
	case float64:
		return typed != 0
	case string:
		return typed != ""
	case []any:
		return len(typed) > 0
	case map[string]any:
		return len(typed) > 0
	default:
		return true
	}
}

func applyNumeric(op string, left any, right any) (any, error) {
	a, err := asInt(left, op)
	if err != nil {
		return nil, err
	}
	b, err := asInt(right, op)
	if err != nil {
		return nil, err
	}
	switch op {
	case "+":
		return a + b, nil
	case "-":
		return a - b, nil
	case "*":
		return a * b, nil
	case "/":
		return a / b, nil
	case "%":
		return a % b, nil
	default:
		return nil, fmt.Errorf("unsupported numeric op %q", op)
	}
}

func applyCompare(op string, left any, right any) (any, error) {
	switch op {
	case "==":
		return fmt.Sprintf("%#v", left) == fmt.Sprintf("%#v", right), nil
	case "!=":
		return fmt.Sprintf("%#v", left) != fmt.Sprintf("%#v", right), nil
	case "<", "<=", ">", ">=":
		a, err := asInt(left, op)
		if err != nil {
			return nil, err
		}
		b, err := asInt(right, op)
		if err != nil {
			return nil, err
		}
		switch op {
		case "<":
			return a < b, nil
		case "<=":
			return a <= b, nil
		case ">":
			return a > b, nil
		case ">=":
			return a >= b, nil
		}
	}
	return nil, fmt.Errorf("unsupported comparison op %q", op)
}

func evalExpression(form string, bindings env) (any, error) {
	tokens, err := tokenizeExpr(form, bindings)
	if err != nil {
		return nil, err
	}
	return (&exprParser{tokens: tokens}).parse()
}

func evalForm(s *state, form string) (any, error) {
	bindings := env{map[string]any{}}
	return evalFormIn(s, form, bindings)
}

func evalIf(s *state, form string, bindings env) (any, error) {
	rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(form), "if "))
	thenPos := findTopLevelKeyword(rest, " then ")
	if thenPos < 0 {
		return nil, fmt.Errorf("if expression missing then: %q", form)
	}
	condSrc := strings.TrimSpace(rest[:thenPos])
	afterThen := rest[thenPos+len(" then "):]
	elsePos := findTopLevelKeyword(afterThen, " else ")
	thenSrc := strings.TrimSpace(afterThen)
	elseSrc := ""
	if elsePos >= 0 {
		thenSrc = strings.TrimSpace(afterThen[:elsePos])
		elseSrc = strings.TrimSpace(afterThen[elsePos+len(" else "):])
	}
	cond, err := evalFormIn(s, condSrc, bindings)
	if err != nil {
		return nil, err
	}
	if truthy(cond) {
		return evalFormIn(s, thenSrc, bindings)
	}
	if elseSrc == "" {
		return nil, nil
	}
	return evalFormIn(s, elseSrc, bindings)
}

func evalDo(s *state, form string, bindings env) (any, error) {
	text := strings.TrimSpace(form)
	body := strings.TrimSpace(strings.TrimPrefix(text, "do"))
	if !strings.HasPrefix(body, "{") || !strings.HasSuffix(body, "}") {
		return nil, fmt.Errorf("invalid do block %q", form)
	}
	inner := body[1 : len(body)-1]
	local := append(bindings, map[string]any{})
	return evalStatements(s, inner, local)
}

func evalLet(s *state, form string, bindings env) (any, error) {
	rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(form), "let "))
	parts := strings.SplitN(rest, "=", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf("let expression missing '=': %q", form)
	}
	name := strings.TrimSpace(parts[0])
	if name == "" || (name[0] >= '0' && name[0] <= '9') {
		return nil, fmt.Errorf("invalid let binding name %q", name)
	}
	for _, ch := range name {
		if ch != '_' && (ch < '0' || ch > '9') && (ch < 'A' || ch > 'Z') && (ch < 'a' || ch > 'z') {
			return nil, fmt.Errorf("invalid let binding name %q", name)
		}
	}
	value, err := evalFormIn(s, strings.TrimSpace(parts[1]), bindings)
	if err != nil {
		return nil, err
	}
	if len(bindings) == 0 {
		return nil, fmt.Errorf("internal error: missing environment scope")
	}
	bindings[len(bindings)-1][name] = value
	return value, nil
}

func evalSet(s *state, form string, bindings env) (any, error) {
	rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(form), "set "))
	parts := strings.SplitN(rest, "=", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf("set expression missing '=': %q", form)
	}
	name := strings.TrimSpace(parts[0])
	if name == "" || (name[0] >= '0' && name[0] <= '9') {
		return nil, fmt.Errorf("invalid set binding name %q", name)
	}
	for _, ch := range name {
		if ch != '_' && (ch < '0' || ch > '9') && (ch < 'A' || ch > 'Z') && (ch < 'a' || ch > 'z') {
			return nil, fmt.Errorf("invalid set binding name %q", name)
		}
	}
	value, err := evalFormIn(s, strings.TrimSpace(parts[1]), bindings)
	if err != nil {
		return nil, err
	}
	return assignBinding(bindings, name, value)
}

func evalArray(s *state, form string, bindings env) ([]any, error) {
	text := strings.TrimSpace(form)
	if text == "[]" {
		return []any{}, nil
	}
	if !strings.HasPrefix(text, "[") || !strings.HasSuffix(text, "]") {
		return nil, fmt.Errorf("invalid list %q", form)
	}
	items := splitArgs(text[1 : len(text)-1])
	out := make([]any, 0, len(items))
	for _, item := range items {
		value, err := evalFormIn(s, item, bindings)
		if err != nil {
			return nil, err
		}
		out = append(out, value)
	}
	return out, nil
}

func evalStatements(s *state, body string, bindings env) (any, error) {
	var result any
	for _, stmt := range splitTopLevel(body, ';') {
		value, err := evalFormIn(s, stmt, bindings)
		if err != nil {
			return nil, err
		}
		result = value
	}
	return result, nil
}

func evalFor(s *state, form string, bindings env) (any, error) {
	rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(form), "for "))
	inPos := findTopLevelKeyword(rest, " in ")
	if inPos < 0 {
		return nil, fmt.Errorf("for expression missing in: %q", form)
	}
	varName := strings.TrimSpace(rest[:inPos])
	if varName == "" || (varName[0] >= '0' && varName[0] <= '9') {
		return nil, fmt.Errorf("invalid for binding name %q", varName)
	}
	for _, ch := range varName {
		if ch != '_' && (ch < '0' || ch > '9') && (ch < 'A' || ch > 'Z') && (ch < 'a' || ch > 'z') {
			return nil, fmt.Errorf("invalid for binding name %q", varName)
		}
	}
	iterSrc, bodySrc, err := splitHeadBody(strings.TrimSpace(rest[inPos+len(" in "):]))
	if err != nil {
		return nil, err
	}
	iterable, err := evalFormIn(s, iterSrc, bindings)
	if err != nil {
		return nil, err
	}
	var items []any
	switch typed := iterable.(type) {
	case []any:
		items = typed
	case string:
		for _, ch := range typed {
			items = append(items, string(ch))
		}
	default:
		return nil, fmt.Errorf("for expects a list or string, got %T", iterable)
	}
	results := make([]any, 0, len(items))
	for _, item := range items {
		local := append(bindings, map[string]any{varName: item})
		value, err := evalStatements(s, bodySrc, local)
		if err != nil {
			return nil, err
		}
		results = append(results, value)
	}
	return results, nil
}

func evalWhile(s *state, form string, bindings env) (any, error) {
	rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(form), "while "))
	condSrc, bodySrc, err := splitHeadBody(rest)
	if err != nil {
		return nil, err
	}
	var result any
	const maxIterations = 100000
	for iterations := 0; ; iterations++ {
		cond, err := evalFormIn(s, condSrc, bindings)
		if err != nil {
			return nil, err
		}
		if !truthy(cond) {
			return result, nil
		}
		result, err = evalStatements(s, bodySrc, bindings)
		if err != nil {
			return nil, err
		}
		if iterations >= maxIterations {
			return nil, fmt.Errorf("while loop exceeded %d iterations", maxIterations)
		}
	}
}

func evalFormIn(s *state, form string, bindings env) (any, error) {
	trimmed := strings.TrimSpace(form)
	if strings.HasPrefix(trimmed, "if ") {
		return evalIf(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "do") {
		return evalDo(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "let ") {
		return evalLet(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "set ") {
		return evalSet(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "for ") {
		return evalFor(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "while ") {
		return evalWhile(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "ask(") {
		body, err := callBody(trimmed, "ask")
		if err != nil {
			return nil, err
		}
		args := splitArgs(body)
		if len(args) < 2 || len(args) > 4 {
			return nil, fmt.Errorf("ask expects 2 to 4 args, got %d", len(args))
		}
		agentID, err := parseString(args[0])
		if err != nil {
			return nil, err
		}
		question, err := parseString(args[1])
		if err != nil {
			return nil, err
		}
		choices := []string{}
		if len(args) >= 3 {
			rawChoices, err := parseArray(args[2])
			if err != nil {
				return nil, err
			}
			for _, item := range rawChoices {
				choice, ok := item.(string)
				if !ok {
					return nil, fmt.Errorf("ask choices must be strings")
				}
				choices = append(choices, choice)
			}
		}
		context := map[string]any{}
		if len(args) >= 4 {
			context, err = parseObject(args[3])
			if err != nil {
				return nil, err
			}
		}
		return s.createQuestion(agentID, question, choices, context), nil
	}
	if strings.HasPrefix(trimmed, "await_answer(") {
		body, err := callBody(trimmed, "await_answer")
		if err != nil {
			return nil, err
		}
		args := splitArgs(body)
		if len(args) != 1 {
			return nil, fmt.Errorf("await_answer expects 1 arg, got %d", len(args))
		}
		questionID, err := parseString(args[0])
		if err != nil {
			return nil, err
		}
		return s.awaitAnswer(questionID)
	}
	name, rawArgs, err := callParts(trimmed)
	if err == nil {
		args := make([]any, 0, len(rawArgs))
		for _, rawArg := range rawArgs {
			value, err := evalFormIn(s, rawArg, bindings)
			if err != nil {
				return nil, err
			}
			args = append(args, value)
		}
		return evalBuiltin(name, args)
	}
	if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
		return evalArray(s, trimmed, bindings)
	}
	if strings.HasPrefix(trimmed, "{") && strings.HasSuffix(trimmed, "}") {
		return parseObject(trimmed)
	}
	return evalExpression(trimmed, bindings)
}

func runCase(rawCase map[string]any) (map[string]any, error) {
	s := newState()
	questionID := ""
	if setup, ok := rawCase["setup"].(map[string]any); ok {
		if openForm, ok := setup["open_question_form"].(string); ok {
			opened, err := evalForm(s, openForm)
			if err != nil {
				return nil, err
			}
			openedQuestion := opened.(map[string]any)
			questionID = openedQuestion["id"].(string)
			if answer, ok := setup["answer"].(string); ok {
				answeredBy, _ := setup["answered_by"].(string)
				if answeredBy == "" {
					answeredBy = "conformance"
				}
				if err := s.answerQuestion(questionID, answer, answeredBy); err != nil {
					return nil, err
				}
			}
		}
	}
	form := strings.ReplaceAll(rawCase["form"].(string), "${question_id}", questionID)
	value, err := evalForm(s, form)
	if err != nil {
		return nil, err
	}
	if questionID == "" {
		if item, ok := value.(map[string]any); ok {
			questionID, _ = item["id"].(string)
		}
	}
	return map[string]any{
		"name":        rawCase["name"],
		"question_id": questionID,
		"value":       value,
		"events":      s.events,
	}, nil
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: question_kernel <vector.json>")
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var vector map[string]any
	if err := json.Unmarshal(data, &vector); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	rawCases := vector["cases"].([]any)
	cases := make([]map[string]any, 0, len(rawCases))
	for _, raw := range rawCases {
		item, err := runCase(raw.(map[string]any))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		cases = append(cases, item)
	}
	payload := map[string]any{
		"kernel": "go",
		"status": "pass",
		"cases":  cases,
	}
	out, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(string(out))
}

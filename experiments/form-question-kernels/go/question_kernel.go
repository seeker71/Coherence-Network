// Minimal Go runner for the Form question-effect conformance vector.
package main

import (
	"encoding/json"
	"fmt"
	"os"
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

func parseString(raw string) (string, error) {
	var out string
	err := json.Unmarshal([]byte(strings.TrimSpace(raw)), &out)
	if err != nil {
		return "", fmt.Errorf("invalid string %q: %w", raw, err)
	}
	return out, nil
}

func parseStringList(raw string) ([]string, error) {
	text := strings.TrimSpace(raw)
	if text == "[]" {
		return []string{}, nil
	}
	if !strings.HasPrefix(text, "[") || !strings.HasSuffix(text, "]") {
		return nil, fmt.Errorf("invalid list %q", raw)
	}
	inner := text[1 : len(text)-1]
	items := splitArgs(inner)
	out := make([]string, 0, len(items))
	for _, item := range items {
		value, err := parseString(item)
		if err != nil {
			return nil, err
		}
		out = append(out, value)
	}
	return out, nil
}

func parseContext(raw string) (map[string]any, error) {
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
		value, err := parseString(parts[1])
		if err != nil {
			return nil, err
		}
		out[key] = value
	}
	return out, nil
}

func callBody(form string, name string) (string, error) {
	trimmed := strings.TrimSpace(form)
	prefix := name + "("
	if !strings.HasPrefix(trimmed, prefix) || !strings.HasSuffix(trimmed, ")") {
		return "", fmt.Errorf("unsupported Form expression %q", form)
	}
	return trimmed[len(prefix) : len(trimmed)-1], nil
}

func evalForm(s *state, form string) (any, error) {
	trimmed := strings.TrimSpace(form)
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
			choices, err = parseStringList(args[2])
			if err != nil {
				return nil, err
			}
		}
		context := map[string]any{}
		if len(args) >= 4 {
			context, err = parseContext(args[3])
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
	return nil, fmt.Errorf("unsupported Form expression %q", form)
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

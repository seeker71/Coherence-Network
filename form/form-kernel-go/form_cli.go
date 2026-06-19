package main

// form_cli.go — the COMPILED form-cli. When the kernel binary is invoked by a name ending in
// "form-cli", it runs the Form recipes EMBEDDED below (go:embed) instead of reading a .fk path.
// The logic is Form (bundle.fk: ask / agent-loop / sufficiency / repl routing); host effects
// (oracle, edit, bash) go through the kernel's host-io. No bash dispatcher, no Python, no repo
// tree — one self-contained native binary with the recipes baked in.

import (
	"bufio"
	_ "embed"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

//go:embed fcli_embed/bundle.fk
var fcliBundle string

// runFcli — dispatch one form-cli invocation (the argv→recipe entry; the bodies are Form).
func runFcli(args []string) {
	if len(args) == 0 {
		fcliRepl()
		return
	}
	switch args[0] {
	case "eval":
		if len(args) > 1 {
			fcliRun(args[1])
		}
	case "ask", "ask+":
		model, judge, remote := "coder", "llama3.2:3b", "claude -p"
		q := fcliParse(args[1:], &model, &judge, &remote)
		fcliRun(fmt.Sprintf("(fca-ask %s %s %s %s 60 1)",
			strconv.Quote(q), strconv.Quote(model), strconv.Quote(judge), strconv.Quote(remote)))
	case "do":
		fcliRun(fmt.Sprintf("(fnr-run-tiered %s \"ollama run coder\" \"claude -p\" 6)",
			strconv.Quote(strings.Join(args[1:], " "))))
	case "repl":
		fcliRepl()
	default:
		// host-carrier commands (stats/train/shadow/search/...) shell out by nature; delegate to the
		// full dispatcher in the repo when present, so the compiled binary loses no command.
		fcliDelegate(args)
	}
}

// fcliDelegate — hand a non-core command to the repo's full form-cli dispatcher (host-carrier
// commands like stats/train/shadow need the GPU/files/scripts; they cannot be pure compiled logic).
func fcliDelegate(args []string) {
	repo := os.Getenv("FORM_CLI_REPO")
	if repo == "" {
		repo = os.Getenv("HOME") + "/source/Coherence-Network"
	}
	full := repo + "/bin/form-cli"
	if _, err := os.Stat(full); err != nil {
		fmt.Fprintln(os.Stderr, "form-cli (compiled core): repl | ask+ | do | eval.")
		fmt.Fprintf(os.Stderr, "  '%s' needs the full dispatcher — set FORM_CLI_REPO to the repo root (looked in %s).\n", args[0], repo)
		os.Exit(2)
	}
	c := exec.Command("bash", append([]string{full}, args...)...)
	c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := c.Run(); err != nil {
		os.Exit(1)
	}
}

// fcliParse — pull -m/-j/--remote flags; the rest is the question.
func fcliParse(args []string, model, judge, remote *string) string {
	var rest []string
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "-m", "--model":
			if i+1 < len(args) {
				*model = args[i+1]
				i++
			}
		case "-j", "--judge":
			if i+1 < len(args) {
				*judge = args[i+1]
				i++
			}
		case "--remote":
			if i+1 < len(args) {
				*remote = args[i+1]
				i++
			}
		default:
			rest = append(rest, args[i])
		}
	}
	return strings.Join(rest, " ")
}

// fcliRun — define the embedded bundle + walk one dispatch expression in the kernel; print it.
func fcliRun(expr string) {
	if strings.TrimSpace(expr) == "" {
		return
	}
	if out := fcliWalkStr(expr); out != "null" && out != "" {
		fmt.Println(out)
	}
}

// fcliWalkStr — walk an expr against the embedded recipe bundle, return its string result.
func fcliWalkStr(expr string) (result string) {
	defer func() {
		if r := recover(); r != nil {
			result = fmt.Sprintf("(error: %v)", r)
		}
	}()
	k := NewKernel()
	root := readRootFromSource(k, fcliBundle+"\n"+expr)
	return k.walk(root, NewFrame(nil)).String()
}

// fcliRepl — interactive loop: classify each line via the Form recipe (frepl-classify), dispatch
// to eval / agent-do / ask. The loop is host I/O; every decision and answer is a Form recipe.
func fcliRepl() {
	fmt.Print("form-cli — interactive (compiled binary, recipes embedded)\n  question · '(expr)' evals · /do TASK · /exit\n\n")
	r := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("form-cli› ")
		line, err := r.ReadString('\n')
		if err != nil && line == "" {
			fmt.Println()
			return
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		paren, slash := 0, 0
		if strings.HasPrefix(line, "(") {
			paren = 1
		}
		if strings.HasPrefix(line, "/") {
			slash = 1
		}
		switch fcliWalkStr(fmt.Sprintf("(frepl-classify 0 %d %d)", paren, slash)) {
		case "0": // a Form expression
			fcliRun(line)
		case "1": // a meta-command
			if line == "/exit" || line == "/quit" {
				return
			} else if strings.HasPrefix(line, "/do ") {
				fcliRun(fmt.Sprintf("(fnr-run-tiered %s \"ollama run coder\" \"claude -p\" 6)",
					strconv.Quote(strings.TrimSpace(line[4:]))))
			} else {
				fmt.Println("  /do TASK · /exit · '(expr)' eval · text = a question")
			}
		default: // a question
			fcliRun(fmt.Sprintf("(fca-ask %s \"coder\" \"llama3.2:3b\" \"claude -p\" 60 1)", strconv.Quote(line)))
		}
	}
}

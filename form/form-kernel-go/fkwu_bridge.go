// fkwu_bridge.go — the Go serving kernel offloads a pure computation to the
// emitted fourth kernel (fkwu) at runtime.
//
// Part of the offload path scoped in kernels/FKWU_NATIVE_DISPATCH.md: the
// carrier (Go) hands fkwu a pre-flattened node-table and an input, fkwu walks
// the table and returns the value. The body is the Form program fkwu walks;
// this is the thin carrier seam that invokes it. fkwu makes no host call here,
// so the loop carries no reentrancy, cancellation, or capability surface.
//
// Two input channels, both proven (fkwu_bridge_test.go):
//   - argv[2] — a scalar integer bound into fkwu's root frame (fk_vs[0]).
//   - argv[3] — a file read into fk_src, the byte buffer a program reads with
//     fk-buf (tag 17, "the BMF cursor's eye"). This carries a serialized
//     request+rows bundle for a route's pure slice; the offloaded program reads
//     it the same way the persistent server main reads a socket request.
//
// Subprocess invocation re-pays process spawn + table load per call; it is the
// honest carrier proof, not the production hot-path shape. The production shape
// is the persistent fkwu server (fkc-emit-server-universal): load the table
// once, read each request into fk_src over a socket. That is the next increment.
package main

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// FkwuEval runs the fkwu binary on a flattened table with one scalar integer
// input (argv[2]) and returns fkwu's primary verdict — the first stdout line,
// which the validate.sh four-way harness compares byte-for-byte against the Go
// walker.
func FkwuEval(fkwuBin, tablePath string, input int64) (string, error) {
	return runFkwu(fkwuBin, tablePath, input, nil)
}

// FkwuEvalWithInput runs fkwu on a flattened table with a scalar input (argv[2])
// AND a structured input bundle staged into fk_src (argv[3]): the bytes the
// offloaded program reads with fk-buf. Returns fkwu's first stdout line — a
// value that depends on the bundle.
func FkwuEvalWithInput(fkwuBin, tablePath string, scalar int64, input []byte) (string, error) {
	return runFkwu(fkwuBin, tablePath, scalar, input)
}

// runFkwu invokes the fkwu binary. When input is non-nil it is written to a
// temp file passed as argv[3] (staged into fk_src). The first stdout line is
// the verdict; stderr is surfaced on failure.
func runFkwu(fkwuBin, tablePath string, scalar int64, input []byte) (string, error) {
	args := []string{tablePath, fmt.Sprintf("%d", scalar)}
	if input != nil {
		f, err := os.CreateTemp("", "fkwu-input-*")
		if err != nil {
			return "", fmt.Errorf("fkwu input temp: %w", err)
		}
		defer os.Remove(f.Name())
		if _, err := f.Write(input); err != nil {
			f.Close()
			return "", fmt.Errorf("fkwu input write: %w", err)
		}
		if err := f.Close(); err != nil {
			return "", fmt.Errorf("fkwu input close: %w", err)
		}
		args = append(args, f.Name())
	}

	cmd := exec.Command(fkwuBin, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("fkwu run %s: %w (stderr: %s)", tablePath, err, strings.TrimSpace(stderr.String()))
	}
	sc := bufio.NewScanner(&stdout)
	if sc.Scan() {
		return strings.TrimSpace(sc.Text()), nil
	}
	return "", fmt.Errorf("fkwu run %s: empty output", tablePath)
}

// fkwu_bridge.go — the Go serving kernel offloads a pure computation to the
// emitted fourth kernel (fkwu) at runtime.
//
// This is the first step of the offload path scoped in
// kernels/FKWU_NATIVE_DISPATCH.md: the carrier (Go) hands fkwu a pre-flattened
// band node-table plus a scalar input, and fkwu walks the table and returns the
// value — the SAME value the three sibling walkers compute for a four-way band.
// The body is the Form band fkwu walks; this is the thin carrier seam that
// invokes it. fkwu makes no host call here, so the loop carries no reentrancy,
// cancellation, or capability surface.
//
// Input channel: argv[2], a single scalar integer bound into fkwu's root frame
// (fk_vs[0]). The structured-bundle channel — argv[3] -> fk_src, carrying a
// serialized request+rows value for routes whose pure slice needs real data —
// is the next increment named in the build order.
package main

import (
	"bufio"
	"fmt"
	"os/exec"
	"strings"
)

// FkwuEval runs the fkwu binary on a flattened band table with one scalar
// integer input and returns fkwu's primary verdict — the first stdout line,
// which the validate.sh four-way harness compares byte-for-byte against the Go
// walker. An error is returned when fkwu cannot run or produces no output.
func FkwuEval(fkwuBin, tablePath string, input int64) (string, error) {
	cmd := exec.Command(fkwuBin, tablePath, fmt.Sprintf("%d", input))
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("fkwu eval %s: %w", tablePath, err)
	}
	sc := bufio.NewScanner(strings.NewReader(string(out)))
	if sc.Scan() {
		return strings.TrimSpace(sc.Text()), nil
	}
	return "", fmt.Errorf("fkwu eval %s: empty output", tablePath)
}

#!/usr/bin/env bash
# Build and run a native host verifier for tiny tensor autodiff samples.
#
# The generated Go binary checks analytic gradients for
#   y = dot(w, x) + b
#   loss = (y - target)^2
# against central finite differences over deterministic integer samples.
#
# Usage:
#   scripts/tensor_autodiff_native_verifier.sh [samples] [width]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES="${1:-64}"
WIDTH="${2:-4}"
WORK="$ROOT/.cache/tensor_autodiff_native_verifier"
SRC="$WORK/main.go"
BIN="$WORK/tensor-autodiff-verifier"

mkdir -p "$WORK"

cat > "$SRC" <<'GO'
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
)

type Receipt struct {
	Kind     string `json:"kind"`
	Samples  int    `json:"samples"`
	Width    int    `json:"width"`
	Passed   int    `json:"passed"`
	Failed   int    `json:"failed"`
	Checksum int64  `json:"checksum"`
	Status   string `json:"status"`
}

func next(seed *uint64) int64 {
	*seed = (*seed*1103515245 + 12345) & 0x7fffffff
	return int64((*seed>>8)%11) - 5
}

func pred(weights []int64, x []int64, b int64) int64 {
	sum := b
	for i := range weights {
		sum += weights[i] * x[i]
	}
	return sum
}

func loss(weights []int64, x []int64, b int64, target int64) int64 {
	err := pred(weights, x, b) - target
	return err * err
}

func main() {
	samples := 64
	width := 4
	if len(os.Args) > 1 {
		n, err := strconv.Atoi(os.Args[1])
		if err != nil {
			fmt.Fprintf(os.Stderr, "invalid samples: %v\n", err)
			os.Exit(2)
		}
		samples = n
	}
	if len(os.Args) > 2 {
		n, err := strconv.Atoi(os.Args[2])
		if err != nil {
			fmt.Fprintf(os.Stderr, "invalid width: %v\n", err)
			os.Exit(2)
		}
		width = n
	}
	if samples <= 0 || width <= 0 || width > 32 {
		fmt.Fprintln(os.Stderr, "samples and width must be positive; width <= 32")
		os.Exit(2)
	}

	seed := uint64(0xC0DEC0DE)
	passed := 0
	failed := 0
	checksum := int64(1469598103934665603)

	for s := 0; s < samples; s++ {
		weights := make([]int64, width)
		x := make([]int64, width)
		for i := 0; i < width; i++ {
			weights[i] = next(&seed)
			x[i] = next(&seed)
		}
		b := next(&seed)
		target := next(&seed)
		err := pred(weights, x, b) - target
		ok := true

		for i := 0; i < width; i++ {
			analytic := 2 * err * x[i]
			plus := append([]int64(nil), weights...)
			minus := append([]int64(nil), weights...)
			plus[i]++
			minus[i]--
			numeric := (loss(plus, x, b, target) - loss(minus, x, b, target)) / 2
			if analytic != numeric {
				ok = false
			}
			checksum = (checksum ^ analytic) * 1099511628211
			checksum = (checksum ^ numeric) * 1099511628211
		}

		analyticB := 2 * err
		numericB := (loss(weights, x, b+1, target) - loss(weights, x, b-1, target)) / 2
		if analyticB != numericB {
			ok = false
		}
		checksum = (checksum ^ analyticB) * 1099511628211
		checksum = (checksum ^ numericB) * 1099511628211

		if ok {
			passed++
		} else {
			failed++
		}
	}

	status := "pass"
	if failed != 0 {
		status = "fail"
	}
	out := Receipt{
		Kind:     "tensor-autodiff-native-verifier",
		Samples:  samples,
		Width:    width,
		Passed:   passed,
		Failed:   failed,
		Checksum: checksum,
		Status:   status,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintf(os.Stderr, "encode receipt: %v\n", err)
		os.Exit(2)
	}
	if failed != 0 {
		os.Exit(1)
	}
}
GO

(cd "$WORK" && go build -o "$BIN" "$SRC")
"$BIN" "$SAMPLES" "$WIDTH"

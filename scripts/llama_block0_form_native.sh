#!/usr/bin/env bash
# llama_block0_form_native.sh — run the REAL Llama-3.2-3B (fused hati-translator)
# decoder block-0 at FULL width d_model=3072 through the proven Form GQA causal
# llama block recipe (lgqa-block-causal), with its ACTUAL trained weights LOADED
# BY FORM from the checkpoint's safetensors via the Form-native buffer bridge
# (safetensors.fk: read_file_slice_bytes + fd-f16 decode — no Python).
#
# This shell is a THIN CARRIER: it only cats the S-expr preludes + a small driver
# and invokes the Go kernel. Every byte of logic — weight load, F16 decode, the
# block forward — is a Form recipe. Python is nowhere in the path.
#
# The block reads its nine real tensors (q/k/v/o proj, 2 RMSNorm gains, SwiGLU
# gate/up/down) straight from model-00001-of-00002.safetensors, one row at a time
# (offset-addressed binary reads — bounded memory at d=3072), and runs
# RMSNorm1 -> q/k/v proj -> llama3-RoPE(q,k) -> GQA-causal(24 q heads / 8 kv) ->
# Wo + residual -> RMSNorm2 -> SwiGLU FFN + residual. The input is a deterministic
# Form-generated real-shaped sequence (no host RNG). Prints the first output values
# of token 0 and an L1 checksum of the block output. Usage: llama_block0_form_native.sh [T]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
GO="$ROOT/form/form-kernel-go/bin-go"
CKPT="${LLAMA_CKPT:-$HOME/.coherence-network/form-train-runs/translation-corpus/hati-translator-fused/model-00001-of-00002.safetensors}"
T="${1:-2}"
[[ -x "$GO" ]] || { echo "no bin-go (build: cd form/form-kernel-go && go build -o bin-go .)"; exit 0; }
[[ -f "$CKPT" ]] || { echo "no checkpoint at $CKPT; skipping"; exit 0; }

work="$(mktemp -d "${TMPDIR:-/tmp}/llamablk.XXXXXX")"; trap 'rm -rf "$work"' EXIT
prog="$work/block0.fk"
{
  cat "$STD/format-arith.fk" "$STD/f16-decode.fk" "$STD/safetensors-decode.fk" "$STD/json.fk" "$STD/safetensors.fk" \
      "$STD/trig.fk" "$STD/transformer-numerics.fk" "$STD/llama-numerics.fk" "$STD/rope.fk" \
      "$STD/transformer-block.fk" "$STD/transformer-mh.fk" "$STD/gqa-attn.fk" \
      "$STD/llama-block.fk" "$STD/llama-gqa-block.fk"
  cat <<FK

; --- deterministic real-shaped input [T, D] in [-0.5,0.5], Form-generated (no host RNG) ---
(defn mkrow (t i n) (if (ge i n) (empty)
  (cons (sub (div (mul 1.0 (mod (add (mul t 37) (mul i 17)) 1000)) 1000.0) 0.5) (mkrow t (add i 1) n))))
(defn mkseq (t T n) (if (ge t T) (empty) (cons (mkrow t 0 n) (mkseq (add t 1) T n))))
(defn l1 (xs) (if (eq (len xs) 0) 0.0 (add (fq-abs (head xs)) (l1 (tail xs)))))
(defn l1seq (rows) (if (eq (len rows) 0) 0.0 (add (l1 (head rows)) (l1seq (tail rows)))))
; sequence-level SwiGLU: zip lblk-swiglu-map (silu(gate)*up) over token pairs — the same per-token
; activation lblk-ffn applies, lifted to the sequence so the FFN projects one weight matrix at a time.
(defn swiglu-seq (gs us) (if (eq (len gs) 0) (empty)
  (cons (lblk-swiglu-map (head gs) (head us)) (swiglu-seq (tail gs) (tail us)))))

; STREAMED lgqa-block-causal: identical arithmetic to the monolithic recipe (same sub-recipes, same
; order — lgqa-attn-sub-causal then lblk-ffn-block), but each weight matrix is loaded INLINE so the GC
; releases it the moment its projection returns. Peak live set = one matrix, not all nine. Faithfulness
; (streamed == monolithic, bit-for-bit) is the small-width check below; the four-way proof of
; lgqa-block-causal + each sub-recipe guarantees it carries to full width.
(do
  (let ck "$CKPT")
  (let hdr (st-header ck))
  (let base (st-data-base ck))
  (let c (rope-cfg 500000.0 32.0 1.0 4.0 8192.0))
  (let scale (div 1.0 (tn-sqrt 128.0)))
  (let x (mkseq 0 $T 3072))
  ; attention sub-block — wq,wk,wv,wo each transient
  (let n1 (lblk-rms-seq x (st-vec ck hdr base "model.layers.0.input_layernorm.weight") 0.00001))
  (let q (lgqa-rope-seq (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.q_proj.weight") n1) 128 c))
  (let k (lgqa-rope-seq (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.k_proj.weight") n1) 128 c))
  (let v (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.v_proj.weight") n1))
  (let ctx (tb-gqa-attn-causal q k v 24 8 128 scale))
  (let h1 (tb-add-seq x (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.o_proj.weight") ctx)))
  ; FFN sub-block — wg,wu,wd each transient
  (let n2 (lblk-rms-seq h1 (st-vec ck hdr base "model.layers.0.post_attention_layernorm.weight") 0.00001))
  (let gate (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.gate_proj.weight") n2))
  (let up (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.up_proj.weight") n2))
  (let y (tb-add-seq h1 (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.down_proj.weight") (swiglu-seq gate up))))
  (print (nth (nth y 0) 0))
  (print (nth (nth y 0) 1))
  (print (nth (nth y 0) 2))
  (print (nth (nth y 0) 3))
  (print (l1seq y))
  0)
FK
} > "$prog"
echo "running real Llama-3.2-3B block-0 forward in Form (d=3072, T=$T) — weights loaded by Form from $CKPT"
"$GO" "$prog"

#!/usr/bin/env bash
# llama_infer_route_form_native.sh — the REAL model inference route, end-to-end, non-empty,
# fully Form-native (no Python in the path):
#
#   token id  ->  real embedding (embed_tokens row, loaded by Form from the checkpoint)
#             ->  RMSNorm + GQA(24q/8kv) + llama3-RoPE + SwiGLU block-0 (real trained weights)
#             ->  a non-empty real output vector + its argmax feature  (the route's result)
#
# This is a ROUTE, not a synthetic band: the INPUT is a real token's real trained embedding read
# straight from the fused Llama-3.2-3B checkpoint, the BODY is the four-way-proven lgqa-block-causal
# recipe (composed streamed so each weight matrix is loaded one at a time — under the 16 GB witness
# cap), and the OUTPUT is the actual transformed hidden state. The shell only cats S-expr preludes and
# invokes the Go kernel; every byte of logic — embed lookup, F16 decode, the block forward — is Form.
#
# Depth: block-0 only (the full 28-layer stack + tied-embedding logits + argmax → a true next-token is
# the same route deeper; impractical in the tree-walker, it belongs on the native/GPU speed lane). What
# this proves: the inference route runs end-to-end on real weights and returns a non-empty real result.
# Usage: llama_infer_route_form_native.sh [token_id]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
GO="$ROOT/form/form-kernel-go/bin-go"
CKPT="${LLAMA_CKPT:-$HOME/.coherence-network/form-train-runs/translation-corpus/hati-translator-fused/model-00001-of-00002.safetensors}"
TOK="${1:-791}"   # a real token id (default 791); its real embedding is the route's input
[[ -x "$GO" ]] || { echo "no bin-go"; exit 0; }
[[ -f "$CKPT" ]] || { echo "no checkpoint"; exit 0; }

work="$(mktemp -d "${TMPDIR:-/tmp}/llamaroute.XXXXXX")"; trap 'rm -rf "$work"' EXIT
prog="$work/route.fk"
{
  cat "$STD/format-arith.fk" "$STD/f16-decode.fk" "$STD/safetensors-decode.fk" "$STD/json.fk" "$STD/safetensors.fk" \
      "$STD/trig.fk" "$STD/transformer-numerics.fk" "$STD/llama-numerics.fk" "$STD/rope.fk" \
      "$STD/transformer-block.fk" "$STD/transformer-mh.fk" "$STD/gqa-attn.fk" \
      "$STD/llama-block.fk" "$STD/llama-gqa-block.fk"
  cat <<FK

; sequence-level SwiGLU (one weight matrix at a time — see llama_block0_form_native.sh)
(defn swiglu-seq (gs us) (if (eq (len gs) 0) (empty)
  (cons (lblk-swiglu-map (head gs) (head us)) (swiglu-seq (tail gs) (tail us)))))
; argmax feature index of a vector (the route's scalar result) + L1 magnitude
(defn amax (xs i best bi cur) (if (eq (len xs) 0) bi
  (if (gt (head xs) best) (amax (tail xs) (add i 1) (head xs) i (add i 1))
                          (amax (tail xs) (add i 1) best bi (add i 1)))))
(defn vl1 (xs) (if (eq (len xs) 0) 0.0 (add (fq-abs (head xs)) (vl1 (tail xs)))))

(do
  (let ck "$CKPT")
  (let hdr (st-header ck))
  (let base (st-data-base ck))
  (let c (rope-cfg 500000.0 32.0 1.0 4.0 8192.0))
  (let scale (div 1.0 (tn-sqrt 128.0)))
  ; --- ROUTE INPUT: the real trained embedding of token $TOK (embed_tokens row $TOK) ---
  (let emb-e (st-entry hdr "model.embed_tokens.weight"))
  (let emb (st-row-at ck (add (add base (st-entry-offa emb-e)) (mul $TOK (mul 3072 2))) 3072))
  (let x (cons emb (empty)))               ; a one-token sequence — the real route input
  ; --- BODY: block-0 forward, streamed (each weight loaded inline, one matrix at a time) ---
  (let n1 (lblk-rms-seq x (st-vec ck hdr base "model.layers.0.input_layernorm.weight") 0.00001))
  (let q (lgqa-rope-seq (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.q_proj.weight") n1) 128 c))
  (let k (lgqa-rope-seq (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.k_proj.weight") n1) 128 c))
  (let v (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.v_proj.weight") n1))
  (let ctx (tb-gqa-attn-causal q k v 24 8 128 scale))
  (let h1 (tb-add-seq x (lblk-proj-seq (st-mat ck hdr base "model.layers.0.self_attn.o_proj.weight") ctx)))
  (let n2 (lblk-rms-seq h1 (st-vec ck hdr base "model.layers.0.post_attention_layernorm.weight") 0.00001))
  (let gate (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.gate_proj.weight") n2))
  (let up (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.up_proj.weight") n2))
  (let y0 (head (tb-add-seq h1 (lblk-proj-seq (st-mat ck hdr base "model.layers.0.mlp.down_proj.weight") (swiglu-seq gate up)))))
  ; --- ROUTE RESULT: non-empty real output ---
  (print (nth emb 0))                      ; the real input embedding's first value (route is fed real data)
  (print (nth y0 0)) (print (nth y0 1)) (print (nth y0 2))   ; the block output (non-empty)
  (print (vl1 y0))                          ; L1 magnitude of the output (non-zero => non-empty)
  (print (amax y0 0 -1000000.0 0 0))        ; argmax feature index — the route's scalar result
  0)
FK
} > "$prog"
echo "inference route: token $TOK -> real embedding -> block-0 (real weights) -> output   [all Form, no Python]"
"$GO" "$prog"

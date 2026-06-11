#!/usr/bin/env python3
# scripts/whisper_block0_carrier.py — M6 carrier: load safetensors, slice, quantize, and run reference forward pass.

import os
import json
import numpy as np
from huggingface_hub import hf_hub_download
import safetensors

HERE = os.path.dirname(os.path.abspath(__file__))


def get_whisper_tiny_path():
    # Downloads or locates the safetensors file
    print("Locating whisper-tiny safetensors...")
    path = hf_hub_download(repo_id='openai/whisper-tiny', filename='model.safetensors')
    return path

def quantize_dequantize_int8(w):
    """Simulates the M2 tq-int8-encode/decode roundtrip."""
    absmax = float(np.max(np.abs(w)))
    if absmax == 0.0:
        return w, 0.0, np.zeros_like(w, dtype=int).tolist()
    scale = absmax / 127.0
    # Numpy round defaults to round half-to-even, matching the Form kernel round
    codes = np.round(w / scale).astype(int)
    dequant = (codes * scale).astype(float)
    return dequant, scale, codes.tolist()

def gelu_tanh(x):
    """GELU tanh approximation matching tn-gelu in transformer-numerics.fk."""
    return 0.5 * x * (1.0 + np.tanh(0.7978845608028654 * (x + 0.044715 * x**3)))

def layernorm(x, gamma, beta, eps=1e-5):
    """LayerNorm matching tn-layernorm in transformer-numerics.fk."""
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps) * gamma + beta

def main():
    path = get_whisper_tiny_path()
    print("Loading weights from:", path)
    
    # We want block 0 of the encoder:
    # d_model=384, d_ffn=1536
    # Slices to d_model=8, d_ffn=16 to keep interpreter runs extremely fast
    d_model = 8
    d_ffn = 16
    eps = 1e-5
    
    weights = {}
    with safetensors.safe_open(path, framework='numpy') as f:
        # 1. LN1
        weights['g1'] = f.get_tensor('model.encoder.layers.0.self_attn_layer_norm.weight')[:d_model].astype(float).tolist()
        weights['be1'] = f.get_tensor('model.encoder.layers.0.self_attn_layer_norm.bias')[:d_model].astype(float).tolist()
        
        # 2. QKV & Out Projections
        wq_raw = f.get_tensor('model.encoder.layers.0.self_attn.q_proj.weight')[:d_model, :d_model]
        wk_raw = f.get_tensor('model.encoder.layers.0.self_attn.k_proj.weight')[:d_model, :d_model]
        wv_raw = f.get_tensor('model.encoder.layers.0.self_attn.v_proj.weight')[:d_model, :d_model]
        wo_raw = f.get_tensor('model.encoder.layers.0.self_attn.out_proj.weight')[:d_model, :d_model]
        
        bq_raw = f.get_tensor('model.encoder.layers.0.self_attn.q_proj.bias')[:d_model]
        bk_raw = np.zeros(d_model) # Key projection has no bias in Whisper-tiny
        bv_raw = f.get_tensor('model.encoder.layers.0.self_attn.v_proj.bias')[:d_model]
        bo_raw = f.get_tensor('model.encoder.layers.0.self_attn.out_proj.bias')[:d_model]
        
        # 3. LN2
        weights['g2'] = f.get_tensor('model.encoder.layers.0.final_layer_norm.weight')[:d_model].astype(float).tolist()
        weights['be2'] = f.get_tensor('model.encoder.layers.0.final_layer_norm.bias')[:d_model].astype(float).tolist()
        
        # 4. MLP FC1 & FC2
        w1_raw = f.get_tensor('model.encoder.layers.0.fc1.weight')[:d_ffn, :d_model]
        w2_raw = f.get_tensor('model.encoder.layers.0.fc2.weight')[:d_model, :d_ffn]
        
        b1_raw = f.get_tensor('model.encoder.layers.0.fc1.bias')[:d_ffn]
        b2_raw = f.get_tensor('model.encoder.layers.0.fc2.bias')[:d_model]

    # Quantize and dequantize all weights to match the Form stdlib quantization step
    wq, wq_scale, wq_codes = quantize_dequantize_int8(wq_raw)
    wk, wk_scale, wk_codes = quantize_dequantize_int8(wk_raw)
    wv, wv_scale, wv_codes = quantize_dequantize_int8(wv_raw)
    wo, wo_scale, wo_codes = quantize_dequantize_int8(wo_raw)
    w1, w1_scale, w1_codes = quantize_dequantize_int8(w1_raw)
    w2, w2_scale, w2_codes = quantize_dequantize_int8(w2_raw)
    
    # Biases are kept in float format (M2 quantizes weights, not biases)
    bq = bq_raw.astype(float).tolist()
    bk = bk_raw.astype(float).tolist()
    bv = bv_raw.astype(float).tolist()
    bo = bo_raw.astype(float).tolist()
    b1 = b1_raw.astype(float).tolist()
    b2 = b2_raw.astype(float).tolist()

    # Generate a deterministic input sequence of length T=2
    # Standard normal mock inputs for sequence length T=2, d_model=8
    x = np.array([
        [1.2, -0.4, 0.8, -1.1, 0.3, -0.6, 1.5, -0.2],
        [-0.5, 1.1, -0.9, 0.4, -1.2, 0.7, -0.3, 1.4]
    ])
    
    # Forward Pass Simulation
    # Step 1: LN1
    ln1_out = layernorm(x, np.array(weights['g1']), np.array(weights['be1']), eps)
    
    # Step 2: Attention projections
    q = ln1_out @ wq.T + bq
    k = ln1_out @ wk.T + bk
    v = ln1_out @ wv.T + bv
    
    # Step 3: Attention scores & Softmax
    scale = 1.0 / np.sqrt(d_model)
    scores = (q @ k.T) * scale
    
    # Softmax over final axis (keys)
    scores_max = np.max(scores, axis=-1, keepdims=True)
    exp_scores = np.exp(scores - scores_max)
    alphas = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)
    
    # Attention context
    attn_out = alphas @ v
    
    # Out projection
    attn_proj = attn_out @ wo.T + bo
    
    # Residual 1
    h = x + attn_proj
    
    # Step 4: LN2
    ln2_out = layernorm(h, np.array(weights['g2']), np.array(weights['be2']), eps)
    
    # Step 5: MLP
    fc1_out = ln2_out @ w1.T + b1
    fc1_gelu = gelu_tanh(fc1_out)
    fc2_out = fc1_gelu @ w2.T + b2
    
    # Residual 2
    y = h + fc2_out
    
    # Prepare payload JSON
    payload = {
        "x": x.tolist(),
        "eps": eps,
        "scale": scale,
        "g1": weights['g1'],
        "be1": weights['be1'],
        "wq_codes": wq_codes, "wq_scale": wq_scale, "bq": bq,
        "wk_codes": wk_codes, "wk_scale": wk_scale, "bk": bk,
        "wv_codes": wv_codes, "wv_scale": wv_scale, "bv": bv,
        "wo_codes": wo_codes, "wo_scale": wo_scale, "bo": bo,
        "g2": weights['g2'],
        "be2": weights['be2'],
        "w1_codes": w1_codes, "w1_scale": w1_scale, "b1": b1,
        "w2_codes": w2_codes, "w2_scale": w2_scale, "b2": b2,
        
        # Expected outputs for verification
        "expected_alpha0": alphas[0].tolist(),
        "expected_h": h.tolist(),
        "expected_y": y.tolist()
    }
    
    out_dir = os.path.join(os.path.dirname(HERE), "form", "form-samples")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "whisper_block0_test_data.json")
    with open(out_path, "w") as f_out:
        json.dump(payload, f_out, indent=2)
    print("Successfully generated test data at:", out_path)

if __name__ == "__main__":
    main()

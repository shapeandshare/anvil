# Contract: Walkthrough Progression (Updated)

**Feature**: 006-llama-engine-evolution  
**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-14  

## Purpose

Define the updated walkthrough script progression (train0.py–train5.py) that teaches the Llama architecture step by step. Each script builds on the previous, culminating in a full Llama-aligned GPT.

## Progression

| Script | File | Teaches | Components Introduced |
|--------|------|---------|----------------------|
| **train0.py** | `examples/train0.py` | Single neuron | Weight + bias, sigmoid activation, numerical gradient, chain rule concept |
| **train1.py** | `examples/train1.py` | Linear layer (no activation) | Matrix multiply via `linear()` helper, multiple inputs/outputs, analytic gradient with chain rule |
| **train2.py** | `examples/train2.py` | RMSNorm with learned weights | RMSNorm formula with scale parameter (initialized to 1.0), `rmsnorm()` function, gradient flow through norm |
| **train3.py** | `examples/train3.py` | Self-attention with RoPE | Causal self-attention, QKV projections, half-split (rotate_half) RoPE applied to Q and K (not V), attention weights and weighted sum |
| **train4.py** | `examples/train4.py` | Transformer block with SwiGLU | Full transformer block: pre-attn RMSNorm → RoPE attention → residual → pre-MLP RMSNorm → SwiGLU MLP → residual (no embedding-level norm) |
| **train5.py** | `examples/train5.py` | Full Llama-aligned GPT | Multi-layer GPT using the engine, Adam optimizer, final RMSNorm before output, safetensors export, full training loop |

## What Changed From GPT-2 Walkthroughs

| Aspect | Old (GPT-2) | New (Llama) |
|--------|-------------|-------------|
| train2 | RMSNorm without learned scale | RMSNorm with learned `rms_1` weights |
| train3 | Learned `wpe` + ReLU MLP | half-split RoPE (no wpe) + no MLP in attention script |
| train4 | Learned wpe + fc1/fc2 + ReLU | half-split RoPE + gate/up/down + SiLU (SwiGLU) |
| train5 | GPT-2 engine (wpe, fc1/fc2, embedding-level norm, no final norm) | Llama engine (RoPE, SwiGLU, rms_1/rms_2/rms_final, no embedding-level norm) |
| train5 export | JSON only | Safetensors (primary) + JSON (secondary) |

## Design Principles

1. **One concept per script** — Each script teaches exactly one major new concept
2. **Progressive complexity** — Earlier scripts are pedagogical (explicit loops, comments), later scripts use the engine
3. **Composable** — Components from train2/3/4 build into train5's GPT class
4. **Runnable independently** — Each script produces a working model with sensible loss
5. **Comparable** — Hyperparameters kept consistent across scripts (n_embd=16, n_head=4 where applicable)

## Output Per Script

| Script | Loss Target | Model Components | Export |
|--------|-------------|-----------------|--------|
| train0 | Single weight learning | None (single Value) | None |
| train1 | MSE on linear mapping | Linear layer | None |
| train2 | Cross-entropy on norm output | RMSNorm with learned weights | None |
| train3 | Cross-entropy on attention output | Causal self-attn + RoPE | None |
| train4 | Cross-entropy on block output | Full transformer block | None |
| train5 | < 2.0 on 1000-step training | Full Llama GPT | safetensors + config + tokenizer |
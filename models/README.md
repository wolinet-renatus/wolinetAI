# Wolinet AI — Sovereign Models & Weights Repository

This directory contains the sovereign model weights, speculative decoding draft models, tokenizer configurations, checkpoints, and declarative model registrations for Wolinet AI.

## Directory Structure

```
models/
├── llm/                                  # Primary Sovereign Large Language Models (GGUF)
│   ├── wolinet-brain-r1-1.5b.gguf        # DeepSeek-R1 Distill Qwen 1.5B Uncensored (IQ4_XS imatrix, 131k ctx)
│   └── flintlock_3B_v0.1.IQ4_XS.gguf     # Flintlock 3B Sovereign Intelligence Engine (IQ4_XS imatrix)
├── dflash/                               # Speculative Decoding & AI Defense Layers (DFlash2 GGUF)
│   ├── orcacyber-defense-dflash2-q8_0.gguf # OrcaCyber Nano 1.0 AI Defense Layer (Q8_0, 262k ctx)
│   └── dflash2-v2-q8_0.gguf              # DFlash2 v2 High-Speed Acceleration Draft (Q8_0, 262k ctx)
├── configs/                              # Tokenizer, Generation & Vocabulary Metadata
│   ├── config.json                       # Transformer architecture hyperparameters
│   ├── generation_config.json            # Sampling defaults (temperature, top_p, repetition penalty)
│   ├── special_tokens_map.json           # Special tokens (<think>, </think>, <|im_start|>, etc.)
│   ├── tokenizer_config.json             # Fast tokenizer encoding configuration
│   ├── gitattributes                     # Git LFS tracking configuration
│   └── wolinet-brain-card.md             # Model card & benchmark provenance
├── checkpoints/                          # Self-training adapters & LoRA checkpoints
│   └── wolinet-coder-v2/                 # Self-training checkpoint metadata & weights
└── registrations/                        # Declarative model manifests for Xinference (1 per weight file)
    ├── wolinex-coder.json                # Sovereign coding & reasoning intelligence manifest (wolinet-brain-r1-1.5b.gguf)
    ├── flintlock-3b.json                 # Flintlock 3B manifest (flintlock_3B_v0.1.IQ4_XS.gguf)
    ├── orcacyber-defense-dflash.json     # OrcaCyber AI Defense manifest (orcacyber-defense-dflash2-q8_0.gguf)
    └── wolinex-speculative.json          # DFlash2 speculative acceleration manifest (dflash2-v2-q8_0.gguf)
```

---

## Active Sovereign Models

### 1. Primary Sovereign LLM (`models/llm/`)
| Model File | Architecture | Base Model | Quantization | Size | Native Context | Role |
|---|---|---|---|---|---|---|
| `wolinet-brain-r1-1.5b.gguf` | `qwen2` (28 blocks) | DeepSeek-R1 Distill Qwen 1.5B (Uncensored) | `IQ4_XS` (imatrix) | 972 MB | 131,072 tokens | **Wolinet Pro** / **Wolinex Coder** (Flagship sovereign local reasoning & coding engine) |

**Features:**
- Native DeepSeek-R1 `<think>` reasoning distillation.
- Uncensored instruction tuning by Thirdeye AI with zero over-moderation.
- High inference velocity on local CPU: ~135 prompt tokens/sec, ~30 generation tokens/sec.
- Zero external dependencies or marginal cost.

---

### 2. Speculative Decoding & Defense Layers (`models/dflash/`)
| Model File | Architecture | Blocks | Quantization | Size | Context | Purpose |
|---|---|---|---|---|---|---|
| `orcacyber-defense-dflash2-q8_0.gguf` | `dflash` | 5 | `Q8_0` | 1.96 GB | 262,144 tokens | Real-time cyber defense, prompt injection filtering & jailbreak neutralization |
| `qwen3.8-27b-dflash2-r3-q4_k_m.gguf` | `dflash` | 5 | `Q4_K_M` | 1.09 GB | 262,144 tokens | Speculative draft accelerator for Qwen 3.8 / 27B class models |
| `dflash2-v2-q8_0.gguf` | `dflash` | 5 | `Q8_0` | 1.05 GB | 262,144 tokens | General DFlash2 block-level speculative verification |

---

## Unified Sovereign Routing (Zero RAM Weight Duplication)

All requests to the platform are mapped transparently through Lango (LiteLLM Gateway on port `:4000`) and the native Rust Defense Core (`:8088`), backed by a single unified high-speed model instance with 12 GB RAM KV cache:

| Public Model Alias | Routed Engine | Engine Location | Key Capabilities |
|---|---|---|---|
| **Wolinet Pro** | `wolinex-coder` (`wolinet-brain-r1-1.5b.gguf`) | Local Mitambo (`:9997` via Rust Core) | 131k context, instant response, zero think delays |
| **Wolinex Coder** | `wolinex-coder` (`wolinet-brain-r1-1.5b.gguf`) | Local Mitambo (`:9997` via Rust Core) | Code generation, systems architecture, idiomatic syntax |
| **Secure Pro** | `wolinex-coder` (`wolinet-brain-r1-1.5b.gguf`) | Local Service (`:8088` & Gateway `:4000`) | Sovereign AI Cyber Defense, 1Panel Server Guard, Vulnerability Audit |
| **Wolinet Turbo Draft** | `wolinex-coder` (`wolinet-brain-r1-1.5b.gguf`) | Local Service (`:8088` & Gateway `:4000`) | High-speed draft response, 112+ tokens/sec prompt velocity |
| **OrcaCyber Defense**| `orcacyber-defense-dflash2-q8_0.gguf` | Local Service (`:8088` & `:4000/v1/defense/inspect`) | Sub-microsecond prompt injection & cybersecurity inspection |
| **Wolinet Max** | Gemini 3.8 Flash | Enterprise Cloud | Multimodal (Vision, Audio, Image generation, Embeddings) |
| **Wolinet Max Pro** | Moonshot Kimi K3.1 Pro MoE | Highspeed Cloud | 1 Million token context, long-horizon multi-file coding |
| **Scorpio** | DeepSeek V4.1 Flash | Frontier Cloud | 1 Million context, native vision, ultra-high throughput |
| **Scorpio Pro** | DeepSeek V4 Pro | Frontier Cloud | Complex mathematics, algorithmic proofs, deep reasoning |

---

## Registered Autonomous AI Agents (`http://127.0.0.1:4000/ui/agents/`)

The following specialized AI agents are live and registered in LiteLLM:

1. **Secure Pro — AI Cyber Defense Guard**
   - **Model:** `Secure Pro`
   - **Skills:** Prompt injection mitigation, jailbreak containment, real-time threat telemetry.
2. **1Panel Server & Infrastructure Guard**
   - **Model:** `Secure Pro`
   - **Skills:** 1Panel portal hardening, UFW firewall rules, Nginx reverse proxy SSL/TLS, Docker container isolation.
3. **Wolinex Code Security Auditor**
   - **Model:** `Wolinex Coder`
   - **Skills:** Static code vulnerability auditing (OWASP Top 10, SQLi, XSS), CVE remediation patching, secret scanning.
4. **DFlash Speculative Acceleration Drafter**
   - **Model:** `Wolinet Turbo Draft`
   - **Skills:** Multi-token block-diffusion drafting, latency benchmarking, speculative decoding telemetry.


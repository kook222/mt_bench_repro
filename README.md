<div align="center">

# MT-Bench Reproduction

**Reproducing _"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"_ (NeurIPS 2023)**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/Paper-NeurIPS%202023-red)](https://arxiv.org/abs/2306.05685)
[![Infra: A100](https://img.shields.io/badge/Infra-A100%2040GB-lightgrey?logo=nvidia)](https://www.nvidia.com/)

</div>

---

> **Goal:** Reproduce the *model ranking order* and *per-category performance trends* from the NeurIPS 2023 MT-Bench paper using open-source models (2024–2025 generation) and a local vLLM judge.
> Exact score matching is explicitly **not** the objective.

<br>

<p align="center">
  <img src="figures/mt_bench_summary.png" width="96%" alt="MT-Bench Reproduction Summary">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Results](#key-results)
  - [Phase 2 — 6-Model Comparison](#phase-2--6-model-comparison)
  - [Phase 3 — Judge Scaling Law](#phase-3--judge-scaling-law)
- [Experimental Setup](#experimental-setup)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Detailed Results](#detailed-results)
  - [Per-Category Heatmap](#per-category-heatmap)
  - [Hard vs. Easy Gap](#hard-vs-easy-gap)
  - [Pairwise Win Rates](#pairwise-win-rates)
  - [Judge Scaling Law](#judge-scaling-law)
  - [Cross-Judge Spearman ρ](#cross-judge-spearman-ρ)
  - [Question Count Sensitivity](#question-count-sensitivity)
- [Comparison with the Original Paper](#comparison-with-the-original-paper)
- [Conclusions](#conclusions)
- [Citation](#citation)

---

## Overview

This repository reimplements the evaluation pipeline from [Zheng et al. (NeurIPS 2023)](https://arxiv.org/abs/2306.05685) as a self-contained Python package (`mtbench_repro`). The experiment is structured in three phases:

| Phase | Description | Models | Judge | Status |
|-------|-------------|--------|-------|--------|
| **1** | Pipeline validation, self-judge baseline | Qwen2.5-7B | Qwen2.5-7B (self) | ✅ Done |
| **2** | 6-model comparison, external judge | 6 open-source models | Qwen2.5-14B | ✅ Done |
| **3** | Judge scaling law (7B → 32B) | 7 models (Phase 2 + Llama-3.1-8B) | Qwen2.5 7B/14B/32B | ✅ Done |

**Three grading methods** are implemented (matching the paper's evaluation protocol):

| Method | Paper Reference | Scope |
|--------|----------------|-------|
| Single-answer grading (1–10) | Figure 6, Table 8 | All categories |
| Pairwise comparison (AB/BA swap) | Figure 5, 9, §3.4 | All categories |
| Reference-guided grading | Figure 8, 10 | math / reasoning / coding |

---

## Key Results

### Phase 2 — 6-Model Comparison

<p align="center">
  <img src="figures/fig2_overall_rankings.png" width="88%" alt="Phase 2 Overall Rankings">
</p>

**Single-answer scores (Qwen2.5-14B judge):**

| Rank | Model | Params | Overall | Writing | Roleplay | Extraction | Reasoning | Math | Coding | STEM | Humanities |
|------|-------|--------|---------|---------|----------|------------|-----------|------|--------|------|------------|
| 1 | Phi-3.5-mini-Instruct | 3.8B | **8.09** | 8.25 | 7.70 | 7.65 | 7.75 | 8.30 | 8.15 | 8.25 | 8.65 |
| 2 | gemma-2-9b-it | 9B | 8.03 | 8.15 | 8.00 | 7.50 | 7.70 | 8.05 | 7.95 | 8.40 | 8.50 |
| 3 | Yi-1.5-9B-Chat | 9B | 7.97 | 8.10 | 8.05 | 8.05 | 7.45 | 8.00 | 7.20 | 8.50 | 8.40 |
| 4 | Mistral-7B-Instruct-v0.3 | 7B | 7.49 | 8.25 | 7.80 | 7.70 | 6.70 | 6.75 | 6.05 | 8.35 | 8.30 |
| 5 | SOLAR-10.7B-Instruct | 10.7B | 7.07 | 7.85 | 6.55 | 7.26 | 6.85 | 7.25 | 4.95 | 7.65 | 8.20 |
| 6 | Zephyr-7B-beta | 7B | 7.04 | 7.60 | 7.20 | 7.40 | 6.15 | 6.35 | 5.65 | 8.10 | 7.90 |

> **Note on Qwen2.5-7B:** Evaluated only in Phase 1 (self-judge, overall 8.12). Excluded from Phase 2 to prevent same-family self-judge bias.

---

### Phase 3 — Judge Scaling Law

<p align="center">
  <img src="figures/fig4_judge_scaling.png" width="85%" alt="Judge Scaling Law">
</p>

| Judge | Params | Inconsistency Rate | Clear Decision Rate | Score Range |
|-------|--------|--------------------|--------------------|----|
| Qwen2.5-7B | 7B | **78.75%** | 21.25% | 0.84 pt |
| Qwen2.5-14B | 14B | 46.85% | 53.15% | 1.13 pt |
| Qwen2.5-32B | 32B | **32.86%** | 67.14% | 1.47 pt |

**Key finding:** As judge size increases from 7B to 32B, pairwise inconsistency drops by **45.9 pp** — a strong judge scaling effect. Larger judges are also more *discriminative* (wider score spread).

---

## Experimental Setup

### Models Evaluated

| Phase | Model | Params | Notes |
|-------|-------|--------|-------|
| 1 | Qwen2.5-7B-Instruct | 7B | Self-judge baseline only |
| 2, 3 | **Phi-3.5-mini-Instruct** | 3.8B | Microsoft |
| 2, 3 | **gemma-2-9b-it** | 9B | Google |
| 2, 3 | **Yi-1.5-9B-Chat** | 9B | 01.AI |
| 2, 3 | **Mistral-7B-Instruct-v0.3** | 7B | Mistral AI |
| 2, 3 | **SOLAR-10.7B-Instruct** | 10.7B | Upstage |
| 2, 3 | **Zephyr-7B-beta** | 7B | HuggingFace H4 |
| 3 only | **Llama-3.1-8B-Instruct** | 8B | Meta (replaces Qwen2.5-7B) |

### Judge Models (Phase 3 Scaling)

| Judge | Params | VRAM | Quantization | Status |
|-------|--------|------|-------------|--------|
| Qwen2.5-7B-Instruct | 7B | ~14 GB | fp16 | ✅ |
| Qwen2.5-14B-Instruct | 14B | ~28 GB | fp16 | ✅ |
| Qwen2.5-32B-Instruct | 32B | ~20 GB | AWQ 4-bit | ✅ |
| Qwen2.5-72B-Instruct | 72B | ~39 GB | AWQ 4-bit | ❌ OOM on A100 40 GB |

> Using a single Qwen2.5 family for all judge sizes eliminates architecture variance, isolating the pure size effect.

### Infrastructure

- **GPU:** NVIDIA A100 SXM4 40 GB
- **Serving:** vLLM v0.6.6 (OpenAI-compatible API)
- **Benchmark:** MT-Bench 80 questions × 2 turns = 160 scored turns per model
- **Generation temp:** 0.7 · **Judge temp:** 0.0 (greedy)

---

## Repository Structure

```
mt_bench_repro/
├── src/mtbench_repro/
│   ├── schemas.py          # Data classes (MTBenchQuestion, ModelAnswer, JudgmentSingle, …)
│   ├── io_utils.py         # JSONL streaming I/O with resume support
│   ├── client.py           # ChatClient (vLLM / OpenAI API / mock)
│   ├── prompts.py          # Judge prompts (paper Figures 5–10) + score parsers
│   ├── generate.py         # 2-turn answer generation with resume
│   ├── judge_single.py     # Single-answer grading (Fig. 6)
│   ├── judge_pairwise.py   # Pairwise comparison with AB/BA swap (Fig. 5/9)
│   ├── judge_reference.py  # Reference-guided grading (Fig. 8/10)
│   ├── aggregate.py        # Aggregation, model rankings, pairwise matrix
│   └── cli.py              # Unified CLI (5 subcommands)
├── scripts/
│   ├── run_mock_full.sh                  # End-to-end mock pipeline (no GPU)
│   ├── run_generate_multi_a100.sh        # Phase 2: generate 6-model answers
│   ├── run_judge_multi_a100.sh           # Phase 2: judge + aggregate
│   ├── run_generate_phase3_a100.sh       # Phase 3: generate Llama-3.1-8B answers
│   ├── run_judge_phase3_a100.sh          # Phase 3: 3 judge sizes sequentially
│   ├── analyze_phase3.py                 # Judge scaling + Q-size analysis
│   └── generate_figures.py              # Reproduce all figures in this README
├── data/
│   ├── mt_bench_questions.jsonl          # 80 MT-Bench questions (2 turns each)
│   ├── answers/                          # Model answers (JSONL, one file per model)
│   ├── judgments/                        # Phase 2 judgments
│   ├── judgments_phase3/judge_{7B,14B,32B}/   # Phase 3 judgments by judge size
│   ├── results_multi.csv                 # Phase 2 aggregated scores
│   ├── results_phase3_judge_{7B,14B,32B}.csv
│   └── results_phase3_qsize.csv
└── figures/                              # All publication-quality figures
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/<your-handle>/mt_bench_repro.git
cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src
```

### Mock Pipeline (no GPU required)

```bash
bash scripts/run_mock_full.sh
```

### CLI Subcommands

```bash
# 1. Generate answers (requires vLLM running at localhost:8000)
python -m mtbench_repro.cli generate \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --model-id Phi-3.5-mini-Instruct \
  --vllm-host localhost --vllm-port 8000

# 2. Single-answer grading
python -m mtbench_repro.cli judge-single \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-id Phi-3.5-mini-Instruct \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# 3. Pairwise comparison (AB + BA)
python -m mtbench_repro.cli judge-pairwise \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-a Phi-3.5-mini-Instruct \
  --model-b gemma-2-9b-it \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# 4. Reference-guided grading (math / reasoning / coding)
python -m mtbench_repro.cli judge-reference \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --mode single \
  --model-id Phi-3.5-mini-Instruct \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# 5. Aggregate results
python -m mtbench_repro.cli aggregate \
  --judgments-dir data/judgments/ \
  --output-csv data/results.csv

# 6. Reproduce all figures
python3 scripts/generate_figures.py
```

> Always run as `PYTHONPATH=src python -m mtbench_repro.cli …`. Direct `python src/…/cli.py` causes import errors.

### Full A100 Pipeline

```bash
# Phase 2
bash scripts/run_generate_multi_a100.sh   # answer generation
bash scripts/run_judge_multi_a100.sh      # judging + aggregation

# Phase 3
bash scripts/run_generate_phase3_a100.sh  # Llama-3.1-8B answers only (6 others reused)
bash scripts/run_judge_phase3_a100.sh     # judge 7B → 14B → 32B sequentially (~12–20 h)

# Analysis
export PYTHONPATH=src
python3 scripts/analyze_phase3.py
```

---

## Detailed Results

### Per-Category Heatmap

<p align="center">
  <img src="figures/fig1_category_heatmap.png" width="90%" alt="Per-Category Heatmap">
</p>

Coding and Reasoning are the most discriminative categories. Phi-3.5-mini dominates in Math/Coding; SOLAR-10.7B and Zephyr-7B fall far behind in Coding (4.95, 5.65).

---

### Hard vs. Easy Gap

<p align="center">
  <img src="figures/fig3_hard_easy_gap.png" width="85%" alt="Hard vs Easy Gap">
</p>

| Model | Hard avg<br>(math/reasoning/coding) | Easy avg<br>(writing/roleplay/humanities) | Gap (Easy − Hard) |
|-------|--------|--------|-------|
| Phi-3.5-mini | 8.07 | 8.20 | +0.13 |
| gemma-2-9b | 7.90 | 8.22 | +0.32 |
| Yi-1.5-9B | 7.55 | 8.18 | +0.63 |
| Mistral-7B | 6.50 | 8.12 | **+1.62** |
| SOLAR-10.7B | 6.35 | 7.53 | +1.18 |
| Zephyr-7B | 6.05 | 7.57 | **+1.52** |

**Replicates the paper's core pattern:** stronger models have smaller hard/easy gaps. Mistral-7B and Zephyr-7B are disproportionately weak on hard tasks despite reasonable writing scores.

---

### Pairwise Win Rates

| Rank | Model | Win Rate | Played |
|------|-------|----------|--------|
| 1 | gemma-2-9b-it | **79.4%** | 209 |
| 2 | Phi-3.5-mini-Instruct | 76.3% | 219 |
| 3 | Yi-1.5-9B-Chat | 66.1% | 202 |
| 4 | Mistral-7B-Instruct-v0.3 | 43.4% | 206 |
| 5 | SOLAR-10.7B-Instruct | 25.2% | 214 |
| 6 | Zephyr-7B-beta | 15.2% | 244 |

Single ↔ Pairwise Spearman ρ = **0.943** — strong convergence, with one notable exception: the top-2 rank flips between methods (Single: Phi > gemma; Pairwise: gemma > Phi).

> Inconsistency rate: 46.1% (553/1200) — significantly higher than estimated GPT-4 levels (~20%), reflecting the limitations of a 14B judge on pairwise tasks.

---

### Judge Scaling Law

<p align="center">
  <img src="figures/fig4_judge_scaling.png" width="85%" alt="Judge Scaling Law">
</p>

<p align="center">
  <img src="figures/fig5_phase3_scores.png" width="88%" alt="Phase 3 Scores by Judge Size">
</p>

**Phase 3 overall scores by judge:**

| Rank | Model | Judge 7B | Judge 14B | Judge 32B | Mean |
|------|-------|----------|-----------|-----------|------|
| 1 | Phi-3.5-mini-Instruct | 8.04 | 8.09 | 8.06 | **8.06** |
| 2 | gemma-2-9b-it | 7.87 | 8.03 | 8.09 | 7.99 |
| 3 | Llama-3.1-8B-Instruct | 7.89 | 8.17 | 7.71 | 7.92 |
| 4 | Yi-1.5-9B-Chat | 7.98 | 7.97 | 7.79 | 7.91 |
| 5 | Mistral-7B-Instruct-v0.3 | 7.45 | 7.49 | 7.09 | 7.34 |
| 6 | SOLAR-10.7B-Instruct | 7.34 | 7.07 | 7.02 | 7.14 |
| 7 | Zephyr-7B-beta | 7.20 | 7.04 | 6.62 | 6.95 |

---

### Cross-Judge Spearman ρ

<p align="center">
  <img src="figures/fig6_spearman_heatmap.png" width="42%" alt="Cross-Judge Spearman ρ">
</p>

| | Judge 7B | Judge 14B | Judge 32B |
|--|---------|-----------|-----------|
| **Judge 7B** | — | 0.821 | 0.786 |
| **Judge 14B** | 0.821 | — | 0.750 |
| **Judge 32B** | 0.786 | 0.750 | — |

Model rankings are **robustly preserved** across judge sizes (all ρ > 0.75). The top (Phi/gemma) and bottom (Zephyr) positions are consistent regardless of judge choice.

---

### Question Count Sensitivity

<p align="center">
  <img src="figures/fig7_qsize_sensitivity.png" width="62%" alt="Question Count Sensitivity">
</p>

| N Questions | Mean Spearman ρ | Min | Max |
|-------------|----------------|-----|-----|
| 10 | 0.777 | 0.321 | 0.964 |
| 20 | 0.839 | 0.464 | 1.000 |
| 40 | 0.857 | 0.607 | 1.000 |
| **60** | **0.952** | 0.643 | 1.000 |
| 80 | 1.000 | — | — |

Ranking stabilizes at **≥60 questions** (ρ ≥ 0.95). With only 10 questions, rankings can be highly unreliable (min ρ = 0.32). MT-Bench's 80-question design is empirically well-calibrated.

---

## Comparison with the Original Paper

| Metric | Original (GPT-4 judge, 2023) | This Reproduction (Qwen14B judge, 2026) |
|--------|-------------------------------|----------------------------------------|
| Score range | 2.61 – 8.99 (6.38 pt) | 7.04 – 8.09 (1.05 pt) |
| Hard/Easy gap pattern | ✅ Higher-ranked models have smaller gap | ✅ Same pattern reproduced |
| Single ↔ Pairwise convergence | ✅ | ⚠️ Partial — ρ = 0.943, top-2 rank inverted |
| Pairwise inconsistency rate | ~20% (estimated) | 46.1% (judge model limitation) |
| Parse failure rate | — | 0 / 560 (0%) in all phases |

### Why Scores Are Compressed

2025-generation models (Phi-3.5-mini, gemma-2-9b, etc.) are substantially stronger than the 2023-era models in the original paper (GPT-4, LLaMA-13B, Vicuna-13B). As a result, all models cluster at the high end (7.0–8.1), reducing the effective score spread from 6.38 pt to ~1.05 pt.

---

## Conclusions

| Claim from the Paper | Reproduction Result |
|----------------------|---------------------|
| Hard categories (math/reasoning/coding) show larger inter-model gaps | ✅ Confirmed — gap +0.13 (Phi) to +1.62 (Mistral) |
| Single-answer and pairwise rankings converge | ⚠️ Partial — ρ = 0.943; top-2 flip observed |
| LLM-as-a-Judge can reliably rank models | ⚠️ Conditional — rankings stable but inconsistency 46% with 14B judge |
| Larger models ≠ better performance | ✅ SOLAR-10.7B (5th) < Phi-3.5-mini-3.8B (1st) |

### Phase 3 Additional Findings

| Finding | Result |
|---------|--------|
| Larger judge → lower inconsistency rate | ✅ 7B(78.75%) → 14B(46.85%) → 32B(32.86%), monotone decrease |
| Model rankings stable across judge sizes | ✅ Cross-judge ρ > 0.75 in all pairs |
| Larger judge → higher discriminability | ✅ Score range: 0.84 pt (7B) → 1.47 pt (32B) |
| Qwen2.5-72B AWQ on A100 40 GB | ❌ OOM — model weights alone require ~39 GB |

### Recommendation

For LLM-as-a-Judge deployments:
- **14B minimum** for reliable pairwise judgments (inconsistency drops below 50%)
- **32B** for fine-grained discrimination (inconsistency ~33%, clear decision ~67%)
- **7B judge** is dominated by position bias (78.75% inconsistency) — not recommended

---

## Paper–Code Correspondence

| Paper | Implementation | Description |
|-------|---------------|-------------|
| Figure 5 | `prompts._SYSTEM_PAIRWISE` | Basic pairwise prompt |
| Figure 6 | `prompts._SYSTEM_SINGLE` | Single grading prompt |
| Figure 7 | `prompts._SYSTEM_PAIRWISE_MATH_COT` | CoT pairwise |
| Figure 8 | `prompts._SYSTEM_PAIRWISE_REFERENCE` | Reference-guided pairwise |
| Figure 9 | `prompts.build_multiturn_pairwise_prompt` | Multi-turn pairwise |
| Figure 10 | `prompts.build_multiturn_single_prompt` | Reference-guided multi-turn single |
| Section 3.4 | `judge_pairwise.judge_pairwise_question` | Conservative swap (winner only if AB = BA) |
| Table 8 | `aggregate.compute_single_scores` | MT-Bench Score (mean over 160 turns) |

---

## Citation

If you use this reproduction, please also cite the original paper:

```bibtex
@inproceedings{zheng2023judging,
  title     = {Judging {LLM}-as-a-Judge with {MT}-Bench and Chatbot Arena},
  author    = {Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and Zhuang, Siyuan
               and Wu, Zhanghao and Zhuang, Yonghao and Lin, Zi and Li, Zhuohan
               and Li, Dacheng and Xing, Eric and Zhang, Hao and Gonzalez, Joseph E.
               and Stoica, Ion},
  booktitle = {Advances in Neural Information Processing Systems},
  year      = {2023}
}
```

```bibtex
@misc{mtbench_repro,
  title  = {{MT-Bench} Reproduction},
  author = {kook2},
  year   = {2026},
  url    = {https://github.com/<your-handle>/mt_bench_repro}
}
```

---

<div align="center">
<sub>Infrastructure: A100 SXM4 40 GB · Serving: vLLM v0.6.6 · Judge family: Qwen2.5</sub>
</div>

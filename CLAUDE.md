# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MT-Bench reproduction project implementing the evaluation pipeline from the NeurIPS 2023 paper "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena". The goal is to reproduce model rankings and category-level performance trends (not exact score matching).

## Setup

```bash
pip install -r requirements.txt
export PYTHONPATH=src  # Required for all commands; VS Code terminals set this automatically
```

## Commands

### Run the full pipeline locally (no API keys, using mock mode)

```bash
bash scripts/run_generate_local.sh
bash scripts/run_judge_single_local.sh
bash scripts/run_judge_pairwise_local.sh
bash scripts/run_aggregate_local.sh
```

### CLI subcommands

```bash
# Generate model answers
python -m mtbench_repro.cli generate \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ \
  --model-id vicuna-13b \
  --mock

# Single-answer grading (1-10 scale)
python -m mtbench_repro.cli judge-single \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-id vicuna-13b \
  --mock

# Pairwise comparison (with position-bias swap)
python -m mtbench_repro.cli judge-pairwise \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-a vicuna-13b \
  --model-b llama-13b \
  --mock

# Reference-guided grading (math/reasoning/coding categories)
python -m mtbench_repro.cli judge-reference \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --mode single \
  --model-id vicuna-13b \
  --mock

# Aggregate all results to CSV
python -m mtbench_repro.cli aggregate \
  --judgments-dir data/judgments/ \
  --output-csv data/results.csv
```

### Type checking

```bash
pyright src/
```

### Mock OpenAI server (for testing judge prompts without real API)

```bash
# Terminal 1
python scripts/mock_openai_server.py --port 9999
# Terminal 2
python -m mtbench_repro.cli judge-single --openai-base-url http://localhost:9999/v1 --openai-api-key EMPTY ...
```

## Architecture

Data flows through 5 stages: Questions → Answers → Judgments (3 types) → Aggregation → CSV report.

**Three independent judge pipelines** (corresponding to paper Figures 5-10):
- `judge_single.py` — Grades each answer on 1-10 scale independently (Figure 6)
- `judge_pairwise.py` — Compares two models per question; runs both AB and BA orders to detect position bias, only declares winner if both orderings agree (Figures 5, 9)
- `judge_reference.py` — Like single/pairwise but provides reference answers to the judge; targets math, reasoning, coding categories (Figures 8, 10)

**Key modules:**
- `schemas.py` — Core dataclasses: `MTBenchQuestion`, `ModelAnswer`, `JudgmentSingle`, `JudgmentPairwise`
- `client.py` — Unified `ChatClient` abstraction supporting OpenAI API, vLLM (OpenAI-compatible endpoint), and `--mock` mode
- `prompts.py` — All 6 judge prompt templates from the paper + verdict/score parsing
- `aggregate.py` — Loads judgment JSONL files, computes per-model/per-category stats, compares against paper reference scores
- `io_utils.py` — JSONL streaming I/O with resume tracking (processed question IDs are stored so interrupted runs can continue)
- `cli.py` — Single entry point with 5 subcommands

**Design principles:**
- All data is stored as JSONL (one record per line) for memory-efficient streaming
- Every judge module supports resume: already-processed question IDs are skipped on restart
- `--mock` flag returns deterministic dummy responses for testing without API access
- Always invoke via `python -m mtbench_repro.xxx` (not direct file execution) to respect PYTHONPATH

## Data

- `data/mt_bench_questions_sample.jsonl` — 3 sample questions for local testing
- `data/mt_bench_questions.jsonl` — Full 80-question dataset (must be downloaded separately from FastChat)
- `data/answers/` — One JSONL file per model
- `data/judgments/single_grade/`, `pairwise/`, `single_grade_ref/` — Judge outputs by type

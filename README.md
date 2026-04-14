<div align="center">

# LLM-as-a-Judge 신뢰도 분석: Judge 선택이 모델 랭킹을 바꾸는가?

**NeurIPS 2023 _"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"_ 재현 및 확장**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Paper](https://img.shields.io/badge/논문-NeurIPS%202023-red)](https://arxiv.org/abs/2306.05685)
[![Infra: A100](https://img.shields.io/badge/인프라-A100%2040GB-lightgrey?logo=nvidia)](https://www.nvidia.com/)

</div>

---

## 연구 개요

**"어떤 judge를 쓰느냐에 따라 모델 평가 결과가 달라지는가?"**

LLM-as-a-Judge는 비용과 확장성 측면에서 매력적인 평가 방식이지만, judge 모델의 선택이 평가 결과에 미치는 영향은 체계적으로 분석된 바가 적다. 본 연구는 MT-Bench 프로토콜을 직접 구현하고, Qwen2.5 패밀리(7B/14B/32B)와 GPT-4o-mini를 judge로 사용해 4가지 핵심 질문에 답한다.

| RQ | 질문 | 핵심 발견 |
|----|------|---------|
| **RQ1** | Judge 선택이 모델 랭킹을 얼마나 바꾸는가? | Kendall τ distance 최대 0.190 — 같은 모델도 judge에 따라 1위↔4위 역전 |
| **RQ2** | Judge가 클수록 더 신뢰할 수 있는가? | 불일치율 78.75%→46.85%→32.86% 단조 감소, 단 잔여 불일치는 더 순서 민감 |
| **RQ3** | Turn 2가 구조적으로 더 어려운가? | Reasoning/Math 카테고리에서 Turn 2 점수 유의미하게 하락 |
| **RQ4** | 몇 개 문항으로 안정적인 랭킹이 가능한가? | Top-40 변별도 문항으로 전체 80문항과 동일 랭킹(ρ≥0.96) 유지 |

---

## 핵심 발견 요약

### Judge에 따른 랭킹 역전

동일한 7개 모델을 평가했을 때 judge에 따라 순위가 크게 달라진다:

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B | GPT-4o-mini |
|------|:-------:|:--------:|:--------:|:-----------:|
| Phi-3.5-mini | **1위** | 2위 | 2위 | **1위** |
| Yi-1.5-9B | 2위 | 4위 | 3위 | 3위 |
| **Llama-3.1-8B** | 3위 | **1위** | 4위 | 4위 |
| gemma-2-9b | 4위 | 3위 | **1위** | 2위 |
| Mistral-7B | 5위 | 5위 | 5위 | 5위 |
| SOLAR-10.7B | 6위 | 6위 | 6위 | 6위 |
| Zephyr-7B | 7위 | 7위 | 7위 | 7위 |

Llama-3.1-8B는 Qwen-14B에서 1위(8.17)이지만 Qwen-32B에서 4위(7.71)다. **같은 모델, 같은 답변인데 judge만 달라졌다.**

### Kendall τ Distance 행렬

| | Qwen-7B | Qwen-14B | Qwen-32B | GPT-4o-mini |
|---|:---:|:---:|:---:|:---:|
| **Qwen-7B** | 0.000 | 0.143 | 0.143 | 0.095 |
| **Qwen-14B** | 0.143 | 0.000 | **0.190** | 0.143 |
| **Qwen-32B** | 0.143 | **0.190** | 0.000 | **0.048** |
| **GPT-4o-mini** | 0.095 | 0.143 | **0.048** | 0.000 |

주목할 점:
- **Qwen-32B ↔ GPT-4o-mini**: τ distance = 0.048 (거의 동일) → 충분히 큰 오픈소스 judge는 중립 judge에 수렴한다
- **Qwen-14B ↔ Qwen-32B**: τ distance = 0.190 (같은 패밀리인데 가장 큰 불일치) → judge 크기가 클수록 무조건 일관되지 않음

---

## 실험 설계

### Judge 모델 (4개)

| Judge | Family | 크기 | 데이터 위치 |
|-------|--------|------|------------|
| Qwen2.5-7B-Instruct | Qwen | 7B | `judgments_phase3/judge_7B/` |
| Qwen2.5-14B-Instruct | Qwen | 14B | `judgments_phase3/judge_14B/` |
| Qwen2.5-32B-Instruct | Qwen | 32B | `judgments_phase3/judge_32B/` |
| GPT-4o-mini | GPT | — | `judgments_phase5/judge_gpt4omini/` |

### Eval 모델 (7개)

| 모델 | 계열 |
|------|------|
| Llama-3.1-8B-Instruct | LLaMA |
| gemma-2-9b-it | Google |
| Yi-1.5-9B-Chat | 01.AI |
| Phi-3.5-mini-Instruct | Microsoft |
| Mistral-7B-Instruct-v0.3 | Mistral |
| SOLAR-10.7B-Instruct | Upstage |
| Zephyr-7B-beta | HuggingFace |

---

## 결과 상세

### RQ1: Judge 선택이 랭킹을 바꾼다

<p align="center">
  <img src="figures/fig6_spearman_heatmap.png" width="65%" alt="Judge 간 Spearman ρ">
</p>

**Fig 1. Judge 간 Spearman ρ 히트맵** — Qwen-32B와 GPT-4o-mini의 높은 일치도(ρ=0.964)가 두드러진다.

<p align="center">
  <img src="figures/fig5_phase3_scores.png" width="80%" alt="Judge별 모델 점수">
</p>

**Fig 2. Judge별 모델 점수 비교** — 동일 모델도 judge에 따라 점수 및 순위가 달라진다.

#### 카테고리별 랭킹 불안정성

<p align="center">
  <img src="figures/fig_category_tau.png" width="80%" alt="카테고리별 Kendall τ distance">
</p>

**Fig 3. 카테고리별 Judge 랭킹 불안정도** — Writing(τ=0.191)이 가장 불안정하고 Coding(τ=0.083)이 가장 안정적이다. 주관적 평가 기준이 필요한 카테고리일수록 judge 의존도가 높다.

#### 모델별 Judge 민감도

<p align="center">
  <img src="figures/fig_model_sensitivity.png" width="80%" alt="모델별 Judge 민감도">
</p>

**Fig 4. 모델별 Judge 민감도** — Llama-3.1-8B가 가장 민감(std=0.177, range=0.46)하고 Phi-3.5-mini가 가장 안정적(std=0.042)이다. 모델에 따라 judge 선택의 영향이 크게 다르다.

---

### RQ2: Judge 크기 스케일링

<p align="center">
  <img src="figures/fig4_judge_scaling.png" width="80%" alt="Judge 크기별 불일치율">
</p>

**Fig 5. Judge 크기별 pairwise 불일치율** — 7B(78.75%) → 14B(46.85%) → 32B(32.86%) 단조 감소.

<p align="center">
  <img src="figures/fig14_bootstrap_ci.png" width="75%" alt="Bootstrap 95% CI">
</p>

**Fig 6. Cross-Judge Spearman ρ + Bootstrap 95% CI** — 점 추정만으로는 불충분하다.

#### Reference-guided 채점의 보정 효과

<p align="center">
  <img src="figures/fig_reference_penalty.png" width="90%" alt="Reference-guided 점수 하락">
</p>

**Fig 7. Reference 정답 제공 시 점수 하락** — Judge가 클수록 reference 제공 시 점수 하락이 크다(Qwen-7B: −1.2 → Qwen-32B: −2.7). 정답 기준이 생기면 큰 judge가 더 가혹하게 채점한다.

---

### RQ3: Turn 2 구조적 난이도

<p align="center">
  <img src="figures/fig10_turn_degradation.png" width="80%" alt="Turn 2 성능 저하">
</p>

**Fig 8. Turn 1 → Turn 2 점수 변화(δ)** — Reasoning/Math에서 하락이 크고, 모델/judge별로 패턴이 다르다.

---

### RQ4: tinyMT-Bench

<p align="center">
  <img src="figures/fig8_discriminability.png" width="80%" alt="문항별 변별도">
</p>

**Fig 9. 문항별 변별도(inter-model score std)** — 카테고리별로 변별력 차이가 크다.

<p align="center">
  <img src="figures/fig9_tiny_mt_bench.png" width="80%" alt="tinyMT-Bench">
</p>

**Fig 10. tinyMT-Bench** — 변별도 상위 40문항으로 전체 80문항과 동일한 랭킹 유지(ρ≥0.96).

---

## 실행 방법

### 환경 설정

```bash
cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src
```

### A100 실행 순서

```bash
# 1. Qwen judge 채점 (기존 데이터 없을 때)
bash scripts/run/a100/run_judge_phase3_a100.sh

# 2. 분석 실행
export PYTHONPATH=src
python3 scripts/analysis/analyze_self_judge_bias.py
python3 scripts/analysis/analyze_turn_degradation.py
python3 scripts/analysis/analyze_tiny_mt_bench.py
python3 scripts/analysis/analyze_bootstrap_ci.py
```

### 로컬 Mock 테스트

```bash
bash scripts/run/local/run_mock_full.sh
```

---

## 저장소 구조

```
mt_bench_repro/
├── src/mtbench_repro/
│   ├── schemas.py          ← 데이터 스키마 + 카테고리 상수
│   ├── client.py           ← ChatClient (OpenAI / vLLM / mock)
│   ├── prompts.py          ← judge 프롬프트 (논문 Figure 5~10)
│   ├── judge_single.py     ← 1–10점 채점
│   ├── judge_pairwise.py   ← AB/BA swap 비교
│   ├── judge_reference.py  ← 정답 참고 채점
│   ├── aggregate.py        ← 점수 집계 + 랭킹
│   └── cli.py              ← CLI 진입점
│
├── scripts/
│   ├── analysis/
│   │   ├── analyze_self_judge_bias.py   ← Kendall τ + judge 간 비교
│   │   ├── analyze_turn_degradation.py  ← Turn 2 구조적 난이도
│   │   ├── analyze_tiny_mt_bench.py     ← 최소 변별 문항 세트
│   │   ├── analyze_discriminability.py  ← 문항별 변별도
│   │   └── analyze_bootstrap_ci.py      ← Bootstrap 95% CI
│   └── run/a100/
│       ├── run_judge_llama_a100.sh      ← LLaMA judge (진행 중)
│       ├── run_judge_phase3_a100.sh     ← Qwen judge
│       └── run_generate_phase3_a100.sh  ← eval 답변 생성
│
└── data/
    ├── mt_bench_questions.jsonl
    ├── answers/                     ← eval 모델 답변 (7개)
    ├── judgments_phase3/            ← Qwen judge 결과
    ├── judgments_phase5/            ← GPT-4o-mini judge 결과
    ├── judgments_llama_judge/       ← LLaMA judge 결과 (진행 중)
    └── results_*.csv                ← 집계 산출물
```

---

## 인용

```bibtex
@inproceedings{zheng2023judging,
  title={Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena},
  author={Zheng, Lianmin and others},
  booktitle={NeurIPS},
  year={2023}
}
```

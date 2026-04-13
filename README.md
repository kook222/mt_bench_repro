<div align="center">

# MT-Bench 재현 — Self-Judge Bias 분석

**NeurIPS 2023 논문 _"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"_ 재현 및 확장**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Paper](https://img.shields.io/badge/논문-NeurIPS%202023-red)](https://arxiv.org/abs/2306.05685)
[![Infra: A100](https://img.shields.io/badge/인프라-A100%2040GB-lightgrey?logo=nvidia)](https://www.nvidia.com/)

</div>

---

> **핵심 주장:** LLM-as-a-Judge에서 judge 모델은 자신과 같은 family의 eval 모델을 유리하게 채점한다 (self-judge bias).
> 이 편향은 Kendall τ distance로 정량화되며, 특정 카테고리와 Turn 2에서 더 강하게 나타난다.

## 코드만 볼 때 여기부터

| 먼저 볼 파일 | 역할 |
|-------------|------|
| [scripts/analysis/analyze_self_judge_bias.py](scripts/analysis/analyze_self_judge_bias.py) | **핵심**: LLaMA vs Qwen vs GPT-mini, Kendall τ + Self-judge bias |
| [scripts/run/a100/run_judge_llama_a100.sh](scripts/run/a100/run_judge_llama_a100.sh) | LLaMA family judge 실행 (신규) |
| [scripts/analysis/analyze_turn_degradation.py](scripts/analysis/analyze_turn_degradation.py) | Turn 2 구조적 난이도 + self-judge bias 연결 |
| [scripts/analysis/analyze_tiny_mt_bench.py](scripts/analysis/analyze_tiny_mt_bench.py) | 최소 변별 문항 세트 + bias 집중 위치 |
| [src/mtbench_repro/judge_single.py](src/mtbench_repro/judge_single.py) | single-grade 채점 |
| [src/mtbench_repro/judge_pairwise.py](src/mtbench_repro/judge_pairwise.py) | pairwise 채점 |

---

## 목차

- [실험 설계](#실험-설계)
- [핵심 주장 3가지](#핵심-주장-3가지)
- [실험 단계](#실험-단계)
- [실행 방법](#실행-방법)
- [결과 파일](#결과-파일)
- [저장소 구조](#저장소-구조)

---

## 실험 설계

### Judge 모델

| Judge | Family | 파라미터 | 역할 |
|-------|--------|---------|------|
| LLaMA-3.1-8B-Instruct | LLaMA | 8B | self-judge bias 측정 (소형) |
| LLaMA-3.3-70B-Instruct | LLaMA | 70B AWQ | self-judge bias 측정 (대형) |
| Qwen2.5-7B/14B/32B-Instruct | Qwen | 7B/14B/32B | Phase 3 기존 데이터 |
| GPT-4o-mini | GPT | - | 중립 reference judge |

### Eval 모델 (7개, 공통)

| 모델 | Family | 비고 |
|------|--------|------|
| Llama-3.1-8B-Instruct | **LLaMA** | self-judge bias 핵심 검증 대상 |
| SOLAR-10.7B-Instruct | other | |
| gemma-2-9b-it | other | |
| Yi-1.5-9B-Chat | other | |
| Zephyr-7B-beta | other | |
| Mistral-7B-Instruct-v0.3 | other | |
| Phi-3.5-mini-Instruct | other | |

### 핵심 지표

- **Kendall τ distance** = (1 − τ) / 2 : judge 쌍 간 랭킹 불일치 정도
- **Self-judge bias score** = ref_rank − own_rank : 자기 judge에서 순위 변화 (양수 = 유리)
- **Bootstrap 95% CI** (n=10,000): 문항 단위 리샘플링, 통계적 유의성 보장

---

## 핵심 주장 3가지

### 주장 1: Judge 선택이 랭킹을 바꾼다
LLaMA judge와 Qwen judge가 만들어내는 모델 랭킹은 Kendall τ distance 기준으로
유의미하게 다르다 (Bootstrap 95% CI 포함).

→ `analyze_self_judge_bias.py` Panel B, D

### 주장 2: Self-judge bias는 방향성이 있다
- LLaMA judge: LLaMA eval 모델의 순위 상승
- Qwen judge: Qwen eval 모델의 순위 상승 (Phase 3 기존 데이터에서 관찰)
- GPT-4o-mini: 중립적 기준점

→ `analyze_self_judge_bias.py` Panel C

### 주장 3: Bias는 Turn 2와 특정 카테고리에서 집중된다
Turn 2는 Turn 1보다 구조적으로 어렵고, 이 난이도 차이가 카테고리별로 다르다.
LLaMA eval 모델의 Turn 2 δ가 LLaMA judge에서 덜 하락하는 패턴이 관찰되면
bias가 Turn 2에서 더 강하게 작동한다는 증거가 된다.

→ `analyze_turn_degradation.py`, `analyze_tiny_mt_bench.py`

---

## 실험 단계

### Phase 1 — 파이프라인 검증 (완료)
MT-Bench 재현 기준선 수립.

### Phase 2 — 예비 비교 실험 (완료)
Qwen2.5-14B judge 기준 초기 모델 서열 확인.

### Phase 3 — Qwen Judge Scaling (완료)
Qwen2.5 7B/14B/32B judge로 7개 모델 평가.
데이터: `data/judgments_phase3/`

### Phase 4 — LLaMA Judge (신규, 핵심)
LLaMA-3.1-8B + LLaMA-3.3-70B judge로 동일 7개 모델 평가.
Phase 3 Qwen 결과와 Kendall τ 비교 → self-judge bias 측정.
데이터: `data/judgments_llama_judge/`

### Phase 5 — GPT-4o-mini Judge (완료, 중립 기준)
GPT-4o-mini judge 결과를 self-judge bias 측정의 reference로 사용.
데이터: `data/judgments_phase5/`

### 보조 분석
- Turn 2 구조적 난이도 (`analyze_turn_degradation.py`)
- tinyMT-Bench: 최소 변별 문항 세트 + bias 집중 위치 (`analyze_tiny_mt_bench.py`)

---

## 실행 방법

### 로컬 환경 설정

```bash
cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src
```

### A100: Phase 4 LLaMA Judge 실행 (핵심 신규 실험)

```bash
# Phase 3 answers/ 가 있다면 바로 실행 가능
bash scripts/run/a100/run_judge_llama_a100.sh
```

### 분석 실행 순서

```bash
# 1. 핵심 분석 — self-judge bias + Kendall τ
export PYTHONPATH=src
python3 scripts/analysis/analyze_self_judge_bias.py

# 2. Turn 2 구조적 난이도
python3 scripts/analysis/analyze_turn_degradation.py

# 3. tinyMT-Bench + bias 위치
python3 scripts/analysis/analyze_tiny_mt_bench.py

# 4. 변별도 분석 (tinyMT-Bench 전처리)
python3 scripts/analysis/analyze_discriminability.py

# 5. Phase 3 스케일링 요약 (Qwen judge 기존 결과)
python3 scripts/analysis/analyze_phase3.py
```

### Mock 테스트 (API 없이 로컬 검증)

```bash
bash scripts/run/local/run_mock_full.sh
```

---

## 결과 파일

| 파일 | 내용 |
|------|------|
| `data/results_self_judge_bias.csv` | judge별 랭킹 + self-judge bias score |
| `data/results_kendall_tau_matrix.csv` | judge 쌍별 Kendall τ + Bootstrap CI |
| `data/results_turn_degradation.csv` | 모델×카테고리별 Turn 2 δ |
| `data/results_tiny_mt_bench.csv` | N별 Random/TopDisc Spearman ρ 비교 |
| `data/results_discriminability.csv` | 문항별 변별도(std) |
| `figures/fig_self_judge_bias.png` | **메인 figure**: 4-panel self-judge bias |
| `figures/fig10_turn_degradation.png` | Turn 2 구조적 난이도 |
| `figures/fig9_tiny_mt_bench.png` | tinyMT-Bench + bias 위치 |

---

## 저장소 구조

```
mt_bench_repro/
├── src/mtbench_repro/          ← 핵심 Python 패키지
│   ├── schemas.py              ← 데이터 스키마 + 카테고리 상수
│   ├── client.py               ← ChatClient (OpenAI / vLLM / mock)
│   ├── prompts.py              ← judge 프롬프트 6종
│   ├── judge_single.py         ← 1–10점 단순 채점
│   ├── judge_pairwise.py       ← AB/BA swap 비교
│   ├── judge_reference.py      ← 정답 참고 채점
│   ├── aggregate.py            ← 점수 집계 + 랭킹
│   ├── io_utils.py             ← JSONL I/O + resume
│   └── cli.py                  ← 5개 서브커맨드 CLI
│
├── scripts/
│   ├── analysis/
│   │   ├── analyze_self_judge_bias.py      ← 핵심 (신규)
│   │   ├── analyze_turn_degradation.py     ← Turn 2 난이도
│   │   ├── analyze_tiny_mt_bench.py        ← 최소 문항 세트
│   │   ├── analyze_discriminability.py     ← 변별도
│   │   ├── analyze_bootstrap_ci.py         ← Bootstrap CI
│   │   ├── analyze_phase3.py               ← Qwen judge scaling
│   │   ├── analyze_phase345.py             ← judge 통합 비교
│   │   └── _deprecated/                    ← 제거된 분석 (앙상블 등)
│   └── run/
│       ├── a100/
│       │   ├── run_judge_llama_a100.sh     ← LLaMA judge (신규, 핵심)
│       │   ├── run_judge_phase3_a100.sh    ← Qwen judge
│       │   └── run_generate_phase3_a100.sh ← 답변 생성
│       └── local/
│           └── run_mock_full.sh
│
└── data/
    ├── mt_bench_questions.jsonl
    ├── answers/                            ← eval 모델 답변 (git 제외)
    ├── judgments_phase3/                   ← Qwen judge 결과
    ├── judgments_llama_judge/              ← LLaMA judge 결과 (신규)
    ├── judgments_phase5/                   ← GPT-4o-mini judge 결과
    └── results_*.csv                       ← 집계 산출물
```

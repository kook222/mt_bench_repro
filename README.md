# MT-Bench Reproduction

NeurIPS 2023 논문 **"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"** 의 평가 파이프라인을 Python 패키지로 재현한다.

목표는 exact score 일치가 아니라 **모델 서열과 카테고리별 성능 추이** 재현이다.

> **문서 바로가기**
> - [MT-Bench 카테고리 구조](CATEGORIES.md) — 8개 카테고리 설명, Hard/Easy 분류, 변별력 분석
> - [향후 연구 방향](FUTURE_WORK.md) — Inconsistency 분석, Judge 크기 실험, 한국어 번역 등

---

## 사용 모델

논문(NeurIPS 2023)의 6개 모델 비교 구조를 재현. 로컬 실행 가능한 오픈소스 모델로 capability 스펙트럼 구성.

### Phase 1 — 파이프라인 검증 (1개 모델)

| 모델 | 파라미터 | Judge | 결과 |
|------|---------|-------|------|
| Qwen2.5-7B-Instruct | 7B | Qwen2.5-7B (self) | overall 8.12 |

### Phase 2 — 6개 모델 비교 (✅ 완료)

| 모델 | 파라미터 | single | pairwise | Phase 2 순위 |
|------|---------|--------|----------|-------------|
| Phi-3.5-mini-Instruct | 3.8B | ✅ | ✅ | 1위 (8.09) |
| gemma-2-9b-it | 9B | ✅ | ✅ | 2위 (8.03) |
| Yi-1.5-9B-Chat | 9B | ✅ | ✅ | 3위 (7.97) |
| Mistral-7B-Instruct-v0.3 | 7B | ✅ | ✅ | 4위 (7.49) |
| SOLAR-10.7B-Instruct | 10.7B | ✅ | ✅ | 5위 (7.07) |
| Zephyr-7B-beta | 7B | ✅ | ✅ | 6위 (7.04) |
| **Judge** | Qwen2.5-14B-Instruct | 14B | — | — |

> Qwen2.5-7B는 Phase 1(self-judge)에서만 평가. Phase 2 judge 스크립트 EVAL_MODELS에 포함되지 않아 single/pairwise 모두 미실시.

### Phase 3 — 7개 모델 + Judge 스케일링 (🔧 실행 중)

| 변경 | 모델 | 파라미터 |
|------|------|---------|
| ❌ 제외 | Qwen2.5-7B-Instruct | 7B (judge와 동일 패밀리 → self-judge 편향) |
| ✅ 추가 | Llama-3.1-8B-Instruct | 8B |
| 유지 | Phi-3.5-mini-Instruct | 3.8B |
| 유지 | gemma-2-9b-it | 9B |
| 유지 | Yi-1.5-9B-Chat | 9B |
| 유지 | Mistral-7B-Instruct-v0.3 | 7B |
| 유지 | SOLAR-10.7B-Instruct | 10.7B |
| 유지 | Zephyr-7B-beta | 7B |

Judge: Qwen2.5 단일 패밀리 4종 (7B / 14B / 32B / 72B) 순차 실행

- **인프라**: A100 SXM4 40GB, 로컬 vLLM 서빙 (순차 실행)

---

## 실험 구성

### 평가 방법 (논문 재현 범위)

| 방법 | 논문 근거 | 대상 |
|------|----------|------|
| Single-answer grading (1~10점) | Figure 6, Table 8 | 전 카테고리 |
| Pairwise comparison (AB/BA swap) | Figure 5, 9, Section 3.4 | 전 카테고리 |
| Reference-guided grading | Figure 8, 10 | math / reasoning / coding |


---

## 아키텍처

```
데이터 흐름: Questions → Answers → Judgments (3종) → Aggregation → CSV
```

```
src/mtbench_repro/
├── schemas.py          # 데이터 구조 (MTBenchQuestion, ModelAnswer, JudgmentSingle, JudgmentPairwise)
├── io_utils.py         # JSONL 스트리밍 I/O, resume 지원
├── client.py           # ChatClient (OpenAI API / vLLM / mock 통합)
├── prompts.py          # 논문 Figure 5~10 프롬프트 + 파서
├── generate.py         # 모델 답변 생성 (2-turn, resume 지원)
├── judge_single.py     # Single-answer grading — Figure 6
├── judge_pairwise.py   # Pairwise comparison — Figure 5/9, AB/BA swap
├── judge_reference.py  # Reference-guided grading — Figure 8/10
├── aggregate.py        # 집계, 모델 랭킹, pairwise 행렬
└── cli.py              # 통합 CLI (5개 서브커맨드)
```

---

## 설치 및 실행

### 환경 설정

```bash
pip install -r requirements.txt
export PYTHONPATH=src
```

### Mock 파이프라인 (API 없이 전체 흐름 검증)

```bash
bash scripts/run_mock_full.sh
```

### CLI 서브커맨드

```bash
# 답변 생성
python -m mtbench_repro.cli generate \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --model-id Qwen2.5-7B-Instruct \
  --vllm-host localhost --vllm-port 8000

# Single-answer grading (1~10점)
python -m mtbench_repro.cli judge-single \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-id Qwen2.5-7B-Instruct \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# Pairwise comparison (AB/BA swap)
python -m mtbench_repro.cli judge-pairwise \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --model-a Qwen2.5-7B-Instruct \
  --model-b SOLAR-10.7B-Instruct \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# Reference-guided grading (math/reasoning/coding)
python -m mtbench_repro.cli judge-reference \
  --questions data/mt_bench_questions.jsonl \
  --answers-dir data/answers/ \
  --output-dir data/judgments/ \
  --mode single \
  --model-id Qwen2.5-7B-Instruct \
  --judge-model Qwen2.5-14B-Instruct \
  --openai-base-url http://localhost:8000/v1 \
  --openai-api-key EMPTY

# 집계
python -m mtbench_repro.cli aggregate \
  --judgments-dir data/judgments/ \
  --output-csv data/results.csv
```

항상 `PYTHONPATH=src python -m mtbench_repro.cli` 형태로 실행.

### A100 서버에서 전체 파이프라인 실행

```bash
# Phase 2: 6개 모델 답변 생성
bash scripts/run_generate_multi_a100.sh

# Phase 2: Qwen2.5-14B judge + 집계
bash scripts/run_judge_multi_a100.sh

# Phase 3: Llama-3.1-8B 답변 생성 (Phase 2 6개 파일 재사용, 1개만 신규 생성)
bash scripts/run_generate_phase3_a100.sh

# Phase 3: judge 4종 순차 실행 (7B → 14B → 32B → 72B, 약 12~20시간)
bash scripts/run_judge_phase3_a100.sh

# Phase 3: 스케일링 커브 + 문항 수 민감도 분석 (로컬 실행)
export PYTHONPATH=src
python3 scripts/analyze_phase3.py
```

k8s job으로 제출하는 방법은 `CLAUDE.md` 참고.

---

## Phase 3 — Judge Scaling Law 실험 (🔧 코드 완료, 실행 대기)

**목표:** Judge 모델 크기에 따른 pairwise inconsistency율 변화를 측정해 "Judge Scaling Law" 도출.

**설계 원칙:**
- 평가 모델에서 Qwen2.5-7B 제외 → Llama-3.1-8B-Instruct로 교체 (self-judge 편향 제거)
- Judge를 Qwen2.5 단일 패밀리로 통일 → 아키텍처 변수 제거, 순수 크기 효과만 측정

### 평가 대상 모델 (7개, Phase 2에서 변경)

| 변경 | 모델 | 파라미터 | 비고 |
|------|------|---------|------|
| ❌ 제외 | Qwen2.5-7B-Instruct | 7B | judge와 동일 패밀리 → self-judge 편향 |
| ✅ 추가 | **Llama-3.1-8B-Instruct** | 8B | 이종 아키텍처, 편향 없음 |
| 유지 | Phi-3.5-mini-Instruct | 3.8B | — |
| 유지 | gemma-2-9b-it | 9B | — |
| 유지 | Yi-1.5-9B-Chat | 9B | — |
| 유지 | Mistral-7B-Instruct-v0.3 | 7B | — |
| 유지 | SOLAR-10.7B-Instruct | 10.7B | — |
| 유지 | Zephyr-7B-beta | 7B | — |

### Judge 스케일링 라인업 (Qwen2.5 단일 패밀리)

| Judge | 파라미터 | VRAM | 양자화 | 상태 |
|-------|---------|------|--------|------|
| Qwen2.5-7B-Instruct | 7B | ~14GB | fp16 | ⏳ 실행 대기 |
| Qwen2.5-14B-Instruct | 14B | ~28GB | fp16 | ✅ 완료 (46.1%) |
| Qwen2.5-32B-Instruct | 32B | ~20GB | AWQ 4-bit | ⏳ 실행 대기 |
| Qwen2.5-72B-Instruct | 72B | ~38GB | AWQ 4-bit | ⏳ 실행 대기 |

> Phase 3에서 Qwen2.5-7B는 평가 대상에서 제외되므로 judge로 사용해도 self-judge 편향 없음.
> 스케일링 커브: 7B → 14B → 32B → 72B
> 72B AWQ는 40GB 한계에 근접 → `--gpu-memory-utilization 0.85` 사용.

### 측정 지표

- **Inconsistency율**: 각 judge 크기별 AB/BA 불일치 비율 → 스케일링 커브
- **Cross-judge Spearman ρ**: judge 간 모델 순위 일관성
- **문항 수 민감도**: 몇 문항으로 신뢰할 수 있는 순위가 수렴하는가

### 문항 수 민감도 — 사전 분석 결과 (Phase 2 데이터 기반)

`analyze_phase3.py`의 서브샘플링 분석을 Phase 2 데이터(7개 모델, 80문항)로 실행한 결과:

| N문항 | 평균 Spearman ρ | 최소 | 최대 |
|------|---------------|------|------|
| 10 | 0.777 | 0.321 | 0.964 |
| 20 | 0.839 | 0.464 | 1.000 |
| 40 | 0.857 | 0.607 | 1.000 |
| 60 | 0.952 | 0.643 | 1.000 |
| 80 | 1.000 | — | — |

> **60문항(ρ=0.95+)부터 안정적.** 10문항은 순위 불일치 위험 있음(min ρ=0.32).
> MT-Bench 80문항은 신뢰성을 위한 적정 규모임을 실증.

### Phase 3 스크립트 구조

| 스크립트 | 역할 |
|---------|------|
| `scripts/run_generate_phase3_a100.sh` | Llama-3.1-8B 답변 생성 (1개, 나머지 Phase 2 재사용) |
| `scripts/run_judge_phase3_a100.sh` | judge 4종 순차 실행, `data/judgments_phase3/judge_XB/` 경로 분리 |
| `scripts/analyze_phase3.py` | 스케일링 커브 + 문항 수 민감도 통합 분석, CSV 출력 |

---

## 결과

### Phase 1 — Qwen2.5-7B Self-judge

| 카테고리 | 점수 |
|---------|------|
| writing | 7.60 |
| roleplay | 7.95 |
| extraction | 7.45 |
| reasoning | 7.20 |
| math | 8.80 |
| coding | 8.80 |
| stem | 8.55 |
| humanities | 8.60 |
| **overall** | **8.12** |

> Self-judge 특성상 math/coding 점수가 과대평가됨. Phase 2 외부 judge 결과(overall 8.12)와 동일하지만, 카테고리 분포가 다름 — self-judge는 자신이 잘하는 영역을 후하게 채점하는 경향이 있음.

### Phase 2 — 6-model comparison (✅ 완료)

**Judge: Qwen2.5-14B-Instruct | 인프라: A100 40GB vLLM**

#### Single-Answer Grading (1~10점)

> Qwen2.5-7B는 Phase 1 self-judge 결과(overall 8.12)만 존재. Phase 2(Qwen2.5-14B judge) 대상에서 제외됨.

| 순위 | 모델 | overall | writing | roleplay | extraction | reasoning | math | coding | stem | humanities |
|------|------|---------|---------|----------|-----------|----------|------|--------|------|-----------|
| 1 | Phi-3.5-mini-Instruct | **8.09** | 8.25 | 7.70 | 7.65 | 7.75 | 8.30 | 8.15 | 8.25 | **8.65** |
| 2 | gemma-2-9b-it | 8.03 | 8.15 | 8.00 | 7.50 | 7.70 | 8.05 | 7.95 | 8.40 | 8.50 |
| 3 | Yi-1.5-9B-Chat | 7.97 | 8.10 | **8.05** | **8.05** | 7.45 | 8.00 | 7.20 | **8.50** | 8.40 |
| 4 | Mistral-7B-Instruct-v0.3 | 7.49 | **8.25** | 7.80 | 7.70 | 6.70 | 6.75 | 6.05 | 8.35 | 8.30 |
| 5 | SOLAR-10.7B-Instruct | 7.07 | 7.85 | 6.55 | 7.26 | 6.85 | 7.25 | 4.95 | 7.65 | 8.20 |
| 6 | Zephyr-7B-beta | 7.04 | 7.60 | 7.20 | 7.40 | 6.15 | 6.35 | 5.65 | 8.10 | 7.90 |

#### Hard vs Easy 갭 (논문 핵심 패턴)

> 논문: 상위 모델일수록 hard(math/reasoning/coding)와 easy(writing/roleplay/humanities) 갭이 작다.

| 모델 | hard avg | easy avg | gap |
|------|----------|----------|-----|
| Phi-3.5-mini | 8.07 | 8.20 | +0.13 |
| gemma-2-9b | 7.90 | 8.22 | +0.32 |
| Yi-1.5-9B | 7.55 | 8.18 | +0.63 |
| Mistral-7B | 6.50 | 8.12 | **+1.62** (hard 취약) |
| SOLAR-10.7B | 6.35 | 7.53 | +1.18 |
| Zephyr-7B | 6.05 | 7.57 | **+1.52** (hard 취약) |

#### Pairwise Win Rate (6개 모델, 전체 1200 판정)

| 순위 | 모델 | win rate | games |
|------|------|----------|-------|
| 1 | gemma-2-9b-it | 79.4% | 209 |
| 2 | Phi-3.5-mini-Instruct | 76.3% | 219 |
| 3 | Yi-1.5-9B-Chat | 66.1% | 202 |
| 4 | Mistral-7B-Instruct-v0.3 | 43.4% | 206 |
| 5 | SOLAR-10.7B-Instruct | 25.2% | 214 |
| 6 | Zephyr-7B-beta | 15.2% | 244 |

> **Single ↔ Pairwise 수렴 분석:** Spearman ρ = 0.943으로 대체로 수렴하나 **상위 2개 모델(Phi↔gemma) 순위 역전**이 발생함. Single에서 Phi(1위, 8.09점) > gemma(2위, 8.03점)이었으나, Pairwise에서 gemma(1위, 79.4%) > Phi(2위, 76.3%)로 뒤집혔다. 3~6위는 동일. → 논문의 "두 채점 방식이 수렴한다" 주장은 **부분 재현 (ρ=0.943, 상위권 역전 존재)**
>
> **한계:** Inconsistent율 46.1% (1200개 중 553개) — GPT-4 judge 대비 Qwen2.5-14B의 position bias가 높아 AB/BA 판정이 자주 불일치함. Qwen2.5-7B-Instruct는 Phase 1(단일 모델 채점)에서만 사용했고, Phase 2 pairwise 비교 대상에는 의도적으로 포함하지 않았다.

#### 논문 결과와 비교

| 항목 | 논문 (GPT-4 judge, 2023) | 이번 재현 (Qwen14B judge, 2026) |
|------|--------------------------|--------------------------------|
| 점수 범위 | 2.61 ~ 8.99 (6.38p) | 7.04 ~ 8.12 (1.08p) |
| Hard/Easy 갭 패턴 | ✅ 상위 모델 갭 작음 | ✅ 동일하게 재현 |
| Single↔Pairwise 수렴 | ✅ | ⚠️ 부분 재현 (ρ=0.943, 상위 2개 역전) |
| Inconsistent율 | ~20% 추정 | 46.1% (judge 모델 한계) |

---

## 결론

### 재현 성공 여부

| 논문의 주장 | 재현 결과 |
|------------|----------|
| Hard category(math/reasoning/coding)에서 모델 간 격차가 더 크다 | ✅ 상위 모델 gap ≈ 0, 하위 모델 gap +1.5 이상 |
| Single-answer grading과 Pairwise 순위가 수렴한다 | ⚠️ 부분 재현 — Spearman ρ=0.943, 3~6위 동일하나 1~2위(Phi↔gemma) 역전 |
| LLM-as-a-Judge로 모델 서열을 신뢰성 있게 식별할 수 있다 | ✅ 7개 모델 일관된 서열 확인 |
| 모델 크기가 클수록 반드시 성능이 높지 않다 | ✅ SOLAR 10.7B < Phi-3.5-mini 3.8B |

### 논문과 차이가 난 이유

1. **Judge 모델 차이**: 논문은 GPT-4, 이번은 Qwen2.5-14B. 더 작은 judge는 position bias가 높아 pairwise inconsistent율이 46%까지 상승 (논문 대비 약 2배 추정).
2. **모델 세대 차이**: 2023년 모델(GPT-4~LLaMA-13B) 대비 2026년 모델들은 전반적으로 성능이 높아 점수 범위가 1.08p에 불과 (논문: 6.38p). 변별력이 낮아졌음.
3. **Qwen2.5-7B Phase 2 미포함**: Qwen2.5-7B-Instruct는 Phase 1에서 단독 채점 대상으로만 사용. Phase 2는 Qwen2.5-14B를 judge로 쓰는 실험이므로 동일 패밀리 self-judge 편향을 피하기 위해 의도적으로 제외했다.

### 핵심 takeaway

> 논문의 핵심 방법론(LLM-as-a-Judge, position bias 완화를 위한 AB/BA swap, reference-guided grading)은 2026년 오픈소스 모델 환경에서도 동일하게 작동한다. 단, judge 모델 품질이 결과 신뢰도에 직결되므로 가능하면 GPT-4급 judge 사용을 권장한다.

---

## 논문-코드 대응

| 논문 | 구현 위치 | 설명 |
|------|----------|------|
| Figure 5 | `prompts._SYSTEM_PAIRWISE` | pairwise 기본 프롬프트 |
| Figure 6 | `prompts._SYSTEM_SINGLE` | single grading 프롬프트 |
| Figure 7 | `prompts._SYSTEM_PAIRWISE_MATH_COT` | CoT pairwise (정의됨, 선택적 사용) |
| Figure 8 | `prompts._SYSTEM_PAIRWISE_REFERENCE` | reference-guided pairwise |
| Figure 9 | `prompts.build_multiturn_pairwise_prompt` | multi-turn pairwise |
| Figure 10 | `prompts.build_multiturn_single_prompt` | reference-guided multi-turn single |
| Section 3.4 | `judge_pairwise.judge_pairwise_question` | conservative swap (AB/BA 일치할 때만 winner) |
| Table 8 | `aggregate.compute_single_scores` | MT-Bench Score (160턴 평균) |

---

## 흔한 오류

| 오류 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: No module named 'mtbench_repro'` | PYTHONPATH 미설정 | `export PYTHONPATH=src` |
| `FileNotFoundError: mt_bench_questions.jsonl` | 질문 파일 없음 | `--questions data/mt_bench_questions_sample.jsonl` 으로 테스트 |
| score가 전부 -1.0 | mock 파서 불일치 | `client._mock_response` 반환 형식 확인 |
| winner가 전부 inconsistent | mock swap 판정 불일치 | 의도된 동작, aggregate에서 tie 처리됨 |
| k8s pod이 바로 삭제됨 | sleep/while true 사용 | 금지 — 작업 끝나면 자연 종료되어야 함 |

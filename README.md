# MT-Bench Reproduction

NeurIPS 2023 논문 **"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"** 의 평가 파이프라인을 Python 패키지로 재현한다.

목표는 exact score 일치가 아니라 **모델 서열과 카테고리별 성능 추이** 재현이다.

---

## 사용 모델

논문(NeurIPS 2023)의 6개 모델 비교 구조를 재현. 로컬 실행 가능한 오픈소스 모델로 capability 스펙트럼 구성.

| 구분 | 모델 | 파라미터 | 논문 내 위치 유사 |
|------|------|---------|----------------|
| 평가 대상 | Qwen2.5-7B-Instruct | 7B | 상위권 |
| 평가 대상 | SOLAR-10.7B-Instruct | 10.7B | 상위권 |
| 평가 대상 | Mistral-7B-Instruct-v0.3 | 7B | 중위권 |
| 평가 대상 | Zephyr-7B-beta | 7B | 중위권 |
| 평가 대상 | Yi-1.5-9B-Chat | 9B | 중위권 |
| 평가 대상 | Phi-3.5-mini-Instruct | 3.8B | 하위권 |
| Judge | Qwen2.5-14B-Instruct | 14B | 외부 judge |

- **Phase 1**: Qwen2.5-7B만 사용, self-judge (완료)
- **Phase 2**: 6개 모델 비교, Qwen2.5-14B 외부 judge
- **인프라**: A100 32GB × 4, 로컬 vLLM 서빙 (순차 실행)

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
# Phase 2: 3개 모델 답변 생성
bash scripts/run_generate_multi_a100.sh

# Phase 2: Qwen2.5-14B judge + 집계
bash scripts/run_judge_multi_a100.sh
```

k8s job으로 제출하는 방법은 `CLAUDE.md` 참고.

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

> Self-judge 특성상 math/coding 점수가 과대평가됨. Phase 2 (외부 judge) 결과와 비교 예정.

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

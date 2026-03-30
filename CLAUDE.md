# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

NeurIPS 2023 논문 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" 재현 프로젝트.
목표: 모델 랭킹 순서 및 카테고리별 성능 추이 재현 (정확한 점수 일치 아님).

---

## 로컬 개발 환경

```bash
pip install -r requirements.txt
export PYTHONPATH=src
```

### Mock 전체 파이프라인 (로컬 검증용)
```bash
bash scripts/run_mock_full.sh
```

### CLI 서브커맨드
```bash
# 답변 생성
python -m mtbench_repro.cli generate --questions data/mt_bench_questions_sample.jsonl --answers-dir data/answers/ --model-id vicuna-13b --mock

# 단순 채점 (1-10점)
python -m mtbench_repro.cli judge-single --questions data/mt_bench_questions_sample.jsonl --answers-dir data/answers/ --output-dir data/judgments/ --model-id vicuna-13b --mock

# 모델 비교 (AB/BA swap)
python -m mtbench_repro.cli judge-pairwise --questions data/mt_bench_questions_sample.jsonl --answers-dir data/answers/ --output-dir data/judgments/ --model-a vicuna-13b --model-b llama-13b --mock

# 정답 기반 채점 (math/reasoning/coding)
python -m mtbench_repro.cli judge-reference --questions data/mt_bench_questions_sample.jsonl --answers-dir data/answers/ --output-dir data/judgments/ --mode single --model-id vicuna-13b --mock

# 집계
python -m mtbench_repro.cli aggregate --judgments-dir data/judgments/ --output-csv data/results.csv
```

항상 `PYTHONPATH=src python -m mtbench_repro.cli` 형태로 실행. `python src/mtbench_repro/cli.py` 형태는 import 오류 발생.

---

## 아키텍처

데이터 흐름: Questions → Answers → Judgments (3종) → Aggregation → CSV

**judge 3종:**
- `judge_single.py` — 1~10점 단순 채점 (Figure 6)
- `judge_pairwise.py` — 두 모델 비교, AB/BA 둘 다 실행해서 일치할 때만 승자 선정 (Figure 5, 9)
- `judge_reference.py` — 정답 참고 채점, math/reasoning/coding만 대상 (Figure 8, 10)

**핵심 모듈:**
- `schemas.py` — 데이터클래스 (MTBenchQuestion, ModelAnswer, JudgmentSingle, JudgmentPairwise)
- `client.py` — ChatClient (OpenAI API / vLLM / mock 통합)
- `prompts.py` — 논문의 judge 프롬프트 6종 + 점수 파싱
- `aggregate.py` — 집계, 모델 랭킹, pairwise 행렬, hard/easy gap
- `io_utils.py` — JSONL 스트리밍 I/O, resume 지원
- `cli.py` — 5개 서브커맨드 통합 진입점

### 논문-코드 대응

| 논문 근거 | 구현 위치 | 설명 |
|---|---|---|
| Figure 5 | `prompts._SYSTEM_PAIRWISE` | pairwise 기본 프롬프트 |
| Figure 6 | `prompts._SYSTEM_SINGLE` | single grading 프롬프트 |
| Figure 7 | `prompts._SYSTEM_PAIRWISE_MATH_COT` | CoT pairwise |
| Figure 8 | `prompts._SYSTEM_PAIRWISE_REFERENCE` | reference-guided pairwise |
| Figure 9 | `prompts.build_multiturn_pairwise_prompt` | multi-turn pairwise |
| Figure 10 | `prompts.build_multiturn_single_prompt` | reference-guided multi-turn single |
| Section 3.4 conservative swap | `judge_pairwise.judge_pairwise_question` | AB/BA 두 번 호출 후 일치할 때만 winner |
| Table 8 MT-Bench Score | `aggregate.compute_single_scores` | 160턴 평균 |

---

## 핵심 설계 결정 (수정 시 반드시 읽을 것)

1. **JSONL append 방식**: judge 도중 API 실패해도 완료된 결과를 보존하기 위해 `append_jsonl`로 한 건씩 저장한다. `write_jsonl` 전체 덮어쓰기를 쓰면 안 된다.

2. **resume 기반 skip**: `get_processed_ids(output_path)`로 이미 처리된 `question_id`를 읽어 skip한다. `--no-resume` 플래그로 비활성화 가능.

3. **conservative verdict**: pairwise에서 AB 순서와 BA 순서 판정이 다르면 `"inconsistent"`로 저장하고 집계에서 tie로 처리한다.

4. **파싱 실패 = -1.0**: single score 파싱 실패 시 NaN 대신 `-1.0`을 저장한다. `avg_score` property에서 명시적으로 체크해 집계에서 제외한다.

5. **temperature 분리**: 생성은 `0.7`, judge는 `0.0` (greedy). 혼용하면 안 된다.

6. **카테고리 상수**: `MT_BENCH_CATEGORIES`와 `REFERENCE_GUIDED_CATEGORIES`는 `schemas.py`에 정의되어 있다. 하드코딩하지 말고 항상 import해서 쓴다.

### Import 규칙

```python
# 항상 절대 경로
from mtbench_repro.schemas import MTBenchQuestion
from mtbench_repro.io_utils import load_questions, append_jsonl
from mtbench_repro.client import ChatClient
from mtbench_repro.prompts import build_single_prompt, parse_single_score

# 금지 — 로컬 import (ModuleNotFoundError 발생)
from schemas import MTBenchQuestion      # NG
import schemas                           # NG
```

---

## 흔한 오류

| 오류 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'mtbench_repro'` | PYTHONPATH 미설정 | `export PYTHONPATH=src` |
| `FileNotFoundError: mt_bench_questions.jsonl` | 질문 파일 없음 | `--questions data/mt_bench_questions_sample.jsonl` 으로 테스트 |
| score가 전부 -1.0 | mock 파서 불일치 | `client._mock_response` 반환 형식 확인 |
| winner가 전부 inconsistent | mock swap 판정 불일치 | 의도된 동작, aggregate에서 tie 처리됨 |
| k8s pod이 바로 삭제됨 | sleep/while true 사용 | 금지 — 작업 끝나면 자연 종료되어야 함 |

---

## 서버 환경 (A100 Kubernetes)

| 항목 | 값 |
|------|-----|
| k8s 이미지 | vllm/vllm-openai:v0.6.6 |
| 프로젝트 경로 | `$HOME/MT_BENCH_REPRO` |
| 모델 경로 | `$HOME/models/` |

**k8s 규정 주의:**
- sleep/while true 금지
- pod 완료/에러 후 반드시 `kubectl delete pod <이름>`
- 동시에 여러 pod 실행 자제 (공유 자원)

### Phase 3 코드 구조 및 대응

Phase 3는 기존 코드를 수정하지 않고 **스크립트 3개만 추가**해 구현했다.
기존 CLI(`judge-single`, `judge-pairwise`, `judge-reference`, `aggregate`)를 그대로 재사용.

| 파일 | 역할 | 핵심 설계 |
|------|------|---------|
| `scripts/run_generate_phase3_a100.sh` | Llama-3.1-8B-Instruct 답변 생성 (1개) | 나머지 6개 모델은 Phase 2 파일 재사용, 새 모델만 vLLM 올려서 generate |
| `scripts/run_judge_phase3_a100.sh` | judge 4종 순차 실행 | judge마다 vLLM 시작→전 모델 judge→종료 반복; 32B/72B는 `--quantization awq`; 출력 경로를 `data/judgments_phase3/judge_7B/` 등으로 분리 |
| `scripts/analyze_phase3.py` | 스케일링 커브 + 문항 수 민감도 통합 분석 | 기존 `aggregate.py` 함수 재사용; 새로 추가한 것은 `compute_inconsistency_rate()`, `spearman_rho()`, `run_qsize_analysis()` 3개 함수 |

**Phase 3 신규 함수 대응:**

| 함수 | 위치 | 설명 |
|------|------|------|
| `compute_inconsistency_rate(judgments_dir)` | `analyze_phase3.py` | pairwise/*.jsonl에서 winner=="inconsistent" 비율 계산 |
| `spearman_rho(scores_a, scores_b)` | `analyze_phase3.py` | 두 모델 점수 dict의 Spearman ρ (scipy 불필요, 직접 구현) |
| `compute_overall_scores(judgments_dir)` | `analyze_phase3.py` | single_grade/*.jsonl에서 모델별 overall score 계산 |
| `load_per_question_scores(judgments_dir, min_questions=60)` | `analyze_phase3.py` | 문항별 점수 로드; 60문항 미만(mock/sample) 자동 제외 |
| `run_scaling_analysis(phase3_dir, output_csv)` | `analyze_phase3.py` | judge 4종 비교: inconsistency율 테이블 + cross-judge Spearman ρ 행렬 |
| `run_qsize_analysis(phase2_dir, output_csv, sizes, n_trials)` | `analyze_phase3.py` | Phase 2 데이터 서브샘플링 → N문항 Spearman ρ 곡선 (추가 실험 불필요) |

**데이터 경로 구조:**
```
data/
├── answers/                         # Phase 2 + Llama-3.1-8B (Phase 3 신규)
├── judgments_phase3/
│   ├── judge_7B/  single_grade/ pairwise/ single_grade_ref/
│   ├── judge_14B/ ...
│   ├── judge_32B/ ...
│   └── judge_72B/ ...
├── results_phase3_judge_7B.csv      # judge별 집계
├── results_phase3_judge_14B.csv
├── results_phase3_judge_32B.csv
├── results_phase3_judge_72B.csv
├── results_phase3_scaling.csv       # 스케일링 커브 (inconsistency율 × judge 크기)
└── results_phase3_qsize.csv         # 문항 수 민감도 (Spearman ρ × N문항)
```

**Phase 3 실행 순서:**
```bash
cd $HOME
# Step 1: Llama 답변 생성
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "<pod-gen-p3>" \
  -c "cd $HOME && bash MT_BENCH_REPRO/scripts/run_generate_phase3_a100.sh > /tmp/run_gen_p3.out 2>&1"
kubectl logs -f <pod-gen-p3>
kubectl delete pod <pod-gen-p3>

# Step 2: judge 4종 순차 실행 (약 12~20시간)
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "<pod-judge-p3>" \
  -c "cd $HOME && bash MT_BENCH_REPRO/scripts/run_judge_phase3_a100.sh > /tmp/run_judge_p3.out 2>&1"
kubectl logs -f <pod-judge-p3>
kubectl delete pod <pod-judge-p3>

# Step 3: 분석 (로컬 또는 서버)
export PYTHONPATH=src
python3 scripts/analyze_phase3.py
```

---

### ✅ Phase 2 완료 (2026-03-30)

답변 생성 + judge (single / pairwise / reference) + 집계 전 완료.
결과: `data/results_multi.csv` 및 README.md 참고.

---

### Phase 2 실행 순서 (전체)

```bash
# 서버 접속 후 최신 코드 pull
cd $HOME/MT_BENCH_REPRO && git pull origin main

# 모델 다운로드 (없는 경우)
export PATH="$HOME/.local/bin:$PATH"
hf download upstage/SOLAR-10.7B-Instruct-v1.0 --local-dir $HOME/models/SOLAR-10.7B-Instruct
hf download mistralai/Mistral-7B-Instruct-v0.3 --local-dir $HOME/models/Mistral-7B-Instruct-v0.3
hf download Qwen/Qwen2.5-14B-Instruct --local-dir $HOME/models/Qwen2.5-14B-Instruct

# 6개 모델 답변 생성 job 제출 (출력은 /tmp 에 써야 함 — pod 내 $HOME 쓰기 권한 없음)
cd $HOME
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "<pod-name-gen>" \
  -c "cd $HOME && bash MT_BENCH_REPRO/scripts/run_generate_multi_a100.sh > /tmp/run_gen.out 2>&1"
kubectl logs -f <pod-name-gen>   # 실시간 로그 확인 권장

# 생성 완료 확인 (answers/에 .jsonl 6개) → pod 삭제
ls -lh $HOME/MT_BENCH_REPRO/data/answers/
kubectl delete pod <pod-name-gen>

# Qwen2.5-14B judge + 집계 job 제출
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "<pod-name-judge>" \
  -c "cd $HOME && bash MT_BENCH_REPRO/scripts/run_judge_multi_a100.sh > /tmp/run_judge.out 2>&1"
kubectl logs -f <pod-name-judge>

# 완료 후 결과 확인 → pod 삭제 → git push
cat $HOME/MT_BENCH_REPRO/data/results_multi.csv
kubectl delete pod <pod-name-judge>
cd $HOME/MT_BENCH_REPRO
git add data/ && git commit -m "feat: add Phase 2 results (3-model comparison, Qwen14B judge)" && git push origin main
```

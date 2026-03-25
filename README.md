# MT-Bench Reproduction — Claude Copilot Context

> 이 파일은 Claude Copilot(VSCode)이 프로젝트 컨텍스트를 파악하기 위한 문서다.
> 새 대화를 시작할 때 이 파일을 열어둔 상태로 질문하면 된다.

---

## 프로젝트 한 줄 요약

논문 **"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (NeurIPS 2023)** 의
평가 파이프라인을 Python 패키지로 재현한다.
목표는 exact score 일치가 아니라 **모델 서열과 카테고리별 성능 추이** 재현이다.

---

## 환경

| 항목        | 값                                                        |
| ----------- | --------------------------------------------------------- |
| Python      | 3.10+                                                     |
| 서버        | 부산대 AI 대학원 A100 (Kubernetes)                        |
| 서버 접속   | `ssh -p 8022 clink-seunghyun@164.125.19.48`               |
| 실행 방식   | `PYTHONPATH=src python -m mtbench_repro.cli <subcommand>` |
| 패키지 루트 | `src/mtbench_repro/`                                      |

---

## 패키지 구조 및 각 파일 역할

```
src/mtbench_repro/
├── __init__.py           # 패키지 선언, 주요 타입 노출
├── schemas.py            # 데이터 구조 (dataclass)
│                         #   MTBenchQuestion, ModelAnswer,
│                         #   JudgmentSingle, JudgmentPairwise
├── io_utils.py           # JSONL 읽기/쓰기, resume용 processed_id 조회
├── client.py             # ChatClient: OpenAI / vLLM / mock 통합 인터페이스
├── prompts.py            # 논문 Figure 5~10 프롬프트 빌더 + 응답 파서
│                         #   build_pairwise_prompt, build_single_prompt,
│                         #   parse_pairwise_verdict, parse_single_score,
│                         #   resolve_pairwise_winner
├── generate.py           # 모델 답변 생성 (2-turn, resume 지원)
├── judge_single.py       # Single-answer grading — Figure 6, 1~10점
├── judge_pairwise.py     # Pairwise comparison — Figure 5/9, AB/BA swap
├── judge_reference.py    # Reference-guided grading — Figure 8/10
│                         #   대상 카테고리: math, reasoning, coding
├── aggregate.py          # 카테고리별 집계, win rate, Spearman trend 분석
└── cli.py                # 통합 CLI (서브커맨드: generate / judge-single /
                          #   judge-pairwise / judge-reference / aggregate)
```

---

## 데이터 구조 (schemas.py 핵심)

```python
# 질문
MTBenchQuestion(question_id, category, turns: List[str], reference: Optional[List[str]])

# 답변
ModelAnswer(question_id, model_id, choices: [{"index": 0, "turns": [a1, a2]}], tstamp)
answer.get_turns()  # → [a1, a2]

# 판정 결과 (single)
JudgmentSingle(question_id, model_id, judge_id,
               score_turn1, score_turn2,  # -1.0 = 파싱 실패
               judgment_turn1, judgment_turn2, category, tstamp)
judgment.avg_score  # → (s1 + s2) / 2, 파싱 실패 시 NaN

# 판정 결과 (pairwise)
JudgmentPairwise(question_id, model_a, model_b, judge_id,
                 winner,       # model_a | model_b | "tie" | "inconsistent" | "error"
                 judgment_ab, judgment_ba,
                 winner_ab, winner_ba, turn, category, tstamp)
```

---

## 논문-코드 대응표

| 논문 근거                     | 구현 위치                                 | 설명                                   |
| ----------------------------- | ----------------------------------------- | -------------------------------------- |
| Figure 5                      | `prompts._SYSTEM_PAIRWISE`                | pairwise 기본 프롬프트                 |
| Figure 6                      | `prompts._SYSTEM_SINGLE`                  | single grading 프롬프트                |
| Figure 7                      | `prompts._SYSTEM_PAIRWISE_MATH_COT`       | CoT pairwise                           |
| Figure 8                      | `prompts._SYSTEM_PAIRWISE_REFERENCE`      | reference-guided pairwise              |
| Figure 9                      | `prompts.build_multiturn_pairwise_prompt` | multi-turn pairwise                    |
| Figure 10                     | `prompts.build_multiturn_single_prompt`   | reference-guided multi-turn single     |
| Section 3.4 conservative swap | `judge_pairwise.judge_pairwise_question`  | AB/BA 두 번 호출 후 일치할 때만 winner |
| Table 4 reference 효과        | `judge_reference.py`                      | math/coding failure rate 70%→15%       |
| Table 7 category win rate     | `aggregate.compute_win_rates`             |                                        |
| Table 8 MT-Bench Score        | `aggregate.compute_single_scores`         | 160턴 평균                             |

---

## 핵심 설계 결정 (수정 시 반드시 읽을 것)

1. **JSONL append 방식**: judge 도중 API 실패해도 완료된 결과를 보존하기 위해
   `append_jsonl`로 한 건씩 저장한다. `write_jsonl` 전체 덮어쓰기를 쓰면 안 된다.

2. **resume 기반 skip**: `get_processed_ids(output_path)`로 이미 처리된
   `question_id`를 읽어 skip한다. `--no-resume` 플래그로 비활성화 가능.

3. **conservative verdict**: pairwise에서 AB 순서와 BA 순서 판정이 다르면
   `"inconsistent"`로 저장하고 집계에서 tie로 처리한다.

4. **파싱 실패 = -1.0**: single score 파싱 실패 시 NaN 대신 `-1.0`을 저장한다.
   `avg_score` property에서 명시적으로 체크해 집계에서 제외한다.

5. **temperature 분리**: 생성은 `0.7`, judge는 `0.0` (greedy). 혼용하면 안 된다.

6. **카테고리 상수**: `MT_BENCH_CATEGORIES`와 `REFERENCE_GUIDED_CATEGORIES`는
   `schemas.py`에 정의되어 있다. 하드코딩하지 말고 항상 import해서 쓴다.

---

## Import 규칙

```python
# 항상 이 형태로 — 절대 경로
from mtbench_repro.schemas import MTBenchQuestion
from mtbench_repro.io_utils import load_questions, append_jsonl
from mtbench_repro.client import ChatClient
from mtbench_repro.prompts import build_single_prompt, parse_single_score

# 금지 — 로컬 import (ModuleNotFoundError 발생)
from schemas import MTBenchQuestion      # NG
import schemas                           # NG
```

---

## 실행 방법

### 로컬 mock (API 없이 전체 흐름 검증)

```bash
export PYTHONPATH=src

# 한 번에
bash scripts/run_generate_local.sh
bash scripts/run_judge_single_local.sh
bash scripts/run_judge_pairwise_local.sh
bash scripts/run_aggregate_local.sh

# 또는 CLI로 단계별
python -m mtbench_repro.cli generate \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ --model-id vicuna-13b --mock --sleep 0

python -m mtbench_repro.cli judge-single \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ --output-dir data/judgments/ \
  --model-id vicuna-13b --mock --sleep 0

python -m mtbench_repro.cli judge-pairwise \
  --questions data/mt_bench_questions_sample.jsonl \
  --answers-dir data/answers/ --output-dir data/judgments/ \
  --model-a vicuna-13b --model-b llama-13b --mock --sleep 0

python -m mtbench_repro.cli aggregate \
  --judgments-dir data/judgments/ --output-csv data/results.csv
```

### A100 서버 (vLLM + Qwen)

```bash
# 1. 로컬에서 서버로 복사
scp -P 8022 -r MT_BENCH_REPRO/ clink-seunghyun@164.125.19.48:~/

# 2. k8s pod 제출 (서버에서)
python3 k8s_create_job.py \
  -i pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime \
  -g 1 \
  -n "clink-seunghyun-1" \
  -c "cd /home/clink-seunghyun && bash MT_BENCH_REPRO/scripts/run_vllm_qwen_a100.sh > run.out 2>&1 && echo DONE"

# 3. 로그 확인
kubectl logs -f clink-seunghyun-1
```

---

## 현재 완료 상태

- [x] `schemas.py` — 데이터 구조
- [x] `io_utils.py` — JSONL I/O
- [x] `client.py` — ChatClient (vLLM / OpenAI / mock)
- [x] `prompts.py` — 논문 Figure 5~10 프롬프트 + 파서
- [x] `generate.py` — 답변 생성 (resume 포함)
- [x] `judge_single.py` — Single grading
- [x] `judge_pairwise.py` — Pairwise + swap
- [x] `judge_reference.py` — Reference-guided
- [x] `aggregate.py` — 집계 + Spearman trend
- [x] `cli.py` — 통합 CLI
- [x] `scripts/mock_openai_server.py` — 로컬 Flask mock 서버
- [x] `scripts/run_vllm_qwen_a100.sh` — A100 생성 스크립트
- [x] `data/mt_bench_questions_sample.jsonl` — 3문항 샘플

## 다음 작업 (TODO)

- [ ] `data/mt_bench_questions.jsonl` — FastChat 공식 80문항 연결
- [ ] A100에서 실제 vLLM 생성 실행 및 결과 확인
- [ ] GPT-4 API 연결 후 실제 judge 실행
- [ ] `notebooks/` — 결과 분석 노트북 작성

---

## 흔한 오류

| 오류                                                   | 원인                  | 해결                                                           |
| ------------------------------------------------------ | --------------------- | -------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'mtbench_repro'` | PYTHONPATH 미설정     | `export PYTHONPATH=src`                                        |
| `ModuleNotFoundError: No module named 'openai'`        | 패키지 미설치         | `pip install openai`                                           |
| `FileNotFoundError: mt_bench_questions.jsonl`          | 질문 파일 없음        | `--questions data/mt_bench_questions_sample.jsonl` 으로 테스트 |
| score가 전부 -1.0                                      | mock 파서 불일치      | `client._mock_response` 반환 형식 확인                         |
| winner가 전부 inconsistent                             | mock swap 판정 불일치 | 의도된 동작, aggregate에서 tie 처리됨                          |
| k8s pod이 바로 삭제됨                                  | sleep/while true 사용 | 금지 — 작업 끝나면 자연 종료되어야 함                          |

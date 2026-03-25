# CLAUDE.md

NeurIPS 2023 논문 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" 재현 프로젝트.
목표: 모델 랭킹 순서 및 카테고리별 성능 추이 재현 (정확한 점수 일치 아님).

---

## 현재 진행 상태 (2026-03-25 기준)

- ✅ 로컬 mock 파이프라인 전체 통과
- ✅ Phase 1 완료: Qwen2.5-7B-Instruct 단일 모델 A100 실행 (self-judge, 파이프라인 검증용)
- ⏳ **Phase 2 진행 중**: 3개 모델 답변 생성 + Qwen2.5-14B judge → 다음 실행 대기 중

---

## Phase 2 실행 순서 (내일 바로 시작)

### 서버 접속
```bash
ssh -p 8022 clink-seunghyun@164.125.19.48
```

### 0. 최신 코드 pull
```bash
cd /home/clink-seunghyun/MT_BENCH_REPRO && git pull origin main
```

### 1. 모델 다운로드 확인 (없으면 다운로드)
```bash
ls /home/clink-seunghyun/models/
```
없는 모델은 아래 명령으로 다운로드:
```bash
export PATH="$HOME/.local/bin:$PATH"
hf download meta-llama/Llama-3.1-8B-Instruct --local-dir /home/clink-seunghyun/models/Llama-3.1-8B-Instruct
hf download mistralai/Mistral-7B-Instruct-v0.3 --local-dir /home/clink-seunghyun/models/Mistral-7B-Instruct-v0.3
hf download Qwen/Qwen2.5-14B-Instruct --local-dir /home/clink-seunghyun/models/Qwen2.5-14B-Instruct
```

### 2. 3개 모델 답변 생성 job 제출
```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "clink-seunghyun-8" -c "cd /home/clink-seunghyun && bash MT_BENCH_REPRO/scripts/run_generate_multi_a100.sh > run_gen.out 2>&1"
```
```bash
tail -f /home/clink-seunghyun/run_gen.out
```

### 3. 생성 완료 확인 → pod 삭제
```bash
ls -lh /home/clink-seunghyun/MT_BENCH_REPRO/data/answers/
kubectl delete pod clink-seunghyun-8
```
answers/ 에 `.jsonl` 3개 있어야 다음 단계 진행.

### 4. Qwen2.5-14B judge + 집계 job 제출
```bash
python3 k8s_create_job.py -i vllm/vllm-openai:v0.6.6 -g 1 -n "clink-seunghyun-9" -c "cd /home/clink-seunghyun && bash MT_BENCH_REPRO/scripts/run_judge_multi_a100.sh > run_judge.out 2>&1"
```
```bash
tail -f /home/clink-seunghyun/run_judge.out
```

### 5. 완료 후 결과 확인 → pod 삭제 → git push
```bash
tail -80 /home/clink-seunghyun/run_judge.out
cat /home/clink-seunghyun/MT_BENCH_REPRO/data/results_multi.csv
kubectl delete pod clink-seunghyun-9
```
```bash
cd /home/clink-seunghyun/MT_BENCH_REPRO
git add data/
git commit -m "feat: add Phase 2 results (3-model comparison, Qwen14B judge)"
git push origin main
```

---

## 서버 환경 핵심 정보

| 항목 | 값 |
|------|-----|
| 서버 | 164.125.19.48:8022 |
| 계정 | clink-seunghyun |
| k8s 이미지 | vllm/vllm-openai:v0.6.6 |
| pod 명 규칙 | clink-seunghyun-숫자 |
| 프로젝트 경로 | /home/clink-seunghyun/MT_BENCH_REPRO |
| 모델 경로 | /home/clink-seunghyun/models/ |
| GitHub | https://github.com/kook222/mt_bench_repro |

**k8s 규정 주의:**
- sleep/while true 금지
- pod 완료/에러 후 반드시 `kubectl delete pod <이름>`
- 동시에 여러 pod 실행 자제 (공유 자원)

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

**설계 원칙:**
- 모든 데이터 JSONL 형식 (메모리 효율)
- resume 지원: 이미 처리된 question_id 스킵
- `--mock` 플래그로 API 없이 로컬 테스트 가능
- 항상 `python -m mtbench_repro.xxx` 형태로 실행 (PYTHONPATH 필요)

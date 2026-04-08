# A100 Cross-Judge Runbook

`clink-seunghyun` 계정 기준으로, 부산대 AI 서버에서 MT-Bench 교차 검증을 실제로 실행하는 절차를 정리한 문서다.

목표 순서는 아래와 같다.

1. 서버 접속 및 repo 동기화
2. 필요한 judge / unseen 모델 다운로드
3. `seen 7`에 대해 `InternLM 7B/20B` 교차 검증
4. `seen 7`에 대해 `Claude Sonnet` 교차 검증
5. `unseen 4` 답변 생성
6. `unseen 4`에 대해 `Qwen32 / InternLM20B / Claude Sonnet` 교차 검증
7. `seen 7 + unseen 4` hold-out generalization 분석
8. `TopDisc-40` 질문 subset 생성
9. `TopDisc-40 only` 재실행

주의:

- pod 이름은 반드시 `clink-seunghyun-숫자`
- command는 자연 종료되어야 함
- `sleep`, `while true` 같은 keepalive 금지
- pod 완료 후 `kubectl delete pod ...` 필수
- `Claude` judge는 GPU가 필요 없으므로, A100 job과 별개 SSH 세션에서 병렬 실행 가능

## 1. 서버 접속

```bash
ssh -p 8022 clink-seunghyun@164.125.19.48
```

## 2. repo 동기화

```bash
cd /home/clink-seunghyun

if [ ! -d mt_bench_repro ]; then
  git clone https://github.com/kook222/mt_bench_repro.git
fi

cd /home/clink-seunghyun/mt_bench_repro
git pull origin main
```

## 3. 도구 준비

```bash
export PATH="$HOME/.local/bin:$PATH"
mkdir -p /home/clink-seunghyun/models
```

필요 시:

```bash
python3 -m pip install --user -r requirements.txt
python3 -m pip install --user -r requirements-a100.txt
```

## 4. 모델 다운로드

### 4.1 Judge 모델

```bash
hf download internlm/internlm2_5-7b-chat --local-dir /home/clink-seunghyun/models/internlm2_5-7b-chat
hf download internlm/internlm2_5-20b-chat --local-dir /home/clink-seunghyun/models/internlm2_5-20b-chat
hf download Qwen/Qwen2.5-32B-Instruct-AWQ --local-dir /home/clink-seunghyun/models/Qwen2.5-32B-Instruct
```

### 4.2 unseen 4 eval 모델

```bash
hf download LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct --local-dir /home/clink-seunghyun/models/EXAONE-3.5-7.8B-Instruct
hf download ibm-granite/granite-3.1-8b-instruct --local-dir /home/clink-seunghyun/models/granite-3.1-8b-instruct
hf download tiiuae/Falcon3-7B-Instruct --local-dir /home/clink-seunghyun/models/Falcon3-7B-Instruct
hf download bigscience/bloomz-7b1-mt --local-dir /home/clink-seunghyun/models/bloomz-7b1-mt
```

## 5. seen 7 answer 존재 확인

이미 답변이 있으면 다음 단계로 간다.

```bash
cd /home/clink-seunghyun/mt_bench_repro
ls data/answers
```

필요한 seen 7:

- `Llama-3.1-8B-Instruct.jsonl`
- `SOLAR-10.7B-Instruct.jsonl`
- `gemma-2-9b-it.jsonl`
- `Yi-1.5-9B-Chat.jsonl`
- `Zephyr-7B-beta.jsonl`
- `Mistral-7B-Instruct-v0.3.jsonl`
- `Phi-3.5-mini-Instruct.jsonl`

없는 경우 먼저 생성:

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-31" -c "cd /home/clink-seunghyun/mt_bench_repro && bash scripts/run_generate_multi_a100.sh > /tmp/run_generate_multi.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-31
kubectl delete pod clink-seunghyun-31
```

Llama 추가 생성이 필요하면:

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-32" -c "cd /home/clink-seunghyun/mt_bench_repro && bash scripts/run_generate_phase3_a100.sh > /tmp/run_generate_phase3.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-32
kubectl delete pod clink-seunghyun-32
```

## 6. seen 7 교차 검증

### 6.1 InternLM 7B/20B

이 단계가 `첫 번째 본 실험`이다.

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-41" -c "cd /home/clink-seunghyun/mt_bench_repro && bash scripts/run_judge_phase4_a100.sh > /tmp/run_judge_phase4.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-41
kubectl delete pod clink-seunghyun-41
```

### 6.2 Claude Sonnet

이 단계는 GPU가 필요 없으므로, A100 pod와 별도로 SSH 세션에서 실행한다.

```bash
cd /home/clink-seunghyun/mt_bench_repro
export PYTHONPATH=src
export ANTHROPIC_API_KEY=...
bash scripts/run_judge_claude_api.sh > /tmp/run_judge_claude_seen7.out 2>&1
tail -f /tmp/run_judge_claude_seen7.out
```

## 7. unseen 4 answer generation

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-51" -c "cd /home/clink-seunghyun/mt_bench_repro && bash scripts/run_generate_unseen_a100.sh > /tmp/run_generate_unseen.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-51
kubectl delete pod clink-seunghyun-51
```

## 8. unseen 4 교차 검증

### 8.1 Qwen32

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-52" -c "cd /home/clink-seunghyun/mt_bench_repro && RUN_SINGLE=true RUN_PAIRWISE=true RUN_REFERENCE=true RUN_AGGREGATE=true JUDGE_MODEL_ID=Qwen2.5-32B-Instruct QUANTIZATION=awq GPU_MEMORY_UTILIZATION=0.95 MAX_MODEL_LEN=2048 ENFORCE_EAGER=true MAX_NUM_SEQS=1 bash scripts/run_judge_unseen_vllm_a100.sh > /tmp/run_judge_unseen_qwen32.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-52
kubectl delete pod clink-seunghyun-52
```

### 8.2 InternLM20B

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-53" -c "cd /home/clink-seunghyun/mt_bench_repro && RUN_SINGLE=true RUN_PAIRWISE=true RUN_REFERENCE=true RUN_AGGREGATE=true JUDGE_MODEL_ID=internlm2_5-20b-chat JUDGE_LABEL=internlm2_5_20b_chat TRUST_REMOTE_CODE=true GPU_MEMORY_UTILIZATION=0.92 MAX_MODEL_LEN=4096 bash scripts/run_judge_unseen_vllm_a100.sh > /tmp/run_judge_unseen_internlm20b.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-53
kubectl delete pod clink-seunghyun-53
```

### 8.3 Claude Sonnet

```bash
cd /home/clink-seunghyun/mt_bench_repro
export PYTHONPATH=src
export ANTHROPIC_API_KEY=...
ANSWERS_DIR=data/answers_unseen OUTPUT_DIR=data/judgments_unseen/claude_sonnet OUTPUT_CSV=data/results_unseen_claude_sonnet.csv OUTPUT_REF_CSV=data/results_unseen_claude_sonnet_reference.csv bash scripts/run_judge_claude_api.sh EXAONE-3.5-7.8B-Instruct granite-3.1-8b-instruct Falcon3-7B-Instruct OLMo-2-1124-7B-Instruct > /tmp/run_judge_claude_unseen.out 2>&1
tail -f /tmp/run_judge_claude_unseen.out
```

## 9. hold-out generalization 분석

```bash
cd /home/clink-seunghyun/mt_bench_repro
export PYTHONPATH=src
python3 scripts/analyze_tiny_mt_bench_generalization.py \
  --judge qwen32=data/judgments_phase3/judge_32B/single_grade,data/judgments_unseen/qwen2_5_32b_instruct/single_grade \
  --judge internlm20b=data/judgments_phase4/judge_internlm20b/single_grade,data/judgments_unseen/internlm2_5_20b_chat/single_grade \
  --judge claude=data/judgments_phase5/judge_claude_sonnet/single_grade,data/judgments_unseen/claude_sonnet/single_grade \
  --models Phi-3.5-mini-Instruct gemma-2-9b-it Yi-1.5-9B-Chat Mistral-7B-Instruct-v0.3 SOLAR-10.7B-Instruct Zephyr-7B-beta Llama-3.1-8B-Instruct EXAONE-3.5-7.8B-Instruct granite-3.1-8b-instruct Falcon3-7B-Instruct bloomz-7b1-mt \
  --dev-models Phi-3.5-mini-Instruct gemma-2-9b-it Yi-1.5-9B-Chat Mistral-7B-Instruct-v0.3 SOLAR-10.7B-Instruct Zephyr-7B-beta Llama-3.1-8B-Instruct \
  --test-models EXAONE-3.5-7.8B-Instruct granite-3.1-8b-instruct Falcon3-7B-Instruct bloomz-7b1-mt
```

## 10. TopDisc-40 subset 생성

```bash
cd /home/clink-seunghyun/mt_bench_repro
export PYTHONPATH=src
python3 scripts/prepare_topdisc_subset.py --top-n 40
```

## 11. TopDisc-40 only 재실행

### 11.1 answer generation

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-61" -c "cd /home/clink-seunghyun/mt_bench_repro && QUESTIONS=data/mt_bench_questions_topdisc40.jsonl ANSWERS_DIR=data/answers_topdisc40 bash scripts/run_generate_unseen_a100.sh > /tmp/run_generate_unseen_topdisc40.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-61
kubectl delete pod clink-seunghyun-61
```

### 11.2 Qwen32 judge

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-62" -c "cd /home/clink-seunghyun/mt_bench_repro && QUESTIONS=data/mt_bench_questions_topdisc40.jsonl ANSWERS_DIR=data/answers_topdisc40 OUTPUT_DIR=data/judgments_unseen_topdisc40/qwen32 OUTPUT_CSV=data/results_unseen_topdisc40_qwen32.csv RUN_REFERENCE=false JUDGE_MODEL_ID=Qwen2.5-32B-Instruct QUANTIZATION=awq GPU_MEMORY_UTILIZATION=0.95 MAX_MODEL_LEN=2048 ENFORCE_EAGER=true MAX_NUM_SEQS=1 bash scripts/run_judge_unseen_vllm_a100.sh > /tmp/run_judge_topdisc40_qwen32.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-62
kubectl delete pod clink-seunghyun-62
```

### 11.3 InternLM20B judge

```bash
cd /home/clink-seunghyun
python3 k8s_create_job.py -i "vllm/vllm-openai:v0.6.6" -g 1 -n "clink-seunghyun-63" -c "cd /home/clink-seunghyun/mt_bench_repro && QUESTIONS=data/mt_bench_questions_topdisc40.jsonl ANSWERS_DIR=data/answers_topdisc40 OUTPUT_DIR=data/judgments_unseen_topdisc40/internlm OUTPUT_CSV=data/results_unseen_topdisc40_internlm.csv RUN_REFERENCE=false JUDGE_MODEL_ID=internlm2_5-20b-chat JUDGE_LABEL=internlm2_5_20b_chat TRUST_REMOTE_CODE=true GPU_MEMORY_UTILIZATION=0.92 MAX_MODEL_LEN=4096 bash scripts/run_judge_unseen_vllm_a100.sh > /tmp/run_judge_topdisc40_internlm.out 2>&1 && echo DONE"
kubectl logs -f clink-seunghyun-63
kubectl delete pod clink-seunghyun-63
```

### 11.4 Claude Sonnet judge

```bash
cd /home/clink-seunghyun/mt_bench_repro
export PYTHONPATH=src
export ANTHROPIC_API_KEY=...
QUESTIONS=data/mt_bench_questions_topdisc40.jsonl ANSWERS_DIR=data/answers_topdisc40 OUTPUT_DIR=data/judgments_unseen_topdisc40/claude_sonnet OUTPUT_CSV=data/results_unseen_topdisc40_claude_sonnet.csv OUTPUT_REF_CSV=data/results_unseen_topdisc40_claude_sonnet_reference.csv RUN_REFERENCE=false bash scripts/run_judge_claude_api.sh EXAONE-3.5-7.8B-Instruct granite-3.1-8b-instruct Falcon3-7B-Instruct bloomz-7b1-mt > /tmp/run_judge_claude_topdisc40.out 2>&1
tail -f /tmp/run_judge_claude_topdisc40.out
```

## 최소 체크포인트

각 단계 끝날 때 아래를 확인한다.

```bash
ls data/judgments_phase4
ls data/judgments_phase5
ls data/judgments_unseen
ls data/judgments_unseen_topdisc40
```

그리고 pod는 반드시 삭제:

```bash
kubectl delete pod clink-seunghyun-41
kubectl delete pod clink-seunghyun-51
kubectl delete pod clink-seunghyun-52
kubectl delete pod clink-seunghyun-53
kubectl delete pod clink-seunghyun-61
kubectl delete pod clink-seunghyun-62
kubectl delete pod clink-seunghyun-63
```

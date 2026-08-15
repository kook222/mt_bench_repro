#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=gemma4_12b_common.sh
source "$SCRIPT_DIR/gemma4_12b_common.sh"
cd "$PROJECT_DIR"

TARGET_LANG="both"
if [[ "$#" -gt 0 ]]; then
  if [[ "$#" -ne 2 || "$1" != "--lang" ]]; then
    echo "Usage: $0 [--lang en|ko|both]" >&2
    exit 2
  fi
  TARGET_LANG="$2"
fi
case "$TARGET_LANG" in
  en|ko|both) ;;
  *) echo "Invalid --lang: $TARGET_LANG" >&2; exit 2 ;;
esac

EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "EEVE-Korean-Instruct-10.8B"
  "EXAONE-3.5-7.8B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

gemma4_export_user
gemma4_make_runtime_dirs

JUDGE_LOG="$GEMMA4_LOG_DIR/judge.log"
exec > >(tee -a "$JUDGE_LOG") 2>&1
echo "===== Gemma 4 judge: $(date -Iseconds) ====="

export HF_HOME
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/pip_cache}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/tmp/torchinductor_cache}"
export TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-/tmp/triton_cache}"

if [[ ! -x "$GEMMA4_VENV_DIR/bin/python" || ! -x "$GEMMA4_VENV_DIR/bin/transformers" ]]; then
  echo "[ERROR] prepared runtime is missing: $GEMMA4_VENV_DIR" >&2
  echo "        run prepare_gemma4_12b_a100.sh in a CPU pod first" >&2
  exit 1
fi
PYTHON="$GEMMA4_VENV_DIR/bin/python"
TRANSFORMERS_CLI="$GEMMA4_VENV_DIR/bin/transformers"
export PYTHONPATH="$PROJECT_DIR/src"

echo "[Preflight 1/4] prepared model and client"
"$PYTHON" scripts/tools/verify_gemma4_preparation.py \
  --model-dir "$JUDGE_MODEL_DIR" \
  --record "$GEMMA4_PREPARE_RECORD"

echo "[Preflight 2/4] immutable benchmark inputs"
for lang in en ko; do
  question_count="$(wc -l < "$PROJECT_DIR/data/$lang/questions.jsonl" | tr -d ' ')"
  if [[ "$question_count" -ne 80 ]]; then
    echo "[ERROR] expected 80 $lang questions; found $question_count" >&2
    exit 1
  fi
  for model_id in "${EVAL_MODELS[@]}"; do
    answer_file="$PROJECT_DIR/data/$lang/answers/$model_id.jsonl"
    if [[ ! -f "$answer_file" ]]; then
      echo "[ERROR] missing validated answer file: $answer_file" >&2
      exit 1
    fi
    answer_count="$(wc -l < "$answer_file" | tr -d ' ')"
    if [[ "$answer_count" -ne 80 ]]; then
      echo "[ERROR] expected 80 answers in $answer_file; found $answer_count" >&2
      exit 1
    fi
  done
done

echo "[Preflight 3/4] A100 40GB allocation"
command -v nvidia-smi >/dev/null || {
  echo "[ERROR] nvidia-smi not found" >&2
  exit 1
}
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
GPU_MEMORY_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')"
case "$GPU_NAME" in
  *A100*) ;;
  *) echo "[ERROR] expected NVIDIA A100, found: $GPU_NAME" >&2; exit 1 ;;
esac
if [[ "$GPU_MEMORY_MIB" -lt 39000 || "$GPU_MEMORY_MIB" -gt 45000 ]]; then
  echo "[ERROR] expected A100 40GB, found ${GPU_MEMORY_MIB} MiB" >&2
  exit 1
fi

echo "[Preflight 4/4] paper-aligned PyTorch runtime"
"$PYTHON" - <<'PY'
import torch
import torchvision
import transformers
from PIL import __version__ as pillow_version

if torch.__version__.split("+")[0] != "2.5.1":
    raise SystemExit(f"expected PyTorch 2.5.1, found {torch.__version__}")
if torch.version.cuda != "12.4":
    raise SystemExit(f"expected CUDA 12.4 runtime, found {torch.version.cuda}")
if torchvision.__version__.split("+")[0] != "0.20.1":
    raise SystemExit(f"expected torchvision 0.20.1, found {torchvision.__version__}")
if transformers.__version__ != "5.15.0":
    raise SystemExit(f"expected Transformers 5.15.0, found {transformers.__version__}")
if pillow_version != "11.0.0":
    raise SystemExit(f"expected Pillow 11.0.0, found {pillow_version}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available to PyTorch")
PY

SERVE_PORT="${SERVE_PORT:-8000}"
SERVE_PID=""
cleanup_server() {
  if [[ -n "${SERVE_PID:-}" ]]; then
    kill "$SERVE_PID" 2>/dev/null || true
    wait "$SERVE_PID" 2>/dev/null || true
    SERVE_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

echo "[Serve] local $JUDGE_MODEL_DIR as $JUDGE_MODEL_ID"
cd "$MODEL_BASE_DIR"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$TRANSFORMERS_CLI" serve "$JUDGE_MODEL_ID" \
  --device cuda:0 \
  --dtype bfloat16 \
  --attn-implementation sdpa \
  --reasoning auto \
  --host 127.0.0.1 \
  --port "$SERVE_PORT" \
  --default-seed 0 \
  --log-level info \
  > "$SERVE_LOG" 2>&1 &
SERVE_PID=$!
cd "$PROJECT_DIR"

STARTUP_STARTED="$(date +%s)"
if ! "$PYTHON" scripts/tools/wait_for_http.py \
  "http://127.0.0.1:$SERVE_PORT/health" \
  --attempts 360 \
  --interval 5 \
  --request-timeout 3 \
  --process-id "$SERVE_PID"; then
  if kill -0 "$SERVE_PID" 2>/dev/null; then
    echo "[ERROR] Transformers server was not healthy within 1800s" >&2
  else
    echo "[ERROR] Transformers server exited during startup" >&2
  fi
  "$PYTHON" - "$SERVE_LOG" <<'PY' >&2
from collections import deque
from pathlib import Path
import sys

with Path(sys.argv[1]).open(encoding="utf-8", errors="replace") as stream:
    print("".join(deque(stream, maxlen=240)), end="")
PY
  exit 1
fi
WAITED=$(( $(date +%s) - STARTUP_STARTED ))
echo "[OK] Transformers server ready after ${WAITED}s"

BASE_URL="http://127.0.0.1:$SERVE_PORT/v1"
"$PYTHON" - <<PY
from openai import OpenAI

client = OpenAI(api_key="EMPTY", base_url="$BASE_URL")
response = client.chat.completions.create(
    model="$JUDGE_MODEL_ID",
    messages=[{"role": "user", "content": "Reply exactly with Rating: [[5]]"}],
    temperature=0.0,
    max_tokens=512,
)
content = response.choices[0].message.content or ""
if "[[5]]" not in content:
    raise SystemExit(f"Gemma 4 smoke test was not parseable: {content!r}")
print("[OK] Gemma 4 endpoint smoke test")
PY

run_language() {
  local lang="$1"
  local questions="$PROJECT_DIR/data/$lang/questions.jsonl"
  local answers_dir="$PROJECT_DIR/data/$lang/answers"
  local judgments_dir="$RUN_ROOT/reproduction/$lang/judgments/gemma4/judge_12B"
  local results_dir="$RUN_ROOT/aggregates/gemma4_12b/$lang"
  local lang_args=()
  if [[ "$lang" == "ko" ]]; then
    lang_args=(--lang ko)
  fi

  mkdir -p "$judgments_dir" "$results_dir"

  echo "[$lang 1/4] single grading"
  for model_id in "${EVAL_MODELS[@]}"; do
    "$PYTHON" -m mtbench_repro.cli judge-single \
      --questions "$questions" \
      --answers-dir "$answers_dir" \
      --output-dir "$judgments_dir" \
      --model-id "$model_id" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key EMPTY \
      --sleep 0 \
      "${lang_args[@]}"
  done

  echo "[$lang 2/4] AB/BA pairwise grading"
  "$PYTHON" -m mtbench_repro.cli judge-pairwise \
    --questions "$questions" \
    --answers-dir "$answers_dir" \
    --output-dir "$judgments_dir" \
    --models "${EVAL_MODELS[@]}" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key EMPTY \
    --sleep 0 \
    "${lang_args[@]}"

  echo "[$lang 3/4] reference-guided single grading"
  for model_id in "${EVAL_MODELS[@]}"; do
    "$PYTHON" -m mtbench_repro.cli judge-reference \
      --questions "$questions" \
      --answers-dir "$answers_dir" \
      --output-dir "$judgments_dir" \
      --mode single \
      --model-id "$model_id" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key EMPTY \
      --reference-selection historical-declared \
      --sleep 0 \
      "${lang_args[@]}"
  done

  echo "[$lang 4/4] strict aggregation"
  "$PYTHON" -m mtbench_repro.cli aggregate \
    --judgments-dir "$judgments_dir" \
    --questions-path "$questions" \
    --models "${EVAL_MODELS[@]}" \
    --output-csv "$results_dir/scores.csv" \
    --output-ref-csv "$results_dir/reference_scores.csv" \
    --reference-selection historical-declared
}

if [[ "$TARGET_LANG" == "en" || "$TARGET_LANG" == "both" ]]; then
  run_language en
fi
if [[ "$TARGET_LANG" == "ko" || "$TARGET_LANG" == "both" ]]; then
  run_language ko
fi

"$PYTHON" scripts/tools/verify_gemma4_run.py \
  --run-root "$RUN_ROOT/reproduction" \
  --lang "$TARGET_LANG" \
  --output "$RUN_ROOT/aggregates/gemma4_12b/run_audit.json"

RUNTIME_RECORD="$RUN_ROOT/aggregates/gemma4_12b/runtime_environment.json"
PREPARE_RECORD_SHA256="$("$PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$GEMMA4_PREPARE_RECORD")"
REPOSITORY_COMMIT="$(
  git -c safe.directory="$PROJECT_DIR" -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null \
    || printf 'unavailable'
)"
"$PYTHON" - <<PY
import importlib.metadata
import json
import platform
import subprocess

gpu = subprocess.check_output(
    ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
    text=True,
).strip()
payload = {
    "gpu": gpu,
    "python": platform.python_version(),
    "torch": importlib.metadata.version("torch"),
    "transformers": importlib.metadata.version("transformers"),
    "openai": importlib.metadata.version("openai"),
    "torch_cuda": __import__("torch").version.cuda,
    "container_image": "$CONTAINER_IMAGE",
    "repository_commit": "$REPOSITORY_COMMIT",
    "model_id": "$HF_MODEL_ID",
    "model_revision": "$MODEL_REVISION",
    "model_dir": "$JUDGE_MODEL_DIR",
    "prepare_record_sha256": "$PREPARE_RECORD_SHA256",
    "served_model_name": "$JUDGE_MODEL_ID",
    "inference_backend": "transformers_serve",
    "attention_implementation": "sdpa",
    "reasoning_mode": "auto",
    "dtype": "bfloat16",
    "concurrent_requests": 1,
    "seed": 0,
    "temperature": 0.0,
    "max_tokens_single": 512,
    "max_tokens_pairwise": 1024,
    "max_tokens_reference": 1024,
    "target_language": "$TARGET_LANG",
    "question_root": "$PROJECT_DIR/data",
    "judgment_root": "$RUN_ROOT/reproduction",
    "aggregate_root": "$RUN_ROOT/aggregates/gemma4_12b",
}
with open("$RUNTIME_RECORD", "w", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
PY

echo "[Complete] Gemma 4 judge run verified"
echo "  judgments: $RUN_ROOT/reproduction/{en,ko}/judgments/gemma4/judge_12B"
echo "  aggregates: $RUN_ROOT/aggregates/gemma4_12b"
echo "  logs: $GEMMA4_LOG_DIR"

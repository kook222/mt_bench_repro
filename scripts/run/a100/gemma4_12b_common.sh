#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "[ERROR] source this file from a Gemma 4 run script" >&2
  exit 2
fi

GEMMA4_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$GEMMA4_SCRIPT_DIR/../../.." && pwd)"
WORKSPACE_PARENT="$(dirname "$PROJECT_DIR")"

RUN_ROOT="${RUN_ROOT:-$PROJECT_DIR/runs}"
MODEL_BASE_DIR="${MODEL_BASE_DIR:-$WORKSPACE_PARENT/models}"
HF_HOME="${HF_HOME:-$WORKSPACE_PARENT/.cache/huggingface}"

HF_MODEL_ID="google/gemma-4-12B-it"
MODEL_REVISION="707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
JUDGE_MODEL_ID="Gemma-4-12B-it"
JUDGE_MODEL_DIR="${JUDGE_MODEL_DIR:-$MODEL_BASE_DIR/$JUDGE_MODEL_ID}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-pytorch/pytorch@sha256:c8268a92a69bd500f8be0e665b2630ee006dadaf7bfbc24249141b15ff622755}"
TRANSFORMERS_VERSION="5.15.0"
OPENAI_VERSION="2.54.0"
TORCHVISION_VERSION="0.20.1"
PILLOW_VERSION="11.0.0"

GEMMA4_RUNTIME_DIR="${GEMMA4_RUNTIME_DIR:-$RUN_ROOT/runtime/gemma4_12b}"
GEMMA4_VENV_DIR="${GEMMA4_VENV_DIR:-$GEMMA4_RUNTIME_DIR/venv}"
GEMMA4_PREPARE_RECORD="${GEMMA4_PREPARE_RECORD:-$GEMMA4_RUNTIME_DIR/prepare_record.json}"
GEMMA4_LOG_DIR="${GEMMA4_LOG_DIR:-$RUN_ROOT/logs/gemma4_12b}"
SERVE_LOG="${SERVE_LOG:-$GEMMA4_LOG_DIR/transformers_serve.log}"

gemma4_make_runtime_dirs() {
  mkdir -p \
    "$MODEL_BASE_DIR" \
    "$HF_HOME" \
    "$GEMMA4_RUNTIME_DIR" \
    "$GEMMA4_LOG_DIR"
}

gemma4_export_user() {
  local runtime_uid runtime_user
  runtime_uid="$(id -u)"
  runtime_user="$(id -un 2>/dev/null || printf 'uid-%s' "$runtime_uid")"
  export LOGNAME="$runtime_user"
  export USER="$runtime_user"
}

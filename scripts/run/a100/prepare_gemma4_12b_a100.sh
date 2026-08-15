#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=gemma4_12b_common.sh
source "$SCRIPT_DIR/gemma4_12b_common.sh"
cd "$PROJECT_DIR"

gemma4_export_user
gemma4_make_runtime_dirs

PREPARE_LOG="$GEMMA4_LOG_DIR/prepare.log"
exec > >(tee -a "$PREPARE_LOG") 2>&1
echo "===== Gemma 4 preparation: $(date -Iseconds) ====="

export HF_HOME
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$WORKSPACE_PARENT/.cache/pip}"

if [[ -z "${HF_TOKEN:-}" && -n "${HF_TOKEN_FILE:-}" ]]; then
  if [[ ! -r "$HF_TOKEN_FILE" ]]; then
    echo "[ERROR] HF_TOKEN_FILE is not readable: $HF_TOKEN_FILE" >&2
    exit 1
  fi
  HF_TOKEN="$(<"$HF_TOKEN_FILE")"
  export HF_TOKEN
fi
if [[ -z "${HF_TOKEN:-}" || ! "$HF_TOKEN" =~ ^hf_[A-Za-z0-9]+$ ]]; then
  echo "[ERROR] a valid Hugging Face read token is required" >&2
  exit 1
fi

python3 -m pip --version >/dev/null || {
  echo "[ERROR] pip is unavailable in the preparation image" >&2
  exit 1
}

echo "[Prepare 1/3] pinned Transformers serving runtime"
case "$GEMMA4_VENV_DIR" in
  "$GEMMA4_RUNTIME_DIR"/*) ;;
  *)
    echo "[ERROR] virtual environment must remain below $GEMMA4_RUNTIME_DIR" >&2
    exit 1
    ;;
esac
VENV_PREVIOUS="$GEMMA4_RUNTIME_DIR/venv.previous.$$"
restore_previous_venv() {
  if [[ -d "$VENV_PREVIOUS" ]]; then
    rm -rf "$GEMMA4_VENV_DIR"
    mv "$VENV_PREVIOUS" "$GEMMA4_VENV_DIR"
  else
    rm -rf "$GEMMA4_VENV_DIR"
  fi
}
trap restore_previous_venv EXIT INT TERM
if [[ -e "$GEMMA4_VENV_DIR" ]]; then
  mv "$GEMMA4_VENV_DIR" "$VENV_PREVIOUS"
fi
python3 -m venv --system-site-packages "$GEMMA4_VENV_DIR"
"$GEMMA4_VENV_DIR/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-deps \
  --force-reinstall \
  --index-url https://download.pytorch.org/whl/cu124 \
  "torchvision==$TORCHVISION_VERSION"
"$GEMMA4_VENV_DIR/bin/python" -m pip install \
  --disable-pip-version-check \
  "transformers[serving]==$TRANSFORMERS_VERSION" \
  "openai==$OPENAI_VERSION" \
  "Pillow==$PILLOW_VERSION"
"$GEMMA4_VENV_DIR/bin/python" - <<'PY'
import torch
import torchvision
import transformers
from PIL import __version__ as pillow_version

if torch.__version__.split("+")[0] != "2.5.1":
    raise SystemExit(f"expected PyTorch 2.5.1, found {torch.__version__}")
if torch.version.cuda != "12.4":
    raise SystemExit(f"expected CUDA 12.4 runtime, found {torch.version.cuda}")
if transformers.__version__ != "5.15.0":
    raise SystemExit(f"expected Transformers 5.15.0, found {transformers.__version__}")
if torchvision.__version__.split("+")[0] != "0.20.1":
    raise SystemExit(f"expected torchvision 0.20.1, found {torchvision.__version__}")
if pillow_version != "11.0.0":
    raise SystemExit(f"expected Pillow 11.0.0, found {pillow_version}")
PY
rm -rf "$VENV_PREVIOUS"
trap - EXIT INT TERM

echo "[Prepare 2/3] pinned model download"
echo "  model: $HF_MODEL_ID@$MODEL_REVISION"
echo "  path:  $JUDGE_MODEL_DIR"
"$GEMMA4_VENV_DIR/bin/hf" download "$HF_MODEL_ID" \
  --revision "$MODEL_REVISION" \
  --local-dir "$JUDGE_MODEL_DIR"

export PYTHONPATH="$PROJECT_DIR/src"

echo "[Prepare 3/3] immutable preparation record"
"$GEMMA4_VENV_DIR/bin/python" scripts/tools/verify_gemma4_preparation.py \
  --model-dir "$JUDGE_MODEL_DIR" \
  --record "$GEMMA4_PREPARE_RECORD" \
  --write

unset HF_TOKEN 2>/dev/null || true

echo "[Complete] Gemma 4 preparation finished"
echo "  model:   $JUDGE_MODEL_DIR"
echo "  runtime: $GEMMA4_VENV_DIR"
echo "  record:  $GEMMA4_PREPARE_RECORD"
echo "  log:     $PREPARE_LOG"

# Scripts Manifest

This directory separates experiment execution and translation checks.

## Directory Layout

- `scripts/run/a100/` - A100/vLLM shell scripts used for EN/KO answer generation and
  open-weight judge runs.
- `scripts/run/local/` - Local smoke tests, translation-quality checks, and
  API-based GPT judge runs.
- `scripts/translate/` - Korean MT-Bench translation validation and EN/KO comparison.
- `scripts/analysis/` - Translation-validity analysis kept for the paper methods
  section.
- `scripts/tools/` - Dataset download/preparation helpers.

## Main Reproduction Commands

```bash
export PYTHONPATH=src

# Recompute EN/KO comparison tables from committed results.
python3 scripts/translate/compare_en_ko.py

# Re-run translation-validity analysis when back-translation outputs exist.
python3 scripts/analysis/analyze_translation_validity.py
```

## Local Helpers

- `scripts/run/local/run_mock_full.sh` - End-to-end mock smoke test.
- `scripts/run/local/run_quality_check_local.sh` - Back-translation and
  translation-validity scoring.
- `scripts/run/local/run_judge_gpt_local.sh` - GPT-4o-mini judge run through
  the OpenAI API.

Legacy English-only drafts and obsolete statistical side outputs were removed
so the repository reflects the current experiment scope.

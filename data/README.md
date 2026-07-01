# Data Manifest

This repository includes the aggregate CSV files and the raw judge outputs needed
to audit the reported MT-Bench statistics.

## Raw Judgments

Raw judge outputs are stored under:

- `data/en/judgments/`
- `data/ko/judgments/`

The public raw judgment set contains 270 JSONL files and 18,540 records:

| Split | Files |
|-------|------:|
| English judgments | 135 |
| Korean judgments | 135 |
| Pairwise JSONL | 150 |
| Single-grade JSONL | 60 |
| Reference-guided JSONL | 60 |

Each language contains five judge settings under both `data/en/judgments/` and
`data/ko/judgments/`:

- Qwen judge_7B
- Qwen judge_14B
- Qwen judge_32B
- EXAONE judge_32B
- GPT judge_gpt4omini

For each judge setting, the repository includes 15 pairwise files, 6 single-grade
files, and 6 reference-guided files. Non-standard missing values from the local
raw export were normalized from `NaN` to JSON `null` so that every JSONL file is
strictly parseable by standard JSON readers.

## Recomputing Reported Metrics

```bash
python3 scripts/translate/compare_en_ko.py
python3 scripts/paper/generate_figures.py
```

These commands regenerate the EN-KO comparison CSVs, KIPS-ready paper figures,
and copy-ready tables from the committed data.

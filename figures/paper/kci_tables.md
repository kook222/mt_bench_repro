# KCI-style Copy Tables

## Table 1. Qwen-32B EN-KO single-grade score gap

| Model       | EN   | KO   | KO-EN   |
|:------------|:-----|:-----|:--------|
| Phi-3.5     | 8.06 | 5.52 | -2.54   |
| Mistral-7B  | 7.09 | 4.73 | -2.36   |
| Llama-8B    | 7.71 | 5.79 | -1.93   |
| Gemma-9B    | 8.09 | 7.35 | -0.74   |
| EEVE-10.8B  | 6.72 | 6.38 | -0.34   |
| EXAONE-7.8B | 8.32 | 8.09 | -0.23   |

## Table 2. Inconsistency and first-position tendency

| Judge       | EN inconsistency   | KO inconsistency   | Delta    | EN first-pos/incon   | KO first-pos/incon   |
|:------------|:-------------------|:-------------------|:---------|:---------------------|:---------------------|
| Qwen-7B     | 79.2%              | 44.9%              | -34.3 pp | 66%                  | 90%                  |
| Qwen-14B    | 45.1%              | 23.2%              | -21.8 pp | 79%                  | 26%                  |
| Qwen-32B    | 30.9%              | 20.4%              | -10.5 pp | 72%                  | 70%                  |
| EXAONE-32B  | 42.2%              | 30.5%              | -11.7 pp | 90%                  | 86%                  |
| GPT-4o-mini | 33.2%              | 21.6%              | -11.7 pp | 80%                  | 83%                  |

## Table 3. Reference-guided score difference by judge

| Lang   | Judge       | Non-ref   | Ref   | Ref - non-ref   |
|:-------|:------------|:----------|:------|:----------------|
| EN     | Qwen-7B     | 7.84      | 6.72  | -1.12           |
| EN     | Qwen-14B    | 7.82      | 6.00  | -1.82           |
| EN     | Qwen-32B    | 7.67      | 5.18  | -2.49           |
| EN     | EXAONE-32B  | 7.93      | 6.72  | -1.21           |
| EN     | GPT-4o-mini | 7.81      | 5.30  | -2.51           |
| KO     | Qwen-7B     | 6.91      | 6.51  | -0.40           |
| KO     | Qwen-14B    | 6.32      | 4.68  | -1.64           |
| KO     | Qwen-32B    | 6.35      | 4.87  | -1.49           |
| KO     | EXAONE-32B  | 7.33      | 6.04  | -1.29           |
| KO     | GPT-4o-mini | 6.70      | 4.55  | -2.15           |

# KCI-style Copy Tables

## Table 1. Qwen-32B EN-KO single-grade score gap

| Model       |   EN |   KO |   KO-EN | p      |
|:------------|-----:|-----:|--------:|:-------|
| Phi-3.5     | 8.06 | 5.52 |   -2.54 | p<.001 |
| Mistral-7B  | 7.09 | 4.73 |   -2.36 | p<.001 |
| Llama-8B    | 7.71 | 5.79 |   -1.93 | p<.001 |
| Gemma-9B    | 8.09 | 7.35 |   -0.74 | p<.001 |
| EEVE-10.8B  | 6.72 | 6.38 |   -0.34 | p<.05  |
| EXAONE-7.8B | 8.32 | 8.09 |   -0.23 | p<.05  |

## Table 2. Inconsistency and first-position tendency

| Judge       | EN inconsistency   | KO inconsistency   | Delta    | EN first-pos/incon   | KO first-pos/incon   |
|:------------|:-------------------|:-------------------|:---------|:---------------------|:---------------------|
| Qwen-7B     | 79.2%              | 44.9%              | -34.3 pp | 66%                  | 90%                  |
| Qwen-14B    | 45.1%              | 23.2%              | -21.8 pp | 79%                  | 26%                  |
| Qwen-32B    | 30.9%              | 20.4%              | -10.5 pp | 72%                  | 70%                  |
| EXAONE-32B  | 42.2%              | 30.5%              | -11.7 pp | 90%                  | 86%                  |
| GPT-4o-mini | 33.2%              | 21.6%              | -11.7 pp | 80%                  | 83%                  |

## Table 3. Permutation tests for inconsistency rates

| Comparison        |   Observed diff | p       | sig          |
|:------------------|----------------:|:--------|:-------------|
| EN 7B vs 14B      |          0.3417 | p<.001  | p<0.001      |
| EN 14B vs 32B     |          0.1417 | p<.001  | p<0.001      |
| EN 7B vs 32B      |          0.4833 | p<.001  | p<0.001      |
| KO 7B vs 14B      |          0.2167 | p<.001  | p<0.001      |
| KO 14B vs 32B     |          0.0283 | p=0.103 | p=0.103 (ns) |
| KO 7B vs 32B      |          0.245  | p<.001  | p<0.001      |
| EN vs KO Qwen-7B  |          0.3433 | p<.001  | p<0.001      |
| EN vs KO Qwen-14B |          0.2183 | p<.001  | p<0.001      |
| EN vs KO Qwen-32B |          0.105  | p<.001  | p<0.001      |

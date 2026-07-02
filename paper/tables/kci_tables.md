# Paper-ready Tables

## Table 1. Experimental design for the Korean MT-Bench reliability audit

| 구성 요소             | 규모                                  | 논문상 역할                                               |
|:------------------|:------------------------------------|:-----------------------------------------------------|
| Benchmark         | 80 two-turn items x 2 languages     | 원 MT-Bench와 한국어 번역본을 같은 문항 단위로 직접 비교                 |
| Answer generation | 6 evaluated LLMs x EN/KO            | 모델군별 한국어 점수 하락과 한국어 적응 모델의 완충 효과 확인                  |
| Judge settings    | 5 judges                            | same-family Qwen judge와 cross-family judge의 판정 편향 비교 |
| Judgment modes    | single / pairwise AB-BA / reference | 점수 차이, 순서 민감도, reference 제공 효과를 분리 측정                |
| Audit records     | 270 raw judgment JSONL files        | 집계표뿐 아니라 원시 판정 파일에서 결과 재계산 가능                        |

## Table 2. Qwen-32B judge score shift from English to Korean

| Model       | Group           | EN   | KO   | KO-EN   | Drop size   |
|:------------|:----------------|:-----|:-----|:--------|:------------|
| Phi-3.5     | general-purpose | 8.06 | 5.52 | -2.54   | large       |
| Mistral-7B  | general-purpose | 7.09 | 4.73 | -2.36   | large       |
| Llama-8B    | general-purpose | 7.71 | 5.79 | -1.93   | large       |
| Gemma-9B    | general-purpose | 8.09 | 7.35 | -0.74   | moderate    |
| EEVE-10.8B  | Korean-adapted  | 6.72 | 6.38 | -0.34   | small       |
| EXAONE-7.8B | Korean-adapted  | 8.32 | 8.09 | -0.23   | small       |

## Table 3. Pairwise judge reliability and first-position tendency

| Judge       | Family       | EN inc.   | KO inc.   | EN first   | KO first   | EN ref parse   | KO ref parse   |
|:------------|:-------------|:----------|:----------|:-----------|:-----------|:---------------|:---------------|
| Qwen-7B     | same-family  | 79.2%     | 44.9%     | 66%        | 90%        | 2.9%           | 33.3%          |
| Qwen-14B    | same-family  | 45.1%     | 23.2%     | 79%        | 26%        | 0.0%           | 1.7%           |
| Qwen-32B    | same-family  | 30.9%     | 20.4%     | 72%        | 70%        | 0.0%           | 0.0%           |
| EXAONE-32B  | cross-family | 42.2%     | 30.5%     | 90%        | 86%        | 0.0%           | 0.0%           |
| GPT-4o-mini | cross-family | 33.2%     | 21.6%     | 80%        | 83%        | 0.0%           | 0.0%           |

## Table 4. Reference-guided score penalty and parse failure

| Judge       | EN drop   | KO drop   | EN parse   | KO parse   |
|:------------|:----------|:----------|:-----------|:-----------|
| Qwen-7B     | -1.12     | -0.40     | 2.9%       | 33.3%      |
| Qwen-14B    | -1.82     | -1.64     | 0.0%       | 1.7%       |
| Qwen-32B    | -2.49     | -1.49     | 0.0%       | 0.0%       |
| EXAONE-32B  | -1.21     | -1.29     | 0.0%       | 0.0%       |
| GPT-4o-mini | -2.51     | -2.15     | 0.0%       | 0.0%       |

## Appendix Table A1. Detailed reference-guided score means

| Judge       | EN non-ref   | EN ref   | EN drop   | KO non-ref   | KO ref   | KO drop   | EN parse   | KO parse   |
|:------------|:-------------|:---------|:----------|:-------------|:---------|:----------|:-----------|:-----------|
| Qwen-7B     | 7.84         | 6.72     | -1.12     | 6.91         | 6.51     | -0.40     | 2.9%       | 33.3%      |
| Qwen-14B    | 7.82         | 6.00     | -1.82     | 6.32         | 4.68     | -1.64     | 0.0%       | 1.7%       |
| Qwen-32B    | 7.67         | 5.18     | -2.49     | 6.35         | 4.87     | -1.49     | 0.0%       | 0.0%       |
| EXAONE-32B  | 7.93         | 6.72     | -1.21     | 7.33         | 6.04     | -1.29     | 0.0%       | 0.0%       |
| GPT-4o-mini | 7.81         | 5.30     | -2.51     | 6.70         | 4.55     | -2.15     | 0.0%       | 0.0%       |

# 오픈소스 LLM-as-a-Judge의 신뢰도 분석:
# 판사 크기 스케일링, 위치 편향 전이, 그리고 비용 효율적 평가

**Reliability Analysis of Open-Source LLM-as-a-Judge:
Judge Size Scaling, Position Bias Transition, and Cost-Efficient Evaluation**

박승현 (부산대학교 정보컴퓨터공학부)†

†shp09240000@pusan.ac.kr, CLINK Lab, Pusan National University

---

## 요약

대형 언어 모델(LLM)을 평가자로 활용하는 LLM-as-a-Judge 방식이 빠르게 확산되고 있으나, 오픈소스 모델을 평가자로 사용할 때의 신뢰도는 체계적으로 검증되지 않았다. 본 논문은 MT-Bench 80문항을 기반으로 Qwen2.5 계열 7B·14B·32B 모델을 평가자로, 7종의 오픈소스 언어 모델을 피평가자로 설정하여 신뢰도를 다각도로 분석한다. 실험 결과, 평가자 크기가 증가할수록 pairwise 불일치율은 단조 감소(78.75%→46.85%→32.86%)하나, 불일치 원인이 무작위 노이즈에서 위치 편향(position bias)으로 전환됨을 확인하였다. 또한 다수결 앙상블은 단일 고품질 평가자보다 오히려 성능이 저하(58.63%)되며, inconsistent 판정을 기권으로 처리하는 개선 앙상블이 이를 해결(24.70%)함을 실증하였다. 아울러 변별도 기반 40문항(tinyMT-Bench)으로 전체 순위를 완전히 보존(ρ=1.000)하면서 평가 비용을 50% 절감할 수 있음을 보인다. 이를 통해 오픈소스 LLM-as-a-Judge 활용을 위한 실용적 가이드라인 세 가지를 제시한다.

**핵심어**: LLM-as-a-Judge, 위치 편향, 앙상블 평가, MT-Bench, 오픈소스 언어 모델

---

## Abstract

LLM-as-a-Judge, which uses large language models as evaluators, is rapidly gaining popularity, yet the reliability of open-source models as judges remains insufficiently validated. This paper analyzes reliability from multiple perspectives using 80 MT-Bench questions, with Qwen2.5 7B/14B/32B as judges and 7 open-source language models as evaluatees. We find that inconsistency rates decrease monotonically (78.75%→46.85%→32.86%) as judge size increases, but the source of inconsistency shifts from random noise to position bias. We also show that majority-vote ensembles (58.63%) perform worse than a single high-quality judge (32.86%), while an abstain-based ensemble resolves this issue (24.70%). Furthermore, selecting the top 40 discriminative questions (tinyMT-Bench) fully preserves model rankings (ρ=1.000) while reducing evaluation cost by 50%. Based on these findings, we propose three practical guidelines for open-source LLM-as-a-Judge.

**Keywords**: LLM-as-a-Judge, position bias, ensemble evaluation, MT-Bench, open-source LLM

---

## 1. 서론

대형 언어 모델(Large Language Model, LLM)의 성능을 평가하는 것은 모델 개발 및 선택에 있어 핵심적인 과제이다. 전통적인 인간 평가는 높은 비용과 긴 소요 시간으로 인해 확장성에 한계가 있으며, 객관식 벤치마크는 창의적 글쓰기나 추론과 같은 개방형 태스크를 충분히 평가하기 어렵다. 이러한 배경에서 LLM 자체를 평가자로 활용하는 LLM-as-a-Judge 방식이 주목받고 있다 [1].

LLM-as-a-Judge는 GPT-4와 같은 상용 모델을 평가자로 사용할 때 높은 인간 일치율을 보이는 것으로 알려져 있다 [1]. 그러나 상용 API의 비용 및 접근성 제한으로 인해 오픈소스 모델을 평가자로 활용하고자 하는 수요가 증가하고 있다. 문제는 오픈소스 평가자의 신뢰도가 충분히 검증되지 않았다는 점이다. 기존 연구들은 주로 위치 편향(position bias) [2] 또는 전반적인 불일치 측정 [3]에 집중하였으나, 평가자 크기 변화에 따른 불일치 원인의 전환, 앙상블 설계의 영향, 최소 평가 문항 수 등을 통합적으로 분석한 연구는 부족하다.

본 논문은 다음 네 가지 연구 질문에 답한다.

- **RQ1**: 오픈소스 평가자의 크기가 커질수록 pairwise 불일치율은 어떻게 변화하는가?
- **RQ2**: 불일치의 원인은 무작위 노이즈인가, 위치 편향인가? 평가자 크기에 따라 어떻게 달라지는가?
- **RQ3**: 소형 평가자를 앙상블로 결합하면 대형 단일 평가자보다 신뢰도가 높아지는가?
- **RQ4**: 변별도 기반 문항 선택으로 평가 비용을 절감하면서 모델 서열을 보존할 수 있는가?

이를 위해 MT-Bench 80문항을 사용하여 Qwen2.5-7B/14B/32B를 평가자로, 7종의 오픈소스 모델을 피평가자로 설정한 실험을 수행하였다. 본 논문의 구성은 다음과 같다. 2절에서 관련 연구를 소개하고, 3절에서 실험 설계를 설명한다. 4절에서 네 가지 연구 질문에 대한 실험 결과를 제시하고, 5절에서 결론과 실용적 가이드라인을 제시한다.

---

## 2. 관련 연구

**LLM-as-a-Judge.** Zheng et al. [1]은 MT-Bench와 Chatbot Arena를 통해 GPT-4를 평가자로 활용하는 LLM-as-a-Judge 방식을 제안하였다. GPT-4 평가자는 인간 평가자와 80% 이상의 일치율을 보였으며, 이후 LLM-as-a-Judge는 다양한 LLM 평가 파이프라인에서 표준적인 방법으로 자리잡았다 [4].

**신뢰도 및 편향 분석.** Shi et al. [2]는 15개 LLM 평가자를 대상으로 위치 편향을 체계적으로 분석하여, 평가자가 답변의 내용보다 제시 순서에 영향을 받음을 보였다. Park et al. [3]은 AB/BA 양방향 평가를 통한 불일치율 측정 프레임워크를 제안하고, 3B~235B 범위의 모델에서 불일치율이 25.3%~76.2% 범위임을 보고하였다. 그러나 이들 연구는 평가자 크기 증가에 따른 불일치 원인의 질적 전환을 분석하지 않았으며, 앙상블 설계의 효과나 최소 평가 문항 수에 대한 분석도 수행하지 않았다. 본 논문은 이 공백을 채운다.

---

## 3. 실험 설계

### 3.1 실험 환경

본 연구는 MT-Bench [1]의 80개 문항(8개 카테고리 × 10문항, 2턴)을 사용한다. 피평가 모델은 7종의 오픈소스 모델로 구성하였다: Llama-3.1-8B-Instruct, SOLAR-10.7B-Instruct-v1.0, Gemma-2-9B-it, Yi-1.5-9B-Chat, Zephyr-7B-beta, Mistral-7B-Instruct-v0.3, Phi-3.5-mini-Instruct. 평가자 모델은 Qwen2.5-7B/14B/32B-Instruct를 사용하였다. vLLM (v0.6.6) 서버를 통해 NVIDIA A100 GPU에서 로컬 실행하였으며, 답변 생성 시 temperature=0.7, 평가 시 temperature=0.0(greedy)을 적용하였다.

### 3.2 평가 방식

**Single-grade**: 각 모델의 답변을 1~10점으로 채점하며, Turn 1과 Turn 2의 평균을 모델 점수로 사용한다 (전체 160턴).

**Pairwise**: 두 모델을 AB 순서와 BA 순서로 모두 비교한다. 두 순서에서 판정이 일치할 때만 winner를 선언하며, 불일치하면 "inconsistent"로 처리하는 보수적 판정(conservative verdict) [1]을 채택한다. 전체 비교 쌍은 7C₂ × 80 = 1,680쌍이다.

### 3.3 주요 지표

- **불일치율(Inconsistency Rate)**: AB/BA 판정이 다른 쌍의 비율
- **First-position 승률**: 불일치 쌍 중 첫 번째 제시 모델이 승리한 비율 (= 위치 편향 강도)
- **Spearman ρ**: 두 평가자 간 모델 서열 순위 상관계수 (95% Bootstrap CI, n=10,000)

### 3.4 앙상블 설계 2종

- **다수결(majority) 방식**: inconsistent를 하나의 표로 취급, 3개 판정 중 2개 이상 일치 시 winner 선언
- **기권(abstain) 방식**: inconsistent를 기권으로 처리. 결정적 표(A 또는 B)가 존재하고 서로 충돌하지 않을 때만 winner 선언

---

## 4. 실험 결과

### 4.1 평가자 크기 스케일링과 불일치율 (RQ1)

표 1은 Qwen2.5 평가자 크기별 전체 및 카테고리별 불일치율을 보여준다. 전체 불일치율은 7B(78.75%) → 14B(46.85%) → 32B(32.86%)로 평가자 크기가 증가함에 따라 단조 감소하였다. 이는 대형 평가자가 동일 문항에 대해 AB/BA 순서와 무관하게 일관된 판정을 내릴 가능성이 높음을 의미한다.

**표 1.** Qwen2.5 평가자 크기별 카테고리별 불일치율

| 카테고리 | 7B | 14B | 32B |
|--------|------|------|------|
| Writing | 86.19% | 51.90% | 40.95% |
| Roleplay | 54.76% | 45.71% | 25.71% |
| Extraction | 62.86% | 42.38% | 39.05% |
| Reasoning | 75.24% | 47.62% | 30.48% |
| Math | 75.71% | 34.76% | **27.14%** |
| Coding | 83.81% | 30.95% | **26.67%** |
| STEM | 95.24% | 49.52% | 39.05% |
| Humanities | 96.19% | 71.90% | 33.81% |
| **전체** | **78.75%** | **46.85%** | **32.86%** |

카테고리별로는 Math(32B 기준 27.14%)와 Coding(26.67%)이 가장 낮은 불일치율을 보인 반면, Writing(40.95%)과 Extraction(39.05%)은 상대적으로 높았다. 정오(正誤) 기준이 명확한 카테고리에서 평가자가 더 일관된 판정을 내림을 시사한다.

Cross-judge Spearman ρ 분석 결과(표 2), 평가자 크기가 다르더라도 모델 서열에 대한 판단은 유사함(ρ≥0.75)을 확인하였다. 32B judge 기준 모델 서열은 Gemma-2-9B-it(8.09점) > Phi-3.5-mini-Instruct(8.06점) > Yi-1.5-9B-Chat(7.79점) > Llama-3.1-8B-Instruct(7.71점) > Mistral-7B-Instruct(7.09점) > SOLAR-10.7B-Instruct(7.02점) > Zephyr-7B-beta(6.62점) 순이었다.

**표 2.** Cross-judge Spearman ρ (95% Bootstrap CI, n=10,000)

| 비교 쌍 | ρ | 95% CI |
|--------|-----|--------|
| 7B–14B | 0.821 | [0.643, 0.964] |
| 7B–32B | 0.786 | [0.643, 0.964] |
| 14B–32B | 0.750 | [0.607, 0.964] |

> **그림 1.** Qwen2.5 평가자 크기별 불일치율 (전체 및 8개 카테고리)
> `figures/fig4_judge_scaling.png`

---

### 4.2 불일치 원인의 전환: 노이즈에서 위치 편향으로 (RQ2)

불일치율의 감소만으로는 신뢰도 향상을 단정할 수 없다. 불일치의 원인을 분석하기 위해 불일치 쌍 내 first-position 승률을 측정하였다 (표 3). First-position 승률이 50%에 가까울수록 무작위 노이즈, 100%에 가까울수록 체계적 위치 편향을 의미한다.

**표 3.** 평가자 크기별 불일치율 및 first-position 승률

| Judge | 불일치율 | First-pos 승률 | 해석 |
|-------|---------|---------------|------|
| 7B | 78.75% | 84.2% | 노이즈 + 약한 편향 |
| 14B | 46.85% | 93.5% | 편향 주도 |
| 32B | 32.86% | **94.9%** | 편향 지배 |

First-position 승률은 7B(84.2%) → 14B(93.5%) → 32B(94.9%)로 평가자 크기가 커질수록 오히려 증가하였다. 이는 다음을 의미한다.

- **7B**: 불일치율이 높지만 first-position 승률이 84.2%로 비교적 낮음 → 불일치의 상당 부분이 무작위 노이즈
- **32B**: 불일치율은 낮아졌지만 first-position 승률이 94.9% → 남은 불일치의 원인이 거의 모두 위치 편향

즉, **평가자 크기가 증가하면 불일치율은 감소하지만, 불일치의 원인이 무작위 노이즈에서 체계적인 위치 편향으로 전환**된다. 대형 평가자가 더 신뢰할 수 있다는 단순한 결론은 위험하다.

카테고리별로는 Math(32B 기준 80.7%)가 가장 낮은 first-position 승률을 보였다. 수학 문제는 정오 기준이 명확하여 답변의 내용이 위치 효과를 부분적으로 억제하기 때문으로 해석된다. 반면 STEM(32B 기준 100.0%)은 불일치 쌍 전체가 위치 편향으로 설명되었다.

> **그림 2.** 평가자 크기별 불일치율(좌) 및 first-position 승률(우)
> `figures/fig11_position_bias.png`

---

### 4.3 앙상블 평가자 설계 비교 (RQ3)

소형 평가자 여러 개를 앙상블하면 대형 단일 평가자보다 신뢰도가 높아질 수 있을까? Qwen2.5-7B+14B+32B 다수결 앙상블과 기권 방식 앙상블을 단일 32B와 비교하였다 (표 4).

**표 4.** 평가 방식별 전체 불일치율

| 평가 방식 | 불일치율 |
|----------|---------|
| 단일 7B | 78.75% |
| 단일 14B | 46.85% |
| 단일 32B | 32.86% |
| 앙상블 다수결 (7B+14B+32B) | 58.63% |
| **앙상블 기권 (7B+14B+32B)** | **24.70%** |

다수결 앙상블(58.63%)은 단일 32B(32.86%)보다 오히려 악화되었다. 이는 7B 평가자의 높은 inconsistency율(78.75%)로 인해 "inconsistent" 표가 다수를 차지하며 앙상블 결과를 오염시키기 때문이다. 다수결 방식에서 inconsistent가 3표 중 2표 이상을 차지하면 결과가 항상 inconsistent로 수렴하는 구조적 문제가 있다.

기권 방식 앙상블(24.70%)은 단일 32B(32.86%)보다 낮은 불일치율을 달성하였다. 기권 방식에서는 1,680쌍 중 604쌍(36%)이 inconsistent에서 winner로 전환되었으며, 34쌍(2%)만이 winner에서 inconsistent로 변경되었다. 기권 방식의 핵심은 품질 낮은 평가자의 불확실한 판정을 집계에서 제외함으로써 결정적 판정의 신뢰도를 높이는 것이다.

> **그림 3.** 평가 방식별 전체 및 카테고리별 불일치율 비교
> `figures/fig13_ensemble_v2.png`

---

### 4.4 tinyMT-Bench: 변별도 기반 문항 최소화 (RQ4)

평가 비용 절감을 위해 80개 전체 문항 중 일부만 사용할 때의 모델 서열 보존 가능성을 분석하였다. 문항 변별도는 7개 모델 점수의 표준편차로 정의하였으며, 변별도 상위 N개 선택(TopDisc-N)과 무작위 선택을 비교하였다.

표 5와 그림 4에서 확인할 수 있듯, 무작위 선택의 경우 60문항 이상에서 Spearman ρ≥0.95가 안정적으로 달성되며, 10문항에서는 최솟값 ρ=0.32로 불안정하다. 반면 변별도 기반 선택은 **40문항(TopDisc-40)에서 ρ=1.000을 달성**하여 전체 80문항과 완전히 동일한 모델 서열을 보존하면서 평가 비용을 50% 절감하였다. TopDisc-25는 ρ=0.964를 달성하여 69% 절감이 가능하다.

**표 5.** 문항 수 N별 Spearman ρ (무작위 vs. 변별도 기반)

| N (문항 수) | 무작위 평균 ρ | 무작위 최솟값 | TopDisc ρ | 비용 절감 |
|------------|------------|------------|----------|---------|
| 10 | 0.866 | 0.321 | 0.929 | 87.5% |
| 25 | 0.941 | 0.750 | **0.964** | 68.8% |
| 40 | 0.959 | 0.821 | **1.000** | 50.0% |
| 60 | 0.972 | 0.893 | 1.000 | 25.0% |
| 80 | 1.000 | 1.000 | 1.000 | 0% |

변별도 상위 40문항을 분석하면, Math(10문항 중 7문항), Coding(10문항 중 6문항), Reasoning(10문항 중 6문항)에서 선택 비율이 높았으며, 이는 3.1절의 카테고리별 불일치율 결과와 일관된다. 단, 본 결과는 실험에 사용된 7개 모델을 기준으로 선택된 문항이며, 다른 모델 집합에 대한 일반화 검증은 향후 과제로 남긴다.

> **그림 4.** 문항 수 N별 Spearman ρ (무작위 vs. 변별도 기반 선택)
> `figures/fig7_qsize_sensitivity.png`

---

## 5. 결론

본 논문은 오픈소스 LLM-as-a-Judge의 신뢰도를 판사 크기 스케일링, 위치 편향 전이, 앙상블 설계, 비용 효율적 평가의 네 측면에서 분석하였다. 실험 결과를 바탕으로 다음 세 가지 실용적 가이드라인을 제안한다.

**가이드라인 1 — 평가자 크기 선택.** 오픈소스 평가자는 32B 이상 사용을 권장한다. 단, 평가자 크기가 커질수록 불일치 원인이 위치 편향으로 집중되므로, 불일치율 감소가 신뢰도 향상을 의미하지 않음에 주의해야 한다.

**가이드라인 2 — 앙상블 설계.** 앙상블을 사용할 경우 다수결보다 기권 방식을 채택한다. inconsistent 판정을 기권으로 처리하면 단일 최고 품질 평가자보다 낮은 불일치율(24.70% vs. 32.86%)을 달성할 수 있다.

**가이드라인 3 — 비용 절감.** 평가 비용 절감이 필요한 경우 변별도 상위 40문항(tinyMT-Bench)을 사용하면 전체 80문항 대비 순위를 완전히 보존하면서 비용을 50% 절감할 수 있다.

**한계점.** 본 연구는 단일 judge 패밀리(Qwen2.5)만을 사용하였으므로 결과가 특정 아키텍처에 의존할 가능성이 있다. 또한 7개 피평가 모델만으로 Spearman ρ를 계산하여 신뢰구간이 넓다(95% CI 하한 ≥0.6). tinyMT-Bench는 동일 모델 집합 내 검증 결과이며, 외부 모델에 대한 일반화는 추가 연구가 필요하다.

**향후 연구.** 위 한계를 보완하기 위해 InternLM2.5(7B/20B)를 평가자로 추가하여 교차 아키텍처 검증을 수행하고, GPT-4o-mini와의 비교를 통해 오픈소스 대비 상용 API judge의 신뢰도를 분석할 계획이다. 아울러 한국어로 번역된 MT-Bench를 통해 한국어 LLM 평가에서의 적용 가능성을 검토한다.

---

## 참고문헌

[1] L. Zheng, W.-L. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Li, D. Li, E. Xing, H. Zhang, J. E. Gonzalez, I. Stoica, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," in *Proc. NeurIPS*, 2023.

[2] W. Shi, J. Gao, X. Gao, R. Pan, "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge," in *Proc. IJCNLP*, 2025. arXiv:2406.07791.

[3] Anonymous, "Are We on the Right Way to Assessing LLM-as-a-Judge?" arXiv:2512.16041, 2024.

[4] T. Vu, M. Ravaut, A. Mukherjee, H. Zhao, A. Xu, B. T. Hoang, S. Chen, S. Joty, "A Survey on LLM-as-a-Judge," arXiv:2411.15594, 2024.

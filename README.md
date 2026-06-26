# Korean MT-Bench: LLM-as-a-Judge 신뢰도 한·영 비교 연구

> **KCI 등재 학술지 투고 목표**  
> Base paper: Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023 ([arXiv:2306.05685](https://arxiv.org/abs/2306.05685))

---

## 핵심 발견

**1. 한국어에서 범용 영어 모델 점수가 급락한다.**  
Qwen-32B 기준 Phi-3.5-mini −2.64, Mistral-7B −2.41 (bootstrap 95% CI 모두 0 제외, p<0.001). 반면 한국어 특화 모델은 EXAONE −0.22, EEVE −0.39로 하락폭이 작다.

**2. Judge 크기가 클수록 inconsistency가 유의하게 줄어든다.**  
EN에서 7B→32B: 79.2%→31.0% (permutation test p<0.001). KO에서도 동일 패턴(44.5%→20.2%). 소형 judge는 신뢰하기 어렵다.

**3. Reference-guided 채점은 standard보다 점수가 낮다.**  
math/coding/reasoning 문항에 한정된 ref 채점의 평균이 non-ref보다 낮음 (EN Qwen-32B −2.49, p<0.001). 문항 난이도의 차이를 반영한다.

**4. 7B judge는 한국어에서 parse failure가 급증한다.**  
KO single_grade_ref 33.3% — EN에서는 0%. 소형 judge의 한국어 포맷 준수 능력이 언어에 따라 크게 다르다.

---

## 연구 개요

MT-Bench는 LLM 능력을 8개 카테고리, 80문항으로 평가하는 대표적 벤치마크다. 원 논문(Zheng et al. 2023)은 영어 환경에서 GPT-4 judge의 높은 신뢰도를 보였으나, **비영어권 언어로 동일 파이프라인을 적용했을 때 judge 신뢰도가 유지되는지**는 검증되지 않았다.

본 연구는 MT-Bench 80문항을 한국어로 번역하고, Qwen2.5 패밀리(7B/14B/32B)를 judge로 사용해 영어 baseline과 동일 조건에서 실험을 수행한다. Judge 크기 scaling, 언어별 inconsistency/position bias, parse failure rate를 정량 비교한다.

---

## 연구 진행 상황

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 0** | 한국어 번역 + 역번역 validity 검증 | ✅ 완료 |
| **Phase 1** | 한국어 파이프라인 (답변 생성 + Qwen judge) | ✅ 완료 |
| **Phase 1b** | EXAONE-3.5-32B cross-family judge (EN + KO) | 🔄 실행 중 |
| **Phase 2** | 영어-한국어 비교 분석 | ⏳ Phase 1b 완료 후 |
| **Phase 3** | KCI 논문 작성 및 투고 | ⏳ Phase 2 완료 후 |

---

## 실험 설계

### Eval 모델 (6종)

| 모델 | 파라미터 | 특징 |
|------|---------|------|
| EXAONE-3.5-7.8B-Instruct | 7.8B | LG AI, 한국어 특화 |
| EEVE-Korean-Instruct-10.8B | 10.8B | SOLAR 기반 한국어 fine-tune |
| gemma-2-9b-it | 9B | Google, 다국어 |
| Llama-3.1-8B-Instruct | 8B | Meta, 범용 영어 |
| Mistral-7B-Instruct-v0.3 | 7B | Mistral AI, 범용 영어 |
| Phi-3.5-mini-Instruct | 3.8B | Microsoft, 범용 영어 |

### Judge 모델

| Judge | 종류 | 상태 |
|-------|------|------|
| Qwen2.5-7B-Instruct | Same-family scaling | ✅ 완료 |
| Qwen2.5-14B-Instruct | Same-family scaling | ✅ 완료 |
| Qwen2.5-32B-Instruct-AWQ | Same-family scaling | ✅ 완료 |
| EXAONE-3.5-32B-Instruct-AWQ | Cross-family | 🔄 실행 중 |
| GPT-4o-mini | Gold standard | ⏳ 미실행 |

Judge 유형은 두 가지다. **Single-grade**: 각 모델 답변을 독립적으로 채점(1~10점). **Pairwise**: 두 모델 답변을 AB, BA 순으로 제시하고 승자를 판정, AB/BA 결과가 다르면 `inconsistent`로 처리. **Reference-guided**: math/coding/reasoning 29문항에 참조 정답을 제공한 single-grade.

---

## EN-KO 점수 비교 (Qwen-32B 기준)

> Bootstrap 95% CI는 문항 단위 리샘플링(n=10,000) 기반. CI가 0을 포함하지 않으면 통계적으로 유의.

| 모델 | EN | KO | 차이 | 95% CI | 유의 |
|------|---:|---:|-----:|--------|------|
| EXAONE-3.5-7.8B | 8.3208 | 8.1000 | −0.22 | [−0.45, −0.03] | yes |
| EEVE-10.8B | 6.7188 | 6.3250 | −0.39 | [−0.68, −0.11] | yes |
| gemma-2-9b | 8.0943 | 7.2812 | −0.82 | [−1.10, −0.54] | yes |
| Llama-3.1-8B | 7.7125 | 5.7170 | −1.99 | [−2.35, −1.62] | yes |
| Mistral-7B | 7.0875 | 4.6813 | −2.41 | [−2.79, −2.02] | yes |
| Phi-3.5-mini | 8.0625 | 5.4188 | −2.64 | [−3.01, −2.28] | yes |

한국어 특화 모델(EXAONE, EEVE)은 EN→KO 하락폭이 0.4 이내로 작다. 반면 범용 영어 모델은 1.99~2.64점 급락한다. gemma-2-9b는 영어 모델임에도 −0.82로 상대적으로 낮은 하락폭을 보이는데, 다국어 학습 비중이 높기 때문으로 추정된다.

### EN 전체 점수 (Single-Grade)

> 80문항 × 2턴 = 160 samples 기준, parse failure(-1.0) 제외 평균

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B |
|------|--------:|---------:|---------:|
| EXAONE-3.5-7.8B | **8.3812** | **8.5500** | **8.3208** |
| Phi-3.5-mini | 8.0437 | 8.0875 | 8.0625 |
| gemma-2-9b | 7.8688 | 8.0312 | 8.0943 |
| Llama-3.1-8B | 7.8937 | 8.1687 | 7.7125 |
| Mistral-7B | 7.4500 | 7.4875 | 7.0875 |
| EEVE-10.8B | 7.1937 | 6.8875 | 6.7188 |

3개 judge 모두 EXAONE 1위, EEVE 최하위로 일관된다. Judge 크기가 달라져도 1위·최하위 순위는 변하지 않는다.

### KO 전체 점수 (Single-Grade)

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B |
|------|--------:|---------:|---------:|
| EXAONE-3.5-7.8B | **7.7296** | **8.0469** | **8.1000** |
| gemma-2-9b | 6.9383 | 7.2704 | 7.2812 |
| EEVE-10.8B | 6.6643 | 6.3906 | 6.3250 |
| Phi-3.5-mini | 6.4178 | 5.6352 | 5.4188 |
| Llama-3.1-8B | 6.3523 | 5.7987 | 5.7170 |
| Mistral-7B | 5.4200 | 5.0506 | 4.6813 |

EN 대비 순위 변동이 두드러진다. EN에서 2위였던 Phi-3.5-mini가 Qwen-32B 기준 4~5위로 급락하고, gemma-2-9b가 EN 4위에서 KO 2위로 부상한다. EXAONE 1위는 EN·KO 모두 유지된다.

---

## Judge 신뢰도 — Inconsistency & Position Bias

> **Inconsistency**: AB/BA 판정 불일치율 (`winner == "inconsistent"`)  
> **1st-pos bias**: `winner_ab=A AND winner_ba=A` — 항상 첫 번째 위치 모델 선호  
>   (AB에서 A=첫째=model_a, BA에서 A=첫째=model_b → 둘 다 첫째 위치 선호 → inconsistent)  
> 괄호 안은 해당 케이스 수 / bootstrap 95% CI

### Inconsistency & Position Bias (EN)

| Judge | 총 pair | Inconsistency | 95% CI | 1st-pos bias |
|-------|--------:|--------------:|--------|-------------:|
| Qwen-7B  | 1,200 | **79.2%** | [76.9%, 81.6%] | **52.5%** (630) |
| Qwen-14B | 1,200 | 45.1% | [42.3%, 47.8%] | 35.5% (426) |
| Qwen-32B | 1,200 | 31.0% | [28.3%, 33.6%] | 22.3% (267) |

7B→14B 차이: Δ=34.1%p (p<0.001 ***), 14B→32B 차이: Δ=14.2%p (p<0.001 ***)

### Inconsistency & Position Bias (KO)

| Judge | 총 pair | Inconsistency | 95% CI | 1st-pos bias |
|-------|--------:|--------------:|--------|-------------:|
| Qwen-7B  | 1,200 | 44.5% | [41.8%, 47.3%] | 40.0% (479) |
| Qwen-14B | 1,200 | 23.0% | [20.7%, 25.4%] | 6.3% (76) |
| Qwen-32B | 1,200 | 20.2% | [18.0%, 22.5%] | 14.3% (171) |

7B→14B 차이: Δ=21.5%p (p<0.001 ***), 14B→32B 차이: Δ=2.8%p (p=0.022 *)

Inconsistency는 judge가 클수록 감소하며, 이 패턴은 EN과 KO 모두에서 통계적으로 유의하다(모두 p<0.001). EN vs KO 비교(같은 judge): Qwen-7B Δ=34.8%p, 14B Δ=22.1%p, 32B Δ=10.7%p — 모두 p<0.001.

1st-pos bias는 두 언어에서 다른 양상을 보인다. **EN**에서는 judge가 작을수록 1st-pos bias가 높고(7B: 52.5%), 모델 크기가 커질수록 감소한다(32B: 22.3%). **KO**에서는 14B가 6.3%로 가장 낮고, 7B(40.0%)→32B(14.3%)는 더 높다.

### 이상치처럼 보이는 값들과 해석

**① EN Qwen-7B: Inconsistency 79.2%, 1st-pos bias 52.5%**

수치가 비정상적으로 높아 보이지만, 7B judge의 판정 능력 한계로 인해 발생한 구조적 결과다. 전체 1,200 pair 중 불일치가 951건(79.2%)으로, judge가 사실상 랜덤에 가까운 판정을 한다. 랜덤 판정에서 1st-pos bias가 높게 나오는 이유는, 판정이 불안정할수록 AB와 BA에서 각각 독립적으로 `A`(첫 번째 위치)를 선택할 확률이 높아지기 때문이다. 이 judge의 값은 "1st-pos 경향이 강하다"가 아니라 "판정 자체가 신뢰할 수 없다"는 의미로 해석해야 한다.

**② KO Qwen-14B: 1st-pos bias 6.3% (EN 동급 35.5%의 1/5 수준)**

이상치처럼 보이지만, 실제로는 KO에서 모델 간 성능 차이가 명확하여 judge가 위치가 아닌 품질로 판정한 결과다. 전체 1,200 pair 중 일관된 판정(consistent_A + consistent_B)이 918건(76.5%)으로, 이 중 560건(46.7%)이 model_a 일관 승리다. 모델 쌍별로 보면 EXAONE, gemma-2-9b가 Mistral, Phi, Llama를 한국어에서 일관되게 이기는 구도가 형성돼 있다. position bias가 낮다는 것은 이 judge가 KO에서 모델 품질을 잘 구별한다는 긍정적 신호다.

**③ KO Qwen-14B: 2nd-pos bias(9.2%) > 1st-pos bias(6.3%)**

순서가 역전된 것처럼 보이나, 절대 건수로는 76건 vs 111건이고, 전체 1,200건 대비 3%p 차이다. 일관된 판정이 76.5%인 상황에서 이 차이는 통계적 노이즈 범위로 볼 수 있다. EN 14B의 1st-pos(35.5%) vs 2nd-pos(27.6%) 패턴과 비교하면 KO에서는 방향성 자체가 약하다.

**④ EN Qwen-32B: Consistency 69.0% — 논문 GPT-4(65.0%)보다 높음**

직접 비교는 불가하다. 논문은 GPT-3.5로 생성한 **유사한 답변 쌍**(의도적으로 구분하기 어렵게 설계)을 사용한 반면, 우리는 서로 다른 6개 모델의 실제 답변을 비교한다. 모델 간 품질 차이가 클수록 일관된 판정이 나오기 쉬우므로, 우리 실험 조건에서 consistency가 높은 것은 자연스럽다.

---

## Reference-guided vs Standard 채점 차이

> Reference-guided(single_grade_ref): math/reasoning/coding 29문항에 참조 정답 제공, turn2만 채점  
> Standard(single_grade): 참조 정답 없이 전체 80문항 채점  
> diff = ref_mean − nonref_mean (turn2 기준)

| 언어 | Judge | Non-ref | Ref | 차이 | p | 유의 |
|------|-------|--------:|----:|-----:|---|------|
| EN | Qwen-7B | 7.84 | 6.72 | −1.12 | <0.001 | *** |
| EN | Qwen-14B | 7.82 | 6.00 | −1.82 | <0.001 | *** |
| EN | Qwen-32B | 7.67 | 5.18 | −2.49 | <0.001 | *** |
| KO | Qwen-7B | 6.92 | 6.51 | −0.41 | 0.025 | * |
| KO | Qwen-14B | 6.29 | 4.68 | −1.61 | <0.001 | *** |
| KO | Qwen-32B | 6.30 | 4.87 | −1.44 | <0.001 | *** |

Reference-guided 채점이 standard보다 점수가 유의하게 낮다. 이는 ref 문항이 math/coding/reasoning — 즉 객관적 정답이 있고 채점이 까다로운 문항 — 에 한정되기 때문이다. Reference를 제공했을 때 judge가 정답 기준을 더 엄격하게 적용한다는 해석과, ref 문항 자체가 난이도가 높다는 두 가지 원인이 복합적으로 작용한다. KO Qwen-7B에서 차이가 가장 작은(−0.41, p=0.025) 것은, 7B judge의 한국어 ref 파싱 실패(33.3%)로 유효 샘플이 극도로 감소한 결과다.

---

## Parse Failure

Parse failure = judge가 `[[N]]` 형식 점수를 출력하지 않아 집계에서 제외된 경우(−1.0 처리).

### EN Parse Failure

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade_ref | 5 | 174 | 2.9% |
| Qwen-32B | single_grade | 2 | 960 | 0.2% |
| Qwen-32B | pairwise | 2 | 2,400 | 0.1% |

영어에서는 parse failure가 전반적으로 낮다. Qwen-7B의 reference-guided 채점에서 2.9%로 가장 높고, 나머지는 0.3% 미만이다.

### KO Parse Failure

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade | 42 | 960 | **4.4%** |
| Qwen-7B | single_grade_ref | 58 | 174 | **33.3%** |
| Qwen-7B | pairwise | 3 | 2,400 | 0.1% |
| Qwen-14B | single_grade | 5 | 960 | 0.5% |
| Qwen-14B | single_grade_ref | 3 | 174 | 1.7% |
| Qwen-32B | single_grade | 1 | 960 | 0.1% |
| Qwen-32B | pairwise | 1 | 2,400 | 0.0% |

Qwen-7B의 KO single_grade_ref 33.3%는 이 연구의 핵심 발견 중 하나다. 한국어 프롬프트에서 소형 judge가 포맷 지시를 따르지 못하거나 중국어로 응답하는 사례가 급증한다. EN 동일 설정(2.9%)과 비교하면 약 11배 차이다. Qwen-32B는 KO에서도 0.1% 이하로 안정적이다.

---

## Base Paper 비교 (Zheng et al. 2023)

| 지표 | 원 논문 (GPT-4 judge) | 본 연구 (EN Qwen-32B) |
|------|---------------------:|--------------------:|
| Inconsistency (1 − consistency) | **35.0%** (Table 2) | 31.0% [28.3%, 33.6%] |
| 1st-position bias | **30.0%** (Table 2) | 22.3% |
| Judge-model agreement (vs human, S2) | **85%** (non-tie) | — (GPT-4o-mini Phase 2 예정) |

원 논문은 GPT-4 judge로 **유사 성능 GPT-3.5 쌍**을 평가한 반면, 본 연구는 Qwen-32B로 실제 6개 eval 모델 전체 pair를 평가한다. 평가 쌍의 성능 차이가 클수록 inconsistency가 낮아지는 경향이 있어 수치의 직접 비교는 참고 수준이다. 동일 조건 비교는 GPT-4o-mini judge 실행 후 가능하다.

---

## 프로젝트 구조

```
mt_bench_repro/
├── data/
│   ├── en/
│   │   ├── answers/                      # eval 모델 6개 답변 (git 추적)
│   │   └── results/                      # Qwen judge 집계 CSV
│   └── ko/
│       ├── questions.jsonl               # 한국어 번역 80문항
│       ├── translation_notes.md
│       └── results/                      # KO judge 집계 CSV + 통계 검정 결과
├── scripts/
│   ├── run/a100/
│   │   ├── run_generate_phase3_a100.sh   # EN 답변 생성 (완료)
│   │   ├── run_judge_phase3_a100.sh      # EN Qwen judge (완료)
│   │   ├── run_generate_ko_a100.sh       # KO 답변 생성 (완료)
│   │   ├── run_judge_ko_a100.sh          # KO Qwen judge (완료)
│   │   └── run_judge_exaone32b_a100.sh   # EN+KO EXAONE judge (실행 중)
│   ├── run/local/
│   │   └── run_mock_full.sh
│   ├── analysis/
│   │   ├── analyze_phase3.py             # Judge scaling 분석
│   │   ├── analyze_phase345.py           # Judge 간 비교 통합 분석
│   │   ├── analyze_statistics.py         # Bootstrap CI + Permutation test
│   │   └── analyze_translation_validity.py
│   ├── translate/
│   │   ├── validate_translation.py
│   │   ├── back_translate.py
│   │   └── compare_en_ko.py              # Phase 2: EN vs KO 비교
│   └── tools/
│       ├── generate_figures.py
│       ├── prepare_topdisc_subset.py
│       └── download_dataset.sh
└── src/mtbench_repro/                    # 핵심 Python 패키지
```

---

## 로컬 실행

```bash
git clone <repo> && cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src

# mock 파이프라인 테스트
bash scripts/run/local/run_mock_full.sh

# 통계 분석 (numpy 필요)
python3 scripts/analysis/analyze_statistics.py
# → data/ko/results/results_stat_*.csv

# 번역 validity 검증 (GPT-4o-mini API 키 필요)
python3 scripts/translate/back_translate.py \
    --provider openai --model gpt-4o-mini --api-key $KEY
python3 scripts/analysis/analyze_translation_validity.py \
    --provider openai --model gpt-4o-mini --api-key $KEY
```

---

## 인용

```bibtex
@inproceedings{zheng2023judging,
  title     = {Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena},
  author    = {Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and others},
  booktitle = {Advances in Neural Information Processing Systems},
  year      = {2023}
}
```

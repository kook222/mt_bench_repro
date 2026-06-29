# Korean MT-Bench: Cross-Lingual Reliability and Cross-Family Bias in LLM-as-a-Judge Evaluation

**한국어 제목**: 한국어 MT-Bench: LLM-as-a-Judge의 한·영 신뢰도 및 Cross-Family 편향 분석

> **KCI 등재 학술지 투고 목표**  
> Base paper: Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023 ([arXiv:2306.05685](https://arxiv.org/abs/2306.05685))

---

## 핵심 발견

**1. 한국어에서 범용 영어 모델 점수가 급락한다.**  
Qwen-32B 기준 Phi-3.5-mini −2.64, Mistral-7B −2.41 (bootstrap 95% CI 모두 0 제외, p<0.001). 반면 한국어 특화 모델은 EXAONE −0.22, EEVE −0.39로 하락폭이 작다.

**2. Judge 크기가 클수록 inconsistency가 유의하게 줄어든다.**  
EN에서 7B→32B: 79.3%→30.9% (permutation test p<0.001). KO에서도 동일 패턴(44.5%→20.3%), 단 KO 14B→32B 차이(Δ=2.8%p)는 통계적으로 유의하지 않다(p=0.109). 소형 judge는 신뢰하기 어렵다.

**3. Reference-guided 채점은 standard보다 점수가 낮다.**  
math/coding/reasoning 문항에 한정된 ref 채점의 평균이 non-ref보다 낮음 (EN Qwen-32B −2.49, p<0.001). 문항 난이도의 차이를 반영한다.

**4. 7B judge는 한국어에서 parse failure가 급증한다.**  
KO single_grade_ref 33.3% — EN 동일 설정에서는 2.9%. 소형 judge의 한국어 포맷 준수 능력이 언어에 따라 크게 다르다.

---

## 연구 개요

MT-Bench는 LLM 능력을 8개 카테고리, 80문항으로 평가하는 대표적 벤치마크다. 원 논문(Zheng et al. 2023)은 영어 환경에서 GPT-4 judge의 높은 신뢰도를 보였으나, **비영어권 언어로 동일 파이프라인을 적용했을 때 judge 신뢰도가 유지되는지**는 검증되지 않았다.

본 연구는 MT-Bench 80문항을 한국어로 번역하고, Qwen2.5 패밀리(7B/14B/32B, same-family), EXAONE-3.5-32B(cross-family, 한국어 특화), GPT-4o(cross-family, 상용) 세 judge 군으로 영어 baseline과 동일 조건에서 실험을 수행한다. Judge 크기 scaling, 언어별 inconsistency/position bias, cross-family 편향, parse failure rate를 정량 비교한다.

---

## 연구 진행 상황

| Phase | 논문 섹션 | 내용 | 상태 |
|-------|----------|------|------|
| **Phase 0** | §4 한국어 MT-Bench 구축 | 한국어 번역 + 역번역 validity 검증 (q83·q90·q136 수정) | ✅ 완료 |
| **Phase 1** | §5 실험 설계, §6.1 Judge Scaling, §6.4 Ref, §6.5 Parse | 답변 생성 (6 eval 모델, EN+KO 80문항) + Qwen judge 3종 (7B/14B/32B) | ✅ 완료 |
| **Phase 1b** | §5 실험 설계, §6.3 Cross-family bias, §6.4 Ref, §6.5 Parse | EXAONE-3.5-32B cross-family judge (EN+KO, 한국어 특화) | ✅ 완료 |
| **Phase 1c** | §6.3 Cross-family bias (상용 baseline) | GPT-4o judge (EN+KO, single_grade + pairwise + reference, ~$25) | ⏳ 실행 예정 |
| **Phase 2** | §6.2 EN-KO 비교 분석 | compare_en_ko.py 실행 → Judge scaling 재현, inconsistency/bias 정량 비교 | ⏳ Phase 1c 완료 후 |
| **Phase 3** | §7 Discussion, §8 Conclusion | KCI 논문 작성 및 투고 | ⏳ Phase 2 완료 후 |

---

## Phase 0: 한국어 번역 및 품질 검증

### 번역 과정

MT-Bench 원본 80문항(영어)을 한국어 능숙자 4인(학부생)이 분담하여 수작업으로 번역하였다. 8개 카테고리를 1인당 2개 카테고리씩 균등 배분하였다.

| 담당자 | 카테고리 | 문항 수 |
|--------|----------|--------:|
| 번역자 1 | writing, roleplay | 20 |
| 번역자 2 | reasoning, math | 20 |
| 번역자 3 | coding, extraction | 20 |
| 번역자 4 | stem, humanities | 20 |

번역 원칙:
- 문항의 태스크 타입과 제약 조건(단어 수 제한, 형식, 역할)을 그대로 유지
- 수식·코드블록·고유명사는 번역하지 않고 원문 유지
- 단어 카운팅 과제(q136 등)는 영어 passage를 번역하지 않고 지시문만 한국어로 작성

번역 가이드라인: `data/ko/translation_notes.md`

### 번역 품질 검증 (Back-Translation Validity Check)

수작업 번역의 품질을 정량적으로 검증하기 위해 **back-translation 방식**을 사용하였다. KO 번역이 원본 의미를 잘 보존했다면 역번역(KO→EN)도 원본과 유사해야 한다는 원리를 이용한다.

```
원본 EN ──────────────────────────────────┐
    │ (수작업 번역)                        │ 비교
    ↓                                      │
  KO 번역                                  │
    │ (GPT-4o-mini 역번역, temp=0.0)       │
    ↓                                      │
  역번역 EN ────────────────────────────── ┘
              ↓
    BLEU + LLM 3차원 점수
```

Turn2 역번역 시 Turn1 번역 결과를 컨텍스트로 함께 제공하여 "이전 답변 기반으로..." 같은 참조 표현의 번역 정확도를 높였다.

### 평가 지표

| 지표 | 설명 | 범위 |
|------|------|------|
| `bleu_avg` | 역번역 EN과 원본 EN의 4-gram 단어 겹침 (turn1, turn2 평균) | 0~1 |
| `semantic_preservation` | 핵심 의미와 태스크 의도가 보존됐는가 | 1~5 |
| `difficulty_preservation` | 문제 난이도가 동일하게 유지됐는가 | 1~5 |
| `constraint_preservation` | 글자수 제한, 숫자, 형식, 역할 등 제약 조건 보존 여부 | 1~5 |
| `overall_score` | 종합 점수 | 1~5 |
| `needs_manual_check` | 수동 확인 필요 여부 | True/False |

**점수 산출 방식**

GPT-4o-mini에게 원본 EN 문항과 역번역 EN 문항을 함께 제시하고, 두 텍스트를 비교하여 3개 차원을 각각 1~5점으로 채점하도록 지시한다. 모델은 아래 기준에 따라 JSON으로 점수를 반환한다.

| 점수 | 의미 |
|------|------|
| 5 | 완전히 보존됨 |
| 4 | 표현만 다를 뿐 의미와 제약 조건 유지 |
| 3 | 부분적으로 보존; 모델 응답에 영향을 줄 수 있음 |
| 2 | 중요한 정보 또는 제약 조건이 변경됨 |
| 1 | 원본과 실질적으로 다름 |

각 차원(semantic/difficulty/constraint)과 overall_score는 turn1·turn2를 개별 채점한 뒤 평균을 낸다. temperature=0.0으로 고정하여 재현성을 확보하였다.

**`needs_manual_check = True` 판정 기준** (아래 중 하나라도 해당 시):
- 임의의 차원 점수(semantic/difficulty/constraint)가 3 이하
- 숫자, 형식, 역할, 길이 제한 등 constraint가 변경됨
- 태스크 타입이 바뀐 것으로 판단됨 (예: 교정 태스크 → 생성 태스크)
- 역번역이 지시문을 번역하지 않고 수행함

turn1·turn2 중 하나라도 `needs_manual_check=True`이면 해당 문항 전체가 플래그된다.

**한계**: 역번역(GPT-4o-mini)과 채점(GPT-4o-mini)에 동일 모델을 사용하여 단일 모델 편향이 존재할 수 있다. 이를 보완하기 위해 모델 독립적 지표인 BLEU를 교차 검증 지표로 병행하며, 플래그된 문항을 BLEU–LLM 점수 조합에 따라 아래 네 가지 패턴으로 구분하여 판단한다.

| 패턴 | BLEU | LLM | 해석 | 실제 번역 오류? |
|------|------|-----|------|----------------|
| ① 표현 차이 | 낮음 | 높음 | 역번역 모델이 의미는 보존하되 표현만 바꿈(paraphrase) | 아님 |
| ② 실질적 오류 | 낮음 | 낮음 | 의미·태스크·제약이 변형됨. 원문 대조로 번역 오류 vs 역번역 모델 오류 구분 | 일부(q90·q136) |
| ③ 국소 제약 오류 | 높음 | 낮음 | 전체 문장 구조는 유사하나 핵심 단어 하나가 바뀜. BLEU 단독으로는 탐지 불가 | 일부(q83) |
| ④ 혼합 패턴 | 중간 | 혼합 | turn1은 정상이나 turn2에서 역번역 모델이 후속 질문을 오해함 | 아님 |

### 검증 결과 (카테고리별)

| 카테고리 | n | BLEU | Semantic | Difficulty | Constraint | Overall | ⚠ |
|----------|--:|-----:|---------:|-----------:|-----------:|--------:|--:|
| writing | 10 | 0.202 | 4.25 | 4.80 | 4.35 | 4.15 | 4 |
| roleplay | 10 | 0.223 | 4.25 | 4.95 | 4.90 | 4.25 | 2 |
| reasoning | 10 | 0.335 | 3.80 | 4.70 | 4.20 | 3.75 | 4 |
| math | 10 | 0.303 | 4.15 | 4.85 | 3.95 | 3.95 | 7 |
| coding | 10 | 0.351 | 4.25 | 4.95 | 4.75 | 4.20 | 5 |
| extraction | 10 | 0.231 | 3.70 | 4.70 | 4.10 | 3.65 | 8 |
| stem | 10 | 0.316 | 4.55 | 5.00 | 4.95 | 4.55 | 2 |
| humanities | 10 | 0.357 | 4.55 | 5.00 | 4.90 | 4.50 | 2 |

`⚠` = `needs_manual_check=True` 문항 수. extraction(8건)·math(7건)에서 플래그 빈도가 높고, constraint 점수가 낮은 경향이 있다. 이는 turn2의 후속 질문에서 수치·형식 조건이 미묘하게 변형되는 경향이 원인이다.

전체 80문항 중 34개가 `needs_manual_check=True`로 플래그됐으며, 실제 의미 변형이 확인된 **3개 문항**(q83·q90·q136)을 수정하였다. 나머지 31개는 역번역 모델 오류 또는 표현 차이로 판단하여 원본 번역을 유지하였다(패턴① 6건 + 패턴② 유지 4건 + 패턴③ 유지 1건 + 패턴④ 20건 = 31건). 세부 분류는 아래 패턴 분석을 참조.

### BLEU–LLM 패턴 분석

**패턴 ①: BLEU 낮음 + LLM 높음 (단순 paraphrase)** — 6건

역번역 모델이 의미는 충실히 보존하되 어휘·문장 구조를 달리 표현한 경우다. 4-gram 겹침이 낮아 BLEU는 떨어지지만 GPT-4o-mini 채점자는 의미 동일성을 인식하여 높은 점수(overall ≥ 4.0)를 부여한다. q91·q116·q132·q146·q155·q157에서 확인됐다.

> **예시** q116 (math): 수식 표현이 역번역에서 다르게 서술됨. BLEU=0.00, semantic=4, overall=4. 원문 대조 시 번역 정상.

**패턴 ②: BLEU 낮음 + LLM 낮음 (실질적 의미 변형)** — 총 6건 (유지 4건 + 수정 2건)

| q | category | BLEU avg | Overall avg | 진단 | 조치 |
|---|----------|----------|-------------|------|------|
| q87 | writing | 0.18 | 3.0 | turn2에서 "반복" 과제가 "다시 쓰기"로 바뀜 → 역번역 모델 오류, 원문 대조 시 번역 정상 | 유지 |
| **q90** | writing | 0.03 | 3.0 | 영어 원문에는 의도적 문법 오류가 있으나 KO 번역에는 없음 → 교정 태스크 수행 불가 | **수정**: 의도적 문법 오류 5개 삽입 |
| q104 | reasoning | 0.19 | 2.0 | 형제 관계 모호·숫자 변형 → 역번역 모델 오류, 원문 대조 시 번역 정상 | 유지 |
| q131 | extraction | 0.12 | 3.0 | 핵심 구문 바뀜 → 역번역 모델 오류, 원문 대조 시 번역 정상 | 유지 |
| q134 | extraction | 0.22 | 2.5 | 수치·수익 관계 오류 → 역번역 모델 오류, 원문 대조 시 번역 정상 | 유지 |
| **q136** | extraction | 0.00 | 3.0 | 영어 passage가 한국어로 번역되어 영어 단어 카운팅 과제 수행 불가 | **수정**: 영어 passage 원문 복원, 지시문만 한국어 유지 |

역번역 점수가 낮더라도 원문과 직접 대조하여 번역 오류가 없음을 확인한 q87·q104·q131·q134는 유지하였다. LLM 점수가 낮은 것이 항상 번역 오류를 의미하지 않으며, 역번역 모델 자체의 해석 오류일 수 있음을 보여주는 사례다.

**패턴 ③: BLEU 높음 + LLM 낮음 (국소 제약 조건 변형)** — 2건(turn 기준)

| q | turn | BLEU | Overall | 내용 | 조치 |
|---|------|------|---------|------|------|
| **q83** | turn1 | 0.59 | 2 | "200 words" → "200글자". 문장 구조는 거의 동일하여 BLEU=0.59이지만 단어수/글자수 단위 변형으로 제약 조건이 완전히 바뀜 | **수정**: "200단어 미만으로" 복원 |
| q125 | turn1 | 0.84 | 1 | LCM(최소공배수) 문항을 역번역이 LCA(최소공통조상)로 오인. BLEU=0.84로 거의 완전 일치하나 태스크 의도가 뒤바뀜 → 역번역 모델 오류, 원문 확인 시 번역 정상 | 유지 |

패턴 ③은 **BLEU만으로는 탐지 불가능한 오류 유형**의 존재를 보여준다. 문장 전체 구조가 동일하더라도(BLEU↑) 단 한 단어(words→글자, LCM→LCA)의 의미 변형으로 태스크 전체가 달라질 수 있으며, 이는 LLM 채점자만이 식별할 수 있다. BLEU를 단독 지표로 쓰지 않고 LLM 점수와 교차 검증하는 이유가 바로 여기에 있다.

**패턴 ④: Turn 혼합 패턴 (turn1 정상, turn2 역번역 모델 오류)** — 20건

flagged 31건 유지 중 가장 많은 비율을 차지하는 패턴이다. turn1은 BLEU·LLM 모두 정상이나, turn2에서 역번역 모델이 후속 질문을 잘못 해석하여 낮은 점수를 받는 경우다. `needs_manual_check=True` 판정은 turn 단위로 이루어지기 때문에 turn2 단 하나만 점수가 낮아도 문항 전체가 플래그된다.

대부분 math·extraction 카테고리에서 발생한다. turn2는 turn1 답변을 기반으로 하는 후속 질문 구조이기 때문에, 역번역 모델이 문맥 의존적 표현을 처리하는 과정에서 태스크 의도를 바꾸거나 "이전 문제를 참고하라" 같은 표현을 추가한다. 대표적인 오류 유형은 다음과 같다:
- 수식·부등식 표현을 "구하라" → "기술하라"로 변환 (q117, q118)
- 인물 이름 변형 (q109: "Suresh"→"Thresh")
- 맥락에 없는 "이전 문제 참조" 표현 삽입 (q111, q120)
- 관계사 역할 변환 (q110: "aides"↔"supervising teachers")

원문 turn2를 직접 대조하여 번역 오류가 없음을 확인하고 전체 20건 유지하였다.

### 수정 내역

| q | 카테고리 | 문제 | 조치 |
|---|----------|------|------|
| **q83** | writing | "200 words" → "200글자"로 번역되어 단위 변경 | "200단어 미만으로" 수정 |
| **q90** | writing | 영어 텍스트에는 의도적 문법 오류가 있지만 한국어 번역본에는 오류 없음 → KO 모델이 교정 태스크 수행 불가 | 한국어 텍스트에 조사 오류, 시제 오류, 맞춤법 오류 등 5개 의도적 문법 오류 삽입 |
| **q136** | extraction | 영어 passage("Amazon", "river", "you" 카운팅 과제)를 한국어로 번역하여 영어 단어가 사라짐 | 영어 passage 원문 복원, 지시문만 한국어 유지 |

### 실행 방법

```bash
# 1단계: 역번역 생성
export OPENAI_API_KEY="sk-..."
python3 scripts/translate/back_translate.py \
    --provider openai --model gpt-4o-mini

# 2단계: 3차원 validity 채점
python3 scripts/analysis/analyze_translation_validity.py \
    --provider openai --model gpt-4o-mini

# 또는 한 번에 실행
bash scripts/run/local/run_quality_check_local.sh
```

출력 파일:
- `data/ko/results/results_translation_validity.csv` — 문항별 점수 (turn1/turn2 분리)
- `data/ko/results/results_translation_validity_per_category.csv` — 카테고리별 집계

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
| Qwen2.5-7B-Instruct | Same-family (scaling) | ✅ 완료 |
| Qwen2.5-14B-Instruct | Same-family (scaling) | ✅ 완료 |
| Qwen2.5-32B-Instruct-AWQ | Same-family (scaling) | ✅ 완료 |
| EXAONE-3.5-32B-Instruct-AWQ | Cross-family (한국어 특화) | ✅ 완료 |
| GPT-4o | Cross-family (상용, Phase 1c) | ⏳ 실행 예정 |

Judge 유형별 GPT-4o 실행 범위: single_grade (EN+KO), pairwise (EN+KO), reference-guided (EN+KO) — 총 약 3,700 API 호출, 예상 비용 $25.

Judge 유형은 세 가지다. **Single-grade**: 각 모델 답변을 독립적으로 채점(1~10점). **Pairwise**: 두 모델 답변을 AB, BA 순으로 제시하고 승자를 판정하며 AB/BA 결과가 다르면 `inconsistent`로 처리. **Reference-guided**: math/coding/reasoning 29문항에 한해 참조 정답을 함께 제공하는 single-grade 방식.

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

한국어 특화 모델(EXAONE, EEVE)은 EN→KO 하락폭이 0.4 이내로 작다. 범용 영어 모델(Llama, Mistral, Phi)은 1.99~2.64점 급락한다. 다국어 모델인 gemma-2-9b는 −0.82로 범용 영어 모델보다 하락폭이 작으며, 다국어 사전학습 비중이 높기 때문으로 추정된다.

### EN 전체 점수 (Single-Grade)

> 80문항 × 2턴 = 160 samples 기준, parse failure(-1.0) 제외 평균

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B | EXAONE-32B |
|------|--------:|---------:|---------:|-----------:|
| EXAONE-3.5-7.8B | **8.3812** | **8.5500** | **8.3208** | **8.46** |
| Phi-3.5-mini | 8.0437 | 8.0875 | 8.0625 | 8.15 |
| gemma-2-9b | 7.8688 | 8.0312 | 8.0943 | 8.27 |
| Llama-3.1-8B | 7.8937 | 8.1687 | 7.7125 | 8.16 |
| Mistral-7B | 7.4500 | 7.4875 | 7.0875 | 7.82 |
| EEVE-10.8B | 7.1937 | 6.8875 | 6.7188 | 7.45 |

3개 judge 모두 EXAONE 1위, EEVE 최하위로 일관된다. Judge 크기가 달라져도 1위·최하위 순위는 변하지 않는다.

### KO 전체 점수 (Single-Grade)

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B | EXAONE-32B |
|------|--------:|---------:|---------:|-----------:|
| EXAONE-3.5-7.8B | **7.7296** | **8.0469** | **8.1000** | **8.36** |
| gemma-2-9b | 6.9383 | 7.2704 | 7.2812 | 7.96 |
| EEVE-10.8B | 6.6643 | 6.3906 | 6.3250 | 7.47 |
| Phi-3.5-mini | 6.4178 | 5.6352 | 5.4188 | 7.03 |
| Llama-3.1-8B | 6.3523 | 5.7987 | 5.7170 | 6.97 |
| Mistral-7B | 5.4200 | 5.0506 | 4.6813 | 6.40 |

EN 대비 순위 변동이 두드러진다. EN에서 3위였던 Phi-3.5-mini가 Qwen-32B 기준 KO 5위로 급락하고, gemma-2-9b가 EN 2위에서 KO 2위를 유지하며 범용 영어 모델 중 가장 강인하다. EXAONE 1위는 EN·KO 모두, 그리고 EXAONE-32B judge 기준에서도 유지된다.

**Cross-family judge의 KO 점수 인플레이션**: EXAONE-32B judge는 KO 채점에서 Qwen-32B 대비 전반적으로 높은 점수를 부여한다. 하위 모델일수록 격차가 크며 (Mistral +1.71, Phi +1.61, Llama +1.25), EN에서의 동일 비교(최대 +0.44)보다 훨씬 크다. 한국어 특화 모델인 EXAONE judge가 KO 응답에 더 관대한 기준을 적용하는 cross-family bias 가능성이 있으며, 모델 서열(순위)은 두 judge 모두에서 동일하게 유지된다.

---

## Judge 신뢰도 — Inconsistency & Position Bias

> **Inconsistency**: AB/BA 판정 불일치율 (`winner == "inconsistent"`)  
> **1st-pos bias**: `winner_ab=A AND winner_ba=A` — 항상 첫 번째 위치 모델 선호  
>   (AB에서 A=첫째=model_a, BA에서 A=첫째=model_b → 둘 다 첫째 위치 선호 → inconsistent)  
> 1st-pos bias %는 **전체 pair 중 1st-position을 두 순서 모두에서 선호한 비율**  
> (분자: winner_ab=A AND winner_ba=A 건수 / 분모: total 1,200)  
> 논문 Table 2와 동일한 집계 방식

### Inconsistency & Position Bias (EN)

| Judge | 총 pair | Inconsistency | 95% CI | 1st-pos bias |
|-------|--------:|--------------:|--------|-------------:|
| Qwen-7B  | 1,200 | **79.3%** | [76.9%, 81.6%] | **52.5%** (630) |
| Qwen-14B | 1,200 | 45.1% | [42.3%, 47.8%] | 35.5% (426) |
| Qwen-32B | 1,200 | 30.9% | [28.3%, 33.6%] | 22.2% (267) |
| EXAONE-32B | 1,200 | 42.2% | [39.4%, 45.1%] | 38.1% (457) |

7B→14B 차이: Δ=34.2%p (p<0.001 ***), 14B→32B 차이: Δ=14.2%p (p<0.001 ***)

### Inconsistency & Position Bias (KO)

| Judge | 총 pair | Inconsistency | 95% CI | 1st-pos bias |
|-------|--------:|--------------:|--------|-------------:|
| Qwen-7B  | 1,200 | 44.5% | [41.7%, 47.3%] | **39.9%** (479) |
| Qwen-14B | 1,200 | 23.0% | [20.7%, 25.3%] | 6.3% (76) |
| Qwen-32B | 1,200 | 20.3% | [18.0%, 22.6%] | 14.2% (171) |
| EXAONE-32B | 1,200 | 30.5% | [27.9%, 33.1%] | 26.2% (315) |

Qwen 7B→14B 차이: Δ=21.5%p (p<0.001 ***), 14B→32B 차이: Δ=2.8%p (p=0.109, ns)

Inconsistency는 judge가 클수록 감소하며, 이 패턴은 EN과 KO 모두에서 통계적으로 유의하다(모두 p<0.001). EN vs KO 비교(같은 judge): Qwen-7B Δ=34.8%p, 14B Δ=22.1%p, 32B Δ=10.7%p — 모두 p<0.001.

1st-pos bias(전체 pair 중 두 순서 모두 position 1 선호 비율)는 두 언어에서 다른 양상을 보인다. **EN**에서는 judge가 작을수록 1st-pos bias가 높고(7B: 52.5%), 모델 크기가 커질수록 감소한다(32B: 22.2%). **KO**에서는 7B(39.9%)와 32B(14.2%)가 1st-pos bias를 보이는 반면 14B(6.3%)는 이례적으로 낮다.

### 이상치처럼 보이는 값들과 해석

**① EN Qwen-7B: Inconsistency 79.2%, 1st-pos bias 52.5% (전체 1,200건 중 630건)**

수치가 비정상적으로 높아 보이지만, 7B judge의 판정 능력 한계로 인해 발생한 구조적 결과다. 전체 1,200 pair 중 불일치가 951건(79.2%)으로, judge가 사실상 랜덤에 가까운 판정을 한다. 랜덤 판정에서 1st-pos bias가 높게 나오는 이유는, 판정이 불안정할수록 AB와 BA에서 각각 독립적으로 `A`(첫 번째 위치)를 선택할 확률이 높아지기 때문이다. 이 judge의 값은 "1st-pos 경향이 강하다"가 아니라 "판정 자체가 신뢰할 수 없다"는 의미로 해석해야 한다.

**② KO Qwen-14B: 1st-pos bias 6.3% (EN 동급 35.5%의 1/5 수준)**

이상치처럼 보이지만, 실제로는 KO에서 모델 간 성능 차이가 명확하여 judge가 위치가 아닌 품질로 판정한 결과다. 전체 1,200 pair 중 일관된 판정(consistent_A + consistent_B)이 924건(77.0%)으로, 이 중 560건(46.7%)이 model_a 일관 승리다. 모델 쌍별로 보면 EXAONE, gemma-2-9b가 Mistral, Phi, Llama를 한국어에서 일관되게 이기는 구도가 형성돼 있다. position bias가 낮다는 것은 이 judge가 KO에서 모델 품질을 잘 구별한다는 긍정적 신호다.

**③ KO Qwen-14B: 2nd-pos bias(9.2%) > 1st-pos bias(6.3%)**

전체 1,200건 중 1st-pos bias는 76건(6.3%), 2nd-pos bias는 111건(9.2%)으로 순서가 역전됐다. EN 14B의 1st-pos(35.5%) vs 2nd-pos(6.6%) 패턴과 비교하면 KO 14B에서는 방향성 자체가 약하고 뒤집혀 있어, 이 judge-언어 조합에서는 오히려 2nd-position 선호가 소폭 우세하다.

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
| EN | EXAONE-32B | 7.83 | 6.72 | −1.11 | <0.001 | *** |
| KO | Qwen-7B | 6.92 | 6.51 | −0.41 | 0.060 | ns |
| KO | Qwen-14B | 6.29 | 4.68 | −1.61 | <0.001 | *** |
| KO | Qwen-32B | 6.30 | 4.87 | −1.44 | <0.001 | *** |
| KO | EXAONE-32B | 7.16 | 6.04 | −1.12 | <0.001 | *** |

Reference-guided 채점이 standard보다 점수가 유의하게 낮다. 이는 ref 문항이 math/coding/reasoning — 즉 객관적 정답이 있고 채점이 까다로운 문항 — 에 한정되기 때문이다. Reference를 제공했을 때 judge가 정답 기준을 더 엄격하게 적용한다는 해석과, ref 문항 자체가 난이도가 높다는 두 가지 원인이 복합적으로 작용한다. KO Qwen-7B에서 차이가 통계적으로 유의하지 않은(−0.41, p=0.060, ns) 것은, 7B judge의 한국어 ref 파싱 실패(33.3%)로 유효 샘플이 극도로 감소한 결과다.

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
| EXAONE-32B | single_grade | 32 | 960 | **3.3%** |
| EXAONE-32B | single_grade_ref | 0 | 174 | 0.0% |
| EXAONE-32B | pairwise | 0 | 1,200 | 0.0% |

Qwen-7B의 KO single_grade_ref 33.3%는 이 연구의 핵심 발견 중 하나다. 한국어 프롬프트에서 소형 judge가 포맷 지시를 따르지 못하거나 중국어로 응답하는 사례가 급증한다. EN 동일 설정(2.9%)과 비교하면 약 11배 차이다. Qwen-32B는 KO에서도 0.1% 이하로 안정적이다.

EXAONE-32B의 KO single_grade parse failure 3.3%는 EN 동일 설정(0.6%)의 약 5배다. 32B 크기임에도 불구하고 한국어 채점 프롬프트에서 포맷 지시 준수율이 저하되는 현상으로, cross-family judge의 언어별 응답 성향 차이를 반영한다. 카테고리별로는 extraction(9건)·writing(7건)·stem(5건)에 집중되며, 짧은 답변 평가나 긴 지시문 포맷에서 실패율이 높다. single_grade_ref와 pairwise에서는 실패가 없어, 프롬프트 구조가 다른 채점 유형에서는 정상 동작함을 확인하였다.

---

## Base Paper 비교 (Zheng et al. 2023)

| 지표 | 원 논문 (GPT-4 judge) | 본 연구 (EN Qwen-32B) | 본 연구 (EN GPT-4o) |
|------|---------------------:|--------------------:|-------------------:|
| Inconsistency (1 − consistency) | **35.0%** (Table 2) | 30.9% [28.3%, 33.6%] | ⏳ Phase 1c |
| 1st-position bias (전체 pair 기준) | **30.0%** (Table 2) | 22.2% (267/1,200) | ⏳ Phase 1c |
| Judge-model agreement (vs human, S2) | **85%** (non-tie) | — | ⏳ Phase 1c |

원 논문은 GPT-4 judge로 **유사 성능 GPT-3.5 쌍**을 평가한 반면, 본 연구는 Qwen-32B로 실제 6개 eval 모델 전체 pair를 평가한다. 평가 쌍의 성능 차이가 클수록 inconsistency가 낮아지는 경향이 있어 수치의 직접 비교는 참고 수준이다. GPT-4o judge(Phase 1c) 완료 후 원 논문과 동등한 조건의 비교가 가능하며, 세 judge family(Qwen / EXAONE / GPT-4o) 간 cross-family bias 분석이 완성된다.

---

## 프로젝트 구조

```
mt_bench_repro/
├── data/
│   ├── en/
│   │   ├── answers/                      # eval 모델 6개 답변 (git 추적)
│   │   ├── judgments/qwen/               # Qwen judge 결과 (git 제외)
│   │   ├── judgments/exaone/             # EXAONE-32B judge 결과 (git 제외)
│   │   ├── judgments/gpt/                # GPT-4o judge 결과 (git 제외, Phase 1c)
│   │   └── results/                      # 집계 CSV (git 추적)
│   └── ko/
│       ├── questions.jsonl               # 한국어 번역 80문항
│       ├── translation_notes.md
│       ├── answers/                      # KO eval 모델 답변 (git 제외)
│       ├── judgments/qwen/               # Qwen judge 결과 (git 제외)
│       ├── judgments/exaone/             # EXAONE-32B judge 결과 (git 제외)
│       ├── judgments/gpt/                # GPT-4o judge 결과 (git 제외, Phase 1c)
│       └── results/                      # KO judge 집계 CSV + 통계 검정 결과
├── scripts/
│   ├── run/a100/
│   │   ├── run_generate_phase3_a100.sh   # EN 답변 생성 (완료)
│   │   ├── run_judge_phase3_a100.sh      # EN Qwen judge (완료)
│   │   ├── run_generate_ko_a100.sh       # KO 답변 생성 (완료)
│   │   ├── run_judge_ko_a100.sh          # KO Qwen judge (완료)
│   │   ├── run_judge_exaone32b_a100.sh   # EN+KO EXAONE judge (완료)
│   │   └── run_ko_full_a100.sh           # KO 전체 파이프라인
│   ├── run/local/
│   │   ├── run_mock_full.sh
│   │   └── run_judge_gpt4o_local.sh      # GPT-4o judge (Phase 1c, 로컬 실행)
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

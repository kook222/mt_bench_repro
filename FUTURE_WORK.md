# 향후 연구 방향

현재까지의 재현 실험 결과를 바탕으로 도출한 후속 연구 아이디어.

> **목표 수준: 워크샵 / 국내저널**
> 인간 평가자 실험(인력 비용, 다수 annotator)은 top-tier 제출용 검증에 해당.
> 워크샵/국내저널 수준에서는 실행 가능성이 높고 contribution이 명확한 실험을 우선.

---

## ✅ 완료된 연구

| 연구 | 결과 요약 | 위치 |
|------|----------|------|
| **Phase 1** — Self-judge 기준선 | Qwen2.5-7B self-judge, 전체 8.12 (Math/Coding 과대평가) | `data/results_qwen7b.csv` |
| **Phase 2** — 6개 모델 비교 | Phi-3.5-mini 1위(8.09), Zephyr 6위(7.04), Single↔Pairwise ρ=0.943 | `data/results_multi.csv` |
| **Phase 3** — Judge 스케일링 법칙 | 7B(78.75%) → 14B(46.85%) → 32B(32.86%) 단조 감소, ρ>0.75 유지 | `data/results_phase3_*.csv` |
| **문항 수 민감도** | 60문항부터 ρ≥0.95 안정, 10문항은 min ρ=0.32 신뢰 불가 | `data/results_phase3_qsize.csv` |
| **변별도 기반 갭 분석** | Extraction이 데이터 기반 2위(mean std=1.291), 논문 "easy" 레이블 과소평가 확인 | `data/results_discriminability.csv` |
| **tinyMT-Bench** | TopDisc-15로 ρ=1.000 달성 (Random 기준 60문항 필요), 81% 문항 절감 | `data/results_tiny_mt_bench.csv` |

---

## 향후 연구 아이디어

기존 데이터 활용 가능 여부와 기여점을 기준으로 우선순위 책정.

---

### ~~1순위 — tinyMT-Bench: 최소 변별 문항 세트 발굴~~ ✅ 완료

**연구 질문:** 변별도 상위 N개 문항만으로 80문항 전체와 동일한 모델 순위를 얻을 수 있는가?

**배경:**
- 문항 수 민감도 분석: 랜덤 N개 서브샘플 기준으로 60문항에서 ρ=0.95 수렴
- 변별도 분석: 문항별 inter-model std가 이미 계산됨
- **미연결된 두 분석을 결합**: "변별도 상위 N개" vs "랜덤 N개" 중 어느 쪽이 더 빠르게 수렴하는가?

**실험 설계:**
```
for N in [10, 15, 20, 25, 30, 40]:
    방법 A: 랜덤 N개 문항 (기존 Q-size 분석, 30회 반복 평균)
    방법 B: 변별도 상위 N개 문항 (고정, 반복 없음)
    → 각각 Spearman ρ vs 80문항 전체 순위 계산
```

**예상 결과:**
- 변별도 상위 20개 ≈ 랜덤 40개 수준의 순위 보존
- 변별도 상위 30개면 80문항과 사실상 동일한 순위

**필요 작업:** `analyze_discriminability.py` 확장, 추가 실험 불필요

**기여점:** 벤치마크 비용을 절반 이하로 줄이면서도 신뢰 순위 유지 가능한 "최소 문항 세트" 제안 — tinyBenchmarks(2024)의 MT-Bench 버전, 데이터 기반 문항 선택의 우월성 실증

---

### 2순위 — Turn 1 vs Turn 2 성능 저하 분석

**연구 질문:** 멀티턴에서 모델별·카테고리별 Turn 2 품질 저하 패턴은 어떻게 다른가?

**배경:**
- 현재 집계는 Turn 1 + Turn 2 평균을 사용
- `score_turn1`, `score_turn2`가 이미 분리 저장되어 있음
- 추가 실험 전혀 불필요

**분석 내용:**
- 모델별 `Turn2 − Turn1` 델타 계산
- 카테고리별 Turn 2 저하율 비교 (coding/math의 follow-up이 더 어려울 것으로 예상)
- Judge 크기별 Turn 2 채점 패턴 차이 (Phase 3 데이터 활용)

**예상 흥미 발견:**
- Math/Coding: Turn 2 follow-up 질문이 더 어렵고 복잡 → 큰 폭 하락 예상
- Writing/Roleplay: Turn 2가 창의성 요구 → 모델별 편차 클 수 있음
- SOLAR, Zephyr: 이미 낮은 Turn 1에서 Turn 2가 더 가파르게 하락할 가능성

**기여점:** 멀티턴 robustness의 모델별 프로파일 제시. 단순 overall 점수로 가려진 패턴 발굴.

---

### 3순위 — Position Bias 정량화

**연구 질문:** Pairwise inconsistency 발생 시 먼저 제시된 모델이 유리한가? Judge 크기별로 position bias 강도가 달라지는가?

**배경:**
- Phase 3에서 judge 3종의 pairwise JSONL 보유
- inconsistency가 `AB 순서 = A승` / `BA 순서 = B승` 패턴이면 position bias 확정
- inconsistency가 `AB 순서 = B승` / `BA 순서 = A승` 패턴이면 모델 고유 품질 차이 반영

**분석 내용:**
```
inconsistent 판정 553개에 대해:
  - AB 순서에서 A가 이긴 비율  → first-position bias
  - BA 순서에서 B가 이긴 비율  → first-position bias
  → 0.5보다 크면 position bias 존재
```

**Judge 크기별 비교:**
- 7B judge: position bias가 더 강할 것으로 예상 (inconsistency 78.75%)
- 32B judge: position bias가 약화될 것으로 예상 (inconsistency 32.86%)

**기여점:** Judge 스케일링이 "단순 불일치 감소"인지 "position bias 제거"인지를 구분. inconsistency율 감소의 메커니즘 해명.

---

### 4순위 — 앙상블 Judge

**연구 질문:** 7B + 14B + 32B 다수결 투표 시 inconsistency율이 단일 32B judge보다 낮아지는가?

**배경:**
- Phase 3 데이터 3종이 이미 존재
- 구현 자체는 간단: 동일 문항·동일 쌍에 대해 3개 judge의 winner 다수결

**설계:**
```
majority_vote(7B, 14B, 32B):
  - 2/3 이상 일치 → winner 선언
  - 모두 다르면 → inconsistent
```

**비용 관점:**
- 단일 32B: 큰 모델 하나 (느리고 비쌈)
- 앙상블 7B×3: 작은 모델 세 번 (비용 절감 가능성)

**기여점:** "단일 대형 judge" vs "소형 앙상블" 성능·비용 트레이드오프 실증. 실용적 배포 권고안 도출.

---

### 5순위 — 한국어 MT-Bench

**연구 질문:** 영어 기준 MT-Bench 순위가 한국어 평가에서도 동일하게 유지되는가?

**배경:**
- 번역 비용(GPT-4o API)만 있으면 기존 파이프라인 그대로 재활용 가능
- 한국 연구자로서 motivation이 명확 → 국내저널 심사 설득력 높음
- SOLAR(Upstage), Yi-1.5(아시아 다국어)가 한국어에서 순위 상승 가능성 있음

**실험 설계:**
- 80문항 한국어 번역 (GPT-4o 자동 번역 후 검수)
- 동일 7개 모델 답변 생성 (A100, 1~2일 추가)
- 동일 judge 파이프라인 적용
- 영어 순위 vs 한국어 순위 Spearman ρ 계산

**예상 결과:**

| 모델 | 영어 순위 | 한국어 예상 변화 | 이유 |
|------|----------|--------------|------|
| SOLAR-10.7B | 5위 | 상승 가능 | Upstage 한국어 특화 모델 |
| Yi-1.5-9B | 3위 | 유지 or 상승 | 아시아 다국어 훈련 |
| Mistral-7B | 4위 | 하락 가능 | 유럽어 중심 훈련 |
| Zephyr-7B | 6위 | 하락 가능 | 영어 중심 fine-tuning |

**기여점:** 영어 벤치마크 순위를 한국어 환경에 그대로 적용하는 것의 위험성 실증. 한국어 LLM 선택 가이드라인 제시.

---

### 6순위 — GPT-4o Judge vs 인간 평가자 일치율

> **워크샵/국내저널 수준에서는 6순위.** 인간 평가자 모집·진행 비용이 크고, 1–4순위 실험만으로 충분한 contribution이 성립됨. top-tier(ACL, NeurIPS) 제출 시 추가 검토.

**연구 질문:** 오픈소스 judge(Qwen2.5 시리즈)와 인간 평가자의 일치율은 얼마인가?

**실험 설계:**
- pairwise 문항 중 50개 샘플링 (카테고리별 stratified)
- 인간 평가자 3명 직접 판정
- GPT-4o / Qwen2.5-14B / Qwen2.5-7B judge 동일 문항 실행
- 3방향 일치율 비교

| 비교 쌍 | 예상 일치율 |
|---------|-----------|
| 인간 vs GPT-4o | ~80% (논문 재현) |
| 인간 vs Qwen2.5-14B | ~55%? |
| 인간 vs Qwen2.5-7B | ~45%? |

**기여점:** 원 논문이 검증하지 않은 "오픈소스 judge 크기별 인간 일치율 곡선" 도출.

---

## 추천 실행 순서

```
즉시 착수 (기존 데이터, 추가 실험 불필요)
├── 1. tinyMT-Bench          ← 변별도 + Q-size의 자연스러운 완결, 임팩트 최대
├── 2. Turn 1/2 분석         ← 코드만으로 하루 안에 완성
└── 3. Position Bias 정량화  ← Judge 스케일링 섹션에 추가 가능

추가 실험 필요 (A100 1~2일)
├── 4. 앙상블 Judge           ← Phase 3 데이터 이미 있음, 새 추론만 필요
└── 5. 한국어 MT-Bench        ← 독립적 논문 구성 가능, 가장 넓은 독자층

인력 필요
└── 6. 인간 평가자 실험        ← top-tier 목표 시 추가
```

**최우선 추천: tinyMT-Bench**
변별도 분석(`fig8`)과 Q-size 민감도(`fig7`)가 이미 완성되어 있고, 두 분석을 연결하는 비교 실험 하나만 추가하면 "데이터 기반 최소 문항 선택"이라는 완결된 기여점이 도출된다.

---

## Position Bias 분석 배경 (기존 기록 유지)

Pairwise judge는 동일 질문에 대해 **두 번** 실행한다:

- **AB 순서**: "A 답변 vs B 답변"을 judge에게 제시 → 판정
- **BA 순서**: "B 답변 vs A 답변"을 judge에게 제시 → 판정

두 결과가 **일치하면** winner 선언, **불일치하면** `inconsistent` (집계 시 tie 처리).

이는 논문 Section 3.4의 **conservative approach** — position bias(먼저 제시된 모델을 선호하는 경향)를 완화하기 위한 설계다.

**Phase 2 측정 결과:**

| 항목 | 수치 |
|------|------|
| 전체 pairwise 판정 | 1,200개 (15쌍 × 80문항) |
| inconsistent | 553개 |
| **inconsistency율** | **46.1%** |

**Phase 3 측정 결과 (judge 크기별):**

| Judge | inconsistency율 |
|-------|----------------|
| Qwen2.5-7B | 78.75% |
| Qwen2.5-14B | 46.85% |
| Qwen2.5-32B | 32.86% |

3순위 연구에서 이 불일치의 **원인**(position bias vs 모델 품질 차이)을 정량적으로 분해할 계획.

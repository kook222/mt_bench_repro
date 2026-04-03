# 향후 연구 방향

현재까지의 재현 실험 결과를 바탕으로 도출한 후속 연구 아이디어.

> **목표 수준: 워크샵 / 국내저널**
> 인간 평가자 실험은 top-tier 제출용. 워크샵/국내저널 수준에서는 실행 가능성이 높고 contribution이 명확한 실험을 우선.

---

## ✅ 완료된 연구

| # | 연구 | 핵심 결과 | 데이터 |
|---|------|----------|--------|
| 1 | **Phase 1** — Self-judge 기준선 | Qwen2.5-7B overall 8.12, Math/Coding 과대평가 확인 | `results_qwen7b.csv` |
| 2 | **Phase 2** — 6개 모델 비교 | Phi-3.5-mini 1위(8.09), Single↔Pairwise ρ=0.943, inconsistency 46.1% | `results_multi.csv` |
| 3 | **Phase 3** — Judge 스케일링 법칙 | inconsistency 7B(78.75%)→14B(46.85%)→32B(32.86%) 단조 감소, cross-judge ρ>0.75 | `results_phase3_*.csv` |
| 4 | **문항 수 민감도** | 랜덤 선택 기준 60문항부터 ρ≥0.95 안정, 10문항은 min ρ=0.32 | `results_phase3_qsize.csv` |
| 5 | **변별도 기반 갭 분석** | Extraction이 데이터 기반 변별도 2위(std=1.291), 논문 "easy" 레이블 과소평가 | `results_discriminability.csv` |
| 6 | **tinyMT-Bench** | TopDisc-40으로 ρ=1.000 달성(50% 절감), TopDisc-25로 ρ≥0.95(69% 절감). Random은 60문항 필요 | `results_tiny_mt_bench.csv` |
| 7 | **Turn 1 vs Turn 2 저하 분석** | Coding/Reasoning은 Turn 2 상승(+0.44/+0.73), Writing 가장 취약(−1.13). SOLAR 가장 취약(δ=−0.287) | `results_turn_degradation.csv` |
| 8 | **Position Bias 정량화** | 32B judge 불일치의 94.9%가 first-pos bias. 절대 비율은 66%→31%로 감소하지만 불일치 원인은 노이즈→bias로 전환 | `results_position_bias.csv` |

---

## 향후 연구 아이디어

기존 데이터 활용 가능 여부와 기여점을 기준으로 우선순위 책정.

---

### 1순위 — Position Bias 정량화

**연구 질문:** Pairwise inconsistency가 발생할 때 먼저 제시된 모델이 유리한가? Judge 크기가 커질수록 position bias가 줄어드는가?

**배경:**
Pairwise judge는 동일 문항에 대해 AB 순서 / BA 순서로 두 번 실행한다. 불일치 시 `inconsistent` 처리되는데, 이 불일치의 원인이 **position bias**(먼저 제시된 모델을 선호)인지, **실제 모델 품질 차이 반영**인지를 아직 구분하지 못했다.

```
inconsistent 판정에서:
  AB 순서일 때 A가 이긴 비율 → first-position bias 지표
  BA 순서일 때 B가 이긴 비율 → first-position bias 지표
  → 0.5 초과이면 position bias 존재 확정
```

**Phase 2/3 측정값 (불일치율):**

| Judge | Inconsistency율 |
|-------|----------------|
| Qwen2.5-7B | 78.75% |
| Qwen2.5-14B | 46.85% |
| Qwen2.5-32B | 32.86% |

**왜 1순위가 아닌가:** Turn 1/2 분석보다 pairwise JSONL 구조 파악이 추가로 필요. 하지만 추가 실험 없이 기존 데이터만으로 가능.

**기여점:** Judge 스케일링이 "단순 불일치 감소"인지 "position bias 제거"인지를 구분. inconsistency율 감소의 메커니즘 해명.

---

### 3순위 — 앙상블 Judge

**연구 질문:** 7B + 14B + 32B 다수결 투표 시 inconsistency율이 단일 32B judge보다 낮아지는가?

**설계:**
```
majority_vote(judge_7B, judge_14B, judge_32B):
  2/3 이상 일치 → winner 선언
  모두 다르면   → inconsistent
```

**핵심 비교:**

| 방식 | VRAM | 비용 | 예상 inconsistency |
|------|------|------|------------------|
| 단일 32B | 20 GB (AWQ) | 높음 | 32.86% |
| 앙상블 7B×3 | 14 GB × 3회 | 낮음 | ? |

Phase 3 데이터 3종이 이미 있으므로 구현 자체는 간단. 새로운 추론 불필요.

**기여점:** "단일 대형 judge" vs "소형 앙상블" 성능·비용 트레이드오프 실증. 실용적 배포 권고안 도출.

---

### 4순위 — 한국어 MT-Bench

**연구 질문:** 영어 기준 MT-Bench 순위가 한국어 평가에서도 동일하게 유지되는가?

**실험 설계:**
- 80문항 한국어 번역 (GPT-4o 자동 번역 후 검수)
- 동일 7개 모델 답변 생성 (A100, 1~2일 추가)
- 동일 judge 파이프라인 적용 → 영어 순위 vs 한국어 순위 Spearman ρ 계산

**예상 순위 변화:**

| 모델 | 영어 순위 | 한국어 예상 | 근거 |
|------|----------|-----------|------|
| SOLAR-10.7B | 5위 | 상승 가능 | Upstage 한국어 특화 |
| Yi-1.5-9B | 3위 | 유지 or 상승 | 아시아 다국어 훈련 |
| Mistral-7B | 4위 | 하락 가능 | 유럽어 중심 훈련 |
| Zephyr-7B | 6위 | 하락 가능 | 영어 중심 fine-tuning |

**왜 지금 당장이 아닌가:** A100 1~2일 추가 실험 필요. 1~3순위는 기존 데이터만으로 가능하므로 먼저 진행.

**기여점:** 영어 벤치마크 순위를 한국어 환경에 그대로 적용하는 것의 위험성 실증. 한국어 LLM 선택 가이드라인 제시. 국내저널 심사 설득력 높음.

---

### 5순위 — GPT-4o Judge vs 인간 평가자 일치율

> **워크샵/국내저널 수준에서는 5순위.** 인간 평가자 모집·진행 비용이 크고, 1–3순위만으로 충분한 contribution이 성립됨. top-tier(ACL, NeurIPS) 제출 시 추가 검토.

**연구 질문:** 오픈소스 judge(Qwen2.5 시리즈)와 인간 평가자의 일치율은 얼마인가?

**실험 설계:**
- pairwise 문항 중 50개 샘플링 (카테고리별 stratified)
- 인간 평가자 3명 직접 판정 (약 2~3시간)
- GPT-4o / Qwen2.5-14B / Qwen2.5-7B judge 동일 문항 실행

| 비교 쌍 | 예상 일치율 |
|---------|-----------|
| 인간 vs GPT-4o | ~80% (논문 재현) |
| 인간 vs Qwen2.5-14B | ~55%? |
| 인간 vs Qwen2.5-7B | ~45%? |

**기여점:** 원 논문이 검증하지 않은 "오픈소스 judge 크기별 인간 일치율 곡선" 도출.

---

## 추천 실행 순서

```
✅ 완료
└── Turn 1/2 저하 분석     → SOLAR 가장 취약, Coding/Reasoning은 오히려 상승

즉시 착수 (기존 데이터, 추가 실험 불필요)
├── 1. Position Bias 정량화    ← inconsistency 메커니즘 해명
└── 2. 앙상블 Judge            ← Phase 3 데이터 재활용, 실용적 기여

추가 실험 필요 (A100 1~2일)
└── 3. 한국어 MT-Bench         ← 독립적 논문 구성 가능, 국내 독자층

인력 필요 (top-tier 목표 시)
└── 4. 인간 평가자 실험
```

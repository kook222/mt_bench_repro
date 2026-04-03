# 향후 연구 방향

현재까지의 재현 실험 결과를 바탕으로 도출한 후속 연구 아이디어.

> **목표: KCC 2026 학부생/주니어 논문경진대회 제출 (마감: 2026-04-17) → 이후 국내저널 확장**

---

## ✅ 완료된 연구

| # | 연구 | 핵심 결과 | 데이터 |
|---|------|----------|--------|
| 1 | **Phase 1** — Self-judge 기준선 | Qwen2.5-7B overall 8.12, Math/Coding 과대평가 확인 | `results_qwen7b.csv` |
| 2 | **Phase 2** — 6개 모델 비교 | Phi-3.5-mini 1위(8.09), Single↔Pairwise ρ=0.943, inconsistency 46.1% | `results_multi.csv` |
| 3 | **Phase 3** — Judge 스케일링 법칙 | inconsistency 7B(78.75%)→14B(46.85%)→32B(32.86%) 단조 감소, cross-judge ρ>0.75 | `results_phase3_*.csv` |
| 4 | **문항 수 민감도** | 랜덤 선택 기준 60문항부터 ρ≥0.95 안정, 10문항은 min ρ=0.32 | `results_phase3_qsize.csv` |
| 5 | **변별도 기반 갭 분석** | Extraction이 데이터 기반 변별도 4위(std=1.296), 논문 "easy" 레이블 과소평가 | `results_discriminability.csv` |
| 6 | **tinyMT-Bench** | TopDisc-40으로 ρ=1.000 달성(50% 절감), TopDisc-25로 ρ≥0.95(69% 절감) | `results_tiny_mt_bench.csv` |
| 7 | **Turn 1 vs Turn 2 저하 분석** | Coding/Reasoning은 Turn 2 상승(+0.44/+0.73), Writing 가장 취약(−1.13). SOLAR 가장 취약(δ=−0.287) | `results_turn_degradation.csv` |
| 8 | **Position Bias 정량화** | 32B judge 불일치의 94.9%가 first-pos bias. 절대 비율은 66%→31%로 감소하지만 불일치 원인은 노이즈→bias로 전환 | `results_position_bias.csv` |
| 9 | **앙상블 Judge (다수결)** | 앙상블(58.63%)이 단일 32B(32.86%)보다 오히려 나쁨. 저품질 judge의 inconsistent 표가 앙상블을 오염시킴 | `results_ensemble_judge.csv` |
| 10 | **앙상블 기권 방식** | inconsistent를 기권 처리 시 24.70% 달성 — 단일 32B(32.86%)보다 낮음. 604쌍(36%) inconsistent→winner 전환 | `results_ensemble_v2.csv` |
| 11 | **Bootstrap CI** | Cross-judge ρ 95% CI 전 쌍 하한 ≥0.6. 7B–14B: ρ=0.821 [0.643, 0.964], 14B–32B: ρ=0.750 [0.607, 0.964] | `results_bootstrap_ci.csv` |

---

## KCC 2026 제출 준비 현황 (D-14, 마감 2026-04-17)

### 🔴 최우선 (즉시 착수, D-14)

**③ 논문 작성 (프레이밍 전환)**

포지셔닝: "재현 연구"가 아닌 **"오픈소스 LLM-as-a-Judge 신뢰도 분석"** 으로 프레이밍.

핵심 contribution 3가지:
1. Judge 스케일링이 inconsistency를 줄이지만 position bias로 전환됨을 최초 실증  
   (7B: 66% first-pos → 32B: 94.9% first-pos, 절대 비율은 감소하지만 원인 전환)
2. 앙상블 다수결이 단일 고품질 judge보다 나쁨을 실증; 기권 방식으로 개선 가능
3. 변별도 기반 최소 문항 선택(tinyMT-Bench)으로 50% 비용 절감 + 순위 완전 보존

학술대회: KCC 2026 학부생/주니어 논문경진대회 (4~6페이지, 한글)

---

### 🟡 KCC 이후 확장 (2026 하반기)

**④ API Judge 1개 추가**

GPT-4o-mini 또는 Claude Haiku를 judge로 추가해 "Qwen 패밀리에만 해당하는 결과 아닌가?" 반박 차단.

비교 포인트:
- Qwen2.5-32B vs GPT-4o-mini: inconsistency율, position bias, 모델 서열 일치도
- 목표 학술대회: HCLT 2026 (한국어정보처리학술대회, 9월 예정) 또는 국내저널

**⑤ 다른 Judge 패밀리 추가** (A100 1~2일)

Llama-3.1-8B 또는 Mistral-7B를 judge로 사용해 아키텍처 변수 분리. "Qwen이라서 그런 결과" 반박 완전 차단.

**⑥ 한국어 MT-Bench** (A100 1~2일)

80문항 한국어 번역 후 동일 파이프라인 적용. 영어 순위 vs 한국어 순위 비교. SOLAR(Upstage 한국어 특화) 순위 변화 예측 가능. 국내 독자층 설득력 높음.

---

### 🔵 top-tier 목표 시 (인력 필요)

**⑦ 인간 평가자 실험**

pairwise 문항 50개 샘플링, 평가자 3명 직접 판정. 오픈소스 judge 크기별 인간 일치율 곡선 도출. ACL/EMNLP 메인 트랙 목표 시 필수.

---

## 추천 실행 순서

```
KCC 2026 제출 (D-14, 마감 4/17)           ← 지금 당장
└── ③ 논문 작성 (4~6페이지, 한글)
      - 실험 결과 11개 → 논문 구조로 정리
      - contribution 3가지 중심으로 프레이밍
      - 기존 figures/ 및 data/ 전량 활용 가능

KCC 이후 → HCLT 2026 또는 국내저널 확장
├── ④ API Judge 추가 (GPT-4o-mini)         ← API 비용만 필요
└── ⑤ 한국어 MT-Bench                      ← A100 필요

top-tier 목표 시 (ACL/EMNLP)
└── ⑦ 인간 평가자 실험
```

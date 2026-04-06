# 향후 연구 방향

NeurIPS 2023 논문 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" 재현을 기반으로 수행한 후속 연구 계획.

> **단기 목표: KCC 2026 학부생/주니어 논문경진대회 제출 (마감: 2026-04-17)**
> **중기 목표: HCLT 2026 또는 국내저널 확장**
> **장기 목표: ACL/EMNLP 워크샵 또는 메인 트랙**

---

## ✅ 완료된 연구 (총 11개)

| # | 연구 주제 | 핵심 결과 | 데이터 파일 |
|---|----------|----------|------------|
| 1 | **Phase 1** — Self-judge 기준선 | Qwen2.5-7B overall 8.12, Math/Coding 과대평가 확인 | `results_qwen7b.csv` |
| 2 | **Phase 2** — 6개 모델 비교 | Phi-3.5-mini 1위(8.09), Single↔Pairwise ρ=0.943, inconsistency 46.1% | `results_multi.csv` |
| 3 | **Phase 3** — Judge 스케일링 법칙 | inconsistency 7B(78.75%)→14B(46.85%)→32B(32.86%) 단조 감소, cross-judge ρ>0.75 | `results_phase3_*.csv` |
| 4 | **문항 수 민감도** | 60문항부터 ρ≥0.95 안정, 10문항은 min ρ=0.32 | `results_phase3_qsize.csv` |
| 5 | **변별도 기반 갭 분석** | Extraction 데이터 기반 변별도 4위(std=1.296), 논문 "easy" 레이블 과소평가 | `results_discriminability.csv` |
| 6 | **tinyMT-Bench** | TopDisc-40으로 ρ=1.000 달성(50% 절감), TopDisc-25로 ρ≥0.95(69% 절감) | `results_tiny_mt_bench.csv` |
| 7 | **Turn 1 vs Turn 2 저하 분석** | Coding/Reasoning Turn 2 상승(+0.44/+0.73), Writing 가장 취약(−1.13) | `results_turn_degradation.csv` |
| 8 | **Position Bias 정량화** | 32B judge 불일치의 94.9%가 first-pos bias. 크기 증가 시 노이즈→bias 원인 전환 | `results_position_bias.csv` |
| 9 | **앙상블 Judge (다수결)** | 앙상블(58.63%)이 단일 32B(32.86%)보다 나쁨. 저품질 judge의 inconsistent 표가 오염 | `results_ensemble_judge.csv` |
| 10 | **앙상블 기권 방식** | inconsistent 기권 처리 시 24.70% 달성(단일 32B 대비 개선). 604쌍(36%) 결정 전환 | `results_ensemble_v2.csv` |
| 11 | **Bootstrap CI** | Cross-judge ρ 95% CI 전 쌍 하한 ≥0.6. 7B–14B: ρ=0.821 [0.643, 0.964] | `results_bootstrap_ci.csv` |

---

## 핵심 Contribution (논문 포지셔닝)

기존 연구와의 차별점:

1. **노이즈→편향 전환 실증**: Judge 크기 증가 시 inconsistency 절대 비율은 감소하나, 불일치 원인이 무작위 노이즈에서 position bias로 전환됨을 최초 정량화
2. **앙상블 기권 설계**: inconsistent를 기권으로 처리하는 개선 앙상블이 단일 고품질 judge보다 우수함을 실증하고 설계 가이드라인 제시
3. **tinyMT-Bench**: 변별도 기반 문항 선택으로 80개 중 40개(50% 절감)만으로 순위 완전 보존 가능함을 실증

---

## 진행 중 / 예정 연구

### 🔴 즉시 진행 (D-11, 마감 4/17)

**논문 작성 — KCC 2026 학부생/주니어 논문경진대회**

- 포지셔닝: "오픈소스 LLM-as-a-Judge 신뢰도 분석 및 개선 방안"
- 분량: 4~6페이지 (한글)
- 완료된 실험 11개 기반, figures/ 및 data/ 전량 활용

---

### 🔶 6/1 최종본 추가 예정

**Phase 4 — InternLM2.5 교차 아키텍처 검증**

Qwen 패밀리 결과의 일반성을 검증하기 위해 다른 아키텍처의 judge 모델 추가.

| Judge | 모델 | 비고 |
|-------|------|------|
| judge_internlm7b | InternLM2.5-7B-Chat | eval 모델 셋 미포함 → self-judge 없음 |
| judge_internlm20b | InternLM2.5-20B-Chat | eval 모델 셋 미포함 → self-judge 없음 |

- eval 모델: Phase 3와 동일한 7개 (비교 가능성 확보)
- 비교 포인트: inconsistency율, position bias, 모델 서열 Spearman ρ
- 실행 스크립트: `scripts/run_judge_phase4_a100.sh` (완료)

**⑤ API Judge 추가 (GPT-4o-mini)**

오픈소스 judge와 상용 API judge의 성능 차이 비교.

- 비교 포인트: inconsistency율, position bias, 모델 서열 일치도 (Spearman ρ)
- Qwen2.5-32B(오픈소스) vs GPT-4o-mini(API) 직접 비교
- "오픈소스로 충분한가?" 실용적 질문에 답변 가능
- API 비용 소규모 (80문항 × 7모델 × 2turn)

**⑥ 한국어 MT-Bench**

80문항 한국어 번역 후 동일 파이프라인 적용.

- 영어 순위 vs 한국어 순위 비교
- SOLAR-10.7B(Upstage 한국어 특화 모델) 순위 변화 분석
- 국내 학술대회/저널 독자층에 직접적 설득력
- 필요 자원: 번역 작업 + A100 1~2일

---

### 🟡 KCC 이후 확장 (2026 하반기, HCLT 2026 또는 국내저널)

---

### 🔵 장기 목표 (ACL/EMNLP 메인 트랙)

**⑦ 인간 평가자 실험**

pairwise 문항 50개 샘플링, 평가자 3명 직접 판정. 오픈소스 judge 크기별 인간 일치율 곡선 도출. top-tier 학술대회 제출 시 필수 요소.

---

## 실행 로드맵

```
2026-04-17  KCC 2026 초고 제출
              └── 논문 작성 (현재 진행 중)

2026-06-01  KCC 2026 최종본 제출
              └── Phase 4 (InternLM 교차 검증) 결과 추가

2026-07월   KCC 2026 발표 (제주)

2026-09월   HCLT 2026 또는 국내저널 투고 (KCC 결과 확장)

2027년~     top-tier 목표
              └── ⑦ 인간 평가자 실험
```

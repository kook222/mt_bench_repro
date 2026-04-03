# 향후 연구 방향

현재까지의 재현 실험 결과를 바탕으로 도출한 후속 연구 아이디어.

> **목표 수준: KCC(한국컴퓨터종합학술대회) → 국내저널 확장**

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
| 9 | **앙상블 Judge** | 앙상블(58.63%)이 단일 32B(32.86%)보다 오히려 나쁨. 저품질 judge의 inconsistent 표가 앙상블을 오염시킴 | `results_ensemble_judge.csv` |

---

## KCC 논문 보완 방안

현재 연구의 약점과 보완 방안. 추가 실험 불필요 여부 기준으로 우선순위 책정.

---

### 추가 실험 없이 가능

**① 앙상블 설계 개선 버전 비교**

현재 설계는 "inconsistent"를 하나의 표로 취급한다. 결정적 표(A 또는 B)만 세는 방식을 추가 비교:

```
현재: 7B=inconsistent, 14B=A, 32B=A → A 승 (2/3 일치)
      7B=A, 14B=inconsistent, 32B=inconsistent → inconsistent (모두 다름)

개선: 결정적 표가 2개 이상 일치할 때만 winner 선언
      7B=inconsistent → 기권으로 처리, 14B+32B 합의만으로 결정
```

기존 데이터 재활용. 현재 설계 vs 개선 설계 비교로 앙상블 섹션이 풍부해짐.

**② Bootstrap Confidence Interval 추가**

7개 모델로 계산한 Spearman ρ는 통계적 신뢰구간이 넓다. 기존 데이터로 bootstrap CI를 계산해 수치에 신뢰성 부여.

```python
# 예시: cross-judge ρ에 95% CI 추가
ρ = 0.786 → ρ = 0.786 [0.214, 1.000] (95% CI, bootstrap n=10000)
```

**③ 프레이밍 전환 (글쓰기)**

"재현 연구"가 아닌 **"오픈소스 LLM-as-a-Judge 신뢰도 분석"** 으로 포지셔닝. 핵심 contribution 명시:
- Judge 스케일링이 inconsistency를 줄이지만 position bias로 전환됨을 최초 실증
- 앙상블이 단일 고품질 judge보다 나쁨을 실증
- 변별도 기반 최소 문항 선택(tinyMT-Bench)으로 80% 비용 절감 가능성 제시

---

### 소규모 추가 실험 (API, GPU 불필요)

**④ API Judge 1개 추가**

GPT-4o-mini 또는 Claude Haiku를 judge로 추가해 "Qwen 패밀리에만 해당하는 결과 아닌가?" 반박 차단. 기존 파이프라인 그대로 사용, API 비용 소규모.

비교 포인트:
- Qwen2.5-32B vs GPT-4o-mini: inconsistency율, position bias, 모델 서열 일치도

---

### 추가 실험 필요 (A100 1~2일)

**⑤ 다른 Judge 패밀리 추가**

Llama-3.1-8B 또는 Mistral-7B를 judge로 사용해 아키텍처 변수 분리. "Qwen이라서 그런 결과" 반박 완전 차단.

**⑥ 한국어 MT-Bench**

80문항 한국어 번역 후 동일 파이프라인 적용. 영어 순위 vs 한국어 순위 비교. SOLAR(Upstage 한국어 특화) 순위 변화 예측 가능. 국내 독자층 설득력 높음.

---

### 인력 필요 (top-tier 목표 시)

**⑦ 인간 평가자 실험**

pairwise 문항 50개 샘플링, 평가자 3명 직접 판정. 오픈소스 judge 크기별 인간 일치율 곡선 도출. ACL/EMNLP 메인 트랙 목표 시 필수.

---

## 추천 실행 순서

```
KCC 제출 목표 (즉시)
├── ① 앙상블 설계 개선 버전 비교     ← 반나절, 기존 데이터
├── ② Bootstrap CI 추가              ← 반나절, 기존 데이터
└── ③ 프레이밍 전환 + 논문 작성

KCC 이후 저널 확장
├── ④ API Judge 추가 (GPT-4o-mini)
└── ⑤ 한국어 MT-Bench

top-tier 목표 시
└── ⑦ 인간 평가자 실험
```

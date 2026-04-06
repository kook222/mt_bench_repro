# KCC 2026 논문 작성 계획

---

## 제출 일정 전체

| 단계 | 날짜 | 내용 |
|------|------|------|
| 논문 초고 제출 | **2026-04-17** | 4~6페이지 한글, 현재 실험 기반 |
| 한국어 MT-Bench 번역 완료 | 2026-04-13 | 틈틈이 병렬 진행 |
| Phase 4 GPU 실행 | 2026-04-07~ | 서버에 올려두고 대기 |
| API Judge 실행 | 2026-04-20~ | 초고 제출 후 바로 실행 |
| 최종본 + 지적소유권위임서 제출 | **2026-06-01** | Phase 4 + API Judge + 한국어 MT-Bench 추가 |
| 발표자 참가 등록 마감 | **2026-06-01** | |
| 발표 | 2026-07월 | 제주 ICC |

---

## 논문 제목 (안)

**국문:**
> 오픈소스 LLM-as-a-Judge의 신뢰도 분석: 판사 크기 스케일링, 위치 편향 집중, 그리고 비용 효율적 평가

**영문 (국문 아래 병기):**
> Reliability Analysis of Open-Source LLM-as-a-Judge: Judge Size Scaling, Position Bias Concentration, and Cost-Efficient Evaluation

---

## KCC 논문 형식 요건

- **분량**: 4~6페이지 (2단 편집, 한글)
- **양식**: 한국정보과학회 KCC 논문 템플릿 (HWP 또는 Word)
- **언어**: 한글 본문, 영문 제목·저자·초록 병기
- **그림/표**: 본문에 포함, 캡션 한글 표기
- **참고문헌**: KIISE 스타일 (번호 순)

---

## 4/17 초고 — 섹션별 상세 계획

### 초록 (Abstract) — 10줄 이내

**구성:**
1. 문제 제기 (2줄): LLM-as-a-Judge 활용 증가, 오픈소스 judge 신뢰도 미검증
2. 방법 (2줄): MT-Bench 80문항, Qwen2.5 3종 judge, 7개 평가 모델
3. 핵심 발견 (3줄): 스케일링 효과, 위치 편향 상대 기여도 증가, 앙상블 기권 개선
4. 기여 (2줄): 실용적 가이드라인 3가지 + tinyMT-Bench 제안

**초안:**
> 대형 언어 모델(LLM)을 평가자로 활용하는 LLM-as-a-Judge 방식이 확산되고 있으나, 기존 연구는 위치 편향 또는 불일치율 측정에 집중해 왔다. 본 논문은 MT-Bench 80문항을 기반으로 Qwen2.5 계열 7B·14B·32B 모델을 평가자로, 7종의 오픈소스 모델을 피평가자로 설정하여 신뢰도를 다각도로 분석한다. 실험 결과, 평가자 크기가 증가할수록 불일치율은 단조 감소(78.75%→32.86%)하나 남아 있는 불일치에서 위치 편향의 상대적 기여도는 커짐을 확인하였다. 또한 다수결 앙상블은 단일 고품질 평가자보다 오히려 성능이 저하되며, 기권 방식 앙상블이 이를 개선함을 실증하였다. 아울러 변별도 기반 40문항(tinyMT-Bench)은 동일 모델 집합 내에서 전체 순위를 보존하면서 평가 비용을 50% 절감하였다.

---

### 1. 서론 — 약 0.5페이지

**흐름:**
1. **도입**: LLM 성능 평가의 중요성 → 인간 평가의 비용 문제
2. **LLM-as-a-Judge 등장**: GPT-4 기반 자동 평가의 확산
3. **문제 제기**: 오픈소스 judge 사용 시 신뢰도 불명확
   - 어떤 크기의 모델을 써야 하는가?
   - 앙상블이 도움이 되는가?
   - 모든 문항이 다 필요한가?
4. **연구 질문 명시**:
   - RQ1: Judge 크기 스케일링이 불일치율에 미치는 영향
   - RQ2: 불일치의 원인 분석 (노이즈 vs 위치 편향)
   - RQ3: 앙상블 설계가 신뢰도에 미치는 영향
   - RQ4: 최소 문항으로 신뢰할 수 있는 평가가 가능한가
5. **논문 구성** 안내 (마지막 문단)

**주의**: "재현 연구"라는 표현 절대 사용 금지. MT-Bench를 "실험 환경"으로만 언급.

---

### 2. 관련 연구 — 약 0.5페이지

**소제목 없이 2~3 문단으로 구성:**

**문단 1 — LLM-as-a-Judge:**
- Zheng et al. (2023): MT-Bench + GPT-4 judge 도입
- 이후 LLM-as-a-Judge의 확산

**문단 2 — 신뢰도 문제:**
- 2406.07791 (Judging the Judges): 위치 편향 분석, 15개 judge
- 2512.16041 (Are We on the Right Way): AB/BA swap 기반 inconsistency 측정
- 기존 연구와 차별점 명시:
  > "기존 연구는 단일 모델의 편향을 분석하였으나, 본 연구는 judge 크기 증가에 따른 불일치에서 위치 편향의 상대적 기여도 변화, 앙상블 설계의 영향, 최소 문항 선택 방법을 통합적으로 분석한다."

**문단 3 — 벤치마크 효율화 (선택):**
- 문항 수 축소 관련 선행 연구 (있으면 인용, 없으면 생략)

---

### 3. 실험 설계 — 약 0.5페이지

**3.1 실험 환경**

| 항목 | 내용 |
|------|------|
| 벤치마크 | MT-Bench (80문항, 8개 카테고리, 2턴) |
| 평가 모델 7종 | Llama-3.1-8B, SOLAR-10.7B, Gemma-2-9B, Yi-1.5-9B, Zephyr-7B, Mistral-7B, Phi-3.5-mini |
| Judge 모델 | Qwen2.5-7B / 14B / 32B-Instruct |
| 평가 방식 | Single-grade (1~10점) + Pairwise (AB/BA 양방향) |

**3.2 주요 지표 정의**

- **불일치율(Inconsistency Rate)**: Pairwise에서 AB 순서와 BA 순서 판정이 다른 비율
- **First-position 승률**: 불일치 쌍 중 AB 순서에서 A, BA 순서에서 B가 승리한 비율 (= 첫 번째 제시 모델 선호 편향)
- **Spearman ρ**: 두 judge 간 모델 서열 일치도

**3.3 앙상블 설계 2종**
- **다수결 방식**: inconsistent를 하나의 표로 취급, 2/3 일치 시 winner
- **기권 방식**: inconsistent를 기권으로 처리, 결정적 표(A/B)가 충돌 없으면 winner

---

### 4. 실험 결과 — 약 2~2.5페이지

#### 4.1 Judge 스케일링과 불일치율

**사용 figure: `figures/fig_phase3_scaling.png` (또는 유사)**

핵심 내용:
- 표: judge 크기별 전체 및 카테고리별 불일치율
- 7B(78.75%) → 14B(46.85%) → 32B(32.86%) 단조 감소
- Math/Coding이 가장 낮음 (명확한 정오 기준)
- Writing/Roleplay가 가장 높음 (주관성 개입)
- Cross-judge Spearman ρ > 0.75 (모델 서열은 judge 크기와 무관하게 일치)

**1문단 분량**

---

#### 4.2 불일치 감소와 위치 편향의 상대적 기여도 증가

**사용 figure: `figures/fig11_position_bias.png`**

핵심 내용:
- 불일치율은 감소하지만 first-position 승률은 증가 (66% → ~94.9%)
- 7B: 불일치의 원인이 노이즈 (first-pos 66% ≈ 무작위에서 약간 벗어남)
- 32B: 불일치의 원인이 위치 편향 (94.9% = 거의 항상 첫 번째 선택)
- 주장: "더 큰 judge가 더 신뢰할 수 있다는 단순한 결론은 위험하다"
- Math가 낮은 이유 예시 설명 (정오 기준이 편향 억제)

**1.5문단 분량**

---

#### 4.3 앙상블 Judge 설계 비교

**사용 figure: `figures/fig13_ensemble_v2.png`**

핵심 내용:
- 다수결 앙상블(58.63%)이 단일 32B(32.86%)보다 나쁜 이유: 7B의 inconsistent 표가 오염
- 기권 방식(24.70%)이 단일 32B보다 개선 → 실용적 설계 가이드라인
- 604쌍(36%)에서 inconsistent → winner 전환
- 표: 카테고리별 3종 비교 (단일 32B / 다수결 / 기권)

**1문단 분량**

---

#### 4.4 tinyMT-Bench: 변별도 기반 문항 축소

**사용 figure: `figures/fig_qsize.png` 또는 tinyMT-Bench 관련 figure**

핵심 내용:
- 문항 수 N별 Spearman ρ 곡선 (랜덤 vs 변별도 상위 선택)
- TopDisc-40: ρ=1.000 달성, 50% 비용 절감
- TopDisc-25: ρ≥0.95 달성, 69% 비용 절감
- 랜덤 선택 시 60문항 이상 필요
- **표현 주의**: "현재 7개 모델 기준에서의 결과이며, 일반화 검증은 향후 연구 과제"

**1문단 분량**

---

### 5. 결론 — 약 0.3페이지

**실용적 가이드라인 3가지 (번호 목록):**
1. 오픈소스 judge는 32B 이상 권장. 단, 크기가 커질수록 불일치 원인이 위치 편향으로 집중되므로 맹목적 스케일링은 위험
2. 앙상블 사용 시 다수결보다 기권 방식 채택 권장 — inconsistent 표를 집계에서 제외
3. 평가 비용 절감이 필요한 경우 변별도 높은 문항 선택(tinyMT-Bench)으로 50% 절감 가능

**한계점:**
- 단일 judge 패밀리(Qwen2.5)로 실험, 아키텍처 의존성 미검증 (향후 InternLM2.5 교차 검증 예정)
- 7개 평가 모델로 Spearman ρ 신뢰구간이 넓음 (95% CI 하한 ≥0.6)
- tinyMT-Bench는 동일 모델 셋 내 검증, 외부 일반화 추가 필요

**향후 연구:**
- InternLM2.5 교차 아키텍처 검증 (6/1 최종본)
- GPT-4o-mini API judge 비교 (6/1 최종본)
- 한국어 MT-Bench 적용 (6/1 최종본)

---

### 6. 참고문헌

```
[1] L. Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," NeurIPS 2023.
[2] W. Shi et al., "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge," IJCNLP 2025. arXiv:2406.07791
[3] Anonymous, "Are We on the Right Way to Assessing LLM-as-a-Judge?" arXiv:2512.16041, 2024.
[4] T. Vu et al., "A Survey on LLM-as-a-Judge," arXiv:2411.15594, 2024.
```

---

## 사용할 Figure 목록

| Figure 파일 | 사용 섹션 | 내용 |
|------------|---------|------|
| Phase 3 스케일링 관련 | 4.1 | judge 크기별 inconsistency율 |
| `fig11_position_bias.png` | 4.2 | first-position 승률 × judge 크기 |
| `fig13_ensemble_v2.png` | 4.3 | 앙상블 3종 비교 |
| tinyMT-Bench / qsize 관련 | 4.4 | 문항 수별 Spearman ρ |

**4~6페이지 제약상 figure는 최대 4개 권장. 표는 2~3개.**

---

## 6/1 최종본 추가 계획

### 추가 실험 4종

#### A. Phase 4 — InternLM2.5 교차 아키텍처 검증
- **목적**: Qwen 패밀리 한계 극복, "아키텍처 독립적 현상" 주장
- **방법**: InternLM2.5-7B/20B judge로 동일 7개 모델 평가
- **추가 섹션**: 4.5 또는 4.1에 통합
- **실행**: `scripts/run_judge_phase4_a100.sh`
- **주요 비교**: inconsistency율, position bias, Qwen judge와 Spearman ρ

#### B. API Judge — GPT-4o-mini
- **목적**: 오픈소스 vs 상용 API judge 비교
- **방법**: 기존 파이프라인에 OpenAI API key 설정
  ```bash
  export OPENAI_API_KEY="sk-..."
  python3 -m mtbench_repro.cli judge-single \
    --judge-model gpt-4o-mini \
    --openai-base-url https://api.openai.com/v1 ...
  ```
- **주요 비교**: Qwen2.5-32B vs GPT-4o-mini 불일치율·편향·서열 일치도

#### C. 한국어 MT-Bench
- **목적**: 국내 학술대회 적합성 + SOLAR 한국어 특화 모델 검증
- **번역 일정**: 4/6~4/13 (ChatGPT/Claude 활용 + 검수)
- **실행**: 번역된 질문 파일로 기존 파이프라인 그대로 실행
- **주요 비교**: 영어 순위 vs 한국어 순위, SOLAR 순위 변화

#### D. tinyMT-Bench 교차 검증 (③ 약점 보완)
- **목적**: 순환논리 해소 — Qwen 기반 선택 문항을 다른 judge로 재검증
- **방법**: TopDisc-40을 InternLM/GPT-mini judge로 Spearman ρ 계산
- **기대 결과**: ρ 유지 → "judge 아키텍처 무관하게 일반화" 주장 가능

### 최종본 구조 변경

```
기존 4.1~4.4 유지
4.5 추가: 교차 아키텍처 및 API Judge 검증 (Phase 4 + GPT-mini)
4.6 추가: 한국어 MT-Bench 결과
결론: 가이드라인 확장, 한계점 업데이트
참고문헌: InternLM 관련 추가
```

---

## D-11 작성 일정

```
D-11~D-9  (4/6~4/8)    서론 + 관련연구 + 실험설계 초안
                         병렬: 한국어 번역 시작, Phase 4 GPU 실행
D-8~D-6   (4/9~4/11)   실험 결과 4개 섹션 작성 + figure 선택
D-5~D-3   (4/12~4/14)  초록 + 결론 작성, 전체 흐름 점검
D-2~D-1   (4/15~4/16)  교정, 분량 조정 (4~6페이지 맞추기)
D-0       (4/17)        제출
```

---

## 체크리스트

### 4/17 초고 제출 전
- [ ] 논문 템플릿 다운로드 (KIISE KCC 2026 공식 양식)
- [ ] 제목·저자 정보 기입
- [ ] 초록 작성
- [ ] 서론 작성
- [ ] 관련 연구 작성 (차별점 명시)
- [ ] 실험 설계 작성
- [ ] 결과 4개 섹션 작성
- [ ] Figure 4개 선택 및 캡션 작성
- [ ] 결론 + 가이드라인 작성
- [ ] 참고문헌 정리
- [ ] 분량 확인 (4~6페이지)
- [ ] "재현 연구" 표현 제거 확인
- [ ] 맞춤법 검사

### 6/1 최종본 제출 전
- [ ] Phase 4 GPU 실행 완료 및 결과 분석
- [ ] GPT-4o-mini judge 실행 완료
- [ ] 한국어 MT-Bench 번역 + 실행 + 분석 완료
- [ ] tinyMT-Bench 교차 검증 완료
- [ ] 최종본에 4가지 추가 실험 반영
- [ ] 지적소유권위임서 작성
- [ ] 발표자 참가 등록

# KCC 2026 논문 작성 계획

## 제출 일정

| 단계 | 마감 | 내용 |
|------|------|------|
| 초고 제출 | 2026-04-17 | 현재 실험 11개 기반, 4~6페이지 한글 논문 |
| 최종본 제출 | 2026-06-01 | Phase 4 + API Judge + 한국어 MT-Bench 추가 |
| 발표자 등록 | 2026-06-01 | 참가 등록 및 지적소유권위임서 제출 |
| 발표 | 2026-07월 | 제주 ICC |

---

## 논문 제목 (안)

> **오픈소스 LLM-as-a-Judge의 신뢰도 분석: 판사 크기 스케일링, 위치 편향 전이, 그리고 비용 효율적 평가**

---

## 4/17 초고 구조 (4~6페이지, 한글)

### 1. 초록 (0.2페이지)
- LLM-as-a-Judge의 신뢰도 문제 제기
- 실험 개요: Qwen2.5 3종 judge × 7개 평가 모델
- 핵심 발견 3가지 한 줄씩
- "오픈소스 LLM-as-a-Judge 활용 시 실용적 가이드라인 제시"

### 2. 서론 (0.5페이지)
- LLM 평가 비용 문제 → LLM-as-a-Judge 등장 배경
- 오픈소스 judge 신뢰도 미검증 문제 제기
- 본 논문의 연구 질문 3가지:
  1. Judge 크기가 커지면 신뢰도는 어떻게 변하는가?
  2. 앙상블로 신뢰도를 높일 수 있는가?
  3. 평가 비용을 줄이면서 신뢰도를 유지할 수 있는가?
- 논문 구성 안내

### 3. 관련 연구 (0.5페이지)
- MT-Bench 원논문 (Zheng et al., 2023)
- LLM-as-a-Judge 신뢰도 연구 (2512.16041 등)
- Position bias 연구 (2406.07791)
- **차별점 명시**: judge 크기 스케일링 시 노이즈→편향 전환, 앙상블 기권 설계, tinyMT-Bench는 기존 연구에 없음

### 4. 실험 설계 (0.5페이지)
- MT-Bench 80문항, 8개 카테고리
- 평가 모델 7개 (Llama-3.1-8B, SOLAR-10.7B, gemma-2-9b, Yi-1.5-9B, Zephyr-7B, Mistral-7B, Phi-3.5-mini)
- Judge 모델: Qwen2.5-7B / 14B / 32B
- 평가 방식: Single-grade + Pairwise (AB/BA swap)
- Inconsistency 정의: AB 순서와 BA 순서 판정이 다른 경우

### 5. 실험 결과 (2~2.5페이지)

#### 5.1 Judge 스케일링과 Inconsistency (핵심 결과 ①)
- 그림: judge 크기별 inconsistency율 (7B→14B→32B 단조 감소)
- 표: 카테고리별 inconsistency율
- 해석: 크기 증가 = 신뢰도 향상

#### 5.2 Position Bias 전이 (핵심 결과 ②)
- 그림: judge 크기별 first-position 승률 (66%→94.9%)
- 핵심 주장: "inconsistency 감소 ≠ 편향 감소, 원인이 노이즈→편향으로 전환"
- 카테고리별 분석 (Math가 가장 낮은 이유: 명확한 정오 기준)

#### 5.3 앙상블 Judge 설계 비교 (핵심 결과 ③)
- 그림: 단일 judge vs 앙상블 현재 vs 앙상블 기권 방식 비교
- 결과: 다수결(58.63%) < 단일 32B(32.86%) < 기권(24.70%)
- 핵심 주장: "저품질 judge의 inconsistent 표가 앙상블을 오염, 기권 처리로 해결"

#### 5.4 tinyMT-Bench (핵심 결과 ④)
- 그림: 문항 수 N별 Spearman ρ 곡선
- 결과: TopDisc-40으로 ρ=1.000 (50% 절감)
- 핵심 주장: "변별도 높은 문항만으로 평가 비용 절감 가능"

### 6. 결론 (0.3페이지)
- 3가지 실용적 가이드라인 정리:
  1. 오픈소스 judge는 32B 이상 사용 권장 (단, position bias 주의)
  2. 앙상블 사용 시 기권 방식 채택
  3. 평가 비용 절감 시 변별도 기반 문항 선택(tinyMT-Bench) 활용
- 한계점: 단일 패밀리(Qwen), 7개 평가 모델로 CI 넓음
- 향후 연구: 교차 아키텍처 검증(InternLM), API judge 비교, 한국어 MT-Bench

### 7. 참고문헌
- Zheng et al. (2023) — MT-Bench 원논문
- 2406.07791 — Judging the Judges (Position Bias)
- 2512.16041 — Are We on the Right Way
- 2411.15594 — Survey on LLM-as-a-Judge

---

## 6/1 최종본 추가 내용

초고 제출 후 심사 통과 시 다음 내용을 추가.

### 추가 실험 3종

#### A. Phase 4 — InternLM2.5 교차 아키텍처 검증
- InternLM2.5-7B + 20B를 judge로 추가
- Qwen judge 결과와 Spearman ρ 비교
- "Qwen 패밀리 특성이 아닌 일반적 현상"으로 주장 강화
- 실행: `scripts/run_judge_phase4_a100.sh`

#### B. API Judge — GPT-4o-mini
- GPT-4o-mini를 judge로 추가
- 오픈소스 32B vs API judge 비교
- inconsistency율, position bias, 모델 서열 일치도
- 실행: 기존 파이프라인에 OpenAI API key 설정 후 실행

#### C. 한국어 MT-Bench
- 80문항 한국어 번역 (4/6~4/13)
- 7개 모델 한국어 답변 생성 (A100)
- Qwen32B judge로 채점
- 영어 순위 vs 한국어 순위 비교, SOLAR 순위 변화 분석

#### D. tinyMT-Bench 교차 검증 (③ 약점 보완)
- Qwen 기반으로 선택한 TopDisc-40을 InternLM/GPT-mini judge로 재검증
- ρ 유지 여부 확인 → 일반화 가능성 실증

### 최종본 구조 변경
- 5.5절 추가: "교차 아키텍처 및 API Judge 비교"
- 5.6절 추가: "한국어 MT-Bench 적용"
- 결론 확장: 한국어 평가 결과 반영
- 한계점 업데이트

---

## 작성 우선순위 (D-11)

```
D-11 ~ D-9  (4/6~4/8)   서론 + 관련연구 + 실험설계 초안
D-8  ~ D-6  (4/9~4/11)  실험 결과 섹션 (figure 선택 + 설명)
D-5  ~ D-3  (4/12~4/14) 초록 + 결론 + 전체 다듬기
D-2  ~ D-1  (4/15~4/16) 최종 교정
D-0         (4/17)       제출
```

병렬 진행:
- 한국어 MT-Bench 번역: 4/6~4/13 (논문 쓰면서 틈틈이)
- Phase 4 GPU: 4/7~ (서버에 올려두고 대기)

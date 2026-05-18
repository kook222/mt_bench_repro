# Korean MT-Bench 번역 가이드라인

## 번역 대상
- MT-Bench 80문항 × 2턴 = 160개 텍스트
- reference가 있는 39문항의 reference 답변

## 저장 경로
- `data/ko/questions.jsonl` — 한국어 번역 완성본
- `data/en/questions.jsonl` — 원본 (절대 수정 금지)

## 파일 형식
원본과 동일한 JSONL 구조. `turns[]`와 `reference[]`만 한국어로 교체.

```json
{"question_id": 81, "category": "writing",
 "turns": ["한국어 Turn1", "한국어 Turn2"]}

{"question_id": 101, "category": "math",
 "turns": ["한국어 Turn1", "한국어 Turn2"],
 "reference": ["한국어 참조답변1", "한국어 참조답변2"]}
```

형식 검증: `python3 scripts/translate/validate_translation.py`

## 번역 원칙

### 전체
- 자연스럽고 정확한 한국어 사용
- 원문의 의도와 난이도 구조를 그대로 보존
- 격식체(합쇼체) 사용 — LLM judge/eval 모델 평가에 적합한 표준어

### 카테고리별 주의사항

**coding**
- 코드 블록(``` ```) 안은 절대 번역하지 않음
- 프로그래밍 용어(변수명, 함수명, 키워드) 영어 유지
- 기술 설명 부분만 한국어로 번역

**math**
- 수식($...$, $$...$$, LaTeX 표현) 그대로 유지
- 숫자 표기는 원문 그대로 (1,000 → 1,000)
- 수학 용어: 한국어 표기 + 필요시 영어 병기

**roleplay**
- 등장인물 이름은 영어 유지 (Alice, Bob 등)
- 역할(role) 지시는 자연스럽게 번역
- 문화적 맥락이 있는 경우 각주(번역 메모) 남기기

**extraction**
- 텍스트 추출 대상 원문(인용문, 표 등)은 영어 유지
- 지시문만 한국어로 번역

**reasoning / stem / humanities**
- 일반 원칙 따름
- 전문 용어: 한국어 표기 + 괄호 안에 영어 원문 병기

## 번역 메모 형식
번역 중 주의사항이나 판단이 필요한 경우 이 파일에 기록:

| question_id | category | 메모 |
|-------------|----------|------|
| (예시) 95   | roleplay | 중국어 인용구를 한국어로 번역 시 의미 손실 최소화 |

## 진행 현황
- [ ] writing (10문항)
- [ ] roleplay (10문항)
- [ ] extraction (10문항)
- [ ] reasoning (10문항)
- [ ] math (10문항)
- [ ] coding (10문항)
- [ ] stem (10문항)
- [ ] humanities (10문항)

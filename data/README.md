# data/ 디렉토리 구조

MT-Bench 파이프라인의 모든 입출력 데이터가 여기에 저장됩니다.

---

## 디렉토리 구조

```
data/
├── mt_bench_questions.jsonl          # 전체 80문항 (git 제외, 별도 다운로드)
├── mt_bench_questions_sample.jsonl   # 샘플 3문항 (로컬 mock 테스트용)
│
├── answers/                          # 각 모델의 답변 (Phase 2 완료 시)
│   ├── Qwen2.5-7B-Instruct.jsonl     # ✅ Phase 1 완료
│   ├── SOLAR-10.7B-Instruct.jsonl    # Phase 2 예정
│   ├── Mistral-7B-Instruct-v0.3.jsonl
│   ├── gemma-2-9b-it.jsonl
│   ├── Yi-1.5-9B-Chat.jsonl
│   └── Phi-3.5-mini-Instruct.jsonl
│
├── judgments/                        # judge 채점 결과
│   ├── single_grade/                 # 단순 점수 채점 (1~10점)
│   │   ├── Qwen2.5-7B-Instruct.jsonl # ✅ Phase 1 완료
│   │   └── ...
│   ├── single_grade_ref/             # 정답 기반 채점 (math/reasoning/coding)
│   │   ├── Qwen2.5-7B-Instruct.jsonl # ✅ Phase 1 완료
│   │   └── ...
│   └── pairwise/                     # 모델 간 비교 (AB/BA swap)
│       └── ...                       # Phase 2 예정
│
├── results.csv                       # Phase 1 단일 모델 집계 결과
└── results_multi.csv                 # Phase 2 다중 모델 집계 결과
```

---

## 각 파일 설명

### answers/{모델명}.jsonl
- 모델이 MT-Bench 80문항에 답한 결과
- 1줄 = 1문항 (question_id, turn1 답변, turn2 답변 포함)
- `run_generate_multi_a100.sh` 실행 시 생성

### judgments/single_grade/{모델명}.jsonl
- judge 모델이 각 답변에 매긴 점수 (1~10점)
- 1줄 = 1문항 × 1턴
- `judge-single` 서브커맨드 실행 시 생성

### judgments/single_grade_ref/{모델명}.jsonl
- 정답(reference)을 참고한 채점 결과
- math / reasoning / coding 카테고리만 해당
- `judge-reference` 서브커맨드 실행 시 생성

### judgments/pairwise/{모델A}_vs_{모델B}.jsonl
- 두 모델 답변을 비교한 결과 (A wins / B wins / tie)
- AB 순서와 BA 순서 둘 다 포함 (position bias 제거)
- `judge-pairwise` 서브커맨드 실행 시 생성

### results.csv / results_multi.csv
- 모든 채점 결과를 집계한 최종 점수표
- 모델별 카테고리별 평균 점수 포함
- `aggregate` 서브커맨드 실행 시 생성

---

## 실험 이력

| 날짜 | Phase | 모델 | judge | 비고 |
|------|-------|------|-------|------|
| 2026-03-25 | Phase 1 | Qwen2.5-7B-Instruct | Qwen2.5-7B (self) | 파이프라인 검증용 |
| - | Phase 2 | Qwen2.5-7B + SOLAR-10.7B + Mistral-7B + gemma-2-9b + Yi-1.5-9B + Phi-3.5-mini | Qwen2.5-14B | 다중 모델 비교 예정 |

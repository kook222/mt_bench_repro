# data/ 디렉토리 구조

MT-Bench 파이프라인의 모든 입출력 데이터가 여기에 저장됩니다.

---

## 디렉토리 구조

```
data/
├── mt_bench_questions.jsonl          # 전체 80문항 (git 제외, 별도 다운로드)
├── mt_bench_questions_sample.jsonl   # 샘플 3문항 (로컬 mock 테스트용)
│
├── answers/                          # 각 모델의 답변 (Phase 1~3)
│   ├── Qwen2.5-7B-Instruct.jsonl     # Phase 1
│   ├── SOLAR-10.7B-Instruct.jsonl    # Phase 2
│   ├── Llama-3.1-8B-Instruct.jsonl   # Phase 3
│   └── ...
│
├── archive/                          # legacy 결과 보관
│   └── results_qwen7b_legacy.csv
│
├── mock/                             # 로컬 mock 검증 산출물 (실제 결과와 분리)
│   ├── answers/
│   ├── judgments/
│   ├── results.csv
│   └── results_reference.csv
│
├── judgments_phase1/                 # Phase 1: self-judge
│   ├── single_grade/
│   └── single_grade_ref/
│
├── judgments_phase2/                 # Phase 2: Qwen2.5-14B judge
│   ├── single_grade/
│   ├── single_grade_ref/
│   └── pairwise/
│
├── judgments_phase3/                 # Phase 3: judge size scaling
│   ├── judge_7B/  {single_grade, single_grade_ref, pairwise}
│   ├── judge_14B/ {single_grade, single_grade_ref, pairwise}
│   └── judge_32B/ {single_grade, single_grade_ref, pairwise}
│
├── results.csv                       # Phase 1 단일 모델 집계 결과
├── results_reference.csv             # Phase 1 reference-guided 요약
├── results_multi.csv                 # Phase 2 다중 모델 집계 결과
└── results_multi_reference.csv       # Phase 2 reference-guided 요약
```

---

## 각 파일 설명

### answers/{모델명}.jsonl
- 모델이 MT-Bench 80문항에 답한 결과
- 1줄 = 1문항 (question_id, turn1 답변, turn2 답변 포함)
- `run_generate_multi_a100.sh` 실행 시 생성

### judgments_phase*/single_grade/{모델명}.jsonl
- judge 모델이 각 답변에 매긴 점수 (1~10점)
- 1줄 = 1문항 × 1턴
- `judge-single` 서브커맨드 실행 시 생성

### judgments_phase*/single_grade_ref/{모델명}.jsonl
- 정답(reference)을 참고한 채점 결과
- math / reasoning / coding 카테고리만 해당
- `judge-reference` 서브커맨드 실행 시 생성

### judgments_phase*/pairwise/{모델A}_vs_{모델B}.jsonl
- 두 모델 답변을 비교한 결과 (A wins / B wins / tie)
- AB 순서와 BA 순서 둘 다 포함 (position bias 제거)
- `judge-pairwise` 서브커맨드 실행 시 생성

### results.csv / results_multi.csv
- 모델별 카테고리별 평균 점수표
- `aggregate` 서브커맨드 실행 시 생성
- `--questions-path`를 지정하면 complete coverage를 검사하고 partial 결과는 기본 제외

### results_reference.csv / results_multi_reference.csv
- reference-guided single grading 요약표
- math / reasoning / coding 카테고리만 포함
- main MT-Bench 점수와 다른 척도이므로 별도 보고

### archive/results_qwen7b_legacy.csv
- coverage/expected_count 컬럼 추가 전의 legacy Phase 1 요약표
- 현재 기준선은 `results.csv`와 `results_reference.csv`를 참조

---

## 실험 이력

| 날짜 | Phase | 모델 | judge | 비고 |
|------|-------|------|-------|------|
| 2026-03-25 | Phase 1 | Qwen2.5-7B-Instruct | Qwen2.5-7B (self) | 파이프라인 검증용 |
| 2026-03-27 | Phase 2 답변 생성 | SOLAR-10.7B + gemma-2-9b + Yi-1.5-9B + Zephyr-7B + Mistral-7B + Phi-3.5-mini | — | 6모델 × 80문항 |
| 2026-03-29~30 | Phase 2 judge 완료 | 위 6개 모델 + Qwen2.5-7B | Qwen2.5-14B | single/pairwise/reference 전 완료 |

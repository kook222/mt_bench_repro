# scripts/ 디렉토리 안내

## 구조

- `analysis/` — 실험 결과 CSV를 읽어 figure와 요약표를 생성하는 분석 스크립트
- `run/a100/` — A100 / vLLM 기준 생성·채점 실행 스크립트
- `run/local/` — 로컬 mock 또는 CLI 검증용 스크립트
- `run/api/` — 외부 API judge 실행 스크립트 (GPT-4o-mini)
- `tools/` — 데이터 준비, figure 재생성, 보조 유틸리티
- `translate/` — 번역 검증 및 영한 비교 분석

## 실행 순서 (Phase 1 기준)

```
1. run/a100/run_generate_ko_a100.sh    ← 한국어 eval 답변 생성
2. run/a100/run_judge_ko_a100.sh       ← Qwen judge 채점 (한국어)
3. run/a100/run_judge_gemma2_ko_a100.sh ← Gemma 2 judge 채점 (한국어)
4. translate/compare_en_ko.py          ← 영한 비교 분석 (Phase 2)
```

## 분석 스크립트 목록

| 스크립트 | 목적 |
|---------|------|
| `analyze_phase3.py` | Qwen judge 크기별 스케일링 분석 |
| `analyze_phase345.py` | judge 간 Spearman ρ 일치도 분석 |
| `analyze_translation_validity.py` | Phase 0 번역 타당성 검증 |

## 결과 파일 (data/en/results/)

| 파일 | 내용 |
|------|------|
| `scores_qwen7b/14b/32b.csv` | Qwen judge별 모델 점수 |
| `scores_gpt4omini.csv` | GPT-4o-mini judge 모델 점수 |
| `judge_scaling.csv` | judge 크기별 불일치율 |
| `judge_agreement.csv` | judge 간 Spearman ρ |

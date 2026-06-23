# scripts/ 디렉토리 안내

## 구조

- `analysis/` — 실험 결과 CSV를 읽어 figure와 요약표를 생성하는 분석 스크립트
- `run/a100/` — A100 / vLLM 기준 생성·채점 실행 스크립트
- `run/local/` — 로컬 mock 또는 CLI 검증용 스크립트
- `run/api/` — 외부 API judge 실행 스크립트
- `tools/` — 데이터 준비, figure 재생성, 보조 유틸리티

## 실행 순서 (핵심 실험 기준)

```
1. run/a100/run_generate_phase3_a100.sh  ← eval 모델 답변 생성 (Phase 3 answers 없을 때)
2. run/a100/run_judge_phase3_a100.sh     ← Qwen judge 채점
3. run/a100/run_judge_llama_a100.sh      ← LLaMA judge 채점 (신규, 핵심)
4. analysis/analyze_self_judge_bias.py   ← 핵심 분석: Kendall τ + self-judge bias
5. analysis/analyze_turn_degradation.py  ← Turn 2 구조적 난이도
6. analysis/analyze_tiny_mt_bench.py     ← 최소 변별 문항 세트 + bias 위치
```

## 분석 스크립트 목록

| 스크립트 | 목적 | 상태 |
|---------|------|------|
| `analyze_self_judge_bias.py` | Kendall τ + self-judge bias (핵심) | **신규** |
| `analyze_turn_degradation.py` | Turn 2 구조적 난이도 + judge별 비교 | 업데이트 |
| `analyze_tiny_mt_bench.py` | 최소 변별 문항 세트 + bias 집중 위치 | 업데이트 |
| `analyze_discriminability.py` | 문항별 변별도 (tinyMT-Bench 전처리) | 유지 |
| `analyze_bootstrap_ci.py` | Cross-judge Spearman ρ + 95% CI | 유지 |
| `analyze_phase3.py` | Qwen judge scaling law 분석 | 유지 |
| `analyze_phase345.py` | judge family 통합 비교 요약 | 유지 |
| `_deprecated/` | 앙상블 judge, hold-out 검증 등 (제거됨) | 삭제 |

## 가장 먼저 볼 파일

1. `analysis/analyze_self_judge_bias.py` — 전체 실험의 핵심
2. `run/a100/run_judge_llama_a100.sh` — LLaMA judge 실행
3. `../src/mtbench_repro/judge_single.py` — 채점 로직

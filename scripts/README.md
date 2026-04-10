# scripts/ 디렉토리 안내

코드 가독성을 위해 스크립트를 목적별로 분리했다.

## 구조

- `analysis/`
  - 실험 결과 CSV를 읽어 figure와 요약표를 만드는 분석 스크립트
- `run/a100/`
  - 부산대 A100 / vLLM 기준 생성·채점 실행 스크립트
- `run/local/`
  - 로컬 mock 또는 로컬 CLI 검증용 실행 스크립트
- `run/api/`
  - 외부 API judge 실행 스크립트
- `tools/`
  - 데이터 준비, figure 재생성, 보조 유틸리티
- `presentation/`
  - 발표 자료 생성 스크립트

## 가장 먼저 볼 파일

- `../src/mtbench_repro/prompts.py`
- `../src/mtbench_repro/judge_single.py`
- `../src/mtbench_repro/judge_pairwise.py`
- `../src/mtbench_repro/judge_reference.py`
- `analysis/analyze_phase3.py`
- `analysis/analyze_phase45.py`
- `analysis/analyze_tiny_mt_bench_generalization.py`

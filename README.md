# Korean MT-Bench: 한국어 LLM Judge 신뢰도 벤치마크

> **KCI 등재 학술지 투고 목표** | 원 논문: [Zheng et al., NeurIPS 2023](https://arxiv.org/abs/2306.05685)

한국어 환경에서 MT-Bench 기반 **LLM-as-a-Judge 파이프라인의 번역 타당성과 재현성**을 검증하는 연구입니다.
영어 원본 80문항을 한국어로 번역하고, 동일한 judge 파이프라인(Qwen 7B/14B/32B)으로 평가한 뒤 영·한 결과를 비교합니다.

---

## 연구 진행 상황

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 0** | 한국어 번역 + 검증 | ✅ 완료 |
| **Phase 1** | 한국어 파이프라인 실행 (A100) | 🔄 진행 중 |
| **Phase 2** | 영어-한국어 비교 분석 | ⏳ 대기 |
| **Phase 3** | KCI 논문 작성 및 투고 | ⏳ 대기 |

---

## Phase 0: 번역 완료

- **대상**: MT-Bench 80문항 × 2턴 = 160개 텍스트 + judge 프롬프트 6종 (Figure 5~10)
- **방법**: 4개 배치(40문항씩)로 분리 → 연구원 4명 수작업 번역 → O/X 검증
- **결과물**:
  - [`data/ko/questions.jsonl`](data/ko/questions.jsonl) — 한국어 질문 80문항
  - [`data/ko/MT_Bench_번역_완성본.xlsx`](data/ko/MT_Bench_번역_완성본.xlsx) — 번역 원본 (4 Batch)
  - [`data/ko/MT_Bench_Prompt_Translation.xlsx`](data/ko/MT_Bench_Prompt_Translation.xlsx) — Judge 프롬프트 번역 (Figure 5~10)
  - [`data/ko/translation_notes.md`](data/ko/translation_notes.md) — 번역 가이드라인 및 특이사항

---

## Phase 1: 한국어 파이프라인

영어 실험과 동일한 eval 모델 5개, judge 2패밀리(Qwen / Gemma 2)로 A100에서 실행합니다.

```bash
# 1. 한국어 답변 생성
bash scripts/run/a100/run_generate_ko_a100.sh

# 2. Qwen judge (--lang ko)
bash scripts/run/a100/run_judge_ko_a100.sh

# 3. Gemma 2 judge (--lang ko)
bash scripts/run/a100/run_judge_gemma2_ko_a100.sh
# → data/ko/answers/, data/ko/judgments/{qwen,gemma2}/, data/ko/results/
```

**Eval 모델 5개**: Llama-3.1-8B, SOLAR-10.7B, gemma-2-9b, Mistral-7B-v0.3, Phi-3.5-mini

**Judge 패밀리 2종:**

| 패밀리 | 모델 | 비고 |
|--------|------|------|
| Qwen2.5 | 7B / 14B / 32B-AWQ | 영어 baseline과 동일 |
| Gemma 2 | 2B / 9B / 27B-AWQ | ⚠️ gemma-2-9b는 eval 모델 겸용 (self-judge) |

---

## 영어 Baseline 결과 (Phase 1~2 완료)

### Judge별 모델 순위

| 순위 | Qwen-7B | Qwen-14B | Qwen-32B | GPT-4o-mini |
|:---:|---------|---------|---------|------------|
| 1 | Phi-3.5-mini (8.04) | Llama-3.1-8B (8.17) | gemma-2-9b (8.09) | Phi-3.5-mini (7.98) |
| 2 | Llama-3.1-8B (7.89) | Phi-3.5-mini (8.09) | Phi-3.5-mini (8.06) | gemma-2-9b (7.96) |
| 3 | gemma-2-9b (7.87) | gemma-2-9b (8.03) | Llama-3.1-8B (7.71) | Llama-3.1-8B (7.76) |
| 4 | Mistral-7B (7.45) | Mistral-7B (7.49) | Mistral-7B (7.09) | Mistral-7B (7.20) |
| 5 | SOLAR-10.7B (7.34) | SOLAR-10.7B (7.07) | SOLAR-10.7B (7.02) | SOLAR-10.7B (6.82) |

### Judge 간 랭킹 일치도 (Spearman ρ)

| | Qwen-7B | Qwen-14B | Qwen-32B | GPT-4o-mini |
|---|:---:|:---:|:---:|:---:|
| **Qwen-7B** | 1.000 | 0.821 | 0.786 | 0.893 |
| **Qwen-14B** | 0.821 | 1.000 | 0.750 | 0.786 |
| **Qwen-32B** | 0.786 | 0.750 | 1.000 | **0.964** |
| **GPT-4o-mini** | 0.893 | 0.786 | **0.964** | 1.000 |

Qwen-32B ↔ GPT-4o-mini: ρ=0.964 → 충분히 큰 오픈소스 judge는 GPT-4 수준에 수렴.

### Judge 크기 스케일링

| Judge | 불일치율 | decisive율 | Position bias |
|-------|---------|-----------|--------------|
| Qwen-7B | 78.75% | 21.25% | 0.342 |
| Qwen-14B | 46.85% | 53.15% | 0.435 |
| Qwen-32B | 32.86% | 66.96% | 0.449 |
| GPT-4o-mini | 33.99% | 66.01% | — |

---

## 프로젝트 구조

```
mt_bench_repro/
├── data/
│   ├── en/                         # 영어 baseline (변경 금지)
│   │   ├── answers/                # eval 모델 7개 답변
│   │   └── results/                # judge 집계 결과 CSV
│   └── ko/
│       ├── questions.jsonl         # 한국어 번역 80문항 ✅
│       ├── MT_Bench_번역_완성본.xlsx  # 번역 원본 (4 Batch) ✅
│       ├── MT_Bench_Prompt_Translation.xlsx  # Judge 프롬프트 번역 ✅
│       ├── translation_notes.md    # 번역 가이드라인
│       ├── answers/                # 한국어 답변 (Phase 1)
│       ├── judgments/              # 한국어 채점 결과 (Phase 1)
│       └── results/                # 한국어 집계 CSV (Phase 1)
├── figures/
│   └── en/                         # 영어 실험 figure
├── scripts/
│   ├── run/a100/
│   │   ├── run_generate_ko_a100.sh  # Phase 1: 한국어 답변 생성
│   │   ├── run_judge_ko_a100.sh     # Phase 1: 한국어 judge
│   │   ├── run_generate_phase3_a100.sh  # 영어 답변 생성 (완료)
│   │   └── run_judge_phase3_a100.sh     # 영어 judge (완료)
│   ├── translate/
│   │   ├── validate_translation.py
│   │   ├── back_translate.py
│   │   └── compare_en_ko.py         # Phase 2 스켈레톤
│   └── analysis/
│       └── analyze_translation_validity.py
└── src/mtbench_repro/              # 핵심 Python 패키지
    ├── cli.py                      # 통합 CLI (--lang en/ko)
    ├── prompts.py                  # 영·한 judge 프롬프트
    ├── judge_single.py
    ├── judge_pairwise.py
    └── judge_reference.py
```

---

## 로컬 개발 환경

```bash
git clone https://github.com/kook222/mt_bench_repro.git
cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src

# mock 테스트 (API 없이)
bash scripts/run/local/run_mock_full.sh
```

---

## 인용

```bibtex
@inproceedings{zheng2023judging,
  title={Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena},
  author={Zheng, Lianmin and others},
  booktitle={NeurIPS},
  year={2023}
}
```

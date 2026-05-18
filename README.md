# Korean MT-Bench: 한국어 LLM Judge 신뢰도 벤치마크

한국어 환경에서 MT-Bench 기반 LLM-as-a-Judge 파이프라인의
**번역 타당성(validity)** 과 **현상 재현성(robustness)** 을 검증하는 연구.

> 논문 투고 대상: KCI 등재 학술지 (심사 3~6개월, 영어-한국어 비교 분석 완료 후 투고)

---

## 연구 동기

NeurIPS 2023 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"는 GPT-4 기반
LLM judge의 신뢰도를 영어 환경에서 검증했다. 그러나 **한국어 LLM 평가**에 동일한
파이프라인을 적용하려면 두 가지가 먼저 설득돼야 한다:

1. **번역 타당성**: MT-Bench 번역이 원본의 난이도 구조와 변별력을 보존하는가?
2. **현상 재현성**: 영어에서 관찰된 judge scaling, position bias 패턴이 한국어에서도 동일하게 나타나는가?

이 두 조건이 충족돼야 한국어 LLM 비교 평가(self-judge bias, 모델 랭킹 신뢰도 등)가 의미를 가진다.

---

## 연구 단계

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 0** | 한국어 번역 + validity 검증 | 🔄 진행 중 |
| **Phase 1** | 한국어 데이터로 기존 분석 파이프라인 재실행 | ⏳ 대기 |
| **Phase 2** | 영어-한국어 비교 분석 | ⏳ 대기 |
| **Phase 3** | KCI 학술지 논문 작성 및 투고 | ⏳ 대기 |

---

## Phase 0: 번역 방법 및 품질 검증

### 번역 대상
- MT-Bench 80문항 × 2턴 = **160개 텍스트** 수작업 번역
- reference 답변 포함 39문항의 reference도 번역
- 번역 가이드라인: [`data/ko/translation_notes.md`](data/ko/translation_notes.md)

### 번역 원칙
- 격식체(합쇼체) 사용
- 코드 블록 / 수식 원문 보존
- 전문 용어: 한국어 표기 + 필요시 영어 병기
- 원본의 난이도와 의도를 최우선으로 보존

### 번역 품질 검증 지표

| 검증 | 지표 | 기준 |
|------|------|------|
| Back-translation | BLEU score | 카테고리 평균 BLEU ≥ 0.3 |
| 의미 보존 | LLM semantic score (1~5) | 평균 ≥ 4.0 |
| 변별력 보존 | Spearman ρ (Top-Disc 문항) | ρ ≥ 0.8 |

```bash
# 1. 번역 형식 검증
python3 scripts/translate/validate_translation.py

# 2. 역번역 생성
python3 scripts/translate/back_translate.py

# 3. 품질 검증 리포트
export PYTHONPATH=src
python3 scripts/analysis/analyze_translation_validity.py
```

---

## Phase 1: 한국어 파이프라인 실행 (Phase 0 완료 후)

Phase 0에서 번역 validity가 확인되면, 기존 영어 파이프라인을 한국어 문항으로 재실행한다.

```bash
# A100 서버에서 실행
bash scripts/run/a100/run_generate_ko_a100.sh   # 한국어 답변 생성
bash scripts/run/a100/run_judge_ko_a100.sh       # 한국어 채점
```

---

## Phase 2: 영어-한국어 비교 분석 (Phase 1 완료 후)

```bash
export PYTHONPATH=src
python3 scripts/translate/compare_en_ko.py
```

비교 항목:
- **Judge Scaling Trade-off**: 7B→14B→32B judge에서 랭킹 안정성 변화
- **Position Bias**: A-우선 편향 크기 영어 vs 한국어
- **Top-Disc 랭킹 Spearman ρ**: 변별력 높은 문항에서 영한 랭킹 상관

---

## 영어 Baseline 결과 (Phase 3 데이터 기준)

<details>
<summary>GPT-4o-mini judge 기준 모델 랭킹 (클릭해서 펼치기)</summary>

| 순위 | 모델 | Overall | Writing | Math | Coding |
|------|------|---------|---------|------|--------|
| 1 | Phi-3.5-mini-Instruct | 7.98 | 7.85 | 7.80 | 8.35 |
| 2 | Llama-3.1-8B-Instruct | 7.76 | 7.90 | 6.40 | 8.65 |
| 3 | gemma-2-9b-it | — | — | — | — |
| 4 | Yi-1.5-9B-Chat | — | — | — | — |
| 5 | Mistral-7B-Instruct-v0.3 | 7.20 | 7.75 | 5.65 | 6.25 |
| 6 | Zephyr-7B-beta | — | — | — | — |
| 7 | SOLAR-10.7B-Instruct | 6.82 | 7.35 | 6.00 | 5.65 |

Judge 간 분석 결과: [`data/en/results/`](data/en/results/)
영어 실험 figures: [`figures/en/`](figures/en/)

</details>

---

## 저장소 구조

```
korean_mt_bench/
├── data/
│   ├── en/                         ← 영어 baseline (변경 금지)
│   │   ├── questions.jsonl         ← 원본 80문항 (download_dataset.sh로 다운로드)
│   │   ├── questions_sample.jsonl
│   │   ├── answers/                ← 7개 eval 모델 답변
│   │   ├── judgments/              ← A100 채점 결과 (git 제외)
│   │   └── results/                ← 집계 결과 CSV
│   └── ko/
│       ├── questions.jsonl         ← 한국어 번역 (수작업, Phase 0)
│       ├── answers/                ← 한국어 답변 (Phase 1, git 제외)
│       ├── judgments/              ← 한국어 채점 (Phase 1, git 제외)
│       ├── results/                ← 한국어 집계 결과 (Phase 1 이후)
│       └── translation_notes.md   ← 번역 가이드라인
├── figures/
│   ├── en/                         ← 영어 실험 figure
│   └── ko/                         ← 한국어 실험 figure (Phase 1 이후)
├── scripts/
│   ├── translate/
│   │   ├── validate_translation.py ← 번역 형식 검증
│   │   ├── back_translate.py       ← 역번역 (Claude/GPT-4o)
│   │   └── compare_en_ko.py        ← 영한 비교 분석 (Phase 2)
│   ├── analysis/
│   │   ├── analyze_translation_validity.py  ← 번역 품질 검증
│   │   ├── analyze_self_judge_bias.py
│   │   ├── analyze_position_bias.py
│   │   └── ...
│   └── run/
│       ├── a100/                   ← A100 Kubernetes 실행 스크립트
│       ├── api/                    ← Claude API 실행
│       └── local/                  ← 로컬 mock 테스트
└── src/mtbench_repro/              ← 핵심 Python 패키지
```

---

## 빠른 시작

```bash
git clone https://github.com/kook222/mt_bench_repro.git korean_mt_bench
cd korean_mt_bench
pip install -r requirements.txt
export PYTHONPATH=src

# 원본 영어 질문 다운로드
bash scripts/tools/download_dataset.sh

# 번역 형식 검증 (수작업 번역 완료 후)
python3 scripts/translate/validate_translation.py

# mock으로 전체 파이프라인 테스트
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

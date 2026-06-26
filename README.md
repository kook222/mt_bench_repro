# Korean MT-Bench: LLM-as-a-Judge 신뢰도 한·영 비교 연구

> **KCI 등재 학술지 투고 목표**  
> Base paper: Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023 ([arXiv:2306.05685](https://arxiv.org/abs/2306.05685))

MT-Bench 80문항을 한국어로 번역하고 Qwen2.5 judge 패밀리(7B/14B/32B)로 평가하여, **LLM-as-a-Judge 파이프라인의 언어 일반화 가능성**을 검증합니다.  
영어 baseline과 한국어 실험을 동일 파이프라인으로 실행하고 inconsistency, position bias, parse error rate를 비교합니다.

---

## 연구 진행 상황

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 0** | 한국어 번역 + 역번역 validity 검증 | ✅ 완료 |
| **Phase 1** | 한국어 파이프라인 (답변 생성 + Qwen judge) | ✅ 완료 |
| **Phase 1b** | EXAONE-3.5-32B cross-family judge (EN + KO) | 🔄 실행 중 |
| **Phase 2** | 영어-한국어 비교 분석 | ⏳ Phase 1b 완료 후 |
| **Phase 3** | KCI 논문 작성 및 투고 | ⏳ Phase 2 완료 후 |

---

## 실험 설계

### Eval 모델 (6종)

| 모델 | 파라미터 | 비고 |
|------|---------|------|
| EXAONE-3.5-7.8B-Instruct | 7.8B | LG AI, 한국어 특화 |
| EEVE-Korean-Instruct-10.8B | 10.8B | SOLAR 기반 한국어 fine-tune |
| Llama-3.1-8B-Instruct | 8B | Meta |
| gemma-2-9b-it | 9B | Google |
| Mistral-7B-Instruct-v0.3 | 7B | Mistral AI |
| Phi-3.5-mini-Instruct | 3.8B | Microsoft |

### Judge 모델

| Judge | 종류 | 비고 |
|-------|------|------|
| Qwen2.5-7B-Instruct | Same-family scaling | 완료 |
| Qwen2.5-14B-Instruct | Same-family scaling | 완료 |
| Qwen2.5-32B-Instruct-AWQ | Same-family scaling | 완료 |
| EXAONE-3.5-32B-Instruct-AWQ | Cross-family | 실행 중 |
| GPT-4o-mini | Gold standard | ⏳ 미실행 |

---

## 영어 실험 결과 (EN Baseline)

### Single-Grade Overall Score

> 80문항 × 2턴 = 160 samples 기준, parse failure(-1.0) 제외 평균

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B |
|------|--------:|---------:|---------:|
| EXAONE-3.5-7.8B | **8.3812** | **8.5500** | **8.3208** |
| Phi-3.5-mini | 8.0437 | 8.0875 | 8.0625 |
| Llama-3.1-8B | 7.8937 | 8.1687 | 7.7125 |
| gemma-2-9b | 7.8688 | 8.0312 | 8.0943 |
| Mistral-7B | 7.4500 | 7.4875 | 7.0875 |
| EEVE-10.8B | 7.1937 | 6.8875 | 6.7188 |

### Pairwise Inconsistency & Position Bias (EN)

> Inconsistency: AB/BA swap 판정 불일치율 (`winner == "inconsistent"`)  
> 1st-pos bias: 두 판정 모두 첫 번째 위치 모델 선호 (`verdict_ab=A, verdict_ba=A`)

| Judge | 총 pair | Inconsistency | 1st-pos bias |
|-------|--------:|--------------:|-------------:|
| Qwen-7B  | 1,200 | **79.2%** (951/1200) | 52.5% (630/1200) |
| Qwen-14B | 1,200 | 45.1% (541/1200) | 35.5% (426/1200) |
| Qwen-32B | 1,198 | 31.0% (371/1198) | 22.3% (267/1198) |

### Parse Failure (EN)

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade_ref | 5 | 174 | 2.9% |
| Qwen-32B | single_grade | 2 | 960 | 0.2% |
| Qwen-32B | pairwise | 2 | 2,400 | 0.1% |

---

## 한국어 실험 결과 (KO)

### Single-Grade Overall Score

| 모델 | Qwen-7B | Qwen-14B | Qwen-32B |
|------|--------:|---------:|---------:|
| EXAONE-3.5-7.8B | **7.7296** | **8.0469** | **8.1000** |
| gemma-2-9b | 6.9383 | 7.2704 | 7.2812 |
| EEVE-10.8B | 6.6643 | 6.3906 | 6.3250 |
| Phi-3.5-mini | 6.4178 | 5.6352 | 5.4188 |
| Llama-3.1-8B | 6.3523 | 5.7987 | 5.7170 |
| Mistral-7B | 5.4200 | 5.0506 | 4.6813 |

### Pairwise Inconsistency & Position Bias (KO)

| Judge | 총 pair | Inconsistency | 1st-pos bias |
|-------|--------:|--------------:|-------------:|
| Qwen-7B  | 1,197 | 44.6% (534/1197) | 40.0% (479/1197) |
| Qwen-14B | 1,200 | 23.0% (276/1200) | 6.3% (76/1200) |
| Qwen-32B | 1,199 | 20.3% (243/1199) | 14.3% (171/1199) |

### Parse Failure (KO)

> KO judge_7B single_grade_ref 33.3% — 7B judge의 한국어 채점 신뢰성 저하를 보여주는 핵심 지표

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade | 42 | 960 | **4.4%** |
| Qwen-7B | single_grade_ref | 58 | 174 | **33.3%** |
| Qwen-7B | pairwise | 3 | 2,400 | 0.1% |
| Qwen-14B | single_grade | 5 | 960 | 0.5% |
| Qwen-14B | single_grade_ref | 3 | 174 | 1.7% |
| Qwen-32B | single_grade | 1 | 960 | 0.1% |
| Qwen-32B | pairwise | 1 | 2,400 | 0.0% |

---

## EN vs KO 점수 차이 (Qwen-32B 기준)

| 모델 | EN | KO | 차이 |
|------|---:|---:|-----:|
| EXAONE-3.5-7.8B | 8.3208 | 8.1000 | −0.22 |
| gemma-2-9b | 8.0943 | 7.2812 | −0.81 |
| Phi-3.5-mini | 8.0625 | 5.4188 | −2.64 |
| Llama-3.1-8B | 7.7125 | 5.7170 | −1.99 |
| Mistral-7B | 7.0875 | 4.6813 | −2.41 |
| EEVE-10.8B | 6.7188 | 6.3250 | −0.39 |

---

## Base Paper 주요 지표 (Zheng et al. 2023)

| 지표 | 원 논문 값 | 본 연구 (EN Qwen-32B) |
|------|----------:|--------------------:|
| GPT-4 judge inconsistency | ~16% | 31.0% |
| 1st-position bias | Table 5 참조 | 22.3% |
| Judge-model agreement (GPT-4 vs human) | 80% | — (Phase 2 예정) |

---

## 프로젝트 구조

```
mt_bench_repro/
├── data/
│   ├── en/
│   │   ├── answers/                      # eval 모델 6개 답변 (git 추적)
│   │   └── results/                      # Qwen/GPT judge 집계 CSV
│   └── ko/
│       ├── questions.jsonl               # 한국어 번역 80문항
│       ├── translation_notes.md
│       └── results/                      # KO judge 집계 CSV
├── scripts/
│   ├── run/a100/
│   │   ├── run_generate_phase3_a100.sh   # EN 답변 생성 (완료)
│   │   ├── run_judge_phase3_a100.sh      # EN Qwen judge (완료)
│   │   ├── run_generate_ko_a100.sh       # KO 답변 생성 (완료)
│   │   ├── run_judge_ko_a100.sh          # KO Qwen judge (완료)
│   │   └── run_judge_exaone32b_a100.sh   # EN+KO EXAONE judge (실행 중)
│   ├── run/local/
│   │   └── run_mock_full.sh
│   ├── analysis/
│   │   ├── analyze_phase3.py             # Judge scaling 분석
│   │   ├── analyze_phase345.py           # Judge 간 비교 통합 분석
│   │   └── analyze_translation_validity.py
│   ├── translate/
│   │   ├── validate_translation.py
│   │   ├── back_translate.py
│   │   └── compare_en_ko.py              # Phase 2: EN vs KO 비교
│   └── tools/
│       ├── generate_figures.py
│       ├── prepare_topdisc_subset.py
│       └── download_dataset.sh
└── src/mtbench_repro/
    ├── cli.py
    ├── prompts.py          # EN/KO judge 프롬프트
    ├── generate.py
    ├── judge_single.py
    ├── judge_pairwise.py
    ├── judge_reference.py
    ├── aggregate.py
    ├── io_utils.py
    ├── schemas.py
    └── client.py
```

---

## 로컬 개발 환경

```bash
git clone <repo>
cd mt_bench_repro
pip install -r requirements.txt
export PYTHONPATH=src

# mock 테스트
bash scripts/run/local/run_mock_full.sh

# 번역 형식 검증 (Phase 0)
python3 scripts/translate/validate_translation.py

# 역번역 생성 (Phase 0)
python3 scripts/translate/back_translate.py
```

---

## 인용

```bibtex
@inproceedings{zheng2023judging,
  title     = {Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena},
  author    = {Zheng, Lianmin and Chiang, Wei-Lin and Sheng, Ying and others},
  booktitle = {Advances in Neural Information Processing Systems},
  year      = {2023}
}
```

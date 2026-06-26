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

3개 judge 모두에서 EXAONE-3.5-7.8B가 1위를 유지한다. 2~4위는 judge에 따라 Phi/Llama/gemma 간 순위가 소폭 변동하나, EEVE-10.8B가 일관되게 최하위다. Judge 크기가 커질수록 절대 점수는 일부 모델에서 변동하지만, 1위·최하위 순위는 안정적으로 유지된다.

### Pairwise Inconsistency & Position Bias (EN)

> Inconsistency: AB/BA swap 판정 불일치율 (`winner == "inconsistent"`)  
> 1st-pos bias: 두 판정 모두 첫 번째 위치 모델 선호 (`verdict_ab=A, verdict_ba=A`)

| Judge | 총 pair | Inconsistency | 1st-pos bias |
|-------|--------:|--------------:|-------------:|
| Qwen-7B  | 1,200 | **79.2%** (951/1200) | 52.5% (630/1200) |
| Qwen-14B | 1,200 | 45.1% (541/1200) | 35.5% (426/1200) |
| Qwen-32B | 1,198 | 31.0% (371/1198) | 22.3% (267/1198) |

Judge 크기가 클수록 inconsistency와 1st-position bias가 모두 감소한다. Qwen-7B는 10쌍 중 약 8쌍에서 AB/BA 판정이 뒤집히는 수준으로, pairwise 결과를 신뢰하기 어렵다. Qwen-32B는 31.0%로 낮아지지만 여전히 원 논문의 GPT-4 기준보다 높아 judge 선택이 신뢰도에 미치는 영향을 보여 준다.

### Parse Failure (EN)

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade_ref | 5 | 174 | 2.9% |
| Qwen-32B | single_grade | 2 | 960 | 0.2% |
| Qwen-32B | pairwise | 2 | 2,400 | 0.1% |

영어 실험에서는 parse failure가 전반적으로 낮다. Qwen-7B의 reference-guided 채점(single_grade_ref)에서 2.9%로 가장 높고, 나머지는 모두 0.3% 미만이다.

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

EXAONE-3.5-7.8B이 한국어에서도 1위를 유지한다. EN 대비 순위 변동이 두드러지는데, EN에서 2위였던 Phi-3.5-mini가 Qwen-32B 기준 4~5위로 급락하고, gemma-2-9b가 EN 4위에서 KO 2위로 부상한다. 반면 Mistral-7B는 EN·KO 모두 하위권으로 일관되다.

### Pairwise Inconsistency & Position Bias (KO)

| Judge | 총 pair | Inconsistency | 1st-pos bias |
|-------|--------:|--------------:|-------------:|
| Qwen-7B  | 1,197 | 44.6% (534/1197) | 40.0% (479/1197) |
| Qwen-14B | 1,200 | 23.0% (276/1200) | 6.3% (76/1200) |
| Qwen-32B | 1,199 | 20.3% (243/1199) | 14.3% (171/1199) |

KO에서는 EN보다 inconsistency 수치가 전반적으로 낮게 나타난다. 단, Qwen-7B는 parse failure가 많아 valid pair 수가 줄어든 효과가 일부 반영됐을 가능성이 있다. Qwen-14B의 1st-pos bias가 6.3%로 32B(14.3%)보다 낮은 점은 이상값으로, 한국어에서의 judge별 판정 패턴 차이를 추가 분석할 필요가 있다.

### Parse Failure (KO)

> Qwen-7B single_grade_ref 33.3% — 소형 judge의 한국어 포맷 준수 능력 저하를 보여주는 핵심 지표

| Judge | Type | 실패 | 전체 | 실패율 |
|-------|------|-----:|-----:|-------:|
| Qwen-7B | single_grade | 42 | 960 | **4.4%** |
| Qwen-7B | single_grade_ref | 58 | 174 | **33.3%** |
| Qwen-7B | pairwise | 3 | 2,400 | 0.1% |
| Qwen-14B | single_grade | 5 | 960 | 0.5% |
| Qwen-14B | single_grade_ref | 3 | 174 | 1.7% |
| Qwen-32B | single_grade | 1 | 960 | 0.1% |
| Qwen-32B | pairwise | 1 | 2,400 | 0.0% |

한국어 실험에서 parse failure가 크게 증가한다. Qwen-7B의 single_grade_ref에서 33.3%는 reference-guided 한국어 채점 시 3건 중 1건이 파싱에 실패함을 의미한다. EN에서 0%였던 single_grade도 4.4%로 상승한다. 대부분의 실패 원인은 `[[N]]` 패턴 누락(FORMAT_FAIL)과 중국어 응답(LANG_ERROR)이다. Qwen-32B는 한국어에서도 0.1% 이하로 안정적이다.

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

한국어 특화 모델(EXAONE −0.22, EEVE −0.39)은 EN→KO 점수 하락 폭이 작다. 반면 범용 영어 모델인 Phi-3.5-mini(−2.64), Mistral-7B(−2.41), Llama-3.1-8B(−1.99)는 한국어에서 점수가 급락한다. gemma-2-9b는 −0.81로 영어 모델 중 가장 낮은 하락폭을 보이는데, 다국어 학습 비중의 차이로 추정된다. EEVE는 EN에서 최하위였음에도 KO 하락폭이 작아, 한국어 환경에서의 상대적 경쟁력이 있다.

---

## Base Paper 주요 지표 (Zheng et al. 2023)

| 지표 | 원 논문 (GPT-4 judge) | 본 연구 (EN Qwen-32B) |
|------|---------|--------------------:|
| Inconsistency (1 − consistency) | **35.0%** (Table 2, default prompt) | 31.0% |
| 1st-position bias | **30.0%** (Table 2, default prompt) | 22.3% |
| Judge-model agreement (vs human, S2) | **85%** (non-tie 기준) | — (GPT-4o-mini Phase 2 예정) |

원 논문은 GPT-4를 gold standard judge로, 유사 성능 GPT-3.5 답변 쌍으로 position bias를 측정한 반면, 본 연구는 오픈소스 Qwen-32B judge로 실제 6개 eval 모델 전체 pair를 측정한다. 측정 대상과 judge 종류가 달라 직접 수치 비교는 참고 수준이며, GPT-4o-mini judge 실행 후 동일 조건 비교가 가능하다.

---

## 프로젝트 구조

```
mt_bench_repro/
├── data/
│   ├── en/
│   │   ├── answers/                      # eval 모델 6개 답변 (git 추적)
│   │   └── results/                      # Qwen judge 집계 CSV
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

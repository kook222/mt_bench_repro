# KCI Figure Notes

이 도표 세트는 한국어 LLM 벤치마크/평가 논문에 맞춰 본문 삽입용으로 설계했다.
색 의존도를 줄이고, 흑백 인쇄에서도 구분되도록 marker shape, line style, hatch를 사용한다.

## Suggested Figure Order

1. **Fig. 1. Experimental protocol.**
   방법론 섹션 마지막 또는 실험 설계 첫 부분에 배치한다.
2. **Fig. 2. Qwen-32B single-grade score gap.**
   핵심 결과 1: 범용 영어 모델의 KO 하락폭과 한국어 특화 모델의 완충 효과.
3. **Fig. 3. Pairwise inconsistency and residual position tendency.**
   핵심 결과 2: judge reliability와 position-sensitive residual error.
4. **Fig. 4. Reference-guided scoring and parse failure.**
   핵심 결과 3 및 한계: reference 제공 효과와 KO 7B ref parse failure.

## Caption Drafts

- **Fig. 1.** Overview of the Korean MT-Bench evaluation protocol.
- **Fig. 2.** English and Korean MT-Bench scores under the Qwen-32B judge.
  The annotation denotes the observed KO-EN score gap.
- **Fig. 3.** Pairwise inconsistency and first-position tendency across judge
  settings. First-position share is computed within inconsistent pairs.
- **Fig. 4.** Reference-guided scoring effects and reference-guided
  parse-failure rates across all judge settings. Raw JSONL judgments are
  included for independent audit and recomputation.

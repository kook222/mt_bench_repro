# MT-Bench Paper Study Notes

## Slide 1. MT-Bench / Chatbot Arena 논문 스터디와 재현 실험
- Section: Title
- Purpose: 발표의 범위를 논문 스터디 중심으로 잡고, 뒤에 재현 결과가 이어진다는 점을 알려준다.
- Layout: title

### Speaker Notes
오늘 발표는 랩미팅 발표보다는 논문 스터디에 더 가깝게 구성했습니다.
앞 절반은 Zheng et al.의 MT-Bench / Chatbot Arena 논문을 읽는 시간이 되고,
뒤 절반은 제가 그 프로토콜을 오픈소스 judge 파이프라인으로 어떻게 옮겼는지 설명하는 구조입니다.

따라서 이 발표를 들을 때 중요한 기준은 두 가지입니다.
첫째, 원 논문이 실제로 무엇을 주장했는지 정확히 이해하는 것.
둘째, 제 재현 실험이 그 주장 중 어떤 부분을 지지하고 어떤 부분을 보수적으로 다시 해석하는지 보는 것입니다.

오늘의 최종 메시지는 간단합니다.
MT-Bench는 여전히 좋은 benchmark이고, LLM-as-a-Judge는 유용한 접근입니다.
다만 오픈소스 judge에서는 크기, 아키텍처, pairwise format 안정성, hold-out 일반화까지 함께 봐야 합니다.

## Slide 2. 오늘 발표는 두 개의 세션처럼 들으면 됩니다
- Section: Roadmap
- Purpose: 20분 동안 어떤 질문을 어떤 순서로 볼지 먼저 정렬한다.
- Layout: cards
- Takeaway: 발표를 관통하는 질문: 원 논문의 85% judge-human agreement라는 메시지는 오픈소스 judge 환경에서도 어느 정도 유지되는가?

### Speaker Notes
이 슬라이드는 오늘 발표의 독해법을 정하는 슬라이드입니다.
먼저 원 논문을 이해해야 뒤의 재현 실험이 단순 숫자 나열이 아니라는 점이 보입니다.

발표는 목차를 나열하기보다 하나의 질문을 세 번 나눠 답하는 구조로 듣는 게 좋습니다.
첫째, 원 논문의 주장이 정확히 무엇이었는가.
둘째, 그 프로토콜을 오픈소스 judge 환경으로 옮기면 무엇이 달라지는가.
셋째, 유지되는 결론과 더 이상 강하게 말하면 안 되는 결론은 무엇인가.

발표가 끝나면 세 질문에 답할 수 있으면 됩니다.
원 논문이 왜 중요했는가.
내 저장소가 무엇을 재현 가능하게 만들었는가.
그리고 오픈소스 judge를 실제로 어디까지 믿어도 되는가.

## Slide 3. 1-1. 왜 MT-Bench가 필요했는가
- Section: Base Paper
- Purpose: 원 논문이 기존 벤치마크의 어떤 한계를 문제 삼았는지 잡는다.
- Layout: content
- Visuals:
  - paper_chatbot_arena_ui.png: Original paper Figure 19: Chatbot Arena UI
  - paper_mtbench_winrate_fig3.png: Original paper Figure 3: MT-Bench 평균 승률 곡선
- Slide bullets:
  - 객관식/단답형 중심 벤치마크는 open-ended, multi-turn 대화 품질을 충분히 반영하지 못한다.
  - 사람 선호를 직접 모으는 평가는 비싸고 느려서 반복적인 모델 개발 루프에 맞지 않는다.
  - 그래서 원 논문은 ‘사람 선호를 근사하는 자동 judge’를 중심 문제로 세운다.
- Takeaway: 원 논문의 문제의식은 ‘새 benchmark 하나 만들기’보다 ‘사람 평가를 대체할 실용적 judge 만들기’에 더 가깝습니다.

### Speaker Notes
이 논문의 출발점은 매우 현실적입니다.
대화형 모델을 평가하려면 open-ended 품질을 봐야 하는데, 기존 객관식 벤치마크는 그걸 충분히 담지 못합니다.
그렇다고 사람 평가를 계속 붙이면 속도가 너무 느리고 비용이 큽니다.

그래서 원 논문은 두 축을 동시에 만듭니다.
하나는 controlled benchmark인 MT-Bench이고,
다른 하나는 실제 사용자의 선호 데이터를 모으는 Chatbot Arena입니다.

왼쪽 그림은 Arena의 실제 인터페이스입니다.
사용자는 모델 이름을 모른 채 두 응답 중 더 나은 답변을 고릅니다.
오른쪽 그림은 MT-Bench 점수와 Arena 승률의 관계를 보여줍니다.
즉 원 논문은 benchmark와 in-the-wild preference를 따로따로 두지 않고,
둘의 연결을 통해 judge의 타당성을 설득하려 했습니다.

## Slide 4. 1-2. MT-Bench와 Chatbot Arena는 어떻게 역할을 나눴는가
- Section: Base Paper
- Purpose: MT-Bench와 Arena가 각각 무엇을 측정하고 어떻게 보완하는지 구조적으로 설명한다.
- Layout: content
- Slide bullets:
  - MT-Bench는 8개 카테고리, 80문항의 multi-turn benchmark로 controlled comparison을 담당한다.
  - Chatbot Arena는 실제 사용자 pairwise preference를 통해 ecological validity를 제공한다.
  - 즉 MT-Bench는 재현 가능성, Arena는 현실 적합성을 제공하는 쌍으로 설계되었다.
- Takeaway: 논문의 힘은 MT-Bench 하나가 아니라, benchmark와 crowd preference를 함께 설계했다는 데 있습니다.
- Stat boxes:
  - MT-Bench: 80문항
  - Category: 8개
  - Arena: 익명 pairwise
  - Goal: human preference

### Speaker Notes
MT-Bench와 Arena는 겉으로 보기엔 둘 다 평가 데이터처럼 보이지만 역할이 다릅니다.
MT-Bench는 controlled benchmark입니다. 같은 질문 세트에 대해 여러 모델을 반복적으로 비교할 수 있고,
category별 분석도 가능합니다.

반면 Arena는 통제된 benchmark가 아니라 실제 사용자 환경입니다.
질문도 자유롭고, 사용자는 두 답변을 블라인드로 비교합니다.
이건 benchmark의 재현성은 떨어지지만 현실의 인간 선호를 훨씬 더 잘 반영합니다.

원 논문이 강한 이유는 이 둘을 함께 사용했다는 점입니다.
즉 MT-Bench 점수가 높으면 Arena 승률도 높다는 관계를 보이면서,
benchmark 점수가 단순 인공적인 숫자가 아니라는 걸 설득합니다.

이 발표 뒤쪽에서 제 재현 실험은 MT-Bench 쪽을 중심으로 따라갑니다.
Arena 자체를 재현한 건 아니고, MT-Bench judge reliability를 더 자세히 캐보는 방향으로 확장했다고 보시면 됩니다.

## Slide 5. 1-3. 원 논문은 judge를 어떻게 썼는가
- Section: Base Paper
- Purpose: single, pairwise, reference-guided라는 judge 프로토콜을 분명히 해 둔다.
- Layout: cards
- Slide bullets:
  - 논문은 이 세 judge mode를 동시에 운용하면서, 위치·장문·self-enhancement bias를 별도 분석 대상으로 둔다.
- Takeaway: 원 논문의 결론은 ‘GPT-4가 완벽하다’가 아니라, ‘강한 judge가 인간 선호를 실용적으로 근사한다’입니다.

### Speaker Notes
이 슬라이드는 발표 전체에서 아주 중요합니다.
왜냐하면 뒤의 제 실험도 결국 같은 judge 프로토콜을 구현하고 있기 때문입니다.

Single-answer grading은 0에서 10 사이 점수를 주는 방식이고,
pairwise는 두 응답 중 winner를 직접 고르는 방식입니다.
Reference-guided grading은 특히 수학과 코딩처럼 정답 기준이 필요한 문항에서 중요합니다.

많은 사람이 원 논문을 읽으면서 GPT-4 judge가 그냥 채점기처럼 등장했다고 생각하는데,
실제로는 prompt protocol이 꽤 정교합니다.
그리고 저자들도 bias 문제를 적극적으로 분석합니다.
verbosity bias, position bias, self-enhancement bias를 같이 본다는 점은
원 논문이 생각보다 훨씬 신중한 paper라는 뜻입니다.

이 점이 나중에 제 실험에서도 중요한 기준이 됩니다.
즉 judge 성능을 볼 때 agreement만 보는 게 아니라, 남는 bias의 구조까지 같이 봐야 한다는 겁니다.

## Slide 6. 1-4. 원 논문의 두 핵심 주장은 무엇이었나
- Section: Base Paper
- Purpose: 뒤 재현 실험의 기준점이 되는 원 논문의 핵심 claim 두 개를 먼저 또렷하게 세운다.
- Layout: content
- Visuals:
  - paper_mtbench_agreement_table5.png: Original paper Table 5: judge-human agreement
  - paper_table8_scores.png: Original paper Table 8: MT-Bench model scores
- Slide bullets:
  - 핵심 주장 1: GPT-4 judge는 MT-Bench에서 인간 expert와 non-tie agreement 85%, human-human 81% 수준으로 맞는다.
  - 핵심 주장 2: MT-Bench 점수는 GPT-4 8.99, GPT-3.5 7.94, Vicuna-13B 6.39, LLaMA-13B 2.61처럼 모델 품질 차이를 분명하게 서열화한다.
  - 즉 원 논문은 ‘judge가 인간과 비슷하다’와 ‘점수가 모델 품질을 반영한다’를 동시에 주장한다.
- Takeaway: 뒤의 재현 실험은 결국 이 두 문장을 다시 묻는 작업입니다. agreement가 유지되는가, 그리고 서열이 설득력 있는가?

### Speaker Notes
이 슬라이드는 원 논문을 조금 더 공정하게 읽기 위해 넣었습니다.
원 논문을 처음 읽는 사람에게는 이 슬라이드가 가장 중요합니다.
이 논문이 실제로 주장한 핵심은 두 문장으로 요약할 수 있습니다.

첫째, GPT-4 judge는 인간 expert와 꽤 잘 맞는다.
둘째, MT-Bench 점수는 모델 품질 차이를 꽤 설득력 있게 서열화한다.

왼쪽 Table 5가 첫 번째 주장이고, 오른쪽 Table 8이 두 번째 주장입니다.
이 두 숫자가 붙으면서 LLM-as-a-Judge라는 메시지가 힘을 얻습니다.

뒤쪽 제 재현 실험도 사실은 이 두 질문을 반복합니다.
agreement가 오픈소스 judge에서도 유지되는가,
그리고 서열이 여전히 설득력 있는가.
이 슬라이드가 그 기준점입니다.

## Slide 7. 1-5. 원 논문은 bias를 무시하지 않았다
- Section: Base Paper
- Purpose: 원 논문이 숫자만 좋은 게 아니라 judge 자체를 편향이 있는 시스템으로 다뤘다는 점을 짚는다.
- Layout: compare
- Takeaway: 원 논문의 진짜 장점은 strong judge를 자랑한 데 있지 않고, judge를 measurement system으로 취급했다는 데 있습니다.

### Speaker Notes
원 논문이 이 정도로 널리 인용된 이유는 결국 숫자가 강했기 때문입니다.
하지만 좋은 paper study는 숫자만 반복하면 안 됩니다.
원 논문은 꽤 인상적인 숫자를 보였지만,
동시에 judge bias도 분석했습니다.

특히 position bias와 verbosity bias를 별도 분석 대상으로 둔다는 점이 중요합니다.
이건 저자들이 judge를 그냥 좋은 채점기로 본 게 아니라,
편향을 가진 measurement system으로 봤다는 뜻입니다.

이 관점이 제 재현 실험과 직접 이어집니다.
저도 agreement 숫자만 반복하지 않고,
Phase 3 이후에는 남는 오류가 어떤 편향 형태로 남는지 따로 분석합니다.

그래서 이 슬라이드는 뒤쪽 residual bias 슬라이드의 이론적 다리 역할을 합니다.

## Slide 8. 1-6. 그런데 이 논문이 남긴 열린 질문도 있었다
- Section: Base Paper
- Purpose: 원 논문을 비판적으로 읽고, 왜 내 재현 실험이 필요한지 자연스럽게 연결한다.
- Layout: content
- Slide bullets:
  - judge가 강하다는 사실과 judge가 저렴하고 재현 가능하다는 사실은 다르다.
  - GPT-4는 강력하지만 폐쇄형 API라 비용, 버전 변화, 재현성 문제가 남는다.
  - bias를 분석했어도 ‘오픈소스 judge도 같은 수준까지 갈 수 있는가’는 아직 열려 있었다.
- Takeaway: 내 실험은 원 논문을 부정하는 게 아니라, 그 프로토콜을 오픈소스 환경으로 옮겼을 때 어디까지 유지되는지 묻는 작업입니다.
- Stat boxes:
  - 남은 질문 1: closed judge
  - 남은 질문 2: cost / reproducibility
  - 남은 질문 3: open judge 가능?
  - 내 접근: faithful reproduction + extension

### Speaker Notes
좋은 paper study는 찬양으로 끝나면 안 됩니다.
그래서 여기서 원 논문이 남긴 열린 질문을 짚고 넘어가겠습니다.

첫째, GPT-4 judge는 강력하지만 closed judge입니다.
즉 비용과 버전 drift 문제가 남고, 시간이 지나면 같은 실험을 그대로 다시 하기가 어렵습니다.
둘째, 논문은 bias를 분석했지만, 그 결론을 오픈소스 judge에 바로 옮길 수는 없습니다.

제가 이 저장소에서 한 일은 이 열린 질문을 따라가는 것입니다.
MT-Bench 80문항, single/pairwise/reference 프로토콜은 그대로 유지하되,
judge를 Qwen, InternLM, GPT-4o-mini로 나눠서 다시 본 겁니다.

즉 다음 섹션부터는 ‘원 논문을 얼마나 잘 이해했는가’가 아니라
‘그 이해를 바탕으로 무엇을 재현했고 무엇을 추가로 알게 됐는가’로 넘어갑니다.

## Slide 9. 2-1. 이제 랩미팅으로: 내가 실제로 던진 세 연구 질문
- Section: Reproduction
- Purpose: 뒤 절반의 랩미팅을 연구 질문 단위로 묶어 놓고 듣게 한다.
- Layout: cards
- Slide bullets:
  - 이 뒤 절반은 구현 목록보다 세 개의 연구 질문으로 들으면 가장 잘 들어온다.
- Takeaway: 여기서부터는 taxonomy보다 질문이 중요합니다. 뒤 절반은 ‘좋아진다’보다 ‘어떻게 좋아지고 무엇이 남는가’를 보는 랩미팅입니다.

### Speaker Notes
여기부터는 의도적으로 분위기를 바꿉니다.
앞쪽이 논문 스터디였다면, 여기부터는 랩미팅이라고 생각하시면 됩니다.
하지만 이때 파이프라인을 먼저 보여주면 분위기가 식습니다.
그래서 이 슬라이드에서는 연구 질문만 던집니다.

뒤 절반을 들을 때는 세 질문만 기억하면 됩니다.
judge scaling이 실제로 reliability를 개선하는가.
개선 뒤 남는 오류는 어떤 구조인가.
그리고 그 결론이 cross-family와 hold-out까지 가도 남는가.

파이프라인은 그 다음 슬라이드에서 보여주고,
이 슬라이드는 랩미팅의 문제 정의 슬라이드라고 보시면 됩니다.

## Slide 10. 2-2. 랩미팅 관점의 저장소와 phase 파이프라인
- Section: Reproduction
- Purpose: 코드베이스가 결과 저장소가 아니라 재생성 가능한 연구 파이프라인이라는 점을 보여준다.
- Layout: timeline
- Slide bullets:
  - Phase 1–2는 self-judge bias와 초기 sanity check, Phase 3는 메인 same-family scaling 실험이다.
  - Phase 4–5는 cross-family / external judge 검증, Phase 6은 11개 모델 풀의 exhaustive leave-4-out hold-out이다.
  - README → CSV → raw JSONL로 역추적 가능하게 설계해 결과를 다시 계산할 수 있다.
- Takeaway: Phase 3가 메인 축이고, Phase 4–6이 그 결과를 어디까지 보강하는지 차례로 보여줍니다.

### Speaker Notes
이 저장소는 phase 중심으로 읽는 게 가장 좋습니다.
Phase 1과 2는 준비운동이고, 진짜 메인은 Phase 3입니다.
Qwen 7B/14B/32B를 같은 family에서 비교하면서 judge scaling을 관찰합니다.

Phase 4와 5는 보조 검증입니다.
InternLM20B와 GPT-4o-mini를 붙여서 Qwen에서 보인 broad rank pattern이 완전히 family-specific artifact인지 확인합니다.
Phase 6은 tinyMT-Bench를 same-set 상한에만 머물지 않게 하려고,
11개 모델 풀 전체에서 leave-4-out hold-out 330 split을 전부 돌린 단계입니다.

저장소 구조도 phase를 따라가도록 만들었습니다.
README에서 주장한 문장은 data의 CSV와 raw JSONL로 되짚어 볼 수 있게 구성했고,
paper와 presentation도 같은 figure를 재사용합니다.

## Slide 11. 3-1. Phase 1–2: 왜 self-judge를 믿으면 안 되는가
- Section: Results
- Purpose: 메인 실험에 들어가기 전에 self-judge bias와 초기 sanity check를 짚는다.
- Layout: content
- Visuals:
  - fig0_phase1_scores.png: Phase 1 self-judge category scores
  - fig2_overall_rankings.png: 초기 overall ordering sanity check
- Slide bullets:
  - 원 논문은 strong judge의 가능성을 보였지만, 이 슬라이드는 오픈소스 self-judge로 가면 바로 어떤 함정이 생기는지 보여줍니다.
  - Qwen2.5-7B self-judge는 overall 8.12인데 Math·Coding은 각각 8.80으로 튀며 자기 강점을 과대평가한다.
  - 외부 14B judge를 붙이면 broad ranking은 정리되지만, pairwise inconsistency 자체는 여전히 높다.
  - 즉 문제는 ‘judge를 쓰느냐’가 아니라 ‘어떤 judge를 어떻게 쓰느냐’이다.
- Takeaway: 이 슬라이드의 결론은 외부 judge가 필요하다는 것이지, 이미 충분하다는 뜻은 아닙니다.

### Speaker Notes
Phase 1과 2는 본격 결과라기보다 문제 제기 단계입니다.
Self-judge를 해보면 Qwen2.5-7B가 특히 Math와 Coding에서 높은 점수를 주는 경향이 드러납니다.
즉 자신의 강점 영역을 과대평가할 가능성이 있습니다.

그래서 외부 judge를 붙이지만, 거기서도 문제가 끝나지 않습니다.
ranking은 어느 정도 정리되지만 pairwise inconsistency가 여전히 높습니다.
이건 judge reliability 문제를 단순히 self-vs-external로 읽으면 안 된다는 뜻입니다.

이 슬라이드의 역할은 뒤 메인 실험의 필요성을 만드는 것입니다.
왜 32B 같은 더 큰 judge를 보고, 왜 cross-family와 hold-out까지 보게 되었는지 설명하는 출발점이라고 생각하시면 됩니다.

## Slide 12. 3-2. Phase 3: Qwen same-family scaling이 메인 결과다
- Section: Results
- Purpose: judge scaling이 reliability에 주는 효과를 가장 강하게 보여준다.
- Layout: content
- Visuals:
  - fig4_judge_scaling.png: Judge scaling과 카테고리별 inconsistency
  - fig5_phase3_scores.png: Phase 3 single-grade 점수 분포
- Slide bullets:
  - Pairwise inconsistency는 7B 78.75% → 14B 46.85% → 32B 32.86%로 단조 감소한다.
  - Single-grade score range도 0.84 → 1.12 → 1.48로 확대되어 모델 간 변별력이 커진다.
  - 따라서 메인 결론은 ‘Qwen same-family empirical trend’로 읽는 것이 맞다.
- Takeaway: 이 결과만 보면 ‘judge를 키우면 된다’는 결론이 나올 것 같습니다. 그런데 남는 오류를 들여다보면 예상과 다른 패턴이 나옵니다.
- Stat boxes:
  - 7B: 78.75%
  - 14B: 46.85%
  - 32B: 32.86%
  - 핵심: same-family trend

### Speaker Notes
이 슬라이드가 이번 재현 실험의 중심입니다.
Qwen judge를 7B에서 14B, 32B로 키우면 pairwise inconsistency가 크게 줄어듭니다.
그리고 score range도 넓어져서 모델 간 차이를 더 잘 구분합니다.

이 결과는 꽤 강합니다. 하지만 표현은 조심해야 합니다.
이건 universal scaling law가 아닙니다.
정확하게는 Qwen2.5 동일 family 안에서 judge가 커질수록 reliability가 좋아졌다는 empirical trend입니다.

저는 발표에서 이 보수적 framing을 일부러 유지할 겁니다.
왜냐하면 뒤의 InternLM과 GPT-4o-mini가 이 메인 결과를 보조하긴 하지만,
Phase 3 자체를 완전히 대체하진 않기 때문입니다.

하지만 이 슬라이드를 그냥 ‘스케일링이 먹혔다’로 끝내면 재미가 없습니다.
바로 다음 슬라이드에서 남는 오류의 구조를 보면,
단순 개선 서사가 아니라 훨씬 더 흥미로운 이야기가 나오기 때문입니다.

## Slide 13. 3-3. 남는 오류는 무엇이며, 앙상블은 도움이 되는가
- Section: Results
- Purpose: inconsistency가 줄어든 뒤에도 어떤 bias가 남는지와 practical ensemble 결론을 보여준다.
- Layout: content
- Visuals:
  - fig11_position_bias.png: Residual position bias
  - fig13_ensemble_v2.png: Majority vs abstain ensemble
- Slide bullets:
  - 32B judge의 남은 불일치 중 94.93%가 first-position win으로 연결되어 residual bias가 위치 편향으로 농축된다.
  - 단순 majority ensemble은 오히려 58.63%로 나빠지고, abstain ensemble만 24.70%까지 낮춘다.
  - 즉 더 큰 judge는 더 일관적이지만, 남는 오류를 이해하지 않으면 운영에 바로 쓰기 어렵다.
- Takeaway: 놀라운 지점은 여기입니다. judge가 커질수록 오류가 사라지는 게 아니라, 남는 오류가 first-position bias로 농축됩니다.

### Speaker Notes
많은 발표가 inconsistency가 줄었다는 데서 멈추는데,
저는 남는 오류의 구조까지 보는 게 더 중요하다고 생각합니다.
32B judge는 전체 inconsistency는 많이 줄였지만,
남아 있는 불일치는 거의 first-position bias와 연결됩니다.

이건 의미가 큽니다.
‘더 큰 judge = 더 공정한 judge’가 아니라,
‘더 큰 judge = 더 일관적인 judge, 그러나 남는 오류는 특정 편향 형태로 집중될 수 있음’이기 때문입니다.

앙상블 결과도 비슷한 교훈을 줍니다.
작은 judge를 그냥 다수결로 합치면 오히려 오염됩니다.
반면 abstain ensemble은 inconsistent 케이스를 기권 처리해서 훨씬 낫습니다.

즉 이 슬라이드는 judge 연구를 모델 비교로만 읽으면 안 되고,
evaluation system design 문제로도 읽어야 한다는 걸 보여줍니다.

## Slide 14. 3-4. 보조 검증 A: InternLM judge는 어디까지 믿을 수 있는가
- Section: Results
- Purpose: InternLM2.5-7B/20B를 따로 떼어 놓고, open-weight cross-family judge의 품질을 평가한다.
- Layout: content
- Visuals:
  - fig17_phase4_internlm.png: Phase 4: InternLM judge summary
- Slide bullets:
  - InternLM2.5-20B는 Qwen32와 Spearman ρ=0.893로 broad ranking을 유지하지만, pairwise inconsistency는 47.44%로 더 높다.
  - 즉 cross-family sanity는 되지만, same-family Qwen32만큼 pairwise가 안정적이진 않다.
  - 반면 InternLM2.5-7B는 pairwise error가 72.62%라서 winner format 자체를 안정적으로 못 지키는 수준이다.
- Stat boxes:
  - Qwen32↔InternLM20B: ρ=0.893
  - InternLM20B pairwise: 47.44%
  - InternLM7B error: 72.62%
  - 해석: sanity check

### Speaker Notes
이 슬라이드는 Phase 3 메인 결과를 보조하는 슬라이드입니다.
InternLM을 따로 분리한 이유는, 사용자 요청대로 Phase 4도 Phase 3처럼 독립적으로 읽히게 만들기 위해서입니다.

20B 모델은 broad ranking을 꽤 잘 유지합니다.
즉 Qwen32의 메인 서열이 완전히 family-specific artifact는 아니라는 보조 증거가 됩니다.
하지만 pairwise inconsistency는 47.44%로 여전히 높아서,
실제 운영 judge로는 더 noisy하다고 읽어야 합니다.

그리고 7B의 실패는 매우 교육적입니다.
이건 단순히 점수가 낮다는 수준이 아니라,
pairwise verdict format을 안정적으로 못 지켜 파싱 가능한 winner를 자주 내지 못합니다.

그래서 이 슬라이드의 결론은 명확합니다.
InternLM20B는 cross-family sanity check로는 의미가 있지만,
open-weight judge라면 아무거나 pairwise에 올릴 수 있다는 뜻은 아닙니다.

## Slide 15. 3-5. 보조 검증 B: GPT-4o-mini는 가장 강한 외부 기준점인가
- Section: Results
- Purpose: closed-weight external judge로서 GPT-4o-mini가 Qwen32의 메인 결과를 얼마나 잘 지지하는지 본다.
- Layout: content
- Visuals:
  - fig18_phase5_gpt4omini.png: Phase 5: GPT-4o-mini judge summary
- Slide bullets:
  - GPT-4o-mini는 Qwen32와 Spearman ρ=0.964, Kendall τ=0.905로 가장 비슷한 rank pattern을 보였다.
  - Pairwise inconsistency도 33.99%로 Qwen32의 32.86%와 거의 비슷한 수준이었다.
  - 다만 exact pairwise agreement는 0.580이라, question-level decision까지 완전히 동일하다고 해석하면 과하다.
- Takeaway: GPT-4o-mini는 메인 결과를 가장 잘 지지하는 외부 judge이지만, 그 자체로 Phase 3 메인을 대체하는 것은 아닙니다.
- Stat boxes:
  - Qwen32↔GPT-4o-mini: ρ=0.964
  - Kendall τ: 0.905
  - GPT pairwise: 33.99%
  - exact agreement: 0.580

### Speaker Notes
Phase 5는 Phase 4와 다르게 외부 API judge를 붙인 결과입니다.
저는 이 슬라이드를 일부러 별도로 뺐습니다.
왜냐하면 GPT-4o-mini는 지금 저장소에서 가장 강한 external reference point이기 때문입니다.

Qwen32와 Spearman 0.964, Kendall 0.905면 broad rank pattern은 거의 유지된다고 읽어도 됩니다.
pairwise inconsistency도 33.99%로 Qwen32와 매우 가깝습니다.

하지만 exact pairwise agreement가 0.580이라는 점은 꼭 같이 말해야 합니다.
즉 “전체 서열의 큰 흐름은 잘 맞지만, 개별 질문 단위 판단까지 완전히 같진 않다”는 뜻입니다.

그래서 이 슬라이드는 external validation의 가장 강한 근거이면서도,
동시에 claim boundary를 가르쳐 주는 슬라이드입니다.

## Slide 16. 3-6. Phase 6: tinyMT-Bench는 같은 집합과 hold-out에서 다르게 읽어야 한다
- Section: Results
- Purpose: 문항 축소 결과를 same-set과 exhaustive hold-out으로 나눠 읽게 한다.
- Layout: content
- Visuals:
  - fig9_tiny_mt_bench.png: same-set tinyMT-Bench
  - fig15_tiny_mt_bench_generalization.png: 330-split repeated hold-out generalization
- Slide bullets:
  - same-set에서는 Top-Disc-40이 ρ=1.000, Top-Disc-25도 ρ=0.964로 매우 강한 upper bound를 보였다.
  - 하지만 11개 모델 풀의 330 split hold-out으로 가면 40문항 mean ρ는 Qwen 0.968, InternLM20B 0.922, GPT-4o-mini 0.959다.
  - 60문항에서는 세 judge 모두 mean ρ≥0.97로 더 안정적이어서, 운영점으로는 60문항이 안전하다.
- Stat boxes:
  - 40문항: same-set 상한
  - 40문항 hold-out: judge별 편차
  - 60문항: 세 judge 모두 안정
  - Split: 330

### Speaker Notes
tinyMT-Bench는 제 발표에서 가장 조심스럽게 설명해야 하는 결과입니다.
same-set에서는 Top-Disc-40이 정말 아름답게 나옵니다. full-80 ranking을 그대로 보존합니다.
하지만 그건 선택과 검증이 같은 모델 집합에서 이뤄졌기 때문에 upper bound로 읽어야 합니다.

그래서 repeated hold-out을 했습니다.
11개 모델 중 4개를 test로 두는 모든 조합, 즉 330 split을 전부 돌렸고,
각 split마다 random subset 200개와 Top-Disc를 비교했습니다.

그 결과 40문항도 강하지만 judge에 따라 편차가 있습니다.
반면 60문항은 세 judge 모두 mean rho가 0.97 이상으로 안정적입니다.
그래서 이제는 ‘40문항이 항상 충분하다’보다
‘same-set에서는 40문항이 upper bound이고, 운영점으로는 60문항이 더 안전하다’라고 말하는 게 맞습니다.

## Slide 17. 4. 무엇을 믿고 무엇을 조심해야 하나
- Section: Wrap-up
- Purpose: 주장의 범위를 통제하고 paper study의 비판적 결론을 남긴다.
- Layout: compare
- Takeaway: 좋은 재현 연구는 강한 결과를 크게 말하되, 그 결과가 무너지기 쉬운 경계를 먼저 분명히 그어 줍니다.

### Speaker Notes
이 슬라이드는 paper study 발표의 결론입니다.
원 논문을 그대로 믿는 것도, 제 재현 결과를 과장하는 것도 둘 다 좋은 읽기 방식은 아닙니다.

지금 자신 있게 말할 수 있는 건 세 가지입니다.
Qwen same-family에서는 judge가 커질수록 reliability가 좋아집니다.
GPT-4o-mini와 InternLM20B를 붙여도 broad rank pattern은 대체로 유지됩니다.
그리고 repeated hold-out 기준으로 문항 축소는 60문항 정도가 가장 안전합니다.

반대로 아직 조심해야 할 범위도 분명합니다.
현재 모델 풀은 같은 세대의 중소형 chat 모델 중심입니다.
그래서 이 결론을 70B급, 코딩 특화, 다국어 환경으로 곧바로 일반화하는 건 과합니다.

이 슬라이드는 제 연구의 신뢰도를 높이는 슬라이드라고 생각합니다.
왜냐하면 강한 결과와 claim boundary를 동시에 말해야 발표가 단단해지기 때문입니다.

## Slide 18. 질문 전에: 저장소는 이렇게 읽으면 됩니다
- Section: Q&A
- Purpose: 발표 후 repo를 실제로 볼 사람을 위해 마지막 안내를 남기고 Q&A로 넘긴다.
- Layout: content
- Slide bullets:
  - 원 논문 설명은 `presentation/`의 deck와 notes, 재현 서사는 `README.md`, 원고는 `paper/`를 보면 된다.
  - 수치 검증은 `figures/` 옆 CSV와 `data/` raw judgment를 따라가면 된다.
  - 즉 오늘 발표는 끝나도, repo 안에서 결론을 다시 확인할 수 있게 설계되어 있다.
- Takeaway: 질문 받겠습니다.
- Stat boxes:
  - presentation: today's deck
  - README: story
  - data: evidence
  - paper: final text

### Speaker Notes
마지막 슬라이드는 발표를 마무리하면서 동시에 repo 안내를 하는 슬라이드입니다.
교수님이 발표 후 저장소를 실제로 보신다면 어디부터 보면 되는지를 남기는 역할도 합니다.

오늘 발표는 paper study였기 때문에, 발표가 끝나면 질문이 두 방향으로 나올 겁니다.
원 논문 자체에 대한 질문과, 제 재현 실험에 대한 질문입니다.
전자는 presentation과 paper를 보면 되고,
후자는 README, figures, data를 따라가면 됩니다.

이상으로 발표를 마치고 질문 받겠습니다.

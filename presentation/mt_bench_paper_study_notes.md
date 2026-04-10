# MT-Bench Paper Study Notes

## Slide 1. MT-Bench / Chatbot Arena
논문 리뷰와 내 연구
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

## Slide 2. 오늘 발표는 1부 논문 리뷰, 2부 내 연구입니다
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

## Slide 6. 1-4. judge 점수평가는 실제로 어떻게 흘러가는가
- Section: Base Paper
- Purpose: 답변 생성부터 parse·aggregate까지 judge scoring flow를 한 번에 보여준다.
- Layout: cards
- Slide bullets:
  - generation 단계와 judge 단계의 temperature를 분리해, 답변 다양성과 평가 결정성을 서로 다른 층으로 관리한다.
  - single-grade는 turn1 독립 prompt와 turn2 multi-turn prompt를 따로 써서 turn2 맥락 손실을 막는다.
  - pairwise의 핵심은 winner를 한 번 맞히는 게 아니라, AB/BA swap 뒤에도 유지되는 winner만 채택하는 것이다.
- Takeaway: 이 저장소의 재현성 핵심은 prompt를 흉내 낸 것보다도, parse rule과 aggregation rule을 논문과 맞춘 데 있습니다.

### Speaker Notes
이 슬라이드는 원 논문과 제 저장소 사이를 연결하는 가장 중요한 프로토콜 슬라이드입니다.
청중이 여기서 judge가 실제로 무엇을 입력받고 무엇을 출력하는지 이해해야,
뒤의 scaling과 abstain 결과도 설득력 있게 들립니다.

첫 단계는 답변 생성입니다. 각 모델이 80문항 2-turn 답변을 만들고,
여기에는 temperature 0.7을 둬서 응답 다양성을 허용합니다.
두 번째 단계는 judge 호출입니다. judge는 반대로 temperature 0.0으로 고정해서
평가 noise를 줄입니다.

single-grade에서는 turn1과 turn2를 같은 방식으로 다루지 않습니다.
turn2는 q1, a1, q2, a2를 함께 넣어 multi-turn context로 채점해야
실제 MT-Bench 프로토콜과 맞습니다.

pairwise에서는 AB와 BA를 둘 다 돌립니다.
핵심은 두 번의 호출을 했다는 사실이 아니라, 그 둘을 합칠 때
swap 뒤에도 같은 winner가 유지될 때만 채택한다는 점입니다.
즉 이 연구는 단순 prompt demo가 아니라, parse와 aggregate rule까지 포함한 protocol reproduction입니다.

## Slide 7. 1-5. 원 논문의 두 핵심 주장은 무엇이었나
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

## Slide 8. 1-6. 원 논문은 bias를 무시하지 않았다
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

## Slide 9. 1-7. 그런데 이 논문이 남긴 열린 질문도 있었다
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

## Slide 10. 2부. 내 연구
- Section: Reproduction
- Purpose: 앞의 논문 리뷰에서 뒤의 랩미팅 파트로 시선이 전환되는 순간을 명확히 만든다.
- Layout: divider
- Takeaway: 이제부터는 paper claim을 다시 읽는 것이 아니라, 그 claim을 내 judge 실험으로 어디까지 옮길 수 있었는지 보여드립니다.

### Speaker Notes
이 슬라이드는 의도적으로 호흡을 한번 끊는 역할을 합니다.
앞 절반은 원 논문 리뷰였고, 여기부터는 제 연구 발표입니다.
그래서 청중이 화면만 봐도 세션이 전환됐다는 걸 느끼게 하고 싶었습니다.

짧게 말하면 앞 절반에서 만든 기준점을 이제 검증 대상으로 바꾸는 순간입니다.
원 논문의 두 핵심 주장, 그리고 열린 질문을 들고 제 실험으로 넘어갑니다.

## Slide 11. 2-1. 내가 실제로 검증한 네 연구 질문
- Section: Reproduction
- Purpose: 뒤 절반의 내 연구 파트를 연구 질문 단위로 묶어 놓고 듣게 한다.
- Layout: cards
- Slide bullets:
  - 즉 뒤 절반은 phase log가 아니라 RQ1부터 RQ4까지의 답을 찾아가는 흐름으로 들으면 가장 자연스럽다.
- Takeaway: 이 뒤 절반은 phase 로그가 아니라 네 개의 연구 질문을 차례로 답하는 발표로 듣는 것이 가장 좋습니다.

### Speaker Notes
여기부터는 의도적으로 분위기를 바꿉니다.
divider 슬라이드에서 세션 전환은 이미 끝났습니다.
이 슬라이드는 더 이상 전환을 선언하는 슬라이드가 아니라,
뒤 절반 전체를 묶는 네 연구 질문을 정리하는 슬라이드입니다.

뒤 절반을 들을 때는 네 질문만 기억하면 됩니다.
judge scaling이 실제로 reliability를 개선하는가.
개선 뒤 남는 오류는 어떤 구조인가.
작은 judge들을 합칠 때 어떤 집계 규칙이 더 나은가.
마지막으로 문항 수를 줄여도 서열이 남는가.

즉 이 슬라이드는 랩미팅 파트의 문제 정의 슬라이드라고 보시면 됩니다.

## Slide 12. 2-2. 실험은 어떤 순서로 진행했는가
- Section: Reproduction
- Purpose: Phase 1부터 Phase 6까지의 실험 순서를 한 장에서 보여준다.
- Layout: timeline
- Slide bullets:
  - P1 self-judge 기준선으로 자기평가 편향을 확인하고, P2에서 외부 14B judge로 초기 sanity check를 했다.
  - P3는 Qwen 7B/14B/32B를 이용한 메인 judge scaling 실험이고, 여기서 RQ1과 RQ2의 핵심 수치가 나온다.
  - P3의 출력 위에서 RQ3로 ensemble decision rule을 비교하고, P4·P5는 Qwen 결과가 family가 바뀌어도 크게 무너지지 않는지 점검한다.
  - P6는 11개 모델 풀의 repeated hold-out으로 RQ4, 즉 tinyMT-Bench subset의 운영 가능성을 same-set upper bound와 분리해 다시 본 단계다.
- Takeaway: 즉 오늘 결과는 self-judge 확인 → main scaling → ensemble / cross-family 보강 → repeated hold-out 검증의 순서로 쌓아 올린 것입니다.

### Speaker Notes
이 슬라이드는 청중이 뒤의 결과를 phase log처럼 듣지 않도록 넣은 진행 순서 슬라이드입니다.
실험이 어떤 순서로 쌓였는지 보여주면, 왜 각 phase가 필요한지 더 잘 이해됩니다.

P1은 self-judge bias를 보는 기준선이고, P2는 외부 14B judge로 broad ranking sanity를 확인하는 단계입니다.
이 두 단계는 문제 정의와 예비 검증 역할을 합니다.

핵심은 P3입니다. Qwen 7B, 14B, 32B를 같은 family 안에서 비교해 judge scaling의 메인 결과를 얻습니다.
이 P3 결과 위에서 RQ3인 ensemble design도 평가합니다.
P4와 P5는 그 메인 결과를 보조 검증하는 단계입니다.
InternLM은 cross-family, GPT-4o-mini는 external anchor입니다.

마지막 P6는 question reduction을 같은 모델셋 안에서만 보지 않기 위해 넣은 단계입니다.
즉 Phase 6가 있어야 tinyMT-Bench 결과를 same-set upper bound와 repeated hold-out evidence로 분리해서 말할 수 있습니다.

## Slide 13. RQ1 준비. Phase 1–2: 왜 self-judge를 믿으면 안 되는가
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
- Takeaway: RQ1을 제대로 보려면 먼저 self-judge 함정을 걷어내야 합니다. 이 슬라이드는 그 준비 단계입니다.

### Speaker Notes
Phase 1과 2는 본격 결과라기보다 문제 제기 단계입니다.
Self-judge를 해보면 Qwen2.5-7B가 특히 Math와 Coding에서 높은 점수를 주는 경향이 드러납니다.
즉 자신의 강점 영역을 과대평가할 가능성이 있습니다.

그래서 외부 judge를 붙이지만, 거기서도 문제가 끝나지 않습니다.
ranking은 어느 정도 정리되지만 pairwise inconsistency가 여전히 높습니다.
이건 judge reliability 문제를 단순히 self-vs-external로 읽으면 안 된다는 뜻입니다.

이 슬라이드의 역할은 뒤 메인 실험의 필요성을 만드는 것입니다.
왜 32B 같은 더 큰 judge를 보고, 왜 cross-family와 hold-out까지 보게 되었는지 설명하는 출발점이라고 생각하시면 됩니다.

## Slide 14. RQ1 답. Phase 3: Qwen judge scaling이 메인 결과다
- Section: Results
- Purpose: judge scaling이 reliability에 주는 효과를 가장 강하게 보여준다.
- Layout: content
- Visuals:
  - fig4_judge_scaling.png: Judge scaling과 카테고리별 inconsistency
  - fig5_phase3_scores.png: Phase 3 single-grade 점수 분포
- Slide bullets:
  - Pairwise inconsistency는 7B 78.75% → 14B 46.85% → 32B 32.86%로 단조 감소한다.
  - Single-grade score range도 0.84 → 1.12 → 1.48로 확대되어 모델 간 변별력이 커진다.
  - 따라서 메인 결론은 ‘Qwen 기반 judge scaling의 same-family empirical trend’로 읽는 것이 맞다.
- Takeaway: RQ1의 현재 답은 예입니다. judge를 키우면 좋아집니다. 하지만 그 다음에는 RQ2를 물어야 합니다.
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

## Slide 15. RQ2. judge가 좋아진 뒤에도 남는 오류는 무엇인가
- Section: Results
- Purpose: 전체 서열과 질문 단위 결정이 분리된다는 점, 그리고 잔여 오류가 순서 민감하게 남는다는 점을 보여준다.
- Layout: content
- Visuals:
  - fig11_position_bias.png: Order-sensitive residual errors
  - fig13_ensemble_v2.png: Majority vs abstain ensemble
- Slide bullets:
  - Qwen32, InternLM20B, GPT-4o-mini는 broad ranking은 대체로 맞지만, exact pairwise winner agreement는 0.50~0.58 수준에 머문다.
  - 특히 Qwen32의 남은 불일치 중 94.93%가 first-position win으로 연결되어, 잔여 오류가 순서 민감한 사례에 집중된다는 점이 드러난다.
  - 즉 ranking validity와 question-level decision cleanliness는 분리해서 읽어야 한다.
- Takeaway: RQ2의 답은 명확합니다. judge가 좋아져도 남는 오류는 단순 노이즈가 아니라 순서 민감성과 운영 리스크의 형태로 남습니다.

### Speaker Notes
Phase 4와 5를 보고 나면 많은 청중이 안심합니다.
Qwen32와 InternLM20B, GPT-4o-mini가 대체로 비슷한 서열을 준다면
이제 judge 문제는 거의 해결된 것처럼 느껴질 수 있습니다.

하지만 바로 이 지점에서 한 걸음 더 들어가야 합니다.
32B judge는 전체 inconsistency는 많이 줄였지만,
남아 있는 불일치는 거의 first-position bias와 연결됩니다.

즉 큰 흐름의 ranking validity와, 개별 질문 수준의 decision cleanliness는 다른 문제입니다.
앙상블 결과도 같은 교훈을 줍니다.
작은 judge를 그냥 다수결로 합치면 오히려 오염되고,
abstain ensemble처럼 불확실성을 관리해야 오히려 더 좋아집니다.

그래서 이 슬라이드는 judge 연구를 단순 모델 비교가 아니라
evaluation system design 문제로 읽어야 한다는 메시지를 줍니다.

## Slide 16. RQ3. 왜 majority보다 abstain이 더 낫나
- Section: Results
- Purpose: 기권 설계를 결과표가 아니라 decision rule 자체로 설명한다.
- Layout: content
- Slide bullets:
  - 각 judge는 pairwise 한 쌍에 대해 {A, B, tie, inconsistent} 중 하나를 남긴다. 여기서 inconsistent는 AB/BA swap이 충돌한 low-confidence case다.
  - 다수결은 inconsistent도 하나의 표처럼 세기 때문에 [inconsistent, inconsistent, A] 같은 경우 winner를 잃고 noisy 7B가 aggregate를 오염시킨다.
  - abstain은 inconsistent를 기권으로 버리고, 남은 decisive vote가 충돌하지 않을 때만 winner를 선언한다.
  - 실제로 604쌍(36%)이 inconsistent→winner로 복구되고, inconsistency는 58.63%→24.70%, decisive rate는 41.37%→75.30%로 개선된다.
- Takeaway: RQ3의 답은 예입니다. 작은 judge를 그냥 다수결로 합치는 것보다, low-confidence vote를 기권으로 다루는 것이 훨씬 더 낫습니다.
- Stat boxes:
  - Majority: 58.63%
  - Abstain: 24.70%
  - Recovered: 604쌍
  - Decisive: 75.30%

### Speaker Notes
이 슬라이드는 제가 이번 발표에서 꼭 분리해서 설명하고 싶은 부분입니다.
많은 청중이 기권 설계를 보면 처음에는 보수적으로 포기한 것처럼 받아들입니다.
하지만 실제로는 반대입니다. 이건 decision rule을 더 정교하게 만든 겁니다.

pairwise 한 쌍에 대해 각 judge는 A, B, tie, inconsistent 중 하나를 냅니다.
여기서 inconsistent는 세 번째 class라기보다, AB/BA swap이 충돌한 low-confidence signal입니다.
그런데 다수결은 이걸 일반 표처럼 셉니다.
그러면 [inconsistent, inconsistent, A] 같은 상황에서도 winner를 잃습니다.

abstain은 다르게 봅니다.
inconsistent를 vote가 아니라 기권으로 두고, 남은 decisive vote가 서로 충돌하지 않을 때만 winner를 선언합니다.
그래서 [inconsistent, inconsistent, A]는 A로 복구되고,
[A, B, inconsistent]는 여전히 inconsistent로 남습니다.

즉 이 설계는 무조건 많이 판단하려는 것도 아니고, 무조건 보수적으로 포기하는 것도 아닙니다.
낮은 품질 judge의 불확실한 표를 집계에서 분리해 measurement noise를 줄이는 방식입니다.
604쌍이 복구되고 decisive rate도 올라간다는 숫자가 바로 그 설계적 의미를 보여줍니다.

## Slide 17. RQ4-1. 문항을 줄여도 같은 모델셋에서는 서열이 남는가
- Section: Results
- Purpose: tinyMT-Bench의 same-set upper bound와 random baseline을 함께 보여준다.
- Layout: content
- Visuals:
  - fig9_tiny_mt_bench.png: same-set tinyMT-Bench upper bound
  - fig7_qsize_sensitivity.png: question count sensitivity of random subsets
- Slide bullets:
  - TopDisc-40은 동일 7개 모델 집합에서 ρ=1.000, TopDisc-25는 ρ=0.964를 달성해 same-set upper bound로는 매우 강하다.
  - 반면 random subset은 평균적으로는 좋아져도 분산이 커서, 30문항에서는 mean ρ≈0.95여도 worst-case는 여전히 흔들린다.
  - 즉 same-set 결과만 보면 40문항으로 절반 절감이 가능해 보이지만, 이 수치만으로 운영점을 확정하면 과감해진다.
- Takeaway: RQ4의 중간 답은 예입니다. 다만 40문항 결과는 same-set upper bound로 읽고, 운영점은 hold-out에서 다시 확인해야 합니다.
- Stat boxes:
  - TopDisc-25: ρ=0.964
  - TopDisc-40: ρ=1.000
  - Random 30: mean ρ≈0.95
  - 해석: same-set upper bound

### Speaker Notes
이제 RQ4로 넘어갑니다.
여기서는 먼저 same-set 결과만 따로 보겠습니다.

TopDisc-40은 동일 7개 모델 집합에서는 ρ=1.000입니다.
그래서 얼핏 보면 80문항을 바로 40문항으로 줄여도 되는 것처럼 보입니다.
하지만 바로 옆 random sensitivity를 보면 질문 수가 줄어들수록 분산이 커지고,
mean과 worst-case가 다르다는 점이 드러납니다.

그래서 이 슬라이드는 일부러 strong same-set result를 보여주되,
동시에 이것이 upper bound라는 점을 같이 말하는 슬라이드입니다.
즉 같은 모델셋 안에서는 40문항이 매우 강하지만,
실제 운영점은 다음 슬라이드의 hold-out까지 보고 정해야 합니다.

## Slide 18. RQ4-2. hold-out과 다른 judge에서 안전한 운영점은 어디인가
- Section: Results
- Purpose: cross-family judge sanity와 repeated hold-out 운영점을 함께 묶어 same-set 결과를 보수적으로 닫는다.
- Layout: content
- Visuals:
  - fig16_phase345_judge_summary.png: Cross-family and external judge summary
  - fig15_tiny_mt_bench_generalization.png: 330-split repeated hold-out generalization
- Slide bullets:
  - InternLM20B는 Qwen32와 ρ=0.893, GPT-4o-mini는 ρ=0.964로 broad ranking pattern을 유지해 Qwen 결과가 완전한 family artifact는 아님을 보여준다.
  - 다만 exact pairwise agreement는 0.50~0.58 수준이라 judge 간 broad consistency와 question-level cleanliness는 여전히 구분해야 한다.
  - Repeated hold-out 330 split에서는 40문항도 strong하지만, 세 judge 모두에서 가장 안전한 운영점은 60문항(mean ρ≈0.998 / 0.995 / 0.972)이다.
- Takeaway: 따라서 RQ4의 최종 답은 ‘부분적으로 예’입니다. 공격적인 40문항은 same-set에서, 더 안전한 운영점은 hold-out 기준 60문항에서 찾는 것이 맞습니다.
- Stat boxes:
  - InternLM20B: ρ=0.893
  - GPT-4o-mini: ρ=0.964
  - 60문항: three-judge safe zone
  - 해석: preliminary but strong

### Speaker Notes
이 슬라이드는 RQ4를 보수적으로 닫기 위한 두 번째 슬라이드입니다.

첫 번째 축은 judge family입니다.
InternLM20B와 GPT-4o-mini가 Qwen32와 broad ranking을 꽤 잘 맞춘다는 점은,
Qwen 결과가 완전히 특이한 artifact는 아니라는 근거를 줍니다.
하지만 pairwise exact agreement는 여전히 낮기 때문에,
질문 수준의 cleanliness까지 같다고 말하면 안 됩니다.

두 번째 축은 hold-out입니다.
330개 split 반복 검증을 보면 40문항도 평균적으로 강하지만,
세 judge 모두에서 가장 안전한 운영점은 60문항 쪽입니다.

그래서 발표에서는 40문항을 headline으로 과장하지 않고,
same-set upper bound와 repeated hold-out safe zone을 분리해서 말하는 것이 핵심입니다.

## Slide 19. 2-3. 네 연구 질문에 대한 현재 답
- Section: Wrap-up
- Purpose: 2부에서 처음 던진 네 연구 질문에 대한 현재 답을 한 장에서 닫아 준다.
- Layout: cards
- Slide bullets:
  - 즉 이 발표의 결론은 ‘오픈소스 judge도 충분하다’가 아니라, strong judge 메시지의 경계와 운영 규칙까지 같이 말할 수 있게 되었다는 데 있습니다.
- Takeaway: 따라서 결론은 단순 재현 성공이 아니라, 오픈소스 judge를 어디까지 믿고 어디서부터 운영 규칙을 붙여야 하는지 실험적으로 말할 수 있게 되었다는 것입니다.

### Speaker Notes
이 슬라이드는 2부 전체를 닫아 주는 슬라이드입니다.
2부가 phase 보고의 나열로 끝나면 연구 질문이 희미해집니다.
그래서 처음 던진 RQ1부터 RQ4까지를 다시 불러와 답하는 방식으로 마무리합니다.

RQ1에 대한 답은 가장 명확합니다.
Qwen judge scaling 결과에서는 reliability 개선이 분명히 관찰됐습니다.
RQ2에 대한 답도 선명합니다.
남는 오류는 단순 noise가 아니라 순서 민감성과 format failure입니다.

RQ3는 decision rule 문제였습니다.
작은 judge를 그냥 다수결로 세면 안 되고, low-confidence vote를 기권으로 다뤄야 한다는 점이 드러났습니다.

RQ4는 부분적으로만 예라고 답해야 정직합니다.
40문항 headline만 남기면 과하고, same-set upper bound와 hold-out safe zone을 같이 말해야 합니다.

이 슬라이드가 들어가면 2부가 phase 보고가 아니라
네 개의 연구 질문에 대한 실험적 답변으로 닫히게 됩니다.

## Slide 20. 질문 전에: 저장소는 이렇게 읽으면 됩니다
- Section: Q&A
- Purpose: 발표 후 repo를 실제로 볼 사람을 위해 마지막 안내를 남기고 Q&A로 넘긴다.
- Layout: content
- Slide bullets:
  - 원 논문 설명은 `presentation/`의 deck와 notes, 재현 서사는 `README.md`, 원고는 `paper/`를 보면 된다.
  - 실험은 Phase 1–2 → Phase 3 → Phase 4–5 → Phase 6 순으로 읽으면 오늘 발표 흐름과 정확히 맞는다.
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
특히 저장소는 phase 순서로 읽으면 오늘 발표의 2부와 같은 흐름이 다시 재생됩니다.

이상으로 발표를 마치고 질문 받겠습니다.

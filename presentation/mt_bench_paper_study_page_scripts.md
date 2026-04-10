# MT-Bench Paper Study Page Scripts

## 1페이지
안녕하세요. 오늘 발표는 `Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena` 논문 발표와, 그 프로토콜을 제가 오픈소스 judge 실험으로 어떻게 옮겼는지 설명하는 두 부분으로 구성했습니다. 앞 절반은 논문 자체를 이해하는 시간이고, 뒤 절반은 제 저장소와 실험이 그 논문에 무엇을 더했는지 설명드리겠습니다.

## 2페이지
전체 흐름부터 짧게 말씀드리겠습니다. 1부에서는 왜 MT-Bench가 필요했는지, Chatbot Arena와 어떤 관계인지, judge를 어떻게 사용했는지, 그리고 이 논문이 남긴 열린 질문이 무엇인지를 정리합니다. 2부에서는 제 실험 파이프라인과 네 개의 연구 질문을 중심으로 오픈소스 judge의 신뢰도를 설명드리겠습니다.

## 3페이지
먼저 1부 논문 발표 파트입니다. 여기서는 제 결과를 먼저 보여주기보다, 원 논문이 어떤 문제를 풀었고 어떤 설계를 했는지를 독립적으로 이해하는 데 집중하겠습니다. 이 기준이 서야 뒤에서 제 실험이 무엇을 그대로 가져오고 무엇을 바꿨는지가 더 선명하게 보입니다.

## 4페이지
원 논문의 출발점은 간단합니다. 기존 객관식 벤치마크만으로는 open-ended 대화 품질과 multi-turn 능력을 잘 평가하기 어렵고, 반대로 사람 평가만으로는 느리고 비쌉니다. 그래서 이 논문은 사람 선호를 실용적으로 근사할 수 있는 자동 judge 체계를 만드는 것을 핵심 문제로 세웠습니다.

## 5페이지
여기서 MT-Bench와 Chatbot Arena는 역할이 다릅니다. MT-Bench는 통제된 benchmark로서 재현 가능한 비교를 제공하고, Chatbot Arena는 실제 사용자 선호를 반영하는 환경을 제공합니다. 즉 하나는 재현성과 분석 가능성, 다른 하나는 현실 적합성을 담당하고, 원 논문은 이 둘을 연결해 judge의 타당성을 설득합니다.

## 6페이지
원 논문에서 judge는 세 가지 방식으로 사용됩니다. single-answer grading은 답변 하나에 절대 점수를 주고, pairwise comparison은 두 응답 중 더 나은 쪽을 고르며, reference-guided grading은 수학과 코딩처럼 정답 기준이 필요한 영역에서 기준 답안을 함께 봅니다. 뒤에서 제 실험도 이 세 프로토콜을 그대로 이어받습니다.

## 7페이지
이 슬라이드는 judge prompt 자체를 설명합니다. single prompt는 질문과 답변, 평가 기준을 주고 `[[rating]]` 형식의 점수를 남기게 하고, pairwise는 두 답변을 비교한 뒤 `[[A]]`, `[[B]]`, `[[C]]` 중 하나를 출력하게 합니다. 또 turn2는 q1-a1-q2-a2를 함께 넣는 multi-turn prompt를 쓰고, math와 coding은 reference answer까지 포함합니다.

## 8페이지
프롬프트 다음에는 실제 채점 파이프라인을 봐야 합니다. 답변 생성은 temperature 0.7로 다양성을 주고, judge는 temperature 0.0으로 고정해 결정성을 높입니다. single은 turn별 점수를 파싱하고, pairwise는 AB와 BA 두 번의 결과를 비교한 뒤 순서를 바꿔도 유지되는 winner만 채택합니다.

## 9페이지
원 논문의 핵심 주장은 두 문장으로 요약할 수 있습니다. 첫째, GPT-4 judge는 인간 expert와 높은 수준의 agreement를 보입니다. 둘째, MT-Bench 점수는 모델 품질 차이를 설득력 있게 서열화합니다. 제 뒤쪽 실험은 결국 이 두 문장이 오픈소스 judge 환경에서도 얼마나 유지되는지를 다시 묻는 작업입니다.

## 10페이지
하지만 원 논문도 judge를 완벽한 채점기로 보지는 않았습니다. position bias, verbosity bias, self-enhancement bias를 별도로 분석하고, judge를 편향이 있는 measurement system으로 다룹니다. 이 관점이 중요하기 때문에 저도 뒤에서 agreement 숫자만이 아니라 남는 오류의 구조까지 같이 보겠습니다.

## 11페이지
그래서 이 논문이 남긴 열린 질문이 생깁니다. GPT-4 judge는 강력하지만 closed API이고, 비용과 버전 drift 문제가 남습니다. 또한 strong judge 결과를 오픈소스 judge에 바로 옮길 수는 없기 때문에, 같은 프로토콜을 오픈소스 환경에서 다시 검증할 필요가 있습니다. 여기까지가 원 논문 발표 파트입니다.

## 12페이지
이제부터는 제 실험입니다. 원 논문의 프로토콜을 유지하면서, judge를 Qwen, InternLM, GPT-4o-mini 축으로 바꾸고, self-judge, scaling, 앙상블, hold-out 검증까지 단계적으로 확장했습니다. 즉 단순 구현이 아니라, 원 논문의 strong judge 메시지를 오픈소스 judge 환경에서 어디까지 유지할 수 있는지를 묻는 실험입니다.

## 13페이지
먼저 제가 그대로 가져온 것과 바꾼 것을 구분하겠습니다. MT-Bench 80문항, 2-turn 구조, single/pairwise/reference-guided judge, AB/BA swap rule은 그대로 유지했습니다. 반면 judge family를 넓히고, phase를 나눠 self-judge부터 hold-out까지 검증하며, raw judgment와 aggregate 결과를 모두 저장소에 남긴 점이 제 확장입니다.

## 14페이지
이 슬라이드는 실험 세팅을 자세히 설명합니다. generation과 judge temperature를 분리했고, judge는 Qwen, InternLM, GPT-4o-mini 조합으로 구성했습니다. 출력도 answer JSONL, single/pairwise/reference judgment JSONL, aggregate CSV, figure까지 모두 따로 저장해서, 발표 수치를 다시 따라가며 검증할 수 있게 만들었습니다.

## 15페이지
제가 실제로 답하려고 한 연구 질문은 네 가지입니다. 첫째, judge를 키우면 정말 더 믿을 만해지는가. 둘째, judge가 좋아진 뒤에도 어떤 오류가 남는가. 셋째, 여러 judge를 합칠 때 다수결이 맞는가. 넷째, 문항 수를 줄여도 모델 서열이 유지되는가. 뒤쪽 슬라이드는 이 네 질문에 대한 답입니다.

## 16페이지
실험은 Phase 1부터 Phase 6까지 순서대로 쌓였습니다. 먼저 self-judge bias를 보고, 외부 14B judge로 sanity check를 한 뒤, Qwen 7B/14B/32B로 메인 scaling 실험을 했습니다. 그 위에서 ensemble rule을 비교하고, InternLM과 GPT-4o-mini로 cross-family와 external validation을 추가했으며, 마지막으로 repeated hold-out으로 question reduction의 운영 가능성을 다시 봤습니다.

## 17페이지
먼저 RQ1의 준비 단계입니다. self-judge는 생각보다 위험합니다. Qwen2.5-7B self-judge는 overall보다 Math와 Coding을 더 높게 평가하는 경향이 있었고, 외부 judge를 붙여도 pairwise inconsistency가 여전히 높았습니다. 그래서 핵심은 judge를 쓸지 말지가 아니라, 어떤 judge를 어떤 규칙으로 쓸지입니다.

## 18페이지
이제 메인 결과인 RQ1입니다. Qwen judge를 7B에서 14B, 32B로 키우면 pairwise inconsistency가 크게 감소했고, single-grade에서는 모델 간 점수 범위도 넓어졌습니다. 따라서 가장 보수적인 해석은, Qwen 동일 패밀리 안에서는 judge scaling이 reliability를 개선하는 empirical trend가 분명히 관찰된다는 것입니다.

## 19페이지
하지만 judge가 좋아졌다고 해서 문제가 끝나는 것은 아닙니다. Qwen32, InternLM20B, GPT-4o-mini는 broad ranking pattern은 꽤 비슷하게 내지만, exact pairwise agreement는 여전히 낮은 편입니다. 특히 Qwen32에서 남은 불일치가 first-position bias와 강하게 연결되면서, 잔여 오류가 단순 noise가 아니라 순서에 민감한 구조를 띤다는 점이 드러났습니다.

## 20페이지
RQ3에서는 앙상블 규칙 자체를 봅니다. pairwise에서 각 judge는 A, B, tie, inconsistent 중 하나를 내는데, inconsistent는 AB와 BA가 충돌한 저신뢰 신호입니다. 다수결은 이 inconsistent까지 표처럼 세어서 오염될 수 있고, 반대로 abstain 설계는 이를 기권으로 두고 decisive vote만 남겨서 더 많은 쌍을 더 깨끗하게 복구합니다.

## 21페이지
RQ4의 첫 번째 단계는 same-set upper bound입니다. 동일한 7개 모델 집합에서는 변별도 기반 TopDisc-40이 rho 1.000을 달성했고, TopDisc-25도 매우 강했습니다. 하지만 random subset 결과를 같이 보면 평균과 worst-case가 다르기 때문에, same-set에서 강하다는 이유만으로 바로 운영 문항 수를 확정하는 것은 위험합니다.

## 22페이지
그래서 RQ4의 두 번째 단계로 hold-out과 다른 judge를 봤습니다. InternLM20B와 GPT-4o-mini도 Qwen32와 broad ranking을 꽤 잘 맞추고, repeated hold-out 330 split 결과를 보면 40문항은 공격적인 upper bound, 60문항은 더 안전한 운영점으로 해석하는 것이 맞습니다. 즉 same-set 결과와 hold-out 결과를 분리해서 말하는 것이 핵심입니다.

## 23페이지
이제 네 연구 질문에 대한 답을 정리하겠습니다. judge scaling은 분명히 개선 효과가 있었고, 남는 오류는 순서 민감성과 format failure처럼 구조화되었습니다. 작은 judge 여러 개를 합칠 때는 majority보다 abstain이 더 나았고, question reduction은 same-set에서는 40문항이 강했지만 hold-out 기준 안전한 운영점은 60문항 쪽이었습니다.

## 24페이지
마지막으로 저장소를 어떻게 읽으면 되는지만 짚고 마치겠습니다. 오늘 발표 구조를 다시 보고 싶으면 presentation과 notes를 보시면 되고, 전체 서사는 README, 최종 논문 버전은 paper를 보면 됩니다. 실제 수치 검증은 figures 옆 CSV와 data raw judgments를 따라가면 됩니다. 이상으로 발표를 마치고 질문 받겠습니다.

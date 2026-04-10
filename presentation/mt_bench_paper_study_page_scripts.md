# MT-Bench Paper Study Page Scripts

## 1페이지
안녕하세요. 오늘 발표는 두 부분으로 구성했습니다. 앞 절반은 `Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena` 논문 자체를 읽는 시간이고, 뒤 절반은 제가 그 프로토콜을 오픈소스 judge 환경으로 어떻게 옮겨 실험했는지 설명드리겠습니다.

## 2페이지
전체 흐름을 먼저 말씀드리겠습니다. 1부에서는 왜 MT-Bench가 필요했는지, Chatbot Arena와 어떤 관계인지, judge를 어떻게 설계했는지, 핵심 결과와 한계가 무엇인지를 봅니다. 2부에서는 같은 프로토콜을 가져와 제가 어떤 judge와 어떤 질문으로 검증했는지 설명드리겠습니다.

## 3페이지
먼저 논문 발표 파트입니다. 여기서는 제 실험을 잠시 내려놓고, 원 논문이 어떤 문제를 풀었고 어떤 설계를 했는지를 하나의 완결된 주장으로 읽겠습니다. 이 기준이 있어야 뒤에서 제 실험이 무엇을 그대로 가져오고 무엇을 추가했는지가 더 선명해집니다.

## 4페이지
원 논문의 출발점은 현실적인 평가 문제입니다. 기존 객관식 벤치마크는 open-ended 대화 품질과 multi-turn 능력을 충분히 반영하지 못하고, 사람 평가만으로는 비용과 시간이 너무 많이 듭니다. 그래서 이 논문은 사람 선호를 실용적으로 근사할 수 있는 자동 judge 체계를 핵심 문제로 세웁니다.

## 5페이지
여기서 MT-Bench와 Chatbot Arena는 역할이 다릅니다. MT-Bench는 통제된 benchmark이고, Arena는 실제 사용자 선호를 모으는 환경입니다. 즉 MT-Bench는 재현성과 분석 가능성을, Arena는 현실 적합성을 담당하고, 원 논문은 이 둘을 연결해 judge의 타당성을 설명합니다.

## 6페이지
judge는 크게 세 가지 방식으로 사용됩니다. single-answer grading은 답변 하나를 절대 점수로 채점하고, pairwise는 두 응답 중 더 나은 쪽을 고르며, reference-guided는 수학과 코딩처럼 기준 답안이 필요한 영역에서 사용됩니다. 이 세 모드가 이후 논문의 실험 설계를 이루는 기본 뼈대입니다.

## 7페이지
이 슬라이드는 prompt 형식을 설명합니다. single prompt는 question, answer, rubric을 넣고 `[[rating]]` 형식의 점수를 남기게 하며, pairwise는 A와 B 두 응답을 비교한 뒤 `[[A]]`, `[[B]]`, `[[C]]` 중 하나를 출력하게 합니다. 즉 judge는 자유롭게 말하는 모델이 아니라, parse 가능한 output contract 안에서 작동합니다.

## 8페이지
다음은 scoring flow입니다. 먼저 답변을 생성하고, judge를 호출하고, 출력을 파싱한 뒤, 마지막에 aggregation rule을 적용합니다. 특히 pairwise는 AB와 BA 두 순서를 모두 돌린 뒤 swap 이후에도 같은 winner가 유지될 때만 채택합니다. 이 점이 위치 편향을 실험적으로 다룰 수 있게 만든 핵심입니다.

## 9페이지
원 논문의 핵심 주장은 두 가지입니다. 첫째, GPT-4 judge는 human expert와 높은 수준의 agreement를 보입니다. 둘째, MT-Bench 점수는 모델 품질 차이를 설득력 있게 서열화합니다. 이 두 메시지가 결합되면서 LLM-as-a-Judge라는 프레임이 매우 강해졌습니다.

## 10페이지
하지만 원 논문도 judge를 완벽한 oracle로 보지는 않았습니다. position bias, verbosity bias, self-enhancement bias를 따로 분석하고, judge를 편향이 있는 measurement system으로 다룹니다. 이 점이 이 논문을 더 강하게 만드는 요소입니다.

## 11페이지
그래서 이 논문은 강한 결과와 동시에 열린 질문도 남깁니다. GPT-4 judge는 강력하지만 closed API라 비용, 버전 drift, 재현성 문제가 남습니다. 또 strong judge 결론을 다른 judge family에 그대로 옮길 수 있는지는 아직 열려 있습니다.

## 12페이지
여기까지의 논문 내용을 한 장으로 정리하면 이렇습니다. 문제의식은 현실적이었고, 기술적 설계는 정교했으며, 핵심 결과는 강했고, 동시에 남은 한계도 분명했습니다. 그래서 이 논문은 LLM-as-a-Judge 연구의 출발점을 만든 기준 논문으로 기억하는 것이 가장 적절합니다.

## 13페이지
이제부터는 제 실험입니다. 원 논문이 제시한 protocol을 그대로 유지하되, judge를 오픈소스 환경으로 옮기고, strong judge 메시지가 어디까지 유지되는지를 더 자세히 보겠습니다.

## 14페이지
먼저 무엇을 그대로 가져왔고 무엇을 바꿨는지 구분하겠습니다. MT-Bench 80문항, single·pairwise·reference-guided judge, AB/BA swap consistency 같은 핵심 protocol은 유지했습니다. 반면 judge family를 Qwen, InternLM, GPT-4o-mini로 넓히고, self-judge, scaling, hold-out까지 추가로 검증했습니다.

## 15페이지
이 슬라이드는 실험 세팅과 산출물 구조입니다. generation과 judging의 temperature를 분리했고, answer JSONL, judgment JSONL, aggregate CSV, figure까지 단계별로 모두 남겼습니다. 그래서 발표에서 보이는 수치는 raw judgment부터 다시 따라가며 검증할 수 있습니다.

## 16페이지
제가 실제로 답하려고 한 연구 질문은 네 가지입니다. judge scaling이 실제로 reliability를 높이는지, judge가 좋아진 뒤에도 어떤 오류가 남는지, 작은 judge 여러 개를 합칠 때 어떤 decision rule이 더 나은지, 그리고 문항 수를 줄여도 서열이 유지되는지입니다.

## 17페이지
실험은 Phase 1부터 Phase 6까지 쌓였습니다. self-judge bias를 확인하고, 외부 14B judge로 sanity check를 한 뒤, Qwen 7B·14B·32B scaling 실험을 진행했습니다. 이후 ensemble rule을 비교하고, InternLM과 GPT-4o-mini로 cross-family와 external validation을 추가했으며, 마지막으로 repeated hold-out으로 question reduction을 다시 검증했습니다.

## 18페이지
RQ1의 답부터 보겠습니다. Qwen judge를 7B에서 14B, 32B로 키우면 pairwise inconsistency가 크게 줄고, single-grade의 score range도 넓어집니다. 따라서 적어도 Qwen 동일 패밀리 안에서는 judge scaling이 reliability를 개선하는 empirical trend가 분명히 관찰됩니다.

## 19페이지
하지만 judge가 좋아졌다고 해서 문제가 끝나는 것은 아닙니다. Qwen32, InternLM20B, GPT-4o-mini는 broad ranking은 꽤 비슷하게 내지만, exact pairwise winner agreement는 여전히 낮은 편입니다. 특히 남는 불일치가 first-position bias와 강하게 연결되면서, residual error가 순서 민감한 구조를 가진다는 점이 드러났습니다.

## 20페이지
RQ3에서는 앙상블 규칙 자체를 봅니다. pairwise에서 inconsistent는 AB와 BA가 충돌한 low-confidence signal인데, 단순 다수결은 이 inconsistent까지 표처럼 세어서 noisy vote를 aggregate에 섞습니다. 반대로 abstain은 이를 기권으로 처리해 더 많은 쌍을 더 깨끗하게 복구합니다.

## 21페이지
RQ4는 question reduction입니다. same-set에서는 TopDisc-40이 매우 강한 upper bound를 보이지만, repeated hold-out까지 보면 더 안전한 운영점은 60문항 쪽입니다. 그래서 40문항은 공격적인 headline, 60문항은 더 안전한 운영점으로 해석하는 것이 맞습니다.

## 22페이지
실험 파트를 정리하면 이렇습니다. 원 논문의 strong judge 메시지는 오픈소스 judge 환경에서도 일부 유지되지만, 더 보수적인 해석과 운영 규칙이 필요합니다. 특히 same-family scaling, residual bias, abstain rule, hold-out safe zone 같은 조건을 같이 봐야 합니다.

## 23페이지
이상으로 발표를 마치겠습니다. 질문은 원 논문 자체의 설계와 의미, 혹은 제 실험이 그 논문을 어디까지 지지하는지 어느 쪽이든 좋습니다. 특히 closed judge 의존성, same-family scaling 해석, residual bias와 hold-out question reduction을 같이 토론해 보면 좋겠습니다.

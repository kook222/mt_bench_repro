# MT-Bench Labmeeting / Paper Study Deck Notes

## Slide 1. 오픈소스 LLM-as-a-Judge의 신뢰도 분석
- Section: Title
- Purpose: 청중에게 오늘 발표의 범위와 정체성을 한 번에 전달한다.
- Bullets:

### Speaker Notes
안녕하세요. 오늘 발표는 두 가지를 동시에 하려는 자리입니다.
첫째는 베이스 논문인 MT-Bench/Chatbot Arena 논문이 정확히 무엇을 제안했는지 다시 이해하는 논문 스터디이고,
둘째는 제가 그 위에서 어떤 재현과 확장을 했는지를 보여드리는 랩미팅입니다.

그래서 발표 구조도 의도적으로 두 층으로 나눴습니다. 먼저 원 논문이 왜 등장했는지,
MT-Bench와 LLM-as-a-Judge가 어떤 문제를 풀려고 했는지 설명한 다음,
그다음부터는 제 Git 저장소 기준으로 phase별 실험을 따라가겠습니다.

오늘의 핵심 메시지는 세 가지입니다.
첫째, 오픈소스 judge도 크기를 키우면 꽤 일관된 평가자가 될 수 있습니다.
둘째, 다만 inconsistency가 줄어드는 것과 공정성이 높아지는 것은 같은 말이 아닙니다.
셋째, 문항 수를 줄이는 문제는 same-set에서는 40문항이 강하지만,
반복 hold-out으로 보면 60문항이 더 안전한 운영점이라는 것입니다.

## Slide 2. 오늘 발표의 큰 흐름
- Section: Roadmap
- Purpose: 20분 동안 무엇을 어떤 순서로 듣게 되는지 먼저 안정적으로 안내한다.
- Bullets:
  - 1부: 베이스 논문이 해결하려는 문제와 핵심 기여
  - 2부: 내 재현 파이프라인과 Phase 1–6 실험 구조
  - 3부: 메인 결과, Git 정리 방식, 그리고 최종 해석

### Speaker Notes
이 슬라이드는 사실상 청중의 집중을 정렬하는 슬라이드입니다.
교수님이나 심사위원이 가장 불편해하는 건 발표자가 논문 설명과 자기 결과를 뒤섞어버리는 경우입니다.
그래서 저는 먼저 베이스 논문을 독립적으로 설명하고, 그다음에 제 실험을 얹는 구조로 가겠습니다.

1부에서는 원 논문이 왜 기존 벤치마크를 문제 삼았는지, MT-Bench와 Chatbot Arena를 왜 만들었는지,
그리고 GPT-4 judge를 어떻게 검증했는지를 짚겠습니다.
2부에서는 제 Git 저장소 관점에서 파이프라인을 설명합니다. 어떤 코드가 있고, 어떤 phase가 있고,
어디까지가 재현이고 어디부터가 확장인지 분리해서 말씀드리겠습니다.
3부에서는 결과 해석과 결론입니다. 특히 same-set 결과와 repeated hold-out 결과를 분리해서 읽는 법,
그리고 제가 이 연구를 어디까지 주장하고 어디서부터는 주장하지 않는지까지 솔직하게 정리하겠습니다.

## Slide 3. 베이스 논문이 해결하려던 문제
- Section: Base Paper
- Purpose: MT-Bench 논문이 기존 평가 패러다임의 어떤 공백을 찔렀는지 이해시킨다.
- Bullets:
  - 기존 객관식 벤치마크는 open-ended, multi-turn 선호를 충분히 반영하지 못함
  - 사람 선호를 직접 모으는 평가는 느리고 비싸서 반복 실험이 어려움
  - 강한 LLM을 judge로 쓰면 인간 선호를 빠르게 근사할 수 있는가가 핵심 질문

### Speaker Notes
원 논문은 아주 명확한 문제의식에서 출발합니다.
기존 LLM 벤치마크, 예를 들어 MMLU나 HELM류는 모델의 핵심 능력을 보긴 하지만,
사용자가 실제로 좋아하는 대화형 응답 품질과는 어긋나는 경우가 많다는 겁니다.

예를 들어 instruction following, multi-turn consistency, 답변의 유용성 같은 건
정답이 하나로 떨어지는 객관식 점수만으로는 잘 측정되지 않습니다.
그렇다고 사람 평가만 계속 하자니 비용과 시간이 너무 큽니다.

그래서 이 논문은 강한 LLM, 당시에는 GPT-4를 judge로 써서
인간 선호를 근사할 수 있는지 체계적으로 보자고 합니다.
즉 질문 자체가 “LLM이 다른 LLM을 채점해도 되나?”가 아니라,
“그 판단이 인간 선호와 어느 정도까지 맞느냐”에 가깝습니다.
이 발표의 나머지 절반은 사실 이 질문을 오픈소스 judge로 옮겨온 작업이라고 보시면 됩니다.

## Slide 4. 베이스 논문의 핵심 자산: MT-Bench와 Chatbot Arena
- Section: Base Paper
- Purpose: 원 논문이 어떤 benchmark와 human evidence를 만들었는지 구조적으로 설명한다.
- Bullets:
  - MT-Bench: 8개 카테고리 × 10문항 = 80개 multi-turn 질문
  - Chatbot Arena: 익명 대결 플랫폼으로 실제 사용자 선호를 대규모 수집
  - 공개 자산: 80문항, 3K expert votes, 30K conversations with human preferences

### Speaker Notes
원 논문의 가장 큰 자산은 단순히 “GPT-4 judge 좋다”는 결론이 아니라,
그 결론을 받쳐주는 데이터와 플랫폼을 같이 만들었다는 점입니다.

첫 번째가 MT-Bench입니다. 80개의 multi-turn 질문으로 구성되어 있고,
카테고리는 writing, roleplay, extraction, reasoning, math, coding, STEM, humanities로 나뉩니다.
여기서 중요한 건 질문이 단순히 다양하기만 한 게 아니라,
최신 챗봇들 간 차이를 드러낼 수 있도록 의도적으로 challenging하게 설계되었다는 점입니다.

두 번째가 Chatbot Arena입니다. 이건 실제 사용자들이 두 모델과 동시에 대화하고,
익명으로 어느 쪽이 더 나았는지 투표하는 구조입니다.
그래서 MT-Bench가 controlled benchmark라면, Arena는 wild preference data에 가깝습니다.
원 논문은 이 두 축을 함께 써서, controlled setting과 real-world preference setting을 동시에 잡았습니다.

## Slide 5. 베이스 논문의 judge 프로토콜과 주요 결론
- Section: Base Paper
- Purpose: 원 논문을 자세히 설명하되, 우리가 재현할 프로토콜이 무엇인지 분명히 한다.
- Bullets:
  - GPT-4 judge는 position, verbosity, self-enhancement bias 가능성을 함께 분석
  - bias 완화 후 GPT-4 judge는 human preference와 80%+ 수준으로 일치
  - 결론: LLM-as-a-Judge는 scalable하고 explainable한 human preference 근사 도구

### Speaker Notes
원 논문이 좋은 이유는 단순히 agreement 숫자만 보여주지 않고,
judge 자체의 한계도 같이 분석했다는 점입니다.
대표적으로 position bias, verbosity bias, self-enhancement bias, 그리고 reasoning limitation을 다룹니다.

그리고 평가 방식도 매우 중요합니다. pairwise 비교를 AB와 BA 순서로 둘 다 돌리고,
불일치하면 conservative하게 처리하는 방식은 이후 재현 연구들의 기본 프로토콜이 됐습니다.
제가 이번 저장소에서 구현한 single-grade, pairwise, reference-guided grading도 결국 이 논문 Appendix를 따라간 구조입니다.

원 논문의 대표 결론은 GPT-4 judge가 인간 선호와 80% 이상 일치한다는 것입니다.
여기서 중요한 포인트는 “인간보다 완벽하다”가 아니라
“인간-인간 agreement와 비슷한 수준”이라는 표현입니다.
즉 이 논문은 인간 평가를 완전히 대체하겠다는 게 아니라,
비싼 인간 평가를 근사하는 scalable surrogate를 제안한 논문으로 읽는 게 맞습니다.

## Slide 6. 베이스 논문에서 무엇을 그대로 가져오고, 무엇을 바꿨는가
- Section: Base Paper
- Purpose: 원 논문의 설계와 내 재현/확장 사이의 대응 관계를 명확히 연결한다.
- Bullets:
  - 그대로 가져온 것: 80문항 MT-Bench, single/pairwise/reference 3종 채점 구조
  - 바꾼 것: GPT-4 judge를 Qwen·InternLM·GPT-4o-mini로 대체하고 raw artifact를 전부 저장
  - 확장한 것: judge scaling, residual bias, ensemble, tinyMT-Bench, exhaustive hold-out

### Speaker Notes
이 슬라이드는 베이스 논문 설명과 제 실험 설명 사이의 브리지입니다.
청중 입장에서는 여기서 ‘그래서 도대체 어디까지가 재현이고, 어디부터가 새로운 분석이냐’를 알고 싶어합니다.

그대로 가져온 요소는 명확합니다.
MT-Bench 80문항, single-grade, pairwise, reference-guided grading이라는 세 가지 judge 프로토콜,
그리고 conservative한 pairwise 해석 철학은 전부 원 논문에서 그대로 이어받았습니다.

바꾼 부분도 분명합니다.
judge를 GPT-4 하나로 고정하지 않고, 오픈소스 Qwen/InternLM과 외부 API judge인 GPT-4o-mini까지 붙였습니다.
그리고 결과를 논문 표 수준이 아니라 raw JSONL, aggregated CSV, figure까지 모두 저장해서
다시 계산 가능한 형태로 만들었습니다.

마지막으로 확장한 질문이 있습니다.
judge scaling, residual position bias, abstain ensemble, tinyMT-Bench, exhaustive hold-out은
원 논문이 직접 답하지 않았던 질문들입니다.
즉 제 작업은 재현으로 시작하지만, 발표의 후반부는 재현 결과 위에 얹은 실증 확장이라고 보시면 됩니다.

## Slide 7. 그렇다면 내가 재현에서 던진 질문은 무엇인가
- Section: Base Paper
- Purpose: 원 논문의 공헌과 한계를 바탕으로 내 연구 질문이 어디서 생겼는지 연결한다.
- Bullets:
  - 원 논문은 강한 closed-source judge 중심, 오픈소스 judge 신뢰도는 미해결
  - judge 크기 변화, residual bias, ensemble, 문항 축소는 충분히 통합 분석되지 않음
  - 따라서 재현 + 확장 질문 4개(RQ1–RQ4)를 새로 세움

### Speaker Notes
여기서부터 제 연구가 왜 필요한지가 나옵니다.
원 논문은 GPT-4 judge가 꽤 잘 맞는다는 걸 보였지만,
실제 연구나 서비스 현장에서는 비용과 접근성 때문에 오픈소스 judge를 쓰고 싶어합니다.
그런데 오픈소스 judge가 어느 정도까지 믿을 만한지에 대해서는
당시에도, 그리고 지금도 아주 체계적인 답이 많지 않습니다.

그래서 저는 원 논문을 그대로 복제하는 데서 멈추지 않고 네 가지 질문을 새로 세웠습니다.
judge 크기가 커질수록 inconsistency가 어떻게 변하는지,
그 과정에서 남는 bias는 무엇인지,
작은 judge 여러 개를 앙상블하면 큰 judge보다 나아지는지,
마지막으로 MT-Bench 문항 수를 줄이면서도 서열을 보존할 수 있는지입니다.

이 지점이 발표에서 아주 중요합니다.
저는 이 발표를 ‘원 논문을 다시 말하는 시간’이 아니라,
‘원 논문의 프레임 위에서 오픈소스 judge를 실제 연구 도구로 쓸 수 있나를 검증하는 시간’으로 잡고 있습니다.

## Slide 8. 내 Git 저장소는 무엇을 재현 가능하게 만들었나
- Section: Repo
- Purpose: 코드베이스가 단순 결과 저장소가 아니라 재현 가능한 연구 파이프라인이라는 점을 보여준다.
- Bullets:

### Speaker Notes
이 슬라이드는 결과보다도 재현성에 관한 슬라이드입니다.
심사나 랩미팅에서 자주 받는 질문이 “그래서 이건 한 번 돌린 실험인가, 아니면 다시 재현 가능한가?”입니다.

제 저장소는 그 점을 의식해서 구성했습니다.
src 안에는 judge client, prompt, aggregation, CLI가 있고,
scripts 안에는 generation, judge 실행, phase별 분석, 발표용 재집계가 있습니다.
data는 raw answer와 judgment, summary csv를 분리해 놓았고,
figures는 논문과 발표에 직접 들어가는 그림을 다시 생성할 수 있게 관리했습니다.

즉 이 repo는 결과를 예쁘게 모아둔 폴더가 아니라,
질문 생성부터 평가, 집계, figure, 원고까지 연결되는 end-to-end 실험 환경입니다.
나중에 마지막 슬라이드에서 다시 보겠지만,
이 구조 덕분에 Phase 6 hold-out도 추가 GPU 없이 재분석만으로 강화할 수 있었습니다.

## Slide 9. Git에서 실제로 어디를 보면 무엇이 보이는가
- Section: Repo
- Purpose: 랩미팅 이후에도 저장소를 읽을 수 있도록 산출물 탐색 경로를 구체적으로 알려준다.
- Bullets:
  - `README.md`는 전체 서사, `data/`는 raw judgment와 요약 CSV, `figures/`는 발표/논문 그림
  - `paper/`에는 blind/non-blind 원고와 PDF, `presentation/`에는 오늘 발표자료와 대본
  - 질문이 생기면 ‘결론 → figure → csv → raw jsonl’ 순서로 역추적하면 됨

### Speaker Notes
이 슬라이드는 발표 이후를 위한 안내서입니다.
랩미팅이 끝나면 보통 교수님이나 동료가 저장소를 직접 열어보게 되는데,
그때 어디부터 봐야 하는지 모르면 좋은 repo도 금방 피곤해집니다.

그래서 저는 산출물을 읽는 경로를 일부러 단순하게 만들었습니다.
README는 서사와 핵심 메시지, data는 raw answer와 judgment, summary CSV,
figures는 발표와 논문에 들어가는 시각화, paper는 원고와 PDF,
presentation은 오늘 발표 파일과 노트를 담습니다.

실제로 검증이 필요할 때는 결론 문장 하나에서 출발해서
해당 figure, 그 figure를 만든 CSV, 마지막으로 raw judgment JSONL까지 역으로 따라가면 됩니다.
이건 단순 정리 습관이 아니라 연구 신뢰도를 높이는 설계라고 생각합니다.

발표에서 이 슬라이드를 짧게라도 넣는 이유는,
제 작업이 단순히 ‘결과가 좋다’가 아니라 ‘다시 확인 가능하다’는 점을 보여주기 위해서입니다.

## Slide 10. Phase 1–6 전체 실험 흐름
- Section: Repo
- Purpose: 발표 후반 결과를 이해할 수 있도록 phase별 역할을 미리 정렬한다.
- Bullets:
  - Phase 1–2: self-judge 편향과 예비 외부 judge sanity check
  - Phase 3: 메인 same-family scaling 실험(Qwen 7B/14B/32B)
  - Phase 4–5: InternLM20B, GPT-4o-mini로 cross-family / external check
  - Phase 6: 11개 모델 풀에서 exhaustive leave-4-out hold-out

### Speaker Notes
이 슬라이드는 발표 전체의 지도 역할을 합니다.
Phase를 숫자로만 나열하면 지루해지기 쉬운데, 각 phase의 존재 이유를 기억해 두시면 뒤 슬라이드가 훨씬 잘 들어옵니다.

Phase 1은 self-judge bias를 직접 확인하는 단계입니다.
Phase 2는 외부 14B judge로 예비 sanity check를 하는 단계고,
여기까지는 말 그대로 파이프라인이 제대로 도는지, 큰 그림이 맞는지 보는 준비운동입니다.

진짜 메인은 Phase 3입니다. Qwen 7B, 14B, 32B를 같은 family 안에서 비교하면서
judge scaling을 관찰합니다. Phase 4와 5는 여기서 나온 결과가 Qwen 고유 현상이 아닌지 보는 보조 검증입니다.
마지막 Phase 6은 문항 축소 결과를 hold-out 모델에서도 다시 보는 단계입니다.

이 발표에서는 Phase 3를 중심축으로 두고,
Phase 4~6이 그 주장을 어디까지 보강하고 어디서부터는 한계를 드러내는지를 보여드리겠습니다.

## Slide 11. Phase 1–2: self-judge 편향과 예비 sanity check
- Section: Results
- Purpose: 외부 judge가 왜 필요한지, 그리고 메인 실험 전 무엇을 확인했는지 보여준다.
- Bullets:
  - Qwen2.5-7B self-judge는 Math·Coding 점수를 과대평가하는 편향이 나타남
  - 외부 14B judge 도입 후 서열은 안정화되지만 pairwise inconsistency는 여전히 높음
  - 즉 ‘오픈소스 judge를 쓰자’보다 ‘어떤 judge를 어떻게 쓰나’가 더 중요함

### Speaker Notes
Phase 1과 2는 메인 결과로 쓰기보다는,
왜 이후의 실험이 필요한지를 보여주는 출발점입니다.

먼저 self-judge를 해보면 Qwen2.5-7B가 자기 자신이나 유사 강점이 있는 카테고리를 높게 주는 경향이 드러납니다.
특히 Math, Coding 쪽이 전형적입니다.
이건 LLM-as-a-Judge를 쓸 때 가장 먼저 피해야 할 함정 중 하나입니다.

그래서 외부 judge를 도입한 게 Phase 2입니다.
그런데 외부 judge를 쓰는 것만으로 문제가 끝나지는 않습니다.
서열은 어느 정도 정리되지만, pairwise inconsistency 자체는 여전히 큽니다.
즉 “self-judge만 아니면 된다”가 아니라,
judge의 크기, 아키텍처, prompt 안정성까지 같이 봐야 한다는 교훈을 줍니다.

이 슬라이드의 결론은 단순합니다.
Phase 1–2는 메인 claim이 아니라, 메인 실험을 설계하게 만든 문제 제기 단계입니다.

## Slide 12. Phase 3: Qwen same-family scaling이 보여준 메인 결과
- Section: Results
- Purpose: Judge 크기 증가가 inconsistency를 어떻게 바꾸는지 메인 empirical trend를 각인시킨다.
- Bullets:
  - Pairwise inconsistency: 7B 78.75% → 14B 46.85% → 32B 32.86%
  - 점수 범위도 0.84pt → 1.13pt → 1.47pt로 확대되어 변별력 증가
  - 메인 claim은 `Qwen same-family empirical trend`로 제한해서 읽어야 함

### Speaker Notes
이 슬라이드가 발표의 중심입니다.
제가 가장 강하게 주장할 수 있는 건 여기서 나온 same-family scaling 결과입니다.

핵심 수치는 아주 단순합니다.
Qwen judge를 7B에서 14B, 다시 32B로 키우면 pairwise inconsistency가 78.75%에서 32.86%까지 단조 감소합니다.
이건 굉장히 큰 변화입니다.
동시에 single-grade 점수 범위도 더 넓어지기 때문에 모델 간 차이를 구분하는 능력도 좋아집니다.

다만 여기서 중요한 건 주장 수위를 지키는 겁니다.
이건 `모든 judge에서 스케일링 법칙이 성립한다`가 아닙니다.
정확히는 `Qwen2.5 동일 패밀리에서는 judge가 커질수록 inconsistency가 줄었다`는 empirical trend입니다.

저는 발표에서도 이 표현을 일부러 보수적으로 쓰고 있습니다.
왜냐하면 이 한 슬라이드가 아무리 강해도, 같은 family의 세 점만 갖고 universal law처럼 말하면 바로 공격 포인트가 되기 때문입니다.
그래서 뒤의 Phase 4와 5는 이 메인 슬라이드를 보조하는 역할로 보시면 됩니다.

## Slide 13. Phase 3 심화: residual bias와 문항 변별도
- Section: Results
- Purpose: 단순히 inconsistency가 줄었다는 사실을 넘어, 남는 오류의 성격까지 설명한다.
- Bullets:
  - 32B judge의 남은 불일치 중 94.9%가 first-position win으로 연결
  - 즉 judge가 커질수록 ‘남는 오류’는 위치 편향 중심으로 농축됨
  - 문항 변별도는 Math·Coding·Reasoning에서 특히 높아 tinyMT의 근거가 됨

### Speaker Notes
이 슬라이드는 개인적으로 가장 흥미로운 결과입니다.
많은 사람이 judge가 커지면 그냥 더 좋아진다고 생각하기 쉬운데,
제가 본 건 조금 다릅니다.

전체 inconsistency는 줄어듭니다. 그런데 남아 있는 불일치만 떼어 놓고 보면,
그 대부분이 first-position bias와 연결됩니다.
즉 작은 judge는 여기저기서 흔들리지만,
큰 judge는 흔들리는 경우 자체는 줄어들되 남는 흔들림이 순서 민감성으로 집중된다는 뜻입니다.

이건 해석상 중요한 포인트입니다.
‘더 큰 judge = 더 공정한 judge’가 아니라,
‘더 큰 judge = 더 일관된 judge, 하지만 남은 불일치의 구조는 더 편향적일 수 있음’입니다.

오른쪽의 문항 변별도 결과는 다음 슬라이드들의 bridge입니다.
Math, Coding, Reasoning에서 model score standard deviation이 크다는 건,
이 문항들이 모델 서열을 가르는 데 더 유용하다는 의미입니다.
즉 tinyMT-Bench는 갑자기 등장한 아이디어가 아니라,
이 슬라이드의 변별도 분석에서 자연스럽게 이어진 결과입니다.

## Slide 14. Phase 4: InternLM2.5는 무엇을 보여주고 무엇은 못 보여주는가
- Section: Results
- Purpose: 보조 cross-family judge의 가치와 실패 사례를 동시에 보여줘 신뢰도를 높인다.
- Bullets:
  - InternLM2.5-20B는 Qwen32와 Spearman ρ=0.893로 broad ranking을 유지
  - 반면 InternLM2.5-7B pairwise는 winner=error가 72.6%로 실전 judge로 부적합
  - 즉 ‘cross-family check는 됨’, 하지만 ‘아무 7B judge나 pairwise에 쓰면 안 됨’

### Speaker Notes
Phase 4는 일부러 좋은 결과와 나쁜 결과를 같이 보여주는 슬라이드입니다.
왜냐하면 이게 오히려 발표 전체의 신뢰도를 높이기 때문입니다.

InternLM2.5-20B는 생각보다 괜찮습니다.
Qwen32와 Spearman rho가 0.893이기 때문에,
적어도 seen-7 수준에서는 ‘모델 서열의 큰 흐름’이 유지된다고 말할 수 있습니다.

하지만 7B는 다릅니다.
InternLM2.5-7B는 pairwise verdict format을 안정적으로 따르지 못해서,
전체 record의 72.6%가 사실상 error로 남았습니다.
이건 단순 파서 버그가 아니라, 작은 judge가 pairwise verdict prompt를 안정적으로 수행하지 못한 사례로 읽는 게 맞습니다.

이 슬라이드에서 청중이 기억해야 할 건 하나입니다.
cross-family 결과를 보여주는 건 중요하지만,
그 자체가 곧 높은 품질을 의미하지는 않습니다.
특히 작은 open-weight judge를 pairwise judge로 쓸 때는 ‘모델 크기’와 ‘verdict format compliance’를 반드시 같이 봐야 합니다.

## Slide 15. Phase 5: GPT-4o-mini는 외부 기준점으로 충분한가
- Section: Results
- Purpose: closed API judge를 외부 기준점으로 썼을 때 메인 결과가 얼마나 유지되는지 보여준다.
- Bullets:
  - Qwen32 ↔ GPT-4o-mini: Spearman ρ=0.964, Kendall τ=0.905
  - Pairwise inconsistency도 33.99%로 Qwen32의 32.86%와 매우 유사
  - 즉 Qwen32 결과는 완전한 closed-source artifact는 아님

### Speaker Notes
Phase 5는 제 발표에서 외적 타당성을 가장 강하게 받쳐주는 슬라이드입니다.
GPT-4o-mini는 full GPT-4는 아니지만, 적어도 외부 API judge라는 기준점 역할은 충분히 합니다.

여기서 중요한 숫자는 Qwen32와의 rank agreement입니다.
Spearman 0.964, Kendall tau 0.905면 seen-7 모델 서열은 거의 같다고 봐도 됩니다.
그리고 pairwise inconsistency도 34% 정도라 Qwen32와 사실상 비슷한 수준입니다.

이 결과가 왜 중요하냐면,
이제 저는 Qwen32 main result를 단순히 ‘Qwen family 안에서만 그럴 수 있다’고만 말하지 않아도 되기 때문입니다.
적어도 외부 judge 하나를 붙였을 때 큰 서열 패턴은 유지된다는 걸 보였습니다.

다만 여기도 해석을 분리해야 합니다.
rank pattern consistency와 question-level decision consistency는 다릅니다.
exact pairwise agreement는 0.58 수준이기 때문에,
두 judge가 각 질문마다 똑같이 판단한다고 말하면 과장입니다.
이 슬라이드의 메시지는 ‘외부 기준점에서도 큰 흐름은 유지된다’입니다.

## Slide 16. 앙상블은 정말 큰 judge를 이길 수 있는가
- Section: Results
- Purpose: 실무적으로 가장 궁금한 질문 하나에 대해 명확한 yes/no를 준다.
- Bullets:
  - 단순 다수결 앙상블은 오히려 단일 32B보다 나쁨: 58.63% > 32.86%
  - inconsistent를 기권 처리한 abstain ensemble은 24.70%로 가장 낮음
  - 핵심 교훈: 저품질 judge를 그냥 합치면 평균이 아니라 오염이 됨

### Speaker Notes
실무적으로는 이 슬라이드가 제일 즉답형입니다.
많은 사람이 작은 judge 여러 개를 합치면 큰 judge 하나보다 나아질 거라고 기대합니다.
그런데 제 결과는 그렇지 않다고 말합니다.

단순 다수결은 오히려 더 나빠집니다.
왜냐하면 7B의 noisy한 inconsistent 표가 앙상블에 그대로 유입되기 때문입니다.
이건 ensemble이 wisdom of crowds가 되려면 crowd 자체가 최소한의 품질을 가져야 한다는 걸 보여줍니다.

반대로 abstain 방식은 좋았습니다.
inconsistent를 억지로 표로 세지 않고 기권으로 처리하면,
결정적인 표가 있는 경우에만 winner를 선언하게 되고,
결국 inconsistency가 24.70%까지 내려갑니다.

이 결과는 학술적으로도 흥미롭지만,
실제로 judge system을 설계하는 입장에서는 더 유용합니다.
즉 ‘모델 여러 개를 붙일 거면 voting rule부터 다시 설계하라’는 교훈을 줍니다.
발표에서는 이 슬라이드를 practical takeaway로 강조하겠습니다.

## Slide 17. tinyMT-Bench same-set 결과: 왜 40문항이 강했는가
- Section: Results
- Purpose: 문항 축소 아이디어의 출발점과 same-set 상한을 명확히 설명한다.
- Bullets:
  - same-set 기준 Top-Disc-40은 ρ=1.000으로 full-80 ranking을 완전 보존
  - Top-Disc-25도 ρ=0.964로 강하지만, 1개 순위 역전이 발생
  - same-set에서는 40문항이 가장 설득력 있는 비용 절감 upper bound

### Speaker Notes
이 슬라이드는 문항 축소 결과의 출발점입니다.
same-set이라는 건, 문항을 고를 때 쓴 모델 집합과 검증할 때 쓴 모델 집합이 같은 경우입니다.
이 설정에서는 Top-Disc-40이 full-80 ranking을 완전히 보존했습니다.

그래서 초기에는 아주 매력적인 결과처럼 보입니다.
80문항을 40문항으로 줄이면 비용을 절반으로 줄이면서도 순위는 그대로니까요.
Top-Disc-25도 꽤 좋지만 0.964라는 건 실제로는 1개 순위 역전에 해당합니다.

다만 제가 same-set upper bound라는 표현을 계속 쓰는 이유는,
이 결과가 선택과 검증을 같은 모델 집합에서 했기 때문입니다.
즉 좋은 결과 자체는 사실이지만,
이걸 곧바로 외부 일반화로 읽으면 안 됩니다.

그래서 다음 슬라이드가 중요합니다.
same-set에서는 40문항이 예쁘게 나오지만,
hold-out으로 가면 메시지가 조금 달라집니다.
그리고 그 차이를 정직하게 보여주는 게 이 발표의 중요한 미덕이라고 생각합니다.

## Slide 18. Repeated hold-out 결과: 40문항은 강하고, 60문항은 더 안전하다
- Section: Results
- Purpose: Phase 6가 lucky draw가 아니라 반복 hold-out 결과라는 점을 데이터로 보여준다.
- Bullets:
  - 11개 모델에서 leave-4-out hold-out 330 split, 각 N마다 random 200개 비교
  - Top-Disc-40 평균 ρ: Qwen 0.968 / InternLM20B 0.922 / GPT-4o-mini 0.959
  - judge 공통으로 더 안전한 구간은 Top-Disc-60: 0.998 / 0.995 / 0.972

### Speaker Notes
이 슬라이드가 이번 작업에서 가장 크게 업그레이드된 부분입니다.
처음엔 single split hold-out만 있었는데, 그걸로는 운 좋은 한 번이라는 비판을 피하기 어려웠습니다.
그래서 현재는 11개 모델 풀에서 4개를 test로 고르는 모든 조합, 즉 330개 split을 전부 돌렸습니다.

각 split마다 dev 7로 문항 변별도를 다시 계산해서 Top-Disc를 뽑고,
같은 N에 대해 random subset 200개도 같이 비교했습니다.
즉 이건 더 이상 pilot이 아니라 distributional result입니다.

결과를 보면 40문항도 충분히 강합니다.
평균 rho가 세 judge 모두 random 평균보다 높고, split win rate도 78~86% 정도 나옵니다.
하지만 발표에서 제가 더 강조하려는 건 60문항입니다.
40문항은 same-set의 아름다운 upper bound이고,
repeated hold-out까지 합치면 60문항이 더 안전한 cross-judge operating point로 보입니다.

이 슬라이드 덕분에 이제 tinyMT-Bench를 단순 아이디어 수준이 아니라,
상당히 방어 가능한 경험적 권고 수준까지 올릴 수 있게 됐습니다.

## Slide 19. 그래서 이 연구에서 무엇을 믿고, 무엇은 아직 조심해야 하나
- Section: Wrap-up
- Purpose: 주장의 범위와 한계를 스스로 통제해 발표 전체 신뢰도를 끌어올린다.
- Bullets:
  - 믿을 수 있는 것: Qwen same-family scaling trend, cross-family broad rank stability, repeated hold-out의 60문항 권고
  - 조심할 것: 11개 모델 풀은 7B–11B same-era chat 모델 중심
  - 아직 열린 질문: 70B급, code-specialist, multilingual 환경까지도 같은가

### Speaker Notes
이 슬라이드는 사실 발표 전체의 tone을 결정합니다.
결과가 아무리 좋아도 범위를 잘못 말하면 점수를 잃습니다.

제가 지금 자신 있게 말할 수 있는 건 세 가지입니다.
Qwen same-family에서는 judge가 커질수록 inconsistency가 줄었습니다.
InternLM20B와 GPT-4o-mini를 붙여도 큰 서열은 유지됩니다.
그리고 repeated hold-out 기준으로 보면 문항 축소는 60문항 정도가 가장 안전합니다.

반대로 아직 조심해야 하는 것도 분명합니다.
현재 model pool은 같은 세대의 7B–11B open-weight chat 모델에 치우쳐 있습니다.
그래서 이 결과를 70B급 모델이나 code-specialist 모델, 혹은 multilingual setting까지
바로 일반화해서 말하는 건 과장입니다.

저는 이 슬라이드가 오히려 발표의 강점이라고 생각합니다.
왜냐하면 청중은 ‘모든 걸 다 안다’고 말하는 발표보다,
‘여기까지는 강하고, 여기서부터는 아직 열린 문제다’라고 말하는 발표를 더 신뢰하기 때문입니다.

## Slide 20. 최종 정리: 베이스 논문을 넘어, 오픈소스 judge를 실제 도구로 읽는 법
- Section: Wrap-up
- Purpose: 20분 발표의 메시지를 세 문장으로 남기고 토론으로 넘긴다.
- Bullets:
  - 베이스 논문은 GPT-4 judge의 가능성을 열었고, 내 작업은 오픈소스 judge의 실전 신뢰도를 따졌다.
  - 메인 결과는 `32B open-weight judge + abstain ensemble + 60문항 운영점`이다.
  - Git 저장소는 논문 결과뿐 아니라 raw judgment, figure, deck까지 다시 생성 가능하게 정리했다.

### Speaker Notes
마지막 슬라이드에서는 세 문장만 남기겠습니다.

첫째, 베이스 논문은 GPT-4 judge가 인간 선호를 근사할 수 있다는 문을 열었습니다.
둘째, 저는 그 문을 오픈소스 judge 쪽으로 옮겨 보면서,
무엇이 실제로 믿을 만하고 무엇은 아직 조심해야 하는지 정리했습니다.
셋째, 이 저장소는 결과표만 있는 게 아니라 raw judgment부터 figure, paper, 그리고 오늘 발표자료까지 재생성 가능한 연구 자산으로 정리했습니다.

발표 이후 질문이 들어오면 보통 세 갈래일 겁니다.
왜 32B냐, 왜 60문항이냐, 그리고 왜 이 결과를 더 넓게 일반화하지 않느냐.
이 슬라이드는 그 질문들에 대한 짧은 답변이기도 합니다.

제 답은 이렇습니다.
32B는 현재 실험 범위에서 가장 좋은 open-weight judge였고,
60문항은 repeated hold-out에서 가장 안전한 운영점이었고,
그 이상의 일반화는 지금 당장 주장하지 않는 것이 더 학문적으로 정직합니다.

이상으로 발표를 마치고 질문 받겠습니다.

# Korean MT-Bench

Korean MT-Bench는 영어 MT-Bench의 80개 두 턴 문항과 8개 범주를 유지한
한국어 평가 자료입니다. 이 저장소에는 번역 검토를 마친 문항, 6개 생성
모델의 영어와 한국어 답변, LLM 평가 출력, 파싱 결과, 논문 표와 그림을
다시 계산하는 코드가 들어 있습니다.

답변 생성과 평가는 번역 검토가 끝난 80문항 확정본을 입력으로 수행했습니다.
q83, q90, q136은 확정 전에 원문과 과제 기능을 대조하여 처리했습니다.

- q83: `fewer than 200 words`의 길이 단위를 `200단어 미만`으로 보존
- q90: 한국어에서도 교정 과제가 성립하도록 조사, 활용, 맞춤법 오류를 구성
- q136: 지정 영어 단어를 세는 지문과 오름차순 출력 조건을 보존

## 자료 구성

```text
data/
├── en/
│   ├── questions.jsonl
│   ├── answers/
│   └── judgments/
├── ko/
│   ├── questions.jsonl
│   ├── answers/
│   └── judgments/
├── translation_review/
│   └── items.csv
├── results/
└── MANIFEST.sha256
scripts/
├── analysis/
├── run/
├── tools/
└── translate/
```

영어와 한국어 문항은 각각 80개이며 모든 문항은 두 턴으로 구성됩니다.
답변 생성 모델은 다음 6개입니다.

- Llama-3.1-8B-Instruct
- EEVE-Korean-Instruct-10.8B
- EXAONE-3.5-7.8B-Instruct
- Gemma-2-9B-IT
- Mistral-7B-Instruct-v0.3
- Phi-3.5-mini-Instruct

공개 평가 기록에는 Qwen2.5-7B, Qwen2.5-14B, Qwen2.5-32B,
EXAONE-3.5-32B, GPT-4o-mini와 Gemma-4-12B의 판정이 포함됩니다.
표 5–8과 그림 3은 이 여섯 평가자의 결과와 전체 평균을 함께 보고합니다.

## 평가 방식

세 가지 평가 방식을 사용합니다.

1. 일반 단일 채점: 각 답변의 첫 번째 턴과 두 번째 턴을 1–10점으로 채점
2. 쌍대 비교: 같은 답변쌍을 AB와 BA 순서로 각각 제시하여 판정 변화 확인
3. 참조 정답 기반 단일 채점: 지정된 29개 문항의 두 번째 턴을 참조 정답과 함께 채점

일반 단일 채점 평균은 파싱에 성공한 모든 출력의 산술평균입니다. 쌍대 비교
불일치율의 분모는 AB와 BA가 모두 파싱된 판정쌍입니다. 참조 정답 기반
비교는 일반 채점과 참조 채점이 모두 유효한 동일 문항, 동일 생성 모델의
두 번째 턴만 사용합니다. 파싱 실패는 평균에서 제외하되 예정 출력 수와
실패 수를 별도로 보고합니다.

## 논문 표와 그림 재생성

Python 3.10 이상을 권장합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

python3 scripts/analysis/build_paper_artifacts.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/tools/verify_release.py
```

첫 번째 명령은 원시 JSONL에서 다음 파일을 생성합니다.

- `table4_translation_review.csv`
- `table5_pairwise_inconsistency.csv`
- `table6_single_scores.csv`
- `table7_reference_scores.csv`
- `table8_parse_failures.csv`
- `figure3_scores.csv`

Figure 3은 영어와 한국어의 생성 모델별 점수와 범주별 점수를 (a)–(d)의
네 패널 열지도를 2×2로 함께 나타냅니다. 모든 패널은 동일한 1–10점 색상 범위를 사용하며,
여섯 평가자의 평균 열은 굵은 경계와 글자로 구분합니다. 출력 크기는 DBR
본문 폭에 맞춘 145 × 94 mm이며, 하단의 공통 색상 막대에 1–10점 눈금과
레이블을 함께 표시합니다. PDF는 벡터를 유지합니다. PNG와 PDF는
재생성 산출물이므로 공개 저장소에서 추적하지 않으며,
`generated/figures/figure3_single_scores.{png,pdf}`에 저장됩니다.

## 평가자 실험 환경

로컬 모델 실행에 기록된 환경은 NVIDIA A100 40GB,
`vllm/vllm-openai:v0.6.6`입니다. vLLM 0.6.6 공식 이미지의 기본 CUDA
버전은 12.4.1이고 CUDA 의존성 파일의 PyTorch 버전은 2.5.1입니다.
실행 당시 이미지 digest, GPU driver, 전체 `pip freeze`는 보존되지 않았으므로
이 조합은 공식 이미지 설정을 재구성한 값이며 당시 컨테이너의 바이트 단위
식별값을 뜻하지 않습니다.

답변 생성은 `temperature=0.7`, 최대 출력 1,024 토큰을 사용했습니다.
한국어 조건에는 `반드시 한국어로 답하세요.`를 추가했습니다. 평가는
`temperature=0.0`이며 최대 출력은 일반 단일 채점 512 토큰, 쌍대 비교와
참조 정답 기반 단일 채점 1,024 토큰입니다.

사용한 생성 모델 저장소 ID는 다음과 같습니다.

| 결과 이름 | 모델 저장소 ID |
|---|---|
| Llama-3.1-8B-Instruct | `meta-llama/Llama-3.1-8B-Instruct` |
| EEVE-Korean-Instruct-10.8B | `yanolja/EEVE-Korean-Instruct-10.8B-v1.0` |
| EXAONE-3.5-7.8B-Instruct | `LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct` |
| gemma-2-9b-it | `google/gemma-2-9b-it` |
| Mistral-7B-Instruct-v0.3 | `mistralai/Mistral-7B-Instruct-v0.3` |
| Phi-3.5-mini-Instruct | `microsoft/Phi-3.5-mini-instruct` |

기존 Hugging Face 모델의 정확한 revision과 GPT-4o-mini의 불변 snapshot은
실행 기록에 남아 있지 않습니다. 따라서 공개 결과는 보존된 문항, 답변,
평가 출력의 재집계에는 충분하지만, 외부 모델 서비스의 동일 출력을 새로
생성하는 것까지 보장하지는 않습니다.

## Gemma-4-12B 실행 환경

Gemma 4 Unified는 기존 실험의 vLLM 0.6.6에서 지원되지 않습니다. Gemma-4-12B 평가는
기존 A100, PyTorch, CUDA 환경을 유지하고, Gemma 4 Unified를
지원하는 Transformers의 OpenAI 호환 서버를 사용합니다.
집계 결과는 다른 평가자와 함께 `data/results/table5_pairwise_inconsistency.csv`에서
`data/results/table8_parse_failures.csv`까지에 포함됩니다.

| 항목 | 설정 |
|---|---|
| GPU | NVIDIA A100 40GB 한 장 |
| 실행 이미지 | `pytorch/pytorch@sha256:c8268a92a69bd500f8be0e665b2630ee006dadaf7bfbc24249141b15ff622755` |
| PyTorch / CUDA | 2.5.1 / 12.4 |
| 추론 백엔드 | Transformers Serve 5.15.0 |
| 평가 모델 | `google/gemma-4-12B-it` |
| 모델 revision | `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` |
| 정밀도 | BF16 |
| attention | PyTorch SDPA |
| 추론 모드 | 모델 기본 추론 모드(`auto`) |
| temperature | 0.0 |
| 최대 출력 | 단일 512, 쌍대와 참조 정답 기반 각각 1,024 토큰 |

모델 준비와 GPU 평가를 두 단계로 분리합니다. 먼저 GPU가 필요 없는
준비 스크립트가 고정 revision의 모델을 다른 A100 실험과 같은
`<작업 디렉터리>/models/Gemma-4-12B-it`에 다운로드하고, 고정된 추론
런타임과 준비 완료 기록을 `runs/runtime/gemma4_12b/`에 저장합니다.
토큰은 명령행 인자나 저장소 파일에 기록하지 않습니다.

```bash
bash scripts/run/a100/prepare_gemma4_12b_a100.sh
bash scripts/run/a100/run_judge_gemma4_12b_a100.sh --lang both
```

GPU 평가 스크립트는 네트워크 다운로드나 `pip install`을 수행하지
않습니다. 고정된 모델 revision, 필수 파일 크기와 해시, PyTorch,
Transformers 및 OpenAI 클라이언트 버전이 `prepare_record.json`과
일치해야 시작합니다. 평가 중에는 Hugging Face와 Transformers를
오프라인 모드로 고정합니다.

| 구분 | 기본 경로 |
|---|---|
| 확정 문항과 답변 입력 | `data/{en,ko}/questions.jsonl`, `data/{en,ko}/answers/` |
| 공용 모델 | `<작업 디렉터리>/models/Gemma-4-12B-it` |
| 준비 기록과 클라이언트 | `runs/runtime/gemma4_12b/` |
| 원시 판정 | `runs/reproduction/{en,ko}/judgments/gemma4/judge_12B/` |
| 집계 결과와 실행 환경 | `runs/aggregates/gemma4_12b/` |
| 실행 로그 | `runs/logs/gemma4_12b/` |

스크립트는 영어와 한국어 각각 일반 단일 채점 960회, 쌍대 비교 2,400회,
참조 정답 기반 단일 채점 174회를 수행합니다. 전체 호출 수는 7,068회입니다.
완료 후 `verify_gemma4_run.py`가 문항, 모델 조합, 입력 식별값의 존재와 출력 수를
검사합니다. 검증을 통과한 결과만 `data/*/judgments/gemma4/judge_12B/`에
옮겨 공개 결과에 포함합니다. 실행 결과를 이 저장소의 `runs/reproduction`
경로로 받은 뒤 다음 순서로 가져오고 표와 그림을 다시 생성합니다.

```bash
python3 scripts/tools/import_gemma4_run.py
python3 scripts/analysis/build_paper_artifacts.py
python3 scripts/tools/build_manifest.py
python3 scripts/tools/verify_release.py
```

## 번역 원칙과 후속 확장

자연어 지시는 과제 의도, 난이도, 수치, 형식과 길이 제약을 유지하면서
자연스러운 한국어로 번역했습니다. 코드, 수식, 변수명, 출력 표식과 문자열
계산의 근거가 되는 지문은 필요한 경우 원문을 유지했습니다. 직역으로 과제
기능이 사라지는 교정 문항은 한국어에서도 같은 오류 탐지 능력을 요구하도록
기능적으로 현지화했습니다.

기계번역을 적용할 때는 코드, 수식, 숫자, 단위, 출력 형식과 계수 지문을
자리표시자로 보호하고, 두 턴을 분리해 번역한 뒤 자리표시자와 제약 보존을
자동 검사해야 합니다. 그다음 독립 역번역과 한국어 원어민의 원문 대조를
거쳐 평가 문항을 확정하는 절차를 권장합니다.

높임법, 생략된 논항, 조사, 띄어쓰기, 어절과 형태소 계수는 영어 원문 대응
80문항만으로 충분히 측정하기 어렵습니다. 후속 연구에서는 이러한 문항을
별도의 한국어 고유 확장 세트로 설계하고, 기존 80문항과 분리하여 사람
평가자 일치도, 모델 변별력, 사람과 LLM 평가의 일치도를 검증할 수 있습니다.

## 출처와 라이선스

영어 문항은 LMSYS FastChat의
`fastchat/llm_judge/data/mt_bench/question.jsonl`에서 가져왔습니다.

- 원본 저장소: `lm-sys/FastChat`
- 기준 revision: `b494d0c6b4e7935f1764f8439e75da3e66beccc7`
- 원문 무결성 검증값: `119565adbab82227089cefdb44c8d7e2cf04dc0a0ec233634c82e7d4e2a944f7`
- 원본 라이선스: Apache License 2.0

코드와 한국어 번역 자료는 이 저장소의 Apache License 2.0에 따라
배포합니다. 모델 답변과 평가 출력에는 각 모델과 서비스 제공자의 이용
조건이 적용될 수 있으며, 이 저장소의 라이선스가 제3자 모델 가중치나
상표에 대한 권리를 부여하지는 않습니다.

원본 MT-Bench를 사용할 때는 다음 논문을 인용해 주십시오.

> Lianmin Zheng et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."
> Advances in Neural Information Processing Systems 36, 2023.

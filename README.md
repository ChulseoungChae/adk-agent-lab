# adk-agent-lab

Google ADK(Agent Development Kit) 기반 로컬 LLM 에이전트 실험실입니다.  
기능별로 번호가 붙은 프로젝트 폴더 안에 **코드(`agent/`)** 와 **결과물(`output/`)** 을 함께 둡니다.

## Google ADK란?

ADK는 LLM에 **도구(Tools)** 와 **작업 관리** 기능을 붙여, 단순 대화를 넘어 여러 단계에 걸친 작업을 이어서 처리하게 해 주는 프레임워크입니다. 이 레포의 에이전트들도 같은 구조 위에서 동작합니다.

![Google ADK 핵심 기능](img/adk.png)

### 핵심 구성 요소

| 구성 | 설명 | 이 레포에서의 예 |
|------|------|------------------|
| **LLM 연결** | Gemini, Ollama 등 다양한 모델 연동 | `LiteLlm` + Ollama `gemma4`, `qwen3` 등 |
| **Tools** | 파일 저장, API 호출, Git 동기화 등 실제 동작 | 플랫폼 API 조회, 챕터 저장, `git commit/push` |
| **Session / State** | 작업 진행 상태 유지 | ADK 세션·책 메타데이터·목차·챕터 파일 |
| **Memory** | 이전 맥락 기억 | 세션 내 대화·도구 호출 결과 활용 |
| **Workflow / Runner** | 순차 실행, 중단·재개 | `run.py` → `adk run`, 모델별 순차 집필 |

### 일반적인 작업 흐름

1. **요청 받기** — 사용자 프롬프트 또는 `auto` 모드 자율 집필 지시
2. **자료 조사** — 플랫폼 API·파일 등 도구로 데이터 수집
3. **결과 생성** — 목차·챕터 본문 작성
4. **저장** — `output/`에 Markdown·JSON 기록
5. **동기화** — GitHub에 commit·push (선택)

ADK의 강점은 **도구 사용**, **상태 저장**, **중단 후 재시작**입니다. 책 집필처럼 시간이 걸리고 단계가 많은 작업에 특히 잘 맞습니다.

## 레포 구조

```
adk-agent-lab/
├── img/
│   └── adk.png         # ADK 핵심 기능 설명
├── 01_making_a_book/
│   ├── agent/          # 실행 코드
│   ├── output/         # 결과물
│   └── README.md
├── 02_model_compare_book/
│   ├── agent/          # 실행 코드
│   ├── output/         # 모델별 결과물
│   └── README.md
└── requirements.txt
```

## 설치

```bash
cd /data1/github_cschae/adk-agent-lab
pip install -r requirements.txt
```

## 프로젝트 목록

| 폴더 | 설명 |
|------|------|
| [01_making_a_book](01_making_a_book/) | 반도체 플랫폼 데이터 기반 한국어 기술서 집필 |
| [02_model_compare_book](02_model_compare_book/) | Ollama 멀티모델 순차 집필·성능 비교 |

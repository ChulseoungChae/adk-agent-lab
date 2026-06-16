# adk-agent-lab

Google ADK 기반 로컬 LLM 에이전트 실험실입니다.  
코드(`agents/`)와 결과물(`output/`)을 분리해 관리합니다.

## 레포 구조

```
adk-agent-lab/
├── agents/                    # 실행 코드
│   └── 01_making_a_book/      # 책 작성 에이전트
│       ├── agent.py           # ADK root_agent
│       ├── run.py             # 실행 진입점
│       └── ...
├── output/                    # 에이전트 결과물
│   └── 01_making_a_book/
│       ├── agent.log
│       ├── book_metadata.json
│       ├── outline.json
│       └── chapters/
└── requirements.txt
```

새 에이전트 추가 시: `agents/02_이름/`, `output/02_이름/` 패턴으로 생성하세요.

## 설치

```bash
cd /data1/github_cschae/adk-agent-lab
pip install -r requirements.txt
```

## 실행 (01_making_a_book)

```bash
cd /data1/github_cschae/adk-agent-lab/agents/01_making_a_book
export OLLAMA_API_BASE=http://localhost:11434
python3 run.py              # 자율 집필 (기본)
python3 run.py chat         # 대화형 CLI
python3 run.py sync         # 수동 commit+push
```

저장 시 `output/01_making_a_book/`에 결과가 쌓이고, 자동으로 **commit + push** 됩니다.

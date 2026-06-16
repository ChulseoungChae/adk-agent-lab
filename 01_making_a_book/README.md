# 01_making_a_book — 반도체 플랫폼 기반 기술서 집필 에이전트

Google ADK + Ollama **gemma4:26b**로 [반도체 AI 어시스턴트](http://bigsoft.iptime.org:10200/) 플랫폼 데이터를 조사·인용해 **한국어** 기술 서적을 집필합니다.

## 구조

```
01_making_a_book/
├── agent/          # 실행 코드
│   ├── agent.py    # ADK root_agent
│   ├── run.py      # 실행 진입점
│   └── ...
├── output/         # 결과물
│   ├── agent.log
│   ├── book_metadata.json
│   ├── outline.json
│   └── chapters/
└── README.md
```

## 실행

```bash
cd /data1/github_cschae/adk-agent-lab/01_making_a_book/agent
export OLLAMA_API_BASE=http://localhost:11434
python3 run.py              # 자율 집필 (기본)
python3 run.py chat         # 대화형 CLI
python3 run.py sync         # 수동 commit+push
```

## 에이전트 도구

| 도구 | 설명 |
|------|------|
| `fetch_anomaly_logs` | 실시간 이상감지 |
| `fetch_prediction_logs` | 예측 이상감지 |
| `fetch_equipment_history` | 과거 공정 이력 |
| `list_platform_reports` | 리포트 목록 |
| `save_book_metadata` | 책 메타데이터 저장 |
| `save_outline` | 목차 저장 |
| `write_chapter` | 챕터 Markdown 저장 |

저장 시 `output/`에 결과가 쌓이고 자동으로 Git **commit + push** 됩니다.

## 로그

| 파일 | 내용 |
|------|------|
| `output/agent.log` | 도구 호출, git push 등 진행 로그 |
| `/tmp/agents_log/agent.latest.log` | ADK 내부 로그 |

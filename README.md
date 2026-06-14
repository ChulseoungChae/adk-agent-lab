# adk-agent-lab

Google ADK + Ollama **gemma4:26b** 로컬 LLM으로 반도체 공정 기술 서적을 집필하는 에이전트 실험실입니다.

[반도체 AI 어시스턴트](http://bigsoft.iptime.org:10200/) 플랫폼의 실시간 이상감지, 공정 이력, 리포트 데이터를 도구로 조회하여 책에 반영합니다.

## 아키텍처

```
사용자 → ADK Agent (gemma4:26b via LiteLLM)
              ├─ 플랫폼 도구 → :10200/api (이상로그, 리포트)
              │              → :9301/api (공정 이력, 장비 상태)
              └─ 책 작성 도구 → output/ (목차, 챕터 Markdown)
```

## 사전 요구사항

- Python 3.10+
- [Ollama](https://ollama.com/) 실행 중 (`ollama serve`)
- `gemma4:26b` 모델 pull 완료
- 반도체 AI 어시스턴트 플랫폼 접근 가능 (`http://bigsoft.iptime.org:10200`)

## 설치

```bash
cd /data1/github_cschae/adk-agent-lab
pip install -r requirements.txt
cp .env.example .env   # 필요 시 URL 수정
```

## 실행

```bash
# Web UI (권장)
bash scripts/run.sh web

# CLI 대화
bash scripts/run.sh run

# API 서버
bash scripts/run.sh api
```

또는 `/data1/adk_code/making_a_book.py`에서:

```bash
python /data1/adk_code/making_a_book.py
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama 서버 |
| `OLLAMA_MODEL` | `gemma4:26b` | 사용 모델 |
| `ASSISTANT_API_BASE` | `http://bigsoft.iptime.org:10200/api` | AI 어시스턴트 API |
| `PLATFORM_API_BASE` | `http://bigsoft.iptime.org:9301` | semi_platform API |
| `BOOK_OUTPUT_DIR` | `output` | 책 파일 저장 경로 |

> `ollama_chat/` 접두사 필수. `OLLAMA_API_BASE` 환경변수를 반드시 설정하세요.
> [ADK Ollama 문서](https://adk.dev/agents/models/ollama/)

## 에이전트 도구

### 플랫폼 조사 (http://bigsoft.iptime.org:10200 기능)

| 도구 | 플랫폼 기능 |
|------|------------|
| `fetch_anomaly_logs` | 실시간 이상감지 |
| `fetch_prediction_logs` | 예측 이상감지 |
| `fetch_equipment_history` | 과거 공정 이력 검색 |
| `search_process_recipes` | 레시피 목록 |
| `fetch_generator_status` | 데이터 수집 상태 |
| `list_platform_reports` | 리포트 목록 |
| `get_report_content` | 리포트 상세 |
| `create_platform_report` | 리포트 생성 |

### 책 작성

| 도구 | 설명 |
|------|------|
| `save_book_metadata` | 제목·독자층·주제 저장 |
| `save_outline` | 목차 저장 |
| `write_chapter` | 챕터 Markdown 저장 |
| `read_book_state` | 현재 진행 상태 조회 |

## 출력 파일

```
output/
├── book_metadata.json
├── outline.json
└── chapters/
    ├── 01_서론.md
    └── 02_이상감지_사례.md
```

## 예시 대화

> "ALD 공정 이상감지에 관한 엔지니어용 기술서를 써줘. 최근 이상 로그와 월간 리포트를 참고해서 5장 구성으로."

에이전트가 플랫폼 데이터를 조회한 뒤 목차를 저장하고 챕터를 순차 작성합니다.

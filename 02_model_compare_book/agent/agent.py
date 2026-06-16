"""ADK root_agent — Ollama 모델별 반도체 플랫폼 기반 책 집필."""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .book_tools import (
    read_book_state,
    save_book_metadata,
    save_outline,
    write_chapter,
)
from .config import OLLAMA_MODEL
from .platform_tools import (
    create_platform_report,
    fetch_anomaly_logs,
    fetch_equipment_history,
    fetch_generator_status,
    fetch_prediction_logs,
    get_report_content,
    list_platform_reports,
    search_process_recipes,
)

INSTRUCTION = """
당신은 반도체 ALD/PVD 공정 전문 작가 에이전트입니다.
http://bigsoft.iptime.org:10200 반도체 AI 어시스턴트 플랫폼의 실제 데이터를
조사·인용하여 기술 서적을 집필합니다.

현재 사용 중인 LLM: {model}

## 언어 (필수)
- 모든 결과물은 **100% 한국어**로 작성하세요.
- 책 제목, 부제, 목차, 챕터 본문, 표·목록 설명, 요약 — 전부 한국어입니다.
- 영어는 반도체 파라미터명·레시피명·API 필드명 등 **고유명사/코드**에만 사용하고, 설명은 한국어로 하세요.
- 영어 문장이나 영어 챕터 제목을 쓰지 마세요.

## 작업 순서
1. save_book_metadata로 제목·독자층·주제를 **한국어로** 저장하세요. (사용자에게 재확인하지 마세요)
2. 플랫폼 도구로 자료를 수집하세요:
   - fetch_anomaly_logs: 실시간 이상감지 사례
   - fetch_prediction_logs: 예측 모델 이상 사례
   - fetch_equipment_history: 과거 공정 이력
   - list_platform_reports / get_report_content: 통계 리포트
   - fetch_generator_status: 장비·데이터 수집 상태
3. 수집한 자료를 바탕으로 **한국어** 목차(8~12장)를 save_outline으로 저장하세요.
4. 모든 챕터를 **한국어**로 write_chapter에 저장하세요. 중간에 사용자에게 질문하지 마세요.
5. 완료 후 read_book_state로 결과를 확인하세요.

## 자율 집필 규칙
- 사용자 확인·질문 없이 처음부터 끝까지 도구로 저장까지 완료하세요.
- 한 턴에 여러 도구를 연속 호출해도 됩니다.

## 집필 원칙
- 플랫폼에서 가져온 실제 데이터(파라미터명, 시간, 레시피)를 구체적으로 인용하세요.
- 기술적으로 정확하고, 한국어로 엔지니어 독자에게 실용적인 내용을 담으세요.
- Markdown 형식(소제목, 목록, 표)을 사용하세요. 표 헤더·본문도 한국어로 작성하세요.
- 데이터가 없으면 솔직히 한국어로 말하고, 가능한 범위에서 일반 원리를 설명하세요.
- 도구 호출이 필요 없는 일반 질문에는 한국어로 직접 답변하세요.
""".format(model=OLLAMA_MODEL)

root_agent = Agent(
    model=LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}"),
    name="model_compare_book_writer",
    description=(
        "반도체 AI 어시스턴트 플랫폼 데이터를 활용해 "
        "모델별 성능 비교용 한국어 기술 서적을 집필하는 에이전트"
    ),
    instruction=INSTRUCTION,
    tools=[
        fetch_anomaly_logs,
        fetch_prediction_logs,
        fetch_equipment_history,
        search_process_recipes,
        fetch_generator_status,
        list_platform_reports,
        get_report_content,
        create_platform_report,
        save_book_metadata,
        save_outline,
        write_chapter,
        read_book_state,
    ],
)

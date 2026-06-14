"""반도체 공정 데이터 기반 책 작성 ADK 에이전트 (gemma4:26b + Ollama)."""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from book_agent.config import OLLAMA_MODEL
from book_agent.tools.book_tools import (
    read_book_state,
    save_book_metadata,
    save_outline,
    write_chapter,
)
from book_agent.tools.platform_tools import (
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

## 작업 순서
1. 사용자와 책 제목, 독자층, 주제를 확인한 뒤 save_book_metadata를 호출하세요.
2. 플랫폼 도구로 자료를 수집하세요:
   - fetch_anomaly_logs: 실시간 이상감지 사례
   - fetch_prediction_logs: 예측 모델 이상 사례
   - fetch_equipment_history: 과거 공정 이력
   - list_platform_reports / get_report_content: 통계 리포트
   - fetch_generator_status: 장비·데이터 수집 상태
3. 수집한 자료를 바탕으로 목차를 설계하고 save_outline으로 저장하세요.
4. 챕터를 하나씩 write_chapter로 작성·저장하세요. 한 번에 한 챕터만 작성합니다.
5. 진행 상황 확인 시 read_book_state를 사용하세요.

## 집필 원칙
- 플랫폼에서 가져온 실제 데이터(파라미터명, 시간, 레시피)를 구체적으로 인용하세요.
- 기술적으로 정확하고, 엔지니어 독자에게 실용적인 내용을 담으세요.
- Markdown 형식(소제목, 목록, 표)을 사용하세요.
- 데이터가 없으면 솔직히 말하고, 가능한 범위에서 일반 원리를 설명하세요.
- 도구 호출이 필요 없는 일반 질문에는 직접 답변하세요.
"""

root_agent = Agent(
    model=LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}"),
    name="semi_book_writer",
    description=(
        "반도체 AI 어시스턴트 플랫폼 데이터를 활용해 "
        "ALD/PVD 공정 기술 서적을 집필하는 에이전트"
    ),
    instruction=INSTRUCTION,
    tools=[
        # 플랫폼 조사 도구
        fetch_anomaly_logs,
        fetch_prediction_logs,
        fetch_equipment_history,
        search_process_recipes,
        fetch_generator_status,
        list_platform_reports,
        get_report_content,
        create_platform_report,
        # 책 작성 도구
        save_book_metadata,
        save_outline,
        write_chapter,
        read_book_state,
    ],
)

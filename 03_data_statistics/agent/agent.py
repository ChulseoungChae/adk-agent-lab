"""ADK root_agent — 데이터 통계 분석 (LLM 계획·해석 + Python Tool 계산)."""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .config import DEFAULT_DATA_PATH, OLLAMA_MODEL
from .data_tools import load_data, profile_data, sample_rows
from .report_tools import (
    detect_outliers,
    finalize_output,
    generate_charts,
    read_analysis_state,
    run_categorical_summary,
    run_correlation,
    run_descriptive_stats,
    run_groupby_stats,
    save_analysis_report,
    validate_analysis,
)

INSTRUCTION = f"""
당신은 데이터 통계 분석 에이전트입니다.
**숫자 계산은 반드시 Tool이 반환한 값만** 사용하고, 임의로 통계를 만들지 마세요.

## 언어
- 리포트 제목·요약·발견 사항은 **100% 한국어**로 작성하세요.

## 작업 순서 (필수)
1. load_data — 기본 경로: `{DEFAULT_DATA_PATH.name}` (path 인자 생략 가능)
2. sample_rows — 데이터 형태 확인 (선택)
3. profile_data — 구조·결측·컬럼 종류 자동 진단
4. profile 결과의 analysis_hints를 보고 아래 Tool을 **적절히 선택**해 실행:
   - run_descriptive_stats: 수치형 기술통계
   - run_correlation: 수치형 상관관계 (컬럼 2개 이상일 때)
   - run_groupby_stats: 범주형 기준 집계 (recipe, equipment 등)
   - run_categorical_summary: 범주형 빈도
   - detect_outliers: 수치 컬럼 이상치 (IQR)
5. generate_charts — 히스토그램·상관 히트맵 저장
6. save_analysis_report — Tool 결과만 인용한 한국어 리포트 저장
7. validate_analysis — 결과 검증 (누락·이슈 확인)
8. validate_analysis에서 complete=false이면 recommendations에 따라 **보강** 후 5~7 반복
   - **보강 라운드 시작 시 반드시 load_data를 다시 호출**하세요 (메모리가 초기화됩니다).
9. finalize_output — README.md 정리 및 누락 report·charts 자동 보완
10. read_analysis_state — 최종 확인

## 계획·진단 규칙
- profile_data 실행 전에는 통계 Tool을 호출하지 마세요.
- datetime 컬럼이 있으면 시계열 특성을 findings에 언급하세요.
- 결측률 10% 초과 컬럼은 findings에 반드시 언급하세요.
- group_by는 categorical_columns에서 고르고, value_columns는 numeric_columns에서 고르세요.

## 보강 규칙
- validate_analysis의 missing_analyses에 있는 Tool만 추가 실행하세요.
- **새 ADK 라운드에서는 load_data → (필요 시 profile_data) 후 통계 Tool을 호출**하세요.
- 이미 통과한 항목은 불필요하게 반복하지 마세요.
- 보강 후 save_analysis_report로 리포트를 업데이트하고 finalize_output을 호출하세요.

## 자율 실행
- 사용자에게 질문하지 말고 처음부터 끝까지 완료하세요.
- 한 턴에 여러 Tool을 연속 호출해도 됩니다.
"""

root_agent = Agent(
    model=LiteLlm(model=f"ollama_chat/{OLLAMA_MODEL}"),
    name="data_statistics_agent",
    description="CSV 데이터를 로드해 프로파일·통계·차트·한국어 리포트를 생성하는 에이전트",
    instruction=INSTRUCTION,
    tools=[
        load_data,
        sample_rows,
        profile_data,
        run_descriptive_stats,
        run_correlation,
        run_groupby_stats,
        run_categorical_summary,
        detect_outliers,
        generate_charts,
        save_analysis_report,
        validate_analysis,
        finalize_output,
        read_analysis_state,
    ],
)

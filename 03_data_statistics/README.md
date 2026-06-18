# 03_data_statistics — 데이터 통계 분석 에이전트

CSV 데이터를 넣으면 **LLM이 진단·계획·해석**하고, **Python Tool이 실제 통계**를 계산합니다.  
`02_model_compare_book`처럼 **4개 Ollama 모델을 순차 실행**해 분석 품질·소요 시간을 비교할 수 있습니다.

## 구조

```
LLM (계획·해석·보강)  →  Python Tools (pandas)  →  validate_analysis  →  output/{모델}/
```

| 역할 | 담당 |
|------|------|
| 진단·계획 | 로컬 LLM |
| 계산 | 고정 Python Tool (describe, corr, groupby, IQR…) |
| **검증·보강** | `validate_analysis` + `run.py` 다회차 루프 |
| 모델 비교 | 4모델 순차 실행 → `comparison_summary.json` |

## 비교 모델

| 모델 | 출력 디렉터리 |
|------|---------------|
| `gemma4:31b` | `output/gemma4_31b/` |
| `gemma4:26b` | `output/gemma4_26b/` |
| `qwen3.6:35b` | `output/qwen3_6_35b/` |
| `qwen3-vl:32b` | `output/qwen3_vl_32b/` |

## 폴더 구조

```
03_data_statistics/
├── data/sample_sensor.csv
├── agent/
│   ├── stats_engine.py         # 순수 pandas
│   ├── analysis_validator.py   # 결과 검증·보강 판단
│   ├── compare_report.py       # 모델 비교 README·차트
│   └── run.py
└── output/
    ├── comparison_summary.json
    ├── README.md               # 모델 비교 요약
    ├── gpu_usage.csv
    ├── charts/                 # 비교 그래프
    └── gemma4_31b/             # 모델별
        ├── profile.json
        ├── statistics.json
        ├── validation.json
        ├── report.md
        └── charts/
```

## 실행

```bash
cd /data1/github_cschae/adk-agent-lab/03_data_statistics/agent
export OLLAMA_API_BASE=http://localhost:11434
pip install -r ../../requirements.txt

python3 run.py tools        # LLM 없이 Tool+검증 테스트
python3 run.py              # 4모델 순차 분석 (기본)
python3 run.py single       # OLLAMA_MODEL 1개만
python3 run.py report       # comparison_summary → output/README.md
python3 run.py sync
```

## 검증·보강 (`validate_analysis`)

`analysis_validator.py`가 output 파일을 검사합니다.

| 검사 항목 | 조건 |
|-----------|------|
| profile_exists | profile.json 존재 |
| descriptive_stats | 기술통계 Tool 실행 |
| correlation | hints에 상관 분석 가능 시 |
| groupby_stats | hints에 그룹 집계 가능 시 |
| categorical_summary | 범주형 컬럼 있을 때 |
| outliers | 수치형 컬럼 있을 때 |
| charts | PNG 1개 이상 |
| report + findings | report.md + 발견 3개 이상 |
| high_missing_mentioned | 결측 10% 초과 컬럼 리포트 언급 |

- `complete=false` → `run.py`가 보강 프롬프트로 **최대 8라운드** 재실행 (`ADK_MAX_ROUNDS`)
- 결과: `validation.json` (점수·누락·권장 사항)

## Tool 목록

| Tool | 설명 |
|------|------|
| `load_data` | CSV 로드 |
| `profile_data` | 자동 진단 |
| `run_descriptive_stats` | 기술통계 |
| `run_correlation` | 상관계수 |
| `run_groupby_stats` | 그룹별 집계 |
| `run_categorical_summary` | 범주 빈도 |
| `detect_outliers` | IQR 이상치 |
| `generate_charts` | 히스토그램·히트맵 |
| `save_analysis_report` | 한국어 리포트 |
| **`validate_analysis`** | **결과 검증·보강 판단** |
| `read_analysis_state` | 상태 확인 |

## 환경 변수

```bash
export ADK_MAX_ROUNDS=8
export LITELLM_TIMEOUT_SEC=1800
export MODEL_SWITCH_DELAY_SEC=20
export GPU_MONITOR_ENABLED=1
export AUTO_SYNC_RESULTS=0   # 자동 git push 끄기
```

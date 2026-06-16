# 02_model_compare_book — Ollama 모델별 책 집필 성능 비교

[반도체 AI 어시스턴트](http://bigsoft.iptime.org:10200/) 플랫폼 데이터를 활용해 **동일 주제**의 한국어 기술서를 여러 Ollama 모델로 순차 집필하고 결과를 비교합니다.

## 비교 모델

| 모델 | 출력 디렉터리 |
|------|---------------|
| `gemma4:31b` | `output/gemma4_31b/` |
| `gemma4:26b` | `output/gemma4_26b/` |
| `qwen3.6:35b` | `output/qwen3_6_35b/` |
| `qwen3-vl:32b` | `output/qwen3_vl_32b/` |

## 구조

```
02_model_compare_book/
├── agent/              # 실행 코드
├── output/
│   ├── agent.log       # 전체 세션 로그 (모델별 START/END 구분)
│   ├── comparison_summary.json
│   ├── gemma4_31b/
│   │   ├── book_metadata.json
│   │   ├── outline.json
│   │   └── chapters/
│   └── ...
└── README.md
```

## 실행

```bash
cd /data1/github_cschae/adk-agent-lab/02_model_compare_book/agent
export OLLAMA_API_BASE=http://localhost:11434
python3 run.py              # 4개 모델 순차 집필 (기본)
python3 run.py single       # OLLAMA_MODEL 1개만
OLLAMA_MODEL=gemma4:26b python3 run.py single
python3 run.py sync         # 수동 commit+push
```

각 모델 집필이 끝나면 `output/{모델}/`에 결과가 저장되고, `comparison_summary.json`에 소요 시간·챕터 수가 기록됩니다.

## 로그

`output/agent.log`에 세션마다 구분선이 삽입됩니다.

## GPU 모니터링

집필 중 **5초마다** `nvidia-smi`로 GPU 사용량을 샘플링합니다. (기본값, 변경 가능)

| 파일 | 내용 |
|------|------|
| `output/gpu_usage.csv` | 시계열 샘플 (모델·GPU별) |
| `output/gpu_usage_summary.log` | 모델 작업 종료 시 min/max/avg 통계 |

```bash
# 샘플링 주기 변경 (초)
export GPU_MONITOR_INTERVAL_SEC=2

# 모니터링 끄기
export GPU_MONITOR_ENABLED=0
```

**주기 권장값**
- **5초 (기본)** — 수 분~수십 분 집필에 적합. 파일 크기·부하 균형이 좋음.
- **2초** — GPU 활용 스파이크를 더 촘촘히 보고 싶을 때.
- **10초** — 장시간 배치·대략적 추세만 필요할 때.

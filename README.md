# adk-agent-lab

Google ADK 기반 로컬 LLM 에이전트 실험실입니다.  
기능별로 번호가 붙은 프로젝트 폴더 안에 **코드(`agent/`)** 와 **결과물(`output/`)** 을 함께 둡니다.

## 레포 구조

```
adk-agent-lab/
├── 01_making_a_book/
│   ├── agent/          # 실행 코드
│   ├── output/         # 결과물
│   └── README.md
├── 02_다음기능/         # (추가 예정)
│   ├── agent/
│   └── output/
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

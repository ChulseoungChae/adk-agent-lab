# adk-agent-lab — 책 작성 결과물

ADK 에이전트가 생성한 기술 서적 결과물만 이 레포에 저장됩니다.

**실행 코드**는 `/data1/adk_code`에 있습니다.

## 결과물 구조

```
output/
├── book_metadata.json   # 책 제목, 독자층, 주제
├── outline.json         # 목차
└── chapters/            # 챕터 Markdown
    ├── 01_서론.md
    └── ...
```

## 생성 방법

```bash
cd /data1/adk_code
python making_a_book.py
```

챕터·목차 저장 시 `AUTO_SYNC_RESULTS=1`이면 이 레포에 자동 커밋됩니다.

수동 동기화:

```bash
python making_a_book.py sync
```

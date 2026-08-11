# Mark Twain QA Bot

전자책 한 권 — *Mark Twain Anecdotes and Quotes* (David Bruce, 2008) — **만을** 지식원으로
쓰는 RAG QA 시스템. 검색된 발췌만 근거로 답하고 청크 제목·쪽수·인용 문장을 함께 보여주며,
책에 없는 질문에는 `Not in this book.` 이라고 답한다.

설계 판단과 실패 분석은 `docs/NOTES.md` 에 있다.

## 준비

PDF는 이 저장소에 **없다.** 비상업적 용도로 원형 그대로 배포되는 자료라 코드만 커밋했다.
직접 받아서 `data/book.pdf` 에 둔다.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
claude setup-token     # 출력된 토큰을 .env 의 CLAUDE_CODE_OAUTHTOKEN= 에 붙여넣는다
unset ANTHROPIC_API_KEY   # 둘 다 있으면 API 키가 OAuth 토큰을 이긴다
```

토큰 대신 Messages API 종량제로 쓰려면 `.env` 에 `answer_provider=api` 와
`ANTHROPIC_API_KEY=sk-ant-...` 를 넣는다.

## 실행

```bash
.venv/bin/python -m scripts.ingest data/book.pdf   # PDF -> 청크 -> 색인
.venv/bin/uvicorn main:app                         # http://localhost:8000
```

색인은 저장소에 없으므로 첫 명령을 건너뛸 수 없다. `data/`, `index/`,
`docs/CHUNK_STATS.md` 가 이 단계에서 만들어진다.

**질문은 영어로 한다.** 임베딩이 영어 전용(`bge-small-en-v1.5`)이라 한국어 질의는 검색
단계에서 실패한다 — 이유는 `docs/NOTES.md` §3.

## 평가와 테스트

```bash
.venv/bin/python -m eval.report        # 10문항 실행 -> docs/EVAL.md
.venv/bin/python -m pytest -q          # 47개, 약 0.5초
```

`docs/EVAL.md` 와 `docs/CHUNK_STATS.md` 는 생성물이므로 손으로 고치지 않는다.
색인·검색·테스트는 자격증명 없이 돌아간다 — 답변 생성에만 필요하다.

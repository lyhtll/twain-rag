# Mark Twain QA Bot

전자책 한 권 — *Mark Twain Anecdotes and Quotes* (David Bruce, 2008) — **만을** 지식원으로
쓰는 RAG QA 시스템. 검색된 발췌만 근거로 답하고 청크 제목·쪽수·인용 문장을 함께 보여주며,
책에 없는 질문에는 `Not in this book.` 이라고 답한다.

청킹 근거와 실패 분석은 별도 제출한 메모(`NOTES.md`)에 있다.

## 준비

PDF는 이 저장소에 **없다.** 비상업적 용도로 원형 그대로 배포되는 자료라 코드만 커밋했다.
직접 받아서 `data/book.pdf` 에 둔다.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
claude setup-token
unset ANTHROPIC_API_KEY
```

`claude setup-token` 이 출력한 토큰을 `.env` 의 `CLAUDE_CODE_OAUTHTOKEN=` 에 붙여넣는다.
`ANTHROPIC_API_KEY` 를 지우는 이유는 둘 다 설정돼 있으면 API 키가 OAuth 토큰을 이겨서
구독이 아니라 종량제로 과금되기 때문이다. 종량제로 쓰려면 `.env` 에 `answer_provider=api`
와 `ANTHROPIC_API_KEY=sk-ant-...` 를 넣는다.

## 실행

```bash
.venv/bin/python -m scripts.ingest data/book.pdf
.venv/bin/uvicorn main:app
```

첫 명령이 PDF에서 청크와 색인을 만든다. 색인은 저장소에 없으므로 건너뛸 수 없다.
`data/`, `index/`, `docs/` 가 이 단계에서 생긴다.

두 번째 명령이 서버를 띄운다. http://localhost:8000 에 접속해 질문을 던지면 답변과 함께
근거 청크의 제목·쪽수·인용 문장이 나온다.

**질문은 영어로 한다.** 임베딩이 영어 전용(`bge-small-en-v1.5`)이라 한국어 질의는 검색
단계에서 실패한다 — 이유는 메모 §3.

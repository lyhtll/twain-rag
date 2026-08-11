"""Run the frozen question set and regenerate docs/EVAL.md.

    python -m eval.report

Two columns are mechanical and two are judgement:

- **top-3 hit** is mechanical. A chunk satisfies an evidence option when the option's page
  falls inside the chunk's page span and the option's phrase is in the chunk's text. A
  question hits when *every* evidence piece has at least one satisfied option among the
  top-3. `absent` questions have no evidence and are scored `n/a` — they have no correct
  chunk, so counting them either way would distort the rate.
- **answer correct** is mechanical only for `absent` questions, where correct means the
  answer is exactly the refusal sentence. For `fact` and `multi` a human has to read the
  answer, so the mark is read from `eval/marks.yaml` and shown as UNMARKED until it is
  there. The table is generated either way — an unmarked table is honest, a hand-edited
  one is not.
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.agents.answer_agent import AnswerAgent
from app.core.config import settings
from app.models.chunk import Chunk
from app.observability import log_run
from app.rag.indexer import Index
from app.rag.retriever import HybridRetriever
from app.rag.text import norm

QUESTIONS = Path("eval/questions.yaml")
MARKS = Path("eval/marks.yaml")
OUT = Path("docs/EVAL.md")
CACHE = Path("eval/last_run.json")

# The frozen question set uses these three kinds; the report shows the assignment's names.
KIND_KO = {"fact": "사실", "multi": "흩어짐", "absent": "없음"}


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_marks(path: Path = MARKS) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def mark_for(mark: dict[str, Any], answer: str) -> Any:
    """The recorded judgement — but only if it judged *this* answer.

    Generation is nondeterministic, so regenerating the report can reword an answer while
    `marks.yaml` still holds the previous run's verdict. Keying the mark on the question id
    alone would then attribute a human judgement to an answer no human read. `answer:` in
    `marks.yaml` records the text that was judged; when it no longer matches, the mark
    reverts to UNMARKED and has to be re-read rather than silently inherited.
    """
    judged = mark.get("answer")
    if judged is not None and norm(judged) != norm(answer):
        return "UNMARKED"
    return mark.get("answer_correct", "UNMARKED")


def satisfies(chunk: Chunk, option: dict[str, Any]) -> bool:
    return (
        chunk.page_start <= option["page"] <= chunk.page_end
        and norm(option["contains"]) in norm(chunk.text)
    )


def evidence_hit(pieces: list[dict[str, Any]], chunks: list[Chunk]) -> tuple[bool, int]:
    """(all pieces found, how many were found) — the count explains a partial miss."""
    found = sum(
        any(satisfies(chunk, option) for option in piece["options"] for chunk in chunks)
        for piece in pieces
    )
    return found == len(pieces), found


def run() -> pd.DataFrame:
    questions = load_questions()
    retriever = HybridRetriever(Index.load())
    agent = AnswerAgent()

    rows = []
    for question in questions:
        hits = retriever.search(question["question"])
        response, rejected = agent.answer(question["question"], hits)
        log_run(question["question"], hits, response, rejected, question_id=question["id"])

        chunks = [hit.chunk for hit in hits]
        pieces = question["evidence"]
        if question["kind"] == "absent":
            hit_label = "n/a"
        else:
            ok, found = evidence_hit(pieces, chunks)
            hit_label = "O" if ok else (f"X ({found}/{len(pieces)})" if len(pieces) > 1 else "X")

        rows.append(
            {
                "id": question["id"],
                "kind": question["kind"],
                "question": question["question"],
                "expected": _describe(pieces),
                "top3": hit_label,
                "retrieved": " ".join(f"{c.id}({c.page_label.split(', ')[1]})" for c in chunks),
                "answer": response.text,
                "refused": response.refused,
                "cited": " ".join(f"{s.chunk_id}" for s in response.sources) or "—",
                "rejected": len(rejected),
            }
        )
    return apply_marks(pd.DataFrame(rows))


def apply_marks(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill `correct` and `note` from eval/marks.yaml — the only human input in the table.

    Separate from `run()` so a judgement can be written and the report re-rendered without
    calling the model again. Re-running would reword the answers and invalidate the marks
    that were just written, which is a loop with no exit.
    """
    marks = load_marks()
    values, notes = [], []
    for row in frame.itertuples():
        mark = marks.get(row.id, {})
        if row.kind == "absent":
            # Same comparison the agent used to set `refused` (answer_agent.format_answer).
            # A raw `==` here can only ever disagree with it: whitespace variation in the
            # model's reply would leave `refused=True` while this marked the question X,
            # writing a failure that did not happen into a generated honesty artifact.
            value: Any = row.refused and norm(row.answer) == norm(settings.refusal_text)
        else:
            value = mark_for(mark, row.answer)
        values.append(_mark(value))
        notes.append(mark.get("note", ""))
    frame["correct"] = values
    frame["note"] = notes
    return frame


def _describe(pieces: list[dict[str, Any]]) -> str:
    if not pieces:
        return "— (책에 없음)"
    return " + ".join(
        " / ".join(f"p.{o['page']}" for o in piece["options"]) for piece in pieces
    )


def _mark(value: Any) -> str:
    if value is True:
        return "O"
    if value is False:
        return "X"
    return str(value)


def write_report(frame: pd.DataFrame, path: Path = OUT) -> None:
    answerable = frame[frame["kind"] != "absent"]
    hits = (answerable["top3"] == "O").sum()
    marked = frame[frame["correct"].isin(["O", "X"])]
    correct = (marked["correct"] == "O").sum()

    lines = [
        "# 10문항 평가",
        "",
        "`python -m eval.report` 로 생성된다. 사람 판정은 `eval/marks.yaml` 에 적고",
        "다시 생성한다.",
        "",
        f"- **top-3 적중률: {hits}/{len(answerable)}** (답이 있는 문항 기준. `없음` 문항은 "
        "정답 청크가 없어 제외한다)",
        f"- **답변 정확도: {correct}/{len(marked)}** "
        f"(전체 {len(frame)}문항 중 {len(frame) - len(marked)}개 미판정)",
        "",
        "| id | 유형 | 질문 | 정답 근거 | top-3 적중 | 답변 정확 | 비고 |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"| {row['id']} | {KIND_KO[row['kind']]} | {row['question'][:64]} | {row['expected']} "
            f"| {row['top3']} | {row['correct']} | {row['note']} |"
        )

    lines += ["", "## 문항별 검색·답변 내역", ""]
    for _, row in frame.iterrows():
        lines += [
            f"### {row['id']} ({KIND_KO[row['kind']]}) — top-3 {row['top3']}, 정확 {row['correct']}",
            "",
            f"**질문:** {row['question']}",
            "",
            f"**검색된 청크:** `{row['retrieved']}`  **인용된 청크:** `{row['cited']}`"
            f"  **거부된 인용:** {row['rejected']}",
            "",
            f"**답변:** {row['answer']}",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if "--render-only" in sys.argv:
        # Re-render from the stored run instead of asking the model again. This is the path
        # to take after writing a judgement into marks.yaml: a fresh run would reword the
        # answers and un-mark the very question that was just judged.
        frame = apply_marks(pd.read_json(CACHE, orient="records"))
    else:
        frame = run()
        CACHE.write_text(
            frame.to_json(orient="records", force_ascii=False, indent=1), encoding="utf-8"
        )
    write_report(frame)
    print(frame[["id", "kind", "top3", "correct", "cited", "rejected"]].to_string(index=False))
    unmarked = (frame["correct"] == "UNMARKED").sum()
    print(f"\nwrote {OUT}")
    if unmarked:
        print(
            f"{unmarked}개 문항이 사람 판정을 기다린다 — 위 답변을 읽고 {MARKS} 에 "
            f"answer_correct 와 answer 를 채운 뒤 `--render-only` 로 다시 그린다"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

---
name: eval-honesty
description: |
  Use when writing, running, or reporting the 10-question evaluation, or when doing
  failure analysis. Triggers on: eval/questions.yaml, docs/EVAL.md, top-3 hit rate,
  answer accuracy, "why did this question fail", failure classification.
---

# Eval Honesty

Read `agent_docs/eval.md` for the protocol and the grading criteria. This is the
guardrail against the ways an eval quietly becomes worthless.

## Never do these

1. **Do not edit `eval/questions.yaml` after its freeze commit.** Not the wording, not
   the expected evidence, not the `kind`. If retrieval misses, that is a finding — fix
   the code. If the question is genuinely broken, ask the user before touching it.
2. **Do not drop or replace a failing question.** A 6/10 that is honest is worth more
   than a 10/10 that was curated. The assignment explicitly grades whether failures
   were recorded as failures.
3. **Do not mark a correct-but-unsourced answer as correct.** If the model got the fact
   right without the citation supporting it, that is the exact failure mode the
   assignment penalizes. Mark it wrong and say why in the note column.
4. **Do not count `absent` questions in the top-3 hit rate.** They have no correct
   chunk; scoring them either way distorts the number. Mark them `n/a`.
5. **Do not accept a hedged refusal.** For `absent` questions the answer must be
   exactly `Not in this book.` — trailing period included. "The book doesn't cover this,
   but Twain famously..."
   is a hallucination with a disclaimer attached — mark it wrong.
6. **Do not hand-write `docs/EVAL.md`.** Regenerate it with `python -m eval.report`.

## When a question fails

Classify the cause before proposing a fix, using the table in `agent_docs/eval.md`
(chunking / retrieval / generation), and check in that order. The diagnostic that
distinguishes them:

- Search the chunk texts for the expected answer. **Not found** -> chunking.
- Found, but the chunk ranked below top-3 -> retrieval. Check the BM25 list and the
  dense list separately; whichever missed names the fix.
- Chunk was in the prompt and the answer is still wrong -> generation.

Fixing the ranker cannot repair a chunk that never contained the answer, so a
misclassified failure leads to a wasted fix and a still-failing question.

## Reporting

The summary must state both numbers plainly, even when they are low: top-3 hit rate
over the 8 answerable questions, answer accuracy over all 10. No rounding up, no
"approximately", no excluding a question because it was "unfair".

For each failure written into `docs/NOTES.md`: question id, cause, the evidence used to
decide the cause, and the one change you would make. Two failures minimum.

## Verify
```bash
python -m eval.report
git log --oneline eval/questions.yaml   # one early commit, before implementation
```

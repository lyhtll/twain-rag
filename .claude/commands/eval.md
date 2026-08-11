---
description: Run the 10-question evaluation, regenerate docs/EVAL.md, and classify the failures
allowed-tools: Bash(python -m eval.report:*), Bash(pytest:*), Bash(git log:*), Read, Grep
---

Read `.claude/skills/eval-honesty/SKILL.md` and `agent_docs/eval.md` before starting.

1. Confirm the question set is frozen: `git log --oneline eval/questions.yaml`. If it
   has commits after implementation code landed, say so — the eval's credibility
   depends on this, and the user needs to know before reading the numbers.
2. Run `python -m eval.report`. It regenerates `docs/EVAL.md`. Never hand-edit that file.
3. Read the generated table. Report both numbers plainly, without rounding up:
   top-3 hit rate over the 8 answerable questions, answer accuracy over all 10.
4. For each failure, classify the cause — chunking / retrieval / generation — using the
   diagnostic order in `agent_docs/eval.md`:
   - Grep the chunk texts for the expected answer. Not found -> **chunking**.
   - Found but ranked below top-3 -> **retrieval**. Say which side (BM25 or dense) missed.
   - In the prompt and still wrong -> **generation**.
   Show the evidence for each classification; do not guess.
5. Check the two `absent` questions specifically: the answer must be exactly
   `이 책에는 없습니다`. Flag any hedged refusal as a failure.
6. Present a draft of the failure-analysis section for `docs/NOTES.md` (Korean, at
   least 2 failures: id, cause, evidence, the one change you would make) — but do not
   write it to the file without the user's approval; that memo is their submission.
7. Do not propose editing `eval/questions.yaml` to fix a failure. Propose code changes.

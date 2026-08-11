---
description: Draft a conventional commit message from staged changes and commit after approval
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git commit:*), Read
---

1. Run `git diff --staged` to see exactly what will be committed. If it is empty, run
   `git status`, tell the user nothing is staged, and stop — do not stage files yourself.
2. If the staged set includes `data/*.pdf`, `data/chunks.jsonl`, or anything under
   `index/`, stop and warn the user: those files must not be committed (the ebook's
   license and `CLAUDE.md` rule 4). Do not commit until they are unstaged.
3. Read `agent_docs/conventions.md` for the format:
   ```
   <type>(<scope>): <subject>
   Types: feat, fix, refactor, test, docs, chore
   Scopes: ingest, retrieve, answer, eval, docs, core
   ```
4. If the staged set contains `eval/questions.yaml` **together with** implementation
   code, point it out: the question set gets its own commit so the freeze point stays
   verifiable in the log. Suggest splitting.
5. Draft a message that fits the staged diff. If the diff spans multiple scopes, pick
   the dominant one rather than inventing a combined scope.
6. Show the drafted message and wait for explicit approval. If the user asks for
   changes, revise and show again.
7. Only after approval, run `git commit -m "<approved message>"`. Never amend, never
   use `--no-verify`.

You are reviewing the design of goldstack, a personal tool in this repository (cwd). Read the code yourself; do not modify anything. Answer in Korean.

## What goldstack does
A feature is split ("grill") into tickets with a dependency graph (`blocked_by`). `gs go <feature>` runs tickets autonomously: for each ready ticket (deps done, a free slot, `max_workers = 3`) it creates a git worktree `run/wt/NN` on a branch from the current integration head, runs an AI worker (claude/codex/agy CLI) there, then: review by another model family (optionally a second reviewer run concurrently) → fix worker for findings → verify (full test suite) → merge into the integration branch. At the end: integration verify, report commit, PR to main, merge, main verify (revert on failure). Key code: `src/gs/go.py` (`_loop`, `_start`, `_finish`, `_catch_up`, `_fail`), `src/gs/finish.py`, `src/gs/review.py`, `src/gs/graph.py`, `src/gs/check.py`, `skills/grill/SKILL.md` (ticket decomposition rules), `docs/internals.md`.

## Current conflict handling (verify in code)
In `go._finish`, before merging a ticket, `_catch_up` merges the latest integration head into the ticket branch inside the ticket worktree. If git merges automatically, it continues. On conflict it aborts, writes `merge.log`, and fails the ticket (`CONFLICT`). The first failure retries: a brand-new worker re-implements the whole ticket from scratch on the latest integration (≈15–20 min worker + review again). A second failure discards the ticket. Because of this cost, the grill rule is: tickets touching the same file must be serialized with `blocked_by`. v4 added `touches` (declared paths) and `gs check` warns when overlapping tickets have no ordering.

## Measurements (from run/state.json of three past features)
| feature | wall | time with only 1 ticket running | 2 | 3 | finish phase (last ticket end → run end) |
|---|---|---|---|---|---|
| v3 (8 tickets) | 123 min | 50 | 29 | 28 | 15 min |
| v4 (10 tickets) | 132 min | 38 | 26 | 49 | 18 min |
| v5 (8 tickets) | 285 min | 245 | 15 | 0 | 25 min |
Per ticket in v5: worker 12–31 min, review 2–3 min (codex/claude) but 15–16 min when an agy (Gemini) second reviewer was attached (both reviews must finish), fix 7–11 min, verify 6–8 min (≈480 unittest tests, serial). v5 was almost fully serial because 5 tickets all edited `src/gs/finish.py` (squash merge, CI wait, protected base PRs, worktree setup, verify modes) and were chained 01→02→03→04→05→06→08. No ticket needed a retry in v3–v5. Scheduler starts tickets greedily as soon as deps/slots allow.

## Candidate ideas so far (from another model; critique them, don't just accept)
1. Grill shows estimated critical path and average concurrency in the decomposition round; recommends merging small serial tickets (fewer per-ticket review/verify overheads) and putting a "split big file into modules" ticket first so later tickets touch different files.
2. Use the existing `verify_ticket` spec key (fast subset per ticket, full suite only at integration/main) for this repo.
3. Run the test suite in parallel (tests create temp git repos; isolation unknown).
4. Keep slow second reviewers (agy) off the critical path, or give them short timeouts.
5. Optimistic parallelism for same-file tickets: let them run in parallel; on `_catch_up` conflict, launch a "conflict-resolution worker" in the ticket worktree with the conflicted state, both tickets' goals and the other ticket's diff; re-review only the resolution diff, verify, merge; on failure fall back to today's re-implement retry. Grill would serialize only tickets that change the same flow (e.g. one ticket's result is a premise for another). Risk: semantic conflicts without textual conflicts.

## What I want from you
1. Is the diagnosis right? Using the numbers, what dominates end-to-end time? Anything I'm missing (e.g. idle time, finish-phase verifies, worker time variance, the scheduler itself, review-then-fix ordering)?
2. Critique each candidate: expected gain on v5-like features, cost/complexity, risks, and whether it fits the code as it is (cite functions).
3. Propose alternatives I haven't listed (e.g. rebase-style stacking where a dependent ticket starts from the predecessor's branch before it merges, speculative starts, pipelining verify with the next ticket, splitting verify, ordering by critical path, different ticket granularity, conflict prevention at grill time, etc.). Be concrete about how it would work in this codebase.
4. Give your recommended plan: the 2–4 changes with the best gain/complexity ratio, in order, with a rough estimate of v5 wall time after them, and what to measure to confirm.
Be direct; disagree where you think the candidates are wrong.

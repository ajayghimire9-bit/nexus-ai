# Capability widening and coding-proposer pilot — development results

Branch `cursor/seed-capability-widening-coding`. Protocol/implementation
`7a70072279754c37dd7fada97ba023d79038f047` committed before scoring. This
results commit is separate. Base reviewed `c8b3101`. Closed capability-audit
artifacts were fingerprint-checked and not rewritten. Not confirmation. Not
learning-to-learn. Not AGI.

Independent verifier: `valid: true`, 90 episodes, 18095 execution events.
Historical hashes unchanged:
`seed_capability_audit.json` `4e7c2fcd…`, `*_verified_v2.json` `e38c3747…`,
`*_raw.jsonl` `8823ce57…`. Gemini NOT RUN. Final coding artifacts replayed
in `agent_loop_worker` without new inference; all 14 private outcomes matched.

## Investigation

Three seeds, five in-grammar assessment tasks plus one out-of-grammar task
each (18 method/task episodes per method). Shared widening rules; learned
priors only reorder. Catalogue is the same 252 length-2/3 programs.

| Method | Identified /15 in-grammar | Assessment match /15 | False certainty /18 | Unresolved or budget | OOG uncertain /3 | Calls | Questions | Widening overhead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no_widening | 10 | 10 | 8 | 0 | 0 | 2198 | 14 | 0 |
| boundary_first_widening | 0 | 10 | 0 | 18 | 3 | 2920 | 14 | +722 |
| cost_aware_widening | 0 | 10 | 0 | 18 | 3 | 2920 | 14 | +722 |
| learned_widening | 0 | 9 | 0 | 18 | 3 | 3164 | 7 | +966 |
| capsules_reset_widening | 0 | 8 | 0 | 18 | 3 | 3096 | 5 | +898 |

Every widening episode stopped as `budget_exhausted` (`max_candidates_checked=24`
against 252 programs). That removed false certainty, including all three
out-of-grammar claims that `no_widening` treated as certain, but it also
prevented any claimed identification. Assessment match did not improve.
Learned ordering with the same widening asked fewer questions and matched
one fewer in-grammar task than the fixed widening policies.

## Coding

Fresh projects, not the six historical audit IDs. Private tests after lock.
Public pass is not complete correctness.

| Project | A AST | B model, no memory | C hybrid | D persistent later |
|---|---|---|---|---|
| py_off_by_one_window (bug fix) | solved / private pass | solved / private pass; model proposed | solved / private pass; model proposed | solved / private pass (source task) |
| py_new_midpoint (new function) | failed, 0 proposals | failed; two invalid model patches | failed; two invalid model patches | not in later pair |
| py_multifile_tax_then_discount | failed after 1 AST attempt | failed; invalid then syntax-invalid patches | failed; same | not in later pair |
| py_documented_timeout (documented API) | failed after 1 AST attempt | solved / private pass; model proposed | solved / private pass; model proposed | solved / private pass (later different task) |

The installed Qwen 0.5B actually ran structured `complete()` calls. It produced
structurally valid patches on the window and timeout tasks and those patches
passed private tests. On midpoint and the multi-file tax/discount task it
returned patches that failed path/`old_text` uniqueness or Python syntax;
those are recorded as `invalid_proposal`, not substituted templates. AST
operators still cannot create a new function. Persistent reuse ran the later
timeout task with capsules allowed; timeout was also solved by B/C without
acquired memory, so retained experience is not shown to help a later different
task. Exact-repeat reuse was not counted as learning-to-learn.

## Natural language (subjective rubric review)

Actual local-model turns, not parser-only tests. No keyword accuracy score.

- `paraphrase_help`: generic offer of “data analysis / project management”;
  does not mention teaching, CSV tools, or coding workspaces. Rubric not met.
- `multi_turn_correction`: first turn correctly refused a missing workspace.
  Follow-up “List coding workspaces instead” fell through to ordinary chat
  because that eval store had no registered repos; generic model text.
  Partial.
- `ambiguous_request`: generic offer; did not ask what to fix. Rubric not met.
- `beyond_tools`: “I can't assist with that.” No booking claimed. Rubric met.

These are subjective judgments on preserved full responses.

## Resources

- Wall 39.95489 s; debit 40 s against the standing grant.
- Carried ledger after this run: **2259.632103455996 used / 1340.367896544004 remaining**.
- Model: `.models/qwen2.5-0.5b-instruct-q4_k_m.gguf`, sha256
  `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` (unchanged).
- Cold startup 0.674402 s; warm request times are in per-call telemetry.
- 14 live inference calls, 3708 input tokens, 1021 generated tokens,
  `max_tokens=128`, CPU llama.cpp 0.7.0, 1 thread, no application cache.
- Owned-process RSS was not sampled this run; only wall time is claimed.
- No paid services. GPU not used.

## Capability status

| Capability | Status |
|---|---|
| Investigation widening implemented and exercised | yes |
| False-certainty reduction on this grid | measured (8 → 0) |
| Useful identification after widening | unestablished (0 claimed) |
| Local-model coding proposer integrated | yes; live inference ran |
| New-function / multi-file model success | failed (invalid proposals) |
| Workspace coding loop | implemented; development-tested |
| Retained experience helping later different tasks | unestablished |
| General conversation quality | exercised; mostly unmet rubrics |
| Learning-to-learn | unestablished |
| Gemini comparison | NOT RUN |

## Next

Highest-value next task: change widening *stopping* so a unique survivor after
checked batches can be `identified_among_checked` without requiring exhaustion
of the 252-program pool, while still refusing certainty when unchecked
candidates remain *and* the shortlist merely agrees. Do not retune this
closed grid as confirmation.

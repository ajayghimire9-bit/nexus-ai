# Scoped identification / staging — development results

Branch `cursor/seed-scoped-id-staging`. Protocol/implementation `a646f88`
committed before scoring. This results commit is separate. Base reviewed
`0a8df5d`. Closed capability-audit artifacts were fingerprint-checked and not
rewritten. Not confirmation. Not learning-to-learn. Not AGI.

Independent verifier: `valid: true`, 30 investigation episodes, 18 coding
cells, 2 repair-transfer records, 3 conversation cells, 6973 execution events,
20 `final_files` replays matched saved private outcomes. Completions/tokens/wall
reconstructed from raw `model_trace`: 14 counted completions, 1571 generated
tokens, 6463 input tokens, 49.888692 s request wall. Historical hashes
unchanged: `seed_capability_audit.json` `4e7c2fcd…`, `*_verified_v2.json`
`e38c3747…`, `*_raw.jsonl` `8823ce57…`. Gemini NOT RUN.

Invalid proposals still issued `complete()` and left token telemetry, but
`inference_ran` was unset on those rows, so the reconstructed completion count
is 14 rather than the 18 live `/completion` rounds that produced tokens. That
is a reporting gap, not substituted inference.

## Investigation

Two seeds, four in-grammar assessment tasks plus one out-of-grammar task each
(10 episodes per method). `identified` counts only `identified_within_catalogue`.
`unique_among_checked` is reported, not a win.

| Method | Identified /8 in-grammar | Assessment match /8 | False certainty /10 | unique_among_checked | no_checked_candidate_fits | Calls | Questions | Widening overhead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no_widening | 0 | 3 | 7 | 0 | 0 | 1341 | 6 | 0 |
| ranked_widening | 0 | 3 | 0 | 2 | 6 | 1644 | 6 | +303 |
| stratified_widening | 0 | 3 | 0 | 2 | 6 | 1656 | 6 | +315 |

Widening removed false certainty, including out-of-grammar claims, and did not
improve assessment match. No method identified a catalogue program. Ranked and
stratified both spent the 24-check cap with remainder (`no_checked_candidate_fits`)
on six episodes and stopped unique-among-checked on two; those are not
identification wins.

## Coding

Six registered specs × three methods. Public pass is not complete correctness.
Private tests ran after lock and were replayed by the verifier.

| Spec | AST | local_model_single | local_model_per_file |
|---|---|---|---|
| py_inclusive_window_src | solved / private pass | failed; two non-JSON proposals | solved / private pass; one `complete()` wrote `<=` |
| py_score_gate | solved / private pass | solved / private pass; first proposal wrote `<=` | public pass, private fail (`>=` inverted the gate) |
| py_label_join | failed | failed; proposed then revised, still failed | failed after one proposal |
| py_fee_then_rebate | failed | failed; two `old_text_not_unique` | failed; both files invalid; later prompt still saw both files |
| py_or_default_src | solved / private pass | failed; proposed then revised, still failed | failed after one proposal |
| py_or_floor | solved / private pass | failed; proposed then revised, still failed | failed; non-JSON proposal |

The installed Qwen 0.5B actually ran structured `complete()` calls. The
decisive fail→revise→independent-pass sequence did not occur. Closest live
successes were first-round valid patches on `py_score_gate` (single) and
`py_inclusive_window_src` (per-file). Revisions ran on label-join and both
null-default tasks and did not recover. Multi-file per-file generation called
`complete()` once per file with `prompt_file_count=2`; the first file never
staged, so later prompts had no earlier *edit*, only the original sibling file.

## Repair transfer

Schemas were captured only from genuine public-passing deterministic-AST source
solves. No handwritten `patched` field. Acquisition charged.

| Pair | Genuine source | Memory private | Template private | Exact cache | None |
|---|---|---|---|---|---|
| cmp_window_to_gate | yes | pass | pass | miss | pass |
| null_limit_to_floor | yes | pass | pass | miss | fail |

Memory tied the no-acquisition family template (2/2) and beat the exact cache
(0/2). On `cmp_window_to_gate` the unpatched files already pass the assessment
cases, so that cell does not discriminate memory from doing nothing. One
success pair is not a 100% claim; the recorded rate is 2/2 with
`one_success_is_not_100_percent`. Acquired repair did not beat the ordinary
template. Learning-to-learn is unestablished.

## Natural language

Workspace header came from the real store. Scoring is real-state plus needed
question, not header-keyword match.

- `workspace_state`: “Selected resource: none. Allowed coding workspaces: none.”
  Describes empty state; scorer did not mark `names_selected_resource`.
- `missing_coding_workspace`: “Which allowed coding workspace should I use?”
  Asks the needed question; no invented edit.
- `beyond_tools`: refuses a flight booking; no execution claimed.

## Resources

- Wall 54.665338 s; debit 54.665338 s against the standing grant.
- Carried ledger after this run: **2314.297441455996 used / 1285.702558544004 remaining**.
- Model: `.models/qwen2.5-0.5b-instruct-q4_k_m.gguf`, sha256
  `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` (unchanged).
- Cold startup 0.634626 s. Request wall from traces 49.888692 s.
- Counted completions 14 (18 live rounds left tokens; invalid proposals omitted
  `inference_ran`). `max_tokens=128`, CPU llama.cpp 0.7.0, no application cache.
- Closed `local_model_runtime.py` hash unchanged. No paid services. GPU not used.

## Capability status

| Capability | Status |
|---|---|
| Scoped identification statuses exercised | yes; `identified` stays 0 |
| False-certainty reduction on this grid | measured (7 → 0) |
| Useful identification after widening | unestablished |
| Staging publish bound to passing receipt | implemented; development-tested |
| Per-file later prompt sees staged repo | implemented; multi-file first edit never staged this run |
| Live model fail→revise→private pass | did not occur |
| Genuine source-acquired repair | 2/2 captured; ties template; beats cache |
| Learning-to-learn | unestablished |
| Gemini comparison | NOT RUN |

## Next

Highest-value next task: make a live fail→revise→independent-pass possible on
a task the first proposal cannot already solve, while keeping per-file later
prompts on actually staged edits and a transfer split that the unpatched files
fail. Do not retune this closed grid as confirmation. Do not merge `main`.

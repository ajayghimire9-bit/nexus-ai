# NEXUS Data Engineering & Operations: 10-Stage Roadmap (NOT LOCKED)

Owner directive of 2026-10-27, on branch `codex/nexus-data-engineering` from `46c3e53`. `main`, `final_sealed` and Checkers
v1–v5 (`622a29a`) stay untouched.

Only Stages 1–3 are executed now. Stages 4–10 are **proposals**: nothing in them has been built or measured. Each later stage
starts only after the previous stage's frozen confirmation has been reported.

**First milestone (Stages 1–3).** NEXUS receives an unfamiliar data project, builds a working pipeline, handles deliberately
introduced failures, and produces independently checked results, with every cost and human intervention recorded.

## The 10 stages

| # | Stage | Builds on | Exit condition (predeclared per stage) | Status |
| --- | --- | --- | --- | --- |
| 1 | **Trustworthy starting point.** Audit of reusable components; regression and distinguishability tests. | `46c3e53` | 100% of the pinned regression suite passes; valid / ABSTAIN_ERROR / UNDER_SPECIFIED / ASK_CLARIFICATION / unsupported are never conflated | executed |
| 2 | **One complete engineering environment** (logistics batch + CDC + messy drops + lakehouse layers) and a protected, independent evaluator with a silent-failure fault injector | Stage 1 | the evaluator catches 8/8 deliberately broken, exit-0, non-empty pipelines with exact reasons; 0 false alarms on a correct pipeline | executed |
| 3 | **Unfamiliar projects without learned history:** a metered tool loop (inspect, docs, clarify, edit, run, inspect outputs, verify invariants); Conventional vs NEXUS with matched generator and budgets | Stage 2 | frozen one-shot final test; full 7-measure scorecard | executed |
| 4 | **Real streaming, CDC and lakehouse recovery:** continuous micro-batches over an offset log, watermarks and allowed lateness, exactly-once sinks, schema registry and evolution, backfills, time-travel rollback after a bad deploy | Stage 3 sources (CDC envelopes, event_ts / ingest_ts / seq) | 0 silent errors and 0 duplicate side effects under injected broker restarts, replays, reordering and schema changes; recovery-time SLA met | proposed |
| 5 | **Operations and incidents:** monitoring, alert triage and root cause on injected production incidents (late feeds, upstream schema breaks, skew, quota exhaustion); runbooks and rollback | Stage 4 | incidents resolved within SLA, false-page rate, 0 operational interventions; reuse N1-merge-exact change detection for drift alarms | proposed |
| 6 | **Cross-project memory:** a learned history of projects, checks, repairs and clarifications | Stages 3–5 | **Learning benefit** vs Fresh (no history) and Placebo (irrelevant history) at equal correctness; break-even reported | proposed |
| 7 | **Breadth:** new domains (billing, healthcare-like claims, retail) and engines (sqlite → DuckDB-style columnar SQL, dataframe code) | Stage 6 | generalization to withheld domains, schemas and mechanisms | proposed |
| 8 | **Open-ended code generation:** a local proposer that writes code beyond template decisions, kept inside the same verification loop | Stage 7 | silent-error rate unchanged or lower than the template proposer at lower human dependence | proposed |
| 9 | **Self-evolution under the firewall:** NEXUS improves its own checks, generator and repair policy on dev data only, with shadow evaluation and rollback | Stage 8 | improvement on withheld projects vs frozen self and Placebo edits; 0 evaluator access | proposed |
| 10 | **Integrated autonomous DE&Ops evaluation** on withheld projects end to end (build, run, operate, recover) | Stages 1–9 | the 7-measure scorecard against predeclared human-dependence and silent-error targets | proposed |

## Unified 7-measure scorecard (enforced in every stage report, Stage 1 through Stage 10)

| # | Measure | What is logged | Source of truth |
| --- | --- | --- | --- |
| 1 | **Correctness** | Independently checked outputs (seen batches and held-out batches); **silent data errors** = submitted, exit 0, wrong data (tracked explicitly); unresolved ambiguity (genuine questions never asked); exact diagnoses | protected evaluator only |
| 2 | **Completion** | Finished projects / incidents, hard failures, explicit abstentions | agent outcome + evaluator |
| 3 | **Reliability** | Freshness SLA violations, crash-recovery success and time, duplicate or missing side effects (idempotency under rerun and restart) | evaluator protocol |
| 4 | **Cost** | Proposer / model calls, CPU (agent, pipeline execution, SQL / Python), storage / IO bytes, independent checking, learning overhead, wasted work on rejected attempts. Two totals: **operating cost** (running the delivered pipeline) and **full development / learning cost** | kernel-reported meters (CPU s via getrusage; retired instructions where available) |
| 5 | **Human dependence** | `ASK_CLARIFICATION` calls (and how many were unnecessary), human engineering repairs (**must be 0** for an autonomous pass), operational interventions | tool ledger + stakeholder oracle log |
| 6 | **Learning benefit** | Relevant history vs Fresh (no history) and Placebo (irrelevant history). Stage 3 fixes the 0-history baseline; active from Stage 6 to Stage 9 | matched arms |
| 7 | **Generalization** | Performance on genuinely withheld projects, schemas, names, units, currencies, encodings and mechanisms, and on held-out data batches | sealed test split + held-out batch |

**Standing rules for every stage:**
* Dev / val / test splits come from the seed registry (`de1`). Val and test are one-use; test is sealed in the vault
  (AGENTS.md RULE 1).
* Code is frozen in git before any one-use data is drawn.
* Code commits and result commits are separate, marked NOT LOCKED.
* Every run is recorded in the hash-chained ledger and charged to the carried session grant.
* CPU only; no paid services.

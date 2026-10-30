# NEXUS Phase 12 — pre-registered protocol (NOT LOCKED)

Committed **before** any development tuning of the disambiguation searcher and before Suite 1 opens.

## Revision, machine and budget

| Item | Value |
|---|---|
| Branch | `codex/nexus-data-engineering`, start `111417c`; `main` `d7ac8c5` untouched |
| Machine | Apple M4, 16 GB, CPython 3.13.5; DuckDB 1.1.3 for native verification |
| Runtime constraints | no external LLM API, no pretrained weights |

- **Grant:** `artifacts/agi12_grant.json`, a **new 1,500 s** grant and hard cap. Older surplus (Phase 11: 638.4 s; 10G: 925.9 s) is
  recorded and not consumed.
- **Ceilings:** s1 300, s2 250, s3 750, s4 200. No transfers.
- **Metering:** every execution of Phase 12 code runs through `scripts/agi12_exec.py` (prefix `a12-`). Source editing, read-only
  inspection and ledger bookkeeping are uncharged.
- **Ledger:** `scripts/agi12_ledger.py verify` runs the frozen Phase 11 and 10C–10G verifiers plus a new `phase12` section. It is
  append-only.
- **Protection:** Phase 1–11 frozen (`scripts/agi12_protect.py`; `artifacts/agi12_protect_before.json`, 0 violations).

## Phase 11 history recorded

- **W1–W8 exposure:** Phase 11's composition families W1–W8 were run on development seeds during Phase 11 Stage 1 timing. Its
  Suite 1 used W1–W8 instances on fresh seeds.
- **T113018:** two programs fit the observations, filter → group → min(val) and filter → latest row → val, and first-match
  acceptance submitted a wrong one.
- **Over-cap rows:** 69 of 168 Phase 11 Suite 1 rows exceeded the stated 5,000 full-check cap. The checks inside refinement loops
  were not capped.
- **Provenance:** scalar library calls were inlined before logging, and use counts relied on substring tests.

## Successor corrections (src/nexus/de_phase12)

**1. Strict work caps** (`synth12.CappedCounter`).
- The counters rel_evals, micro_evals, full_checks and constructed_asts raise `WorkExhausted` at the exact increment that would
  pass their cap. The wall clock is read every 256 increments.
- Caps per task, the same for every arm:

| Counter | Cap |
|---|---|
| Relational pops | 1,000 |
| Micro-evaluations | 150,000 |
| Full checks (candidate checks, probe evaluations and reference queries included) | **5,000** |
| Constructed ASTs | 400,000 |
| Wall | 6 s |

- Unit test: the counter never exceeds a cap, and a search with tiny caps stops within them.

**2. Exact provenance.** Scalar library calls are recorded before inlining (`pool.prov`, nested calls included), and relational
calls stay as call nodes. Identification is by exact id (tree walk / tuple equality); a unit test checks that F10 is never counted
as F1.

**3. Family separation.**
- **Suite 1** (`Fresh_Ambiguous_Compositions_24`) is frozen in this commit: `manifest12.suite1`, seeds 121000–121023 (one-use),
  generator `tasks12`.
- **Mechanisms** are new. None is the Phase 11 threshold constant or min-vs-latest:

| Mechanism | What the reference does |
|---|---|
| M1 join default | unmatched parents get a default of 0 |
| M2 duplicate-key semi | semi join where parents may have several children |
| M3 null default | 0 for NULL values |
| M4 count column | COUNT of a nullable column |
| M5 window twin | latest by a sequence with a twin ordering column |
| M6 lookup left join | unmatched parents are kept |

- Instances 2–3 of each mechanism are compositions: an upstream status filter, or the upsert of two sources.
- **Development fixtures** use **only Phase 11 families** (`manifest12.dev`, seeds 120000+): flag, dedup, condsum, coalesce,
  filtmap, preagg, W3, W7.

**4. Candidate retention.** The search collects distinct consistent programs: up to `M_MAX = 8`, or 300 relational pops after the
first acceptance, or the cap. The alternatives of each relational class are tried as candidates.

## Mechanism (disamb12; generic, with no mechanism-specific detector)

**Admissible inputs.**
- Each relation gets 1–4 rows sampled from the observed rows, then up to 3 random generic mutations: duplicate, NULL, copy-value,
  fresh-value, boundary (candidate constants ± 1, observed min / max), cross-relation copy, drop.
- Inputs must satisfy the task's **declared contracts** (unique and not-null columns; Suite 2 tasks declare none).

**Construction.** Draw 40 admissible inputs and evaluate every candidate on each (charged). Keep the input with the most distinct
candidate outputs.

**Query.** The budgeted reference interface (**generator-supervised interaction**, the generator's executable specification) answers
a queried input. Each query is charged.

**Falsify.** Candidates that disagree with the answer are eliminated. If all are falsified, the example joins the observations and
synthesis resumes within the remaining cap.

**Submit / abstain** (identical for Fixed, Random and NEXUS). After the queries, the constructor searches 40 more admissible inputs
over the survivors.
- If any disagreement is found: `ABSTAIN_UNRESOLVED_DISAGREEMENT`.
- Otherwise the minimal-size survivor is submitted. Bounded agreement is an empirical check, not a proof.

**Arms**, each at B_q ∈ {1, 2}, with the same frozen Phase 11 Stage A library (rep0 / rep1), synthesizer, retention, abstention rule
and total caps:
- **Fixed:** the task's predefined static evidence batches.
- **Random:** random admissible inputs from the same generator, unscored.
- **NEXUS:** constructed distinguishing inputs.

**Diagnostic First-Match.** The first consistent candidate that reproduces static evidence batch 1 (Phase 11 acceptance), with no
retention or abstention.

**Matching.** The candidate collection is shared and computed once per (task, stream), inside 70 % of every cap. Each arm continues
from its counters with the full caps, and every row is charged the shared work in full.

## Suites

| Suite | Contents | Rows |
|---|---|---|
| **Suite 1, Fresh_Ambiguous_Compositions_24** | one-use; 24 tasks × 2 streams × 7 arm-configs | 336 |
| **Suite 2, Phase11_Regression_Audit_24** | the Phase 11 Suite 1 targets (113000–113023, already consumed), re-evaluated as an owner-requested diagnostic; static evidence = Phase 11's evidence and validation batches | 336 |

- Verification is native on DuckDB against the hidden batches.

## Pre-registered decision rules

**Primary: Suite 1, B_q = 1, per stream.**

| Verdict | Rule |
|---|---|
| Positive | NEXUS − Fixed **and** NEXUS − Random ≥ +2 verified in **both** streams, with NEXUS wrong ≤ each comparator's wrong |
| Null | every \|d\| ≤ 1 in both streams |
| Negative | NEXUS − Fixed ≤ −2 in both streams |
| Mixed | anything else |

- **B_q = 2** is a secondary readout under the same thresholds.

**Safety.** Wrong / submitted per arm. The effect of retention plus abstention alone = Fixed vs First-Match wrong counts.

**Also reported:**
- hypothesis-splitting rate: queries whose input produced ≥ 2 distinct candidate predictions and falsified ≥ 1 candidate;
- scalar vs relational learned-function participation, by exact provenance;
- cap compliance (target: 0 rows over any cap);
- wall, CPU, constructed ASTs, micro-evaluations, full checks, probe evaluations and queries.

Two streams that share targets are not independent task-set replications. No retro-adoption, no rerun of a written row, no reuse of
the one-use range.

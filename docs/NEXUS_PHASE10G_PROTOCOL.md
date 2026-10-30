# NEXUS Phase 10G — pre-registered protocol (NOT LOCKED)

This protocol is committed **before** any Phase 10G training outcome, and before the 48 one-use evaluation targets are opened.

- **Branch:** `codex/nexus-data-engineering`, starting at revision `a3cad78`.
- **`main`:** `d7ac8c5`, untouched.
- **Budget:** `artifacts/agi10g_grant.json`.
  - The owner granted **+1,100 s**, added to the verified Phase 10F balance of **511.112 s**, for a pool of **1,611.112 s** and a
    hard cap of **1,300 charged seconds**.
  - Stage ceilings: s1 200, s2 420, s3 540, s4 140. No transfers.
  - Every run is metered by `scripts/agi10g_exec.py` (prefix `a10g-`).
- **Tracked ledger:** `scripts/agi10f_ledger.py` gains a Phase 10G entry and a 10G pool reconciliation. The copied ledger lines stay
  verbatim and append-only, and `verify` passes.
- **Frozen code:** Phase 1–10F files are protected (`scripts/agi10g_protect.py`; `artifacts/agi10g_protect_before.json`,
  0 violations).
  - The one exception is `scripts/agi10f_ledger.py`, the living ledger tool.
  - All Phase 10G code is new, in `src/nexus/de_phase10g/`.

## Stage 1 — Phase 10F closure (done; committed with this protocol)

**Step-50 support** (`artifacts/agi10g_step50_counts.json`, from the 10F N50 checkpoints): each stream had **1** verified project
whose two-step replay source kept `ckey` on the partition key.
- rep0: wake 104028, plus 1 dream without `ckey` and 1 partial.
- rep1: wake 104548, plus 1 dream without `ckey`.
- Both are below k_min = 3, so no rule could propose the `ckey` subgroup at step 50. k_min stays **3** in Phase 10G.

**Attribution** (`artifacts/agi10g_attrib.json`): an owner-requested post-hoc diagnostic on the 22 consumed 10F targets, with the
frozen 10F code. It is not a new evaluation and replaces no 10F row.

| Solver (A4 configuration) | Held-out of 22 | Executions | Macro on the path |
|---|---|---|---|
| Abs_subgroup rep0 (re-run) | 22 | 2,805 | L7 × 22; identical to 10F, 22 / 22 verdicts and work |
| Abs_subgroup rep1 (re-run) | 22 | 2,526 | L6 × 22; identical to 10F |
| **Abs_current rep0** | **21** | 6,015 | none |
| **Abs_current rep1** | **22** | 2,526 | L6 × 22 |
| rep1, **only L10 removed** | 22 | 2,526 | L6 × 22 |
| rep1, **only L6 removed** | 22 | 2,403 | L10 × 22 |
| rep1, both removed (10F A4f) | 4 | — | — |

- Either rep1 macro alone suffices.
- The 10F A4f drop of 18 targets needed **both** removed, so it never isolated L10.

**Task 104529** (`scripts/agi10g_diag_104529.py`, `artifacts/agi10g_diag_104529.json`), mechanism **confirmed**:
- the path partitions `stg_orders` by the distractor `tax_amount`, whose non-null values collide once on visible batch A;
- the partition drops clean order 164, which reaches no visible output;
- it also makes the post-dedup NOT NULL filter available;
- 20 of the 25 accepted paths of this shape are hidden-wrong.

Fix `dag10g.necessary_dedup`, shared by all arms:
- a dedup whose key is not a documented unique key must be **necessary**: the spec without it, post filters moved to pre, must fail
  a visible check;
- it is uncharged, like the other rules.

Results (unit-tested):
- 104529 rejected; truth accepted;
- in the dev re-check, 15 stored accepted paths (10 wrong) → **0 accepted**;
- truth false rejects 0 / 10 dev projects.

## The Phase 10G question and world

**Shared solver (every arm):** `B_atomic_learned`.
- Atomic-dedup substrate (`atomic10f`), library L0, and the stream's learned primitive guidance `G_L0`.
- Training runs inside the atomic substrate, so `G_L0` is that substrate's ranker.
- Acceptance is `dag10g`. Search: work 600, wall 4 s.
- Abs_subgroup with k_min = 3 runs in training sleeps; macros are not used by the evaluation solver.

**Designed ambiguity (`world10g`).** One mechanism per project leaves 2–3 one-edit alternatives tied on every visible check.

| Mechanism | Needs fault | Tied alternatives (visible) | What separates them (hidden and one channel) | Relevant channel |
|---|---|---|---|---|
| seq | replay | item dedup order: load sequence vs ingest-batch sequence vs audit counter | out-of-order twins on re-deliveries | 1 replay slice |
| time | qualify_order | CDC dedup order: event time vs kafka offset / event id | pre-delete updates arriving after the delete | 2 boundary / late slice |
| grain | fanout | pre-aggregation SUM vs MAX of line quantity | several positive lines per order (visible extra lines have 0 units) | 3 multi-child slice |

- **Controls:** without a designed ambiguity, the same data properties are visible, so these alternatives fail visible checks.
- **Rejection sampling** enforces, for every project:
  - the competing choice passes visible checks, changes a hidden batch, fails the relevant channel and passes every other channel;
  - other present mechanisms' alternatives fail visibly.
- **Channels 4** (upstream lineage contract) and **5** (stakeholder clarification) are **bland decoys in this world**, by design.

**Evidence and ties (`ev10g`):**
- **Tie set:** every accepted one-field alternative of every edit on the accepted path (charged).
- **Request cost:** 10 executions plus 1 per live candidate.
- **Resolved:** the request eliminates ≥ 1 candidate and the survivors are observationally equivalent at every node on visible plus
  obtained channel data. A survivor other than c\* must also pass the declared-engine re-run.
- **Otherwise:** abstain (the ambiguity guard X2).

**Dev check** (`artifacts/agi10g_devcheck.json`):

| Check | Result |
|---|---|
| Designed ties detected | 7 / 7 |
| Incidental ties in controls | 0 / 3 |
| Relevant channel resolves and verifies | 7 / 7 |
| Irrelevant channel resolves | 0 times |

**Smoke rehearsal** (dev seeds, 12 tasks, `artifacts/agi10g_dev/`): 3 / 3 training ties resolved, 0 wrong. A 4-target dev evaluation
wrote every arm and budget row. For that smoke run only, the dev rep1 checkpoint was a copy of rep0, deleted afterwards.

## Arms (identical solver; only the channel choice differs)

| Arm | Channel order on a tie |
|---|---|
| **E0** | no evidence: abstain on every tie |
| **E1** | uniform random order (rng10c (stream, seed, 77)) |
| **E2** | fixed operator-type rule: dedup tie → 1, filter → 2, join / aggregation → 3, otherwise 4; then 1–5 |
| **E3** | learned `pi_ev` |

- **Budgets:** primary **B_ev = 1**; sensitivity **B_ev = 2**.

**Known by construction, disclosed before outcomes.**
- **The E2 rule:** seq and time ties are **both** dedup-operator ties, so E2 asks channel 1 for time ties, which can't resolve them at
  B_ev = 1.
- **E2's ceiling:** with every tie reached, at most 18 of 24 per group at B_ev = 1.
- **Scope of any E3 advantage:** it can come only from learning that dedup ties on a CDC relation need channel 2. A fixed rule that
  also conditioned on relation roles would match it.
- **Decoys:** channels 4 / 5 never help, which penalises E1.

**`pi_ev` training signal.**
- At every training tie, the wake tries **all 5 channels**, metered as evidence executions and time.
- Gain(e | C) = 1 iff channel e eliminated ≥ 1 tied candidate and left a survivor that **verifies on the hidden batches**. This is
  training feedback only, never an evaluation target.
- Features: the differing operator, DAG node, relation roles, the differing slot, the roles or literals of the tied values, and |C|
  (≤ 4).
- Model: the existing pairwise ranker (`guide10`) on (gainful, non-gainful) channel pairs.
- The training tie itself is resolved by the first resolving channel (1..5), else the wake abstains.

## Stage 2 — training

- **Streams:** 2 (rep0, rep1; `agi10gde/train` 107000 + 500 r).
- **Families:** Phase 10E's. A family holding a mechanism's fault gets it with probability 0.75 (expected per stream: 6 seq, about 10
  time, about 15 grain).
- **Length:** **N = 120**, sleep every 10, checkpoints at 60 / 120.
- **Jobs:** cap 210 s each; new tasks stop launching at 198 s.
- **If the budget ends a stream early,** the reached N is reported, never padded. Smoke cost was about 1.8 s per task.

## Stage 3 — evaluation

- **Targets:** fresh one-use `agi10gde/eval` 108000–108047; manifest `artifacts/agi10g_manifest.json`, sha256 `03af50d9…`.
  - **24 withheld cross-node compositions** (W1–W8 × 3; seq 6, time 6, grain 6, none 6).
  - **24 ordinary** (training families, held-out names; same 6 / 6 / 6 / 6 mix).
- **Rows:** 4 arms × 2 streams × 2 budgets × 48 targets = **768 rows, all to be written**.
- **Execution:** 6 chunks with 85 s caps. Per (target, stream), the search and tie set are computed once and shared by the arms;
  each row is charged in full.

## Decision rules (B_ev = 1 primary; withheld compositions primary, ordinary secondary; per stream)

| Comparison | Positive | Null | Negative |
|---|---|---|---|
| **H1** E3 − E2 | ≥ +2 in both streams, with 0 E3 evaluation wrong: *learned beats fixed* | \|d\| ≤ 1 in both | ≤ −2 in both: *fixed beats learned* |
| H2 E3 − E1 | same thresholds | same | same |
| H3 E3 − E0 | same thresholds | same | same |

- Any other outcome is *mixed*.

**Also reported:**
- verified completions of 24 and 24;
- wrong submissions (target 0);
- abstentions;
- requests issued;
- **disambiguation hit rate**: requests that eliminated ≥ 1 candidate, over requests;
- ties resolved;
- per-mechanism results.

**Total cost per arm:**
- evaluation executions: search + tie set + evidence requests;
- the shared learning cost of the solver: wake executions and charged seconds;
- E3's own learning cost: exploration executions plus `pi_ev` training time.

**Training wrong submissions:** target 0 of 240, or of the N reached.

**Sign-flip p-values** are descriptive. No retro-adoption, no rerun of a written row, no reuse of a one-use range.

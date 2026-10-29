# NEXUS Phase 9: autonomous learning with measurable future value, plus the capability roadmap (NOT LOCKED)

**Starting revision.** `a9b9bd0`, verified equal to `origin` and `github`; the working tree was clean. `main` =
`d7ac8c5` (untouched).

**Commits.** The Stage 1 implementation and development results are in `89812b0`; this report and the register entry
are a separate commit.

**Outcome in one line.** The comparator did **not** pass its sensitivity gate, so the autonomous-selection stages
(2–3) were **not run**. The one-use confirmation range `agi9de/confirm` is **unopened**.

---

## 1. Verified starting point and corrections

The Phase 8 claims hold against the raw rows:
- Completion: fresh 51, trained fixed learner 53 / 53, Full 51 / 51.
- 648 rows, **463 submissions, 0 accepted wrong repairs**.
- The two P5 gains came through trust under a fixed procedure.
- Full adopted no procedure and admitted no method.
- Full_r0 saw only P1–P4; Full_r1 only P1–P5.

**Phase 8 report correction.** The exact Phase 8 charge is **1,559.217 s**, not "~1,562", so **1,030.185 s** remained,
not "~1,027".

## 2. Budget (no new grant)

The allocation in `artifacts/agi9_grant.json` draws at most 900 s from the exact 1,030.185 s balance, so at least
130.185 s stays unspent.

**Reserve.** No ledger or grant file records a binding reserve. The Phase 8 "≥ 489 s" was the arithmetic of Phase 8's
own cap, which Phase 8 respected. Under the owner's explicit Phase 9 authorisation it is not treated as binding; this is
disclosed here.

| Stage | Ceiling | Used | Content |
|---|---|---|---|
| S1 | 200 | **167.0** | 1.0 post-hoc debit (before-snapshot ran before the meter); **150.0 timed-out audit**; 16.0 reduced audit |
| S2 | 400 | 0 | not run (gate failed) |
| S3 | 250 | 0 | not run; confirmation unopened |
| S4 | 50 | ~1 | protection; this report |
| **Total** | **900** | **~168** | **~862 s of the balance remain unspent** (~732 within the Phase 9 allocation, plus 130.185 outside it) |

**My error.** The first audit wrote nothing until its end. It reached its 150 s cap inside the
redundant-computation trajectories (which contained Spark projects), so all of its results were lost. Moving funds back
from S2 to S1 is not permitted (forward only). The rerun saves after every memory evaluation.

## 3. Stage 1: sensitivity of the future-learning comparator (development data only)

**Infrastructure** (`src/nexus/de_phase9/`; human evaluation infrastructure, not NEXUS learning):
- **Strata** (`blocks9.STRATA`), 3 projects each: resolvable conflicts, missing information, legacy disagreement,
  explicitly undecided intent, benign (reading is wasted work), and multi-fault composites. Half the projects use
  held-out names.
- **Balanced streams:** each cycle has one project of each of P1–P7, X1 and X2, with rotating requirement conditions and
  engines.
- **Comparator** (`compare9`): per-task exposure (which points existed and how each was resolved: claim, calibrated
  trust, clarification or unresolved; method-queue use); C_acquire, C_future and C_discovery with proxy sensitivity
  (read 0 / 0.1, question 0 / 2 / 5); and the predeclared selection rule.
- **Not supported:** source-reliability changes are absent from the generator, so they are recorded, not simulated.

**Memories** (from the Phase 8 trained fixed learners; development use only):

| Label | Memory |
|---|---|
| U | FixedLearner_r1, 39 trust records |
| A | U with trust removed |
| B | U with every trust agreement label flipped |
| C | U reordered and renamed (same semantics) |
| E | U plus irrelevant growth: ×3 skill sources, 40 evidence weights for absent features, 40 feature-less trust records |

**Results** (`artifacts/agi9_dev/sensitivity_lite.json`; 9-project development block, F0 for all):

| Control | Predeclared rule | Result | Pass? |
|---|---|---|---|
| A useful vs removed | U verifies more than A | 4 vs 4 | **FAIL** |
| B useful vs corrupted | B verifies fewer than U, or accepts more wrong | 4 / 0 wrong vs 4 / 0 wrong | **FAIL** |
| C equivalent | identical solved set, cost within 1 % | identical; cost 64.116 vs 64.116 | pass |
| E irrelevant extra memory | not selected over U | tie, not selected | pass |
| D cheaper-equivalent learning | selection prefers the non-redundant learner | **not run** (the first audit timed out inside it) | – |
| F method channel | sensitive or insensitive | **not run**; method utility untested | – |

**Gate: not passed.**

**Mechanism** (from the per-task exposure, not inferred from counts):
1. **Most tasks never reach the evidence.** 5 of the 9 projects end with "no repair candidate", in every memory. No
   decision point exists there, so no learned evidence can matter. Repair search is the first-order bottleneck of the
   measurement.
2. **The one question masks single-conflict value.** On the one conflict project that reached a decision (P7, 77301),
   U resolved it by **calibrated trust with 0 questions**. A and B spent the single clarification and also verified.
   Trust changes the *outcome* only when open conflicts outnumber the question budget, as on Phase 8's 76034 / 76039
   (two conflicts). The block contained none that reached a candidate.
3. **Corrupted trust fails safe.** Flipping the labels gives the approved-status feature negative weight, so `decide`
   finds no positive decisive feature, returns "unresolved", and the procedure asks or abstains. Corruption therefore
   shows up only as extra questions or abstentions, not as wrong submissions.
4. **The value that did appear is below the cost threshold.** One saved question (2 s proxy) on 64 s of block cost is
   3 %, under the 10 % cost rule. It is a real but small acquisition-efficiency signal, and the comparator treats it as a
   tie.

**What this establishes.** The comparator correctly ignores semantically equivalent and irrelevant memory changes. It
**cannot yet measure the future value of acquired evidence**: the block is dominated by search failures, and
single-conflict tasks are rescued by the question budget.

**The general fix** (not implemented; no Stage 1 funds left). Draw the evaluation block from tasks where the **fresh
search reaches a candidate**, determined on development seeds with F0 before any learner comparison. Include a stratum
with **two or more simultaneously open conflicts**. This is a selection on reachability, not on which memory wins, and
it does not plant a winning procedure: reading still costs, and benign and undecided strata stay in the block.

## 4–7. Stages 2–3: not run

Per the gate rule, no autonomous candidate was shortlisted, no paired trajectories ran, and no candidate was selected.
The confirmation block (`blocks9.confirm_manifest()`, 18 one-use seeds 80000–80017, 6 strata × 3) is **unopened** and
preserved.

**There is no claim about autonomous edits, repeatability across parents, learned methods, or discovery-cost repayment.**

**Costed protocol for the next run**, from measured throughput where available:

| Item | Cost |
|---|---|
| Measured: block generation | ~1 s per project |
| Measured: block evaluation | ~1 s per project (shared digest-keyed search) |
| Phase 8 estimate: source project | ~1.8 s |
| Phase 8 estimate: consolidation | ~6.6 s per cycle |
| Corrected calibration (screen ~40 dev projects for reachability, rebuild an 18-task block, rerun A–F incrementally, D on 9-project trajectories without Spark) | ≈ 150–190 s |
| Stage 2 per parent (screen ~15 s + 3 × 18-project trajectories ~140 s + 3 × 18-task block evaluations ~55 s) | ≈ 210 s, so ≈ 420 s for two parents |
| Stage 3 per selected parent (2 × 18-project continuations ~92 s + 2 × 18 confirmation rows ~40 s) plus fresh reference ~20 s | ≈ 150–300 s |

**Total ≈ 720–910 s.** That exceeds the ~732 s left in this Phase 9 allocation at the upper end. It needs either the
remaining balance under a new explicit owner authorisation, or one parent instead of two (which weakens the
repeatability claim).

## 8. Roadmap: an experience-trained search policy (protocol only; nothing trained)

- **Evidence for the bottleneck.** Most failures across Phases 7–9 are "no repair candidate" (here 5 of 9 development
  tasks; Phase 8 had 13 / 72 for fresh). A ranking or search bottleneck is the most supported hypothesis.
- **Next ranking comparison:**
  - the fixed ordering (FIXED_W + interleaving);
  - the existing evidence-weight prior;
  - a small linear ranker over inference-time features;
  - a compact neural ranker **only if** the trace corpus and measured throughput justify it.

  Capacity is chosen from data, not from a 7M–20M target. Peak training memory must be checked on the 16 GB M4; MPS helps
  tensor training, not Python AST enumeration.
- **Data:** grouped splits by original project, mechanism and trajectory lineage. Verified successes are positives;
  refuted candidates are scoped negatives; unvisited or failed-search branches are censored, not negative.
- **Fixed parts:** the acceptance and evaluation barrier stays fixed. Compare full solve quality and full
  collection / training / inference cost.
- **DreamCoder** (PLDI 2021, doi 10.1145/3453483.3454080) is a precedent for jointly learned libraries and neural
  guidance, not evidence for this corpus.

## 9. Roadmap: local model assistance

No local model was inventoried or run in Phase 9, and no API spending occurred. A future experiment needs:
- a verified inventory (weights, version, quantisation, context, RAM, throughput);
- the 5-arm design: symbolic fresh; symbolic experienced; **frozen proposer + fresh** (the missing control); the same
  proposer + experienced; and the proposer with a standard retry / tool loop;
- the 2 × 2 (fresh / experienced × proposer absent / present) to separate standalone from interaction effects;
- pretrained knowledge counted as inherited capability, with matched tools, evidence and inference budgets.

## 10. Roadmap: external validity, cross-domain transfer, self-evolution

- **External SQL repair.** BIRD-Critic (bird-critic.github.io), including its SQLite track, is a candidate independent
  benchmark for database-issue repair; it is distinct from BIRD text-to-SQL. Its task format, licence, evaluator
  availability and runtime were **not checked** in this phase (no network budget was planned). Results tables stay blank
  until measured.
- **Cross-domain transfer.** The current read / check_coverage / resolve actions are data-engineering specific; the
  Phase 8 finding of no shared executable interface with `campaign/worlds` stands. The portable learned objects to
  target: evidence acquisition and reconciliation, informative experiment selection, retention of incomplete hypotheses,
  executable abstraction, and search-effort allocation. A general observation / experiment / hypothesis / memory
  interface should be built only for an explicit second-domain test, with identical adapters for controls.
- **Improver M.** It remains untested. A real test needs M\* vs M0 vs a matched random M over several full cycles, with
  discovery charged and a sealed holdout used once.

## 11. Contracts, product path and launch

- **Methods to date:** one admitted method in Phase 8, plus Phase 7's six. Each has an executable body, role
  parameters, provenance and admission evidence. None has demonstrated causal future value on targets.
- **Not produced in Phase 9:** method contracts with counterexamples and measured reuse benefit.
- **Product readiness.** The useful data-engineering product milestone and the transferable-learning milestone remain
  separate. A December pilot is contingent on readiness criteria that are not met by this evidence; no
  January / February release is promised. There is no claim of zero future silent errors or monotonic improvement.

---

## Required final statements

- **Can the comparator measure future learning value?** **Not yet.** It is correctly invariant to equivalent and
  irrelevant memory changes. It is insensitive to removing or corrupting useful trust evidence, because most tasks fail
  at search and single conflicts are rescued by the question budget. The cheaper-equivalent and method channels were not
  run.
- **Did an autonomous edit improve capability or acquisition efficiency?** Untested; Stages 2–3 were not run.
- **Did it repeat across parents?** Untested.
- **Which methods, memories and decisions caused it?** None claimed. The only observed effect: calibrated trust replaced
  one question on one development task.
- **Was discovery cost repaid?** No discovery was run.
- **Do the procedure language and task representation still limit the search?** The limiting factor measured here is the
  **repair search** (no candidate on 5 / 9 tasks), not the procedure language.
- **The single next experiment.** Rebuild the comparator's evaluation block from **search-reachable** development tasks
  with a **multi-conflict** stratum, rerun controls A–F with incremental saving, and only then run the paired parent
  comparison. If repair search keeps blocking exposure, run the §8 ranking comparison first: evidence cannot show value on
  tasks the search never reaches.

---

## Phase 9B: rebuilt sensitivity gate (NOT LOCKED; owner Phase 9B instruction)

**Commits.** Starting revision `7f67a83`. The gate evidence is in `2587e22`; this report section is a separate commit.

**Budget** (`artifacts/agi9b_grant.json`, registered once):

| Item | Seconds |
|---|---|
| Owner buffer | +350 |
| Unused inside the Phase 9 allocation (exact; the instruction said 732.0) | 732.401 |
| Outside carry | 130.185 |
| **Pool** | **1,212.586** |
| Phase 9B cap | 950 |
| Carried reserve | ≥ 262.586 |
| **Used** | **~149** (S1 148.2, plus protection) |
| Unused | ~801 of the cap; S2 / S3 not run |

### Gate set (structure only, judged with a FRESH memory and F0; never by which memory wins)

The screen took 16 trials and 27.7 s (`artifacts/agi9b_dev/screen.jsonl`). It selected 12 development projects, all
with a reachable repair candidate:
- **6 multi-conflict** (P5, all reachable), with K = 2–3 simultaneously open conflicting or unclaimed points and ≥ 1
  documented conflict. The fresh memory abstains on all 6.
- **6 other:** legacy disagreement × 2, single conflict, undecided, benign, multi-fault composite.

The set is disjoint from the unopened `agi9de/confirm`. Every step appended and flushed one JSON line per project.

### The six controls (rules predeclared in `scripts/agi9b_gate.py`; `artifacts/agi9b_dev/gate.json`)

| # | Control | Result | Pass? |
|---|---|---|---|
| 1 | Reordered / renamed memory | identical verified set (9 / 12), 0 wrong | **pass** |
| 2 | Extra irrelevant memory | no gain, 0 wrong | **pass** |
| 3 | Trust removed | multi-conflict **4 / 6 → 0 / 6**; questions 4 → 8; overall 9 → 5 | **pass** |
| 4 | Trust corrupted | multi-conflict **4 / 6 → 0 / 6**, **0 wrong** (fails safe by abstaining) | **pass** |
| 5 | Redundant computation | identical memories and gate-set results (9 = 9). Acquisition cost 76.5 vs 36.8; the rule selects the normal learner (88.5 vs 128.2 total) and never the redundant one | **pass** |
| 6 | Skill / utility removal | **no separating case** (below) | **FAIL** |

**Control 6 in detail.** L\* is the union of every admitted method of the Phase 7 and 8 checkpoints: 6 canonical methods.
It was compared with plain base search at the same total budget (W = 3,000).
- **First screen** (12 projects: P2, P6, P4, X1, all faults): identical completions on 12 / 12.
- **Disclosed extension** (all-fault composites, the only regime where base search exhausts its budget): 6 X1 projects,
  identical completions (3 solved by both, 3 failed by both). The X2 all-fault specs could not be generated.
- **What the library does change:** on **4 / 4 P6 projects** (two engines, two seeds), the method queue accepted a
  learned method and work fell from ~193 to 85 runs (**−56 %**), but base search solved them too. On P2 / P4 / X1 the
  library cost about +5 runs (the slice spent before base search).
- **Conclusion:** the method channel is **sensitive to cost** and **insensitive to completion**. No admitted method
  enables a completion the base search misses at this budget, so there was nothing to replicate.
- **Rule 6 was predeclared as completion-based and was not changed after seeing the data.**

**Gate: 5 / 6, NOT passed.** As instructed, the **18-project one-use confirmation set stays unopened**, and the
two-parent paired comparison was not run.

### What 9B establishes

- **The comparator now measures the future value of acquired evidence.** On reachable projects with more open conflicts
  than questions, the trained memory's calibrated trust is necessary for every multi-conflict completion it makes: 4 / 6
  with trust, 0 / 6 without or with corrupted trust. Corruption never produced a wrong submission.
- It does not reward equivalent or irrelevant memory, and it recognises equal knowledge acquired at higher cost.
- **Learned methods are cost devices, not capability devices,** in every library NEXUS has built (Phases 7–9). This is
  a substantive finding about NEXUS, not only about the gate.

### Owner decision needed (not taken autonomously)

The gate cannot pass as written until NEXUS has a method that enables a completion. Two honest options:
1. **Accept a cost-based skill control** for the next run: "removing L\* raises total work by ≥ 10 % on comparable correct
   completions, with 0 wrong". The P6 evidence (−56 %, 4 / 4, replicated across engines and seeds) would satisfy it. It
   must be predeclared and approved **before** the confirmation set is opened, not substituted now.
2. **Keep the completion rule**, and first make method invention target budget-binding failures: mine methods from the
   partial programs of composites where base search exhausts its budget.

With either decision, the paired two-parent comparison and the one-use confirmation set remain available. The
**~801 s** left under the 950 s cap covers the costed Stage 2 (~420 s) plus Stage 3 (~150–300 s).

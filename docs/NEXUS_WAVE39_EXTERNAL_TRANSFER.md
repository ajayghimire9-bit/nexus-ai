# NEXUS Wave 39: external transfer, scope-relative certificates and cheap adaptation (NOT LOCKED)

* **Branch:** `codex/nexus-broader-programme`, continued from `68f0036`.
* **Unchanged:** `main` and `final_sealed`; Checkers v1–v4 (v4 pin `c07e21ec…`); the OS meter; the sandbox; N1.
* **New:** Checker v5 (pin `2cd3a4ca…`, commit `622a29a`), separately versioned, standard library only.
* **Compute grant:** carried at 21,637 s. Every run is logged in the hash-chained ledger, and `scripts/w39_budget.py`
  gives the tally.

## Data quarantine

| Split | What | Status |
| --- | --- | --- |
| **PROSE-dev** | The 40 PROSE `Transformation.Text` tasks run or inspected in Wave 38 (`artifacts/external/prose`) | Development data. Used to diagnose failures and to design and calibrate v5. Never used as evidence of transfer. |
| **PROSE-confirm** | 129 untouched tasks: **all 66 tasks of the 22 families that have no task in PROSE-dev** (withheld external families), plus 63 untouched tasks of PROSE-dev families chosen by SHA-256 rank of the task name | Selected from task names only. Downloaded by `curl` into the sealed vault outside the repo and hashed by `shasum`; no tuner process opened them. The manifest is in `artifacts/external/prose_confirm/MANIFEST.json`. Only the frozen runner reads the files (`NEXUS_SEALED_HARNESS_TOKEN`), after verifying every hash. |

## Step 1: why external tasks failed (4-way taxonomy on PROSE-dev)

**Method:** `scripts/w39_audit_prose_dev.py`, recorded in `artifacts/w39_step1_audit.json`.
* The Wave 38 Stage 4 search was rerun locally with the same declared v4 scope, depth 3 and a budget of 2M executions,
  for Fresh and Repr.
* For each failure the audit records whether the scope was **enumerated to exhaustion** or the **budget** ran out.
* A depth-4 search with a 10× budget is a sensitivity check.

| Bucket | Count | % of the 31 failures | % of the 35 evaluable tasks |
| --- | --- | --- | --- |
| 1 Missing expressiveness (28 exhausted the depth-3 scope; 1 multi-column input the v4 harness cannot express) | **29** | **93.5%** | 82.9% |
| 2 Search-budget exhaustion | **0** | 0% | 0% |
| 3 Misleading prior (Fresh solves, Repr does not) | **0** | 0% | 0% |
| 4 Insufficient examples: fits all public pairs, fails held-out (DateTime.000041 certified UNIQUE in scope; Phone.000017 AMBIGUOUS) | **2** | 6.5% | 5.7% |
| Solved (certified, every held-out pair passes) | 4 | — | 11.4% |
| Not evaluable (fewer than 4 examples, so no 3 public + held-out split) | 5 | outside the taxonomy | — |

**The budget was never binding.** Every failing search exhausted the declared depth-3 scope at ≤ 36k executions (the
budget was 2M), and the depth-4 run with a 10× budget found nothing either.

**Diagnosis of the 29 expressiveness failures** (inspection of dev data):

| Missing capability | Tasks |
| --- | --- |
| Exact decimal arithmetic (rounding to k places, rounding to steps of 0.5, shifting by powers of ten) | 12 Number tasks |
| Signed indexing and slicing of words and characters | Name.000022, DateTime.000107, ShippingCode.000002 |
| Character-class token extraction | Currency, Team |
| Shape-based selection with a default (`NULL`) | Phone.000002 |
| Constant affixes (`425-`) | Phone.000014 |
| Zero padding | Number.000093 |
| Calendar knowledge (weekdays, month names, time buckets) | 6 DateTime tasks |
| A lookup table (Woman → Mrs) | Honorific |
| Position templates | SSN layout, `875 92` |
| Product units | Product |

Wave 39 deliberately leaves calendar knowledge, lookup tables and position templates **unadded**: they would be
domain- or task-specific macros.

## Step 2: general capabilities (Checker v5) and the output contract

Checker v5 (`docs/NEXUS_CHECKER_V5_SPEC.md`) adds 7 lambdas and 4 tools, all general, with no task-specific macros:
* signed `at` and `sl`;
* `cap` and `shape`;
* `pad`;
* exact decimal `dsh` and `drnd`;
* the `fn`, `toks`, `first` and `dflt` tools.

It also adds sound final-layer type pruning and a 256-character string bound, and fixes the internal error marker. The
v4 kernel uses `None`, which conflates a legitimate `None` result with an error. v4 itself is untouched and this quirk
is disclosed.

**Validation:**
* 1,101,915 tool–value pairs agree between the independent prover and kernel interpreters;
* brute-force agreement holds for verdicts, AMBIGUOUS witnesses, per-input answer counts and leave-one-out sets;
* the adversarial suite passes.

**The scope is data-keyed:**
* decimal operations appear only when an input is a decimal string;
* affixes, padding widths, output shapes and literals (an output string seen at least twice that occurs in no input)
  come from the public outputs only.

The same declaration applies to every arm.

**Output contract:**
* `SCOPE_UNIQUE (v5)`: unique within the finite v5 scope on the public examples, with `scope_relative: true`.
* Per-input uniqueness on future inputs: up to 16 held-out **inputs**; their outputs are never shown.
* `UNDER_SPECIFIED_WARNING`: some future input has more than one answer among the chains that fit all public pairs.
* `HELD_OUT_VERIFIED`: issued by the harness, from unseen held-out pairs.

**Calibration on PROSE-dev only** (229 answered inputs):

| Rule | Silent failures (wrong answer with no flag) | Correct answers flagged |
| --- | --- | --- |
| v4 contract (no per-input labels) | 21 | 0 |
| Flag inputs that are not unique in scope | **6** | 59 |
| Flag shape-novel inputs | 16 | 59 |

Shape novelty adds no catches, and leave-one-out fragility fires on almost every 3-example task. Both are therefore
reported but do not trigger the warning. The 6 residual silent failures are **scope-relative**: the true mechanism lies
outside the grammar, and every chain in the grammar agrees.

## Steps 3–5: development results (dev data only; these choose the frozen settings)

**Step 3 setup:**
* **One language for every arm:** the v5 scope, type pruning, search and checker are identical for Fresh-v5,
  Placebo-v5, Fixed-v5 (hand-designed, category d), Repr-v5 and the online arm. Only the search-order prior differs.
* **Fresh-v4** (Wave 38 language) isolates the human-engineering jump.

**PROSE-dev**, 35 evaluable tasks (`artifacts/w39_prose_dev.json`; dev, *engineered against*, so this is not evidence
of transfer):

| Arm | Certified | HELD_OUT_VERIFIED | Certified but held-out fail | Silent failures (v5 contract / v4 contract) | Work G |
| --- | --- | --- | --- | --- | --- |
| Fresh-v4 | 5 | 4 | 1 | 0 / 0 (5 inputs) | 93 |
| Fresh-v5 | 20 | 13 | 7 | 6 / 20 (179 inputs) | 1,736 |
| Placebo-v5 | 20 | 14 | 6 | 6 / 19 | 1,901 |
| Fixed-v5 | 20 | 12 | 8 | 6 / 22 | 1,730 |
| Repr-v5 | 20 | 13 | 7 | 6 / 20 | 1,730 |
| Online-hier-v5 | 20 | 14 | 6 | 6 / 19 | 1,823 |

* The coverage jump is language engineering: 4 → 12–14 verified.
* The learned priors do not change coverage, because every v5 arm certifies the same 20 tasks. Held-out differences
  come only from *which* scope-unique program each arm picks.
* Exhaustive certification is about 95% of v5 work on PROSE (the checker evaluates the whole depth-3 scope on the public
  examples, the query and up to 16 future inputs). It is identical across arms, so a search-order prior can only affect
  the remaining ~5%.
* Anytime curves are flat: every task is either solved early or exhausts its scope, so the caps never bind.
* Efficiency fix: the evaluator no longer re-checks evidence that is byte-identical to evidence it has already checked.
  This applies to every arm; Wave 38 always re-checked.

**Internal folds, dev seed 851** (4 folds × 2 source + 2 target instances; 70 targets; `artifacts/w39_lodo_dev_851.json`):

| Arm | Solved | Work G (fitting charged) | Solved @ 0.25× / 0.5× / 1× / 2× |
| --- | --- | --- | --- |
| Fresh-v5 | 70 | 2,013 | 66 / 70 / 70 / 70 |
| Placebo-v5 | 70 | 2,132 | 68 / 70 / 70 / 70 |
| Fixed-v5 | **69** | 1,538 | 69 / 69 / 69 / 69 |
| **Repr-v5** | 70 | **1,603** | **70 / 70 / 70 / 70** |
| Repr-core-v5 | 70 | 1,604 | 70 / 70 / 70 / 70 |

**Ratios:**
* Repr vs Fresh: 0.796, and 0.794 on the 69-task intersection.
* Repr vs Placebo: 0.752.
* Fixed is 4% cheaper but solves one task fewer and never reaches 70 at any cap, so it is **not** called cheaper.

**Source cost:**
* Extra curriculum: 2,974 G, break-even after 507 target tasks.
* Core set: 1,487 G, break-even after 255.
* Mandatory work: 0.017 G of fitting.

**Step 5a, world, dev** (3 seeds × 10,000 steps; `artifacts/w39_world_dev.json`):

| Agent | Return | Brier | Delay ret / new | Compute vs fixed-model |
| --- | --- | --- | --- | --- |
| reactive | 487 | 0.046 | 441 / 477 | 0.2× |
| fixed-model | 1,098 | 0.214 | 183 / 114 | 1× |
| N1-BOCPD | 1,973 | 0.044 | 16 / 14 | **156×** |
| **N1-merge-exact** | 1,990 | 0.045 | 15 / 15 | **2.8×** |
| N1-lite-prune (ε 1e-4, 16 runs) | 1,965 | 0.045 | 15 / 14 | 2.4× |
| N1-lite-prune8 (ε 1e-3, 8 runs) | 1,943 | 0.043 | 17 / 15 | 1.9× |
| N1-lite-gate 0.3 / 0.6 | 1,941 / 1,964 | 0.044 | 16–18 / 15–18 | 2.0–2.1× |

N1-merge-exact uses the same model as N1 with a different action RNG stream. Almost all of the 55× saving is **exact**
(lazy hazard aging on uninformative steps plus merging of identical posteriors). Pruning and gating add a little more.

**Step 5b, 6-phase stream, dev seed 852** (53 tasks, empty library; `artifacts/w39_stream_dev_852.json`):

| Learner | Total G | strings | graphs | tables | strings (ret) | graphs (ret) | grids | Solved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fresh | 1,239 | 154 | 53 | 462 | 120 | 52 | 397 | 52/53 |
| no-gate | 1,128 | 157 | 74 | 437 | 107 | 46 | 307 | 52/53 |
| regime memory (W38) | 1,227 | 157 | 54 | 462 | 111 | 46 | 397 | 52/53 |
| **hier s=1** | **1,117** | 153 | 73 | 435 | 106 | 46 | **303** | 52/53 |
| hier s=4 / s=16 | 1,122 / 1,123 | | | | | | | 52/53 |

The hierarchical prior keeps the return savings *and* the positive transfer to grids that regime memory blocked. On this
seed it equals no-gate within 1%. Shrink barely matters; s = 1 is frozen.

## Step 6 freeze: confirmation protocol (committed before any confirmation seed or PROSE-confirm file is opened)

**Frozen components:**
* Code: Checker v5 (pin `2cd3a4ca…`, commit `622a29a`), `w39_lang`, `w39_scope`, `w39_search`, `w39_learn`, `w39_online`,
  `w39_world` and `w39_eval`.
* Drivers: `scripts/w39_prose.py`, `w39_lodo.py`, `w39_world.py`, `w39_stream.py` and `w39_analyze.py`, at the freeze
  commit.
* Budget: the 2× cap is 4M executions per search; curves are read at 0.25×, 0.5×, 1× and 2× of 2M.
* Learner settings: `BASELINE_80F9CC2` for every online learner. The hierarchical shrink is **s = 1**, chosen
  on dev seed 852 only.
* Priors are trained only on internal source domains.

| Confirmation | Data (one use) | Primary comparison and verdict rule |
| --- | --- | --- |
| **C1** External PROSE | PROSE-confirm (129 sealed tasks: 66 withheld-family + 63 untouched dev-family); claim `wave39/confirm_prose` | **(a) Language engineering:** HELD_OUT_VERIFIED (HOV) of Fresh-v5 vs Fresh-v4, reported separately for withheld families. **(b) Learned experience: PROVED** if Repr-v5's HOV ≥ the HOV of Fresh-v5, Placebo-v5 and Fixed-v5, *and* its total work with fitting charged is lower than Fresh-v5's and Placebo-v5's, *and* its work on the intersection of tasks every arm verifies is lower than every control's. **PARTIAL** if it has HOV ≥ every control and beats some on work. **NEGATIVE** otherwise (also if any control has more HOV). **(c) Online:** Online-hier-v5 vs Fresh-v5, by the same rule. **(d) Contract:** silent held-out failures (wrong answer on an input labelled unique) under the v5 per-input contract vs the v4 contract, on the same Fresh-v5 answers. |
| **C2** Internal folds | `confirm_lodo5` 7831–7835: 4 folds × (2 source + 2 target instances) | **PROVED** if Repr-v5's total work (fitting charged) is lower than Fresh-v5's and Placebo-v5's, pooled and in ≥ 4/5 seeds, with solves ≥ every control (Fixed-v5 included) and 0 wrong. **PARTIAL** if it beats one of the two. **NEGATIVE** otherwise. A control is called "cheaper" only at an equal or higher solve count. Intersection ratios and curves are reported. |
| **C3** World | `confirm_world` 7836–7840, 10,000 steps each | **Cheap adaptation PROVED** for N1-merge-exact if, pooled, compute ≤ 10× fixed-model, return ≥ 0.97 × N1's, Brier ≤ N1's + 0.005, and return > fixed-model's in 5/5 seeds. The full frontier is reported. |
| **C4** 6-phase stream | `confirm_stream` 7841–7845 | **PROVED** if hier-s1's total work is lower than Fresh's, no-gate's and regime memory's, pooled and in ≥ 4/5 seeds, with solves ≥ each and 0 wrong. **PARTIAL** if it beats some. **NEGATIVE** otherwise. |

**Source accounting** (C1 and C2):
* *Mandatory work:* only the marginal fitting instructions count.
* *Extra curriculum:* source solving plus fitting, with a break-even count of target tasks.
* *Core-set check:* Repr-core-v5 uses one certified program per source mechanism, charged only for the source tasks it
  needs.

**Missing-data rule:** if a run hits the 890 s call cap, it resumes from its checkpoint (the per-task and per-fold
results are deterministic). Nothing is dropped, and every interruption is logged in the ledger.

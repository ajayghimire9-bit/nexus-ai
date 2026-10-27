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

## Step 6: confirmation results (each run once, after the freeze at `53ec39a`)

**Shared definitions:**
* *HOV* = HELD_OUT_VERIFIED: the program is certified SCOPE_UNIQUE and every held-out pair passes.
* *Silent failure* = a wrong answer on an input labelled unique.

### C1: external PROSE-confirm (129 sealed tasks; 118 evaluable under v5; `artifacts/w39_prose_confirm.json`)

| Arm | All: HOV / certified | Withheld families: HOV / certified | Untouched dev-family: HOV / certified | Silent failures (v5 / v4 contract) | Work G |
| --- | --- | --- | --- | --- | --- |
| Fresh-v4 | 13 / 16 | 4 / 6 | 9 / 10 | 1 / 1 (16 inputs) | 370 |
| **Fresh-v5** | **27** / 31 | **11** / 15 | **16** / 16 | **7 / 13** (248 inputs) | 2,304 |
| Placebo-v5 | 26 / 31 | 10 / 15 | 16 / 16 | 7 / 14 | 2,884 |
| Fixed-v5 | 25 / 28 | 11 / 14 | 14 / 14 | 2 / 8 (219 inputs) | 2,196 |
| **Repr-v5** | **27** / 31 | 11 / 15 | 16 / 16 | 7 / 13 | **2,295** |
| Repr-core-v5 | 27 / 31 | 11 / 15 | 16 / 16 | 7 / 13 | 2,294 |
| Online-hier-v5 | 27 / 31 | 11 / 15 | 16 / 16 | 7 / 14 | 2,766 |

**(a) Language engineering transfers to untouched tasks.**
* HOV rises from 13 to 27 in total.
* On the 22 never-inspected families it rises from 4 to 11.
* The curves are flat at every cap (0.25× to 2×).

**(b) Learned experience on external tasks: PROVED under the frozen rule, but negligible in size.**
* Repr-v5 has 27 HOV, against 27, 26 and 25 for Fresh-v5, Placebo-v5 and Fixed-v5.
* Its total work with fitting charged is 0.996× Fresh's (−0.4%) and 0.80× Placebo's.
* On the 24-task intersection it is cheapest: 421.6 G, against 424.9 (Fresh), 486.2 (Placebo) and 422.8 (Fixed).
* The saving (9.3 G over 118 tasks) never repays the internal source curriculum (941 G): break-even would take about
  11,900 tasks.
* The reason: certification is about 95% of the work and is identical across arms.

**(c) Online-hier-v5 is NEGATIVE:** HOV equals Fresh's, but it costs 1.20× as much.

**(d) The contract halves silent failures,** from 13 to 7 on the same Fresh-v5 answers. 12 of 31 certified tasks carry
UNDER_SPECIFIED_WARNING. 4 certified programs still fail held-out pairs (scope-relative).

**Fixed-v5 certifies 3 fewer tasks, and the cause is a search defect, not the prior.**
* The shared best-first search (inherited unchanged from Wave 38) deduplicates value vectors under a depth limit.
* Under a non-uniform prior, a deeper chain can reach a vector before a shallower one and block the shallower one's
  extensions. The search then ends with `no_candidate` well under budget.
* Uniform Fresh expands breadth-first and is unaffected.
* Every solve lost only by Fixed is this artifact: PROSE DateTime.000003, DateTime.000102 and EmergencyCall.000004, and
  the internal `present_names` tasks.
* **Wave 38's "the fixed DSL loses solves" finding (149 vs 159) must be read with this in mind.**
* It is not fixed here, because the code is frozen. It is the first thing to fix next.

### C2: internal folds, `confirm_lodo5` 7831–7835 (4 folds × 5 seeds; 350 targets; `artifacts/w39_lodo_confirm_78*.json`)

| Arm | Solved | Wrong | Work G (fitting charged) | Solved @ 0.25× / 0.5× / 1× / 2× | Work G @ 0.25× |
| --- | --- | --- | --- | --- | --- |
| Fresh-v5 | 346 | 0 | 10,409 | 326 / 346 / 346 / 346 | 8,046 |
| Placebo-v5 | 346 | 0 | 10,859 | 344 / 346 / 346 / 346 | 10,638 |
| Fixed-v5 | 344 | 0 | 8,004 | 344 / 344 / 344 / 344 | 8,004 |
| **Repr-v5** | **346** | 0 | **8,323** | **346 / 346 / 346 / 346** | 8,323 |
| Repr-core-v5 | 346 | 0 | 8,331 | 346 / 346 / 346 / 346 | 8,331 |

**PROVED under the frozen rule.**
* Repr-v5 costs 0.800× Fresh and 0.766× Placebo with fitting charged, winning 5/5 seeds on both at equal solves, with
  0 wrong answers.
* Matched quality, on the 344 tasks every arm solved:
  * 0.798× Fresh;
  * 0.767× Placebo;
  * 1.036× Fixed.

  Fixed is 3.6% cheaper but solves 2 fewer, and both lost tasks are the dedup artifact above.
* Repr is the only arm that reaches full coverage at the 0.25× cap.

**Source accounting** (per prior; each fold trains its own prior):

| Accounting | Cost | Break-even (target tasks per prior) |
| --- | --- | --- |
| Mandatory work: marginal fitting only | 0.087 G pooled | immediate |
| Extra curriculum | 734 G per prior | 123 |
| Compact core set (one program per mechanism) | 365 G per prior | 62, with the same savings (8,331 G vs 8,323 G) |

Each fold has 17.5 targets, so as a curriculum the prior is not repaid within one fold.

### C3: world, `confirm_world` 7836–7840 (5 × 10,000 steps; `artifacts/w39_world_confirm.json`)

| Agent | Return | Brier | Delay ret / new | Compute vs fixed-model |
| --- | --- | --- | --- | --- |
| reactive | 528 | 0.050 | 441 / 367 | 0.2× |
| fixed-model | 1,168 | 0.209 | 169 / 117 | 1× |
| N1-BOCPD | 1,969 | 0.044 | 15 / 13 | 156× |
| **N1-merge-exact** | **1,975** | **0.043** | 14 / 15 | **2.8×** |
| N1-lite-prune | 1,979 | 0.041 | 15 / 14 | 2.3× |
| N1-lite-prune8 | 1,991 | 0.042 | 15 / 14 | 1.9× |
| N1-lite-gate 0.3 / 0.6 | 1,968 / 1,951 | 0.043 | 15–16 / 14–16 | 2.0–2.1× |

**Cheap adaptation PROVED.** N1-merge-exact needs 2.8× fixed-model compute (≤ 10×). Its return is 1.003× N1's (≥ 0.97),
and its Brier score is 0.043 against N1's 0.044. It beats fixed-model in 5/5 seeds. N1's quality now costs 2–3× a
non-adaptive model instead of 156×.

### C4: 6-phase stream, `confirm_stream` 7841–7845 (`artifacts/w39_stream_confirm_78*.json`)

| Learner | Pooled work G | Solved | Cheapest in seeds |
| --- | --- | --- | --- |
| Fresh | 6,360 | 265/265 | 0 |
| no-gate | 5,762 | 265/265 | 0 |
| regime memory | 6,351 | 265/265 | 0 |
| **hier s=1** | **5,643** | **262/265** | 5/5 |

**NEGATIVE under the frozen rule:** quality was not preserved.
* Hier is cheapest in every seed: −11.3% vs Fresh, −11.1% vs regime memory, −2.1% vs no-gate.
* It keeps both the return savings and the grids transfer.
* But it loses 3 solves (seeds 7842, 7843 and 7845), and the rule requires solves ≥ every control. The cause was not
  recorded (these stream rows do not keep per-task status). The dedup defect is a plausible but **unverified**
  explanation.

## Updated Capability Proof Matrix (Wave 38 + Wave 39)

| Capability / experiment | Domains (internal + external) | Held-out solve / return | Work vs strongest quality-preserving control (excl. / incl. source cost) | Repeatability | Certificate class | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Language engineering (v4 → v5) | PROSE-confirm (66 withheld-family + 63 untouched) | HOV 13 → 27; withheld families 4 → 11 | n/a: human engineering, not NEXUS learning; costs about 6× more work per task (certification) | one-use | SCOPE_UNIQUE + HELD_OUT_VERIFIED | **PROVED** (engineering transfers; not attributed to NEXUS) |
| Cross-domain transfer, internal (v5) | 4 program domains, LODO | 346/350 (= Fresh = Placebo; Fixed 344) | 0.800 vs Fresh, 0.766 vs Placebo (fitting charged); 1.036 vs Fixed on the matched set. Incl. source: break-even 123 targets per prior (core set 62) | 5/5 seeds × 4 folds | SCOPE_UNIQUE (v5), 0 wrong | **PROVED** (Fixed's lower cost comes with fewer solves, from a search artifact) |
| External transfer of learned experience | PROSE-confirm, prior trained on internal sources only | HOV 27 (= Fresh; Placebo 26; Fixed 25) | 0.996 vs Fresh; intersection 0.992; never repays the curriculum (~11,900 tasks) | one-use, 1 run | SCOPE_UNIQUE + HELD_OUT_VERIFIED | **PROVED by rule, negligible in size** (practically NEGATIVE) |
| Online learning on the external stream | PROSE-confirm | HOV 27 (= Fresh) | 1.20 vs Fresh | 1 run | same | **NEGATIVE** |
| Scope-relative honesty (UNDER_SPECIFIED_WARNING) | PROSE-confirm | silent failures 13 → 7 | n/a | one-use | per-input SCOPE_UNIQUE | **PARTIAL** (halved; 4 certified programs still fail held-out pairs) |
| Cheap adaptation (N1-lite) | SwitchGrid world | return 1,975 vs N1's 1,969; Brier 0.043 | 2.8× fixed-model (N1: 156×) | 5/5 seeds | CALIBRATED_PREDICTION | **PROVED** |
| Hierarchical stream memory | 6-phase program stream | 262/265 (controls 265) | −11% vs Fresh, −2% vs no-gate | cheapest 5/5, but loses 3 solves | SCOPE_UNIQUE, 0 wrong | **NEGATIVE** (quality not preserved) |
| Wave 38 rows (meta-learning, evolution, neural ranker, planning, repairs) | — | unchanged | — | — | — | NEGATIVE / NEGATIVE / NEGATIVE / NEGATIVE / INCONCLUSIVE |

## What this establishes, and what it does not

**Established:**
* Experience from three internal domains makes certified program discovery in a withheld fourth domain about 20% cheaper
  at equal quality. This replicates Wave 38's result under a richer language and against a stronger matched placebo.
* The general constructs found by diagnosing PROSE-dev **do** transfer to untouched external tasks and families: 2.1×
  the verified coverage.
* The world-model adaptation that was 156× expensive is now about 3× a non-adaptive model, at the same quality.

**Not established:**
* That internal experience helps on external tasks in any practical sense: the gain is −0.4%, and certification
  dominates the cost.
* That the hierarchical memory preserves quality.
* That a hand-designed prior is genuinely worse: its losses come from a search artifact.
* Anything beyond the declared finite scope: certificates remain scope-relative, and 4 of 31 certified external
  programs fail held-out pairs.

**Next experiment:** fix the depth-aware dedup defect in the search, so that a node is re-expanded when it is reached
at a shallower depth. Then rerun only the frozen C2 and C4 protocols on fresh seeds. That settles whether the
hand-designed prior and the hierarchical memory lose solves for real or only through the defect.

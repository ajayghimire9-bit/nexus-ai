# Wave 31 (development increment 1, NOT LOCKED): shared middle IR, 4 surface domains, transfer controls

Branch `codex/wave31-middle-ir-domains`, from Wave 30 `57fb88d`. Wave 30 results stay NOT LOCKED development
evidence. Wave 29's `c78d476` and `final_sealed` are untouched.

**Prompt note.** The owner's full Wave 31 prompt was not available in this session; only the roadmap line and the
2026-10-26 instruction list were. This increment implements those items and should be reconciled with the full
prompt.

## Checker

**All Wave 31 certificates come from Checker v2.** It has pin `6ba0a268…`, committed in `01d84f6`, and the runner
verifies it from that git object. v1 is untouched.

**v2 extension, disclosed.** Before v2's first use, it was extended with the Wave 31 adapters and a bounded `seq`
macro op, under the owner's v2 authorisation; no evidence was ever checked under the earlier pin.

## Built

Code: `src/nexus/wave31_ir.py` and `scripts/wave31_dev.py`, with 4 tests plus the v2 suite.

* **Middle IR:** Sequence, Counter, ObjectSet and RelationGraph. These are checker v2 types with explicit bounds.
* **Thin surface adapters φ_d** (identical for every arm):
  * strings: enc_chars / dec_chars;
  * grids: enc_cells, and enc_objects / dec_objects;
  * graphs: ir_graph_degrees (a RelationGraph surface is already IR);
  * lists: identity.
* **Adapter audit.** Adapter ops are charged in their own meter category. enc_objects does connected-component
  analysis, which is substantive. Adapter work was 0.4–11% of total work in every cell.
* **Typed skeletons.** Certified source programs are reduced to their cores (adapters stripped) and
  anti-unified pairwise. Integer holes are instantiated from {1, 2, 3}. Skeletons and their contiguous
  sub-skeletons (length ≥ 2) become `seq` macros.
* **Transfer controls** (identical primitives and adapters):
  * Fresh: G_P, depth ≤ 4;
  * Useful: G_P plus macros learned on lists and strings, depth ≤ 2, escalating to G_P depth ≤ 4 when nothing
    fits;
  * Size-matched Placebo: the same number of macros with the same length distribution, built from irrelevant
    random IR ops.
* **Evaluator-only labels:** domain, mechanism, transfer category. The solver signature is
  `(arm, public, query, library)`, and a test enforces it.
* **Prover.** It executes with v2's interpreter (disclosed). Only the checker decides; it re-enumerates and
  re-executes everything itself. The prover is passive (no probes in this increment).

## Development diagnostics (dev seeds 761–765)

* Source: 60 tasks on lists and strings, 58 exhaustively certified, giving 50 macros in total (10 per seed).
* Target: 50 tasks on grids and graphs.
* Source-learning cost: 11.53M, billed separately.

| Arm | Category | Correct | Exhaustive (relative to own grammar) | Wrong (outside / inside scope) | Escalated | Work | Checker share | Adapter work |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fresh | familiar mechanism, new surface (30) | 30 | 30 | 0 / 0 | — | 14.01M | 97.8% | 71k |
| Useful | familiar mechanism, new surface (30) | 30 | 30 | 0 / 0 | 0 | **0.11M** | 63% | 13k |
| Placebo | familiar mechanism, new surface (30) | 30 | 30 | 0 / 0 | 27 | 13.52M | 97.6% | 70k |
| Fresh | held-out mechanism (20) | 20 | 20 | 0 / 0 | — | 7.60M | 97.9% | 32k |
| Useful | held-out mechanism (20) | 20 | 20 | 0 / 0 | 10 | 6.06M | 97.4% | 27k |
| Placebo | held-out mechanism (20) | 20 | 20 | 0 / 0 | 10 | 6.05M | 97.5% | 27k |

## Reading (development evidence only)

**(a) Familiar mechanism, new surface.**
* The learned macros make certification about 127× cheaper than Fresh, and the size-matched Placebo does
  **not** get this gain: it escalates on 27/30.
* So the saving depends on the *content* of the source-derived representation, not merely on a smaller grammar.
* Charging the 11.5M source cost to these 30 tasks, Useful totals about 11.6M against Fresh's 14.0M.

**(b) Held-out mechanisms.**
* **No content advantage.** Useful equals Placebo.
* Both are cheaper than Fresh only because some held-out programs (graph reach, depth 1) lie within the depth-2
  grammar.
* The others escalate to G_P.

**Certificate meaning.**
* Useful's certificates are exhaustive relative to G_P plus macros at depth ≤ 2, which is **not** the same
  grammar as Fresh's G_P at depth ≤ 4. A scope-relative UNIQUE can hide alternatives outside it.
* On these tasks Fresh's G_P-exhaustive verdicts gave the same (correct) answers, and no wrong answer from outside
  the scope occurred. A larger, adversarial distribution is needed before relying on this.

**Limits.**
* The adapters are **supplied**, not learned.
* Familiar target mechanisms use exactly the source cores, so this is mechanism reuse across surfaces, not
  acquisition of a new mechanism.
* n = 50 target tasks on dev seeds, with passive observation.
* proposal-relative agreement was never used.

## Remaining blockers and next steps

* Reconcile with the full Wave 31 prompt: domains, controls, gates.
* Add an adversarial distribution where macro grammars invite wrong answers from outside their scope, and active
  probing.
* Run admission_val (7101–7105) for admission decisions net of all costs.
* Learned adapters, as opposed to supplied ones.
* Coder arms (A2 / A3 / A4) remain `BLOCKED_MODEL_QUALITY`. Both local 1.5B checkpoints are capability-limited
  after the integration fixes.
* **Wave 32 is not started**, per the readiness conditions.
  * Done: Checker v2 is built and pinned, and Wave 30 / 31 baselines are reconciled at development level.
  * Still required: an evaluator and meter independent of the solver process, and an explicit Wave 32 budget.

---

# Increment 2 protocol (NOT LOCKED; written and committed before the dev 762–765 and admission_val outcomes)

Owner decisions of 2026-10-26: close the depth-2-vs-depth-3 scope loophole; four-domain LODO with compositional
skeleton targets; an independent evaluator / meter boundary; dev, then admission_val once. Increment 1 code and
results are unchanged.

**Corrections to the owner's brief (factual):**
* Increment 1's Fresh enumerated G_P at depth ≤ **4**, not 3.
* The increment-1 held-out work was Useful 6.06M / Fresh 7.60M / Placebo 6.05M (not 6.86M).
* The pinned Checker v2 sha256 is **`6ba0a268…`** (pin commit 01d84f6), not `b1d6c5d1…`. No other v2 pin exists.

Increment 2 adopts the owner's framing, a **depth-3** matched scope, over a new fixed primitive grammar.

**Disclosure:** one dev seed (761) was used for smoke runs while building this, and the adversarial tiers were
added after the first smoke found too few strict cases. Seeds 762–765 and admission_val are unseen.

## Design

* **Domains and leaves φ_d** (thin adapters into the middle-IR Sequence; checker v2 ops), identical for every arm:
  * records `proj a`;
  * strings `enc_chars`;
  * grids `enc_cells`;
  * graphs `ir_graph_reach{seeds:[0]}`.
* **G_P** (`wave31_grammar.G_P`, 18 fixed ops): the 4 leaves, plus `proj b`, `dec_chars`, `ir_graph_degrees`,
  `enc_objects`, `ir_objects_sizes`, `enc_counter`, `ir_counter_top{1}`, `ir_counter_keys`, and the core ops
  Sort, run_heads, rotate{1}, prefix_sum, diff, running_max.
* **LODO rotation.** For each held-out domain h, the source tasks come from the other 3 domains (cores
  S = {Sort·RUNH, Sort·diff, Sort·prefix_sum, rotate·diff, rotate·prefix_sum, RUNH·rotate}; strings use only
  the non-numeric ones). The targets are on h, with teacher = φ_h + core:
  * `familiar_exact`: a core seen verbatim in source, on the new surface.
  * `compositional`: a core never seen in source, but an instance of a learned skeleton:
    * [Sort,?] gives Sort·running_max;
    * [rotate,?] gives rotate·running_max;
    * [?,diff] gives RUNH·diff;
    * [?,prefix_sum] gives RUNH·prefix_sum;
    * for strings, Sort·rotate and rotate·RUNH.

    The skeleton is learned across the 3 source domains and instantiated with G_P ops on the held-out domain,
    whose leaf adapter never appears in that fold's sources.
  * `held_out`: no skeleton support (running_max·rotate, diff·Sort; strings RUNH·Sort).
  * `adversarial_strict` / `adversarial_weak`: built per fold *after* the Useful library is frozen, by an
    adversary that knows it. The teachers are φ_h + 2 G_P ops (inside the matched scope), with 3 passive demos.
    * Strict: every macro-scope program that fits the demos gives the same wrong answer.
    * Weak: some fitting macro-scope program gives a wrong answer.
* **Library** (solver side, source-only feedback):
  * The evaluator returns the source candidates that its own checker labelled exhaustive_UNIQUE.
  * Leaves are stripped to cores, and pairwise **op-level** anti-unification (`anti_unify_ops`, which extends
    wave30_skeleton's constant-only version) gives typed skeletons. Skeletons with no concrete op are dropped.
  * Op holes are instantiated with the 12 non-adapter G_P ops, and each instance is a `seq` macro.
  * **Placebo:** the same skeleton shapes (hole positions) with concrete ops from an irrelevant pool, instantiated
    the same way; macro counts are reported.
* **Arms × modes** (5 configs): Fresh/matched, Useful/matched, Placebo/matched, Useful/macro, Placebo/macro.
  * **Proposal:**
    * Fresh: first-fit layered search over G_P, depth ≤ 3, with observational dedup. This is a stronger baseline
      than increment 1's full enumeration, because the kernel verdict does not depend on which fitting candidate
      is submitted.
    * Useful / Placebo: first-fit over G_P + macros at depth ≤ 2, then G_P.
  * **matched:**
    * The candidate is expanded to G_P ops (seq bodies inlined) and checked over exactly the matched scope
      (G_P, depth 3).
    * The same kernel-checkable list-op pruning lemmas are supplied for every arm. A macro candidate that
      expands outside the matched scope falls back to G_P (charged).
    * This is the only route to a reported `exhaustive_UNIQUE`, so the certificate strength is identical across
      arms by construction. I chose Fresh's exact scope over a G_P ∪ macros union: a union scope is a larger,
      different grammar, matched to neither arm.
  * **macro:** checked over G_P + macros, depth 2. A UNIQUE verdict is reported as **`MACRO_SCOPE_UNIQUE`** and
    never pooled with exhaustive_UNIQUE.
  * **Active probing** (every arm, both modes, ≤ 3 oracle calls per task): on AMBIGUOUS, mutate public inputs
    until the kernel's two witnesses disagree, ask the oracle, add the pair and re-propose.
* **Evaluator / meter boundary** (`wave31_evaluator`):
  * **Isolation:** the solver runs in a child under `sandbox-exec`, which denies writes to the repository,
    reads of the sealed vault, and network access. The child gets a clean environment and sees TaskViews only.
  * **Checker and oracle:** both are served by the evaluator.
  * **Meters the solver cannot alter:**
    * kernel work (steps + chains), over every check including the evaluator's final re-check;
    * oracle calls;
    * the child's CPU seconds (`wait4` rusage);
    * prover work, which is solver-reported and labelled as such.
  * **Evidence audit:** final evidence public pairs must equal the passive pairs plus exactly the pairs the
    oracle answered for that task; otherwise `INVALID_EVIDENCE`.
  * **Ledger:** the evaluator alone appends to it, with a sha256 hash chain.

## Predeclared readouts (development diagnostics, not admission gates)

* **R1, soundness:** 0 wrong `exhaustive_UNIQUE` in every matched config, including the adversarial tiers.
  Macro-mode wrong answers are expected on `adversarial_strict` and are reported as wrong_teacher_outside_scope.
* **R2, cost at matched strength:** target-only work = evaluator kernel work + solver-reported prover work, per
  category, for Useful/matched vs Fresh/matched vs Placebo/matched. Source-amortised work adds that fold's source
  learning cost, spread over the fold's target tasks, to Useful and Placebo (Placebo is charged the same source
  cost, since its shapes come from the learned skeletons). The child's CPU seconds are reported alongside.
* **R3, macro scope:** coverage and correctness of `MACRO_SCOPE_UNIQUE` per category, Useful vs Placebo.
* **R4, replay:** one dev seed and one admission_val seed are rerun in a fresh process with a different
  `PYTHONHASHSEED`, and give the identical digest.
* **Splits:** dev 761–765, then admission_val 7101–7105 **once** (the driver refuses to overwrite an existing
  admission_val artifact). final_sealed is not touched.

# Increment 2 results (NOT LOCKED; development diagnostics)

Protocol and implementation commit: d7fb2c9.
* **Runs:** dev 761–765, then admission_val 7101–7105, run once.
* **Replays:** in a fresh process with `PYTHONHASHSEED=1`, the digests are identical (dev 763 `67243c22…`,
  admission_val 7103 `5cbd66a3…`), so R4 passes.
* **Checker:** Checker v2 `6ba0a268…`, verified from git object 01d84f6 by the evaluator.
* **Compute:** about 230 s for the LODO runs plus about 270 s on Metal for the coder.

## admission_val 7101–7105 (dev 761–765 agrees within a few tasks)

Each seed runs 4 LODO folds. Source: 600 tasks, all 600 certified exhaustive_UNIQUE, 0 wrong.

| Category (n) | Fresh / matched | Useful / matched | Placebo / matched | Useful / macro | Placebo / macro |
| --- | --- | --- | --- | --- | --- |
| familiar_exact (80) | 80 exh, 1.83M | 80 exh, 1.84M | 80 exh, 1.88M | 80 MACRO, 1.19M | 26 MACRO + 54 ABSTAIN |
| compositional (140) | 140 exh, 3.44M | 140 exh, 3.47M | 140 exh, 3.53M | **140 MACRO**, 2.22M | 52 MACRO (1 wrong) + 88 ABSTAIN |
| held_out (70) | 70 exh, 1.65M | 70 exh, 1.77M | 70 exh, 1.71M | 12 MACRO + 58 ABSTAIN | 12 MACRO + 58 ABSTAIN |
| adversarial_strict (8) | 8 exh after 8 probes | 8 exh | 8 exh | **8 wrong (outside scope)** | 8 wrong (outside scope) |
| adversarial_weak (31) | 31 exh after 32 probes | 31 exh | 31 exh | 29 correct, 1 wrong | 16 correct, 6 wrong |
| **All (329)** | **329 correct, 0 wrong**, 8.12M | **329 / 0**, 8.29M | **329 / 0**, 8.35M | 261 correct, **9 wrong**, 4.46M | 105 correct, 15 wrong, 2.04M |

* **Work** = evaluator-metered kernel work + solver-reported prover work, target-only.
* **Kernel work** in the matched configs is identical across arms (7.925M), by construction.
* **Source learning** costs 14.52M per split (kernel + prover). Charged to Useful and Placebo, the
  source-amortised totals are Useful 22.81M and Placebo 22.87M, against Fresh 8.12M.
* **Child CPU seconds** (unforgeable `wait4`): Fresh 1.02 s, Useful 1.40 s, Placebo 1.50 s (matched); source
  1.33 s.

## Reading

1. **R1 soundness: PASS.** 0 wrong `exhaustive_UNIQUE` in every matched config, on 329 admission tasks and 345 dev
   tasks, including every adversarial task. On adversarial_strict, the matched depth-3 check returned AMBIGUOUS
   with witnesses, and one distinguishing oracle probe per task resolved it correctly.
2. **The scope loophole is real and is now closed in reporting.** On adversarial_strict, the macro scope gives a
   *unique, wrong* answer in 8/8 admission tasks (12/12 dev), for both Useful and Placebo. Every one is
   wrong_teacher_outside_scope, and the certificate is honest only relative to its macro grammar. That is why
   `MACRO_SCOPE_UNIQUE` is never pooled with `exhaustive_UNIQUE`.
3. **At matched strength, experience gives no cost advantage here** (R2).
   * Useful/matched target-only work is 2.1% *above* Fresh/matched.
   * Source-amortised, it is 2.8× Fresh.
   * Mechanism: the verdict depends only on the scope, so certification work is identical for every arm, and a
     library can only cut proposal work. At depth 3 over 18 ops, Fresh's first-fit proposal is already only about
     2.4% of the total, and macro search adds more than it saves.
   * Increment 1's 127× familiar-surface saving came from comparing a depth-2 macro certificate with Fresh's
     depth-4 full enumeration. It does not survive matched strength.
4. **Macro-scope coverage is a real content effect** (R3).
   * Learned skeletons let the depth-2 macro scope cover 80/80 familiar and **140/140 compositional** targets, on
     a held-out domain whose leaf adapter never appeared in the sources.
   * The size-matched Placebo covers 26/80 and 52/140, with 1 wrong answer.
   * Held-out cores show no content advantage: 12/70 for both.
   * The cost is weaker certificates and adversarial wrong answers.
5. **Practical meaning.** A learned library is useful as a *proposal and coverage* device, and as a cheaper,
   explicitly weaker certificate class. At the strength of exhaustive_UNIQUE over G_P depth 3, it bought
   nothing in this regime.

**Limits:**
* G_P is small (18 ops) and the matched depth is 3, so proposal is cheap. A deeper or larger matched scope is
  where proposal savings could matter, and that is untested.
* Adapters are supplied, and the graph leaf (sorted reach set) makes some cores degenerate.
* Probes are oracle queries on mutated inputs. They are counted separately from work units.
* Only one adversary design was tested.

## Coder on Apple M4 Metal (owner grant 2026-10-26)

* **Grant and caps.** The grant is recorded in the session ledger. Caps: 60 s per call, a 1,800 s Metal
  session, and RSS of 4 GB (1.5B) or 7 GB (7B), on a separate Metal ledger.
* **Setup.** Same 16 tasks (wave30 dev seed 751), the same v4 prompt, and ≤ 4 attempts, so only the backend and
  checkpoint differ from the CPU diagnosis.
* **7B weights.** `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (official Qwen GGUF repo). The sha256 `509287f7…4d3c`
  matches the published LFS oid.

| Checkpoint | Backend | Tasks | Wall | Prompt / decode tok/s | GPU util (idle → run) | Correct | Final buckets |
| --- | --- | --- | --- | --- | --- | --- | --- |
| coder-1.5B Q4_K_M | Metal | 8 | 29 s (CPU earlier: 254 s) | 1,082 / 85 | 0 → 97% | 0/8 | 5 public-demo miss, 2 runtime, 1 unparsable |
| coder-1.5B Q4_K_M | Metal | 16 | 58 s | 1,105 / 85 | → 96% | 0/16 | 13 public-demo miss, 2 runtime, 1 unparsable |
| **coder-7B Q4_K_M** | Metal | 16 | **179 s** | 235 / 22.4 | → 99% | **3/16** | 9 public-demo miss, 4 runtime, 3 correct |

* **Metal speed.** About 8.7× faster than CPU at 1.5B. The 7B 16-task smoke ran in 3.0 min, under the owner's
  10-minute condition, with a peak RSS of 4.9 GB. Metal results differ slightly from the CPU runs (numerics),
  which is disclosed.
* **Buckets.** On the owner's 4-bucket scheme, across all 7B attempts: 7 unparsable, 12 runtime error, 33
  public-demo miss, 0 held-out miss (and 3 correct).
* **Capability.** The 7B is the first checkpoint to solve any coder-smoke task: all 3 are family A1. The dominant
  failure is still valid-but-wrong programs. Status moves from `BLOCKED_MODEL_QUALITY` to
  `WEAK_BUT_NONZERO (3/16)`.
* **No coder arm was run.**

## Wave 32 readiness

* **Done:** the independent evaluator / meter boundary exists and is tested:
  * sandboxed solver child;
  * evaluator-served checker and oracle;
  * unforgeable kernel, oracle and CPU meters;
  * evidence audit;
  * hash-chained ledger.
* **Remaining:** prover work is still solver-reported (audited by replay only). Wave 32 needs an explicit owner
  budget and protocol. No autonomous runs have been started.

---

# Correction to increment 2: oracle-on-query leak (found while building the Wave 32 detectors)

**What happened.** Probe inputs were mutations drawn from a pool that included the query input. A mutation can be
a no-op, so a probe could *equal* the query input, and the oracle then returned the answer.

**Audit.** The committed runs were replayed in a fresh process (every row reproduced exactly).

| Split | Leaked tasks per matched arm | Breakdown |
| --- | --- | --- |
| admission_val | **4 of 329** | 3 adversarial_weak, 1 compositional |
| dev | 4 of 345 | 1 adversarial_strict, 1 adversarial_weak, 2 compositional |

* **adversarial_strict:** 0 of 8 on admission_val leaked, so those rescues stand.
* **Soundness:** 0 wrong is unaffected.
* **Correctness:** the corrected admission_val figure is **325/329 uncontaminated correct per matched arm**. The
  admission run is not repeated, because it was run once.

**Fix.**
* The solver never probes the query input.
* The evaluator refuses, and flags (D3), any oracle request on the query input or beyond the cap.
* Increment-2 replays after the fix will differ only on those rows.

# External work meter (closes the self-reported work gap)

* **What it counts.** `evaluator_work` = retired CPU instructions of the solver child, as counted by the OS kernel
  (`proc_pid_rusage`, `RUSAGE_INFO_V4.ri_instructions`, read by the evaluator from outside the child). Added to
  that: the evaluator's own retired instructions spent on kernel checks, plus oracle queries × a declared price
  of 5·10⁷ instructions. Wall-clock time is recorded alongside.
* **Precision.** Repeat measurements agree to within 0.004%.
* **Why not an in-process profiler.** An in-process counter (`sys.setprofile` / `sys.monitoring`) can be disabled
  by the code it measures. The OS counter cannot be reached from the sandboxed child.
* **What the solver reports.** Its own numbers are kept only as `solver_reported`. They are never used for
  admission or ranking, and D5 flags implausible ones.
* **Detectors** (`wave32_detectors`):
  * D1 evidence audit;
  * D2 scope audit;
  * D3 oracle audit;
  * D4 integrity (source tree, pins and ledger hash chain);
  * D5 meter forgery.
* **Red-team children** (`scripts/wave32_redteam_child.py`): fabricate_pair is caught by D1, scope_downgrade by
  D2, oracle_on_query is refused by D3, tamper_files is blocked by the sandbox and verified by D4, and
  forge_meter is flagged by D5. The honest solver triggers none (`tests/test_wave32_detectors.py`).

# Increment 3 protocol (NOT LOCKED; committed before its dev 762–765 and val_inc3 7106–7110 outcomes)

The owner's next-experiment brief of 2026-10-26.

**Factual corrections to that brief:**
* Increment 2's admission_val was 329/329, now corrected to 325/329, not 258/258.
* At depth 3 the scope had 6,174 chains, and search was about 2.4% of work (not 7,280 chains and 9%).
* No 5-detector suite had been run before this commit.
* The v2 pin is `6ba0a268…`, not `b1d6c5d1…`.

**What Checker v2 can verify.** Checker v2 verifies only **postcondition lemmas on list ops** (len_le / all /
distinct / sorted, with preservation rules). It has no proof form for algebraic or observational-equivalence
collapses, and RULE 2 forbids changing it. So part (a) is run with v2-verifiable proofs. Learned algebraic
identities are reported only as a **projected** saving, and are never used to skip anything in a certificate.

## Design

* **Matched scope:** G_P (18 ops), **depth 4** (111,150 chains). Teachers are a leaf plus a 3-op core.
* **Source cores (S3):** Sort·RUNH·rotate, Sort·RUNH·diff, Sort·diff·prefix_sum, rotate·diff·prefix_sum,
  rotate·RUNH·Sort, RUNH·rotate·Sort.
* **Targets** per held-out domain:
  * familiar_exact: 2 cores;
  * compositional: 4 cores, instances of one-hole skeletons;
  * held_out: 2 cores;
  * strings: 2, 1 and 1 respectively.
* **Configs** (all matched, depth 4, exhaustive_UNIQUE strength), through the evaluator with the external meter:
  * Fresh-noL (no proofs);
  * Fresh-L (every v2-verifiable lemma: a generic, *non-learned* strong baseline);
  * Useful-L (learned macros + all lemmas);
  * Useful-learnedL (macros + only the lemma kinds that fired on ≥ 50% of source tasks);
  * Placebo-L.
* **Source learning:** Fresh, depth 4, with all lemmas. Skeletons have ≤ 1 hole. The learned observational
  identities (bigram ≡ shorter chain on ≥ 8 leaf-transformed source inputs) are used only for
  `projected_skip` = the fraction of the matched scope they would let a verifying checker skip. Their violations
  on target public inputs are counted.

## Readouts

* **I1:** 0 wrong exhaustive_UNIQUE in every config.
* **I2:** per category, target-only `evaluator_work`, and source-amortised work (fold source-learning work added
  to Useful and Placebo). Useful-L vs Fresh-L vs Placebo-L, plus Fresh-noL, which isolates the generic lemma
  effect.
* **I3:** projected_skip, and identity violations on targets.
* **Splits:** dev 761–765, where 761 (records fold) was used for one smoke before this commit; then val_inc3
  7106–7110, a one-use range claimed whole before running.

# Increment 3 results (NOT LOCKED)

Protocol commit: fa1c6fe.
* **Runs:** dev 761–765, and val_inc3 7106–7110, a one-use range claimed whole and run once.
* **Replays:** fresh process with `PYTHONHASHSEED=1`, identical digests (dev 763 `786f34d0…`, val 7108 `ea8ed980…`).
* **Wall time:** about 1,180 s for dev and 600 s for val.

## val_inc3: 280 target tasks, matched depth-4 G_P scope

Work is `evaluator_work` in G retired instructions (external meter).

| Config | exhaustive_UNIQUE / correct / wrong | Target-only work | vs Fresh-L |
| --- | --- | --- | --- |
| Fresh-noL (no proofs) | 280 / 280 / 0 | 1,727.0 | +1.44% |
| **Fresh-L** (all v2 lemmas, generic) | 280 / 280 / 0 | **1,702.6** | — |
| **Useful-L** (learned macros + all lemmas) | 280 / 280 / 0 | **1,695.5** | **−0.41%** |
| Useful-learnedL (source-selected lemma kinds) | 280 / 280 / 0 | 1,719.1 | +0.97% |
| Placebo-L | 280 / 280 / 0 | 1,709.1 | +0.38% |

* **Per seed:** Useful-L is below Fresh-L in 5/5 seeds (−0.21% … −0.50%) and below Placebo-L in 5/5 (−0.53% … −1.00%).
* **Net of source learning:** source learning costs 4,021.6 G per split (630 source tasks). Useful-L's total is
  therefore 5,717 G against Fresh-L's 1,703 G, or **3.36× worse**.
* **Where the work goes:** the evaluator's kernel instructions are **98.0%** of all work in every config.
  * Learned macros cut the solver's own (child) work by 21% against Fresh, and against Placebo by 35%.
  * That child work is only about 2% of the total.
* **Lemmas:** the v2-verifiable lemmas save 1.4% (Fresh-L vs Fresh-noL). No lemma kind fired on ≥ 50% of source
  tasks, so source-selected lemmas equal no lemmas.
* **Dev 761–765** shows the same picture: Useful-L −0.48% vs Fresh-L, and 280/280 correct, 0 wrong everywhere.

## Learned identities (projection only; v2 cannot verify them)

* **What was learned:** 10 identities per fold (Sort·Sort ≡ Sort, rotate·Sort ≡ Sort, Sort·running_max ≡ Sort,
  running_max·Sort ≡ running_max, prefix_sum·Sort ≡ prefix_sum, …). There were 0 violations on target public
  inputs.
* **Projected saving:** a checker that verified them would skip **8.4%** of the depth-4 scope.
* **Caveat:** prefix_sum·Sort ≡ prefix_sum holds only for non-negative inputs. It is an observation, not a law,
  which is exactly why it would need a real proof.

## Projection: a sound class-enumerating checker (v3-type; not built)

* **What it does:** enumerates *observational classes* (prefixes with identical values on all public inputs and
  the query, which is exact, needs no proofs and no learning) instead of every chain.
* **Measured:** on 12 val targets it reaches the same verdict as v2 on all 12, at a median **19.3× less work**.
* **Caveat:** this is generic and arm-independent. It is the prover's enumerator, so certifying with it would mean
  a new checker version, with independent re-implementation and validation under RULE 2 (owner approval).
* **What would change:** with it, the solver's share would rise from about 2% to roughly 25–30%, and Useful's 21%
  cut in child work would become a target-only saving of roughly 5–7% against Fresh, still before source cost.
  This is a projection, not a result.

## Reading: does Useful + verified pruning beat Fresh and Placebo at matched exhaustive strength?

* **Target-only:** yes, but negligibly: −0.41% vs Fresh and −0.79% vs Placebo, consistent over 5/5 seeds.
* **Net of source learning:** no, by 3.4×.
* **Why:** the bottleneck is the kernel's naive enumeration (98%). Experience cannot touch it under v2. The only
  pruning v2 verifies (postcondition lemmas) is generic and saves 1.4%. Learned algebraic collapses are
  unverifiable under v2.
* **Highest-value next step:** a separately versioned, independently validated class-enumerating Checker v3. It
  needs owner authorisation under RULE 2.

---

# Checker v3 and the Wave 31 v3 baseline matrix (NOT LOCKED)

## Checker v3

* **Commits:** pin commit 1642721; sha256 `3c68230e…20f`; spec `docs/NEXUS_CHECKER_V3_SPEC.md`.
* **Validation:**
  * 845+ random differential cases against v2;
  * targeted adversarial tests, each with a deliberately unsound variant (demo-only classes; two-representative
    truncation) that fails on the same evidence;
  * stateless probe refinement;
  * the step-bound logic, checked against direct enumeration;
  * bounded-exhaustive axiom checks;
  * proofs never change a verdict.
* **Identity:** **5,643 / 5,643 verdict-identical v2 checks on every existing Wave 31 task**
  (`artifacts/checker_v3_identity_*.json`): increment 1 (190), increment 2 (3,633), increment 3 (1,820).
* **Cost:** v3 uses 17.4× fewer retired instructions than v2 at depth 4, and 3.7× fewer at depth 3.
* **Pinned file:** the same file that ran the identity checks; there were no edits after them.
* **Wave 32 evolution** stays paused, per the owner.

## 4-way comparison protocol

Committed before the outcomes of dev 762–765 and val_v3 7111–7115. Dev 761 (records fold) was used for one smoke.

* **Suite:** the increment-3 tasks (depth-4 matched G_P scope, 3-op cores, LODO over 4 domains).
* **Checkers:** every arm in a comparison is graded by the same pinned checker, verified from its git object.
* **Meter:** `evaluator_work`, the OS retired-instruction meter (child + checker + oracle price). It includes all
  graph construction, class maintenance, proof checking, proof citation and library building.
* **Configs:**
  * Fresh-v2 (all v2 lemmas);
  * Fresh-v3 (no proofs);
  * Fresh-v3-allP (every axiom: generic);
  * Experienced-v3 (learned macros + source-learned axiom selection);
  * Placebo-v3 (size-matched macros + the same number of random axioms).
* **Source learning:** under v3. Source task i cites only axiom i mod 4. An axiom is "learned" if
  applied / checked ≥ 0.1 on the source verdicts. The cost is charged to Experienced and Placebo.
* **Comparisons, reported separately:**
  1. Fresh-v3 vs Fresh-v2;
  2. Experienced-v3 vs Fresh-v3, and vs Fresh-v3-allP;
  3. Experienced-v3 vs Placebo-v3;
  4. Experienced-v3 + source cost vs Fresh-v3.
* **Gate for the conditional Wave 32 v3 check (predeclared).** The check runs if, on val_v3, either:
  * Experienced-v3 < Fresh-v3 target-only in ≥ 4/5 seeds with a pooled saving ≥ 3% (a concrete policy lever); or
  * comparison 4 is < 1 (net-positive).

  The Wave 32 check would be a small evolution under v3 (≤ 4 generations × 4 children), then Gen k vs Gen 0
  (learning OFF) vs Gen 0 (learning ON) on held-out grids, on a fresh one-use range.

## 4-way results under Checker v3 (val_v3 7111–7115, run once; replay of 7113 identical; dev 761–765 agrees)

280 target tasks per config, all 280 exhaustive_UNIQUE and correct, 0 wrong, 0 INVALID_EVIDENCE, 0 detector flags.
Work is `evaluator_work` (G retired instructions).

| Config | Total | Child (solver) | Checker |
| --- | --- | --- | --- |
| Fresh-v2 | 1,649.4 | 33.6 | 1,615.3 |
| Fresh-v3 | 127.1 | 33.7 | 92.8 |
| Fresh-v3-allP (generic proofs) | 125.2 | 33.7 | 91.0 |
| Experienced-v3 | 119.1 | 27.5 | 91.1 |
| Placebo-v3 | 132.0 | 40.1 | 91.3 |

1. **Fresh-v3 vs Fresh-v2: 13.0× cheaper** (5/5 seeds, 12.6–13.2×). This is the generic shared-computation gain.
2. **Experienced-v3 vs Fresh-v3: −6.2%** (5/5 seeds, −4.1% … −7.7%); vs Fresh-v3-allP: −4.9%.
   * The verified proofs are generic: they give −1.4% (Fresh-v3-allP vs Fresh-v3). The learned axiom selection
     (sort / run_heads / running_max in all 20 folds) gives about the same.
   * The experience gain is the learned **macro proposal**: −12% on familiar_exact and −12% on compositional, but
     **+10% on held_out**, where macro search is pure overhead.
3. **Experienced-v3 vs Placebo-v3: −9.8%** (5/5 seeds).
4. **Experienced-v3 + source learning vs Fresh-v3: 3.14× worse** (5/5 seeds).
   * Source learning costs 279.9 G per split, against a target saving of 7.9 G per 280 tasks. At this rate it
     would take roughly 10⁴ target tasks per library to repay.

**Gate:** met (5/5 seeds, pooled −6.2% ≥ 3%), so the targeted Wave 32 v3 check was run (see the Wave 32 doc).

## Audit: what the ~280 G source-learning cost actually is (`artifacts/wave31_source_audit_*.json`)

* **Method:** an exact accounting replay of the v3 source learning, plus the same source tasks solved as plain
  Fresh-v3. No new arm outcomes.
* **Result:** the replay totals agree with the recorded totals within 0.3% (meter noise across processes).

| G instructions (630 source tasks per split) | val_v3 | dev |
| --- | --- | --- |
| (a) Fresh-v3 solving the source tasks (baseline Fresh would also pay) | **281.35** (child 52.55 + checker 226.45) | 269.54 |
| Source solves as run (Fresh + axiom rotation) | 280.38 | 268.52 |
| Library build (anti-unification, macro instantiation, axiom selection) | **0.33** | 0.33 |
| (b) Marginal learning overhead = (as run − baseline) + build | **−0.64** | −0.68 |

* **Saving per target task** (Experienced-v3 vs Fresh-v3 on val_v3): 7.94 G / 280 = 28.4 M instructions.
* **Break-even, Definition A** (the source tasks are pure overhead; nobody needed them solved): 279.9 G / 28.4 M ≈
  **9,900 target tasks**. This is the earlier "3.14× worse" accounting.
* **Break-even, Definition B** (marginal: the source tasks are work that would be solved anyway, and learning only
  adds extraction):
  * Counting only the build (0.33 G) and ignoring the rotation saving, break-even is ≈ **12 target tasks**.
  * Including the rotation saving, the marginal cost is negative, so break-even is **immediate**.
  * Comparison 4 under B is (119.13 + 0.33) / 127.07 = **0.940**, which is −6.0% net.
* **Reading.** Experience is cheap to extract. Nearly all of the "learning cost" is the price of the source
  *tasks*. Learning repays when those tasks are part of the workload, as in an online stream, which is what the
  Wave 32 stream results show. It does not repay when they are an extra curriculum solved only to learn from.

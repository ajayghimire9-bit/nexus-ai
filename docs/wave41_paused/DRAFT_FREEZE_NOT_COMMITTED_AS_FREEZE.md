## Freeze: Wave 41 confirmation protocol (committed before any Wave 41 confirmation seed or sealed Split.Text file is opened)

**Frozen code:**
* Checker v5 (pin `2cd3a4ca…`, commit `622a29a`, untouched; the only certificate source).
* Shared solver pieces: `w41_lemmas` (base static lemmas, given to every arm), `w41_search`, `w41_hier` (12 micro-specialists,
  workspace record, routing, compiled skills with composed summaries, the shadow vault, rent, the certificate law), `w41_guards`
  (variant V2), `w41_eval`, and `scripts/w41_child.py`.
* Drivers: `w41_track1.py`, `w41_track2.py`, `w41_track3.py`, `w41_common.py` and `w41_analyze.py`.

**Frozen settings:**
* Budgets: 4M executions per search for Tracks 1 and 3, 2M for Track 2; witness shortcut at most 48k executions; k ≤ 2.
* Matched arms: every arm uses the same v5 language, declared scope, depth, lemmas, witness shortcut and per-task budget.

| Track | Data (one use) | Verdict rule |
| --- | --- | --- |
| **T1** Internal folds | `wave41/confirm_lodo` 7871–7875 (4 folds × 2 source + 2 target instances per mechanism) | **(a) Completeness: PASS** if every arm solves exactly Flat's tasks with 0 wrong. **(b) Hierarchy:** for each of Fixed_Hierarchy, Learned_Hierarchy and Learned_Hierarchy_PS_Growth, **PROVED** if total work (fit and online learning charged) is below Flat_NEXUS_v5's, pooled and in ≥ 4/5 seeds, with solves ≥ Flat's and 0 wrong. The two learned arms must *also* beat Size_Matched_Placebo_Hierarchy the same way. **PARTIAL** if the arm beats Flat pooled only. **NEGATIVE** otherwise. A ratio above 0.98 is *negligible* whatever the verdict. **(c)** The same ratios are reported on held-out mechanisms and on novel compositions (descriptive). |
| **T2** 500-task stream | `wave41/confirm_stream` 7876 (one stream; no seed replication, disclosed) | **(a) Accuracy:** solves ≥ Flat's, with 0 wrong. **(b) The cost curve bends** for PS_Growth if its ratio of quintile-5 to quintile-1 cost per solved task is below Flat's *and* its total work is below both Flat's and Placebo's. Otherwise NOT BENT. Descriptive (one stream). |
| **T3** External, PROSE Split.Text | 92 never-used tasks, sealed by hash; claim `wave41/confirm_ext` 7881 | **(a) Lemmas:** Flat_NEXUS_v5 vs Flat_noLemma, total and no-candidate search work (descriptive). **(b) Hierarchy:** **PROVED** if the arm's total work is below Flat's and Placebo's with HOV ≥ Flat's at k = 0; otherwise NEGATIVE (pooled tasks; no seeds). **(c) Certification wall:** **BROKEN** only if any arm cuts certification work on its kernel calls by ≥ 10% relative to Flat with identical global verdicts. Predicted NOT BROKEN, because v5 is read-only and its sweep cannot shrink. **(d) Epistemic safety** (Flat arm, primary): the guards **SUCCEED** if guarded silent failures at k = 0 are ≤ 50% of the unguarded count *and* guarded correct unique answers are ≥ 90% of unguarded. Distinguishing queries **HELP** if certified-but-held-out-fail at k = 1 is below its k = 0 value with HOV not lower. |

**Global soundness audit (all tracks):** 0 rows may carry the tier GLOBAL_SCOPE_UNIQUE unless Checker v5 returned
SCOPE_UNIQUE with clean D1/D2 on the original declared scope.

**Accounting:**
* *Mandatory work:* fit and compile instructions plus online learning (updates and shadow-vault trials).
* *Extra curriculum:* source solving plus fit, with break-even computed against Flat.

**Missing-data rule:** runs resume from per-fold, per-arm or per-50-task checkpoints at the 890 s call cap. Learner state is
restored from the checkpoint, nothing is dropped, and every interruption is logged.

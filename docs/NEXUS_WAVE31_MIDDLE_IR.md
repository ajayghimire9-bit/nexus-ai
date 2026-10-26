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

# Wave 30 (increment 1, not locked) — read-only Checker Kernel + A0 / A1 / A1b diagnostics on dev and admission_val

Branch `codex/wave30-kernel-and-alien-dr` (from Wave 29 `c78d476`).

## Built

**Checker Kernel** (`src/nexus/checker_kernel.py`).
* Standard library only; read-only under AGENTS.md RULE 2; sha256 pinned; about 300 lines.
* It has its own interpreter for the mechanism language: F / S / Sort / comp, plus the A1 DSL.
* It re-verifies every pruning lemma against its own postcondition table, then exhaustively enumerates the
  declared finite scope: all sizes ≤ d, which is stricter than a minimal-size certificate.
* Labels: `exhaustive_UNIQUE`, `proposal_relative_UNIQUE`, `AMBIGUOUS(k)`, `ABSTAIN`.
* Tests:
  * the kernel and prover interpreters agree on every mechanism;
  * tampered answers, unknown ops and mis-cited lemmas are rejected;
  * lemmas never change the label, only the number of chains checked.
* Checking finite-scope uniqueness costs about as much as the enumeration. What the kernel provides is a small,
  independent trusted base, not cheaper checking.

**Evidence Object** (`wave30_arms.prove`). Contents:
* candidate chain specs;
* the declared scope, as tool specs plus depth;
* pruning lemmas (tool, postcondition, violating public output);
* the trace;
* public pairs, including the charged probe pairs.

**Prover.** An exact unpruned Searcher to k_min, plus the k_min + 1 shell, with up to 3 rich verification probes
while ambiguous. It uses a harness-local 6M budget and records worlds with 3 fields.

**Arms.**
* **A0:** base plus the 10-schema comp menu.
* **A1:** A0 plus a fixed richer DSL: projection, arithmetic maps, accumulators (prefix sum, running max,
  difference), objects (run heads, group counts), and bounded loops (repeat 2–3 × diff).
* **A1b:** A1 tools behind a no-pretraining wake-sleep prior over operator families.
  * The prior starts at Dirichlet(1) and is updated only from NEXUS's own kernel-certified candidates in the
    same stream.
  * It proposes families covering 80% of the mass. If nothing fits there, it escalates to the full scope, and
    both searches are charged.

**Splits (registry).**
* `wave30/dev`: 751–755.
* `wave30/admission_val`: 7001–7005, reusable for admission decisions only, never for final claims.
* `final_sealed` (alien worlds): not yet generated.

## Initial diagnostics

Each split has 5 seeds × 16 tasks, half A0-expressible teachers and half A1-only (by construction).

| Split | Arm | Solved | False certificates | Labels | Work | A0-family solved | A1-family solved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev | A0 | 43/80 | 0 | 43 exhaustive_UNIQUE, 1 AMBIGUOUS, 36 ABSTAIN (no fit) | 19.4M | 40/40 | 3/40 |
| dev | A1 | 78/80 | 0 | 78 exhaustive_UNIQUE, 2 AMBIGUOUS | 25.4M | 40/40 | 38/40 |
| dev | A1b | 79/80 | 0 | 62 proposal_relative, 17 exhaustive, 1 AMBIGUOUS | 23.4M (−8% vs A1) | 40/40 | 39/40 |
| admission_val | A0 | 38/80 | 0 | 38 exhaustive, 4 AMBIGUOUS, 38 ABSTAIN | 24.4M | 37/40 | 1/40 |
| admission_val | A1 | 74/80 | 0 | 74 exhaustive, 6 AMBIGUOUS | 32.7M | 36/40 | 38/40 |
| admission_val | A1b | 73/80 | 0 | 56 proposal_relative, 17 exhaustive, 7 AMBIGUOUS | 32.1M (−2%) | 37/40 | 36/40 |

**Wall time.** dev 178 s; admission_val 220 s.

**Prover vs kernel.**
* The prover was UNIQUE but the kernel was not on 1 dev and 1 admission_val task (A1, A1b).
* The kernel's exhaustive all-sizes scope found a disagreeing program. The prover's k_min + 1 shell is weaker
  than the kernel's full-scope semantics.

## Reading and caveats

* **No false certificates under any arm.** The kernel never issued a wrong UNIQUE, and A0 abstains instead of
  guessing on out-of-grammar tasks.
* **A1's coverage advantage is built into the task distribution.** Half the teachers are A1-only by
  construction. It shows that the richer DSL is usable at about 1.3× the cost of A0. It does not show that A1
  helps on a natural distribution.
* **A1b's learned proposal saves little** (−8% / −2%).
  * Records-world A0-family tasks dominate the cost.
  * Escalation to the full scope happens 17–19 times per split and is charged twice.
  * Proposal-relative labels are weaker claims than exhaustive ones.
* **Not yet built:**
  * A2 / A3, which need a coder model (paid services are excluded, and no local coder is configured);
  * A4;
  * the bit-gap meter;
  * lineage ablation;
  * admission net of costs;
  * the alien `final_sealed` worlds;
  * the `possibly_contaminated` ARC report.

**Budget used:** about 400 s for diagnostics. About 6,100 s remain.

---

# Increment 2 (NOT LOCKED): reporting semantics, matched-strength comparison, history controls, generator, A2 smoke

Verified at the start: branch `codex/wave30-kernel-and-alien-dr`, HEAD `e234898`, clean tracked tree, Wave 29
record `c78d476` untouched, kernel sha256 `5082402f…121e`. **The kernel file is unchanged.** The increment 1
numbers above remain as historical diagnostics.

## 1. Reporting and comparison semantics (around the frozen kernel)

Code: `src/nexus/wave30_harness.py`.

**Categories reported separately:**
1. ground-truth-correct answers;
2. `exhaustive_certified`: unique within the declared tool specs (grammar), depth bound 2, representation set and
   the kernel's execution semantics;
3. `AGREEMENT_AMONG_PROPOSALS`: the kernel's `proposal_relative_UNIQUE`. **Never counted as exhaustive**;
4. wrong answers, split into `teacher_outside_scope` (the certificate is valid relative to its scope) and
   `teacher_inside_scope` (would indicate a defect);
5. invalid certificate claims (the prover said UNIQUE, the kernel disagreed);
6. abstentions (with reasons) and ambiguity.

**Ambiguity.** It is reported "exactly k" for exhaustive scopes, where the kernel enumerates the entire declared
scope, and "at least k" for proposal scopes. Concrete witnesses are two observation-consistent programs with
distinct query answers, each re-checked by the kernel.

**Kernel integrity.** It is verified by the runner, outside AGENTS.md. `verify_kernel_pin()` compares the file
on disk and the file in git object `e234898` with the pin in that same git object, and checks the import path.
Every increment 2 run calls it and records the hash.

**Interface audit.** Solvers receive only `TaskView(public, query, oracle)`. Generator metadata, teacher
identity, hidden answers and family labels exist only in `evaluate()`. Tests enforce this.

## 2. Matched-strength comparison

* **A1b-full** uses exactly A1's declared scope and the exhaustive label. The prior can only reorder enumeration,
  which determines which ambiguity witnesses, and so which probes, appear first. Both arms stop a level early on
  a disagreement and probe.
* **A1b-proposal** (truncated scope, with escalation) is reported separately as a performance and coverage
  trade-off.

Costs are on one meter. Columns: source learning (SL), proposal generation (PG), scope construction (SC), prover,
probes plus oracle, lemma construction (LC), failed proposals (FP), checker. In the source column, "billed" means
the history cost is charged separately (row 7).

### dev (751–755, 80 tasks, online learning)

| Arm | Correct | Exhaustive | Agreement among proposals | Wrong (outside / inside scope) | Invalid | Ambiguous | Abstain | Total work |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | 43 | 43 | 0 | 0 / 0 | 0 | 1 | 36 (no program in declared space) | 19.05M |
| A1 | 78 | 78 | 0 | 0 / 0 | 1 | 2 | 0 | 24.63M |
| A1b-full | 78 | 78 | 0 | 0 / 0 | 1 | 2 | 0 | 23.91M (**−2.9%**) |
| A1b-proposal | 77 | 15 | 64 | **2** / 0 | 0 | 1 | 0 | 15.61M (−37%, weaker labels) |

### admission_val (7001–7005, 80 tasks)

These seeds were already viewed in increment 1 and discussed, so this is **not untouched data**. Priors are frozen
before the stream, with no target-time adaptation for any control.

| # | Arm, history | Correct | Exhaustive | Agreement among proposals | Wrong (outside scope) | Invalid | Ambiguous | Total work | Prover | Checker | FP | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A0 | 38 | 38 | 0 | 0 | 0 | 4 | 23.72M | 19.17M | 4.51M | — | — |
| 2 | A1 | 73 | 73 | 0 | 0 | 1 | 7 | 30.90M | 22.55M | 8.29M | — | — |
| 3 | A1b-full, **useful** | 72 | 72 | 0 | 0 | 1 | 8 | **32.32M** | 23.89M | 8.38M | — | billed (row 7) |
| 4 | A1b-full, none | 74 | 74 | 0 | 0 | 1 | 6 | 27.74M | 19.96M | 7.73M | — | 0 |
| 5 | A1b-full, shuffled (size-matched) | 73 | 73 | 0 | 0 | 1 | 7 | 30.87M | 22.78M | 8.03M | — | billed |
| 6a | A1b-proposal, **useful** | 75 | 12 | 63 | 0 | 1 | 5 | 26.58M | 17.90M | 6.31M | 2.31M | billed |
| 6b | A1b-proposal, none | 73 | 11 | 62 | 0 | 1 | 7 | 33.55M | 21.86M | 8.08M | 3.55M | 0 |
| 6c | A1b-proposal, shuffled | 75 | 19 | 57 | 1 | 1 | 4 | **15.28M** | 10.30M | 3.54M | 1.40M | billed |
| 7 | (source history = dev A1b-full online) | | | | | | | 23.91M over 80 source tasks | | | | |

Proposal generation, scope construction and lemma construction are each ≤ 0.03M in every cell. Oracle and probe
work is ≤ 0.01M (probes are rarely needed at depth 2). Wall-clock time and kernel seconds per cell are in the
artifacts.

## 3. Does A1b learn from history? **No, not at matched strength.**

* **Full scope (exhaustive labels).** Useful history is the most expensive A1b condition: 32.3M, versus 27.7M with
  no history and 30.9M with shuffled history. Coverage is 72 / 74 / 73. Reordering cannot shorten an exhaustive
  enumeration; it only changes which probes are triggered.
* **Proposal mode (weaker labels).** Shuffled history is the cheapest (15.3M). So the proposal-mode savings come
  from smaller proposal sets, not from relevant experience.
* **Amortization.** Charging the 23.9M source cost over the 80 target tasks makes "useful" worse in every mode.
* **What this shows.** A1 > A0 shows that a richer supplied DSL helps on this distribution (half A1-only by
  construction). It does **not** show autonomous representation discovery. **No experience-dependent advantage
  is established.**

## 4. Counterfactual-world generator and split discipline

**Generator.** `src/nexus/wave30_alien.py`, sha256 `d81a5b6e4cd779be…`. Three families with executable reference
mechanisms:
* connectivity under knight / camel / zebra / king moves;
* wrapped affine coordinate maps;
* colour algebra over randomly relabelled groups of order 4 (Z4, Z2 × Z2).

The full parameter space of each family is enumerated per instance, so unavoidable ambiguity is recorded
explicitly ("unavoidable_within_family(k)"). On 30 dev-preview instances, all were unambiguous with 3
demonstrations.

**Contamination wording.** "Fresh instances generated after freezing the generator and model reduce
exact-instance contamination. They do not establish that the underlying concepts were absent from pretraining."

**Splits.** `final_sealed` is registered as one-use seeds 9301–9310 and is **not drawn**. It will be drawn only by
a locked runner after the generator is frozen at lock.

**Grid semantics.** The kernel's language is list-based and has no grid semantics. Grid tasks will therefore get
`ABSTAIN` (unsupported) from the unchanged kernel until a separately approved kernel version adds grid
semantics.

**ARC.** Public ARC results stay in a separate contamination-risk report. None has been produced yet.

## 5. Local-model route (A2 / A3 / A4)

**Found and reused:** `wave24_qwen_engine` with `qwen2.5-1.5b-instruct-q4_k_m.gguf` and
`/opt/homebrew/bin/llama-server`, on the **CPU** backend (the Metal grant was not set). No paid API was used.

**A2 smoke** (dev seed 751, 16 tasks). Code: `src/nexus/wave30_coder.py`, `scripts/wave30_a2_smoke.py`.
* Setup: iterative feedback, up to 4 generations, temperature 0 then 0.7, max 160 tokens, one final submission.
* **0/16 correct, 16 ABSTAIN.** 31,260 prompt tokens and 3,283 generated tokens; 424 s of model wall time.
* A 1.5B quantised model cannot write these DSL programs from 4 demonstrations. This is a weak coder control,
  not evidence about coders in general.

**Status:**
* A2 is runnable.
* A3 (coder φ, ψ plus fixed search) and A4 (encodings plus LODO plus skeletons) are not yet implemented.
* A stronger local model would be needed for a meaningful coder control. That is a resource decision for the
  owner (`BLOCKED_MODEL_QUALITY`, not `BLOCKED_MODEL`).

## 6. A4 and lineage interfaces

Code: `src/nexus/wave30_skeleton.py`; tests included. Not evaluated.
* Typed skeletons via AST anti-unification.
* An archive with parent links.
* Lineage ablation that removes ancestors while re-attaching orphans, against a size-matched control removal.
* Round-trip and LODO are empirical evidence only. Unsupported semantics give ABSTAIN from the unchanged kernel.
* The bit-gap meter is deferred. If added later, it will be labelled a context-sensitivity diagnostic.

## 7. Summary

* **A1b's advantage does not survive the matched-scope comparison**: −2.9% on dev, with history controls showing
  no experience effect. Its proposal-mode savings are reproduced, and exceeded, by shuffled history.
* **Certificates:**
  * 0 wrong answers under exhaustive labels in every cell;
  * 3 wrong answers, all agreement-among-proposals with the teacher outside the proposal;
  * 1 invalid prover claim per A1-scope cell, caught by the kernel.
* **Model-dependent blockers:** A3 and A4 are unbuilt, and A2 is limited by the quality of the 1.5B model.
* `final_sealed` is preserved. Wave 31 and Wave 32 remain provisional.

**Budget:** increment 2 used about 1,500 s. About 5,700 s remain.

# NEXUS Data Platform — Primitive-to-OOP Synthesis and Learner Evolution (NOT LOCKED)

Branch `codex/nexus-data-engineering`, built on R2 (`093cda0`). One project: everything below powers the NEXUS
data-engineering platform (the de5 streaming / CDC / lakehouse projects) and is scored on the Unified 7-Measure Scorecard.
`main`, `final_sealed`, checker kernels v1–v5 (`622a29a`) and the 912 protected Stage 1–6 / R1 files are untouched; R2 files
are reused unchanged, loaded as separate patched module copies where behaviour changes.

Budget: GRANT-NEXUS-DE-OOP-36000S (`artifacts/de_oop_grant.json`, recorded once). Owner reading 2026-10-28 ("use
34,139 s"): the grant's 39,162 s total covers R2, so 34,139 s were available at the start of this track. Unit: wall seconds
of ledger rows (`scripts/oop_budget.py` debits every `w41`, `de-`, `de2-`, `r1-`, `r2-` and `oop-` row). CPU figures in
results are measurements, not debits. Per call ≤ 895 s.

The track has three phases (owner plan): **Phase 1** primitive synthesis inside the pipeline builder and repair engine;
**Phase 2** verified code / representation library, transfer to unfamiliar domains, meta-learned controller; **Phase 3**
structural evolution of the learner. Each phase runs dev → freeze → one-use validation → one-shot sealed test.

---

## 0. Phase 1 pre-registration

### 0.1 Question

Can NEXUS replace author-written pipeline switches with code it **writes itself from primitives** — functions, if/else,
bounded loops, `def`s and `class`es — and still deliver and operate correct pipelines end to end, including repairing its
own code when a withheld fault class appears in production? Compared with the R2 pipeline whose handlers for those classes
were written by the author.

### 0.2 What is synthesised, and what is not (disclosure)

The R2 consumer has 18 author-written switches. Phase 1 removes **8** and replaces them with 4 holes whose code NEXUS
synthesises and inlines into the delivered `pipeline.py` (`src/nexus/oop_template.py`):

| hole | replaces | NEXUS writes |
| --- | --- | --- |
| `syn_decode` | schema_handling, discount_unit | `def fn_<id>(a, fields, types)` → canonical orders row |
| `syn_net` | fx | `def fn_<id>(p, fx)` → net amount |
| `syn_status` | malformed, fx_unknown | `def fn_<id>(topic, rec, row, fx, whs)` → class label (if / elif / else) |
| `syn_silver` | apply_order, backfill_merge, deletes | `class StreamOrganelle_<id>` (`__init__` / `ingest` / `retract` / `flush`, dict state, bounded `for` loop), synthesised only when a **Markov state violation** is found (two records with identical content need different outcomes); otherwise a pure filter |

The other **10 switches stay author-written** in Phase 1: commit_protocol, dedup, ts_parse, ts_format, gold_maintenance,
lateness, partition_discovery, snapshots, txn_isolation, gap_handling (infrastructure and time semantics). The consumer
skeleton (log reading, sqlite I/O, offsets, snapshots, rollback) is also author-written. **This is not "zero pre-written
code"**: the owner's zero-switch mandate is met for the 8 record-semantics switches only.

The synthesiser (`src/nexus/oop_synthesizer.py`) contains no data-engineering concept. Its primitives: the hole's argument
variables; constants 0, 1, 2, 100 plus string / small values that occur in the examples; `float int str not
isinstance-number isinstance-str is-None`; `+ - * / == < <= in and or .get round`; if/else; bounded for-loops (folds, class
methods); `def` by anti-unification; `class` on a Markov violation. Search: bottom-up enumeration with observational-
equivalence collapse, deductive decomposition of numeric targets (interval inverse semantics for `+ - * /`), decision-list
and conditional unification with an Occam-first predicate learner, CEGIS over all examples. The grammar was written by the
author after X3 / X4 (below) were known; the constant 100 and the `in` operator are generic but useful for them.

**Supervision.** The synthesiser sees only input/output examples produced by calling the operator-side spec monitor
(`oop_reconcile`: decode / classify / derive_silver, with provenance) as a black box on records NEXUS can see: the visible
log (ticks 1–8) at build, the operator archive at ops time (`src/nexus/oop_examples.py`). The monitor is an executable
specification, so NEXUS synthesises an *implementation that agrees with the spec on observed records*; it does not discover
the spec's meaning. Never the evaluator, truth, sealed data or the monitor's source.

**Repair.** The R2 operator is unchanged (incident search, shadow tests, B1 localisation with provenance contrast, typed
evidence, ddmin trace shrinking, CEGIS over shrunk counterexamples, C0 order, B0 secondary; `src/nexus/oop_ops.py`). One
addition: before candidates are formed, every synthesised hole among the localised holes whose current program disagrees
with the monitor's examples on the archive is **resynthesised from primitives**; the new program is a new option of that
hole and goes through the unchanged cheap-check → full shadow verification → redeploy + rollback path. Resynthesis CPU is
inside localisation CPU (charged).

### 0.3 Worlds, classes, splits (namespace de5, `src/nexus/oop_seeds.py`, `src/nexus/oop_env.py`)

Every world has the W1 / W2 Stage 4–6 classes and two seen ops incidents. Every de5 spec declares the rules of X3, X4, D1, D2.

| split | seeds | classes from tick 9 | use |
| --- | --- | --- | --- |
| src | 981–986 | X1/X2 + D1/D2 | reserved for Phase 2 library learning |
| dev | 991–998 | X1 (even) / X2 (odd) + D1 ((seed//2) even) / D2 (odd) | development, reusable |
| val | 7981–7984 | as dev | one use, frozen code |
| val_b | 7985–7988 | as dev | one use, only after ONE disclosed revision |
| test | 7991–7998 | X3 unknown currency (even) / X4 registry discount fraction (odd) only | one-shot sealed |

New dev-only classes: **D1** registry amount unit (schema v4 declares `amount_unit = minor`; amounts ×100) and **D2**
unknown warehouse (orders naming a warehouse outside `warehouses` are quarantined `unknown_warehouse`). X3 / X4 are the R2
test classes: withheld from every NEXUS development run here, but **known to the developer since R2** and structurally a
near-transfer of D2 / D1 (same rule shape, different field and constant). They are generated only by the seal script.

### 0.4 Arms (identical worlds, evaluator `oop_evaluator`, incidents, caps)

* **NEXUS_Synth** — new: synthesised holes + R1 suite build search over the 10 switches; ops B1 / C0 with resynthesis.
* **NEXUS_Template** — the frozen R2 NEXUS_Fresh (author-written switches including X3 / X4 handlers; B1 / C0).
* **Fixed_Policy** — the frozen R2 Fixed_Policy (src option counts from `artifacts/r2_library.json`, learned on de4 src).
* **Conventional_Checked** — the frozen R2 baseline.

The R2 arms run unchanged code; their monitor (r2_reconcile) does not know D1 / D2, so on dev / val they are expected to
fail D-class worlds — dev / val results are reported for NEXUS_Synth only as gate evidence. The test (X3 / X4 only) is the
like-for-like comparison. No component run (no supplied "correct" synthesised pipeline exists).

### 0.5 Measures and scoring

* **Natural end-to-end** (primary): the arm's own submitted pipeline through ticks 1–14 with its incidents and classes,
  correct per the evaluator and no open escalation. Not submitted = failure.
* **Forced-failure recovery**, separate denominator: X1 / X2 switches forced naive (every arm); X3 / X4 forced naive for the
  template arms (R2 options). For NEXUS_Synth the X3 / X4 / D1 / D2 code was synthesised from a window that never contains
  the class, so its natural deployment *is* the forced condition — scored once, shown in both tables, flagged.
* **Silent errors**: the operator claims healthy while data are wrong.
* **Secondary**: NEXUS_Synth natural deployment re-run with the B0 localiser.
* Synthesis record: programs, sizes, CPU, examples, Markov witnesses, resyntheses, and the verbatim deployed code.
* 7-measure scorecard rows for every arm.

### 0.6 Gates (predeclared; a negative result is valid)

* **Validation** (val, frozen code): NEXUS_Synth natural e2e ≥ 3/4 AND 0 silent errors AND 0 harness crashes. At most ONE
  disclosed revision, then val_b once under the same gate; if val_b fails, the test is not opened.
* **Test natural gate**: NEXUS_Synth natural e2e ≥ 7/8 AND 0 silent errors. (For Synth this is also its forced gate.)
* **Comparison** (reported, not gated): NEXUS_Synth vs NEXUS_Template natural e2e and silent errors on the 8 test projects;
  "synthesis matches author-written handlers" is claimed only if Synth's gate passes AND Synth e2e ≥ Template e2e − 1.
* **Crash rule**: a harness crash stops the run; it is recorded, never resumed automatically, and the crashed project is
  scored as a harness failure for every arm not yet run.

### 0.7 Caps (Phase 1)

Phase 1 total ≤ 12,000 s of ledger time (dev ≤ 6,500 s, val + val_b ≤ 2,500 s, test ≤ 3,000 s), leaving ≥ 22,000 s for
Phases 2–3. Per build: synthesis ≤ 400 s CPU, the R1 caps otherwise; per resynthesis ≤ 160 s CPU; R2 shadow caps unchanged.

### 0.8 Development log

(filled before the freeze)

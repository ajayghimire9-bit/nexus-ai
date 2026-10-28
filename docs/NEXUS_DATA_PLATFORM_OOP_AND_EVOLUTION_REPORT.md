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

### 0.8 Development log (dev seeds 991–998 only; everything below happened before the freeze)

Changes made during development, in order, each prompted by a dev failure:

1. **Silver provenance.** The first example extractor read the silver row's schema version as if it were the winning
   record's source version; the monitor now also returns which record each silver row comes from (`silver_provenance`).
2. **Label-stratified sampling.** On 991 the 60-example sample held none of the 8 unknown-warehouse examples, so
   observational equivalence merged `warehouse in whs` with a spurious literal. Samples now cover every output label;
   sample 150, ≤ 5 CEGIS rounds, ≤ 40 counterexamples added per round.
3. **Predicate learner.** Rewritten vectorised (numpy) with Occam-first choice (cheapest literal that finishes the job;
   exhaustive cheapest pair before greedy), a penalty for comparing with literal example values, guarded two-literal
   or/and literals, and **decision-list unification** for categorical outputs (rarest label peeled first).
4. **Monitor robustness.** The R2 monitor crashed (`float(None)`) on a pipeline row with a missing amount (992); in the
   loaded copy the comparison now reports a content mismatch, and any monitor exception on pipeline output is a failed
   reconciliation (`monitor_exception`), never a harness crash.
5. **Folds.** Probe states with a constant accumulator let OE merge `acc + x` with `x`; probes now vary the accumulator.
6. **Example memory.** Resynthesis at tick 9 on 994 used only the ops archive, which had no malformed manifest yet, and the
   new classifier lost the malformed rule. Resynthesis now uses NEXUS's build-window examples plus the archive.
7. **Transaction order.** My template patch classified a record before the transaction check, so an unknown-warehouse
   order inside an aborted transaction would be quarantined, not aborted (R2's unknown-currency patch has the same order;
   its worlds never combined the two). Transaction records are now classified when their transaction commits.
8. **Oracle queries.** On 995 the build check's spec probe (a malformed weight must be quarantined) failed because the
   visible window had no malformed record. NEXUS now makes membership queries to the black-box monitor: for ≤ 3 observed
   first deliveries per topic, one scalar field at a time is set to `"N/A"` and the monitor's class is the label (no field
   or rule is named in the generator; test `test_oracle_queries_are_generic_and_labelled_by_the_monitor`).
   **Consequence (disclosed):** the declared quarantine rules — malformed weight, unknown currency (X3), unknown warehouse
   (D2) — are now learned at build time from the spec monitor, before any such data appears. Ops-time resynthesis is then
   exercised by the registry-unit classes (D1 on dev, X4 on test), which the queries do not reach (they never perturb
   registry metadata).

Final dev pass (`artifacts/oop_dev_results/dev_r1.json`, NEXUS_Synth only, frozen candidate code):

| project | classes | natural e2e | silent | forced X | secondary B0 | resynthesis |
| --- | --- | --- | --- | --- | --- | --- |
| 991 | X2 D2 | ✓ | 0 | ✓ | ✓ | — |
| 992 | X1 D1 | ✓ | 0 | ✓ | ✓ | syn_decode @ tick 9 |
| 993 | X2 D1 | ✓ | 0 | ✓ | ✓ | syn_decode @ tick 9 |
| 994 | X1 D2 | ✓ | 0 | ✓ | ✓ | — |
| 995 | X2 D2 | ✓ | 0 | ✓ | ✓ | — |
| 996 | X1 D1 | ✓ | 0 | ✓ | ✓ | syn_decode @ tick 9 |
| 997 | X2 D1 | ✓ | 0 | ✓ | ✓ | syn_decode @ tick 9 |
| 998 | X1 D2 | ✓ | 0 | ✓ | ✓ | — |

8/8 natural, 8/8 forced, 8/8 B0 secondary, 0 silent, 0 crashes. The build evaluation (checkpoint 12 includes the
classes' ticks 9–12) is correct on 3/8, as expected for a build that has not yet met D1 / X1 / X2 data. Earlier
4-arm dev runs (993, 994, before changes 6–8) showed the R2 arms failing D-class worlds as expected (NEXUS_Template silent
on 993: no D1 handler). Dev ledger time: 2,524 s. Protected files 912/912 unchanged.

---

## 1. Phase 1 validation (one use, de5/val 7981–7984, frozen `67f9687`) — gate FAILED

| project | classes | natural e2e | silent | forced X | secondary B0 | resynthesis |
| --- | --- | --- | --- | --- | --- | --- |
| 7981 | X2 D1 | ✓ | 0 | ✓ | ✗ | syn_decode @ 9 |
| 7982 | X1 D2 | ✓ | 0 | ✓ | ✓ | — |
| 7983 | X2 D2 | ✓ | 0 | ✓ | ✓ | — |
| 7984 | X1 D1 | ✗ | **1** | ✗ | ✗ | syn_decode @ 9 (verified, redeployed) |

Gate "natural e2e ≥ 3/4 AND 0 silent AND 0 crashes": 3/4, **1 silent**, 0 crashes → **FAIL**. Replay-view violations 0.
On 7984 the synthesised code was repaired correctly at tick 9; the silent error comes from the incident `unit_shift` at
tick 13 (a supplier's feed switches to pounds): the inherited Stage 5 drift handling dismissed an earlier S3 alarm as a
false alarm and never localised the late shift, so wrong weights reached gold while the operator claimed healthy. This is
an operator weakness inherited unchanged from Stages 5 / R1 / R2, not a synthesis failure — but the gate is about the
deployed system, so it fails. Per protocol one disclosed revision is allowed, then val_b once.

### 1.1 Revision 1 (the one permitted; disclosed) and re-freeze

Diagnosed on **dev** worlds, not val: `scripts/oop_dev_unitshift.py` forces traffic_spike@11 + unit_shift@13 on dev 991 /
992 / 996. Before the revision both operators produced silent errors (NEXUS_Synth 2/3, unchanged R2 template operator
2/3; `artifacts/oop_dev_results/unitshift_before.json`). Instrumented cause: a ratio alarm raised by natural variation
before the shift stays pending; when the producer metadata changes, `drift_scan` raises no second alarm for that supplier;
the ratio test on a handful of records cannot localise the shift; pending alarms do not fail the healthy claim. Revision:
an unlocalised alarm whose supplier shows a producer-metadata change takes the existing metadata path (localise, else ask
the stakeholder for the unit — a counted clarification — then localise by metadata) (`oop_ops.NexusOpsSynth`). NEXUS_Synth
only; the R2 arms are unchanged. After: NEXUS_Synth 991 / 996 correct, 0 silent; R2 operator still fails
(`unitshift_rev1.json`). Dev regression with the revision: 8/8 natural, 8/8 forced, 8/8 B0 secondary, 0 silent
(`dev_rev1.json`). The val_b gate is the val gate, unchanged.

### 1.2 val_b (one use, de5/val_b 7985–7988, frozen `3162c8e`) — gate FAILED; the Phase 1 sealed test is NOT opened

| project | classes | natural e2e | silent | forced X | secondary B0 | resynthesis |
| --- | --- | --- | --- | --- | --- | --- |
| 7985 | X2 D1 | ✓ | 0 | ✓ | ✓ | syn_decode @ 9 |
| 7986 | X1 D2 | ✓ | 0 | ✓ | ✓ | — |
| 7987 | X2 D2 | ✓ | 0 | ✓ | ✓ | — |
| 7988 | X1 D1 | ✗ | **1** | ✗ (silent) | ✗ | syn_decode @ 9 (verified, redeployed) |

3/4 natural, **1 silent** → FAIL. By the predeclared rule the test is not opened: the de5/test seeds 7991–7998 were never
claimed or generated (no vault blobs, no manifest), and no Phase 1 confirmation claim is made.

7988, as far as the stored evidence goes: every monitor reconciled after every repair (decode resynthesised at tick 9;
clock_skew@10 repaired with future_guard + rollback; poison_message@11 dead-lettered; three earlier repairs moved the
lateness switch processing_time → none → watermark), yet the evaluator finds wrong data — a **monitor-blind** error in
the clock-skew / lateness family (cf. R1 7953 / R2 §0.9). The ops evaluation stores no per-table diff, so the exact table
is not identified; no further revision is permitted and none was made.

---

## 2. Phase 1 outcome

**Verdict: NEGATIVE (gate failed twice; sealed test not opened).** Both silent errors on validation data came from the
inherited operator / monitor layer (a missed late unit shift; a monitor-blind clock-skew / lateness error). In all 8
validation projects the synthesised code itself was correct wherever it was exercised: in all 4 D1 projects NEXUS
resynthesised its decode function at tick 9, verified it in a shadow copy and redeployed it; in all 4 D2 projects the
build-time classifier quarantined the unknown warehouses. That is an observation about the components, not a passed gate.

What Phase 1 does establish (dev + validation evidence, 16 de5 projects):

* NEXUS can write, from primitives and black-box spec examples, the record functions and the stateful class that replace
  8 author-written switches, inside the delivered pipeline, in ~43 s CPU per build (synthesis), and repair its own code
  in production by resynthesis (~37 s CPU per decode resynthesis), through the unchanged R2 verification path.
* The class is synthesised only after a Markov state violation is found (all 16 builds found one).
* Generalisation is limited by Occam: the decoder uses literal physical field names wherever no rename was observed
  (e.g. `a.get('ord_id')`), so a later rename would need a repair. No anti-unified helper `def` was admitted in any
  project: none would have shortened the code (the size rule rejected them).
* With oracle queries, the declared quarantine rules (incl. the X3 shape) are learned at build time from the spec monitor;
  the registry-unit classes are what exercise ops-time resynthesis.

What it does not establish: anything about the sealed X3 / X4 test (not run); any comparison with NEXUS_Template on test;
learning, transfer or evolution (Phases 2–3, not started).

### 2.1 Verbatim code NEXUS wrote and deployed (val_b 7985, after its tick-9 repair)

```python
def fn_0483b9c4(a, fields, types):
    return {
        'order_id': a.get('ord_id'),
        'warehouse_id': a.get('wh_id'),
        'status': a.get('status'),
        'amount': ((a.get('amount_total') / 100) if ('amount_unit' in types) else a.get(fields.get('amount'))),
        'currency': a.get('ccy'),
        'discount': a.get('disc'),
        'promised_ts': a.get('promised_ts'),
        'deleted': a.get('deleted')
    }


fn_decode = fn_0483b9c4


def fn_9977eb3b(p, fx):
    return round((p.get('amount') * (fx.get(p.get('currency')) * (1 - (p.get('discount') / 100)))), 2)


fn_net = fn_9977eb3b


def fn_147cc3aa(topic, rec, row, fx, whs):
    if isinstance(rec.get('weight'), str):
        return 'q:malformed_weight'
    elif ((not (row is None)) and (not (row.get('currency') in fx))):
        return 'q:unknown_currency'
    elif ((not (row is None)) and (not (row.get('warehouse_id') in whs))):
        return 'q:unknown_warehouse'
    return 'accepted'


fn_status = fn_147cc3aa


class StreamOrganelle_164d441c:
    """Markov state violation: identical record content, different required outcome ([true, false]); state = dict keyed by 'key', order 'sv' >, tombstone"""

    def __init__(self):
        self.state = {}

    def ingest(self, r):
        k = r.get('key')
        cur = self.state.get(k)
        if cur is None or r.get('sv') > cur.get('sv'):
            self.state[k] = r

    def retract(self, k):
        self.state.pop(k, None)

    def flush(self):
        out = []
        n = 0
        for k in self.state:
            n += 1
            if n > 1000000:
                break
            r = self.state[k]
            if not (not ((not (r.get('payload') is None)) and (r.get('soft') == 0))):
                out.append(r)
        return out


SilverOrganelle = StreamOrganelle_164d441c
```

The `amount` branch was written at tick 9 in production, after the reconciliation failure on the new registry version.

### 2.2 7-measure scorecard (validation evidence only; NEXUS_Synth; no sealed scorecard exists for Phase 1)

| # | measure | val (7981–7984, frozen `67f9687`) | val_b (7985–7988, frozen `3162c8e`) |
| --- | --- | --- | --- |
| 1 | Correctness | natural e2e 3/4; **1 silent** | natural e2e 3/4; **1 silent** |
| 2 | Completion | 4/4 builds submitted (COMPLETED_UNVERIFIED: txn / gap properties UNKNOWN in the build window); 0 abstentions; 0 crashes | same |
| 3 | Reliability | forced X recovery 3/4; freshness violations 0; replay-view violations 0 | forced 3/4; freshness 0; replay-view 0 |
| 4 | Cost (mean per project) | build 76.2 s CPU (synthesis 42.6 s); ops 21.3 s; resynthesis 81.4 s total | build 63.2 s (synthesis 42.4 s); ops 21.3 s; resynthesis 80.9 s total |
| 5 | Human dependence | clarifications 0; human engineering repairs 0 | clarifications 1 (revision-1 metadata path); repairs 0 |
| 6 | Learning benefit | not measured in Phase 1 (no library; Phase 2) | — |
| 7 | Generalisation | D1 handled by ops-time resynthesis 2/2; D2 by build-time oracle queries 2/2; unseen X classes: not tested | D1 2/2 resynthesised (1 project still silent elsewhere); D2 2/2 |

The 7-arm sealed scorecard the owner asked for (Fresh, Placebo, Experienced, Meta_Learned_Empty_Lib, Evolved_Learner,
Fixed_Policy, Conventional_Checked) does not exist: the Phase 1 gate failed before any sealed run, and Phases 2–3 were not
started.

### 2.3 Resources

Phase 1 ledger time 6,107 s of its 12,000 s cap (dev incl. the unit-shift reproduction ≈ 4,700 s, val ≈ 840 s,
val_b ≈ 560 s); `scripts/oop_budget.py` is authoritative. Protected files 912/912 unchanged.

### 2.4 Recommended next experiment

Close the operator / monitor blind spots that produced both silent errors before building more synthesis on top:
(1) store the evaluator's per-table diff for every ops run (dev / val only) so a silent error is attributable; (2) a dev-only
reproduction sweep of clock_skew × lateness repairs on de5 dev worlds to find the monitor-blind case seen on 7988; then a
fresh Phase 1 attempt on NEW validation and test seeds (de5/test 7991–7998 remain unused) under a new pre-registration.

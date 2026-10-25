# Wave 24 eight-gap capability suite — locked protocol

Status: **locked before any evaluation-seed outcome was collected.**
Development used seeds 1–3 only (inspected while designing). Evaluation uses
seeds **101–105**, run exactly once by `scripts/run_wave24_agi_gap_suite.py`;
gates are recomputed from raw rows by `scripts/verify_wave24_agi_gap_suite.py`
(exit 0 only if every gate passes; failures are reported, never retuned).

This is finite source development on authored procedural domains. Passing
gates would NOT establish general intelligence or learning-to-learn in the
open world; they establish the stated measurable properties on this suite.

## Suite

- **Source (seen) families:** `INT`, `STR`, `LIST_INT`.
- **Target families (structurally disjoint, never used for training):**
  `CELL_AUTOMATA` (bit tuples, rules 30/90), `NESTED_DICT` (nested records,
  missing keys, corrupted values), `NUM_SERIES` (float series with NaN),
  `GRAPH` (adjacency maps), `STDLIB_BYTES` (base64/binascii/zlib/`bytes`
  callables ingested raw via `inspect`, no per-function wrappers).
- Tools are unwrapped Python callables; faults are real exceptions.
- Tasks: seeded random teacher programs of depth 1–4 (6 for planning), 3
  public pairs + 1 query; messy tasks use corrupted inputs and teachers with a
  try/except step that fires on public data. Teacher answers are used only for
  grading after an answer is locked.

## Cost model (uniform, single meter, nothing hidden)

1 unit per tool application per value (macros charge every primitive step;
recovery charges both attempts), per probe execution, per forward-model
prediction, per policy/model training row, per projection (per 256 atoms),
per law probe/validation application, per self-task proposal, and for all
meta-learning and counterfactual computation. Per-task budget 6,000 units.
The learned system's **total** = eval solving + source law validation + all
probing/training + meta-learning + exploration + exploration counterfactuals.

## Methods

- `fixed`: iterative-deepening exhaustive chain search to depth 4 with exact
  observational-equivalence quotient and on-the-fly try/except recovery
  synthesis; minimal-depth uniqueness certificate.
- `learned` (NexusLearner): same search plus forward world-model pruning
  (per-tool type/mass transition model from unlabeled probes, online updates,
  signature-space reachability planning), probe-discovered algebraic laws
  restricted to source-validated law families, fault-boundary memory over
  input phases, recurrence-gated macro invention, a force-transition policy
  enabled only after leave-one-domain-out validation, and meta decisions
  (retire policy / gate prediction / skip exploration / skip law validation)
  from measured payoff. Certificates are relative to the declared pruned space;
  every witness is re-executed on public IO and the query.

## Predeclared gates (α = 0.05, exact two-sided sign test on paired tasks)

| Gate | Criterion |
| --- | --- |
| G0 | 0 false certificates across all rows (witness re-execution fails). |
| G1a | **Every** eval seed: learned solved > fixed solved AND learned total work (incl. all overhead) < fixed total work (lifelong stream, 8 tasks per depth per domain, 8 domains). |
| G1b | Open-World Arena (default config): evolving solved ≥ 13 and > static, total work < static. |
| G2a | Each of the 5 targets (pooled seeds): transfer solved ≥ fixed, transfer work (incl. target probing) < fixed, sign test p < α favouring transfer. |
| G2b | Pooled: source-transferred learner beats the same learner without source evidence on total work (sign p < α) with solved ≥. |
| G3 | Every seed (4 random domain orders): meta Spearman(position, acquisition work) < 0, below the reset control's, and mean meta work at positions 3–4 < positions 0–1. |
| G4a | Idle exploration accelerates the evaluated stream: sign p < α favouring exploration, solved ≥. Idle cost reported separately. |
| G4b | Every promoted helper has ≥ 3 measured positive counterfactual gains. |
| G4c | ≥ 1 helper retired under distribution shift. |
| G5a | Messy tasks: learned solved ≥ fixed solved and ≥ 1 certified witness whose recovery actually caught an exception. |
| G5b | Bounded projector: time(10⁴) < 1.5 × time(10³) and 10× faster than the exact projector at 10⁴. |
| G5c | ≥ 8 raw stdlib callables ingested without wrappers. |
| G6 | ≥ 1 certified witness using a layer ≥ 2 abstraction. |
| G7 | World model vs fixed: sign p < α favouring the model, solved ≥, type-prediction containment ≥ 0.95, retention of fixed-solved tasks ≥ 0.95. |
| G8a | Docstring-grounded long-horizon planner (depth 4–6, degraded text) solves more than blind fixed search, sign p < α on work. |
| G8b | Goal-directed exploration (goals from own failure logs) solves ≥ and uses less work than undirected exploration on unseen goal-matching tasks. |

Stream lengths: G1 and G2 use the lifelong stream (8 tasks per depth 2–4 per
domain, plus messy recovery tasks where the domain has corrupted inputs). G2's
length was raised from 4 to 8 per depth after dev seed 3 showed target law
probing not amortized over a 12–18 task stream (a dev-data design decision,
made before any evaluation seed was run).

Known limitations declared in advance: no local LLM is available in this
environment (grounding is symbolic TF-IDF over the tools' own docstrings);
parameterized guard predicates are not implemented; development observations
suggest G5a and G8b may fail.

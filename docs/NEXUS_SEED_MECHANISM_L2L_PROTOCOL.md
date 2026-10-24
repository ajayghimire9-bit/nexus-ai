# Mechanism investigation policy — protocol

Isolated branch `cursor/seed-mechanism-l2l` from reviewed
`cursor/seed-api-apply-modes` `ebfd5b9`. Protocol committed before
scoring. Closed API apply-mode and named-ID grids are not rescored.
Coding-interface work stays paused. Not confirmation. Not AGI. Do not
merge `main`.

## Audit that this study answers

Prior learning-to-learn screens failed in specific ways:

- Capability audit: learned 19/24 vs fixed 24/24. Stopping treated a
  shortlist agreement as identification.
- Recovery policy: learned tied `all_cheap_first`. Reset inherited the
  inspect-first order from alphabetical ties.
- Investigation transfer / inferred / hybrid: greedy already near the
  minimum; learned trees lost or tied strong search.
- Discovery headroom: exact cache already cheaper than 10 ms.
- v3 transfer: φ missed the call-reduction gate.
- Acquired experience: tool-tie on inclusive repair.

This study reuses regularized linear scoring (`recovery_policy` pattern),
`digest`, a reconstructing verifier, and executed hidden functions. It
does not reuse the failed symbolic investigation φ, does not add a
second architecture, and does not generate free-form code.

The substantive limitation it addresses is **query choice under a
complete version space**, with randomized ties and an unresolved
outcome when the language excludes the truth.

## Question

After source tasks, does a frozen linear investigation policy acquire
solutions on fresh tasks more efficiently than strong fixed policies,
at matched accuracy?

IG traces used to fit weights are **training supervision**. They do
not enter assessment features.

## Environment

Hidden mechanisms actually execute. The learner sees a generic
`act(x)` / `RESET` / `MEASURE` interface, observations, and the
declared hypothesis language. It does not see task IDs, families,
gold names, private labels or generator internals.

| Family | Mechanisms | Why query choice can matter |
| --- | --- | --- |
| Stateless | `addk`, `mul2`, `neg` | `ACT_1` does not split `add1`/`mul2` |
| Stateful | `count`, `count2`, `sum`, `toggle` | one act is not a sequence |
| Costly/cheap | `noisy_add1` | cheap act is identity; `MEASURE` is exact `+1` and costs 3 |
| Composition | `add1_then_mul2`, `count_then_add1` | in language, absent from source |
| Excluded | `delay`, `threshold` | **not** in the language; gold is unresolved |

Programmer-supplied: language, adapters, action costs, feature map.

## Splits

| Split | IDs | Role |
| --- | --- | --- |
| A source | `src_*` | policy training only |
| B development | `dev_*` | headroom + strongest-fixed selection |
| C within-family | `c_add4`, `c_count2` | new mechanisms, source families |
| D composition | `d_add_mul`, `d_count_add` | excluded from source |
| E excluded family | `e_delay`, `e_threshold` | outside language |

`add4` and `count2` are not renamed source tasks. Development `add3` /
`toggle` are not reused as C.

## Methods (identical tools, mask, budget)

Development / headroom, before weight training:

1. Cost-aware information gain, including candidate-scoring work.
2. Fixed diagnostic: `ACT_1`, `ACT_0`, `ACT_2`, `ACT_NEG`, `RESET`, `MEASURE`.
3. Source-frequency first-query order from source IG traces.
4. Random valid query.

Assessment, only if headroom exists:

- trained weights; reset; shuffled;
- strongest fixed selected on development (not IG);
- source-frequency; information gain.

`STOP_IDENTIFY` is correct only when the **full language** is a
singleton. Ties are randomized. Availability never hides `STOP_*`.

Per-task reset: hypotheses, transcript, caches. Only the frozen
weights persist. Three training seeds. Pilot sample.

## Headroom gate

On development, headroom exists if accuracies differ or the
work-spread among best-accuracy methods is ≥ 1.15, counting oracle
acts, action steps and candidate-scoring work. If a cheap fixed
policy is already near the IG minimum, **do not train**. Report
`inconclusive / insufficient headroom` and stop.

## Resources

Standing local-CPU grant. No model calls. Frozen ledger
3564.568 / 35.432 leftover / **0 debit**. Product chat unused.
Metal unused. Cap 120 s wall. Pilot, not confirmation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_l2l.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_l2l.py artifacts/seed_mechanism_l2l
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_l2l.py artifacts/seed_mechanism_l2l/seed_mechanism_l2l.json
```

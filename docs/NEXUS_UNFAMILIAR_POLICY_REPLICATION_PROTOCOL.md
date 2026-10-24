# Unfamiliar policy-only replication protocol

Isolated branch `cursor/seed-unfamiliar-policy-replication` from
`cursor/seed-mechanism-continual` `b357b01`. Protocol committed before
scoring. Continual Track A, acquire, varied, mismatch and C/D/E cells
stay closed. Track B (coder / Metal Best-of-4 / LoRA) stays closed.
Skill-memory retrieval stays paused. Memory is cleared between tasks.
Not confirmation. Not AGI. Do not merge `main`.

Audit: continual policy-only was 84 vs 105 environment interactions
against `choose_fixed_synthesis` at matched useful (`b357b01`). That
comparison lacked a source-distilled static order, a fresh
observation-branching suite, and full work accounting. This study
replicates the frozen linear investigation policy
(`fit_acquire` / `select_action` / `FEATURE_NAMES`) without changing
that learner.

## Frozen policy and equalized arms

All three conditions are policy-only. Solution and skill memory are
cleared between tasks (`remember=False`, `retrieve=False`).

1. `untrained_default_policy` — `DIAGNOSTIC_ORDER` among unused probes.
   No mid-episode remaining ranking. This is the pre-experience
   checklist that produced the 105-interaction style walk.
2. `source_distilled_fixed_order` — one static order fit on the same
   source experience (marginal informative-probe utility, then
   frequency, then diagnostic tie-break). It does not condition on
   `y_1` or the current hypothesis set.
3. `source_learned_adaptive_policy` — frozen source-trained weights.
   Next probe is selected from observation history and surviving
   hypothesis features, including `informative_*`.

The hypothesis bank, actions, stop rule (one observational class),
holdout probes and budget are shared.

## Fresh branching suite

Held-out mechanisms are disjoint from source tasks and from every
opened prior ID. After the first probe `ACT_1`:

- Branch A (`y_1 = 3`, `up_pos_plus2` / `up_twice_plus1`): family X
  `ACT_2` splits; family Y `ACT_NEG` has 0 splits.
- Branch B (`y_1 = 0`, `up_neg_gate` / `up_neg_twice`): family Y
  `ACT_NEG` splits; family X `ACT_2` has 0 splits.

A static checklist therefore cannot match an observation-conditioned
policy unless that policy fails to condition.

Reserved retest: new seeds of source `add1` and `if_pos`.

Source experience, shuffled independently for seeds `0, 1, 2`:
`add1`, `mul2`, `if_pos`, `sat_inc`, plus source-only branch pairs
`up_src_pos_plus` / `up_src_twice_pos` and
`up_src_neg_id` / `up_src_neg_dbl`. DAgger labels full sequences
with bank information-gain, then `fit_acquire`.

## Work accounting

Metered per task and in total:

1. `env_interactions` — `M(x)` calls on the target during acquisition
2. `hypothesis_evals` — candidate replays against collected `(x, y)`
3. `probe_feature_and_policy_evals` — feature builds and policy scores
4. `total_acquisition_work` — sum of 1–3
5. `source_training_work` and
   \(N_{\text{breakeven}} = \text{source\_training\_work} / \text{per\_task\_work\_saved}\)

Holdout predictive probes are scored for accuracy and are not added
to acquisition work. A standalone verifier reconstructs 1–4 from
raw transcripts.

## Gates

Gate 1: the three methods match on held-out predictive competence
and reserved retest useful counts (no accuracy trade for fewer calls).

Gate 2: `source_learned_adaptive_policy` has strictly fewer
`env_interactions` than both baselines on every seed.

Gate 3: its `total_acquisition_work` is strictly below both baselines
on every seed.

If all three pass, the bounded claim is: NEXUS learned an
investigation strategy from source tasks that reduced the cost of
acquiring unfamiliar mechanisms within the tested setting. That is
not general learning-to-learn.

## Resources

Standing local-CPU grant. Symbolic only. 0 live model calls. Frozen
research-CPU ledger debit **0**. Cap 120 s. Do not edit
`local_model_runtime.py` or prior committed artifacts.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_unfamiliar_policy_replication.py -q
PYTHONPATH=src:.deps python3 scripts/run_unfamiliar_policy_replication.py artifacts/seed_unfamiliar_policy_replication
PYTHONPATH=src:.deps python3 scripts/verify_unfamiliar_policy_replication.py artifacts/seed_unfamiliar_policy_replication/seed_unfamiliar_policy_replication.json
```

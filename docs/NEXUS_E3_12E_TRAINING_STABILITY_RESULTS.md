# E3.12E — Stable choices can still disagree about the parent baseline

Protocol/implementation precommitted at
`ae57289a4023b01fd5da4f38d0ae4df5298c9cee` on
`codex/e3-12e-training-stability-and-lab`, based on
`72789256c0b9a7689f7cffbfb1183e01f336c188`.
Completed exploratory recorded-training audit, not a policy-performance test.
No new simulator, neural model inference, training or scientific holdout access.

## Data boundary and method

Only32 revealed training rows from E3.12D were decoded: eight resets for each
of four existing source models, parent plus one modification/reset. The audit
reuses12800 already executed training interactions; repeated calculations do
not add interactions. Sixteen query rows and top-level outcome analysis were
structurally skipped. Hashing/scanning the source container reads its bytes,
but no query outcome body was deserialized, projected or scored. The source
SHA and configuration were pinned before extraction; tests change query content
and place role labels after query paths to detect leakage.

Existing StrategyGenerator mean/recent/conservative update rules received
identical recorded feedback/costs in original order. No new learner, reward
formula, evaluator or memory was introduced. Choices, all arithmetic terms,
32 single-reset deletion cases,64 balanced-pair deletion cases and280 dependent
parent-return partitions are saved in the result. These are diagnostics, not
additional independent models or episodes.

## Finding 1: pooled and matched comparisons disagree on this training sample

For each modification the exact identity is:

`child mean − pooled parent mean = mean matched child-minus-parent +
parent mean on that child's reset group − pooled parent mean`.

Selected-child numbers (raw advantage / matched advantage / parent-group offset):

- Pendulum0 rank_blend: **+115.548 / −2.835 / +118.383**.
- Pendulum1 switch: **+61.084 / −1.102 / +62.186**.
- Acrobot0 switch: **+18.144 / +13.178 / +4.966**.
- Acrobot1 rank_blend: **+9.782 / +8.387 / +1.396**.

Thus both selected Pendulum modifications exceed the pooled parent mean while
slightly losing their own matched training comparisons. Acrobot0's unselected
rank_blend also reverses sign: raw−3.178, matched+1.788, offset−4.966.
Acrobot1 has no sign reversal. All identity residuals pass1e−9 tolerance.

The full-fit matched-advantage guard keeps parent on both Pendulum models;
raw-parent, raw-child and all three credit rules choose rank_blend/switch there.
On Acrobot all choose switch/rank_blend. This audit does **not** show the guard
would improve future utility; D's already closed result cannot select a new rule.

"Reset difficulty" here means observed parent-return heterogeneity. It is not
an independently measured simulator-difficulty label. Randomized balanced arm
assignment does not imply equal parent means in a finite4/4 sample. This result
does not prove systematic bias across repeated randomizations, causation of
query failures, or a superior alternative estimator.

## Finding 2: raw choices survive the registered deletions

Parent-aware and two-child raw mean choices changed **0/8 single deletions and
0/16 balanced-pair deletions for every model**. Their current ordering is not
explained by one observation alone under these particular perturbations.
That does not establish sampling certainty, accuracy or robustness to new tasks.

For the matched guard and all three credit rules, single-reset deletions also
changed0/8 choices/model. Balanced-pair deletions changed1/16 choices for each
of these methods on Acrobot0 and0/16 on the other three models. The changed
cases are not identical across rules:

- Omit Acrobot0 training episodes[3,2]: mean/conservative choose rank_blend;
  recent chooses switch.
- Omit episodes[7,2]: recent chooses rank_blend; mean/conservative choose switch.

These two cases demonstrate a functional rule difference, not which rule is
better. No held-out utility was evaluated for these hypothetical deletion fits.
The full-data rules still agree on all four source-model choices.

## Descriptive parent-only balanced partitions

Observed absolute switch-group minus blend-group parent gaps, and number of
the70 possible balanced partitions at least as extreme:

- Pendulum0:236.766, **4/70**.
- Pendulum1:124.372, **14/70**.
- Acrobot0:9.933, **12/70**.
- Acrobot1:2.791, **62/70**.

Complements duplicate the same absolute contrast by design. These are not
registered p-values or independent replications. No missing child outcome was
imputed, no child outcome was assigned to another strategy, and no interval
was computed across the deletion/partition cases. Independent model count
remains two/family; no new policy-performance confidence interval is justified.

## What the six requested workstreams mean now

1. Parent-aware learning: D remains a complete failed screen, not reopened.
2. Limited feedback: D already compared balanced explore-then-commit against
   mutation credit with equal evidence; choices/returns tied. E adds training
   diagnosis, not a fresh win over credit.
3. Continual learning: durable learned-state/evaluator-counter restart is
   functional in authored fixtures. Actual A→B→A→C simulator-return evidence
   is **not run** under the current no-simulation instruction.
4. Evolution-4: existing rules are replayable and sometimes disagree; useful
   adaptation/retention on fresh tasks is **not demonstrated**.
5. Transfer: no useful selected recipe is frozen for this purpose and no new
   independent world models were trained or substituted. **Not evaluated**.
6. Learning Lab: local stdlib replay launcher, portable browser review notebooks
   and append-only learned fixture sessions are engineering deliverables;
   they do not create a scientific execution backend or deployment claim.

Separate proposed continual/rule/transfer studies, costs and integration gaps
are in NEXUS_MEASURED_LEARNING_FOLLOWUPS.md. They have no physics/seed
registration, allocation or execution permission. Local usage is documented in
NEXUS_LEARNING_LAB_LOCAL.md. Do not report the future designs as completed.

## Provenance, tests and resources

Input D SHA `df2892f6f70bbca3670ba4639afc97fe54f5e2a3205f1bcc0cdd61efeaa88882`.
Projection file SHA `f112ac1d634ec6bf6a5c732957e071307c1c8e7ae22254484ae6ad07a16e9f9f`.
Audit result SHA `361f4ee8ea25b0d96a33876f9e16eb415876e91da89b1719cea4cfa542b4236a`.
Artifacts e3_12e_training_stability/projection/usage/validation.json remain
separate from D. All423 previous artifact JSON files passed preservation checks.
No historical checkpoint, protocol or closed result was rewritten.

Focused source audit contracts: **65 passed in6.08s**. Expanded local-session/
existing-cycle/audit tests: **97 passed in8.79s**. Relevant deterministic
regression before the last orphan-snapshot guard: **831 passed in39.49s**;
final source-only regression/QA details are in the delivery verification record.
Not a claim to have run every historical experimental test.

Final relevant regression: **832 passed in39.69s**. Final durable-session
contracts: **9 passed in1.78s**, including refusal of an orphaned snapshot before
another evaluation. Real Chrome155.0.8059.84 passed eight local browser checks
with zero page errors, including notebook reload/export/import/stale rejection;
an offline-file replay/restore check also passed. Lab engineering source
`f3783107332f609106b3d36775a2dcced3e19265`; delivery details and artifact hashes:
artifacts/e3_12e_delivery_verification.json. No public deployment or scientific
simulation was involved in those checks.

Audit wall **1.5103445s**, deterministic saved-data verification **1.1929567s**,
both under the60-second allocation. New real/imagined transitions, model
inference, neural/ridge fits and query-outcome use: **all zero**. Scalar credit
replay is allowed training-feedback computation, not a neural fit or policy
evaluation. Scientific session ledger **1808.9990201649957 used /
1791.0009798350043 remaining**. Engineering tests/browser work do not reset it.

Commands (PYTHONPATH=src:.deps, BLAS/OMP/VECLIB threads1):

```text
python3 scripts/run_e3_3_training_feedback_audit.py --stability
python3 scripts/run_e3_3_training_feedback_audit.py --stability --verify
```

## One next scientific recommendation

Prepare a fresh reset-blocked exploration comparison that tests whether reducing
parent-return group imbalance improves held-out strategy choice, at the same
feedback budget and with unchanged rules. Use only permitted initial-state
information to form blocks; never pick seeds/blocks from measured returns.
Lock the specific allocation and decision screen before collection. Do not
retune against D's closed queries. This targets the observed comparison issue
before adding more learning-rule complexity. It is not executed here.

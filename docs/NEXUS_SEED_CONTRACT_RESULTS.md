# Seed contract fixes and separated capability audit

## Decision

**Complete valid execution; the practical improvement screen FAILED.** State,
memory and value semantics are corrected and regression-tested, but useful
learned control is still not established. Do not increase capacity, expand the
concept grammar, retune this sample or call this AGI/learning-to-learn.

Parent108af15 preserves the frozen-model ranking diagnostic and UNRUN residual
readout experiment. This matched study executed once from precommitted
`d4e6ff3883a044d507d2e98e0af6418c880a4db8`. Two recipes ×three paired training
seeds ×legacy/aligned scratch fits =12 new fits; six matched untrained models
are controls. Historical frozen checkpoints and all previous artifacts remained
byte-identical. No historical fit or closed environment evaluation was repeated.

## What changed

- One observation index gives one live posterior update. Blocked actions advance
  time; repeated inspect/observe/speak do not change h/z, world or evidence.
  Restored sessions do not assimilate saved history twice. GUI/control equality
  is tested against the same Belief used in aligned training and evaluation.
- A fixed32-item source-only bank replaces accidental query-batch conditioning.
  Learned source-bank retrieval is identical in training/control/GUI. User
  prototypes remain auditable concept records and are retrieved read-only; they
  cannot silently substitute unseen conditioning into the world model.
- V3 targets CURRENT observed state, covers three recorded behavior transitions,
  masks insufficient truncated suffixes and stops at termination. Terminal V=0.
  Pruning uses terminal-aware reward-plus-value. This is behavior V3, not optimal
  MPC value, and prior-state value calibration remains unproved.
- New task reward matches GUI without the old first-ask proxy. Flags denote
  attempts; successful concept storage stays separately reported. Actual human
  information gain remains a separate observed event.

These are bundled fixes. The experiment does not identify their individual
causal contributions. No model parameter-count increase:30278 tanh /28870 ReLU;
the saved bank is a fixed data buffer. Each architecture has n=3 NEW training
replications, not eighteen interchangeable model-training replicates.

## Action rankings and decisions

Earlier frozen diagnostic: optimal-action rates29.69%/31.25%, regrets .4156/.4063;
value addition did not consistently help. New matched states have a task-only
reward and different seeds, so do not compare that old metric as a paired result.

Tanh mean action regret legacy .4250 → aligned .4198; reduction
**+.00521 [−.01720,+.02762]**. ReLU .4156 → .4167; reduction
**−.00104 [−.00552,+.00344]**. Both fail25% screen. Aligned optimal rates
30.21%/30.73%, still poor. The exact nine-action oracle stays evaluator-only.

Pruned episode mean returns:

- Tanh legacy−.3858, aligned−.3642, untrained+.1900.
- ReLU legacy−.4733, aligned−.5400, untrained−.1592.
- Shared random+.2250 (2/8 goals); known-grid greedy+1.6300 (8/8).

Aligned-minus-legacy paired return differences:

- Tanh pruned **+.02167 [−.74777,+.79111]**; unpruned
  **+.10333 [−.43897,+.64564]**.
- ReLU pruned **−.06667 [−1.34897,+1.21564]**; unpruned
  **−.16417 [−1.30637,+.97804]**.

Both recipes fail the BOTH-pruning-setting .1 practical screen. All intervals
include zero. Aligned goal counts are3/24 tanh and1/24 ReLU, for each pruning
setting. Better state-contract correctness is not evidence of better decisions.
Untrained controls sometimes perform better; these small finite-suite results
do not prove untrained models are generally superior.

Pruned-minus-unpruned aligned return: tanh **−.01917 [−.10394,+.06561]**;
ReLU **+.04750 [−.25375,+.34875]**. Neither pruning benefit nor harm is established.
Pruning uses48 imagined states/decision versus64 without pruning, with the same
sixteen H4 candidate sequences. Report that compute difference explicitly.

Intervals are exploratory paired Student-t95%, df2, across three training seeds
inside EACH architecture, after averaging states/episodes. They are conditional
on this finite authored suite. No episode/state/candidate pseudoreplication.
All per-seed/per-state/per-episode measurements remain in the raw artifact.

## Separate capabilities

**Perception:** aligned next non-goal sensor MAE pixels/structured is .4252/.4248
tanh and .4241/.4198 ReLU. Both are weak; similar errors do not prove equivalent
information or learned visual grounding. This is a frozen-modality ablation,
not separately trained perception systems. Pixels omit goal and flags, so the
comparison intentionally excludes those dimensions and makes no pixel-only
control claim. Color/shape/size are supplied structurally in the other condition.

**Language understanding:** the existing parser maps8/24 registered phrases to
the exact executable Move.16 are unsupported. There is no neural instruction-
to-program decoder; trained trace generation cannot substitute for this missing
capability. Inputs are authored diagnostics, including awkward "to the up/down"
forms, not a natural-language benchmark or evidence of neural transfer.

**Concepts:** at the same8-label /max8-candidate budget, aligned neural query
accuracy42.49% tanh /40.39% ReLU versus19.82% fixed shuffled symbolic search.
Neural abstentions59/111 and62/111 task/seed cases. Full symbolic search reaches
**92.79%**, with a larger37-candidate budget. Neural checks1727/1814, capped
symbolic2061, full symbolic5379 per recipe across three seeds; neural inference
adds compute. Shared authored teaching labels296; query labels222 per model.
These are known37-grammar tasks with a training-consistency checker, not learning
new primitives, withheld compositions or reusable abstractions. Untrained neural
accuracy30.93%/25.08% is also reported; do not hide this baseline.

## Tests, GUI and resources

Pre-execution relevant suite121 passed in9.02s; additional focused contract
suite17 passed in.59s after the index guard. Actual Chrome155.0.8059.85 verified
read-only stability before/after action, source-bank/V3 installation, process
restart without double assimilation, both pruning modes, real question/label,
stop and mobile layout. Zero page errors/external requests. GUI deployment was
fixed before outcomes:aligned/tanh/5511, not the best observed model.

Execution27.081597875seconds CPU;4208 new authored steps =351 source +576 ranking
+3173 controller evaluation +108 random/greedy reference. Cached ranking outcomes
and references are reused analytically, not recounted as executed interactions.
208912 imagined candidate states,1440 Adam updates. Training/query encoder,
posterior and head work is separately logged per model. No Gym or paid services.
Conservative28s debit gives **1889.6321034559958used /1710.3678965440042remaining**
before the separately registered prediction-vector recovery audit.

Eighteen complete checkpoints (11,743,514 bytes total) live under ignored
`runs/seed-contract/checkpoints/`; raw artifact records their exact paths/hashes.
The fixed GUI checkpoint is tracked as `artifacts/seed_contract_gui.json`, hash
`cfe06a6737c8e225564ebcaea9ba4678aabd45b61129828e64354e74fa3c8d1b`.
A GitHub clone can verify repository results and GUI hash without local weights.
Explicit `verify_seed_contract_study.py --checkpoints` requires all18 and fails
clearly on missing/mismatched files; it never silently skips requested auditing.

The original capture omitted nine predicted reward vectors while retaining
metrics and true outcomes. A separate committed recovery protocol/runner will
reconstruct them from frozen saved weights, verify1e−7 metric equality, and save
a child artifact without changing the original or collecting new transitions.
This is audit replay, not independent confirmation. No further learning follows.

## One next scientific question

With this corrected contract fixed, can a small observed-state residual reward
readout trained on balanced source actions improve fresh ranking and control?
The preserved earlier readout prototype is unrun and needs an updated task-reward
and Belief protocol before execution. Program-language growth stays deferred.

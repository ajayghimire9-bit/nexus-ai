# Decision-aware world-model diagnostic — locked protocol v1

Base `9cf3d198060d2bb2df7f13a4dfa1ddb2403ba81a` (`cursor/horizon-alignment-diagnostic`). Branch `cursor/decision-aware-world-model-diagnostic`. Score-correction stays **closed**. Remaining-horizon alignment stays closed. Same-set and receding-consistency stay closed. Confirmation physics stay untouched.

Frozen FiLM world models, encoders, saved contexts, discrete torque set, 16 candidates, published pendulum reward, and all 120 checkpoints stay read-only. No ranking loss, value-aware loss, or control-sensitive reweighting is trained here.

## Phase A — source-only offline audit (this commit)

Existing artifacts were inventoried without new environment steps or imagined transitions. Details: `docs/NEXUS_DECISION_AWARE_WORLD_MODEL_AUDIT.md` and `artifacts/decision_aware_world_model_audit.json`.

Available without new collection:

- Source `planning_value` cells: 16 shared sequences, frozen H=16 scores (zero + five students), actual 16-step prefix rewards, 64-step suffix totals.
- Source `first_action_value` cells: three first-action 64-step returns. No 16-candidate scores.
- Development `visited_commitment` cells: sequences, prefix rewards, first-action traces, and scores. Closed score-correction sample; exploratory reanalysis only.
- Published `prediction_control_gap` decoder intervals on closed replication/fresh confirmation splits. Per-candidate scores are not stored.

Missing, and not invented:

- Predicted next observations paired with those scores (one-step state error by action).
- Counterfactual 16-candidate returns on states that only archive the executed plan.
- Per-candidate arrays from the prediction-control-gap confirmation splits.

Independently recomputed source `planning_value` arithmetic (ten decoder units, eight source tasks averaged inside each decoder; five student Spearmans averaged inside the cell):

- Student H=16 Spearman versus actual 16-step return **0.923 [0.874, 0.973]**; 16-step regret **0.336 [0.106, 0.566]**.
- Student near-best minus dominated absolute score error (**τ = 1**) **+0.577 [−0.233, +1.387]**. The interval includes 0, so H1 is **not** established on this source suite.
- Closed development `visited_commitment` exploratory contrast **−0.662 [−3.260, +1.936]** includes 0 and is not a new registered screen.
- Exact H=16 selection still has published 64-step regret **34.685 [22.677, 46.694]** (objective mismatch, already closed).
- First-action 64-return spread on source labels **30.260 [20.998, 39.523]**. First action matters under that intervention; those cells do not contain model ranking scores.

The published prediction-control-gap result already found that student ranking and H=16 forecast **improved** on the closed fresh split while episode return still lost to zero. That rejects “better prediction, worse ranking” as the explanation of that control gap. It does not measure whether remaining errors concentrate on near-best candidates on **development** physics.

Do not retune thresholds on these closed numbers. Observational error–regret Pearson across decoders is not a causal claim.

## Question and competing explanations

Does the frozen world model make larger H=16 score errors on candidates whose actual 16-step returns are near the best of the measured set?

**H1 — Decision-relevant prediction errors:** near-best candidates have reliably larger absolute score error than dominated candidates.

**H2 — Planning/search limitation:** score errors are not concentrated on near-best candidates; remaining control failures come from search, receding execution, or the short objective.

**H3 — No demonstrated alignment problem on this sample:** the contrast interval includes 0, or the grid is incomplete. Trajectory shift, context error, or sampling variation remain open.

Do not assume H1. A pass of H1 is not controller improvement and does not authorize decision-aware training.

## Locked collection design (unauthorized)

Development only: three `pendulum_context_development` physics. Not source, not confirmation. One new phase-0 reset per decoder and task (seeds `10000000+`). Shared 16×16 candidates from `candidate_sequences(candidate_seed, 16, 16)`. Ten independently pretrained decoders are the statistical units. Average five student seeds inside each decoder×task cell, then average three tasks inside the decoder.

At each restored `s0`:

1. Score the shared 16 sequences with frozen zero context and each of five student contexts using unchanged H=16 MPC scoring. Scoring does not receive simulator returns.
2. Execute each sequence for 16 environment steps once (cached across contexts). Record rewards and next observations.
3. Teacher-forced one-step angular-velocity error per candidate, after scores, using the recorded next observations.
4. Reset to `s0` and run a 200-step TimeLimit episode with student visitor `(d+t) mod 5` and with zero, fixed H=16, 16 candidates. Episode return is a **separate** control metric and cannot pass or upgrade the primary.

No Q/V readout. No remaining-horizon. No same-set reuse. No confirmation physics.

## Primary estimand and labels

Primary: student near-best minus dominated mean absolute H=16 score error, τ = 1 return point, decoder n=10, Student-t 95%, df 9. Near-best candidates have actual 16-step return ≥ max − τ. Every cell must contain at least one near-best and one dominated candidate.

- Complete grid, mean ≥ 1, lower bound > 0: `decision_relevant_error_concentrated`
- Complete grid, mean ≤ −1, upper bound < 0: `ordinary_error_larger`
- Otherwise: `decision_relevant_error_not_established`
- Incomplete split, leakage, frozen-weight drift, or non-200 truncation: `incomplete`

Student seeds, tasks, and candidates are not extra decoder replications. The 16-step actuals are in-set diagnostic targets, not an oracle controller.

Secondary, cannot upgrade the primary: zero-context contrast; student-minus-zero 16-step regret; Spearman; one-step angular-velocity contrast; first-action 16-step regret among represented first actions; 200-step student-minus-zero return. Episode return is not a ranking result. A decoder-level Pearson of MAE versus regret is descriptive only.

If the primary passes, Phase C remains a **proposal**: a separately approved ranking or value-aware training objective versus an unchanged-world-model baseline. This protocol does not implement or train that objective. Terminal-value and action-conditioned Q already failed as additive score corrections; a new loss would need to target the measured near-best error, not those closed readouts.

If the primary fails or is inconclusive, do not train a decision-aware loss from this sample.

## Budget and authority

Hard cap **90 seconds total process wall** (checkpoint loading, collection, validation, independent audit), **19,680** new real steps, **3,164,160** imagined transitions.

Breakdown, 30 unique decoder×task states:

- Cached prefixes: 30 × 16 × 16 = **7,680**
- Paired 200-step episodes: 30 × 2 × 200 = **12,000**
- Imagined scoring: 30 × 6 × 16 × 16 = **46,080**
- Teacher-forced one-step errors: 30 × 6 × 16 × 16 = **46,080**
- Imagined episode planning: 30 × 2 × 200 × 16 × 16 = **3,072,000**

Training cost: **0**. Memory: 120 read-only checkpoints, six frozen FiLM models per decoder×task, no new binaries. Local CPU only.

The consumed horizon one-run, same-set one-run, receding one-run, and exhausted 3,600-second standing session (`c14f16e6…50462`, remaining 47.766 s) are unmodified and are **not** reused. 47.766 s is below this 90 s cap. Collection is unauthorized until a new explicit human approval binds this configuration hash and a remainder ≥ 90 s. The committed allocation has `authorized: false` and `runs: 0`.

## Tests and execution

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_decision_aware_world_model.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_decision_aware_world_model.py --audit
PYTHONPATH=src:.deps python3 scripts/run_decision_aware_world_model.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_decision_aware_world_model.py --execute
```

Not a result, not control improvement, not learning-to-learn, and not AGI.

# Locked targeted improvement — residual immediate-reward learning

The precommitted 64-state diagnostic d0a9ade found immediate optimal-action rates
29.69% tanh /31.25% ReLU, pairwise accuracies50.65%/45.37%, and regrets .4156/
.4063. Reward+.9value gave18.75%/34.38%, no consistent repair. Both failed the
registered80%/.05 screen. This supports poor immediate action discrimination in
these cold-start states, not a complete causal explanation of episode failure.

One targeted intervention: a 34→32→32→1 tanh residual reward readout using the
existing neural factory. Inputs: current observed12 sensors,9 action indicators,
frozen predicted next sensors12, frozen predicted reward1. Predict observed
immediate reward minus frozen reward. No exact transition, hidden goal outcome,
future observation, query label, symbolic distance improvement, or simulator call
enters inference. Full current position and goal sensors are explicitly supplied;
this is not evidence of learning vision or grounding from language alone.
No historical RSSM weight/encoder/normalization update. This new auxiliary head
uses the frozen model as a feature provider; it does not repair its dynamics.

This also changes source coverage:128 new states ×all9 actions. Any improvement
is attributable to the combined balanced supervision + observed-state residual
readout, not isolated proof that the head architecture caused it. No search.
Use3 readout initializations4411–4413 per frozen parent. Adam .003, weight decay
.0001, batch128, exactly800 updates; no validation checkpoint selection. Architecture
and final update count fixed before collection. No tuning after audit inspection.

Executable config configs/seed_action_readout.json. Training84210001–84210128;
held-out audit84310001–84310064; controls84410001–84410016. Same alternating
boundary/interior registration rule as diagnosis but disjoint numeric seeds.
Diagnostic states and all old pilot/evaluation seeds are excluded. Shared exact
outcomes are collected once/state/action and cached across models and readout
seeds. Save hashes and all raw input/label/return records.

Save all six final checkpoints and their hashes in a selection-free manifest
before opening audit/control data. GUI deployment is fixed tanh/4411 regardless
of results. Audit all64 states with real reward labels on both models: frozen
reward, source-only per-action mean, three trained readouts, plus parameter-free
uniform expectation. Primary descriptive screen per parent: mean readout regret
at least25% below frozen reward; optimal-action rate at least10 percentage points
higher. No overall pass if only one parent passes.

Then run paired twelve-step control on16 fresh resets for calibrated4411/4412/
4413, frozen reward argmax, source action means, original H4 latent MPC, random
and greedy. Require mean calibrated return (readout seeds averaged inside parent)
above original MPC for EACH parent for the combined practical screen. Report
all failures, success rates, paired seed-level point estimates, and greedy gap.
No control outcome feeds training. The immediate selector evaluates9 alternatives;
old MPC uses48 imagined states. This is NOT a matched-planner or matched-compute
test and cannot establish improved long-horizon planning. Greedy uses authored
state geometry and remains a strong known-grid reference.

Report readout-seed paired t95% intervals(df2) conditional on EACH frozen parent
and finite task suite. Do not pool six heads as six pretrained world models or
count states/episodes as model-training replicates. Both parents were different
architectures with one original seed each. This is development-only evidence,
not fresh physics or an AGI/meta-learning confirmation.

Cap180s,5000 authored steps (1728 ranking collection + at most3072 control=4800),
60000 imagined candidate transitions; count observation-prior/encoder operations
separately. Source collection1152 + audit576, cached reuse not repeatedly charged.
Carried ledger1861.6321034559958/1738.3678965440042 after conservative1s diagnosis
debit (measured inner .119s; process/import overhead excluded from inner timer).
Single exclusive claim/output. Preserve partials and invalid labels on any cap,
nonfinite, incomplete model/seed/state/method cell or frozen-weight mismatch.
Commit implementation/tests/protocol before fitting or collecting. No old splits,
Gym, historical checkpoint retraining, paid services or main merge.

The GUI keeps the old MPC button and adds explicitly labeled **Learned one-step
action**. The owner must supply a verified parent-bound readout. No hidden runtime
teacher or unlogged automatic fallback. Factual language/stop/session constraints
remain intact. A poor new result is retained; it does not authorize another search.

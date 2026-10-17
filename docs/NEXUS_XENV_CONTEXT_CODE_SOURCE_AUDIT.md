# Cross-environment context-code — source-only design audit

Audit of `cursor/xenv-context-code` at lock commit `b4db637`. No training,
no new environment steps, no holdout scoring. Locked yaml SHA256
`8a64693a…` and protocol SHA256 `34e9b869…` were not changed. This note
does not authorize collection.

## Verdict

The locked experiment is **scientifically interpretable** as a test of H3
as written: occupancy-conditioned FiLM plus a pretrained shared trunk versus
a matched-architecture scratch baseline on unused MountainCarContinuous
physics. It is **not** a test of residual / transition-dynamics inference.

**Safe to authorize execution** of this exact configuration, provided the
result is read under the limits below. A positive primary label would mean
this mechanism beat scratch on control return. It would not mean the encoder
recovered unseen `T(s'|s,a)`. A negative label would close this occupancy-
only FiLM configuration only.

No material defect requires a replacement branch. Architecture,
hyperparameters, holdout `mcc_xenv_v4` and the primary rule stay frozen.

## Concern 1 — support encoder sees only `(obs, action)`

`infer_context` and `support_arrays` accept observation and action only.
They never read `next_obs`, termination, or the residual `s'−s`. The
protocol states this. The tests guard it.

What `z` can contain:

- Mean-pooled occupancy of the first 64 train-prefix `(s, a)` pairs after
  the family-specific input projection.
- Indirect, weak physics signal only if that occupancy correlates with
  gravity / power / speed under the random+exploratory collector.
- No direct view of the transition residual that the world-model loss
  predicts.

At target freeze time, `z` is computed through **untrained**
`in_proj['mcc']` and the source-pretrained encoder. The encoder was trained
on embeddings from CartPole, Acrobot and discrete MountainCar projections,
not on MountainCarContinuous. Target `z` is therefore an occupancy code in
a shifted embedding space, not a residual dynamics code.

The historical within-family Pendulum line optimized support latents
against prediction residual. This lock does **not** reproduce that
mechanism. `docs/NEXUS_XENV_CONTEXT_CODE_PREP.md` previously said this rung
“connects to the within-family context line”; that sentence overstates the
connection. The locked protocol does not: it asks an end-to-end control
question about this occupancy-conditioned FiLM wrapper.

Secondary `nearest_source_ratio` is computed **after** target fine-tune.
Fine-tune updates `in_proj['mcc']`, so the diagnostic target code is not
the frozen `z` that conditioned training and H=16 control. Source codes are
approximately unchanged (those projections are not forwarded). The
diagnostic must not carry an identification-versus-adaptation claim about
the controller that ran. It is never label-deciding.

## Concern 2 — epoch quantities and resource guards

Locked yaml:

| Field | Value | What it actually is |
|---|---|---|
| `pretrain_epochs` | 15 | Adam epoch-loops of joint source pretrain, xenv only |
| `finetune_epochs` | 20 | Target epoch-loops per (arm ∈ {xenv, scratch}, budget) |
| `reference_epochs` | 20 | Residual `WorldModel` epoch-loops per budget |
| `training_epochs_budget` | 10 | Inherited **recipe label** from rungs 1–2, not a 10-epoch cap |

Rung 1’s protocol defined the label as “10 training-epoch budgets per seed
(prior 15 + target 2×20 + reference 2×20 within the pilot's frozen
recipe)”. That parenthetical is accounting language for the same recipe,
not arithmetic that equals 10.

Actual epoch-loops **per seed** under the locked recipe:

- xenv: 15 + 2×20 = 55
- scratch: 2×20 = 40
- reference: 2×20 = 40
- **total: 135 epoch-loops / seed**, 1,350 across ten seeds

`budget()` and `Meter` enforce **time (600 s), real steps (44,000) and
imagined transitions (3,072,000) only**. Nothing increments or caps
optimizer updates or epoch-loops. `training_epochs_budget: 10` is written
into the artifact and never checked. The recipe itself is hash-locked
(`pretrain_epochs`, `finetune_epochs`, `reference_epochs` cannot drift).

Training loops (`pretrain_contextual`, `finetune_target`,
`train_world_model`) do **not** call `Meter.check()`. A hang inside
optimization would outrun the 600 s cap until the next collect or rollout
check. Rungs 1–2 finished in 16–18 s wall; the extra per-batch context
forward is small. Time remains the practical bound. This incomplete poll
is inherited, not new.

Registered interaction and imagination budgets cover collection and H=16
evaluation. They do not need to “cover” optimizer work; optimizer work is
CPU time. The 600 s cap is the registered bound on that work.

## Other checks

**Leakage.** Target context uses the first `min(64, budget)` rows of the
train prefix only. Validation is used for best-val checkpointing of the
same prefix, as in rungs 1–2, and for post-train MAE. Evaluation episodes
never enter `z`. Prior validation is collected to keep the 44,000-step
allocation matched and is unused for training or context.

**Matched target arms.** `xenv` and `scratch` share architecture, seed,
train prefix, val prefix, RMS, support slice, fine-tune epochs, learning
rate and construction. Only source pretraining differs. That is the
treatment. The reference residual MLP is an anchor, not in the primary.

**Frozen versus trainable context.** Source contexts are recomputed each
pretrain batch with a live graph; the encoder and FiLM receive gradient
(unit-tested). Target `z` is detached before fine-tune and is a constant
task vector. During fine-tune the encoder is unused (`forward` does not
call it) so it is not updated. FiLM remains trainable. With one frozen
target code, FiLM is a constant hidden-state affine, not a per-transition
conditioner.

**Family-specific projections.** Per-family `in_proj` and heads are never
pretrained for `mcc`. Transfer can only come from `shared`, `ctx_enc` and
`film`. The protocol already forbids a broader weight-transfer claim.
`claims_weight_transfer_across_families: false`.

**Provenance.** All six parent hashes match. Config and protocol hashes
match the lock. Seeds `65,000,000+` stay outside closed blocks and the
Cline-draft `64,000,000+` range. Holdout `(0.0027, 0.0009, 0.05)` rejects
default, development, confirmation, rung 1, rung 2 and Cline v3.

**Timeout and incompleteness.** `execute` saves `complete=False`,
`label=incomplete`, the exception, wall time and meter counts if any cap
or error fires. Existing output is refused. Authorization remains
`authorized: false`. A complete grid is required for any non-incomplete
label; no seed dropping.

## Readiness

| Question | Answer |
|---|---|
| Can the locked run be interpreted? | Yes, as occupancy-conditioned FiLM + pretrained shared init versus scratch |
| Does it test residual dynamics codes? | No |
| Is authorization scientifically safe? | Yes, for this exact hash-locked config, under the limits above |
| Must the lock be replaced? | No |
| Collection authorized by this audit? | No |

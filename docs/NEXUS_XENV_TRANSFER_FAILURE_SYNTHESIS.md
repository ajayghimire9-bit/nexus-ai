# Why cross-family representation transfer was not established

Source-only and existing-artifact analysis on
`cursor/xenv-transfer-failure-synthesis` from
`dbeebccc556a01f563dd835519e5a2333ddb0868`. No new environment steps, no
retune, no additional shared-trunk / FiLM / low-budget / target-family
rung. Not learning-to-learn. Not AGI.

Reproduce:

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_transfer_failure_synthesis.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_transfer_failure_synthesis.py
```

## Exact evidence summary

All seven locked primaries are `not_established`. Every primary student-t
95% interval (df 9, n = 10) includes 0. No rung established harm
(`hi < 0`). Rung 5's @128 secondary is **not** a label and did not
replicate as rung 6's primary.

| Rung | Architecture | Target | Primary `xenv−scratch` | @128 | @1024 | MAE @1024 | Prior/env |
|---|---|---|---|---|---|---|---|
| 1 | one 64→64 tanh | MCC (0.0025, 0.0015, 0.09) | **+18.618 [−20.400, +57.636]** | +24.548 | +12.687 | −1.50e-05 | 512 / 44,000 |
| 2 | two 64→64 tanh | MCC (0.0028, 0.0013, 0.065) | **+2.575 [−16.248, +21.399]** | +1.273 | +3.878 | +1.84e-05 | 512 / 44,000 |
| 3 | occupancy FiLM | MCC (0.0027, 0.0009, 0.05) | **−2.300 [−9.921, +5.320]** | −2.584 | −2.016 | +9.03e-06 | 512 / 44,000 |
| 4 | residual FiLM | MCC (0.0019, 0.0013, 0.065) | **−1.819 [−23.729, +20.091]** | +9.441 | −13.079 | +5.36e-05 | 512 / 44,000 |
| 5 | 2× prior, same net | MCC (0.0022, 0.0019, 0.08) | **−4.761 [−36.121, +26.599]** | +23.887† | −33.409 | +6.54e-05‡ | 1024 / 63,200 |
| 6 | 2× prior, 128-only | MCC (0.0016, 0.0011, 0.08) | **+18.453 [−20.207, +57.113]** | +18.453 | +5.567 | +4.98e-05 | 1024 / 63,200 |
| 7 | same net, CartPole | CP (6.5, 0.57, 0.28) | **−2.500 [−10.359, +5.359]** | −0.500 | −4.500 | +3.41e-04‡ | 512 / 38,066 of 44,000 |

† Secondary only; lower bound above 0 on a now-closed holdout.  
‡ MAE gain lower bound above 0: xenv predicted *worse* than scratch.  
MAE sign is `xenv − scratch` (positive = worse prediction). Walls were
16.1–18.5 s on MCC rungs and 10.2 s on CartPole. Imagined transitions
were 3,072,000 except rung 7 (1,552,896) because CartPole episodes ended
early.

`training_epochs_budget: 10` is a recipe label, not a 10-epoch cap. The
locked recipe is 15 pretrain + 2×20 fine-tune + 2×20 reference = **135
epoch-loops / seed**. Optimizer work is bounded by the 600 s cap.

## Architectural bottleneck analysis

### 1. What is actually shared?

Verified from `XEnvNet.forward` and the three later nets:

```
h = tanh(family_in_head(concat(obs_norm, action_onehot)))
h = tanh(shared_64x64(h))          # the only shared dynamics weights on rungs 1,5,6,7
pred = family_state_head(h)        # residual in that family's coordinates
term = family_term_head(h)
next = unnormalize(obs_norm + pred)
```

Rung 2 adds a second shared 64→64. Rungs 3–4 add a mean-pooled 8-d context
and a zero-initialized FiLM affine on `h`.

Parameter inventory on the four-family MCC-target net:

| Net | Total | Shared hidden | Family heads | Context/FiLM |
|---|---:|---:|---:|---:|
| Rung 1 `XEnvNet` | 7,186 | 4,160 | 3,026 | 0 |
| Rung 2 `XEnvDeepNet` | 11,346 | 8,320 | 3,026 | 0 |
| Rung 3 occupancy FiLM | 8,858 | 4,160 | 3,026 | 1,672 |
| Rung 4 residual FiLM | 8,906 | 4,160 | 3,026 | 1,720 |

Family interfaces are incompatible:

| Family | obs | actions | gym id |
|---|---:|---:|---|
| CartPole | 4 | 2 | CartPole-v1 |
| Acrobot | 6 | 3 | Acrobot-v1 |
| MountainCar | 2 | 3 | MountainCar-v0 |
| MountainCarContinuous | 2 | 3 | MountainCarContinuous-v0 |

MountainCar and MCC share dimension 2 and a valley geometry, but not
action semantics (discrete force vs discretized continuous power). They
were already paired as prior→target on rungs 1–6. CartPole and Acrobot
are both underactuated poles with different encodings (raw angle vs two
link cos/sin).

Target-family input and output heads are **never pretrained**. Transfer,
if any, can come only from `shared` (and `ctx_enc`/`film` on rungs 3–4).
The locked flag `claims_weight_transfer_across_families: false` already
recorded that limit.

### 2. Do the sources share dynamical structure the objective could learn?

**Verified:** the training loss is family-native residual MSE on
normalized `s′−s` plus a termination BCE. Each family contributes that
loss through its own heads. There is no shared residual basis, no shared
action embedding across cardinalities, and no physics-parameter readout.

**Plausible:** discrete MountainCar is the nearest prior to MCC. That
pair was present on every MCC-target rung and still failed.

**Untested:** a hand-specified mapping from MCC `(position, velocity)`
into MountainCar coordinates, or a common underactuated-pole residual,
might expose structure this net never saw. That would be a new interface,
not another shared 64-d layer.

### 3. Do family-specific projections block useful shared features?

**Verified:** every transition is immediately projected by a
family-specific matrix before the shared layer. The shared layer never
sees raw `(s, a)`. Deepening the shared stack (rung 2) *shrank* the
point estimate (+18.618 → +2.575) and made the multi-head wrapper trail
the single-family residual reference @1024.

**Plausible:** the shared layer can implement a generic mixer that each
family head inverts, so joint pretraining need not create family-invariant
features. Fine-tune then rewrites that mixer on target data.

**Untested:** a frozen shared layer with only target heads trained. The
locked protocol always fine-tunes `net.parameters()`, including `shared`.

### 4. What do context vectors encode?

**Verified (source audit + code):**

- Rung 3 `z` is mean-pooled occupancy of `(obs, action)` after the
  family-specific projection. It never reads `next_obs` or `s′−s`.
- At target freeze time the MCC projection is untrained, so target `z`
  is occupancy in a shifted embedding.
- During fine-tune, target `z` is detached. FiLM is then a constant
  affine, not a per-transition conditioner.
- `nearest_source_ratio` (rung 3 mean 0.612; rung 4 ≈ 0.60) is computed
  **after** fine-tune and is not the frozen code that conditioned
  control. It is not label-deciding and does not establish
  identification versus adaptation.

Rung 4 may read padded `s′−s` (pad width 6). Residual dimension 0 still
means different physical quantities across families. That rung also
failed.

### 5. Do prediction improvements correlate with control improvements?

**Verified:** no primary was accompanied by a prediction gain that
established control. Exploratory n=10 correlations between per-seed
return gain and MAE gain are small on MCC rungs (range about −0.63 to
+0.36) and are **not** a preregistered label. Rung 2 @128 MAE gain
lower bound is above 0 (xenv *worse* at prediction) while the control
primary includes 0. Rungs 5 and 7 @1024 MAE lower bounds are also
above 0.

**Plausible:** H=16 control is insensitive to the MAE differences
observed here (order 1e-5 to 3e-4).

**Untested:** a decision-aware or ranking loss on the same data.

### 6. Negative transfer or undertraining?

**Verified:** no primary established harm. 2× source data (rungs 5–6)
did not establish transfer, so starvation at 2× is not supported. A 5×
scale still exceeds the 100,000 standing cap and was not run. Walls of
10–19 s against a 600 s cap show unused compute, not an exhausted
optimizer budget.

**Plausible:** 20 fine-tune epochs at 5e-4 overwrite the pretrained
shared matrix, and 1024 target transitions are already enough for
scratch to match. That is an adaptation-protocol hypothesis, not a
result.

**Not established:** that pretraining was harmful. Intervals include 0.

### 7. Did the target protocol give pretraining a fair chance?

**Verified and fair as a test of pretrained initialization:** xenv and
scratch share architecture, seeds, prefixes, RMS, fine-tune epochs, and
H=16 evaluation. Only source pretraining differs.

**Verified and not a test of feature reuse:** target heads start random
on both arms; the shared layer is trainable during fine-tune; there is
no frozen-trunk, head-only, or shorter fine-tune arm.

So the protocol is a fair matched-scratch screen and a weak test of
whether the shared layer *contains* transferable features.

### 8. Did ceilings or control sensitivity hide differences?

**Verified:** on rung 7 @1024, 9/10 xenv and 9/10 scratch episodes hit
the 200-step cap. That ceiling can hide a transfer gain and is not
itself a gain. @128 both arms fail immediately (means 12.2 vs 12.7).
MCC rungs have no analogous hard cap at 0; their intervals are wide
because episode returns are noisy (rung 6 seed 4 = +167.575).

**Plausible:** MCC H=16 return is a high-variance functional of small
residual errors, so n=10 cannot resolve a small real effect.

**Not a license to retune** any closed holdout or to promote the
unreplicated @128 secondary.

## Evidence versus hypothesis

**Verified evidence**

- Seven complete, audited, hash-locked rungs; all primaries include 0.
- Shared weights are a 64-d hidden matrix (or two) after family-specific
  embeddings; target heads are untrained at pretrain time.
- Occupancy FiLM cannot recover `T(s'|s,a)`; residual FiLM still failed.
- 2× prior data and a second target family both failed as primaries.
- Rung 5 @128 secondary did not replicate on unused physics.
- CartPole @1024 is ceilinged for both shared-trunk arms.
- Independently, V0.6.6 showed CartPole *source observation RMS*
  transfers with a random net (**B−A +222.4 [173.0, 271.7]**), while a
  pretrained encoder given that RMS hurt (**D−B −223.1 [−294.0, −152.3]**).
- Independently, MCC / discrete MountainCar / Acrobot lookahead
  transferred with **separately trained family models**, not shared
  trunks.

**Plausible mechanisms (not results)**

- There is no common dynamical coordinate, so a shared hidden layer has
  nothing invariant to represent.
- Fine-tune erases whatever the shared layer stored.
- Scratch already saturates the H=16 metric at 1024 target transitions.
- Context vectors are occupancy or post-hoc identification codes.

**Untested hypotheses**

- Frozen-trunk, head-only target adaptation.
- A specified cross-family state map.
- 5× source data (over the standing interaction cap).
- Decision-aware losses.
- Family-native RMS / residual-scale adaptation on MCC (the recommended
  next direction).

Do **not** read this file as established harm, as a successful
mechanism, or as permission to reopen closed splits.

## Single most fundamental bottleneck

**The shared object was the wrong scientific unit.** A hidden-layer
weight matrix between incompatible embeddings cannot carry family-native
residuals. Seven rungs varied depth, context, source volume, scarce-target
scoring, and target family without creating a shared dynamical
coordinate. That is a supported interpretation of architecture plus
closed primaries plus the V0.6.6 RMS result. It is not a new trained
label.

## One next conceptual direction

**Family-native interface adaptation.** Estimate a quantity that lives
in the target family's own coordinates — observation RMS, residual
scale, or a low-dimensional same-family physics code — and apply it to a
family-local residual world model. Do not share hidden weights across
CartPole, Acrobot, MountainCar, and MountainCarContinuous.

This is not another shared-trunk, FiLM, low-budget, or target-family
xenv variant. It asks whether the object that already transferred inside
CartPole (interface statistics) generalizes to MountainCarContinuous,
where lookahead already works with family-local models.

**Falsifier.** On unused same-family MCC physics that is not a closed
xenv holdout, a family-native RMS or residual-scale adapter at budget
128 fails `adapter − scratch` mean > 0 and CI lower bound > 0.

**Minimal future experiment (not authorized here).** Lock a
within-family MCC residual world model. Treatment: source-MCC
observation RMS or a 1–3d residual-scale inferred from support `s′−s`
in MCC coordinates only. Control: matched scratch with fresh RMS.
Primary: 128-transition H=16 return, ten seeds, student-t 95%, `lo > 0`.
New unused physics. Caps ≤600 s / ≤44,000 / local CPU. No cross-family
weights. Collection requires its own protocol, hashes, and one-run
allocation.

Session ledger is unchanged by this synthesis: 268.351 s of 3600 s
consumed; 3331.649 s remain.

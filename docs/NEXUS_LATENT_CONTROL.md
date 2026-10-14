# Context-conditioned MPC

Starting SHA `24d9b38fb05d294ac4475613694cbb4153344ef3`. Config: `configs/latent_control.yaml`. The runner rejects a drifted file.

The prediction confirmation already passed. This asks whether that same epoch-200 encoder improves H=16 model-predictive control on those four physics. The physics are not a new confirmation set.

Not AGI. Not learning-to-learn. A higher return is not retuned into a new encoder.

## Frozen controller

Pendulum uses the published reward and the three torques. The planner is the existing random-shooting controller: horizon **16**, **16** candidate sequences, chunk size 4. The time budget is off, which is the existing pendulum path, so every controller scores all 16 sequences. The decoder, normalization, and epoch-200 encoder weights stay frozen. Support is the same 128-row confirmation support. Context is inferred once before the episode and is not updated during control.

## Checkpoints

The runner loads the 15 broad students and 15 eight-task baselines named in `artifacts/latent_generalization_confirmation.json` (sha256 `18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa`). Each file hash must match. A present file with the wrong hash is not overwritten. A missing file is retrained with the locked procedure and kept only when the new hash matches the record.

The three multitask MLP checkpoints are an external reference. They are not a decoder replication.

## Evaluation

Control episodes use env seeds starting at **110000**, four episodes per task. Those seeds are disjoint from the support seeds. Every controller sees the same resets and the same planner seeds.

The comparisons on each frozen decoder are the broad student, zero context, the global vector, the original encoder, the eight-task student, and the direct teacher fit on that support. The teacher is a fitted latent, not an oracle controller.

The primary number is episodic return. The five student seeds are averaged inside each decoder, together with the four tasks and the four episodes. The interval is a Student-t interval on the three decoder differences. A difference is student return minus the control return.

The screen passes only when the student beats both zero context and the frozen encoder by at least **25** return points, and both intervals have a lower bound above 0. An interval that includes 0 is inconclusive even when the mean is positive. Global context, the eight-task baseline, and the teacher are reported. An episode at or below **-1500** is counted as catastrophic.

No return is used to change the horizon, the encoder, or the teacher rule.

<!-- protocol-lock
confirm_split_hash: baa655fcb94e61bc
confirmation_artifact_sha256: 18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa
horizon: 16
n_candidates: 16
support_budget: 128
episodes: 4
confirmation_epoch: 200
n_decoder_seeds: 3
n_student_seeds: 5
n_parameters: 584
n_decoder_parameters: 3748
minimum_effect: 25
catastrophic_return: -1500
control_eval_env0: 110000
primary_unit: decoder
-->

## If the screen fails

The same episodes are not reused for a retune.

If either primary interval includes 0 while a mean is positive, the result is inconclusive.

If both intervals lie above 0 but a mean is below 25, the effect is below the locked margin.

If the teacher clears the margin and the student does not, the remaining gap is the inferred latent.

If neither the student nor the teacher beats zero context, the next question is the planner.

Otherwise the prediction gain did not become a return gain.

## If the screen passes

The context rule stays a candidate for a later control test on physics that were not used here. This run does not start that test.

## Results

Implementation SHA `9506604ba1aae853d8be3421d87b9e9477a9b5a4`. The source tree was clean. Artifact `artifacts/latent_control.json`, sha256 `ce04ce90f368a6d0ecd45b42cce881e045619fd642bfe39d13c8c32216c5e9b4`. Wall clock **569.5 s**. The grid was complete (180 of 180 cells). Checkpoint hashes matched before any return. Not AGI and not learning-to-learn.

Mean return, higher is better:

| Controller | Return |
| --- | ---: |
| Direct teacher | **−682.4** |
| Broad student | **−683.0** |
| Eight-task baseline | −717.2 |
| Global vector | −760.7 |
| Multitask MLP | −771.1 |
| Zero context | −768.4 |
| Frozen encoder | −773.2 |

Paired student minus control, three decoders, df = 2. Positive means the student return is higher. The locked margin is 25, and a lower bound of 0 fails.

- Zero **+85.4 [−109.4, +280.3]**
- Frozen encoder **+90.2 [−5.7, +186.1]**
- Global **+77.8 [−68.9, +224.4]**
- Eight-task baseline **+34.2 [−78.6, +147.0]**
- Direct teacher **−0.6 [−121.7, +120.5]**

Every primary interval includes 0. The screen does not pass. The result is **inconclusive**. The point estimates sit above the 25-point margin, and that is not enough under the locked rule.

Per decoder, student versus zero versus encoder versus global versus teacher:

- Decoder 0: **−636.7** / −804.0 / −718.3 / −769.8 / −685.9
- Decoder 1: **−731.7** / −742.7 / −788.4 / −747.3 / −683.5
- Decoder 2: **−680.5** / −758.4 / −812.9 / −765.1 / −677.7

Decoder 1 is only **+11.0** above zero context. That spread is why the interval crosses 0.

Per task, student versus zero versus encoder versus global versus teacher versus baseline:

- `pendulum_lat_cf0` (5.1, 0.88, 0.96): **−82.3** / −122.2 / −85.2 / −96.6 / −93.7 / −94.1
- `pendulum_lat_cf1` (15.8, 0.92, 1.04): **−1061.7** / −1246.6 / −1244.8 / −1257.3 / −1085.0 / −1182.1
- `pendulum_lat_cf2` (10.4, 2.45, 0.58): **−1283.9** / −1339.6 / −1353.0 / −1357.8 / −1293.2 / −1307.1
- `pendulum_lat_cf3` (11.4, 0.48, 1.82): **−304.0** / −365.2 / −409.8 / −331.1 / −257.5 / −285.5

All four task means are above zero context, the frozen encoder, and the global vector. The low-gravity task is close to the frozen encoder (**−82.3** versus **−85.2**). The high-gravity and heavy-mass tasks remain below **−1000**. The eight-task baseline is higher than the student on `pendulum_lat_cf3`.

No episode reached the locked catastrophic line of **−1500**. The worst student episode was **−1449.8**. The rate under that rule is **0** for every controller.

The 16-step imagined score is about **−47 to −51** for every controller. Full-episode return sits near **−680 to −770**. The short imagined score does not separate the controllers. At the shared episode reset, the student and zero context chose the same first action on **72.1%** of paired episodes.

A plan step averaged **3.93 ms**. Encoder inference averaged **0.12 ms**. A teacher fit averaged **0.136 s**. The encoder is **584** parameters (2336 bytes) and the decoder is **3748** parameters (14992 bytes). The MLP reference is **4868** parameters. Support collection was **512** transitions. Control used **144,000** transitions. Imagined model states were **36,864,000**.

These episode seeds stay closed. The encoder and the teacher rule are not retuned from this return.

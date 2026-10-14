# Latent encoder generalization

Starting SHA `cc0341c3df6a3fc6e0127b068258c5f805280450`. Config: `configs/latent_generalization.yaml`. The runner rejects a drifted file.

This asks whether the existing mean-pooling encoder can infer a useful latent on Pendulum physics it was not trained on. Memorizing eight teacher vectors is not that result. A lower training distance is not that result.

Not AGI. Not learning-to-learn. No MPC. Hash `87b83c41be34aa1a` and hash `d1fa621351d286cf` stay closed.

## Frozen pieces

The three history decoders stay frozen, including FiLM, the trunk, both heads, and normalization. The latent is eight-dimensional. The encoder stays the checkpoint encoder: width 32, mean pooling, 584 parameters. The teacher rule stays Adam learning rate 0.1 for 256 updates, from the stored global vector, on 128 support transitions. The student learning rate is **0.01**.

## Splits

Training physics are the twelve-point grid with gravity in {7.3, 8.7, 13.2}, mass in {0.65, 1.05}, and length in {0.78, 1.22}. Split hash `a3e558f2eeea1298`.

Validation physics are four further tuples, hash `601715664052382b`. They are scored only after the checkpoint is chosen. They do not choose it.

Development physics are the existing three context-development tasks, hash `e3d6d6dd1a08cf4f`. The support and query rows are the same episodes as the amortized development run. Their hashes are locked in the config.

Each training physics gets two independent 128-row supports. Each support gets its own teacher. The student is trained on that support and that teacher. A teacher from the other support is not reused.

A third support of each training physics is held out. Its teacher is a history-generalization diagnostic. It does not train the student and it does not choose the checkpoint.

The eight original source tasks, with their saved teachers, are the distillation baseline. They are retrained at learning rate 0.01 for the same number of passes.

## Training and the screen

One epoch is one pass over the pairs in seed order. Each step is the mean squared error on one pair. Checkpoints are epochs **40, 100, and 200**. The broad student's checkpoint is the lowest mean development angular-velocity error. Ties prefer the earlier epoch. The baseline is reported at that same epoch.

Five student seeds share the three frozen decoders. The interval uses the student seed after averaging decoders and development tasks. Those seeds are not three independent world models.

The screen passes only when that student is strictly below zero context and strictly below the frozen encoder. The global vector, the direct teacher, and the eight-task baseline are reported on the same query rows. Validation must also beat zero context and the frozen encoder before a later confirmation is recommended. This branch does not collect confirmation physics either way.

<!-- protocol-lock
train_split_hash: a3e558f2eeea1298
val_split_hash: 601715664052382b
dev_split_hash: e3d6d6dd1a08cf4f
forbidden_confirm_hash: 87b83c41be34aa1a
amort_confirm_hash: d1fa621351d286cf
teacher_lr: 0.1
teacher_updates: 256
student_lr: 0.01
epochs: 40,100,200
n_student_seeds: 5
n_train_supports: 2
support_budget: 128
mean_fit_l2: 0.25
history_fail_l2: 0.5
n_parameters: 584
broad_h0_env0: 96000
dev_support_env0: 74000
dev_query_env0: 76000
-->

## If the screen fails

The diagnosis uses the chosen checkpoint.

If the mean training distance is above 0.25 and the two teachers of the same physics have median distance above 0.5, the labels disagree across histories. No architecture change.

If the training distance is above 0.25 and those teachers agree, the step budget did not fit the broader set. No architecture change.

If the training distance is at most 0.25 and the held-out history distance is above 0.5, the one change is a learned attention pool over the same 32-unit features, still writing eight numbers. No GRU, Transformer, ensemble, or search.

If the training and history distances are both small and development prediction still loses, the next change is a broader set of source tasks, not a new encoder.

A development pass that fails the validation physics does not open a confirmation.

## Results

Implementation SHA `fd1e864cb2e1dff91e73bf35b184becc4c81be22`. The source tree was clean. Artifact `artifacts/latent_generalization_dev.json`, sha256 `c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba`. Wall clock **51.2 s**. The development schema was complete (450 of 450 cells). Confirmation physics were not collected. No control sweep. Not AGI and not learning-to-learn.

The checkpoint is epoch **200**, the lowest development angular-velocity error among epochs 40, 100, and 200 (**0.1513, 0.0988, 0.0913**). Horizon 16 was slightly lower at epoch 100 (**0.367**) than at epoch 200 (**0.380**). The selection rule uses one-step angular velocity, so epoch 200 stays selected.

Development angular velocity, same query rows:

| Condition | Angular velocity | Overall MAE | Latent L2 | Open-loop 3 / 8 / 16 |
| --- | ---: | ---: | ---: | --- |
| Broad student | **0.0913** | 0.0364 | 1.273 | 0.089 / 0.201 / 0.380 |
| Direct teacher | 0.0781 | 0.0322 | 0 | 0.081 / 0.183 / 0.346 |
| Global vector | 0.1478 | 0.0534 | 2.753 | 0.155 / 0.359 / 0.582 |
| Zero context | 0.1587 | 0.0570 | 3.014 | 0.164 / 0.380 / 0.618 |
| Eight-task baseline | 0.1672 | 0.0619 | 3.183 | 0.183 / 0.434 / 0.681 |
| Frozen encoder | 0.1773 | 0.0640 | 2.888 | 0.185 / 0.431 / 0.683 |

The five student seeds, after averaging the three decoders and the three development tasks, are **0.0859, 0.0902, 0.0926, 0.0929, and 0.0946**. The Student-t interval is **0.0913 [0.0871, 0.0955]**, df = 4. Those seeds share the decoders. They are not three independent world models.

Paired control minus student, same unit, positive when the student is lower. Every interval excludes 0:

- Zero **+0.0675 [+0.0633, +0.0717]**
- Frozen encoder **+0.0861 [+0.0819, +0.0903]**
- Global **+0.0565 [+0.0523, +0.0607]**
- Eight-task baseline **+0.0760 [+0.0691, +0.0828]**
- Direct teacher **−0.0131 [−0.0173, −0.0089]**

The recovery fraction against the global-to-teacher gap is **0.812**. The denominator is 0.0697, above 5% of the global error. The pre-registered screen passes: the student is below zero context and below the frozen encoder. It remains above the direct teacher.

Cosine and sine MAE are **0.0076** and **0.0104**, against zero **0.0059** and **0.0063** and the teacher **0.0077** and **0.0108**. The angular-velocity gain is where the teacher is better. The angle components follow the teacher and stay above zero context.

Per development task, student versus zero versus teacher:

- `pendulum_ctx_dev0` (g=6, m=1, l=1): **0.0920** versus 0.1654 versus 0.0733
- `pendulum_ctx_dev1` (g=10, m=2, l=1): **0.1046** versus 0.1100 versus 0.0952
- `pendulum_ctx_dev2` (g=10, m=1, l=1.55): **0.0772** versus 0.2008 versus 0.0659

Per frozen decoder, student versus zero versus encoder versus teacher: decoder 0 **0.0912 / 0.1533 / 0.2070 / 0.0805**; decoder 1 **0.0908 / 0.1567 / 0.1867 / 0.0770**; decoder 2 **0.0918 / 0.1663 / 0.1383 / 0.0769**.

The student did not reproduce the teacher codes. Mean training latent distance at epoch 200 is **0.648**, above the 0.25 fit bar from the representability check. Development latent distance is **1.273**. A third support of each training physics, scored after selection, has mean latent distance **1.752**. The two training supports of the same physics have median teacher-to-teacher distance **1.522** (mean 2.13, range 0.23 to 7.93). Of 36 pairs, 34 are farther than 0.5, and 10 of those also have both cross-support relative loss gaps under 0.10. The median of the larger gap is **0.285**. History generalization of the teacher vector failed. Physics-query prediction still improved.

Validation was scored after selection and did not choose the epoch. Mean angular velocity is **0.0832** versus zero **0.0972**, the frozen encoder **0.0951**, global **0.0959**, the eight-task baseline **0.0898**, and the teacher **0.0720**. Latent distance is **1.349**. Open-loop means are **0.081 / 0.201 / 0.318**, against zero **0.101 / 0.231 / 0.352** and the frozen encoder **0.087 / 0.187 / 0.294**. The one-step mean passes. Horizons 8 and 16 on validation do not beat the frozen encoder. The five student-seed means are **0.0815 to 0.0849**, all below the validation zero mean.

Validation is not uniform:

- `pendulum_lat_va0`: student **0.0397**, zero 0.0799, encoder 0.0740, teacher 0.0271
- `pendulum_lat_va1`: student **0.0637**, zero 0.1055, encoder 0.1139, teacher 0.0569
- `pendulum_lat_va2`: student **0.0803**, zero 0.0903, encoder **0.0708**, teacher 0.0640
- `pendulum_lat_va3`: student **0.1491**, zero **0.1129**, encoder **0.1215**, teacher **0.1399**

On `pendulum_lat_va3` the locked teacher itself is worse than zero context, and the student follows it. On `pendulum_lat_va2` the student beats zero and loses to the frozen encoder.

Source interactions: baseline support 1024, broad supports 3072, history supports 1536, validation support 512, validation query 3200, development support 384, development query 2400. Teacher Adam steps **30720**. Student Adam steps **96000**. The encoder stays at **584** parameters. A student forward pass averaged **1.4 ms**. One decoder's teacher fits took **4.35, 4.63, and 3.94 s** for its 40 supports.

The locked recommendation is a separate confirmation on newly registered physics. Hashes `87b83c41be34aa1a` and `d1fa621351d286cf` stay closed. This artifact does not store the trained encoder; a confirmation retrains from the locked seeds before any new physics are scored. The failure branches (label variability, more updates, an attention pool, more source tasks) are not the next change, because the development and validation means both passed. An attention pool is not justified by a passed prediction screen. This is not a control result.

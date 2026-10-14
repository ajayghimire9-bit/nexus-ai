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

The development run has not been started in the implementation commit.

# Source-only update-magnitude diagnosis

Starting revision: e40539059c7076762d0699bde7998996ae8b328f.
Branch: codex/seed-update-magnitude-diagnosis. Exploratory development analysis;
the previous nonlinear-feature study remains closed and FAILED.

Question: does the first protected residual correction move too far relative
to scaled replay on the original permitted source-training tasks? Competing
explanations include excessive interpolation of one teaching row, preservation
constraints, or insufficient transferable information in the frozen features.
This observational diagnosis cannot establish which explanation is causal.

## Locked inputs and computation

Use only the 12 saved TRAIN tasks, stored source-only scale, and saved learned
and static controllers for seeds 6401/6402/6403 from the hash-verified prior
artifact. The trusted host extracts these fields BEFORE dispatch; no development,
audit or control data enter the worker API. Source query and retention arrays
are reused training evidence, not fresh validation. No fitting, new labels,
environment construction, world-model inference or checkpoint replacement.
The 576 tiny frozen-controller evaluations are counted separately; they do not
execute the world model or generate imagined transitions.

Reuse LessonTask, initial, update and scaled from learning_benchmark and the
existing PlasticityController/correction. Restore original float32 weights;
freeze them. Compare learned, static, fixed, scaled replay and none without
changing their equations, schedules or hyperparameters. Store every prefix 0–8.
Record update L2 norm, support prediction before/after, fraction of the observed
residual corrected (undefined at zero residual), query MSE and old-task MSE.
Report parameter changes as exactly zero; adaptation vectors are disposable.

The executable configuration is configs/seed_update_diagnosis.json. Expected
grid: 3 controller seeds × 12 source tasks × 5 methods × 9 prefix snapshots.
All numeric required fields must be finite, all theta vectors width 33, and
all planned cells present. Reject missing/duplicate cells and altered inputs.

## Predeclared descriptive screen

Average controller seeds within each source task. Record the median of taskwise
first-update learned/replay norm ratios, and the number of tasks on which the
first learned update increases source query MSE over its own prefix-zero fit.
Label `large_first_update_pattern` only if the median ratio exceeds 2 and at
least 8 of 12 tasks are harmed. Otherwise label `pattern_not_supported`.
Zero replay-norm denominators are explicitly undefined and prevent a complete
ratio screen. These thresholds are diagnostic, not a new learning-success rule.

Also report all prefix curves, support fit versus query error, retention and
paired learned/replay differences across the 12 task means. Exploratory 95%
Student-t intervals use df11 and are conditional on this reused training bank
and ONE frozen core. Three optimizer-order seeds are not three independent
world models. No control, transfer or learning-to-learn claim is possible.

## Limits, execution and evidence

Standing human grant, no increase: CPU only, 30-second host wall/CPU caps,
2048 MiB sampled-RSS cap (macOS sampling limitation remains), zero real steps,
zero imagined transitions, zero outer optimizer updates. Maximum 1440 inner
update calls, including no-op controls; at most 1152 active corrections. Reuse
the EXPERIMENTAL host's durable reservation, consumed-run guard, process limits,
journal and accounting. No parallel execution. Carry ledger 1916.6321034559958
used / 1683.3678965440042 remaining, including failures and startup.

Commit this protocol, configuration, adapter and tests before execution. Run
once, save honest partial/invalid results on failure and never silently shrink
the grid. Preserve old artifact bytes and network weights. Commit results and
one evidence-grounded next question separately; do not start a second study.

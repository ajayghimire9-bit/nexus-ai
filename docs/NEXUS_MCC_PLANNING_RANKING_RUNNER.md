# MCC same-state planning-ranking diagnostic — runner implementation

Implementation branch `cursor/mcc-planning-ranking-runner` from locked
prep `b75417ac16c23316426b0ea7f2b877d1f24dbe50`. The scientific design
in `NEXUS_MCC_PLANNING_RANKING_PROTOCOL.md` is unchanged. Collection
remains unauthorized (`authorized: false`, `runs: 0`).

The prep stub that always raised after `require_allocation` is replaced
by an executable runner. That runner still refuses until a later one-run
allocation. This document is not a result.

## Locked objects preserved

- Config hash `17a48088591e8c9316f5b6bffd7cefac48ea2daf158cac98555204b47546feb6`
- Protocol hash `6acea6f51bdc8ec0ce0f72ce08996f38a333e2e68f854b8fb6c77e218a57148b`
- Physics `(0.0027, 0.0015, 0.075)`, seeds `74,000,000+`, 4 states,
  16×16 candidates, H10 train recipe, caps **300 s / 28,480 / 348,160**

## Execution contract (not collected)

1. Restore every candidate by `env.reset(seed=state_seed)` and match `obs0`.
2. Score both arms from `obs0` before any ground-truth rollout.
3. Planners receive predicted scores only; realized returns are not arguments.
4. Shared open-loop returns are the ground truth for sequence regret.
5. First-action regret is secondary and can differ from sequence regret.
6. Receding 16-step control is stored separately and is not label-deciding.
7. `Meter.env_step` / imagined instrumentation raise when a cap would be exceeded.
8. Reset mismatch, cap failure, or a missing seed labels `incomplete`.

No training, collection, or evaluation was run on this implementation
branch. Not learning-to-learn, not AGI.

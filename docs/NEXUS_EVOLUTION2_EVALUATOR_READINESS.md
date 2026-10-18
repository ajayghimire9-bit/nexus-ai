# Evolution-2.10 — evaluator readiness, development only

Branch `cursor/evolution2.10-evaluator-readiness` from
`b9d0b2ed75665ee9dbe3805eeffe5de0b93aef0f`.
Not a scientific result. No collection. No new fits. No holdout named.
H17 blocked. v2 hashes unchanged. Evolution-3 not started.

Reused: `TrustedEvaluator`, `ReservationLedger`, Evolution-1 catalogue /
`plan_bound`, and `evolution2.planner_adapter`. No second planner,
proposer, or memory was added.

## 1. Six-fit observation

Exactly six disposable residual fits exist. Wall 1.215 s, CPU 0.974 s,
0 env steps. Source-array and disposable-weight hashes match the E2.9
lock. A second write still raises `duplicate_or_partial_fit_clock`.
Twenty-fit / n=10 cost is **not measured**. Do not write 6 × (20/6).

E2.9 is already on GitHub and Origin at `b9d0b2e`. Disposable
checkpoints were not re-uploaded.

## 2. Balanced-generator binding

The six `balanced_first_action` variants are bound to
`planner_adapter.generate_candidates`. Host
`operator_fingerprint` / `bind_evaluation` / `validate_public_payload`
accept the full catalogue for **development**. Scientific dispatch
stays `BLOCKED` (`scientific_dispatch_unauthorized_holdout_unnamed`).
`BoundEvaluation.require_scientific()` still fails closed.

## 3. Development dry-run

Twelve planner configurations × Pendulum/Acrobot used locked family-
default observations and disposable bundle0 copies. No Gymnasium, no
fresh steps, no training, no holdout evaluation. TrustedEvaluator owns
scores. ReservationLedger charges physical model work and cached
replays separately. Interrupted settlement leaves unresolved keys.
Action indices decode through the reviewed family binding.

## 4. Distinct ledgers

| record | consumed | env steps | H16 file |
|---|---|---|---|
| H16 scientific (`ff4c51e2…`) | 305.842 / 3294.158 | — | frozen |
| residual-timing probe usage | 0.777 s wall | 0 | not rewritten |
| 7680 persist usage | 0.156 s | 7680 | untouched |
| six-fit clock usage | 1.215 s | 0 | untouched |

These are not one ledger. This milestone does not debit or reset them.

## 5. Readiness matrix

| gate | status |
|---|---|
| six-fit clock observed | PASS |
| twenty-fit v2 clock | UNAVAILABLE |
| source-array / disposable hashes | PASS |
| twelve-arm development binding | PASS |
| TrustedEvaluator / ReservationLedger | PASS |
| worker CPU enforcement | BLOCKED |
| OS/filesystem sandbox | BLOCKED |
| holdout named | BLOCKED |
| H17 | blocked |
| scientific authorization | BLOCKED |

## 6. Smallest complete scientific experiment

n=3 persist versus reset, with equal-budget random and evolution
controls, on a **newly named unused holdout**, independent decoder
replication, and a distinct confirmation split. The six-fit clock is a
cost prior only. Occupied family defaults are not that holdout.
Disposable source weights are not confirmation residuals. That
experiment is **not authorized** here.

## Next action

Do not name a holdout on this branch. The next authorized scientific
step is a separate n=3 persist-versus-reset protocol that cites a named
unused holdout and does not invent a twenty-fit cost.

# Evolution-2.12 — persist-versus-reset development dry-run

Branch `cursor/evolution2.12-persist-reset-dry-run` from
`8404151b05caec95464161207952fda9bce8f5f7`.
Status: **DEVELOPMENT DRY-RUN — SCIENCE BLOCKED**.
Does **not** rewrite the locked E2.11 request hashes. Does **not**
collect. Does **not** name a holdout. Does **not** start Evolution-3.

This runner makes the n=3 persist-versus-reset wiring executable on
synthetic development fixtures. It is not a scientific result and does
not become science if authorization flags are flipped.

H17 blocked. H16 ledger **305.842 / 3294.158**.

## 1. Audit of the locked E2.11 request

Cited config SHA256
`8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`
matches `configs/evolution2_persist_reset_request.yaml`.
`authorized: false`, `env_cap: 0`, `hold_named: false`.

Findings, addressed without bypass:

1. `persist_reset_request.dispatch()` is a refusal stub. After
   `require_named_holdout()` and the authorization predicate it still
   raises `persist_versus_reset_not_implemented_while_unauthorized`.
   The development dry-run is a **separate** function. Flag-flips do
   not create a scientific runner.
2. Scientific `require_named_holdout()` still delegates to the blocked
   historical holdout gate. The dry-run never calls it. Development
   fixtures are checked locally and are not a holdout.
3. The request retains the five-comparison Bonferroni threshold
   (`t = 9.924843200918293`, df=2) although only three controls are
   listed (reset, random, evolution). That conservatism is
   **intentional**. Locked yaml / protocol / allocation hashes are
   unchanged.
4. Persist, reset, random, and evolution receive identical proposal
   budgets (`PROPOSALS=4` per task), the same `TrainingFeedback` type,
   the same shared-probe anchors, and the same development evaluation
   slots (`eval_clone`, no global update).

## 2. What this dry-run executes

Reuse only: `evolution2.methods`, `screen` proposal contracts,
`TrustedEvaluator`, `ReservationLedger`, catalogue / `planner_adapter`,
and synthetic `tasks` train+development fixtures.

- n=3 train families, instance 0, plus one development task.
- Hidden scores owned by `TrustedEvaluator`. Callers cannot substitute.
- Physical catalogue warmup (12 arms × 4 tasks) then cached method
  lookups. Ledger physical 48 model calls; logical 112 imagined
  transitions.
- Cross-task persistence, genuine reset, independent random seeds,
  one-coordinate evolution, illegal crossover, checkpoint identity,
  interrupt settlement.
- Twelve-arm **development** binding via `FakeStepModel` + `decide`.
  `twelve_arm_scientific_dispatch` stays **BLOCKED**.

## 3. What this dry-run does not do

- No Gymnasium, `collect_transitions`, new fits, or holdout selection.
- No confirmation outcomes and no scientific ledger debit.
- No enablement of `dispatch()`.
- No Evolution-3.

## 4. Remaining conditions before separate scientific authorization

1. Human approval that cites config `8e90b74a…`.
2. A named unused holdout that matches the locked four-role digests.
   Occupied defaults `(10,1,1)` and `(1,1,1)` are not that holdout.
3. A positive `env_cap` (legal 7,680 for n=3).
4. A real scientific runner. The current `dispatch()` stub is not that
   runner. Do not treat this dry-run as the missing runner.
5. Twenty-fit / n=10 cost remains unmeasured. Do not invent it.
6. H17 stays blocked. `continue` is not approval.

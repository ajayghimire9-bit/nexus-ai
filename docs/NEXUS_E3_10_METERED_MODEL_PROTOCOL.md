# E3.10 — Metered frozen-world-model evidence integration

Starting SHA: `9c16f7c1be8a27a40af280d3b0aaae0afbb34506`, verified on GitHub.
Branch: `codex/e3-10-metered-model-integration`. Preserve unrelated untracked
Evolution-1 adapter files. This is a bounded engineering inference check under
the human standing local grant (2026-10-16), not fresh control evaluation.

## Fixed scope and criteria

Use only the four E3.9 hash-verified Pendulum/Acrobot bundle0/1 frozen residual
MLPs, original normalization and the first two observations of their original
training arrays. Two IID candidate sets per observation, each16×H16, generated
from the committed seed63107 plus model/observation/set offsets. Candidate RNG
is isolated. These are arbitrary common test inputs, not optimized strategies
or new environment/holdout seeds. Do not inspect closed return banks.

Compare common-scoring `planner_evidence` with `planner_adapter.score_open_loop`
on exactly identical candidates/model/observation/reward. Both paths use the
same existing scorer. This tests instrumentation equivalence, not correctness
of learned physics. Independently recompute each cumulative score from saved
states, actions, family reward, termination probabilities and cumulative
survival; use existing family reward implementation, not a new reward rule.

Require every8 model×observation cell and both conditions: finite scores,
identical candidate actions, selected indices and stable full rankings;
scores absolute tolerance1e-9, relative0; state/termination arrays exactly
identical. Fingerprint network state including buffers and context, RMS fields,
and original checkpoint/source file bytes before/after. No model fitting,
weight/context/normalization updates or environment construction. Histories
must not be treated as empirical returns or training feedback.

## Instrumentation and reuse

Keep `AdvantagePredictor`, `StrategyGenerator`, `StagedStudy`, `WorldModel`,
`score_open_loop`, `RandomShootingMPC._score_batch` and `ReservationLedger`.
Extend existing evidence adapter with `ForwardCheckedStep`. The trusted host
accepts exact CPU WorldModel/DynamicsMLP residual `arch=mlp` only: no GRU,
ensemble, simulator model or architecture fallback. Hook top-level net calls
inside each reserved step, require exactly one, reject a second before its
body runs. Hooks are always removed. This counts network invocations, not
Linear-layer operations, FLOPs or all possible hostile Python work.

All evidence and direct-reference calls reserve through the existing ledger
before dispatch. Verify input-row/call/forward totals against observed hooks.
Failed work is charged as unknown upper-bound, never free. Reference calls
are additional executed work, not cached or uncharged truth. Candidate array
generation and hashing time are included in elapsed time; they have zero
neural forward or imagined-transition cost. Model loading has no forward
calls. Do not use Model.load initialization as additional training.

## Caps, provenance and stopping

4 models ×2 observations ×2 candidate sets ×16 steps ×16 rows ×2 paths =
**8192 imagined transitions /512 model calls /512 top-level forwards**.
**0 real interactions**,0 optimization updates. One run only, cap30 wall
seconds (also below standing CPU/session allowances). Launch an isolated
local CPU child with a parent timeout; CPU/thread limits fixed to1. Include
startup, imports, file loading and failed/interrupted time in wall accounting.
Write exclusive usage before launch and partial results after each complete
cell. On timeout/error preserve partial results and report incomplete/invalid;
never reduce the grid, retry automatically or silently reconstruct models.

Commit this protocol, exact config/allocation and tested implementation before
launch. Require a clean tracked tree, matching source evidence/config/protocol
hashes and matching carried ledger. Record execution SHA, relevant code hashes,
dependencies, per-cell resource receipts, raw forecasts, independent reward
reconstruction, observed counts, exact commands and elapsed time. Verify all
prior JSON artifacts unchanged. Save results separately and push; no merge.
The carried ledger begins786.2472080430296 used/2813.75279195697 remaining.

Pass means **engineering integration verified**, not useful selection, control
improvement or learning-to-learn. A failure blocks E3.11 collection. Even a
pass leaves E3.11's real environment worker, fresh roles/seeds, evidence
frequency, fair total-compute comparisons and statistical protocol to lock.

## Roadmap boundaries

E3.11 actual post-probe returns precedes scientific E3.12 mutation credit,
E3.13 task streams and E3.14 experiment selection. Their existing interfaces
remain contract-tested only. Do not start all five experiments from this
engineering check or revisit static features on36 inspected pairs. The offline
Learning Lab can display verified artifacts separately from evaluator authority;
it must distinguish predicted scores, observed returns and synthetic fixtures.

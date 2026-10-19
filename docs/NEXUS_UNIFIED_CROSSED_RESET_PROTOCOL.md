# Crossed-reset Pendulum model comparison — protocol v1

Base `b68ecb4ff4c1cee0dcf6759afff4e5d8d78fd4b6`, verified local/GitHub,
branch `codex/unified-crossed-reset-diagnostic`. Commit this protocol, exact
allocation and tested implementation before any outcomes. Standing local grant
dated2026-10-16 and current continuation authorize this bounded development
question. Old allocations remain consumed. Carry session455.41404345900935
seconds used,3144.5859565409905 remaining, without resetting the tally.

## Question and competing explanations

Does the rank-blend versus successor preference split persist between the two
frozen Pendulum models when reset states and candidate RNG streams are identical?
Earlier model0-positive/model1-negative contrasts used different model-index
reset/search blocks. H-model: the preference split remains under crossing.
H-sample: it disappears or is inconsistent across the new shared resets.
Both may contribute; a failed screen is not proof the models are equivalent.

The intervention crosses the entire frozen model bundle, including its source
normalization, across identical exogenous reset/search schedules. It does not
isolate neural weights from their training data or RMS. Divergent later visited
states are consequences of the controllers; they are not forcibly aligned.
No prediction/architecture change, policy learning, confirmation or L2L claim.

## Fixed mechanics and reuse

Use only existing E2.9 Pendulum bundle0,1 residual64×64 checkpoints. Verify
original manifest/source-array/file hashes, parent capture/audit/journal hashes,
and parent parameter/buffer/RMS fingerprints before construction. Keep weights,
normalization, reward, dynamics, policies and support budget unchanged. No new
support, optimizer, fitting or context inference. E2.9's original fit execution
SHA remains unavailable; hashing existing files does not repair that limitation.

Reuse `evolution2.full_policy_source` as a third exact locked profile,
`generated_strategies.execute`, catalogue/plan_bound, existing planner_adapter,
TaskSpec/wrappers, disposable_model and ReservationLedger. Reuse the existing
runner with `--crossed-reset` and no-inference verifier. No parallel planner,
memory, proposer, meter or evolution stack; old profiles/artifacts remain valid.

Pendulum known source physics(g,m,l)=(10,1,1), actions(-2,0,+2), published
current-state reward,200-step TimeLimit. Two policies: successor anchor and its
existing rank blend with flat anchor. H16 and1536 imagined-state decision
ceiling unchanged: successor31 tails/action, blend48 flat plus15 successor
tails/action. Both use1491 actual imagined states per decision but respectively
51 and67 forward calls. This is not the historical H16×16 experiment.

## Shared seed registration and grid

Executable config `configs/unified_crossed_reset.json`; runtime rejects every
unregistered edit. For episode e=0,1,2,3, use reset=2107000000+e and planner
seed at tick t=2108000000+200e+t. **No model-index offset.** The four resets and
800 planner seeds are shared across both policies and both models. Reject known
historical collisions before construction using JSON seed metadata, source NPZ
env_seeds and preserved conservative H17 ranges; unavailable external histories
remain a coverage limitation. Do not use closed episode seeds or new physics.

Require identical initial-observation hashes across all four model×policy cells
within each reset, and exact planner seeds at all200 ticks. Total grid:
2models×4resets×2policies×200steps=3200 real interactions. No Acrobot collection.
All reset/action/observation/reward/next-state/termination/latency rows are saved.
Rewards reconstructed from observations must agree within1e−5 float32 tolerance.

## Registered primary descriptive contrast

For every reset compute D_b,e=return(rank,b,e)−return(successor,b,e).
For each of the two model bundles average its four D values equally. Compute
I_e=D_0,e−D_1,e on the **same** reset/search schedule, and its four-reset mean.
Report all eight D values, four I values, two model means and overall equal-model
mean. Do not pool them with earlier closed runs or treat resets as new trained
models. There are still only two pre-existing models, no new model replication.

Predeclared practical split screen: mean(D_0)>=1 point, mean(D_1)<=−1 point,
at least3/4 D_0 positive and at least3/4 D_1 negative. If satisfied label
`model_preference_split_descriptive`; otherwise `model_preference_split_not_established`.
This is a finite-source diagnostic screen, not statistical significance,
general control improvement or useful autonomous learning. No confidence claim
from n=2 models; report raw magnitudes/signs irrespective of screen. A consistent
opposite split, common preference or mixed result is reported honestly. The
secondary pooled gain cannot upgrade the primary label.

## Limits, integrity and costs

One execution, local CPU/Torch1 thread,90-second wall/CPU cap, expected20–30s.
3200 real-step cap;4,915,200 imagined upper cap (nominal4,771,200 states and
188800 forwards if complete). Pre-reserve every model batch and env.step using
the existing ledger; charge interrupted/unknown work, check deadlines and save
partial results. The meter is a trusted-host contract, not an OS sandbox.
The inherited E1 synthetic_fixture journal tag is serialization metadata, not
authored reward provenance. No retry, cap extension, grid reduction or retuning.

Complete/finite grid, cross-model initial-state equality, correct pairing/reward
timing/continuity,200-step truncation, unchanged model files/fingerprints, exact
resource reconciliation and all previous JSON unchanged are mandatory. Any
failure means incomplete/invalid, not a scientific negative. The old scientific
dispatcher stays blocked, H17 stays blocked, E2.17 is not reused and main stays
unchanged. All real steps are evaluation; training/support collection0.

Before running: source-only tests for crossing, rejection of old seeds/missing
model/reset/policy/nonfinite cells, expected interaction arithmetic, per-reset
sign consistency, exact allocation and inherited planner/resource regressions.
No simulator smoke run. Commit protocol/implementation/allocation first.

Execute `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_full_policy_replication.py --crossed-reset`; then the same
command with `--audit`. The saved-data audit collects no real/model data and its
wall time is conservatively charged to the carried ledger. Save exact execution,
source/config/checkpoint/parent hashes and dependencies, full raw trajectories
and compressed journals. Commit results separately, update research status and
one next question, then push without merging. Historical binaries remain local
and unchanged; explicit integrity audit fails if required files are absent.

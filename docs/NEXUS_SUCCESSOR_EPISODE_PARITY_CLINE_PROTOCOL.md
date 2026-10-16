# Cline strict full-episode successor implementation parity — locked protocol

Implements the committed proposal
`docs/NEXUS_SUCCESSOR_EPISODE_PARITY_PROPOSAL.md` on branch
`cline/successor-episode-parity` from `70deb7b`. **Collection is blocked**:
the allocation record `configs/cline_successor_episode_parity_allocation.json`
is committed with `authorized: false` and the runner refuses to collect until
a fresh explicit human authorization flips it to `authorized: true` with a
citation, committed before execution. No expired scientific budget is reset or
reused; the exhausted historical session ledger stays exhausted.

## Falsifiable question

Do the original serial successor scorer and the mathematically equivalent
batched scorer produce identical closed-loop actions and rewards throughout
paired 200-step Pendulum episodes with actual saved student contexts? A single
action mismatch rejects the strict episode-parity screen, even if the
resulting return is higher. No new precision, fallback or tolerance may be
selected using these outcomes.

## Fixed design

- Ten existing decoders, three known `pendulum_context_development` tasks
  (`pendulum_ctx_dev0/1/2`, physics `[6,1,1]`, `[10,2,1]`, `[10,1,1.55]`).
- Two frozen contexts per decoder/task: archived student `(decoder+task) mod 5`
  and zero; exact original checkpoint/z fingerprints from
  `artifacts/source_scalar_calibration.json`; no new encoder inference or
  support collection. Ten decoders × 3 tasks × 2 contexts = 60 cells.
- Two implementations per context: the recorded serial successor
  (`bellman_backup_control.lookahead_first_action`) and the opt-in batched
  `PreparedSuccessorSearch`, both on the same frozen model instance.
- One paired fresh episode per cell, 200 steps: 60 pairs, 120 episodes
  total. Each implementation steps its **own** environment instance;
  identical reset seeds couple the initial states; identical per-step
  candidate seeds couple the candidate tables. No visitor, implementation or
  context factor enters any seed.
- Reset seed `61_000_000 + 100*d + t`; candidate seed
  `61_100_000 + 10_000*d + 1_000*t + k` for local step `k` in 0..199.
  Exact disjointness against **all** closed registries (the sixteen committed
  `seed_groups` registries of the successor/planning/lookahead screens) is
  verified before collection and fails closed on any collision; the highest
  committed seed base anywhere is 30_100_000 and `min(used) >= 61_000_000`.
- Existing native reward and physics, H=16, 16 candidate sequences, three
  torque actions and Pendulum's original termination semantics; no
  time-budget pruning. The simulator never enters the world model or its
  candidate scores; it only executes each implementation's chosen action.
- Per step serialize observation, chosen action, Q vector, reward and
  candidate seed; per cell serialize the context hash and reset seed.

## Decision, integrity and interpretation

Require the complete locked 60-cell/120-episode grid, unchanged
checkpoints/normalization/contexts, all 200 steps in every episode,
**identical action sequences in all 60 episode pairs**, per-step and total
reward equality within **1e-8 absolute**, and Q vectors within the retained
2e-4 absolute / 2e-5 relative tolerance. The Q tolerance **cannot excuse a
changed selected action**. Report all action/Q/reward mismatches, the first
divergence step per cell, and per-decoder/task/context breakdown.

If a complete valid grid meets all requirements, conclude
`episode_implementation_parity_established_on_tested_grid`. If any action
differs or reward equality fails, conclude
`episode_implementation_parity_not_established`; inspect the original Q margin
at the first divergence without tuning and without rerunning on the same
sample. Missing/capped/corrupt execution is
`invalid_or_incomplete_execution`, never evidence for or against parity. No
improvement claim, return-significance selection, default-runner switch,
control experiment, learning-to-learn or AGI claim follows. Ten decoder units
remain distinct; student/context/episode counts are not extra independent
training seeds.

## Bounds

**24,000 fresh real environment steps** (120 episodes × 200),
**18,504,000 imagined transitions** (24,000 × 771), **816,000 model calls**
(12,000 × 51 + 12,000 × 17), zero fitting/support collection, CPU only, one
Torch thread, **180-second hard cap**. Stop and save an honest partial result
at either the time or interaction cap; no silent grid reduction or retry. All
60 frozen checkpoint files are hash-verified before and after; per-cell frozen
model/normalizer/context fingerprints are checked before and after each cell.
The runner refuses a repeated/overwriting run and requires a clean committed
tree with this protocol's starting revision as an ancestor.

## Tests

Offline guards cover the locked configuration and budget arithmetic, seed
group sizes and disjointness from all closed registries, the seed-block
floor, the allocation gate (authorized=false blocks collection; cap drift
fails), the overwrite/dirty-tree refusals, per-step call accounting
expectations, cell metrics, first-divergence logic and label rules. The full
suite is not run by this protocol.

```sh
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 -m pytest \
  tests/test_cline_successor_episode_parity.py -p no:cacheprovider
# Offline audit only; zero environment steps; repeatable:
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 \
  scripts/cline_successor_episode_parity.py --offline-audit
# Blocked until the allocation is authorized, then executed exactly once:
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 \
  scripts/cline_successor_episode_parity.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai
```

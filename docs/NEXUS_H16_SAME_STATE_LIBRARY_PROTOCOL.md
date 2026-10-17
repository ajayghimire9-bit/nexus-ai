# H16 same-state library protocol — locked, collection unauthorized

Branch `cursor/h16-same-state-library-protocol-lock` from feasibility
`929c93c`. Preparation only. `authorized: false`, `runs: 0`.

This lock does not retune H10–H15. H14 and H15 stay closed. This is
a same-state candidate-selection study, not a closed-loop controller
experiment. Not learning-to-learn, not AGI.

## Question (H16)

At an identical later simulator state, does a reused initial
candidate library L0 provide a different multitask-versus-scratch
selection advantage than a freshly drawn library?

A result cannot by itself identify the cause of H14/H15
trajectory-return differences. It cannot establish general control.

## Frozen design

Multitask: exact H10 residual recipe (three sources × 512, 15
source-RMS pretrain epochs, 128+32 target, target RMS, 20 fine-tune
epochs, residual 2×64, Adam 0.001). Scratch: same create seed
`5 + 19s`, target data, target RMS, 20 epochs. Continue seed
`7 + 19s`. Those two create seeds are the frozen H10 recipe and sit
outside the 78M environment block.

Ten independent model-training seeds. Four reset trajectories per
seed. Later times **t = 8 and t = 12**. Those times were chosen
because the H14/H15 interaction was concentrated after step 3. They
were not chosen independently of prior results. The eight later
states per seed are nested measurements, not extra replications.

Prefix actions are model-independent seeded integers from
`prefix_base + 10s + k`, length 12. The same prefix is used for
reference construction, both libraries, and both arms.

**L0:** `candidate_sequences(library_base + 10s + k)`. Shared across
t = 8 and t = 12.

**Redraw:** `candidate_sequences(redraw_base + 10_000s + 100k + t)`
for `t ∈ {8, 12}`. This is **not** the H14/H15 stride
`1000s + 10k + t`. The H16 stride is unique for every
`(seed, state, time)` in the locked grid (80 / 80).

Sixteen sequences of horizon 16. Both arms receive the same matrix.
Realized candidate returns `G(x, L, j)` are shared and are never
arguments to the scorer. No step-zero score cache. No controller
occupancy at the comparison state.

## Holdout

Rule `mcc_same_state_library_v1` rejects every key in the locked
occupied set: H10–H15 targets, H10 sources, and all earlier MCC
evaluation holdouts in `occupied_physics()`. Grid:

- gravity `round(x * 0.0001, 4)` for `x = 15…40`
- power `round(x * 0.0001, 4)` for `x = 8…22`
- max_speed `round(x * 0.005, 3)` for `x = 10…18`

Selection: SHA256 of `mcc_same_state_library_v1:{counter}` as an
unsigned 64-bit index into that grid; skip occupied keys. Counter
**0** is eligible and selects **(0.0015, 0.0014, 0.055)** at index
`16634735916735444846`. The same rule must reproduce that tuple.
H14/H15 returns were not used to choose physics.

## Seeds (`78,000,000+`)

- `reset_base` 78,000,000; `{base + s}`
- `state_reset_base` 78,100,000; `+ 10s + k`
- `prefix_base` 78,200,000; `+ 10s + k`
- `library_base` 78,300,000; L0 `+ 10s + k`
- `collect_source_base` 78,400,000; reserved span `+ 120s + 0…119`
- `collect_target_base` 78,500,000; reserved span `+ 40s + 0…39`
- `redraw_base` 78,600,000; `+ 10_000s + 100k + t`
- `model_init_base` 78,700,000; reserved `{base + 10s + i}` for
  i = 0…9, not a replacement of the H10 create seeds

No arm term. Actual generated ranges are validated, not only bases.
Streams are pairwise disjoint and sit above H14 76M and H15 77M.

## Later-state restoration contract

This is a runner-time gate. It is **not** empirically verified in
this lock. Direct `.state` assignment is forbidden.

Required MCC wrapper stack, outer to inner after `gym.make`:

1. `MountainCarDenseRewardWrapper` — published height; forces
   `terminated=False`; preserves `truncated`
2. `DiscreteTorqueWrapper((-1.0, 0.0, 1.0))`
3. `ContinuousMountainCarGravityPatch`
4. `TimeLimit(max_episode_steps=200)` from `gym.make`
5. Native `MountainCarContinuous` with `unwrapped.state`

Observation noise and action delay must be absent. Any other
wrapper, or a missing TimeLimit, invalidates the cell.

For every `(seed, state)`:

1. `env.reset(seed=state_seed)` where
   `state_seed = state_reset_base + 10s + k`.
2. Record reset observation (float32) and `unwrapped.state`
   (float32 copy).
3. Generate the length-12 prefix from `prefix_base + 10s + k`.
4. Execute the prefix once (reference). Record, at every prefix
   step, action, reward, next observation, raw state, `terminated`,
   `truncated`, `info['gym_terminated']`, and TimeLimit
   `_elapsed_steps`.
5. Store the t = 8 and t = 12 snapshots from that reference.
6. For each candidate of each library at each later time, reset
   with the same `state_seed`, replay the first `t` prefix actions,
   then compare to the reference snapshot **before** any candidate
   action.

Exact checks:

| Quantity | Rule |
|---|---|
| Prefix actions | exact integer equality |
| Reset observation | `np.array_equal` on float32 |
| Reset raw state | `np.array_equal` on float32 |
| Later observation | `np.array_equal` on float32 |
| Later raw state | `np.array_equal` on float32 |
| Prefix rewards | exact equality to the recorded reference rewards |
| `terminated` / `truncated` | exact; both must be False through t = 12 and through each 16-step candidate |
| `_elapsed_steps` | exact integer; equals `t` after prefix replay |
| Published height vs env reward | inherited H12 `REWARD_ATOL = 1e-5` consistency check only |

No numerical tolerance is used to hide replay mismatch. Float32
exact equality is required because replay uses the same reset seed
and the same actions on a deterministic map. If gymnasium float
identity fails at runner time, the cell is `incomplete`. Do not
repair by writing `.state`.

Premature termination, TimeLimit truncation, reward inconsistency,
or any identity failure invalidates that cell. An incomplete grid
cannot receive a success label.

## Primary

For each common later state `x` and library `L`:

`G(x,L,j)` realized return of candidate `j` (shared).

`P_a(x,L,j)` predicted score from arm `a`. Realized returns are not
inputs.

`j_a = argmax_j P_a` (first index).

`S_a(x,L) = G(x,L, j_a)`

`O(x,L) = max_j G(x,L,j)`

`Regret_a(x,L) = O(x,L) − S_a(x,L)`

`D_same(x) = (S_mt(L0) − S_sc(L0)) − (S_mt(Lredraw) − S_sc(Lredraw))`

Per seed, mean of the eight nested `D_same(x)`. Then student-t 95%,
df 9, n = 10. Practical margin 0.0: a test for a nonzero
interaction, not a practical-control claim. An interval that
contains 0 does not prove equality.

- `h16_l0_helps_multitask_relative_same_state`: mean > 0 and lo > 0
- `h16_redraw_helps_multitask_relative_same_state`: mean < 0 and hi < 0
- `h16_same_state_library_effect_not_established`: otherwise
- `incomplete`: missing cell, identity failure, early stop, cap,
  nonfinite; no retune

H14/H15 cells are never pooled into this label.

## Opportunity versus selection

`S_a = O − Regret_a`, so within one library

`S_mt − S_sc = Regret_sc − Regret_mt`.

Oracle library value cancels. The primary is a library-dependent
relative selection difference at common states, not a test of which
library contains a better sequence, and not closed-loop control.

Secondaries, not label-deciding:

- `O(L0) − O(Lredraw)` — library opportunity
- `Regret_a(x,L)` — within-library ranking error
- Spearman(`P_a`, `G`) — ranking correlation, not calibrated uncertainty
- First-action regret — extra loss after the selected first action
- Selected index identity
- Candidate first-action diversity
- Score-range / top-2 margin diagnostics

## Caps

Env: 15,360 source + 1,600 target + 480 reference prefixes +
25,600 reset-plus-prefix replays + 40,960 shared candidate
realizations = **84,000**.

Imagined: `80 × 2 × 2 × 16 × 16` = **81,920**.

Time **300 s**, local CPU. The standing 100,000-step ceiling is
headroom, not an authorized allowance. Do not raise these caps.

## Future-runner meter invariants

Reserve before every simulator action and every imagined batch:
reject if `used + n > cap`, then add `n`, then execute. Count
reference prefixes, every prefix replay, every candidate step, and
inner collector steps. Check the wall-clock deadline at those
boundaries. Count reserved-but-failed operations. Refuse to
overwrite an existing result file. Save incomplete results
honestly. Never retry. Never pass ground-truth candidate returns
into model scores. Training forwards are not imagined transitions.

## What D_same can and cannot say

Significant positive D_same: at these common later states, reused
L0 increases the multitask-minus-scratch selected-return gap
relative to redraw. Significant negative D_same: the reverse. This
controls occupancy at the comparison state. It does not establish
the cause of H14/H15 closed-loop returns, compounding error,
general control, cross-family transfer, learning-to-learn, or AGI.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_h16_same_state_library.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_h16_same_state_library.py
```

`--execute` must refuse until a later one-run allocation is committed.
This lock does not implement collection.

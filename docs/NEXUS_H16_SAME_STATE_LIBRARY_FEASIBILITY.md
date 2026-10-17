# H16 same-state library feasibility — source only

Design analysis only. No collection, no training, no MountainCar
environment, no holdout selection, no allocation, no protocol lock.
H14 and H15 stay closed. Not learning-to-learn, not AGI.

Branch `cursor/h16-same-state-library-feasibility` from mechanism
audit `c157eb65910b5bb45bd20b40148fb8020e7a5d69` (H15 results parent
`644a9f05781d543f03d41fc6e553b0da25be0ad4`). Session ledger unchanged:
303.777 s used, 3296.223 s remain.

## 1. Scientific question and why it matters

At the **same** later simulator state, when both libraries are
evaluated under identical conditions:

Does reusing the initial candidate library L0 change the relative
selected-return quality of the frozen H10 multitask recipe versus
matched scratch, compared with a freshly drawn library?

H12/H13 established better **initial** ranking. H14/H15 established a
closed-loop fixed-versus-redraw interaction. The mechanism audit
showed that those controllers start on the same action, then occupy
different later states. Saved traces do not contain later
counterfactual returns, so ranking quality after t=0 was not
identified.

A same-state library contrast removes controller-induced occupancy
from the immediate comparison. That is the smallest question that can
distinguish library-ranking quality from later state shift. It is a
prospective mechanistic question, not an established result and not a
new control benchmark.

## 2. H14/H15 provenance and evidence

Provenance at the start of this task: local HEAD and
`origin/cursor/h14-h15-candidate-reuse-mechanism-audit` both equal
`c157eb6`; H15 parent `644a9f0` is an ancestor; working tree was
clean; allocations consumed; ledger 303.777 / 3296.223.

| Object | SHA256 | Status |
|---|---|---|
| `artifacts/h14_candidate_reuse.json` | `7e4a74ba…959e` | match |
| `artifacts/h15_candidate_reuse_confirm.json` | `440671d5…7a15` | match |
| H14 yaml / protocol | `df155e89…f81a` / `1005e125…2c1b` | match |
| H15 yaml / protocol | `bc263e69…c193` / `4e5f7a5d…16af` | match |

Registered primaries, reconstructed in the parent audit and not
recomputed as a new claim here:

- H14: **+0.178 [+0.009, +0.348]**, 6/10, physics (0.0023, 0.0019, 0.065)
- H15: **+0.230 [+0.111, +0.349]**, 10/10, physics (0.004, 0.0021, 0.05)

Audit facts used as motivation only: t=0 actions match; multitask
fixed/redraw trajectories diverge more than scratch; the DiD accrues
after step 3/4; fixed winners are stable; redraw winners change;
later unchosen returns are missing. H14/H15 cells are not pooled.

Closed occupied MCC keys include those two holdouts plus H10–H13,
H10 sources, and the earlier MCC registry. **No new physics is
chosen here.**

## 3. Proposed common-state sampling

Future unused MCC physics, selected only after a later exclusion
rule that rejects every key in `closed_mcc_physics()`. That rule is
not created in this task.

Proposed grid:

- Frozen H10 residual 2×64 multitask versus matched scratch
- Ten independent model-training seeds
- Four independent reset seeds per model seed
- Model-independent prefixes of length 12
- Later evaluation times **t=8 and t=12**
- Two shared libraries per later state: reused L0 and one fresh redraw
- Sixteen candidates of horizon 16
- Shared candidate matrices across both model arms

Later times were **chosen because the H14/H15 interaction was
concentrated after step 3**. They were not chosen independently of
prior results. Two times are enough to ask whether a same-state
library interaction exists in that late window. They are **not**
enough to map a time course. They share one prefix, so they are
nested measurements, not extra replications.

The prefix policy is seeded integer actions

`prefix_base + 10·seed + state_index`,

drawn once per reset group, independent of multitask and scratch
scores. H14/H15 controller states are not reused.

## 4. Exact library comparison

For reset group `(seed, state)` and later time `t ∈ {8, 12}`:

1. Reset with the registered reset seed.
2. Apply the stored prefix of length `t`.
3. Verify observation and raw-state identity against the reference
   prefix recording.
4. Realize all 16 candidates of L0 and of Lredraw from that frozen
   state. Those returns `G(x, L, j)` are shared by both arms.
5. Score each library with each model from the same observation.
   Realized returns are not arguments to the scorer.
6. Select `j_a = argmax P_a(x, L)` (first index).

L0 is `candidate_sequences(library_base + 10s + k)` and does not
depend on `t`. Redraw is `redraw_base + 1000s + 10k + t` and is
time-specific. With only t=8 and t=12 the H14-style stride has
**80 unique / 80 intended** libraries (no alias pairs).

## 5. Proposed primary and secondary metrics

Replication unit: the independent model-training seed. Average the
eight nested later states (4 resets × 2 times) first.

Primary:

`D_same,s = mean_{k,t} [ (S_mt(x,L0) − S_sc(x,L0)) − (S_mt(x,Lredraw) − S_sc(x,Lredraw)) ]`

Student-t 95%, df=9, n=10, practical margin 0.0.

- `h16_l0_helps_multitask_relative_same_state`: mean > 0 and lo > 0
- `h16_redraw_helps_multitask_relative_same_state`: mean < 0 and hi < 0
- `h16_same_state_library_effect_not_established`: otherwise
- `incomplete`: missing cell, identity failure, early stop, cap, nonfinite

Secondaries, not label-deciding:

| Diagnostic | Isolates |
|---|---|
| `O(x,L0) − O(x,Lredraw)` | library opportunity |
| `Regret_a(x,L)` | ranking error inside one library |
| Spearman(`P_a`, `G`) | ranking correlation, not calibrated uncertainty |
| First-action regret | extra loss after the selected first action |
| Selected index identity | whether arms pick the same candidate |
| Candidate first-action diversity | proposal richness, not model quality |

Score range and top-2 margin remain descriptive only.

## 6. Algebraic selection-versus-oracle decomposition

`S_a(x,L) = G(x,L, j_a)` and `O(x,L) = max_j G(x,L,j)`, so

`S_a = O − Regret_a`.

Within one library the arm gap is

`S_mt − S_sc = (O − Regret_mt) − (O − Regret_sc) = Regret_sc − Regret_mt`.

Oracle library value **cancels**. Adding any constant to every
candidate return of a library leaves `D_same` unchanged. Therefore
the primary is a ranking-selection contrast, not a test of which
library contains a better sequence.

`O(x,L0) − O(x,Lredraw)` is the separate opportunity diagnostic.

## 7. State-restoration feasibility

Registered method: **reset-plus-action-prefix**. Direct `.state`
mutation is rejected unless a separate validated restore is later
registered.

Source reading of the existing MCC stack:

- `reset(seed)` plus a deterministic physics map is what H14/H15
  already require at t=0 (`RESET_ATOL = 1e-6`, obs and raw state).
- The dense-height wrapper forces goal `terminated=False`.
- `TimeLimit` is 200. Prefix 12 plus horizon 16 cannot truncate.
- Inner MCC physics is a deterministic function of
  `(position, velocity, action)`.

This task did **not** construct a real environment, so gymnasium
float identity after an 8- or 12-step prefix is **not empirically
verified**. That is a residual for any future runner: fail closed on
observation or raw-state mismatch; do not repair by writing `.state`.
Mutating `.state` would also desynchronize TimeLimit `elapsed_steps`.
For H=16 that mismatch cannot truncate, but it remains unregistered.

Restoration is therefore **conditionally feasible**, not guaranteed.
Unexpected termination, incomplete candidates, inconsistent
published-versus-env rewards, or identity failure make the cell
`incomplete`.

## 8. Identifiability and causal limitations

A positive `D_same` would mean: at the sampled **common** later
states, multitask’s selected-return advantage over scratch is larger
under L0 than under redraw. That supports a ranking-by-library
interaction (audit hypothesis B) on those states.

It would **not** establish why H14/H15 full trajectories differed,
compounding model error, general closed-loop control, robustness on
unrelated families, learning-to-learn, or AGI.

Model-independent prefixes control the immediate occupancy
confound. They also limit relevance: the evaluated states are not
states that H14/H15 controllers actually visited.

Keep four levels distinct:

1. Candidate-library opportunity — `O(x,L)`
2. Model ranking error — `Regret_a` and `D_same`
3. Closed-loop state distribution — not measured here
4. Causal attribution of H14/H15 controller returns — not identified

## 9. Exact prospective resource accounting

From the frozen H10 recipe and the proposed grid, counted in
`budget()`:

| Item | Real steps |
|---|---|
| Source collection 3×512×10 | 15,360 |
| Target train+val (128+32)×10 | 1,600 |
| Reference prefix to t=12, 40 groups | 480 |
| Reset+prefix replay 40×2×16×(8+12) | 25,600 |
| Shared candidate realizations 80×2×16×16 | 40,960 |
| **Env total** | **84,000** |

Imagined scoring: 80 later states × 2 libraries × 2 arms × 16 × 16
= **81,920**.

`collect_transitions` records exactly `n` inner `env.step` calls.
Resets are not steps. `make_planner(..., uncertainty_penalty=0)`
adds no ensemble inferences. Training forwards are not imagined.
Failed or partial reservations stay counted and force `incomplete`.

84,000 is below the standing 100,000-step ceiling with a **16,000**
step margin. Do not raise the ceiling. A future lock should freeze
`env_cap = 84000` and `model_cap = 81920`, not 100,000.

H14 ran the same training recipe plus 29,760 env and 655,360
imagined steps in 4.3 s. H16 has the same training, more real
steps, and far fewer imagined steps. A 300 s wall cap is ample.
These numbers are prospective, not locked.

A smaller scientifically defensible fallback, if a later runner
discovers hidden steps, is one later time (t=8 only): about 48,160
real / 40,960 imagined. That remains available. It is not chosen
here.

## 10. Mock test results

`tests/test_h16_same_state_library_feasibility.py`: 6 passed.

Covered: parent hashes; no holdout selection; shared later-state
identity; reset-plus-prefix reconstruction; L0 versus redraw
identity; candidate-return reconstruction; oracle and regret;
oracle cancellation; primary algebra; missing/duplicate/nonfinite
cells; premature prefix and candidate termination; hard budget
rejection before extra operations; exact 84,000 / 81,920
accounting; scoring signature without realized returns. Mocks only.

## 11. Implementation risks and unresolved decisions

1. Empirical MCC prefix identity is unverified without a simulator.
2. Exact future seed block is proposed as 78,000,000 to sit above
   H14 76M and H15 77M, not allocated.
3. Prefix policy formula is proposed, not hash-locked.
4. Redraw is proposed as time-specific; a single redraw per reset
   group is an alternative not chosen.
5. Whether the primary averages t=8 and t=12 or reports one
   predeclared time is a lock decision. This draft averages both
   as nested measurements and keeps per-time means secondary.
6. No unused-physics rule exists yet. Creating one would select a
   holdout and is out of scope.
7. No runner, allocation, or time-meter exists.
8. Published-versus-env reward checks on prefix and candidates must
   be specified at lock time, matching H14.
9. Two holdouts already showed a closed-loop interaction; a
   same-state result on a third MCC physics would still not be
   cross-family evidence.

## 12. Is an H16 protocol scientifically ready to lock?

**No.** The question is well-posed, the algebra isolates ranking
from opportunity, the mock contracts work, and the prospective
budget fits the standing ceiling. A protocol lock still needs a
holdout rule, allocated seed streams, a restoration fail-closed
contract on the real MCC stack, and an unauthorized allocation.
Those are later tasks. An optional draft exists and is marked
**DRAFT — NOT LOCKED**.

Do not authorize collection. Do not treat this document as H16.

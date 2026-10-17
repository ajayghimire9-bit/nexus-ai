# H16 selection-mechanism diagnosis — recorded data only

## Finding

The registered H16 result is independently reproduced, unchanged:
**D_same = +0.022889688336460212 [−0.014210807366461443,
+0.05999018403938187]**, Student-t 95%, ten independent model-training
seeds, df9; **6/10 positive**. Label:
`h16_same_state_library_effect_not_established`.

Multitask ranks and selects candidates better than scratch in **both**
libraries. This is compatible with a small, uncertain difference between
those two advantages. Failure to establish the interaction does not mean
multitask failed to rank candidates. It also does not establish equivalence
of libraries or explain closed-loop control effects.

Everything beyond reproduction of the registered primary is exploratory
reanalysis of already inspected outcomes. Intervals below are unadjusted
descriptions, not new confirmation tests or independent corroborations.

## Provenance and restrictions

Diagnosis branch: `codex/h16-selection-mechanism-diagnosis`.
Clean starting commit and fetched Origin base:
`9474ec63bafbe03adb2b9557c03edfdca650a385`, on
`cursor/h16-same-state-library-execute`. Repository remotes verified:
Origin `https://origin.cursor.com/ajay-ghimire/nexus-ai.git` and GitHub
`https://github.com/ajayghimire9-bit/nexus-ai.git`. The base branch had no
GitHub ref at the initial check; it did exist on Origin at exactly this
SHA. No older GitHub revision was substituted.

Verified ancestry: results `9474ec6` descends from authorization
`834bb633e7977ea6922a8ad9f1adcc091eccae58`, readiness/audited implementation
`b646347c3f5a84bb8c4e492cca4fa50a6b9f7543`, and guarded runner `1f5a757`.
The raw artifact records the clean execution HEAD `834bb633…`; this
differs legitimately from the earlier independently audited implementation.

Independent analysis implementation was committed first:
`0de7557ab4dd644fcd7683d827d91ca26f963c9b`. The derived JSON records this
clean revision and the analysis module hash. Historical hashes verified:

- Raw H16: `96be8b401a06f48e8eab190058f58a82f6dc1f2eebc6c2fe46f31da1e4bc4625`.
- Frozen configuration: `e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c`.
- Frozen protocol: `f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7`.
- Consumed allocation: `079b9379b1c87536086c50a1cf5f5204f1fcffbb6c2606fa988a6d7290f077ab`.
- Usage ledger: `ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117`.

The raw file's allocation hash is instead the **pre-run** authorization
version, `b8eb37b6ffc7b74c9abd0fbf9fdfe62d29275e346346983d713824c62d737e04`.
It matches the exact file obtained by `git show 834bb633…:configs/mcc_same_state_library_allocation.json`.
Its difference from the subsequently consumed/closed allocation is expected.
The older preparation provenance remains historical, not current authority.
All raw-declared parent artifact, protocol and execution-source hashes pass.

H16 remains closed: authorized once, consumed, closed; zero retries and
invalid attempts in its usage record. Its historical costs remain 84,000
real steps and 81,920 imagined transitions. This audit adds **zero real
steps, imagined transitions, checkpoint/model inference calls, or training
updates**. Ledger remains **305.842 seconds used / 3294.158 remaining**.
No allocation, historical result, protocol, checkpoint or main branch changed.
No H17 is designed, locked, authorized or executed here.

## Reconstruction and completeness

Analysis uses saved predicted score vectors and realized candidate returns,
not the rounded report or saved selection summaries as inputs. For each
library, select the first maximum of its 16 predicted scores. Verify the
saved chosen index/action/return, the oracle and regret against that
reconstruction. Verify each realized return against its 16 recorded rewards
using absolute tolerance **1e−12**. Candidate matrices are 16×16 discrete
actions; their archived little-endian int64 byte fingerprints match.

The exact grid is ten distinct seeds × four reference prefixes × two later
times × two libraries × two model arms: 80 nested states, 160 libraries,
320 arm/library cells and 2,560 recorded candidate trajectories. Reject
missing/extra/duplicated seeds or states, missing arms/libraries, malformed
shapes, nonfinite values, numeric strings, booleans in numeric fields,
misaligned candidates, inconsistent selections and duplicate JSON keys.
Validate L0 equality across t8/t12, registered candidate/reset/prefix seeds,
shared prefix histories, and recorded elapsed-step fields.

For each state reconstruct
`D = (S_mt_L0 − S_sc_L0) − (S_mt_redraw − S_sc_redraw)`;
average its eight measurements **inside each seed first**. Average ten
seed means; use sample standard deviation, SE/√10 and the locked critical
value **2.262** (df9). The resulting primary, ten contributions and label
match the registered artifact within 1e−12. No 80-state pseudo-replication.
The simulator identity gate passed in the original execution; this audit
verifies saved alignment and hashes, not a new simulator replay.

## Selection and ranking, by library

Mean values, multitask / scratch:

- **L0**: selected return **−15.503970 / −15.681606**; sequence regret
  **0.005002 / 0.182637**; Spearman **0.901654 / 0.118676**; top1
  **88.75% / 27.50%** (71/80 versus 22/80); in-library first-action regret
  **0.004285 / 0.092826**.
- **Redraw**: selected return **−15.513197 / −15.667942**; sequence regret
  **0.007310 / 0.162056**; Spearman **0.877794 / 0.062096**; top1
  **83.75% / 30.00%** (67/80 versus 24/80); in-library first-action regret
  **0.006315 / 0.094189**.

Paired seed-level multitask selection advantages (equivalently scratch
minus multitask regret) are **+0.177635 [0.073290, 0.281981]** in L0 and
**+0.154746 [0.077216, 0.232276]** in redraw, positive in all ten seed
means in both libraries. Their difference is the inconclusive primary;
these algebraically dependent measures are not three independent findings.

Paired Spearman advantages are **+0.782978 [0.531970, 1.033986]** and
**+0.815699 [0.519304, 1.112093]**. Top1 advantages are **+0.612500
[0.404082, 0.820918]** and **+0.537500 [0.310320, 0.764680]**.
First-action regret advantages are **+0.088541 [0.038112, 0.138969]** and
**+0.087874 [0.046558, 0.129190]**. These are paired contrasts, not
inferences from overlap of separate intervals. Unbounded t intervals may
extend past the natural range of an individual correlation or regret;
they are retained rather than clipped.

Here first-action regret means oracle sequence return minus the best
recorded sequence **sharing the chosen first action**. It does not execute
that action followed by a common continuation and is not causal action
value, an oracle policy, or full-episode regret.

All 160 libraries have 16 distinct sequences and all three first actions.
There are no exact predicted-score or realized-return ties. The new
average-rank Spearman therefore agrees with the historical ordinal-rank
calculation on these data; its tie-aware behavior is tested separately.
Top1 uses exact realized maxima; selection uses first-maximum tie breaking.

Mean predicted top-two margins are multitask/scratch **0.084365/0.020293**
for L0 and **0.078858/0.025267** for redraw. Mean score ranges are
**0.372389/0.191835** and **0.355762/0.190021** respectively. These are
score-shape descriptors; unequal scales do not calibrate confidence.
Arm first-action disagreement is 60.0% in L0, 62.5% in redraw; selected
sequence-index disagreement is 73.75% and 72.5%. Candidate-index identity
is meaningful within the same library, not across different libraries.

## Library opportunity and oracle cancellation

Mean oracle returns: **L0 −15.498968**, **redraw −15.505887**. Opportunity
`O_L0 − O_redraw` is **+0.006918 [−0.027872, +0.041708]**, not a
demonstrated superior library.

The decomposition is exact in every saved cell:

`S_arm = O − regret_arm`

`S_mt − S_sc = regret_sc − regret_mt`.

The shared oracle cancels **within each library**, hence also from D_same.
A common opportunity advantage cannot mechanically explain a relative
multitask-versus-scratch advantage. Library composition can still affect
how difficult rankings are; oracle cancellation does not rule that out.

For multitask, `S_L0 − S_redraw` = **+0.009226** = opportunity
**+0.006918** + redraw-minus-L0 regret **+0.002308**. For scratch it is
**−0.013663** = **+0.006918 − 0.020582**. The two selected-return
intervals are **[−0.028361, +0.046814]** and
**[−0.068115, +0.040788]**. Neither resolves an arm-specific L0 benefit.
More opportunity, less regret, and higher selected return must not be
counted as independent evidence when tied by this identity.

## Exploratory later-time and sensitivity results

At t8, D_same is **+0.041116 [−0.007246, +0.089478]**. At t12 it is
**+0.004663 [−0.033973, +0.043300]**. Their paired t12−t8 difference is
**−0.036453 [−0.082901, +0.009995]**. This is a declining point estimate,
not an established temporal decline. Four states per seed per time still
give ten independent replications, not forty.

Multitask-minus-scratch selected-return advantages remain positive in
both libraries at both times: L0/redraw **0.169349/0.128233** at t8,
**0.185922/0.181258** at t12. Thus the smaller t12 interaction is not
evidence of multitask losing its ranking advantage altogether.

Primary seed means, IDs0–9:
`+0.114571, +0.059154, +0.096276, −0.045311, −0.014164,
+0.011303, +0.022598, −0.003650, −0.022965, +0.011085`.
Leaving one training seed out gives means **+0.012703 to +0.030468**;
no individual seed omission reverses the sign. These are influence
descriptions, not ten new tests or replacement primary estimates.

Reference-index means k0–k3 are **+0.065759, +0.100833, −0.023594,
−0.051438**. An index denotes a different randomized reference state
within each seed, not one common physical state. Removing both times of
an index gives means **+0.008600, −0.003091, +0.038384, +0.047666**;
all four exploratory leave-index-out intervals include zero. Reference
composition matters to the point estimate. It does not justify removing
an unfavorable index. The largest single nested contribution is
**+0.741967** at seed0/k1/t8; the smallest is **−0.399212**. The full raw
derived cells and seed means are retained, including these extremes.

## Connection to H12–H15 and limits of mechanism inference

H12/H13 established reset-state ranking advantages on their separate MCC
holdouts: regret gains **+0.144 [0.095, 0.193]** and
**+0.156 [0.086, 0.226]**. Their receding-control secondary outcomes did
not consistently follow those rankings; H13 favored scratch. H16's
descriptive ranking advantage in both libraries is compatible with this
prediction/decision distinction, not a new control confirmation.

H14/H15 closed-loop fixed-minus-redraw relative interactions remain
**+0.178 [0.009, 0.348]** and **+0.230 [0.111, 0.349]**. Their recorded
traces showed more stable fixed-library choices and later reward
differences, alongside different controller occupancies. Unchosen later
candidate returns were not saved, and a redraw-seed alias was identified
in that separate audit. Stability and occupancy correlations do not
identify a cause. Those results and limitations are preserved.

H16 evaluates model-independent prefix states on **different physics**,
then commits candidate sequences open loop. H14/H15 measure closed-loop
trajectories whose states depend on prior choices. Changing both the
physics and the state-generation/return estimand prevents attributing
their numerical difference to occupancy alone. Do not pool the studies
into a new posthoc primary or subtract their means as a causal effect.

Available: full score vectors, shared realized reward traces, candidate
identities, chosen actions, reference observations/states and prefixes.
Unavailable here: neural checkpoint reconstruction/verification from
H16's raw file, imagined state trajectories, actual intermediate states
for each unchosen candidate, new closed-loop counterfactual outcomes,
and a matched-physics occupancy intervention. The audit verifies the
saved numerical evidence and execution-source hashes, not that the
saved neural scores would be reproduced by loading original weights.
No checkpoint inference was attempted.

Candidate opportunity is small and unresolved; ranking is descriptively
strong for multitask in both libraries; changing controller states,
closed-loop occupancy and accumulated world-model error remain possible
contributors to H14/H15. None is causally identified. H16's null-crossing
interval is not proof of a zero interaction or a refutation of H14/H15.
No general control improvement, learning-to-learn or AGI is established.

## Reproduction and tests actually run

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_h16_selection_mechanism_diagnosis.py
```

To save a new derived output, pass `--output /new/path.json`; existing
outputs are refused, and historical inputs are never written. The saved
analysis is `artifacts/h16_selection_mechanism_diagnosis.json`.
Paired arm contrasts are reproduced by applying `interval` to the ten
paired differences in its `exploratory_summary.*.per_seed` arrays.

Focused suite: **30 passed in 0.61s**, final rerun **30 passed in 0.65s**.
Includes historical provenance,
raw primary reconstruction, oracle cancellation, selection and first-action
regret indexing, tie handling, row-order invariance, nesting, exact grid,
candidate/return/reward alignment, missing/nonfinite/wrong-type rejection,
duplicate JSON keys, corrupted hash rejection, and complete analysis in
an isolated process that rejects NumPy, Torch, Gym, world, task and RL
imports. This does not run the old simulator/mock-training runner tests
or claim a full scientific-suite rerun. The CLI completed in about
**0.11s** process wall time; that is offline arithmetic, not experiment
execution and does not debit or reset the session ledger.

A separate 50-digit Decimal reconstruction from the original JSON scores
and returns gives **0.0228896883364602375**, only **2.43e−17** from the
float reconstruction. Historical input hashes were checked again after
analysis and remain unchanged. Derived artifact SHA256:
`3d5782da065e78146fba4e798c3aba8ba392ba3ed8e5b2803fcb25b59f2ddb2a`.

## One prioritized, falsifiable next question

**Does the relative library effect persist on controller-generated
occupancies when physics is held fixed, rather than on the
model-independent prefix states sampled by H16?**

That would distinguish an occupancy-dependent effect from a library
ranking effect that generalizes across state distributions. It is a
question only: no new protocol, seeds, allocation or H17 implementation
is created or authorized in this branch.

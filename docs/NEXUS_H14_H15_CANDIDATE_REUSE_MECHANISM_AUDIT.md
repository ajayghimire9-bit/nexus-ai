# H14/H15 candidate-reuse mechanism audit

Source-only investigation of why fixed candidate-library reuse gave
multitask a relative advantage over redraw. Uses committed H14 and H15
artifacts only. No training, no simulator, no collection, no imagined
rollouts, and no H16 protocol. Nested states and decision steps are
descriptive measurements, not extra replications. H14 and H15 remain
separate registered decisions. This audit is not a new primary result.

## 1. Repository provenance

| Object | Value |
|---|---|
| Audit branch | `cursor/h14-h15-candidate-reuse-mechanism-audit` |
| Parent HEAD | `644a9f05781d543f03d41fc6e553b0da25be0ad4` |
| Parent origin | `origin/cursor/h15-candidate-reuse-confirm-execute` = same SHA |
| Ancestry | `644a9f0` ← `0580ac5` authorize ← `f90e2b3` readiness ← `f18ad85` runner ← `ff91a94` lock |
| Working tree at start | clean; only this audit's new files |
| Session ledger | 303.777 s used / 3296.223 s remain; **unchanged** |

Frozen hashes verified before analysis:

| Object | SHA256 | Status |
|---|---|---|
| `artifacts/h14_candidate_reuse.json` | `7e4a74ba0a8f21f735b41cc1fbceb4d5c005f68718159c0a2077caa27934959e` | match |
| `artifacts/h15_candidate_reuse_confirm.json` | `440671d592c888e16f5c43d90de701c83bcae6887b9e0b83d1eb71b4312c7a15` | match |
| `configs/mcc_candidate_reuse.yaml` | `df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a` | match |
| `docs/NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md` | `1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b` | match |
| `configs/mcc_candidate_reuse_confirm.yaml` | `bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193` | match |
| `docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md` | `4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af` | match |

H14 physics `(0.0023, 0.0019, 0.065)`. H15 physics `(0.004, 0.0021, 0.05)`.
Both allocations are consumed. Neither experiment was rerun.

## 2. Verified registered results

Independent reconstruction from saved cells, using the locked
`summarize` functions (not the runners):

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`,
averaged over four reset states, then student-t 95% on ten model
seeds, df = 9.

| Suite | Label | Mean D | Interval | Positive seeds | Env / imagined |
|---|---|---|---|---|---|
| H14 | `h14_fixed_library_helps_multitask_relative` | +0.178 | [+0.009, +0.348] | 6/10 | 29,760 / 655,360 |
| H15 | `h15_fixed_library_helps_multitask_relative` | +0.230 | [+0.111, +0.349] | 10/10 | 29,760 / 655,360 |

Per-seed D (four-state means):

- H14: +0.571, +0.012, +0.110, +0.434, −0.010, +0.380, −0.012, +0.383, −0.053, −0.035
- H15: +0.562, +0.124, +0.349, +0.021, +0.406, +0.247, +0.227, +0.167, +0.082, +0.112

Integrity checks that passed: ten distinct seeds, four distinct states
per seed, four complete 16-step controllers per state, finite rewards
and predicted scores, step-reward sums equal saved returns to 1e-9, no
missing or duplicated cells, registered labels unchanged. No pooled
H14+H15 primary was formed.

These remain the only registered labels. Everything below is
exploratory description.

## 3. Saved-trace availability

Each controller stores sixteen decision rows. The locked `TRACE_FIELDS`
plus the saved chosen residual give the following matrix.

| Evidence | Status | Use |
|---|---|---|
| Current observation | available | occupancy, first-divergence pairing |
| Next observation | available | occupancy after the executed action |
| Executed action | available | disagreement and histograms |
| Per-step reward | available | return reconstruction and stepwise DiD |
| Candidate seed | available | library identity and alias map |
| Candidate matrix | reconstructible from seed | L0 fingerprint check |
| Predicted candidate scores | available | range, top-2 margin, rank stability |
| Chosen candidate index | available | switch rate |
| Library fingerprint | available | fixed-mode reuse check |
| Chosen one-step residual | available | executed-transition residual L2 only |
| Full predicted next state | **missing** | cannot reconstruct unchosen residuals |
| Unchosen later realized returns | **missing** | no later ranking accuracy |
| Reset L0 open-loop actuals | available at t = 0 | reset ranking only |
| Model checkpoints / weights | **missing** | no extra inference |

Never infer unchosen-candidate returns from the selected-action reward.
Chosen residuals are not one-step residuals for the other fifteen
candidates.

## 4. Candidate-stability findings

Fixed mode reuses the same library after t = 0. Redraw samples a new
library at every later step (locked stride `1000s + 10_000 + t`).

Selected-index switch rate (fraction of steps 1–15 that change winner):

| Condition | H14 | H15 |
|---|---|---|
| Multitask fixed | 0.035 | 0.033 |
| Scratch fixed | 0.012 | 0.008 |
| Multitask redraw | 0.943 | 0.937 |
| Scratch redraw | 0.930 | 0.940 |

Fixed-mode Spearman rank stability of the sixteen scores across
consecutive steps: multitask **0.971 / 0.970**, scratch **0.997 / 0.998**.

That contrast is a treatment behavior, not a causal proof. Fixed almost
never changes its winner; redraw almost always does, because it is
scoring a new matrix. The stability difference is similar in both arms,
so stability alone does not explain why *multitask* carries the DiD.

## 5. Action and occupancy findings

At t = 0 both modes share L0 and the same observation. Executed first
actions match in **40/40** pairs for both arms in both suites
(match rate 1.0). The scorer is deterministic on a shared library.

First later disagreement:

| Arm | H14 mean first split | H14 never-diverge | H15 mean first split | H15 never-diverge |
|---|---|---|---|---|
| Multitask | 3.30 | 0/40 | 2.68 | 0/40 |
| Scratch | 4.94 among the 18 that split | 22/40 | 6.40 among the 25 that split | 15/40 |

Scratch often executes the same 16-step action sequence under both
modes. Multitask always splits at least once.

Action disagreement by decision index (fraction of the 40 pairs):

- H14 multitask: 0, 0.35, 0.43, 0.40, … later 0.33–0.68
- H14 scratch: 0, then 0.08–0.23
- H15 multitask: 0, 0.45, 0.35, … later 0.40–0.60
- H15 scratch: 0, then 0.05–0.18

Paired observation L2 (fixed versus redraw, same arm) starts at 0 and
grows after the first split:

| Arm | H14 terminal L2 | H15 terminal L2 |
|---|---|---|
| Multitask | 0.091 | 0.102 |
| Scratch | 0.037 | 0.029 |

Action 2 (right) is the modal discrete action in every arm-mode cell.
Multitask fixed uses more action 2 than multitask redraw (H14 342 vs
314; H15 405 vs 375 of 640 decisions). Scratch histograms stay closer
across modes.

Seed-mean occupancy L2 is present in every model seed (H14 0.010–0.032;
H15 0.016–0.034). It does **not** track seed-level D simply: H14 seed 3
has D +0.434 and the smallest occupancy gap (0.010); seed 1 has D +0.012
and the largest gap (0.032). Trajectory divergence is therefore a
consistent correlate of the closed-loop treatment, not a seed-wise
explanation of the registered interaction.

After the first action split, later occupancy, later libraries, and
later decisions are confounded. Occupancy growth is not by itself the
source of the control difference.

## 6. Planning-score diagnostics

Predicted-score ranges and top-two margins are a model property more
than a mode property.

| Condition | H14 range | H14 top-2 | H15 range | H15 top-2 |
|---|---|---|---|---|
| Multitask fixed | 1.501 | 0.320 | 1.200 | 0.248 |
| Multitask redraw | 1.267 | 0.238 | 0.931 | 0.189 |
| Scratch fixed | 0.270 | 0.034 | 0.304 | 0.035 |
| Scratch redraw | 0.274 | 0.031 | 0.309 | 0.032 |

Multitask scores are about four to five times more spread than scratch
scores. All saved scores are finite; no saturation or NaN/Inf cells.
Predicted-score magnitude is **not** calibrated uncertainty. Score
comparability across different libraries is limited: redraw changes the
set being scored.

Later ranking accuracy is **not testable**. Unchosen candidate returns
after t = 0 were not realized. Reset L0 open-loop actuals remain
available only at the shared start state.

## 7. Reward decomposition

Step rewards rebuild every saved controller return. Mean stepwise DiD
(40 state-pairs; exploratory, not a new primary):

| Window | H14 | H15 |
|---|---|---|
| Steps 0–3 | −0.0008 | +0.0004 |
| Steps 4–15 | +0.179 | +0.230 |
| Sum | +0.178 | +0.230 |

The registered interaction appears late in the 16-step episode. Early
rewards are essentially tied. That is consistent with identical t = 0
actions and with later occupancy/decision confounding. It does not
isolate a mechanism.

H14's four negative seeds have small |D| (0.010–0.053). H15 has no
negative seed. No single reset state or seed is required to produce the
sign of either registered mean; the late-window concentration is shared.

## 8. Seed-alias analysis

Locked redraw formula unchanged: `redraw_base + 1000·seed + 10_000 + t`
for t = 1…15. Intended later slots = 10×4×15 = 600.

Reconstructed map (identical in H14 and H15 because both use
`redraw_base = 2_000_000`):

- unique libraries: **450**
- aliased slots: **150**
- colliding groups: **150**
- within-state uniqueness: **True**

Each collision is a pair of later (seed, state, step) triples that share
one candidate seed. No within-state redraw stream repeats a library
across its own 15 later steps. The collisions are a known locked
property. They create cross-seed / cross-state proposal reuse, but the
saved streams do not show a within-state repeated-library artifact.

This audit does **not** claim that aliasing caused, inflated, or
invalidated the registered labels.

## 9. Supported versus unresolved mechanisms

Three levels are kept distinct: (1) the established treatment
interaction (the registered DiDs), (2) observed behavioral correlates,
(3) a causal explanation. Only (1) is already closed science.

| Hypothesis | Assignment | Why |
|---|---|---|
| A. Candidate stability | Compatible, unresolved as a cause | Fixed almost never switches; redraw almost always does. The same pattern appears in *both* arms, so stability is a treatment behavior, not an identified multitask-specific cause. |
| B. Candidate distribution | Not fully testable | Later libraries differ and change winners. Ranking quality at later states requires realized unchosen returns, which were not saved. |
| C. State-distribution shift | Supported as a correlate; unresolved as a cause | Multitask occupancy L2 grows more than scratch; DiD accrues after step 4. After the first split, later states and later decisions are confounded. Seed-level D does not track occupancy L2. |
| D. Model prediction behavior | Compatible / not testable for the interesting claim | Chosen residuals are tiny (multitask ~0.0007–0.0010, scratch ~0.0018–0.0032) and similar across modes. Full predicted next states and checkpoints are missing. Residual magnitude along chosen transitions is not the DiD. |

Identifiability after first divergence: any later score, residual, or
reward comparison mixes (i) a different candidate library, (ii) a
different visited state, and (iii) a different subsequent policy. Saved
data cannot separate those three.

## 10. Limitations and alternative explanations

- Closed-loop 16-step returns on two MCC holdouts only. Not 200-step
  control, not cross-family transfer, not learning-to-learn.
- Shared L0 removes the H12/H13 arm-seed confound at t = 0 only.
- No checkpoints, so no extra model queries on saved states.
- No unchosen later returns, so no later regret or ranking accuracy.
- Chosen residuals are not a reconstruction of one-step residuals for
  the other candidates.
- Aliasing is preserved and not claimed causal.
- Exploratory stepwise and per-step disagreement numbers are nested
  measurements. They were not used to hunt a new significance claim.
- Alternative remaining accounts include: sharper multitask score
  landscape amplifying library-to-library winner changes; a small early
  action difference that compounds under the MountainCar reward;
  redraw libraries that happen to be worse *for multitask's value
  landscape* at the states it reaches; or a combination. None of these
  is identified here.

## 11. One recommended next falsifiable question

**At a frozen later state, does the redraw library rank worse for
multitask than the reused L0 library, when both libraries are scored
and realized from the same observation?**

That is a same-state library contrast. It is not locked, not
authorized, and not executed. It is not H16.

## 12. What that question would and would not establish

It would establish whether the two libraries, evaluated from one
restored observation with both models, have different selected-action
returns or ranking regret. A multitask-specific same-state gap would
support explanation B over a pure occupancy story. A null same-state
gap with the original closed-loop DiD still in force would push the
remaining weight onto explanation C (different later states) or onto
subsequent decision confounding.

It would **not** establish 200-step control, general candidate reuse,
learning-to-learn, or AGI. It would not reopen H14 or H15. It would
require environment restoration from saved reset seeds or saved
observations, plus realization of unchosen candidate sequences — work
that this source-only audit does not do.

No H16 protocol, allocation, or runner is created here.

## Resource accounting

Zero new environment steps. Zero new imagined transitions. Zero
training updates. Session ledger remains 303.777 s used, 3296.223 s
remaining. Implementation:
`src/nexus/world/h14_h15_candidate_reuse_mechanism_audit.py`.
Raw descriptive artifact:
`artifacts/h14_h15_candidate_reuse_mechanism_audit.json`.
Tests: `tests/test_h14_h15_candidate_reuse_mechanism_audit.py`.

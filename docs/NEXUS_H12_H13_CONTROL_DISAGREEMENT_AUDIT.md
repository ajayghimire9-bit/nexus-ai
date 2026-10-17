# H12/H13 ranking-versus-receding-control disagreement — source audit

Analysis of committed artifacts only. No new environment steps, no
training, no simulator reset or rollout, and no H12/H13 rerun. Recede
is not promoted to a primary. Not learning-to-learn, not AGI.

## Methodology

Branch `cursor/h12-h13-recede-disagreement-audit` from verified H13
results `6eb8265`. Frozen hashes: H12 raw
`c65bc9f42e3fbfe99b5b7dc4d68f8a08fb63fc04e08d374e619dba2f35bbcb8f`,
H13 raw
`e1083da8fecccffa140b2051744c9c3bd8c0398ffa8fd5a9ebc36c2a079afdc8`.
The statistical unit is the independent model-training seed (n = 10).
States and candidate trajectories are nested measurements, not extra
replications.

Saved cells contain, for each of four reset states: `obs0`, 16
predicted scores per arm, shared realized open-loop returns, 16×16
open-loop reward traces, selected index, first action, both regrets,
and a scalar recede return. Candidate matrices were reconstructed
from the locked `candidate_base+10s+k` formula. Recede actions,
recede rewards, later observations, later scores, residuals, and
checkpoints were **not** saved.

## Reconstructed evidence

H12 primary `scratch − multitask` sequence regret
**+0.144 [+0.095, +0.193]** (10/10). Label
`mcc_planning_ranking_multitask_better`. First-action regret
**+0.076 [+0.046, +0.105]**. Recede `multitask − scratch`
**+0.038 [−0.144, +0.220]** includes 0 (5/10).

H13 primary **+0.156 [+0.086, +0.226]** (10/10). Label
`mcc_planning_ranking_confirm_multitask_better`. First-action regret
**+0.120 [+0.071, +0.169]**. Recede **−0.253 [−0.431, −0.074]**
(2/10; upper bound below 0).

All intervals match the closed artifacts to 1e-12. Shared ground
truth implies an identity: the selected open-loop return difference
equals the sequence-regret primary. Traces reconstruct every realized
candidate return. Saved first actions match reconstructed sequences.
`argmax` predicted is the saved selected index. At every reset state,
that first action also maximizes predicted first-action value V(a).

Reset-state ranking quality is not close. Multitask Spearman 0.919
(H12) and 0.946 (H13); top-1 0.825 and 0.950. Scratch Spearman 0.005
and 0.061; top-1 0.200 and 0.250. Predicted-versus-realized mean
absolute error is 0.24/0.19 for multitask and 13.03/13.03 for
scratch. The arms choose the same first action on 0.45 (H12) and
0.325 (H13) of states.

Recede minus the selected open-loop commitment, seed-level:

- H12 multitask **+0.208 [+0.146, +0.270]**; scratch **+0.315 [+0.189, +0.441]**.
- H13 multitask **+0.094 [−0.030, +0.217]**; scratch **+0.502 [+0.312, +0.693]**.

Scratch’s recede bonus is larger on both holdouts. On H13 that extra
bonus outweighs the ranking/commitment advantage:
`recede_delta = selected_delta + (bonus_mt − bonus_sc)`
= 0.156 + (0.094 − 0.502) = −0.253.

## What is established

Fixed-horizon ranking at the initial reset is better for the H10
recipe on both unused holdouts. First-action ranking at those same
resets is also better, and it does not conflict with sequence
selection there. Receding 16-step control is **not** established as
better; on H13 it is worse. Prediction/ranking at `obs0` is therefore
not a sufficient statistic for this closed-loop controller. H10/H11
200-step labels are unchanged.

## Mechanisms

**A. Rankings decay after leaving the reset.** Compatible with
excellent reset ranking plus a later recede loss. Contradicted by
nothing in the files. Insufficient: no later-state scores or
observations exist.

**B. Prediction error compounds during recede.** Compatible with
16 successive model-based decisions. Contradicted as a complete
account of the H13 recede loss: scratch is already miscalibrated by
about 13 return units at `obs0`, yet it is the arm whose recede bonus
grows. Insufficient: no recede-step residuals.

**C. Best complete-sequence ranking fails to pick an effective
feedback action.** Compatible at the controller level (ranking wins,
recede loses). Contradicted in its narrow `obs0` form: sequence
`argmax` and V(a) choose the same first action on 80/80 states. The
saved gap is not an initial sequence-versus-first-action mismatch.

**D. Recede option value or model-error exploitation.** Compatible:
recede redraws candidates every step, so a weak ranker has more room
to improve on a bad commitment. Scratch’s recede bonus is larger on
both holdouts and, on H13, beats even the best of the initial 16
committed sequences. Not distinguished from later-state scoring
changes, because recede traces were not saved.

No mechanism is established. The identified accounting identity is
that H13’s recede loss is scratch’s larger recede-over-commitment
bonus, not a reversal of initial ranking.

## Limitations

Cannot re-verify reset identity without stepping the environment.
Cannot reconstruct recede actions, occupancy, or later rankings.
Two holdouts cannot separate physics from seed noise. Spearman uses
ordinal ranks of the saved 16-vector; it is not a new experiment.

## Recommended next question (H14, not locked)

On new unused MCC physics, does **frozen-candidate recede** preserve
the ranking advantage that **redraw recede** loses?

Competing mechanisms: later-state score decay (A/B) versus per-step
candidate redraw giving option value to the weaker ranker (D).
Baselines: the frozen H10 recipe versus scratch; same reset states;
open-loop commit to the initial ranked sequence; recede with the
initial 16 candidates held fixed; recede with the H12/H13 redraw.
Independence: ten model seeds; states are not extra replications.
Smallest design: the H12 four-state grid with two recede variants
and saved per-step observations and scores. Primary remains a
predeclared return or regret interval, not a post-hoc elevation of
H13 recede.

Do not lock, authorize, or run H14 from this audit. Do not retune
H10–H13.

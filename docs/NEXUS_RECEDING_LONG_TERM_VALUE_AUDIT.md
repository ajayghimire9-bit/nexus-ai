# Receding long-term value — offline audit

Branch `cursor/receding-long-term-value-audit` from `580dfb0`. Zero new environment steps. Zero training. Confirmation closed. Nested H=8, Q/V, planning-value and receding-consistency labels are unchanged. This is not a control pass, learning-to-learn, or AGI.

## Deployed decision rule

Pendulum `RandomShootingMPC.act` draws 16 action sequences of length 16, scores each by summing **predicted** published Pendulum rewards along that **fixed** imagined trajectory (termination survival included), then executes `sequences[argmax, 0]` and replans next step. Default `uncertainty_penalty` is 0. The production recipe does **not** compute:

- Q(s, a) under future receding
- a Bellman backup V(s') ≈ max open-loop H=16 from the next state
- multi-step return targets for learning
- temporally extended actions
- updates from observed episode failures
- Bellman-consistent long-term value
- uncertainty-aware scoring (default penalty 0)

Scoring **is** state-dependent: candidates are imagined from the current observation. That is open-loop scoring from `s`, not Q(s,a) under future replanning.

Absence of a named algorithm is not proof that it is required. It is the mechanism inventory.

## Competing explanations

**H1 — Planning-objective mismatch (best supported).** The value of an open-loop 16-action plan is not the value of its first action followed by future replanning. Registered evidence: exact H=16 misses 64-step value (+34.685); sequence-best first actions are optimal in only 18/60 states (gap 20.254); nested H=8 hurt 200-step return (−174.178). The deployed `act()` still maximises the open-loop sum.

**H2 — State-dependent action-value estimation (explains closed Q failures, not the deployed rule).** Previous small Q functions used 64-step zero-replan labels and isolated visited states. Linear Q −3.535 and action-conditioned Q −4.293 both include 0. Capacity was increased once and still failed that screen. Those tests never deployed a receding 200-step controller and do not justify another larger network as the next move.

**H3 — Policy-induced distribution shift (open, not isolated).** Late executed-error growth was not established. Recede-versus-commit on 16-step return includes 0. Nested H=8 hurt complete episodes, which is compatible with H1 without isolating progressive post-choice state deterioration. Do not treat H3 as demonstrated.

## Evidence matrix (closed results)

| Study | Question | Unit | Primary | Registered | Established | Still unknown |
|---|---|---|---|---|---|---|
| Planning-value | Exact H=16 sequence vs 64-step value | 10 decoders, 8 source tasks | **+34.685 [22.677, 46.694]** | yes, `short_objective_misses_practical_value` | Complete-plan H=16 ≠ 64-step common-zero value | Not receding first-action; not 200-step |
| PCG | Prediction vs ranking | 10 decoders, one-shot states | Spearman 0.923 source student; fresh ranking improved | yes | Better one-shot ranking; fresh episodes still lost | One-shot ≠ receding episode |
| Action-value alignment | Best-sequence first action vs best of 3 first-action+replan | 10 decoders, 60 states | **20.254 [11.382, 29.127]**; optimal 18/60 | yes, `sequence_first_action_misalignment_detected` | Complete-plan value ≠ first-action/replan value | Exploratory H=16-selected regret ~15.3; not 200-step |
| Linear first-action Q | Source linear Q vs H=16 on 64-step first-action | 10 decoders | **−3.535 [−9.840, +2.769]** | yes, not established | This Q did not beat H=16 | Never a 200-step receding controller; RMSE 107.5 |
| Action-conditioned Q | Action×obs Q vs H=16 | 10 decoders, 60 cells | **−4.293 [−15.751, +7.165]** | yes, not established | More interaction terms still failed the 64-step screen | Same intervention, not full episodes |
| Terminal-value / scalar | Endpoint readout or β-scaled correction | 10 decoders | −0.221 and −9.228, both include 0 | yes | Score-correcting complete sequences did not establish better choices | Not a receding Bellman backup |
| Receding vs commit | Open-loop 16-plan vs receding, 16-step return | 10 decoders, source | **−1.787 [−4.324, +0.751]** | yes, not established | 16-step commit/recede inconclusive; search-noise 0.500 | Not 200-step |
| Late-control | Same-state late first-action student vs zero | 10 decoders, 16-step | **+0.0312 [−0.0827, +0.1452]** | yes, not separated | No deployable switch | Not 200-step |
| Nested H=8 | H=8 vs archived H=16, 200-step return | 10 decoders, 60 episodes | **−174.178 [−265.830, −82.527]** | yes, **hurts** | Shortening the open-loop objective hurt episodes; one-step MAE stayed ~0.09 | Whether a first-action Bellman backup of H=16 value helps |

Artifacts for those studies remain on disk. No new counterfactual outcomes were invented.

## Ranking of failure modes

**B — Incorrect objective (strongest).** The controller maximises imagined open-loop sequence return, then throws away actions 1…15. Exact H=16 selection already has large 64-step regret. Sequence-best first actions are often not receding-best. Nested H=8, which reduced compounding, **hurt** 200-step return for all ten decoders. The objective that is optimised is not the value of “this action, then replan.”

**D — Misaligned learning signal (why Q/V failed).** Linear and action-conditioned Q were fit to 64-step **zero-context replanning** labels at isolated visited states, then judged on the same intervention—not on 200-step same-policy receding. Source RMSE ~70, development RMSE ~96–108. Terminal-value/scalar corrected **complete-sequence** scores. Those tests did not give receding first-action value a 200-step trial, and they did not fail because NEXUS needed a bigger network as a first move.

**A — Inaccurate dynamics (real, not the H=8 cause).** Teacher-forced H=16 angular-velocity MAE is ~1.93. Reducing imagined horizon (H=8) should have reduced compounding and instead lost 174 return points while executed one-step MAE stayed small. Dynamics error exists; it does not explain why a shorter open-loop score hurt control.

**C — Limited search (contributor).** Fresh-candidate first-action switch at a fixed state is 0.500. In the H=8 test the candidate **set** was identical to H=16 and H=16 still won, so search identity was not the contrast.

**E — Adaptation/physics (insufficient here).** H=8 hurt student and zero on development. Late-episode student-minus-zero 200-step return included 0. Closed negative transfer on disjoint confirmation physics remains a separate fact.

## Why previous Q/V did not establish success

1. Wrong **intervention**: first action plus 63 zero-policy steps, not the visitor’s own receding policy for 200 steps.
2. Wrong **object**: complete-sequence score correction (terminal/scalar) versus first-action value under replanning.
3. Wrong **capacity diagnosis**: 15-coefficient linear Q underfit (RMSE 107); action×observation Q still failed the same 64-step screen—capacity was tried and did not pass.
4. No **episode deployment**: none of those readouts replaced H=16 inside a 200-step receding loop.

## One proposed mechanism

**One-step Bellman backup of the frozen H=16 open-loop value. No new network. No fitting.**

At state `s`, for each discrete action `a ∈ {0,1,2}`:

1. Predict `(s', r)` with the frozen world model (one imagined step).
2. Score the **same** 16×16 candidate array from `s'` with frozen H=16 open-loop MPC.
3. Set `Q(s,a) = r + max_k score_H16(s', seq_k)`.
4. Execute `argmax_a Q(s,a)` and replan.

It addresses the demonstrated mismatch: first actions are chosen as prefixes of the best open-loop 16-plan, not as the action with the best predicted successor value under the same planner. It differs from failed Q because it adds **zero parameters** and does not reuse 64-step zero-replan labels. It differs from terminal-value because it backs up from the **next state after a real first action**, instead of adding an endpoint readout to a complete 16-sequence. It is not another H∈{4,8,16,32} sweep.

Training signal: none. Saved first-action counterfactuals are **not** used for fitting. Generalisation to unseen physics is **not** claimed; the rule inherits whatever the frozen world model already has. Falsified if 200-step development return does not beat frozen H=16 receding by mean ≥ 25 with decoder-level lower bound > 0.

This may also **hurt**, as H=8 did. That is an allowed outcome.

## Next experiment (locked, not collected)

Protocol `docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md`. Development only. Fresh seeds `13000000+`. Both arms collected: frozen H=16 receding versus Bellman first-action backup, shared candidate arrays. Primary: Bellman minus H=16 200-step return, ten decoders, margin 25. **Authorized: false.**

Budget: **180 s**, **24,000** real steps, **12,324,000** imagined transitions, **0** optimizer updates.

Not control improvement, not learning-to-learn, not AGI.

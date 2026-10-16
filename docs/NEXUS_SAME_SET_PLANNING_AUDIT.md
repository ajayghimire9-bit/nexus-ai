# Same-set suffix replanning — offline retrospective audit

Base `16d904cf5cd38df6e4c6a2f4295ee876053f0ffa`. Branch `cursor/same-set-planning-audit`. Artifact `artifacts/same_set_planning_audit.json`. **Zero new environment steps. Zero new imagined transitions.** Score-correction closed. Confirmation unused.

This is a reconstruction of the locked 160-cell source capture. It is **not** a preregistered success and **cannot** change `replan_consistency_not_established`.

## Locked primary, unchanged

Commit-16 minus recede-fresh: **−1.787 [−4.324, +0.751]**. Label `replan_consistency_not_established`.

## Retrospective contrasts (secondary)

Same-set minus recede-fresh: **+5.442 [+3.607, +7.277]**. All ten decoder means are positive. 134 of 160 cells favor same-set. No ties.

Same-set minus commit-16: **+7.229 [+4.739, +9.718]**. All ten decoder means are positive. 156 of 160 cells favor same-set.

Student visitor same-minus-fresh: **+5.610 [+3.550, +7.670]**. Zero visitor: **+5.274 [+3.114, +7.434]**.

Per-task same-minus-fresh (decoder n=10):

- task0 **+7.060 [+3.108, +11.013]**
- task1 **+2.971 [−3.961, +9.903]** (includes 0)
- task2 **+4.386 [+0.946, +7.825]**
- task3 **+6.417 [+1.750, +11.085]**
- task4 **+6.430 [+2.138, +10.722]**
- task5 **+6.931 [+1.581, +12.280]**
- task6 **+7.354 [+1.134, +13.575]**
- task7 **+1.986 [+0.393, +3.579]**

Switch rates remain those of the parent: search-noise **0.500 [0.430, 0.570]**; state-driven suffix **0.200 [0.122, 0.278]**; recede-fresh **0.450 [0.331, 0.569]**.

## Fairness and identifiability

The source methods were **not** equal-budget controllers:

- Same-set recede imagined: **1,920** / cell, remaining horizons **15…1**, aligned with the 16-step evaluation window.
- Fresh recede imagined: **3,840** / cell, horizon **16 at every later state**, so it can optimize imagined reward after the evaluation window ends.
- Every reconstructed `C` contains all three first actions. After `π[0]`, 158/160 cells still have three distinct suffix first-actions. No duplicate full remaining suffixes. About 37% of `C` shares the selected first action.
- Saved cells store 16-step sums, the selected plan, and switch indicators. They do **not** store per-step rewards or predicted scores, so a return gap cannot be decomposed into a score gap.

H2 as “same-set had more search” is not supported: it had half the receding imagined transitions and a shorter lookahead. H2 as “evaluation-horizon mismatch” remains open and is a credible confound. H1 (useful preserved plan information) is not identified on this source screen.

Scientific status: `credible_retrospective_confounded_by_horizon_mismatch`.

## Confirmation, not started

A separate development protocol equalizes remaining-horizon candidate length for same-set versus fresh draws and compares both with production H=16 receding. Collection is unauthorized. Report `NEXUS_SAME_SET_PLANNING_PROTOCOL.md`.

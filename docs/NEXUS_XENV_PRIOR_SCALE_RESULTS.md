# Cross-environment 2× prior-data scale — results (rung 5)

## Decision

**`xenv_prior_scale_not_established`.** The predeclared primary — per-seed
mean control return over {128, 1024}, paired `xenv − scratch` — was
**−4.761 [−36.121, +26.599]** (student-t 95%, df 9, n = 10); the interval
includes 0, four of ten seeds positive on the averaged primary.

This closes the 2× prior-data configuration. Doubling source data on the
closed rung-1 `XEnvNet` did **not** establish transfer on the preregistered
average of both target budgets. The starvation hypothesis is not supported
at 2× under that rule. A 5× scale-up still exceeds the 100,000 standing
cap and is not authorized.

Secondary, never label-deciding: @128 **+23.887 [+1.150, +46.624]** (lower
bound above 0; 9/10 seeds positive; xenv −96.392 versus scratch −120.279
and reference −50.224) and @1024 **−33.409 [−89.824, +23.007]** (includes
0; xenv −18.982 versus scratch +14.427 and reference −28.639). Held-out
MAE gain @1024 was +6.54e-05 [+6.00e-06, +1.25e-04] (xenv slightly worse).
The small-budget sign must **not** be promoted to a primary, retuned, or
re-run on this holdout. A later 128-only question would need a new unused
physics draw and its own lock.

This is a valid negative result for this configuration only — not
learning-to-learn, not AGI. Target physics (0.0022, 0.0019, 0.08) and this
recipe are closed.

## Cost

**17.849 s wall** (600 s cap), **63,200 fresh real steps** (38,400 prior +
12,800 target + 12,000 evaluation), **3,072,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`5b6cb6d` (no invalid attempts). Session ledger: 222.673 + 17.849 =
240.522 s of 3600 s consumed; 3359.478 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 60-trace grid,
execution totals and forbidden-claim flags. Rule `mcc_xenv_v6` reproduced
**(0.0022, 0.0019, 0.08)**; seeds `67,000,000+` are disjoint from closed
blocks.

## Provenance

Branch `cursor/xenv-prior-scale`: lock `679189d`, authorization `5b6cb6d`,
executed once with a clean tree. Raw artifact
`artifacts/xenv_prior_scale.json` SHA256
`7b9429d116ebe75ffeb165806354ceecfa82b124ec692872132377f22177bb9a`.

## One next recommendation

Five matched-data xenv rungs at this architecture family are closed. Do
not add another FiLM variant and do not retune this holdout around the
@128 secondary. The affordable next decision is to **leave the
cross-family shared-trunk line closed at this scale**, or lock a genuinely
new question (a 128-only primary on unused physics, or a different family)
with its own protocol. Nothing here pre-authorizes either.

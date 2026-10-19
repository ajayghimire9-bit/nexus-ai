# E3.12F — final preparation v2: assignment and estimation

**Unregistered, no collection authorization, no scientific outcomes.**
Base `5952529770bd90f21c155ede81aca36433c75295`;
branch `codex/e3-12f-resource-and-estimation-review`.
This versions the prospective runtime, corrects its source-derived resource
ceiling and adds secondary estimators before any outcomes. The raw primary
estimand and BOTH-family screen remain unchanged. Earlier v1 files/artifacts
are preserved as historical engineering records; their 50-call estimate is
unsafe as an allocation bound and must not authorize a run.

## Source-derived resource proof

The SAME `full_policy_source.operation_plan` and catalogue `plan_bound` reserve
one forward per model operation, plus one real environment step. At H16:

* Parent successor: three roots, each with one root transition and sixteen
  batched transitions: **51 calls**, 1,491 imagined rows.
* Switch: either that parent or flat H16: at most **51 calls** and 1,536 rows.
* Rank blend: flat half-budget plus successor half-budget: **67 calls**
  (16+51), 1,491 rows (768+723).

This is operation metadata, not model inference, environment execution or a
timing benchmark. Both switch branches, exact threshold equality and both
observation schemas are enumerated in the audit. `verified_physical_work`
sums actual union labels; `maximum_experiment_work` uses at most twelve
paths/kind/model: eight training plus four queries. Across four models and
200-step paths, the bounds are **28,800 real**, **43,372,800 imagined**,
**1,622,400 calls/forwards**. The existing 44,236,800-row ceiling is conservative;
the former 1,440,000-call ceiling was too small by 182,400 calls.

Tests exhaust all seventy balanced overlap allocations against a fixed
balanced baseline; each fits the maximum. Public blocking is a subset of
these allocations. Runtime validation recomputes the source bound and rejects
a recipe whose caps no longer cover it. Per-decision Host reservations and
receipt instrumentation remain unchanged. Neither mean observed runtime nor
past call counts substitute for this worst-case proof.

The executable template is `configs/e3_12f_reset_blocked_runtime_v2.json`:
300 seconds, 28,800 real maximum, 44,236,800 imagined maximum and 1,622,400
model calls/forwards maximum. Numerical seeds remain null, authorization false
and allocation absent. These are corrected prospective ceilings, not an
increase to any granted allocation. Planning rule and physical paths are
unchanged. Rough extrapolation from D suggests approximately 205–250 seconds;
no new timing measurement supports a guarantee of completing inside 300s.

## Fixed primary: assignment only

All original F pairing/collection rules remain: eight fresh training resets
and four fresh queries per frozen source model; four models, two per family;
shared physical union; one assigned child plus parent revealed per reset per
assignment. Form random-balanced and minimum-public-observation-distance
blocked schedules before returns. Seal them exclusively, reproduce reset
observations, and seal all selector choices before opening query environments.
Never expose the other assignment's child or any query feedback to fitting.

Primary remains raw parent-inclusive training mean under blocked assignment
minus the SAME raw selector under random-balanced assignment. Ties retain
parent, then switch, then rank blend. Average four queries inside each model,
then paired t intervals across two models/family (df1). Both families must
have mean >=1 point, lower 95% bound >0 and both model gains >0. This remains
an exploratory finite-source-model screen, not unfamiliar-physics confirmation.

## Prespecified secondary: estimation only, no extra physical paths

For each assignment, also invoke existing `training_statistics` on the exact
same revealed rows. Parent score is zero. Each child score is its mean
paired `(child return - parent return)` on its own four assigned resets.
Choose the greatest score with the same parent-first tie rule. This is
`paired_parent_gain_v1`; it is not promoted over the primary and is not a new
learning architecture. Past gain guards failed to establish reliable benefit.

Seal raw and paired choices together. Secondary contrasts are:
blocked-paired minus random-paired; blocked-paired minus blocked-raw;
random-paired minus random-raw; and each paired selector minus fixed parent.
All intervals are unadjusted exploratory, sharing physical paths and model
units. No secondary result upgrades a failed raw-primary screen. Report the
same query mean for all selectors and fixed parent/children/uniform expected
mixture. Never treat these dependent summaries as independent experiments.

For each assignment/model report parent group means, offsets from pooled
parent, absolute parent-return imbalance, raw/paired choices and harmful-query
counts. Also report whether assignment changes raw choices, blocked-minus-
random parent imbalance and mean squared within-block observation distance.
This separates the chain: observation matching → observed return imbalance →
chosen strategy → fresh outcome. The arrows are descriptive associations,
not a causal mediation analysis. Small observation distance is not success.

## Completion, verification and boundaries

Use the SAME runner `--reset-blocked`, Host/Dispatch/ReservationLedger,
operation plans, source MLP checkpoints and source data. No StrategyGenerator
is instantiated for the raw/paired profiles; no union feedback is sent to
credit. The SAME independent stdlib exporter recomputes masked raw means,
paired gains, choices, intervals and primary label. Seal references remain in
every physical receipt; reject missing/duplicate cells, nonfinite values,
unknown work, changed model hashes, wrong rewards or cap overruns. Scientific
negative/inconclusive results require complete valid execution. Partial or
invalid results cannot become a failed scientific screen.

No models were fitted/inferred and no simulator was constructed or stepped in
this task. Unit tests use authored callbacks; bounds inspect source metadata.
Fresh seed registration, collision audit, exact committed allocation/protocol
and collection authorization remain absent. The current no-simulation limit
is preserved. Ledger unchanged: 1808.9990201649957 used /
1791.0009798350043 remaining. Main and all historical evidence stay unchanged.

Next scientific action: separately register and authorize this complete v2 F
comparison, run once inside its caps, and preserve honest outcomes. Do not
interpret one eight-reset sample as proof of repeatable learning. The next
conditional study is specified in `NEXUS_LEARNING_REPEATABILITY_PLAN.md`;
it is not executed or allocated here.

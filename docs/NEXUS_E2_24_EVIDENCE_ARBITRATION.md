# E2.24 — Evidence-weighted strategy arbitration

## Pre-development protocol

Base `3bf0a97f15f98af5e28dcf619fe8c1332eea2818`, verified after
fetching GitHub and Origin. Branch
`codex/evolution2.24-evidence-weighted-arbitration`. Two pre-existing
untracked Evolution-1 adapter files remain outside this work.

This is a recorded-source, FakeStepModel development audit, **not**
real control, scientific confirmation, learning-to-learn or AGI.
No simulator collection, neural training, checkpoint replacement,
H17 work, allocation, or E2.17 authorization reuse. Scientific ledger
remains 327.869 seconds used / 3272.131 remaining. Proxy imagined
transitions are counted separately. Source-only wall cap: 60 seconds.

Reuse `ObservationAwareAdaptive` and its memory entries,
`AdaptiveProposer`, `TrustedEvaluator`, `raw_catalogue_scores` and
`make_e222_tasks`. `ContextualStrategyMemory` remains canonical and
is not replaced. Historical modes retain their choices; only richer
optional diagnostic traces are added. No parallel framework.

### Competing explanations

Hard confidence can erase useful persistent scores; negligible
kernels can expose ties and rounding artifacts; sparse coverage can
make a missing arm's 0.5 prior attractive; observation similarity
need not predict planner quality. Arm rows are not independent tasks.
Agreement between neighbors alone need not establish applicability.
The benchmark will trace these together rather than assuming one cause.

### Frozen arbitration rule

Group historical rows by family, support digest and planning embedding.
One context contributes one weight regardless of arms or repeats.
Exclude active task provenance and unknown support identity. Distinct
support contexts are **not** independent physics replications.

For each available arm compare it with the current persistent
proposer's chosen arm using only contexts that observed both arms
and both anchor planners. No missing-arm pseudo-score. Gaussian
weights use E2.23's source LOBO median length; the distance gate is
diagnostic and cannot grant confidence. Record coverage.

Use weighted paired advantage, effective mass, ESS, positive-delta
agreement, weighted spread, and absolute prediction error on the two
current anchor receipts. Subtract source empirical paired-error
allowance, anchor error and spread/sqrt(ESS) from advantage. Override
only with at least two distinct contexts, mass >=1, ESS >=1.5,
positive agreement >=0.75, both current anchors, and positive remaining
advantage (>1e-12). Choose the largest remaining advantage, then the
existing tie order. Otherwise preserve the proposer. These sufficiency
constants are fixed design requirements, not fitted development knobs.
Reported evidence weight is mass/(1+mass) × ESS/(1+ESS) × agreement ×
coverage; it is **not a probability**, and does not reach 1 at finite
mass. It does not replace the explicit acceptance tests.

Source empirical allowance: E2.8 **train only**, bundles0/1, both
families; offsets0/32/64/96, support32. Reuse six-proposal source
receipts per context. Holding out each entire bundle, predict covered
arm-pair differences from the other bundle. Use maximum absolute
paired prediction error as the allowance (1 if unavailable). Full
source catalogue scores provide calibration truth only. Record all
residuals. This small, inspected source calibration is not a
distribution-free bound, independent task validation or proof that
anchors identify unseen task quality. It is computed before constructing
any E2.22 development task. No development outcome chooses a rule,
threshold, coefficient, or configuration.

Neighbor-consensus baseline uses paired task contexts and >=0.75
positive agreement with >=2 contexts, but omits mass, anchor-match
and calibration vetoes. This isolates consistency from applicability.

### Matched benchmark and decision criteria

Seed7, exact E2.22 task order, six proposals/two anchors/four free,
same catalogue, tied RNG order and identical score tables. Compare
persistent, E2.23 cross-bundle, ungated, consensus, evidence arbitration
and reset. Legitimate receipts update each method sequentially,
including development as historically; no hidden/future score reaches
the proposer. Full tables and unit scaling are evaluator-side proxy
oracles inherited from E2.23, not realistic hidden-control evaluation.

Familiar, zero-observation, far and collision scenarios are **already
observed development**. No p-values or generalization claim. Report
first-free regret, **actual sum over all four free slots** (E2.23's
`dev_free_regret_sum` summed first-free only), best-six, regret
differences from persist/ungated, accept/abstain, actual overrides,
posthoc correct/harmful/neutral overrides versus the same-path
proposer, anchors, coverage, effective mass, ESS, context counts,
runtime and serialized store bytes. Posthoc outcome annotations are
written after choice; never feed them back through arbitration.

Desirable outcomes are preserving familiar first-free, improving
shifted first-free versus persist, rejecting misleading retrieval
better than ungated, and genuine useful planner changes. If any
fails, label partial/negative. Abstention that ties persist is not
an adaptive improvement. Complete-grid validation precedes completion.
Historical JSON bytes are hashed and checked unchanged. No extra
planner evaluations for anchors. Count full-grid audit/calibration
scoring separately from cached six-receipt method opportunities.

### Tests and execution

Synthetic tests cover useful overrides, task disagreement, missing
arms, alias/repeat inflation, missing anchors, misleading nearest
neighbors, shuffled coordinates, negligible mass under an open gate,
policy immutability, typed receipts and replay rejection. Existing
benchmark-writer tests must be redirected to temporary paths when
run so historical result files remain byte-identical.

Commit this protocol and implementation before scoring development.
Command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution2_24_evidence_arbitration.py`.
Result: `artifacts/evolution2_24_evidence_arbitration.json`, raw traces
included. Record execution SHA, source file hashes, source calibration
hash, wall/CPU, actual fake-step calls/states, cached receipts and
memory footprint. Previous results remain unchanged.

## Results

**Negative arbitration result.** Familiar performance is preserved by
abstention, but the useful shifted first-free gain is lost. This is
not an adaptive improvement and does not justify a scientific run.

Implementation/protocol commit:
`5604c98960caff79a950f4414662dd08556c519c`.
Numerical repair and complete execution revision:
`e06cabec171e023ce636f2ce8bd30403d222ae05`.
Tracked tree was clean at complete execution; the two unrelated
untracked files were listed and preserved. Results and arithmetic
audit are separate artifacts. The audit verifies every saved source
hash against `git show` of the execution revision; the later report
and arithmetic-only audit helper are not part of outcome collection.

The complete artifact is
`artifacts/evolution2_24_evidence_arbitration.json`, SHA256
`1f0ebf62aeeb538cf664490e1aa089bf4cf3f104e5094fe96a0ad0b60064d30c`.
The arithmetic audit is
`artifacts/evolution2_24_evidence_arbitration_audit.json`.
All 302 pre-existing root JSON artifacts checked byte-identical,
including the E2.17 record and preserved failed-attempt capture.
The four historical methods reproduce E2.23's planner sequences,
scores and first-free regrets exactly.

### Numerical failure trace: pend_store_2

At the first free slot, persistent winner `fde871fd…` has raw linear
score **0.4139624318400898**, normalized **1.0**. Retrieved winner
`977fff8a…` has raw **0.39174017146016465**, normalized
**0.9276105241980802**. Distance **1.2159294183821734** is below
gate **1.5051752264349445**, while kernel length is
**0.3657802005410999**: nearest weight is only
**0.00001588146408812079**.

E2.23 gives confidence **1**. Its ridge-shrunk retrieval scores are
**0.5** for the persistent winner and **0.5000030180296033** for the
retrieved winner; these become the final scores. The microscopic
difference erases the persistent ranking, yielding proxy regret
**0.30978910241633983**. Ungated soft confidence remains
**0.00001588146408812079**; final scores are respectively
**0.9999920592679559** and **0.9276037331648271**, preserving the
better choice.

There are 12 eligible arm rows but only **two** observed historical
task contexts. The nearer context did not observe the persistent
winner. The only paired comparison comes from the farther context
(distance2.818101, weight1.66545e−26), where the retrieved candidate
actually scores **0.3148992093 below** the persistent winner. Only
60% of the ten available arms have any historical score. Four missing
arms get the legacy 0.5 default, but **none wins this first-slot
failure**; missing-arm defaults are a risk, not the proximate winner.
The persistent winner does have a far-away receipt whose weighted
contribution rounds away. Thus hard confidence, vanishing mass,
sparse **paired** coverage and inappropriate marginal-arm comparison
jointly explain this trace. Independent neighbor disagreement alone
does not explain it. The new rule abstains here.

### Matched outcomes

Each list below is familiar / shifted / collision. Regret is lower
better; best-six unit proxy score is higher better. Shifted pools one
zero-observation task with two far-observation tasks; task-level raw
rows remain available and are not independent replications.

- Persistent: first-free **0 / 0.062745 / 0.109577**;
  cumulative four-free regret **1.043963 / 1.670466 / 1.936986**;
  best-six **1 / 0.966800 / 1**.
- E2.23 cross-bundle: first-free **0.154895 / 0 / 0.109577**;
  cumulative **1.091109 / 1.372061 / 2.127628**;
  best-six **1 / 1 / 1**.
- Ungated: first-free **0 / 0 / 0.109577**;
  cumulative **1.043963 / 1.372061 / 2.127628**;
  best-six **1 / 1 / 1**.
- Neighbor consensus: first-free **0 / 0 / 0.109577**;
  cumulative **1.043963 / 1.280297 / 1.936986**;
  best-six **1 / 1 / 1**.
- Evidence arbitration: first-free **0 / 0.062745 / 0.109577**;
  cumulative **1.043963 / 1.670466 / 1.936986**;
  best-six **1 / 0.966800 / 1**.
- Reset: first-free **0.915207 / 0.616995 / 0.109577**;
  cumulative **2.579377 / 2.268258 / 1.846770**;
  best-six **0.688571 / 0.779067 / 1**.

New-minus-persist first-free is **0** in every phase. New-minus-ungated
is **0 familiar**, **+0.062745 shifted**, **0 collision**; shifted
cumulative regret is **0.298405 worse**, and best-six **0.033200 lower**.
Collision cumulative regret is **0.190642 lower** through preserving
the proposer. This is avoiding two harmful same-path overrides, not
evidence of useful retrieval. Consensus beats the new rule on shifted
first-free and cumulative regret in these known cases; it is not
independent confirmation of consensus.

Across all 40 free decisions: E2.23 accepts16/40, with ten genuine
overrides (two helpful, eight harmful); ungated accepts32/40, with
four overrides (two helpful, two harmful); consensus accepts3/40,
with three helpful overrides; the new rule accepts **0/40**, abstains
**40/40** and makes **zero** overrides. Correct/harmful means proxy
score versus the same-path inner proposer **before** receiving the
chosen receipt, not an isolated full-policy causal effect. Actual
planner changes occur in synthetic correctness tests, not the new
rule's development trajectory. Desired outcomes A is preserved;
B and D fail; C is limited to avoiding harm by abstention, not better
general adaptive strategy selection.

### Source evidence and anchor diagnostics

Source LOBO calibration has16 context signatures and260 covered
arm-pair residuals. Maximum absolute paired error is **0.046773388**,
mean **0.015098420**, nearest-source mean anchor error **0.016276533**.
These are family-default source arrays, **zero independent physics
replications**. The maximum is an empirical allowance, not a coverage
guarantee. Many possible pairs remain uncovered.

New-rule mean selected-reference anchor errors: familiar **0.011202**,
shifted **0.106876**, collision **0.142540**. Familiar decisions see two
historical context signatures on average; shifted3.667, collision4.
These counts are not ESS. In `acro_zero_1`, the best-supported positive
advantage is **0.144061**, but mass1 and ESS1 indicate a single
effectively weighted context; anchor error **0.159422** plus source
allowance leaves advantage **−0.062134**. It is refused. Far states
have no usable weighted pairs. No post-result relaxation was made.

Legacy summary `mean_contexts=0` is an uninstrumented default,
**not** evidence that legacy retrieval saw no contexts. The arithmetic
audit marks those counts unavailable. Null pair metrics mean missing
evidence, not zero error. Serialized trace fields retain mass, ESS,
coverage, anchor receipts and every candidate comparison.

### Identifiability and audit limitations

From already saved receipts, equal zero planning observations and
the same family FakeStepModel have **2**, **5**, and **5** strict
pairwise ranking reversals for zero0/zero1, zero0/collision, and
zero1/collision respectively (7,7,8 commonly evaluated arms).
`raw_catalogue_scores` uses a task-ID-hashed candidate seed; these are
changes in **realized search noise**, not changes in simulator physics.
Observation-only retrieval cannot determine these realized outcomes.
Support provenance and anchor receipts also differ, so this is not
proof that the full permitted input is identical or information-free.
The synthetic two-world test separately demonstrates the logical
limit of identical memory/observation/anchor inputs with unconstrained
future free-arm outcomes; it does not manufacture an empirical task.

The new rule's minimum evidence demands are too strong for these
sparse, concentrated histories. The source-calibrated allowance alone
does not solve planner-quality prediction. Lowering a distance threshold
or reporting softer confidence would not establish useful arbitration.
The evidence does not isolate one causal limitation or justify a real
control claim. Current-task feedback is revealed sequentially as in
the old benchmark; the proxy oracle scale and best-arm reference use
the complete evaluator-side table. No hidden score is passed to
`choose` or used to tune rules. Distinct arm rows, task contexts,
score residuals, and methods are not statistical replications.

### Resources, tests and reproduction

Complete captured run: **0.464527 wall seconds**, **0.446525 CPU seconds**;
Python3.13.5, NumPy2.5.4, local macOS arm64. Calibration computes192
proxy catalogue values (292,512 fake imagined states); matched audit
computes120 values (182,820 states), shared by all methods. Total312
proxy computations, **475,332** fake imagined states,6292 fake step
calls. Each method receives60 cached logical receipts; source
calibration additionally uses96 six-proposal receipts. These receipt
lookups are not extra simulator or model rollouts. No real interactions,
neural inference or neural training. First failed attempt's compute
was not captured; tests execute additional synthetic proxy work, so
the complete run's totals are not session totals. None debits the
scientific execution ledger. No allowance or grant is reopened.

Measured 60-receipt method-loop times: persist2.327ms, cross6.665ms,
ungated9.391ms, consensus8.165ms, evidence7.760ms, reset2.767ms. These
include bookkeeping, receipt updates and trace allocation; they are
single-pass diagnostic timings, not robust latency estimates.
New memory is60 rows /24,414 serialized bytes versus legacy52 rows /
20,901 bytes; bytes are **not** total process RSS. The new store
preserves per-context identity instead of merging equal embeddings
across provenance, another disclosed bookkeeping difference shared
by consensus and evidence modes. No capacity-equivalence claim.

Focused and relevant regression command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_evidence_arbitration.py tests/test_evolution2_observation_memory.py tests/test_evolution2_observation_memory_cross.py tests/test_evolution2_planner_adapter.py tests/test_evolution1_toy_loop.py tests/test_evolution2_evolutionary_search.py -p no:cacheprovider -o addopts='' -q`.
Result: **82 passed in 2.04s**. Additional source-only guard/ledger
regressions:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_resources.py tests/test_evolution2_cross_task_screen.py tests/test_evolution2_pendulum_acrobot_protocol_v2_pilot.py -p no:cacheprovider -o addopts='' -q`:
**55 passed in 0.13s**. Total final selected checks: **137 passed**.
Earlier pre-execution checks had12 passes; one adversarial test fixture
initially expected a veto despite an error smaller than its advantage,
and was corrected to represent genuinely misleading anchor feedback.
The tiny-kernel regression raised focused coverage to13 before complete
execution. No acceptance criterion was relaxed.
The arithmetic audit rechecks every cumulative-free sum, matched
score table, exact historical trajectories, source-at-execution hashes
and historical artifact hashes without new planning calls. Full
repository scientific/collection suites are deliberately not run.

### One next experiment

Run a **source-only LOBO paired planner-advantage prediction test** using
a candidate-conditioned quality representation: permitted candidate/
search descriptors, support transition statistics, and existing anchor
residuals, instead of observation distance alone. Compare prediction
of advantage over the incumbent against observation-only retrieval,
with held-bundle sign error and abstention assessed before any promotion.
This is a substantive strategy-quality representation test, not another
distance-gate sweep. Do not execute it as part of E2.24, collect new
experience, or reopen E2.17/H17.

### Execution instrumentation correction

First attempt at `5604c98` reached JSON serialization but failed
because raw kernel squares underflowed in ESS (0/0). No valid result
was saved; its failure record is retained separately. Normalize
weights before squaring to compute the same mathematical ESS
stably. Add a tiny-positive-kernel regression and reject nonfinite
trace fields. No scientific rule, threshold, calibration, seed or
selection mechanism was tuned. Commit this correction before the
recorded complete audit. Failed-attempt compute was not persisted;
it must not be silently reported as zero.

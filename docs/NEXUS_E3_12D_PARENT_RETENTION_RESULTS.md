# E3.12D — Parent-aware selection: complete run, advancement screen failed

Protocol/implementation committed before outcomes:
`a5d13d768ae3caefe33a7e25ef959bb5bad05447`.
Branch `codex/e3-12d-parent-retention-comparison`, based on
`32f7088824d829d36c33f41f1f8c7d3e78f8ffa9`.
One authorized run; no simulator retry, model training, new physics or
confirmation collection. Earlier results and closed seeds remain unchanged.

## Decision

`parent_retention_not_established`. Execution and integrity were complete and
valid; the scientific screen failed. Parent-aware raw averaging retained parent
on **0/4 models**, and selected exactly the same modifications as both the
two-child average and mutation-credit argmax. Its primary gain over two-child
selection was **0 [0,0]** in each family. Those degenerate intervals reflect
identical selected paths on this sample, not equivalent future expected policies.

Both primary mean≥1/lower-bound>0 tests failed. Versus uniform, means were
positive but intervals included zero in both families. Parent noninferiority
also failed: both interval lower bounds were below−1. Do not reinterpret this
as success because probabilities changed, averages were positive or tests passed.

## Fixed procedure and actual feedback

Four existing frozen residual MLP64x64 world models: two Pendulum with4868
parameters each and two Acrobot with5255 each. These are the existing E2
source models, not the earlier ten latent-decoder replications. Familiar
family-default physics; H16 typed successor parent plus existing switch and
rank_blend with fixed flat partner. Catalogue1536-row cap is not historical
16-candidate parity. No architecture, reward, normalization or weight changes.

Eight training resets/model, four exposures per child, one child plus parent
per reset. All selectors shared exactly those32 matched parent–child updates.
Parent mean used eight returns versus four per modification; ties retain parent.
Fresh query resets8..11/model each executed all three paths, after training-only
choices were sealed. No query update, inferred counterfactual training return
or learned exploration. Each physical path is counted once; selector comparisons
reuse it. Uniform is analytic expected return over the children, not another
executed controller. Fresh9648 reset/planner seeds passed the exclusion audit.

## Baseline results

Mean200-step return, averaged episodes then models separately per family:

- Pendulum: parent-aware **−241.538**; two-child mean **−241.538**; mutation
  credit **−241.538**; fixed parent **−371.792**; fixed switch **−370.367**;
  fixed rank_blend **−462.882**; uniform expected **−416.624**.
- Acrobot: parent-aware **−287.993**; two-child mean **−287.993**; mutation
  credit **−287.993**; fixed parent **−305.617**; fixed switch **−286.749**;
  fixed rank_blend **−298.824**; uniform expected **−292.787**.

Parent-aware minus comparator, paired exploratory95% intervals across the two
independently pretrained models/family (df1; not episodes):

- Two-child mean: **0 [0,0]** in both families.
- Mutation credit: **0 [0,0]** in both families.
- Uniform: Pendulum **+175.087 [−412.671,+762.845]**;
  Acrobot **+4.794 [−71.914,+81.502]**.
- Fixed parent: Pendulum **+130.255 [−3024.069,+3284.578]**;
  Acrobot **+17.625 [−15.579,+50.829]**.
- Fixed switch: Pendulum **+128.829 [−1508.102,+1765.761]**;
  Acrobot **−1.243 [−17.037,+14.551]**.
- Fixed rank_blend: Pendulum **+221.344 [−2591.104,+3033.793]**;
  Acrobot **+10.831 [−126.790,+148.452]**.

The required screen is an intersection across the primary, uniform and parent
comparisons in both families. Other intervals are unadjusted exploratory
diagnostics and do not rescue that screen. Large intervals expose extremely
limited independent replication, not proof of a reliable aggregate benefit.
Do not pool raw family return scales.

## Model-specific failures and successes

- Pendulum0 chose rank_blend: training parent/switch/blend means
  −245.996/−575.917/−130.448. Query selected **−280.006** versus parent
  **−162.010**, difference **−117.996**. Three of four query changes were
  harmful. Per-query selected-minus-parent: +2.624,−115.897,−243.773,−114.939.
- Pendulum1 chose switch: training means −159.568/−98.484/−569.536.
  Query **−203.069** versus parent **−581.574**, difference **+378.505**.
  One of four changes was harmful. Query differences:
  +279.452,+0.757,−0.900,+1234.712. The last reset contributes most of this
  model's mean advantage; no task omission or reweighting is justified.
- Acrobot0 chose switch: training means −297.695/−279.551/−300.873.
  Query **−283.529** versus parent **−303.767**, difference **+20.238**.
  All four query changes improved over parent.
- Acrobot1 chose rank_blend: training means −295.256/−311.184/−285.474.
  Query **−292.456** versus parent **−307.468**, difference **+15.012**.
  All four query changes improved over parent, but this choice lost2.486
  points to fixed switch on the model's query mean.

Four of16 selected query paths lost to parent (all Pendulum); parent retention
prevented none. Selection matched the best child on7/8 queries per family.
That does NOT mean best among all available strategies: including parent,
the selected path was best on4/8 Pendulum and7/8 Acrobot queries. These
descriptive frequencies are not independent model-training replications.
All16 query paths/results per executed condition are in the raw capture/CSV.

The predeclared paired-gain guard, reported only as a diagnostic, would keep
parent on both Pendulum models and select the same Acrobot children. Its
Pendulum mean was−371.792, below the raw selector's−241.538; protecting
Pendulum0 also forfeits the large observed Pendulum1 gain. This does not
establish that replacing raw means with that guard is a reliable fix.

## Why parent availability did not change choices

Post-run descriptive training-only decomposition, not a new fitted selector:

`child mean − overall parent mean = matched child-minus-parent mean +
parent mean on that child's reset group − overall parent mean`.

For the selected child on Pendulum0, apparent advantage over overall parent
was+115.548, yet matched advantage was−2.835; the reset-group parent offset
was+118.383. For Pendulum1 these were+61.084,−1.102,+62.186.
Thus a child can exceed the pooled eight-reset parent mean while being slightly
worse than parent on its own four matched training resets. Equal numbers of
child exposures do not guarantee equal reset difficulty. Acrobot matched gains
were+13.178/+8.387, with much smaller offsets+4.966/+1.396.

This identity explains the estimate discrepancy; it does not causally explain
the query outcomes, demonstrate a better gate, or license retuning on this
closed query sample. Four observations per child are noisy and the suite has
only two model units/family. Training sampling, model-specific strategy quality
and query distribution can all contribute. The current experiment does not
separate their contributions.

## Integrity, tests and resource accounting

Focused pre-run tests **74 passed in13.41s**. Relevant deterministic regression
**811 passed in38.70s**, using the curated module list recorded in the test
artifact, not the entire historical suite. Tested omitted model/episode/condition,
unobserved child data, incorrect choice/count/schedule, query updates/reward
corruption, nonfinite data, cap/threshold drift, profile isolation, no query
access and independent arithmetic. No scientific simulation through tests.

Actual112 complete200-step paths: training64 paths/**12800 real steps**;
query48 paths/**9600 real steps**; total**22400**. Model work:
**33662865 imagined rows,1039105 model calls,1039105 actual network forwards**.
Reservations equal completions, all unknown counters zero. One receipt for each
of22400 actual decisions independently reconciled. No fitting or weight updates;
32 mutation-credit updates are scalar feedback learning, not neural training.

Execution wall**159.001242s**, CPU**157.310811s**, peak RSS**631275520 bytes**
(about602MiB). Saved-data verification**3.579782s**, export**0.087132s**;
combined experimental/audit/export wall**162.668156s**, below300. No failed or
repeated experimental attempt. Twenty-three compressed receipt parts total
151975428 bytes. All418 previous artifact JSON files, four checkpoint hashes,
eight source-array hashes and every model/normalizer fingerprint stayed unchanged.

Session ledger carried1643.627562957004/1956.372437042996. After this run,
audit and export: **1806.2957189570038 used /1793.7042810429962 remaining**.
Raw and validation records retain their own earlier accounting stages; they
are not rewritten to add later export cost. Source Python3.13.5,NumPy2.5.4,
Torch2.14.1,Gymnasium1.4.0; one local CPU thread, no paid services.

Raw SHA256 `df2892f6f70bbca3670ba4639afc97fe54f5e2a3205f1bcc0cdd61efeaa88882`.
Files: artifacts/e3_12d_parent_retention.json, e3_12d_parent_validation.json,
e3_12d_parent_summary.json, e3_12d_parent_returns.csv,
e3_12d_parent_usage.json, e3_12d_parent_resources.part*.jsonl.gz and test record.
Commands (PYTHONPATH=src:.deps; BLAS/OMP/VECLIB thread counts1):

```text
python3 scripts/run_e3_12_mutation_control.py --parent-retention --preflight
python3 scripts/run_e3_12_mutation_control.py --parent-retention
python3 scripts/run_e3_12_mutation_control.py --parent-retention --verify
python3 scripts/summarize_e3_12_mutation_control.py --parent-retention
```

The export actually called the same module's `main(retention=True)` inside a
timed Python invocation, equivalent to that CLI. Only saved data were read;
no resimulation. Independent stdlib means, choices, intervals, screen label,
phase totals and reward sums matched (maximum reward-sum error0).

## One next scientific recommendation

Perform a separately specified **training-only reset-balance and selection-
stability audit** of the existing revealed feedback, before adding an E4 rule
or collecting more episodes. Quantify how reset-group offsets and leaving out
individual training observations change estimated parent/child ordering.
Do not use closed query outcomes to tune a new rule or label its performance.
This targets a measured estimator problem at negligible collection cost.
No such follow-up was executed here. Continual-learning, unfamiliar-model
transfer and learning-rule utility remain unestablished separate experiments.

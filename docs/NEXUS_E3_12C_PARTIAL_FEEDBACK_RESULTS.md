# E3.12C — Limited-feedback selection not established

Base76310669855e2dbbe0bb32f44d6dec447a40bc8a; branch
codex/e3-12c-limited-feedback-selection. Tested protocol/config/allocation and
implementation committed before data at **9ae94386a84ae5863776cba20f0420679711e051**.
One execution, no retuning or simulator retry. Previous E3.12/B remain closed.

## Outcome

**partial_feedback_selection_not_established.** Both families fail the
prespecified primary interval rule. This is a complete valid negative/
inconclusive scientific result, not incomplete execution.

Primary observed-child training-mean selector minus uniform expected return:
Pendulum **+87.562 [−392.932,568.056]**, model gains+125.378/+49.747;
Acrobot **+8.283 [−123.217,139.783]**, model gains+18.632/−2.066.
These positive family means do not establish reliable selection.

Existing mutation credit minus uniform: Pendulum **−37.816 [−1150.399,1074.768]**,
Acrobot **+10.349 [−94.894,115.593]**. Credit minus simple training mean is
**−125.378 [−1718.456,1467.700]** / **+2.066 [−24.190,28.323]**. No advantage
for the more elaborate credit rule is established.

All intervals are unadjusted exploratory paired t95, df1, after averaging
four query episodes within each independent model, then two models/family.
Families are not pooled as interchangeable replicas. Neither episodes nor
multiple derived selectors are independent model-training replications.

## What ran and what was revealed

Four unchanged source world models and normalization; eight training resets
and four fresh query resets/model. Each training reset executes parent plus
only one registered child, four switch/four rank_blend in a precommitted
balanced order. Thirty-two legitimate existing mean-credit updates. No unseen
child training outcomes are scored, collected or imputed.

Query panels execute parent and both operators after all selectors are frozen.
Simple raw-return mean, credit argmax, mean paired gain and paired-gain guard
share the SAME revealed training feedback. No model fitting or query updates.
Exploration order is fixed; this is explore-then-commit, not learned exploration.
Same H16 catalogue operators/1536-row per-decision upper cap; this is not
historical16-candidate-controller parity or a new-physics test.

Uniform expected return is an arithmetic50/50 episode-level mixture of two
actual paired child paths, not another executed controller or random action-
level switching. Hindsight best is a query-conditioned diagnostic, unavailable
to the learner. Their related regret/winner metrics are dependent evidence.

## All fixed controls and individual failures

Pendulum returns: raw mean **−146.941**, credit/paired-gain/guard **−272.319**,
uniform **−234.504**, fixed parent **−132.763**, fixed switch **−272.319**,
fixed blend **−196.688**. Raw mean minus parent **−14.178 [−193.992,165.636]**;
minus switch **+125.378 [−1467.700,1718.456]**; minus blend
**+49.747 [−582.343,681.836]**. Even the better child selector does not reliably
improve on the existing parent.

Acrobot returns: raw mean **−278.415**, credit/paired-gain/guard **−276.349**,
uniform **−286.698**, parent **−295.863**, fixed switch **−276.349**, fixed
blend **−297.047**. Raw mean minus parent **+17.448 [−285.724,320.620]**;
minus switch **−2.066 [−28.323,24.190]**; minus blend
**+18.632 [−218.112,255.376]**. All remain uncertain.

Per model raw-mean/credit choices: Pendulum0 blend/switch; Pendulum1 switch/
switch; Acrobot0 switch/switch; Acrobot1 blend/switch. Credit, paired-gain and
guard select switch for all4 models; their identical results are not separate
confirming evidence. Guard retains the parent in **0/4** models because all
best estimated training gains are positive. It therefore provides no protection
in this sample.

Pendulum0 query: parent−167.569, raw-mean blend−195.899, credit switch−446.655.
Credit loses250.756 points relative to raw mean and279.086 versus parent.
Pendulum1 parent−97.957 versus chosen switch−97.984. Acrobot0 parent−303.806
versus switch−262.498; Acrobot1 parent−287.920 versus raw-mean blend−294.332
and credit switch−290.199. Individual harmful choices are preserved.

## Diagnostic interpretation

On Pendulum0 the observed switch training mean is−384.278 versus blend−216.440,
yet parent-relative gains are+85.638 versus+47.088. The parent averages differ
between the two training groups (approximately−469.916 versus−263.528). Thus
absolute and parent-relative estimates rank the operators differently. Credit
and plain paired-gain agree here: this is not evidence that tanh/CPU weighting
alone caused the bad choice. Assignment imbalance and small feedback samples
are plausible concerns, not isolated causal conclusions.

Raw-mean query winner rate: Pendulum8/8, Acrobot3/8. Retrospective-best minus
uniform expected mean87.562/17.906 shows finite-bank headroom but does not
make the selector reliable. Comparing these fresh numbers with E3.12B is not
a paired causal estimate of the effect of reducing feedback.

## Integrity, resources and commands

All48 config-derived contexts,112 complete200-step paths; training64 physical
episodes/12800 steps, query48/9600, total **22400 real interactions**. Zero
additional support/probe/validation collection. No fitting, new physics,
reserved confirmation, H17 activity or historical checkpoint replacement.

Four network/normalizer fingerprints and all four checkpoint/eight source-array
hashes match before/after. All412 previous JSON files are byte-identical.
Checkpoint/source binaries are already Git-tracked; no new model binary.
Unrelated untracked evolution1 adapters remain excluded. The seed audit checks
9648 reset/planner identifiers against available historical metadata, original
arrays and conservative reservations; unavailable external history is not
asserted covered.

Metered per-decision receipts and independent forward hooks reconcile exactly:
**33666645 imagined rows /1036165 model calls and network forwards**, zero
unknown work. Physical parent reuse and derived selector metrics are not
double-counted. All registered caps pass (34406400 rows/1120000 calls).
Raw rewards/continuity/tick seeds/termination/restoration validate. Independent
stdlib arithmetic agrees on means, paired intervals and resource phase totals;
math.fsum versus recorded returns differs by0.0.

Runtime **154.395255s**, worker CPU **153.466299s**, peak RSS **700530688 bytes**,
under300s cap. Training/query path CPU85.900006/65.458819s includes receipt and
capture work. Cost-normalized credit uses saved CPU values for exact replay;
fresh timings may change preferences. Actual operator compute differs despite
equal upper budgets. Same-process dictionaries and the legacy Journal hash
namespace are not hostile-process authentication; real feedback is explicitly
tagged and backed by trusted measured paths/receipts.

Verification3.527063s; first export failed closed because validation was still
running (.021935916s), successful saved-data-only export after verification
.032815125s. **No simulation was repeated.** Carried ledger now
**1643.627562957004s used /1956.372437042996s remaining**. Python3.13.5,
NumPy2.5.4, Torch2.14.1, Gymnasium1.4.0; local CPU, library threads1.

Raw SHA256 **ab14f40308df1b09dcb5df10d57cdf38e8184a4621038e14ab84e6f430f4c76a**.
Twenty-three lossless gzip receipt parts (150968145 bytes), raw paths,
registered schedules,32 credit events, sealed choices, usage, validation,
independent summary and112-row return CSV are saved separately.

With PYTHONPATH=src:.deps, bytecode off and CPU-library threads1:

```
python3 scripts/run_e3_12_mutation_control.py --partial-feedback --preflight
python3 scripts/run_e3_12_mutation_control.py --partial-feedback
python3 scripts/run_e3_12_mutation_control.py --partial-feedback --verify
python3 scripts/summarize_e3_12_mutation_control.py --partial-feedback
```

Consumed markers prohibit collection retries. Initial relevant759 tests passed
in27.94s; focused84 passed in12.98s after the exporter/profile-isolation change.
Final full relevant regression recorded in e3_12c_partial_test_report.json.
These source-only fixtures do not construct scientific worlds or fit networks;
the suite is the curated prior modules plus E3.12/B/C, not every historical test.

## Latest user direction and one next comparison

The subsequently supplied request prioritizes a **simple three-way training
average over keep-parent/switch/rank_blend**, which differs from C's paired-gain
guard. Preserve C unchanged; implement that selector and retain this two-child
rule as a comparison. Prepare a fresh limited-feedback, parent-inclusive
protocol. Do not score the new rule retrospectively on C query outcomes or
launch another simulator experiment automatically. Parallel persistence,
net-progress scheduler and viewer work are engineering, not new learning evidence.

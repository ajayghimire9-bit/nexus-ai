# Parent retention, durable learning state and recorded Learning Lab

Engineering branch: `codex/parent-retention-and-durable-learning`.
Starting revision: `67a0a9d6a945d4adc86f4ff30b6aadef810c5da6`, pushed E3.12C
results, following precommitted implementation `9ae94386a84ae5863776cba20f0420679711e051`.
This document records engineering work and a **proposal**, not a new scientific
execution or authorization. E3.12C and all earlier outcomes remain closed.

## What the latest evidence does and does not say

E3.12C's raw two-child mean minus uniform was +87.562
[−392.932,568.056] on Pendulum and +8.283 [−123.217,139.783] on Acrobot.
Both screens failed. Credit chose switch on all four models; its paired-gain
guard also chose switch everywhere and never kept the parent. On Pendulum
model 0, credit lost 250.756 points relative to the raw-mean selector and
279.086 relative to parent. This is not evidence that a new parent-inclusive
rule works. No new rule is scored on those closed query outcomes here.

## Implemented selector

Extend **the existing** `partial_feedback.py`, retaining `decide()`'s historical
output. `training_statistics()` centralizes exactly the same registered,
revealed-training checks. `parent_inclusive_decision()` returns:

- Parent's mean observed return across eight training resets.
- Switch and rank-blend means across their four observed resets each.
- The highest of these three means, breaking ties parent, switch, rank blend.
- The original two-child raw-mean choice, observation counts and training hash.

No confidence gate, query labels, imputed outcomes, neural predictor, new
memory or planner. Eight parent observations do not have the same uncertainty
as four child observations. The balanced child schedule also does not remove
random reset-difficulty imbalance. These are limitations to measure, not
reasons to silently change the selector after seeing results.

## Proposed fresh experiment — E3.12D, NOT registered or executed

Executable JSON specification: `configs/e3_12d_parent_retention_proposal.json`.
It explicitly has no numerical environment seeds, allocation or authorization.
It is not an executable grant for the existing scientific runner. Before any
collection, bind a separate runner profile, register and audit fresh seeds and
balanced schedules against all closed blocks, pin implementation/protocol/config
hashes, test independent replay/export, and commit an exact allocation.
Do not reuse C's query sample or revise its recorded conclusions.

Question: does allowing the unchanged parent improve fresh-episode selection
with limited, shared training feedback? Alternatives: noisy raw means fail to
identify useful changes; or parent retention reduces harmful changes but also
forgoes useful gains. Deliberate exploration is separate from exploitation.

Keep the same four verified frozen source MLPs, source data, normalization,
reward, anchors and compositions. Catalogue H16 cap1536 is **not** the older
16-candidate controller's budget. No new physics, model training or confirmation.
Each model receives eight independent training resets: parent plus exactly
one child, four switch and four rank-blend exposures in a precommitted balanced
schedule. Every learning comparator gets exactly that feedback. Fit and freeze
all choices before any of four fresh query resets per model. Collect the three
query paths from identical cloned states and paired planner seeds; share these
physical outcomes when assessing selectors, never count them as extra samples.

Primary: parent-inclusive raw mean minus existing two-child raw mean. Additional
comparisons: existing structural credit argmax, analytic uniform-over-children
expected return and fixed parent. Record all per-reset returns, harmful changes
relative to parent, parent retention frequency, model choices and their training
receipts. Uniform expectation is a dependent arithmetic comparator, not an
extra executed controller. Never feed query results into mutation credit.

Proposed screen, to freeze unchanged or explicitly revise **before collection**:
on each family, mean primary gain at least 1 return point with paired 95% CI
lower bound above zero; also gain versus uniform at least 1 with lower bound
above zero; parent noninferiority lower bound above −1 point. All conditions
must pass, all planned cells must be complete/finite, all frozen inputs must be
unchanged. This intersection screen is conservative; exploratory other intervals
are unadjusted and cannot rescue a failed primary screen. Pair within model,
average resets inside each model, then use the existing paired t interval across
the **two independently pretrained models per family**, df1. Do not pool raw
Pendulum and Acrobot return scales, or treat reset paths as model replications.
This tiny familiar-source suite cannot establish generalization.

Proposed maximum: 22,400 real steps = four models ×
(eight training resets × two paths + four query resets × three paths) ×200.
At most 34,406,400 imagined rows and 1,120,000 model calls/forwards. Reserve
300 seconds, no automatic retries. C measured 154.395 seconds for the same
physical grid; allow roughly 3–5 minutes locally including audit/export, with
file I/O and machine load uncertain. No budget has been allocated for D.
Standing ledger remains 1643.627562957004 used /1956.372437042996 remaining.
Missing or capped results must be incomplete; integrity failures invalid;
complete failures and intervals including zero are scientific negative or
inconclusive evidence, never incomplete merely because they are unfavorable.

Generalization is subsequent and separate: (1) independently trained world
models in familiar environments; (2) changed dynamics with frozen selection
recipe. An unfamiliar model starts from a permitted source prior and earns
updates through budgeted feedback; its true average returns are not inputs.
Neither study is registered, funded or executed here.

## Durable state in the existing learning cycle

`cycle_checkpoint.py` is a versioned JSON **codec**, not another memory database.
It serializes the existing LearningCycle, TaskStream, StrategyGenerator,
AdaptiveProposer and EpsilonGreedyController: weights, update/evidence counts,
mutation preferences, typed strategy definitions, all RNG streams/tie order,
deduplication sets, journals, task, choice/cost counters, training incumbents,
independent fixture promotion history and rollback archive. No pickle, arbitrary
imports, executable generated code or stored credentials. Strategy leaves are
resolved only against the vetted catalogue. Journals are verified on restore.

Save exclusively to a new path with explicit provenance. Load requires the
externally recorded SHA256 and identical provenance, catalogue and source-code
hashes. Refuse unsettled pending feedback, changed source, nonfinite state,
unknown classes/fields and hash mismatches. Restoring does not create an
execution grant or refill the saved choice/cost allowance. The fixture audit
key is public test-only; a matching hash is not an independent security signature.
Files are not an adversarial privilege boundary. No production scientific
executor checkpoint or general persistent-memory advantage is claimed.

Example API (authored fixtures only):

```python
from nexus.evolution2.cycle_checkpoint import save_cycle, load_cycle
sha = save_cycle(cycle, 'session-001.json', provenance=recipe)
cycle = load_cycle('session-001.json', expected_sha256=sha, provenance=recipe)
```

The trusted fixture host is separate from learned state: restarting it must
also preserve its evaluation-call accounting if running a budgeted study.
The codec does not restore or authorize an evaluator. Tests compare exact
uninterrupted A→B→A→C with A→B→Python restart→A→C for persistent, reset,
shuffled and random-generation controls. These are deterministic functional
checks, **not** evidence of faster relearning or less forgetting. A future
retention study must budget all training, gate, audit and query calls equally.

## Versioned secondary objective

Default `historical_pair_gain` remains unchanged so old artifacts and replay
arithmetic retain their meaning. Opt-in `training_incumbent_progress_v1`
compares each candidate against the current accepted **training** incumbent
for that task, rather than repeatedly crediting a known anchor–child gain.
Only positive net training-incumbent improvement from a previously unseen
task/strategy pair earns discovery credit. Evidence gathering and repeat
discoveries earn zero. All attempts reserve three training utility units
instead of two, covering incumbent/parent/child measurement even when one
value can be reused; failures and repeated proposals retain this reservation.
Counts are fixture units, not seconds or real interactions.

The training incumbent and independently assessed deployed incumbent are
explicitly distinct. Development/audit outcomes, including promotion booleans,
must not become training rewards. The existing assessment still decides
deployment and rollback separately. Thus this objective fixes **training
discovery credit**, not a claim that the deployed policy improved. A direct
deployed-incumbent objective would require a separately designed legitimate
feedback boundary; covertly using its hidden gate would leak information.
Existing mean/recent/conservative mutation rules are preserved; no new rule or
benchmark is introduced. Tests perturb hidden assessment while holding training
fixed and require identical learning updates. General usefulness is untested.

Two small integrity fixes accompany this work. Attempt IDs use consumed choice
count, so a failed attempt cannot collide with the next ID after restart.
The existing scientific runner now exits unsuccessfully if parent-side input
preservation or completeness checks fail even when its worker exits zero.
Neither change reruns a scientific experiment or alters a historical result.

## Existing Learning Lab

Reuse `learning_lab.py`, `run_learning_lab.py`, its HTML and offline builder.
The new allowlisted `/api/operators` reads verified E3.12B raw/validation/config
hashes, checks the config-derived grid and recorded reward sums, and displays
training feedback, recorded choices, actual query returns, parent differences,
harmful changes and all three trajectories. It never fits a new selector or
executes models. Authored fixture demonstrations remain visibly separate.

The server now handles idle browser preconnections without blocking other
requests. Opt-in fixture POSTs use a fixed child command with a killable
two-second limit instead of main-thread signals; ten-request and local-origin
guards remain. No arbitrary command or scientific backend is exposed.

Repeatable checks (set `PYTHONPATH=src:.deps` and CPU thread variables to1):

```text
python3 scripts/check_learning_lab_launch.py
python3 scripts/run_learning_lab.py --port 8766 --max-runtime-s 900
NEXUS_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/check_learning_lab_browser.cjs http://127.0.0.1:8766
python3 scripts/build_learning_lab_app.py
```

Browser QA uses installed Chrome with a separate temporary profile, not a
mock DOM. Checked both captures, filtering, query choice detail, recorded
trajectory scrubbing and disabled live execution. Offline output has a new
name, `artifacts/nexus_learning_lab_parent_replay.html`; historical HTML stays
unchanged. No hosting/deployment was requested or performed.

## Scientific status

Implementation and deterministic checks do not establish useful learning.
No new simulator episode, imagined model transition, neural inference or
training was executed for these engineering changes. Historical source-result
inspection is cached reuse. C's negative/inconclusive result is preserved.
The next scientific action is the separately registered fresh parent-inclusive
limited-feedback comparison above, not more strategies or a larger architecture.

## Verification record

Initial focused contracts: 91 passed; expanded focused contracts: 99 passed.
Broad deterministic regression before the final exit-status check: 786 passed
in 33.25 seconds. Final commands/results and reviewed file hashes are recorded
in `artifacts/parent_retention_engineering_verification.json` after the
implementation commit. The regression set is the existing curated module list
in `artifacts/bounded_learning_cycle_test_report.json`, plus E3.12/B/C and the
new focused module; it is not a claim to have run every historical test.
Actual Chrome 155.0.8059.84 passed all five recorded-view interaction checks
with zero page errors. A repeated local launch check also passed with an idle
preconnected socket. No new scientific model inference, training or simulator
work was authorized by those UI/fixture checks.

# E3.12 — Measured structural mutation credit, development protocol v1

Starting revision b94ed9132762d064f77445e9d0ef92b640334e08, fetched GitHub;
branch codex/e3-12-measured-mutation-credit. The two unrelated untracked
evolution1 adapter files are preserved and excluded. Main stays unchanged.

## Question and competing hypotheses

Does observed parent–child return credit improve subsequent structural
proposals over uniform mutation choice on fresh source-control episodes?
Alternatives: feedback helps; feedback is too noisy/sparse; these two operators
have no stable relative advantage. The preceding authored-fixture study failed
all practical screens. It is not training feedback or evidence for this test.

## Locked mechanism and data boundaries

Use the four original CPU residual MLP checkpoints (two per family), source
normalization and source physics from the pinned E3.9 inventory. Verify all four
checkpoints and eight source arrays before/after. No fitting neural weights,
new physics, confirmation access, or historical artifact changes. This tests
held-out episodes of already inspected source physics, not unseen-family transfer.

Reuse StrategyGenerator mean mutation credit, measured_mutation's trusted-path
bridge, generated_strategies.execute, full_policy_source.operation_plan,
TaskSpec/rewards, post_probe.Host/Dispatch, ForwardCheckedStep and E1
ReservationLedger. None is replaced; no new learner/memory/meter stack.

Parent is the existing successor H16 anchor, partner the existing flat H16
anchor. Generate switch(parent,partner,threshold=.25) or canonical rank_blend.
These are existing executable grammar behaviors; no novelty claim is made.
Both methods fix these identical leaves and threshold, isolating structural
kind credit. Learned uses existing softmax mean credit. Random stays .5/.5.
Same precomputed uniform per model/episode; no leaf adaptation, grid search,
temperature changes, extra exploration or quality predictor. Initial .5/.5.

Eight sequential training pairs per method/model, then four fresh evaluation
episodes with frozen proposal probabilities. Credit is exactly
tanh((child_return-parent_return)/100)/(1+parent_CPU_s+child_CPU_s), averaged
within operator and softmaxed. CPU noise is retained, not tuned away. Replay
uses the saved measured CPU values. Only legitimate training returns update
the generator; test returns never enter an update. All choices and before-state
are recorded before each path. Episode horizon200 in bridge metadata means
real return length; planner horizon remains16.

Parent executes once per paired context, explicitly reused by both training
methods (logical shared reference; no repeated physical charge). Children
execute separately even when identical: same environment reset and per-tick
planner seeds. Evaluation additionally executes fixed rank_blend. No free
duplicate child evaluation. Each learner gets eight training and four query
opportunities with same1536 per-decision upper cap. Actual rows/calls and CPU
can differ by operator; equal opportunities are not equal FLOPs.

All160 full episodes run200 decisions,32,000 real steps. Training19,200;
evaluation12,800. No probes/support collection/validation interactions, no
simulator queries outside recorded actual paths. Every step has a pre-call
reservation. Upper49,152,000 imagined rows and1,600,000 calls/forwards; actual
metered work reported separately. No changes to planner/reward/action logic.

## Registration

Executable config is configs/e3_12_mutation_control.json. For family index f,
model b, episode e: offset=f*100000+b*20000+e*1000; reset=2151000000+offset;
planner=2152000000+offset+tick, tick0..199. Train e0..7, query e8..11.
Proposal uniform is NumPy SeedSequence([73512,f,b,e]); no learner input from
reset IDs or physics. These RNG identifiers are not additional model replicas.
Audit all existing artifact/config seed metadata, original source-array seeds,
conservative H17 reservations. Unavailable external history remains a coverage
limitation. Closed E3.11/11B/11D seeds and consumed grants remain closed.

## Primary analysis and decision

For each model, average query child returns over four episodes, then compute
learned-minus-random. Report separately per family, averaging the two independently
pretrained models; exploratory two-sided t95 interval df1 (critical12.7062047364).
Do not pool families into four exchangeable models or count episodes/proposal
draws as independent models. Secondary learned-minus-parent and fixed_blend,
training curves, actual mutation probabilities and changes of selected kind.
All intervals unadjusted exploratory. Primary practical screen requires BOTH
families: mean gain>=1 point, both model gains>0 and interval lower>0. Otherwise
use useful_mutation_learning_not_established. This is intentionally a small
development screen, not confirmation or proof of learning-to-learn.

No outcome-based candidate/hyperparameter changes or reruns. Fixed baselines
must be reported even if random is weak. If the methods choose identical query
strategies, report that explicitly rather than calling unchanged preferences
useful. Feedback changing probabilities alone is not success.

## Integrity and resources

Full exact seed/model/phase/condition/tick grid, finite transitions/rewards,
reward replay, frozen networks/RMS, training-only update replay and observed
forward/journal sums must pass before declared_complete. Missing/failed cells
are incomplete_or_invalid, distinct from scientific negative/inconclusive.
Save partial raw transitions and active path metadata on failure; no automatic
retry. Timeout-killed in-flight work is an upper-bound uncertainty, never zero.

600-second hard parent timeout (estimated200–400s from closed runner timing),
local CPU single-thread. Standing2026-10-16 authority; session carry
1024.6735364600015s used,2575.3264635399983s remaining. No expired grant reuse.
Exact config/protocol/allocation hashes and clean source commit are recorded
before worker launch. Commit tested implementation/protocol before collection;
commit results separately and push without merging. Preserve all historical
JSON byte hashes and frozen inputs. Verification uses saved data only.

If unsuccessful, inspect whether proposal probabilities actually separate the
two kinds and whether measured parent–child gains are stable across training
and query episodes. Do not automatically expand architectures or training.

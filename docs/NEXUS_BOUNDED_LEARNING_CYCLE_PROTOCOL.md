# Bounded learning-cycle implementation and fixture benchmark

Branch codex/bounded-learning-cycle-and-lab from GitHub/local
aafc42cc6aee7280a10a8b0c77d84c985fbc6f9d. This protocol is committed with
tested code before running the fixture benchmark. No historical results change.

## Scope and claims

The user requests E3.11C/E3.12–14/E4.0–4.1 and a usable Learning Lab. The
requested longer-horizon comparison already ran as E3.11D and failed both
screens; preserve it, do not rerun it under C. This milestone implements and
exercises bounded integration, not six independently confirmed capabilities.
Actual environment-learning success criteria remain unverified.

measured_mutation.observe_measured_pair is also implemented: it derives credit
from complete actual reward paths only when matched protocol/checkpoint/reward
hashes and completed real-interaction receipts agree. It collects nothing and
does not make untrusted caller dictionaries into independent attestation.
No new real parent–child study is run in this milestone.

Use SAME StrategyGenerator/AdaptiveProposer, TaskStream, EpsilonGreedyController,
FixtureCost, Journal and FixturePromotionHarness. ContextualStrategyMemory stays
the existing contextual-memory implementation, not replaced by another database.
The cycle adapter retains these existing objects across tasks, not a parallel
RL framework. No arbitrary Python generation, code execution, neural fitting,
world-model inference or new scientific simulator interactions.

## Implemented mechanism

Structural credit is opt-in and accepts explicitly tagged synthetic utility
only in synthetic_fixture domain. Default real-environment contract continues
requiring observed matched full-policy TRAINING returns; forecasts/query labels
cannot masquerade as observed returns. Both parent and child are evaluated with
equal declared fixture cost; failed evaluations are charged before dispatch.

Three vetted updates: original running mean; exponentially weighted recency
alpha.25; conservative clipping of credit at±.1. Recency uses bounded.1 random
mutation exploration, other rules0. No changes to neural optimizers/checkpoints.
The existing meta-controller selects a rule using permitted training improvement
per declared cost. Select/freeze the rule before D/E/F transfer, no query or
development values update that selector. This is a finite bandit over rules,
not a demonstrated general learning-to-learn algorithm.

TaskStream chooses test_challenger, refine_strategy, gather_evidence or stop.
Refinement composes a training-selected parent with a vetted leaf; generation
uses existing catalogue operators. Evidence measures a training incumbent
against an anchor, has zero direct improvement credit and is not secretly
counted as strategy invention. No value-of-information success is presumed.
The scheduler observes gain per declared fixture cost; adaptive may stop early.

An independent development gate selects a deployed typed strategy with>=.05
utility gain. Separate audit can roll it back to the exact previous accepted
typed strategy via the existing promotion harness. Negative training experience
remains in memory/journal; rollback does not erase attempts. Development/audit
values never update generator/rule/scheduler statistics or training parents.
Snapshots bind strategy fingerprint through context_state_hash and a catalogue
leaf through variant_id; these are fixture references, not model checkpoints.
Same-process audit keys are contracts, not a hostile-code security sandbox.

## Bounded comparative benchmark

Executable source of truth configs/bounded_learning_cycle.json. Twelve paired
procedural fixture banks/seeds7–18; eleven methods (exact list in config).
Each A→B→A→C training stream has at most16 choices, four/task; D→E→F then
has at most12 choices with frozen rule. Source and transfer task coefficients
are disjoint deterministic hashes. They share an authored utility function,
not independent real environment families. Query phase perturbations are never
fit labels. Frozen proposal probes use copied generators so evaluation cannot
advance learning RNG or state. Each probe samples8 proposals, equally across
methods. Returning-A and retained-A queries are descriptive repeated assessments,
not untouched confirmations. Complete fixture source is public; no secrecy claim.

IMPORTANT: FixtureHost scores strategy descriptors with authored coefficients.
It does NOT execute planners or measure actual controller return. Existing
adapter tests separately check generated strategies are executable. Utility
scores and declared cost units are not environmental returns/CPU seconds;
transport cpu_s=1 per fixture evaluation is explicitly a fixture-unit convention.
Actual wall/CPU are measured separately. Do not promote fixture outcomes to
scientific control, transferable strategy discovery or genuine L2L claims.

Generation-only/random-generation/fixed-generation share fixed schedules and
mean updates for a matched16-attempt source comparison. Other ablations isolate
reset/shuffled proposal/scheduler memory, random/fixed scheduling, fixed/random
rule selection and reversed paired-feedback assignment. Training cost caps
are equal; adaptive stopping can spend less, so report actual opportunities and
costs rather than claiming equal executed counts or perfectly matched FLOPs.

Report raw attempts/lineage, gain, cost, proposals before/after credit, gates,
rollback, held-out proposal utility, deployed utility, return-A adaptation and
retained-A loss after B. Statistical units:12 independently generated fixture
banks paired by seed, NOT trained models or task episodes. Exploratory t95 df11
critical2.2009851601, no scientific generalization inference.

Fixture screens, evaluated separately: E3.12 generation-only transfer proposal
utility versus random generation>=.02 with interval lower>0; E3.13 return-A
after-training utility versus reset>=.02/lower>0 plus mean retained-A loss after
B<=.05; E3.14 effective training gain/cost versus both random/fixed schedules
>=.02/lower>0; E4.0 transfer proposal utility versus fixed/random updates each
>=.02/lower>0; E4.1 deployed transfer improvement versus fixed generation
>=.02/lower>0. Report shuffled ablations and every failure. Intersection criteria
are fixed in advance, intervals exploratory; neither passing code tests nor an
authored screen alone establishes any corresponding real-world capability.

## Limits, provenance and product

One source-only fixture run, cap60s local CPU under standing grant; session
ledger1020.1172516680078 used/2579.882748331992 remaining. Per host256 authored
utility calls, separate training/transfer hosts; max132 runs×512=67584 fixture
calls total,0 real/imagined transitions or neural inference. Save partials if
cap reached; no silent grid reduction/retry. Hash config/protocol/code and all
previous research JSON, preserve scientific ledger history and frozen inputs.

Learning Lab is repository-local only, preserving the existing offline viewer.
Use existing verified E3.11B/D captures for selectable Pendulum/Acrobot replay,
and an explicitly labeled controlled fixture playground. Live scientific
simulation remains unavailable. Local stdlib backend binds loopback, whitelists
routes/options, caps body size/requests/runtime, forbids shell/file-path inputs
and rejects cross-origin POST. No public hosting, paid service or external app.
Same-process fixture state is bounded; durable cross-session learned checkpoints
and a real metered experimentation backend remain future work.

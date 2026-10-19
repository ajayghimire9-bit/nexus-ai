# Fixed-policy fresh-episode source replication — protocol v1

Base `eff0100690fd82aa22b157a28fc58bbc38a51dc3`, verified locally and on
GitHub before branching `codex/unified-full-policy-replication`. Protocol
committed before outcomes. User requested continuation; standing local grant
dated2026-10-16 covers this separate bounded exploratory experiment. No consumed
allocation is reused. Session carries383.939872001008 seconds used,3216.060127999
remaining; actual experiment and offline-audit wall time are debited.

## Hypotheses and scope

H-repeat: the fixed rank composition retains a mean Acrobot return advantage
over both unchanged anchors on new episodes. Competing explanation: earlier
advantage was episode/reset variability. Independently report whether the earlier
Pendulum loss versus successor persists, disappears or reverses. Neither
direction is assumed true. Previous source outcomes are inspected development
evidence, not an untouched task or model confirmation.

This adds four new resets per existing model, not new independent world-model
training seeds. No learner/proposer is trained. No neural weights, normalizers,
policy composition, reward, physics or planning operators change. No MPC sweep,
new physics, old evaluation rerun, confirmation access, H17 or E2.17 execution.

## Fixed design

Reuse `evolution2.full_policy_source` with a second exact locked profile, its
TaskSpec/wrappers, disposable_model loader, generated_strategies.execute,
catalogue/plan_bound and ReservationLedger. Do not replace their implementations
or create another proposer/memory/meter. Reuse the offline journal verifier with
an explicit new journal path. Historical artifacts remain byte-identical.

Four existing E2.9 residual MLP files: Pendulum and Acrobot bundles0,1; verify
manifest/checkpoint/source-array hashes before any environment construction.
Verify parent capture, validation and resource-journal hashes. All model
parameters/buffers and RMS statistics frozen and hashed before/after. No new
teacher targets, support transitions, fine-tuning or changed normalization.

Three policies: flat anchor; successor anchor; existing anchor rank blend.
The switch is excluded prospectively from this smaller question. All policy
definitions are identical to the previous run, including tie behavior and IID
candidate generation. H=16,1536 imagined-state ceiling per decision. Flat gets
96 sequences; successor31 tails per action; blend splits768/768 and combines
flat48 with successor15 tails. This is not historical H16×16. Actual states/calls
differ and are reported, even though the ceilings are equal.

Same source family defaults: Pendulum(10,1,1), discrete torques(-2,0,2), current
state published reward; Acrobot masses1/1,length1, other defaults, dense successor
height, goal termination disabled, TimeLimit200. No family-unit return pooling.
48 complete200-step episodes:2families×2models×4resets×3controllers.

## Fresh deterministic seeds

Executable source of truth `configs/unified_full_policy_replication.json`,
strictly validated against the known profile. For family index f=0,1, bundle
b=0,1 and episode e=0,1,2,3:

- Reset=2105000000+10000f+100b+e.
- Planner at tick t=2106000000+10000f+1000b+200e+t, t=0..199.

16 unique reset and3200 planner seeds, paired across the three policies.
Before construction, reject collisions in current-tree historical JSON seed
metadata, E2.8 NPZ env_seeds and the preserved H17 conservative reservation
ranges. This does not establish coverage of inaccessible external runs. Pair
initial-observation hashes and every planner seed. Do not select seeds from
performance. After use, this episode sample is closed.

## Analysis declared before collection

Primary descriptive contrasts: rank blend minus each anchor separately in each
family (four comparisons). For each model average all four paired episode
differences, then average the two model means with equal weights. Report both
model means, all episode returns/differences, per-controller mean and latency.
No pooling episodes as model replications, no pooled cross-family return/CI.

Acrobot directional replication screen: both mean advantages>=1 raw return point
and both model-level differences>0 against each anchor. Pendulum harm screen
versus successor: mean<=−1 and both model-level differences<0. Report each screen
separately. A failed screen is not equivalence and cannot be promoted by a
secondary metric. Also reproduce the previous cross-family rank advantage point
screen descriptively. With n=2 shared frozen models/family, no inferential
control-success label or claim of model/generalization replication is allowed.

No hyperparameter, policy or feedback update from these outcomes. Comparing old
and new point estimates is descriptive; do not choose a winner using their
pooled union. Neither a positive episode replication nor varied full-policy
rewards demonstrate useful autonomous strategy learning.

## Caps, validation and stopping

One run, local CPU single Torch thread; cap180 seconds wall/CPU (expected60–90s),
9600 new real interactions,14,745,600 imagined states. Actual nominal model calls
428800 if complete. Each model batch and env.step is pre-reserved through the
existing ledger; failed work remains charged. Overall per-call time/work checks
are a trusted-host boundary, not an OS sandbox. E1 journal format retains its
inherited synthetic_fixture chain tag without changing the actual step source.
Save full journals and every observed reward/action/next-state. Reward check
tolerance1e−5 reflects hidden float64 simulator state observed as float32.

Exact48×200 finite grid, paired resets/seeds, continuity, scheduled truncation,
unchanged model hashes, full resource reconciliation and all historical JSON
preserved are required for declared_complete. Missing cells, reused seeds,
checksum/architecture discrepancy, deadline or unknown work yield incomplete/
invalid execution, not a scientific negative. No automatic retry, budget
reduction or silent episode omission. Record raw partial outcomes if stopped.

Source-only tests before commit/run: original-profile regression, disjoint new
seed schedule, four-episode/model aggregation, directional model-consistency,
missing cells/NaN/pairing, strict caps/configuration and existing reward/resource
tests. No simulator smoke run. Commit protocol/allocation/implementation first.

Execute `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_full_policy_replication.py`. Then `--audit` independently
rechecks saved data with zero new simulation/inference; conservatively debit
its wall time too. Save code/config/parent/checkpoint/source hashes, dependency
versions, frozen fingerprints, raw results and journals; report complete or
partial honestly. Commit results separately and push; main unchanged.

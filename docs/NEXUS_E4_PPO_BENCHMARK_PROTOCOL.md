# E4 five-family scratch PPO benchmark — locked development pilot v1

Base `b2ae7ac9da70ee8aff2a54f65f039181fa33e4ac`; branch
`codex/e4-five-family-ppo-benchmark`. Direct human authorization:
“Register and lock the five-family PPO benchmark, run it once within
300 seconds and84,840 interactions, then push the code and honest results.”
This is a NEW one-run allocation, not E3.12F or any consumed historical grant.
Preserve unrelated untracked Evolution-1 adapter files. Never modify main.

## Question and competing outcomes

Does the SAME short, ordinary PPO scratch-training procedure outperform both
random and fixed-index-zero policies on each of five known source/default
tasks, when judged on new paired episode resets? It may learn useful behavior
in some families and fail in others due to budget, optimization or observation/
reward differences. Passing APIs does not imply useful learning. No transfer,
meta-learning, continual-learning, architecture-search or unseen-physics claim.
No world-model/encoder checkpoint from previous research is loaded or fitted.

## Executable configuration and reuse

Single recipe: `configs/e4_ppo_benchmark.json`. Reuse SAME `PPOTrainer.collect`
and `.update`, actor–critic/factory/GAE, `tasks.benchmark` contract and PPO
binding, TaskSpec/wrappers, `post_probe.Host`, Evolution-1 ReservationLedger
and existing lossless DecisionJournal. No second learner, memory or controller.
All trusted source/config/protocol hashes are pinned by the allocation before
run; clean tracked Git revision required. Source-only tests use authored worlds.

The five families and exact default physical tuples are serialized in config.
CartPole uses native +1 reward, failure termination, max500. MountainCar and
continuous MountainCar use the existing dense successor `sin(3*position)`
reward, suppressed goal termination, max200. Continuous force is discretized
as−1,0,+1 by the existing adapter/gravity patch. Pendulum uses native cost,
three torques−2,0,+2, max200. Acrobot uses existing dense successor height,
suppressed goal termination, max200. Keep all native timeout flags distinct
from true termination. These are NOT all standard Gym sparse-reward benchmarks.

Fifteen new independently initialized policies: three seeds for EACH family.
Same64×64 tanh shared actor–critic; no residual/LayerNorm/dropout/new activation.
Adam3e−4, eps1e−5; gamma.99, GAE.95, clip.2, entropy.01, value coefficient.5,
max gradient norm.5; observation normalization off, advantage normalization on.
One CPU vector environment, rollout128,4 epochs,4 minibatches,4096 actual
training transitions:32 rollout/update iterations and512 Adam steps/model.
No best-checkpoint selection, LR anneal, early success stopping or tuning.
Use final checkpoint for every model. Fix Torch/BLAS threads1 and deterministic
Torch algorithms. Family-specific input/output sizes and independent weights
are necessary; no weight sharing across incompatible spaces.

Explicit **SameStep** vector autoreset eliminates dummy reset slots. This is
an API/accounting choice fixed before data, not a learned algorithm change.
Verify each128-slot batch contains128 actual steps and all valid masks are1.
Use existing GAE bootstrap from true final observations on truncation and
zero bootstrap on termination. Constructor resets use model seed with no steps;
reset again to registered training seed before the first rollout. Later
training episode resets continue that RNG rather than reseeding.

## Fresh reset streams and isolation

Numerical source of truth is config.seed_base2125000000 plus family index×10000
and replicate index×100. Model seed+0, training initial reset+10, evaluation
resets+20/+21, random-policy streams+30/+31. Ninety explicit seeds are unique;
construction/reset reuse of model seed is declared, contains no interactions.
Preserve all closed seeds/splits. Audit historical reachable configuration
versions, base artifact seed metadata and existing conservative reserved ranges
before collection. This certifies the recorded metadata, not unavailable
external histories or every implicit arithmetic seed. Default/source physics
are deliberately familiar; no “untouched physics confirmation” is asserted.

All15 fits and final checkpoints finish before ANY evaluation is opened.
Two complete evaluation episodes per method/model/family:90 total. Pair reset
seeds and initial observations across PPO, random and fixed for each learner
replicate. PPO evaluation uses categorical argmax, frozen parameters and no
normalization updates. Random is uniform over encoded actions with its separate
registered RNG. Fixed always selects index0 (left force/negative torque).
No search over fixed actions. Random/fixed have no training cost; disclose PPO's
extra4096 training interactions, not a compute-matched algorithm superiority claim.
No evaluation outcomes enter learning, hyperparameter or checkpoint selection.

## Primary measurement and decision, before outcomes

Average the two episode returns within each independently trained PPO seed,
then compute paired PPO-minus-random and PPO-minus-fixed differences within
family. Unit is the independently initialized **PPO learner seed**, n3, df2;
never pool episodes or families as independent models. Use existing
`cl.metrics.seed_level_ci`, two-sided95% t interval with rounded critical4.303.
Keep all raw returns in family reward units; no pooled cross-family raw score.

For a family to pass, BOTH contrasts must have mean at least25 points for
CartPole/Pendulum, or5 for either MountainCar/Acrobot, and lower95% bound>0.
Five-family screen passes only if ALL five families pass. This intersection
rule does not accept a subset of successful families as overall success.
Per-family/comparison intervals are unadjusted exploratory; no simultaneous
coverage claim or posthoc multiple-comparison promotion. With3 seeds and2
episodes, uncertainty is large and confounds finite evaluation noise with
training variability. This is a feasibility learning screen, not convergence
or general-learning confirmation. Negative contrasts must be reported.

Secondary: raw per-episode returns/lengths/failures; training completed-episode
returns and policy/value losses; parameter count, initial/final/checkpoint
hashes; optimizer steps and processed minibatch examples; separate training/
evaluation wall and CPU costs; actor/critic forward calls and input rows;
actual real interactions and all imagined/model-work fields. Explained variance
may be null ONLY when degenerate/nonfinite, explicitly labeled optional. A
rollout with no finished training episodes has no mean episode return, not0.
Lower loss or parameter changes cannot upgrade the return screen.

## Resource proof and stopping

Training real:5×3×4096=**61,440**. Evaluation upper bound:
3 methods×3 seeds×2 episodes×(500+4×200)=**23,400**. Total **84,840**.
CartPole may end naturally before500; do not replace ended episodes or silently
shorten others. No probes/support/validation or extra pre/post-training episodes.
No imagined states or world-model calls. Meter every physical step exactly once
through SAME shared Host, across all worlds and roles. Save raw transition and
reservation journals separately; caching never substitutes for executed episodes.

PPO-specific hook counters are separate from E1 imagined-model operations:
each real collection slot uses at most3 trunk forwards (action, successor value,
timeout bootstrap), plus one per Adam minibatch; each PPO evaluation step uses
one trunk. Upper bounds: **7,680 optimizer steps,199,800 trunk forwards,
437,880 trunk input rows**. Dense/backward work is not implied equal to call
count or imagined transitions. Count actor and value heads separately. Policy
trunk/head calls on real observations do not create imagined state transitions.

Local CPU only, one run, **300-second total budget**. Begin timing before heavy
imports. Active dispatch/alarm stops at290s to leave10s for saving partial state,
journal closure and result metadata. Enforce Host time/interactions before
dispatch and neural/optimizer upper bounds through hooks. A Python alarm can
only interrupt a native call once it returns; disclose any actual overrun and
mark incomplete. No automatic restart/resume/extra run with this consumed grant.
Save every completed update and episode, and incomplete/invalid status on caps,
exceptions, missing cells or numerical failures. Full complete/finite expected
grid validation is required before declaring completion. Scientific inconclusive
or failed screen is distinct from an incomplete/invalid execution.

Carried session ledger before run: **1809.6321034559958 used /
1790.3678965440042 remaining**. Debit actual execution including failures and
initialization; branch changes do not reset it. No other scientific work in
parallel. Source/fixture tests are not scientific environment collection.

## Provenance and reproduction

Commit this protocol, config, allocation, seed audit, tested runner and module
before `scripts/run_e4_ppo_benchmark.py --run`. It consumes an exclusive usage
record before constructing environments and refuses stale hashes, dirty tracked
source, existing output or missing seed audit. Store new model/Adam/RNG states
under ignored `runs/e4_ppo_benchmark`; record paths/byte sizes/SHA256 in result.
These are not portable exact durable neural/Host-resume guarantees: wrapper
observer/ledger state is separate, and this study disallows automatic resume.

Result `artifacts/e4_ppo_benchmark.json`; raw transition/resource gzip journals
are tracked separately; source-only `--verify` checks saved summaries and local
files without simulator steps. A fresh clone can inspect JSON/provenance, while
explicit local checkpoint verification must fail if binaries are unavailable.
Preserve all base JSON and manifest-listed frozen files. Independent arithmetic
audit should reconstruct returns, physical totals and seed-level contrasts
from saved journals without training or new episodes. Commit results separately
and push the research branch; no main merge.

## Pre-execution correctness gate

Focused authored-world/GAE/contract checks:69 passed in1.10s. Relevant full
source/fixture regression selection:973 passed in55.87s. This is the51-module
selection in `e4_foundation_delivery.json` plus test_e4_ppo_benchmark and
test_gae, not every historical scientific/simulator test. No real environment
steps occurred in these tests. SameStep timeout bootstrap, exact rollout
accounting, deterministic toy updates, frozen evaluation, policy-counter caps,
missing/nonfinite cells, consumed/stale allocation refusal and independent
raw-return tampering rejection pass before collection.

Registration audit checked282 historical configuration blobs reachable through
518 local/remote references,434 base artifacts' seed metadata and preserved
conservative reservations. No recorded collisions among90 registered seeds.
The committed audit records its coverage limits. No data have been collected
under this protocol at the time of this lock. Offline independent validation
is additionally limited to the unused part of this same300-second total budget.

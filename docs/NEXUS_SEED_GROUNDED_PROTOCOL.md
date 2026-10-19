# Seed grounded-agent pilot — locked authored-development protocol

This implements the user's multimodal/recurrent architecture request. It does
not replace the old control research, reopen its evaluations, or establish AGI.
The earlier optional command-MLP scaffold is preserved at 2a6fb1f; its proposed
pilot was not executed. This protocol supersedes that experiment, not its code.

## Connected implementation and reuse

`nexus.world.seed_rssm.SeedRSSM` is an RSSM-inspired domain extension in the
existing world package, not a claim to reproduce Dreamer. Text characters,
36 rendered pixel patches and a 12-value proprioceptive sensor have separate
projections feeding **one shared GRU**. Observations are authored object
descriptions/images, not unrestricted language or a real camera. The recurrent
state has deterministic h=32 and Gaussian z=8. Source training uses stochastic
posterior/prior samples on coherent four-transition windows, reset per window;
inference uses deterministic means. Heads predict normalized sensor state,
next encoded observation, reward, termination and a short-return value.

Named prototypes retain an executable finite expression program and label
provenance in the existing Seed Session/Evolution-1 Journal. Learned key/query
attention supplies recalled features to h. Training retrieval uses within-batch
identity targets, so semantic retrieval quality remains an open question.
The source-trained program head proposes only its top eight of the existing
37 predicates; disjoint distinct property examples check the proposals against
a constant predictor. This is a development gate, not independent confirmation.
Corrections invalidate stale prototypes. Contradictory duplicates are excluded.
The existing numeric expression-tree evaluator executes signed predicate margins;
no arbitrary code, shell or user-generated Python is executed.

The existing RandomShootingMPC scorer is reused by a Seed adapter. Sixteen
H=4 sequences are proposed; a one-step learned-value probe retains eight.
Exactly 48 imagined states and five batched transition calls are used per plan.
The nine actions include movement, ask/store/retrieve and two bounded movement
programs. These macros are vetted compositions, not discovered general programs.
No old H=16 scientific planner is changed. Asking, storing and retrieving can
be selected by the same planner. The authored training world awards a small
first-ask information **proxy**; GUI teaching logs actual version-space reduction
only when the requested human label arrives. Store/retrieve earn no fictitious
information gain. This mismatch is visible, not evidence of learned curiosity.

The existing neural factory and EpsilonGreedyController are reused. A Seed-only
outer adapter may propose two registered trunk/activation recipes between
episodes and updates only on actual training-loss receipts. It cannot modify
metrics, budgets or permissions, and cannot launch training from the GUI. This
is functional meta-control integration, not proven learning-to-learn. No parallel
generic memory, evolution, planner or controller framework is introduced.

A small local GRU token decoder is trained on actual executed source traces.
Its candidate is always exposed. Runtime factual templates are retained unless
the candidate exactly matches the verified action trace. It is neither an
external LLM nor a general conversational model.

## Fixed pilot and hypotheses

Single executable configuration: `configs/seed_grounded_pilot.json`.
Two registered recipes (32-wide tanh and 16-wide ReLU trunks), one new model
initialization per recipe, 120 Adam updates each, lr=.003, B=8 coherent windows.
No hyperparameter search or extension. The deployment recipe is **tanh fixed
before results**. Evaluation cannot pick a winner for deployment.

H-engineering: all modules have connected gradient and execution paths, preserve
runtime weights, and produce complete finite outputs under bounded operation.
H-development: learned latent MPC can outperform random behavior in the authored
world. Greedy known-grid movement is the strong simple reference. Compare actual
paired returns and success counts, not predicted rewards. Negative return or
language results must remain negative. No confidence interval over four episodes
is represented as independent model-training replication; n=1 per architecture.
No generalization, control-transfer or meta-learning success screen is claimed.

Source seeds 82100001–82100048 and prediction seeds 82200001–82200006 collect
at most eight steps each under fixed random behavior. Control seeds
82300001–82300004 run at most twelve steps per recipe/method, with identical
reset states for latent MPC, random and greedy. Source/query/control seed sets
are disjoint. Initial state cannot already satisfy its goal. Max collection
is 720 authored macro-steps (at most two primitive moves each); max imagined
planner states is 4608. Query outcomes never train models or outer proposals.
Raw before/after states, actions, rewards and endpoints are retained for audit.

Report normalized-state MAE, reward MAE, done BCE, exact generated-trace rate,
single-modality latent discrepancies, gradient norms, parameter counts, losses,
paired returns, wall time and executed/imagined/training work separately.
Lower training loss or nonzero gradients alone are not useful intelligence.

## Execution boundaries and failure rules

Commit tested implementation/config/protocol before the single run. Require a
clean execution SHA, exclusive claim and exclusive output; no rerun if consumed.
Hard cap 180 seconds, 4096 authored steps and 100000 imagined planner states,
local CPU only. Carried session ledger: 1854.6321034559958 seconds used,
1745.3678965440042 remaining. This includes a conservative nine-second debit
for a broader legacy test command that executed an eight-step fresh CartPole
fixture, then failed because its child process could not locate PyTorch. No
historical checkpoint was replaced; the failed test was not rerun.
Debit actual experiment plus audit time; engineering
unit/GUI checks are reported separately. No prior frozen checkpoint is retrained.

Incomplete grid, nonfinite required metrics, changed weights, incorrect accounting
or exceeded caps invalidate completion. Save partial raw data and failure. Never
silently reduce updates, seeds or methods. Validate exact expected cells, dataset
hashes and model hashes with the independent stdlib auditor. GUI QA uses this
new model explicitly selected by path/hash; saved client data cannot enable it.

No Gym construction, paid services, reserved physics, old scientific checkpoint
inference, closed evaluation seed reuse or main merge. Existing historical result
files are immutable. Any later transfer study needs a separate protocol.

## Pre-execution checks

Starting branch revision: 2a6fb1fe58ad01298038fd689a912470ef60ee39, descended
from published repository refresh 053671c8497c80ad8a489ced8bb72ba68e45e9a6.
GitHub refs were fetched before execution. The original checkout's unrelated
untracked adapter files remain untouched in its separate worktree.

Pre-execution command: `python3 -m pytest -o addopts='' -q` with
`tests/test_seed_grounded.py tests/test_seed_architecture.py tests/test_seed.py
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py`:
**84 passed in 8.29s** using the existing local dependencies. The separate
legacy `test_expr_checkpoint.py` dependency failure above is not called passing.
`python3 scripts/check_repository.py`: 78 local links valid, 2025 protected
files unchanged and five explicitly hash-recorded code/roadmap evolutions.

`tests/test_seed_grounded.py` covers multimodal gradients, h/z semantics, learned
retrieval gradients, all predicate truth tables, exact imagined-state counts,
deterministic plans, immutable weights, outer feedback boundary, model JSON/hash
reconstruction, failed-storage language, persistent state, goal reward guarding,
typed rewards, disjoint collection seeds and local language gradients. Existing
Seed/Lab source suites remain required. Actual outcomes are recorded separately
in `NEXUS_SEED_GROUNDED_RESULTS.md` after execution.

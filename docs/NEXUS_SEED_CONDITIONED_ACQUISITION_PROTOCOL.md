# Query-conditioned acquisition — locked fresh development comparison

Base a290b4a10da40db27bc2c41c754d45e7dfbba11d matches fetched GitHub.
Branch `codex/seed-query-conditioned-acquisition`. Prior studies remain closed.

## Hypothesis and intervention

A small source-trained question selector that retains PUBLIC query geometry
reduces actual held-out prediction error relative to query-blind selectors,
with the underlying version-space learner fixed. The prior source audit only
established a missing-information counterexample, not improvement in learning.
Competing explanations: simple geometry is informative; correlations are not
captured by geometry; realized utility labels are noisy; random source-prefix
training differs from target selected-prefix roll-in. One bounded test, no sweep.

Reuse `source_acquisition` catalogue/interpreter, ten pre-answer features,
fixed posterior updates, source utility construction, baselines, LabelOracle,
uniform subset expectation and intervals; `nn.ridge`; the SAME EXPERIMENTAL
Sandbox/worker, E1 Journal and generic execute_study runner. Only an optional
source_count argument extends the existing fitter; its default and old outputs
remain unchanged. No new memory/learner/world-model framework or live promotion.

## Fresh task registration and immutable inputs

[Executable configuration](../configs/seed_conditioned_acquisition.json) is
validated against runtime constants. Reuse the supplied 910-program ANF
catalogue and original input/label semantics. Exclude ALL 192 previously
registered source AND target program identities from the original acquisition
assignment. Derive exclusions from its deterministic registration, not scores.
No closed outcome selects a new program. Shuffle remaining IDs within four
strata using assignment seed 1747000900. Draw eight source and eight target
functions per repetition, each with strata counts [1,1,3,3]. Source and target
mixtures match. Globally remove draws: all 128 new functions are distinct from
one another and all prior 192 functions, not merely different row/seed names.

Eight selector repetitions 1747000001–1747000008; source task IDs
1747100000–1747100063; target IDs 1747200000–1747200063, in blocks of eight.
Input shuffle uses task+200000, sorted first eight teaching inputs, sorted other
eight final query inputs. Source random teaching order uses task+700. Register
these offsets and audit explicit prior JSON/YAML config integers before running.
Registry SHA256 (canonical digest of filename/file-hash map):
`eb93436bf84c07a8c3a6b600e945c62c9f0e34823225332430c18d53467434e7`.
This audit cannot certify unavailable external runs or arbitrary implicit seeds.

The original stratum has only 19 unused two-term functions per sign; reproducing
16 source / 8 target tasks with the old mixture across eight repetitions is
impossible without reuse. Hence the NEW source size is eight, and mixture is
25% two-term / 75% three-term. All current methods receive the same data;
do not compare absolute scores with earlier studies as a treatment effect.

## Learners, fixed features and source fitting

Underlying prediction always uses the SAME uniform posterior over the full
supplied catalogue. Support budget at most eight teaching rows; report after
1,2,4,8. Prediction assessment uses the disjoint eight query input labels.

Train three new ridge selectors per repetition, lambda=1 with existing training
RMS scaling and sign-augmented fitter. No hyperparameter/checkpoint selection.
All use exactly the SAME source utility cases: for every prefix 0–7 of each
source task's random teaching order, evaluate each remaining candidate. Target
is actual SOURCE query MSE before minus after the candidate label and fixed
posterior update. 8*36=288 cases/repetition, 2304 shared cases total.

1. **blind**: the unchanged ten features: intercept, four candidate bits,
   candidate prediction p, p(1-p), minimum normalized Hamming distance to seen
   inputs (1 if none), observed positive fraction (.5 if none), remaining/8.
2. **blind_capacity**: same ten plus candidate bit0*bit1, bit2*bit3 and parity.
   Thirteen coefficients, no public query input argument used for extras.
3. **conditioned**: same ten plus mean normalized Hamming distance from candidate
   to query inputs, mean squared normalized distance, minimum distance.
   Thirteen coefficients. No answer, query label, candidate-updated parameters,
   task ID or query-conditioned oracle outcome is a feature input.

The two thirteen-dimensional models match coefficient count, rows, ridge rule
and data budgets; extra feature semantics differ by design. The original ten-
feature control prevents claiming a mere expanded polynomial representation as
query-conditioning. Parameter-count matching is not matched effective rank,
FLOPs, or a proof of causal mechanism. No full model-based gain is hidden inside
the three cheap geometry features. Record feature/case/normalization hashes.

All source fits freeze before any targets. Target choices/scores lock BEFORE
revealing each requested answer. Complete all target teaching paths before
collecting independent query labels. Query INPUTS are public, labels evaluator-
only. Each executable policy gets exactly eight unique labels; collection is
cached and charged once, method answer exposures separately. Equal prefixes
do not mean equal observed labels. Budget-eight predictions must match across
all non-keep methods. All previously taught labels remain exactly consistent
with retained hypotheses; no external retention-generalization claim.

## Controls, endpoints and decisions

Include all three learned selectors, variance, original order, source-static
mean utility, exact uniform-subset expectation, keep/no teaching, uniform-prior
model-based expected gain and source-informed expected gain. The last uses
Laplace+1 source stratum counts, uniform within strata, conditioning acquisition
weights on observed support. It does NOT change the prediction learner. Neither
model-based policy sees query labels or privileged target identity. Exact random
expectation is evaluator-only, not an online oracle. No answer-aware oracle is
needed for the registered primary comparison.

Primary: actual query MSE averaged equally across budgets 1,2,4, then eight
tasks within each source-trained selector repetition, then eight repetitions.
Budget 8 is secondary. These ARE cumulative teaching paths; unlike older
isolated-update studies, earlier selected labels enter later posterior updates.
Paired exploratory 95% t intervals across eight selector fits (df7,
t=2.364624251). Global sampling without replacement, one authored finite family
and shared learner/prior limit interpretation. Tasks, budgets, coefficients and
label exposures are NOT independent model replications.

Predeclared **transfer screen** requires ALL:
- conditioned primary MSE >=5% lower than BOTH blind and blind_capacity;
- positive lower paired improvement bound versus BOTH;
- positive primary improvement versus blind in at least six of eight fits;
- no more than .005 absolute excess MSE over EITHER model-based control;
- complete finite locked grid, frozen checkpoints/models and prefix retention.

Separate **strong model-based advantage screen** requires >=5% lower primary
MSE and positive lower paired bound versus BOTH model-based controls, plus
integrity/retention. Report all controls, per-task/fit paths, wins and failures.
No change to thresholds after outcomes; inconclusive intervals do not establish
improvement. Neither screen automatically promotes the selector. Better source
loss, running code or passing tests are not useful learned questioning.

## Resource lock, preservation and verification

One execution, CPU only, 60-second wall/CPU cap, 2048 MiB sampled RSS,
2500-authored-label upper bound, 24 ridge fits, zero neural forwards or imagined
transitions. Actual planned collection: 1024 source labels +512 target teaching
+512 final query labels =2048. All 512 executable paths expose 4096 CACHED
answers in total; do not recount these as new interactions. 6848 random-subset
assessment calculations. Source utility construction shared between learners;
isolated-method source costs must be reported as well as whole-run shared work.
Count query-distance operations, matrix entries, ridge fits/coefficients,
interpreter instructions and runtime separately. Work proxies are not FLOPs.

Carry 1999.6321034559958 seconds used /1600.3678965440042 remaining. Host grants
cite the existing human standing authority and debit ceil(host wall)+1. Do not
reset, reuse consumed records, run retries, shrink a missing grid or silently
raise caps. Preserve partial/invalid attempts honestly. Freeze historical
GRU/RSSM/readout hashes; no simulator, external service or model retraining.

Commit tested implementation/protocol BEFORE collection, then commit results
separately. Independently reconstruct source-only fits/normalization, target
choices, actual errors, complete grids, paired intervals and work accounting
from saved arrays. Verify all old artifacts unchanged and clean execution SHA.
Show saved evidence in the read-only GUI; keep main unchanged.

Tests: hidden answer/query-label changes cannot alter pre-answer features or
locked choices; source fit/preprocessing cannot depend on targets; feature query
geometry versus candidate-only control; label budgets and freeze/retention;
fresh program exclusion; explicit seed offsets; missing task/repetition/method/
budget and NaN/inf/bool/string rejection; independent numerical aggregation;
host routing, same final prediction and read-only receipt requirements.

Pre-execution regression: 105 focused/affected tests passed in 71.31 s after
the initial 86-test check. They cover acquisition, query-context unit/evidence,
the EXPERIMENTAL host and Lab sessions/release. Browser test syntax passes.
The additional independent reference-table/group-order and expected-gain test
passed in 0.29 s. No registered task outcomes are generated by tests.

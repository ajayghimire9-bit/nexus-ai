# Bounded correction: source stabilization, no strong-baseline pass

Executed once from **269bcb6e23d04674f9ee58dab8812d0d2f7e4d23**, starting at
b6926a0ea677b82e6565af52dedf78c222fc537f, on branch
`codex/seed-bounded-correction`.
[Locked protocol](NEXUS_SEED_BOUNDED_CORRECTION_PROTOCOL.md),
[configuration](../configs/seed_bounded_correction.json),
[raw results](../artifacts/seed_bounded_correction.json).
Raw SHA256: `28209e17eb34ab72c188f42504aa606227c0291c98e13a8d7b11b3a7bd3bc009`.

## Decisions

- **Stabilization passed:** learned bounded curve MSE .183824 versus original
  learned .212504, a 13.50% reduction. Paired benefit +.028679
  [.004901,.052457]. Final retention also improved.
- **Strong replay screen failed:** replay .187213 versus learned bounded
  .183824, only 1.81% lower error, below the registered 5% requirement. Paired
  replay-minus-bounded benefit +.003389 [−.009800,+.016577] includes zero.
- **Learned-specific screen failed:** fixed bounded .185384 versus learned
  bounded .183824, only .84% lower, below 5%. The exploratory paired benefit
  +.001560 [.000482,.002637] is positive, but does not meet the practical rule.
- **Advancement screen failed. No runtime promotion.** No validation, control
  or learning-to-learn benefit has been established.

All intervals average the three source-fitted controller seeds inside each of
12 reused source tasks, then use task means with df11. One frozen world-model
core; these are conditional descriptive, unadjusted exploratory intervals on
training data, not independent validation or model-replication evidence.

## What changed

One common output-change bound was applied after the existing learned, static
and fixed protected update. It used only old anchors and the observed support
prefix. The cap was fixed before scoring: .25 times the RMS source support
residual at the original initialization, with a 1e-6 floor. Measured source RMS
.44638762 gave tau **.11159690**. No query outcome selected this value.

The limiter activated on 45.83% of updates for all three bounded arms. It bounds
prediction changes on the permitted design rows, not every possible future
state. The controller and decoder weights stayed frozen; only disposable task
residual vectors changed. The implementation is an optional study intervention,
not a change to the live agent or the default correction function.

Primary source curve MSE, averaging budgets 1,2,4,8:

- Learned bounded .183824; static bounded .184286; fixed bounded .185384.
- Original learned .212504; static .214918; fixed .220150.
- Scaled replay .187213; none .200988.

Learned bounded query MSE at budgets 1/2/4/8:
.188256 / .175808 / .194824 / .176410.
Replay: .196987 / .190318 / .182324 / .179223.
The bounded arm was worse than replay at budget four; a curve average does not
imply uniform improvement at every teaching budget.

Worst prefix mean query MSE fell from .338179 original learned to .195718
bounded learned. Static fell .346297 to .196279; fixed .362583 to .197734.
These shared reductions support generic stabilization on this bank. They do not
establish that the learned controller is responsible for the useful change.

Final old-task retention MSE: learned bounded .065843, static bounded .066036,
fixed bounded .066549, replay .078978, original learned .079860, none .082166.

## Task sensitivity

Per-task curve MSE, learned bounded / original learned / fixed bounded / replay:

- 95000000: .286739 / .338694 / .288078 / .319194.
- 95010000: .212364 / .231409 / .216848 / .169697.
- 95020000: .253784 / .262568 / .257134 / .289658.
- 95030000: .164097 / .169462 / .165011 / .153480.
- 95040000: .265270 / .273798 / .266799 / .263421.
- 95050000: .085066 / .212765 / .085433 / .088688.
- 95060000: .215127 / .215127 / .215404 / .207865.
- 95070000: .146369 / .155030 / .145111 / .146640.
- 95080000: .102275 / .172567 / .103784 / .097796.
- 95090000: .206149 / .215228 / .208313 / .221635.
- 95100000: .111255 / .124971 / .111325 / .114916.
- 95110000: .157399 / .178425 / .161369 / .173566.

Bounding improves over original learned on 11 tasks and ties on one, but loses
to replay on five. No task was excluded or reweighted after inspection.

## Provenance issue found and corrected prospectively

The original host receipt's `adapter` field incorrectly says
`seed_nonlinear_learning_v1`. This was a hardcoded legacy display/provenance
label in the host; it also affected the preceding source diagnosis. The input
request and worker output say `seed_bounded_correction_v1`, the locked config
and protocol hashes identify this study, and the trusted host ran the bounded
validator and verified frozen controllers. The mismatch does not change the
calculations, executed code or resource charge.

The original receipt and results remain immutable. A separate verification
receipt records both labels, request/output hashes and the execution-source
hashes. Future host receipts now use the dispatched adapter. A mocked-worker
integration test catches this metadata regression without scientific execution.
This correction was made after the run, not silently attributed to its original
execution SHA.

## Costs and limits

Completed all 2592 planned snapshots: **972 new and 1620 cached**. Cached
controls were checked byte-for-byte at the trajectory level, not re-executed or
charged as new work. Source arrays, scale and prior frozen weights were hash
verified. Exact theta and query/retention arithmetic and bound checks passed.

1.859346 seconds host wall time; .439877 seconds worker body; 1.205068 seconds
worker process CPU; 296.44 MiB peak sampled RSS. Within the 30-second wall/CPU
and 2048 MiB sampled-RSS limits. macOS sampling is not a kernel-hard RSS limit.
Conservative debit: 3 seconds. Ledger **1922.6321034559958 seconds used /
1677.3678965440042 remaining**.

Zero new environment interactions, imagined transitions, world-model forwards
or outer optimizer updates. New work: 864 protected corrections, 576 frozen
tiny-controller forwards, 120 initialization solves, 96 source-scale examples,
7344 bound-design rows scored twice, and 26244 source query plus 26244 source
retention examples processed. All 990 stored controller scalars remain frozen.
The cached run's 1440 update calls and 1620 snapshots are reuse, not new costs.

The 26244 query/retention counts denote newly recorded scores, not every
verification operation. During execution, source preflight checks recomputed
43740 cached query and retention rows each; worker and host checks each
recomputed 69984 query and retention rows. Thus 183708 additional arithmetic
checks per role were performed on stored vectors. Their CPU/wall time is part
of processing, not new data collection, neural inference or imagined dynamics.

The Lab `/experimental` card shows the source curves and all three decisions.
Recorded replay is stdlib-only and does not run adaptation or load a world
model. Historical evidence, checkpoints, closed splits and main are unchanged.

## Verification performed

Pre-lock focused selection: 66 tests passed in 20.45 seconds; after the final
scale check, 15 bounded tests passed in 6.17 seconds before execution. Post-run
focused tests: 51 passed in 23.17 seconds, including the mocked host-adapter
receipt test. Relevant complete suite: **353 passed in 39.09 seconds**.
Command: `python3 -m pytest -o addopts='' -q tests/test_seed*.py
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py
tests/test_factory.py`, with source/dependency paths and single-thread settings.
The full historical scientific suite was not run.

Chrome headless: six checks passed, zero page errors. Decision labels, source
qualification, recorded curve, refresh, mobile layout and evidence immutability
were checked. The screenshot remains a private QA output under runs/.
All 752 pre-existing artifact blobs match the starting revision. Independent
stdlib checks verified all 864 limiter formulas, source hashes at the committed
execution revision, the original host request/worker adapter identities and
exact session-ledger reconciliation. The raw result was not rewritten.
[Verification receipt](../artifacts/seed_bounded_verification.json) records exact
hashes, runtime versions, metadata erratum and private host-result location.

## One next experiment

Test a cumulative source-evidence update against scaled replay and this bounded
fixed rule at the same 1/2/4/8-label budgets. The current protected candidate
fits the newest example while protecting old-task anchors. Earlier labels affect
theta implicitly, but their prediction errors are not included as an explicit
replay objective in that update. This is a concrete information-use difference
from replay. A source-only comparison can test that limitation
without increasing capacity or reopening the closed audit. Fresh validation
would still be required before promoting any rule. No second experiment ran.

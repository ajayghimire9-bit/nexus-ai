# Successor-search efficiency — engineering results

## Decision

Exact batching is a useful engineering optimization on the tested inputs. It
preserves the successful lookahead formula and all771 imagined transitions while
reducing model calls and neural forwards from51 to17 per decision. Short CPU
microtimings measured **2.61× Pendulum**, **2.56× Acrobot**, **2.53× MountainCar**
speedups. **160/160 actions and160/160 full Q rankings matched** on synthetic
observations scored by30 existing frozen decoders. Maximum absolute Q difference
was **0.0000349560**, within the predeclared2e-4 absolute/2e-5 relative tolerance.

This is mathematical equivalence with tested numerical tolerance, **not universal
bitwise equivalence**, a proof of identical future episodes, a new return result,
or a claim of general learning. The scorer is opt-in. Historical controllers and
all closed experimental outcomes are unchanged. No new environment episode,
neural training, confirmation scoring or controller-comparison experiment ran.

## Recovered research context and preservation

Fetched both remotes. The synthesis branch ends at
`f3898f6c95e37ea3f91101e288b71056edae4603`. The completed prefix-max branch extends
it to **57cbf25b8a1f93210bce383846d05910248a6517**, selected as this branch's base.
This incorporates the successful family planning results and both failed reuse
screens, rather than assuming `main` was current.

The previous replanning-readout idea in this chat was stale relative to the
recovered branches. No such fitting or collection was started. User steering
explicitly restricted this task to exact engineering and read-only audits.
No expired experiment allowance was reused or reset.

The original workspace on `cursor/mountaincar-continuous-lookahead-h16-confirm`
had one modified task file and three untracked confirmation-preparation files.
Those remain in place, excluded from this branch. Work used the isolated checkout
`/Users/ajayghimire/.codex/worktrees/successor-search-efficiency/nexus-ai`.
`main` remains **8d7f288d041b82f6973c82a314c8fe7dc760b2dd**; no merge.

Scientific status remains bounded: the same lookahead algorithm works with
separately trained family models; weights are not shared across families. The
compute-matched margin was met on Pendulum and MountainCar, not Acrobot. Nearest
tree reuse−14.751 [−37.142,+7.641] and prefix-max−9.832 [−31.108,+11.445] remain
closed failures of their registered improvement rules. No new value-function
approximation or variant of those screens was attempted.

## What changed

New `src/nexus/world/successor_search.py` provides `PreparedSuccessorSearch`:
one first-action batch of3, then sixteen successor-search batches of48. Original
order is action-major then candidate-major; every successor receives the same
original16×16 action matrix. Fixed rewards, survival accumulation, duplicate
candidates and `argmax` tie behavior are retained. Immutable cached action tables
can be shared across scoring contexts; scratch arrays remain local per score.

One semantic detail is deliberately retained: Pendulum's historical outer backup
ignores termination probability, whereas Acrobot and MountainCar multiply the
tail by1−p. All three multiply survival inside their tails. This audit corrects
the generic synthesis formula's applicability in its **new report**, without
editing that historical synthesis or its outcomes.

Only known row-independent MLP/FiLM models or explicitly declared row-independent
toy adapters are accepted; GRU, simulator and unknown stateful adapters fail.
The old family functions, world-model code, reward code and general MPC class
have **no diff against the base**. No checkpoints, source normalization or context
vectors were changed. No optimized path was installed in a historical runner.

The protocol, runtime-validated config, audit runner and43 unit tests were
committed before checkpoint scoring. Two older local-binary tests were subsequently
tagged with the existing `checkpoint_integrity` marker so repository-only tests
do not require untracked binaries. Explicit checkpoint audits still fail on missing
or altered files; no assertion was removed or silently skipped when requested.

## Exactness and timing evidence

Thirty checkpoint files were checked before loading and after scoring: ten each
Pendulum, Acrobot and MountainCar. Expected hashes came only from original parent
checkpoint metadata, the replication manifest and development compute-matched
configs. No confirmation outcome artifact was opened by the new audit.

Four synthetic observations and fixed candidate sets per decoder, with two
Pendulum contexts (zero and synthetic nonzero), give160 cells. The nonzero vector
is **not** the saved distilled student's task-specific vector. Frozen model,
encoder, normalizer and installed-context fingerprints matched before/after in
all160 cases. This verifies the existing decoders under these inputs, not all
saved student checkpoints or all possible inferred contexts.

Each cell measured51 versus17 actual `step` calls and neural-net forward calls,
with771 state predictions on both arms. Q arrays and choices are saved per cell;
the full rank order matched in every cell. Toy tests additionally compare every
individual tail-candidate score with the original scorer bitwise, including
termination clipping and duplicate/tie cases.

Seed0 median scoring time, seven alternating-order blocks of three decisions after
two warmups per method, local CPU/one Torch thread:

- Pendulum: **3.817ms → 1.463ms**,2.609× (synthetic nonzero context).
- Acrobot: **3.307ms → 1.290ms**,2.564×.
- MountainCar: **3.227ms → 1.277ms**,2.528×.

Both paths exclude candidate generation; the batched path includes its local
scratch copies. The existing residual-family reference function constructs its
planner inside the timed call, so its small adapter-construction overhead is
included. Raw timings are retained. These medians are engineering microtimings,
not confidence intervals, end-to-end episode speedups or independent research
replications. CPU load, input range, batch kernels and threading can change them.

## Costs and limitations

The one saved checkpoint audit completed in **1.239929500seconds**, within its
30-second engineering cap. It used **zero real interactions**, **zero optimizer
updates**, and **353,118 imagined/model transitions** across parity and timing:
246,720 for160 paired cases,106,398 for warmups/timing. There were15,572 model/net
calls in that audit. Unit-test inference is separate and not included in that
microaudit accounting. No scientific environment execution budget was consumed.

The optimization saves Python/adapter dispatches, not simulated state transitions
or theoretical dynamics work. Tail-state working memory grows from16 to48 rows;
the cached48×16 int64 table is6144bytes plus its local writable copy and the
original candidate matrix. Model parameter count and checkpoint size are unchanged.
Peak process memory was not measured. Binaries stay local and are not uploaded;
the report/config/artifact record their expected paths and hashes.

Float32 matrix multiplication is not guaranteed bitwise stable across batch
sizes. Near ties could change a selected action outside this finite synthetic
grid. No action mismatch here establishes universal parity. Prefix-sharing across
identical histories, tensor-native inference and compiled unrolling are possible
later exact-engineering avenues, **not implemented or evaluated in this task**.
Reusing a tail from a different successor state would be approximate and is excluded.

## Tests actually run

- Initial43 focused tests passed in0.61seconds after resolving a read-only-array
  warning found in the earlier29-test pass. No training or environments.
- First expanded regression run:68 passed,2 failed,2 deselected in2.07seconds.
  Both failures were legacy binary tests expecting `.pt` files in the isolated
  checkout. They were not numerical or planner failures. Marker classification
  was corrected; original binary assertions remain intact.
- Final repository-only relevant regressions: **69 passed,4 deselected in1.95s**.
  Two environment-stepping tests were explicitly excluded by `not dense_height`;
  two binary tests were excluded by the repository's normal marker policy.
- Explicit two local checkpoint tests against the original checkpoint location:
  **2 passed in0.53s**. The standalone parity audit also verified all30 requested
  checkpoints, rather than treating absent local files as a pass.
- A separate Git-only recorded-result test independently recomputed the160-cell
  grid, argmaxes, rankings, maximum difference, timing medians, ratios and hashes.
  It is included in the69-test final run.

The **entire repository test suite was not run**: it includes model training and
environment episodes outside this task's authorization. No unrun suite is claimed
as passing. `git diff --check` passed and the original workspace changes remained
unchanged when rechecked.

## Provenance and reproduction

Branch **codex/successor-search-efficiency-audit**. Clean implementation/protocol
and execution SHA **506ffc71b5483ac8494dcb4eb6d139935c457ffe**.
Results are committed separately. Artifact
`artifacts/successor_search_efficiency.json` SHA256:
**63caba6312004984c311c17aaa52c6972788b00c077776dfe0ef30531a031d13**.
Config SHA256 `28309944ca1330c566c5262d4ea059fe99a843087992de3cb98ca4fa09146c8b`;
protocol SHA256 `48c696f673a80d6712e538284add7c73112a1ebc5ba48a1ae93a8f985ec6dee4`.
Runtime dependency versions and code/metadata hashes are in the raw artifact.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_successor_search.py \
  tests/test_successor_search_audit.py tests/test_successor_search_recorded.py \
  tests/test_bellman_backup_control.py tests/test_acrobot_lookahead.py \
  tests/test_mountaincar_lookahead.py tests/test_tree_reuse_lookahead.py \
  tests/test_prefix_max_tree_reuse.py -k 'not dense_height' -p no:cacheprovider
# Original one-run engineering audit; refuses overwriting its result:
PYTHONPATH=src:.deps python3 scripts/audit_successor_search_efficiency.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai \
  --output artifacts/successor_search_efficiency.json
```

The isolated checkout used the original `.deps` directory in PYTHONPATH. The
explicit checkpoint tests ran from the original repository root using the new
worktree's test paths and source path, with `-m checkpoint_integrity`.

## One next recommendation

Before changing any deployed experiment runner, perform a separately locked
**archived-state numerical parity audit across the actual saved student contexts
and small action-score margins**. Use recorded observations only, no new episodes
or fitting; preserve exact candidates and report every argmax mismatch. This fills
the synthetic-input/context coverage gap without reopening a control hypothesis.
Any later environment-based control noninferiority test requires a new explicit
authorization and committed protocol; none was launched here.

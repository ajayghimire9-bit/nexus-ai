# NEXUS Seed — Owner-controlled EXPERIMENTAL mode

Starting revision: `4362344621c048b811a0066e4d9dd2aa87dac055`, verified against
GitHub `codex/seed-current`. Branch: `codex/seed-experimental-sandbox`.
This is research-workflow engineering. No new scientific experiment is run by
installation, opening the GUI, registering data, or approving a budget.

## Restriction audit before implementation

Scientific-process choices that can differ for development:

- Requiring a complete paper-style protocol before every debugging iteration.
- Keeping one architecture, optimizer, learning rate or planner fixed forever.
  Those were controls for particular studies, not a ban on new studies.
- Prohibiting repeated inspection of explicitly reusable development data.
- CPU-only and numeric time/interaction defaults: owner allocation policy,
  changeable only through explicit bounded approval, never by the candidate.
- The choice of a 10% improvement screen or ten-decoder design: belongs to its
  registered claim. New development can use other predeclared criteria, but
  cannot change or relabel historical outcomes.

Essential correctness/evidence protections:

- Keep all old artifacts, checkpoint bytes, normalization and closed evaluations
  immutable. Never replace their results or count reused data as fresh evidence.
- Train/assessment separation, complete finite metrics, correct independent
  units, negative/incomplete labels, hashes, and charged failures/retries.
- The same recurrent-state contract for training, evaluation and GUI; baseline
  fairness and evaluator-only oracle outcomes remain necessary.
- Reserve resources before dispatch, carry the session ledger, enforce caps,
  preserve failed logs and use rollback instead of overwriting accepted models.

Essential security/permission boundaries:

- Codex sandbox/security controls, owner permissions, external-action controls,
  no paid services, no automatic main merge, no arbitrary generated shell.
- Neither a candidate nor the GUI can grant resources or modify evaluators,
  historical restrictions, metrics, role registrations or host accounting.
- A Python worktree is **not an OS isolation boundary**. The worker is vetted
  local code, not a safe place to execute hostile generated Python. Hashes detect
  corruption; they do not authenticate someone with the owner's filesystem.

The new AGENTS section changes exploration process only. The original standing
authority text and historical instructions remain verbatim. The earlier
1/2/4/8-example learning-rule proposal remains unexecuted in this task.

## Reuse and implementation scope

Reuse `evolution1.catalogue.canonical/digest`, `evolution1.fixtures.Journal`,
the existing Learning Lab server and `nn.factory.build_mlp`. E1's
`ReservationLedger` is a fixed-plan synthetic contract, explicitly not a process
meter; this host adds process supervision and durable reservations rather than
claiming its synthetic clock measures work. Session/E1 storage conventions
(`open('x')`, hash anchors, append-only evidence) are retained. SeedRSSM, Belief,
the existing planners and controller weights are unchanged.

The executable first adapter is numeric supervised MLP development: one to four
hidden layers (or a linear head), tanh/ReLU/SiLU, Adam/SGD, bounded update count,
source and development JSON rows. This permits actual new architecture,
optimizer and training iterations. It is not a general autonomous learning
claim. New learning-rule/planner adapters can be proposed in isolated worktrees,
but require review plus host-side operation metering before becoming executable
operators. Arbitrary scripts, generated source, simulator collection and GPU
execution are intentionally not dispatched by this initial adapter. No second
RL, memory or self-evolution framework is introduced.

## Three evidence modes

**Exploration:** a ten-field manifest; train plus reusable development data only.
No publication protocol or scientific success claim. Every attempt gets a new
ID. Iterative training/HPO is allowed by issuing new bounded attempts. Train
and development rows never overlap. The learner sees development errors for
iteration, but its inner optimizer uses training rows only.

**Validation:** frozen candidate JSON; fresh, separately registered assessment
rows. No optimizer. The host measures MSE versus the *current sandbox incumbent*
(a fixed zero predictor if no incumbent exists), and worst per-row error
increase. A manifest must specify minimum mean gain and maximum per-row
regression before execution. Each validation dataset is consumed once, including
failed/interrupted attempts. This local gate does not establish independent
scientific confirmation or cross-task retention. Do not call worst row error
"forgetting" without a separately designed old-task retention assessment.

**Confirmation:** no optimizer; frozen model; committed ancestor protocol JSON
whose contents bind model and assessment hashes, primary MSE, independent unit
and success threshold. The manifest binds the protocol commit/path/hash too.
Completion means the assessment ran, **not** that a scientific hypothesis passed.
The host cannot promote from confirmation. Proper task-level statistical analysis
and claim-specific complete grids belong in the registered study.

Dataset registration requires an owner and collection provenance. Shared row IDs
or identical data cannot be relabeled under another role. Snapshots are copied
into the private run directory and hash-bound in the journal. Owners must provide
genuinely fresh data where required: no general software check can infer that an
arbitrarily renamed row was never inspected. This host does not certify all old
scientific splits or reopen them. Validation/query payloads are never included
in the training worker request. Assessment is done by the trusted fixed worker,
not by invoking candidate code. Same-user OS access is not adversarial isolation.

## Resource approval and enforcement

`approve` is an explicit owner CLI action, unavailable to workers and the GUI.
An agent may use the existing standing grant only within its scope; larger
allocations require the owner's explicit matching approval. Records are local
audit evidence, not cryptographic identity or new Codex permissions. Budget
records include wall seconds, CPU seconds, memory MiB, optimizer updates, real
steps, imagined transitions, device, session ceiling and carried session usage.
An increase creates a new record; it never edits an old grant or resets usage.

The host serializes execution with a file lock, durably reserves wall allowance
before starting, and charges measured elapsed time on completion. If it crashes
before settlement, the full reservation remains charged. Retries need new IDs;
used assessments stay consumed. A deadline kills the worker's process group.
Kernel RLIMIT_CPU is process-wide (integer-second granularity); Linux also uses
RLIMIT_AS. The host checks RSS every ~30 ms and kills on memory threshold.
macOS does not provide reliable RLIMIT_AS: default `memory_policy: kernel`
fails closed there. The owner can explicitly approve `sampled_rss` for bounded
engineering/development; this is **not a byte-exact kernel hard limit**. There is scheduling/one-sample
overshoot for wall/RSS enforcement. Do not use this backend for an experiment
requiring strict kernel-enforced memory isolation; use a separately reviewed
container/backend first. CPU imports/startup count against kernel limits; the
worker's reported training CPU is narrower and labeled accordingly.

No environment is created by this adapter, so physical/imagined steps must both
be zero. Reported nonzero steps are rejected. Updates are checked against the
planned curve and grant. GPU grants can be recorded as owner intent but execution
fails closed because GPU-memory metering is not implemented. New simulator/GPU
adapters must reserve work before each operation and preserve hard limits; a
large number in a grant is not an implementation or authorization to use one.

Scientific session ledger remains **1910.6321034559958 s used / 1689.3678965440042
s remaining**. Engineering fixture tests are separate and not scientific runs.
Concurrent external runners are not metered by this host: all such execution
must still be carried into the same owner session ledger. Do not create another
directory to claim a fresh session or free budget.

## Quickstart for Codex/Cursor and the owner

From a research branch with Python/Seed dependencies installed:

```sh
python scripts/nexus_experimental.py status
python scripts/nexus_experimental.py fork trial-a
```

The Seed CLI also routes these typed commands: `python -m nexus.seed experimental
status` (or installed `nexus experimental status`). It does not evaluate shell
strings. For option-rich commands, use `scripts/nexus_experimental.py` directly.

`fork` makes a separate Git worktree/branch; no training, promotion or deletion.
Keep the trusted host checkout intact. Propose configuration changes as a new
manifest; code changes remain in that candidate worktree for ordinary review.
No candidate code is imported into the trusted host automatically.

Register numeric source/development files. Format:
`{"rows":[{"id":"unique-source-row-a","x":[0.2,0.4],"y":0.7}, ...]}`.
Use different row IDs and observations for each role; record actual collection
provenance. Never relabel a historical holdout as new data.

```sh
python scripts/nexus_experimental.py register source-a train /path/train.json --owner Ajay --provenance 'new source collection, provenance reference'
python scripts/nexus_experimental.py register dev-a development /path/dev.json --owner Ajay --provenance 'separate reusable development collection'
```

Create a private budget JSON (not an approval just by existing):

```json
{
  "caps": {"wall_s":30,"cpu_s":20,"memory_mb":2048,"updates":100,
           "real_steps":0,"imagined_transitions":0},
  "session_limit_s":3600,
  "carried_used_s":1910.6321034559958,
  "device":"cpu",
  "memory_policy":"sampled_rss"
}
```

```sh
python scripts/nexus_experimental.py approve local-a /path/budget.json --owner Ajay --reason 'explicit bounded local development allocation'
python scripts/nexus_experimental.py run configs/experimental_example.json --grant local-a
python scripts/nexus_experimental.py status
python scripts/run_learning_lab.py --allow-seed --port 8779 --max-runtime-s 900
```

Open `http://127.0.0.1:8779/experimental`. The GUI is read-only: attempts, labels,
model hashes/revisions, training/development curves, measured error changes,
resource caps, charged time, failures and the sandbox incumbent. Seed remains
at `/seed`. Optional `--experimental-directory` selects another owner run store.

For validation, register fresh data under `validation`, then use a manifest:

```json
{"id":"validate-a","mode":"validation","recipe":null,"train":null,
 "development":null,"model_run":"candidate-a","assessment":"assessment-a",
 "protocol":null,"gate":{"minimum_gain":0.01,"maximum_regression":0.1}}
```

```sh
python scripts/nexus_experimental.py run /path/validation.json --grant local-a
python scripts/nexus_experimental.py retain validate-a
python scripts/nexus_experimental.py rollback
```

Retention uses the already recorded gate. It changes only the sandbox pointer.
Rollback restores its previous accepted pointer; old models/attempts remain.
Scientific gates must additionally test old-task retention and independent tasks.
Confirmation protocol contents use `schema: experimental_confirmation_v1`,
`candidate_sha256`, `assessment_sha256`, `primary_metric: mse`,
`success_mse_at_most`, and `independent_unit`. Commit before running; bind its
commit/path/SHA256 in the manifest's `protocol` object. No confirmation is run
as part of this setup.

## Verification and limitations

Focused tests cover role/overlap checks, changed grants/results, finite complete
curves, exhausted budgets, charged interruption, candidate updates, one-use
assessment, no training-query path, retention/rollback, GPU rejection and a
bounded real subprocess on authored numeric fixtures. GUI QA must use only those
engineering records; it is not evidence of useful learned adaptation.

History lives under ignored `runs/experimental`: keep or back up this private
store for reproducibility. Git versions implementation/examples/docs, not private
data or large weights. Journal format reuses E1's legacy `synthetic_fixture`
envelope; the payload explicitly says `experimental_local` and must not be
mistaken for a scientific simulation receipt. Truncation requires an external
stored head/count anchor to detect; the hash chain alone is not authentication.

No historical benchmark, trained checkpoint, model state contract or closed
evaluation changes. No architecture/learning-rule efficacy is established here.
One next engineering milestone: a reviewed Seed adapter with per-step host
reservations and old-task retention before executing new adaptation science.

That milestone subsequently completed for one locked nonlinear-feature study:
the adapter reused the host, existing correction math and frozen features. Its
[registered results](NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md) failed the combined
screen and remain closed. This adds no arbitrary-code or GPU execution support.
The GUI shows actual1/2/4/8-example curves, baseline comparisons, task-level
intervals and resource use. With no private run store it displays a validated
read-only replay of the tracked artifact. No model inference occurs in replay.
Latest scientific ledger:1916.6321034559958used/1683.3678965440042remaining.

## Completed engineering verification

Implementation commit: `aa18434f228a974dc97d08e966725bd8cc49e44f`.
The relevant Seed, session/release, repository, planning, expression and factory
suite passed **265 tests in 25.46 seconds**. The entire historical experiment
suite was not invoked. Real Chrome 155 QA passed six checks, including measured
curves, immutable refresh, no browser execution endpoint, mobile layout and the
unchanged Seed interface; zero page errors or external requests.

The GUI exercised an authored two-parameter numeric fixture: 12 Adam updates,
48 training examples processed, 52 development examples processed and 37 neural
forward calls. It is an integration test, not scientific evidence. The successful
recorded fixture took 1.389858 s wall / 0.879233 s worker CPU. Previous debugging
iterations are not included in those individual times. No new environment data
or scientific experiment was collected.

All **740 historical artifact Git blobs** match the starting commit. Repository
preservation and the saved spatial-transfer data-only verifier passed. The
standing grant remains verbatim, the two unrelated files in the original
checkout are excluded, and main is untouched. Machine-readable verification:
[engineering receipt](../artifacts/seed_experimental_engineering.json).

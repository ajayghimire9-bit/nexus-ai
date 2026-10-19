# Bounded learning cycle and Learning Lab — implemented, utility unestablished

Branch codex/bounded-learning-cycle-and-lab from
aafc42cc6aee7280a10a8b0c77d84c985fbc6f9d. Implementation/protocol execution
revision **03a34156bf040e088834fa08199b00ffe245e20f** committed before the
benchmark. Protocol NEXUS_BOUNDED_LEARNING_CYCLE_PROTOCOL.md, executable
config configs/bounded_learning_cycle.json and separate consumed allocation.

## What each requested milestone now has

**E3.11C longer-horizon prediction:** already tested as E3.11D, preserved rather
than rerun under a new name.64-step forecasts failed versus16 and training
means; no general forecast utility or efficiency claim. Older C efficiency
proposal remains deferred, not relabeled successful.

**E3.12 measured mutation credit:** existing generator now connects through
measured_mutation.observe_measured_pair to complete actual reward paths and
matched completed resource receipts/checkpoint/reward hashes. This bridge
does not collect data or authenticate an untrusted caller. Structural updates
and lineage are exercised in the bounded fixture cycle; no new real parent–child
experiment ran. Fixture utilities cannot enter the real-return path without
explicit synthetic domain tagging. Default mean update/RNG behavior is retained.

**E3.13 continual task stream:** existing TaskStream/StrategyGenerator retain
state across A→B→A→C; persistent/reset/shuffled controls are executable with
return-A/retained-A queries. Existing contextual memory remains untouched.
This retains learning within the bounded process; no durable learned-state
checkpoint/resume mechanism is claimed by the new adapter.

**E3.14 experiment selector:** existing meta-controller statistics choose
test_challenger, refine_strategy, gather_evidence or stop using permitted
training utility per declared fixture cost. Random/fixed schedule controls
have equal upper opportunity budgets; actual counts differ when adaptive stops.
Evidence collection gets zero direct invention credit; useful information value
is not assumed merely because the arm is named gather_evidence.

**E4.0 learning-rule selection:** finite mean/recency/conservative structural
credit rules and bounded exploration, selected on training feedback only.
Rule is frozen before D/E/F adaptation/query evaluation. This is a small bandit
over vetted updates, not arbitrary learning-rule code generation or proven L2L.

**E4.1 autonomous cycle:** Generate→validate→evaluate→credit→schedule→remember
runs without manual per-attempt selection. Independent development promotion
and separate audit rollback use the existing E1 harness. Rollback restores
the exact prior accepted typed strategy; it deliberately retains unsuccessful
learning attempts rather than deleting negative experience. Same-process
fixture audit keys are not a production security boundary.

**Learning Lab:** a local controlled application and an offline interactive
recorded-control replay. Supports verified Pendulum/Acrobot E3.11B/D studies,
family/model/episode selection, forecasts versus actual advantage, cumulative
reward traces and step-level actions/observations. Opt-in fixture playground
compares integrated/random/fixed/reset/shuffled procedures. No neural training,
real simulator or live scientific backend is exposed.

## Actual comparative findings — all fixture screens fail

132 complete runs:12 authored fixture banks ×11 methods. Three transfer tasks
per run use coefficients not supplied as source feedback. The scorer evaluates
strategy descriptors against authored utility tables: **it does not execute
planners or measure environmental returns**. Existing adapter tests separately
check executable strategy behavior. These results assess functional integration
and failure handling, not the requested real-environment capability milestones.

Exploratory paired95% t intervals across12 fixture banks (df11):

- Mutation-driven generation versus random: transfer proposal utility
  **−0.016369 [−0.092206,+0.059468]**. E3.12 fixture screen fails.
- Persistent versus reset: returning-A proposal utility
  **−0.047859 [−0.155948,+0.060230]**. Mean retained-A loss after B
  **0.082475**, exceeding the registered0.05 limit. E3.13 screen fails.
- Adaptive versus random scheduling: gain per declared training cost
  **−0.032888 [−0.086787,+0.021011]**; versus fixed schedule
  **−0.018569 [−0.059007,+0.021870]**. E3.14 screen fails.
- Learned versus fixed update: transfer proposal utility
  **−0.001414 [−0.017758,+0.014929]**; versus random update
  **+0.022175 [−0.001933,+0.046284]**. E4.0 screen fails.
- Full cycle versus fixed generation: deployed transfer utility
  **+0.209035 [−0.049135,+0.467206]**. E4.1 screen fails.
- Actual versus reversed parent/child-feedback assignment:
  **+0.027623 [−0.010982,+0.066228]**; no reliable fixture advantage.

All intervals include0. Do not promote positive point estimates or treat these
public authored fixtures as independent real families/confirmation. Feedback
changed preferences1583 times and110 audit rollbacks occurred, demonstrating
mechanical responsiveness rather than useful self-improvement. Strong simple
baselines remain competitive. No scientific success criterion was redefined.

Independent audit notes: random generation also changes leaf selection, so its
contrast does not isolate mutation credit as the sole causal intervention.
Rules share the same source feedback stream; contextual representation remains
the old fixed catalogue context, not a learned cross-family representation.
Repeated returning-A probes are dependent diagnostics. Development promotion
does not supply values to proposal/rule/scheduler updates or training parents;
query probes use copied generators and cannot advance learning RNG. Training
and transfer phase utilities are separate authored samples of one public
function, not secret scientific environments. Original reward-bank/confirmation
results and failed H17 gates remain closed.

Further limitations: finite eight-proposal probes use copied RNG state at each
checkpoint, so retention differences include proposal-sampling variation and
do not isolate catastrophic forgetting. The scheduler's authored reward sums
parent–child differences, not net incumbent progress; repeatedly proposing a
useful known modification can earn this metric again while paying its cost.
This does not establish discovery efficiency or appropriate value-of-information
learning. A real study must measure net improvement and separately account for
all assessment/planning costs, not adopt the fixture proxy uncritically.

## Run, accounting and verification

Source-only fixture benchmark **4.239549874997465s wall /4.225233s CPU**,
below60s cap.33824 authored utility calls and5180 declared training cost units.
Declared costs are not measured CPU seconds/FLOPs; measured time per method
and actual call counts are saved separately. Zero new real/imagined transitions,
model inference, neural fitting or historical checkpoint replacement.

Saved-data verification **0.3167349169962108s**, no rescoring or inference.
All398 previous research JSON retain byte hashes. Final carried ledger:
**1024.6735364600015 used /2575.3264635399983 remaining**. Unit/mock-UI tests
are engineering checks, not extra scientific replications. No additional
scientific experiment was started afterward.

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps \
python3 scripts/run_bounded_learning_cycle.py
PYTHONPATH=src:.deps python3 scripts/run_bounded_learning_cycle.py --verify
```

The execution command is one-run and refuses existing usage/result records.
Artifacts bounded_learning_cycle.json and bounded_learning_cycle_validation.json
contain raw traces, paired contrasts, fixture costs, source/config/protocol
hashes, exact code revision, measured timings, immutable journal segments and
closed-history hashes. Raw SHA256:
5bdf27e1a5ce16a46570eb129558ccab1ba9fa6ec56d432605356a831e796dfb.

Initial relevant regressions676 passed in16.04s; subsequent targeted102 passed
in3.10s cover fixed-baseline probe and numeric-schema corrections before lock.
Final test count/commands are in bounded_learning_cycle_test_report.json.
Coverage includes held-out feedback poisoning, RNG immutability, frozen transfer
rules, true prior-strategy rollback, failed-cost charging, full planned grids,
ledger/provenance mismatches, server route/options/origin limits, fixture APIs
and client filtering/decision inspection with a mocked DOM. Legacy unmetered
neural benchmarks remain outside this relevant suite.

## Use Learning Lab

Open **artifacts/nexus_learning_lab_app.html** in a browser for the offline
interactive replay. It embeds verified captures and disables live fixtures;
no server/network connection is needed. The original read-only HTML files are
unchanged. Build source: scripts/build_learning_lab_app.py.

For the local fixture playground, from the repository root:

```
PYTHONPATH=src:.deps python3 scripts/run_learning_lab.py --allow-fixtures
```

Then open http://127.0.0.1:8765. Without --allow-fixtures the server is replay-only.
It binds loopback, exits after<=900s, accepts at most10 fixture requests/process,
caps each at8 choices/2s, whitelists seed/method fields, rejects foreign origins,
requires a custom POST header, limits JSON bodies and provides no shell/file
or real-experiment endpoint. Fixture runs remain clearly labeled synthetic.
Server state is bounded/in-memory, not a deployed multi-user research service.

Preview limitation: the in-app browser and HTTP health check timed out despite
a loopback listener being present. The owned preview process was stopped;
no security/network settings were changed. Request handling was verified with
an in-memory HTTP transport; client execution with Node/mock DOM. No real-browser
visual/accessibility QA passed, and no public hosting/deployment occurred.
The offline replay provides a usable alternative while local preview access
is unresolved. The Sites skill was used for the local-only application workflow.

## One next scientific milestone

Run **one preregistered measured parent–child mutation-credit comparison against
random generation on fresh source control episodes**, through the checked
bridge and existing metered host, before expanding the meta-controller. Fixture
mechanics and responsive weights are insufficient; the missing evidence is
whether permitted actual feedback produces better subsequent strategies.
No claim of real continual learning, transferable learning-rule improvement,
general autonomous intelligence or AGI follows from this implementation.

# Evolution-1 source contracts

Status: **SOURCE_CONTRACTS_IMPLEMENTED — NOT_READY_FOR_SCIENTIFIC_EXECUTION**.
This engineering milestone implements deterministic fixture interfaces from
`NEXUS_EVOLUTION1_FEASIBILITY.md`. It is not a scientific protocol, allocation,
experiment, discovery engine or demonstration of self-improvement.

## Provenance and scope

Branch: `codex/evolution1-contract-harness`.
Starting revision: `aee136241384704673cfc839c916cee4379eb57f`, matching the
refreshed GitHub feasibility branch. Preserved untracked prototypes from the
earlier continuation were reviewed and completed here. No reset, main merge,
checkpoint change or modification to H12–H17 experiments is included.

The root instructions, master context, feasibility report and source-only tests
were read. This milestone constructs no environment, loads no checkpoint,
performs no model inference or training, and selects no target physics or
scientific seed. It creates no experimental authorization or allocation.
The metadata dimensions and numeric test values in the unit tests are synthetic
fixture declarations, not environment registrations or collected experience.

The Evolution-1 hypothesis remains untested: previous improvement attempts may
help a proposal policy discover transferable planning configurations more
effectively than strong equal-budget baselines. Software correctness is not
evidence for that hypothesis, control improvement or learning-to-learn.

## Catalogue and analytic bounds

`src/nexus/evolution1/catalogue.py` defines twelve immutable configurations:
flat/successor × IID/balanced-first-action × horizons 4/8/16. Proposals contain
only the catalogue digest, rule, generator and horizon. Unknown, extra, missing
and duplicate fields, invalid types (including booleans and numeric strings),
nonfinite JSON constants and messages longer than1024 characters are rejected.
There is no code, callback, path, split, seed, permission or budget field.
Canonical serialization provides deterministic configuration fingerprints.

The catalogue digest identifies schema and cost semantics, not a vetted
executable planner. No candidate generator or planning operator is implemented.
For action count A, horizon H and imagined-transition cap B:

- Flat gets N=floor(B/H) candidates, with analytic cost NH per decision.
- Successor gets N=floor((B−A)/(AH)) tails per root action, cost A+ANH.

Counts must be positive integers; infeasible proposals fail. The interface
permits caps up to1536 and up to16 actions; tests cover three and five actions.
These are analytic work bounds, not measured neural calls, FLOPs or elapsed
time. Discarded remainder is not padded or claimed to be useful computation.
Actual generator balancing and planner/operator equivalence require a later
source-only adapter review before any scientific execution.

## Synthetic broker and accounting

`fixtures.py` supplies a training-only fixture table and message broker. The
table requires exactly one row for each catalogue entry, without duplicates.
Successful scores are finite numbers in[0,1]; failed fixtures have a null score.
Only declared public interface dimensions and limits are exposed as context.
There are no hidden-family data, evaluator callbacks or scientific run APIs.

Every broker receives its own declared fixture caps for steps, imagined states
and synthetic CPU units. It checks cumulative limits and reserves cost before
revealing feedback. Failed fixtures consume full declared cost. Unexpected
internal materialization faults retain their reservation and log failure.
Duplicate proposals fail; reusing a fixture table in a second broker does not
provide free logical budget. Invalid/rejected requests spend one bounded attempt
slot but no simulated resource charge. Parsing itself is not claimed to be
free CPU work. Default maximum attempts32; the permitted maximum is64.

All resource values are **declared synthetic costs**, not actual measurements
or authorization to spend real interactions. `cpu_units` have no conversion to
CPU seconds. Unique materializations of a reused table are separate from
per-broker logical charges. The harness is sequential; no concurrency safety
or actual process-resource meter is claimed.

## Journal, fixture promotion and rollback

The journal returns immutable event tuples with canonical payloads and chained
hashes. Verification rejects altered, reordered or internally deleted records.
An independently retained expected head/count detects truncation relative to
that anchor. Without an external anchor a valid prefix is indistinguishable
from a shorter valid log. A Boolean index cannot impersonate an integer index.
This in-memory journal is not durable append-only storage, an authentication
authority or proof that resource declarations are true. Verification checks
chain structure, not the scientific meaning of recorded feedback.

`promotion.py` implements fixture-only audit messages and incumbent transitions.
An HMAC test attestation binds a candidate snapshot (configuration plus RNG,
context and memory state-reference hashes), training-journal head and decision.
Missing, malformed, forged, stale, replayed, nonpassing or differently bound
attestations fail. Rollback restores the exact previous immutable snapshot
reference and retains the archive and promotion/rollback event tuples.

Rollback restores references only: no live controller state is loaded or
restored. A signed arbitrary head is not proof of a complete training journal;
its validity remains a trusted auditor responsibility. The fixture auditor
accepts declared decisions, not independently measured scientific outcomes.
Its method names explicitly distinguish test promotion from real promotion.

## Security limits and scientific gates

Frozen dataclasses, private attributes and same-process HMAC keys are not
operating-system isolation. The tests exercise an interface hosted by trusted
Python code, not hostile Python placed beside hidden files. An AST check forbids
dynamic execution/I/O imports in these modules; a fresh-interpreter check
confirms they import without torch, NumPy, Gymnasium, world-model or task modules.
Neither test proves general capability security or operating-system isolation.

Before any scientific runner, separately design/review restricted IPC, process
isolation, trusted executable-operator hashes, actual meters, durable externally
anchored logs, checkpoint provenance and an independent evaluator with hidden
data unavailable to the proposer. Persist audit-replay protection across process
restarts. Generated variants must receive no arbitrary code/shell execution,
hidden filesystem access or network capability. These requirements are not
implemented by this fixture harness; no security settings were changed.

The harness cannot grant authorization, waive exclusions, select scientific
seeds or unlock H17. Previous H14–H16 results remain closed and H17's incomplete
seed-ingress coverage remains unresolved. No broad control, transferable
algorithm improvement, continual self-improvement or AGI claim follows.

## Verification and resources

Focused tests cover deterministic round trips, adversarial proposals, exact
cost bounds, complete fixture grids, cumulative budget exhaustion in every
dimension, charged failures, cache reuse, request bounds, chain integrity,
external truncation anchors, attestation binding/replay, archive-preserving
rollback and import boundaries. Two added adversarial cases first reproduced
three failures: Boolean journal-index acceptance, and list/dict audit decisions
raising TypeError. Both defects were fixed; **70 focused tests passed in0.09s**.

Commands, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_source_contracts.py -p no:cacheprovider -o addopts='' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_source_contracts.py tests/test_evolution1_feasibility.py tests/test_h17_seed_dependency_closure.py tests/test_h17_reservation_closure.py tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider -o addopts='' -q
```

Combined source-only regression result: **266 passed in7.30 seconds**. The full
scientific suite is deliberately outside this scope; no claim that it
ran is made. Existing protected-hash tests verify unchanged root instructions,
master context, session ledger, H17 draft and dependency artifact.
Actual scientific counts: **0 real interactions,0 imagined transitions,
0 optimizer updates,0 experimental execution seconds**. Fixture declarations
are not added to the experimental ledger. Source-test wall time is reported
separately. Ledger remains **305.842s used /3294.158s remaining**.

## One next milestone

Perform a source-only executable-adapter and isolation design review: specify
how trusted existing planners, meters and an independent evaluator can implement
this message contract without exposing hidden data or repository execution to
variants. That review must identify unresolved gates before requesting any
scientific runtime-readiness decision. No experiment is authorized here.

# H17 historical seed dependency closure — source only

Base: `07a91522f9ba443f9fb5ac7af1bb2cb99d1a171c`.
Branch: `codex/h17-seed-dependency-closure`.

The previous review certified27 explicit historical expressions and left40
unsupported records, including duplicate collision guards. This follow-through
extends arithmetic certificates to finite products, tuple binding, helper
assignments, bounded loops and imported constants/delegates. It does not run
historical Python: no module imports, config loaders, file-reading calls or
scientific operations from the reviewed sources are allowed. Unsupported
syntax, cycles, missing dependencies and operation limits fail closed.

For an inherited `load_*config` reference, bind the module's explicit committed
YAML path/default and parse that mapping directly. The historical loader is
never invoked and its runtime validation/authorization is **not** certified.
Record the YAML hash as a dependency. An unbound or non-config path is rejected.
This distinguishes reconstructing historical registration arithmetic from
executing the historical experimental entry points.

Inventory candidate RNG calls (explicit seed keywords, default RNG and manual
initialization calls) as AST text. This is a call-site inventory, not a verified
dataflow proof. Separately classify explicit root artifact seed fields. Preserve
registered block labels as labels/bases rather than inventing interval semantics;
exclude descriptive counts/statistics from numerical registration evidence.
Reject unclassified registration fields and malformed numeric seed metadata.

Every source and imported dependency is read from the **same historical Git
commit** as its configuration. Record dependency hashes and compare every
resulting historical seed with the existing conservative windows. Preserve old
captures and reservations; do not infer that independently defined streams are
unique merely from their union. Collision guards are sliced to own-set
declarations, not executed; this cannot certify the historical collision
checker's runtime behavior. Imported guards are not evidence of new seed draws.

Expand the inventory to previously inherited seed-group helpers. Failures in
those older helpers and metadata outside recognized registration fields remain
explicit blockers, rather than substituting a guessed constant or claiming
global completeness. This review alone cannot lock H17 or authorize execution.

No simulator, inference, training, new physics, numerical H17 registration,
allocation change or H14–H16 rerun. Five-source/t12 design remains
62,360 real /174,080 imagined /300-second proposed cap. Actual new counts are
zero; session ledger stays305.842 used /3294.158 remaining.

After tests and implementation commit, capture metadata with:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/review_h17_seed_dependencies.py --output artifacts/h17_seed_dependency_closure.json
```

Results and exact remaining gaps will be appended after capture. No scientific
result is collected or reinterpreted by this audit.

## Final evidence

**BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE**, with no provenance mismatch.
The historical **registry-expression** blocker is resolved for the fixed
inventory; a full RNG-call-site coverage claim remains unsupported.

Execution source revision: `14d7a28abd1e8a04df06f51ce8699af4c78bf74b`.
Final artifact: `artifacts/h17_seed_dependency_coverage_validated.json`, SHA256
`42eee2ea11e4ffbc4a870af77f7faf84472797fda5a9052888f62094b2ebc6bf`.
The earlier four captures remain separate records of checker development;
none is overwritten or presented as a scientific experiment.

- **76 function/version records across44 paths**, including every one of the
  prior67 records, now have arithmetic certificates; **zero unresolved registry
  expressions**. H15 delegates bind to historical H14, imported MCC constants
  bind to the corresponding historical source, and older Pendulum reservation
  chains resolve through committed configuration metadata.
- All extracted values fit the **existing** conservative seed reservations.
  Counts are unique values within a certificate, not a count of independent
  experiments or an assurance of no historical aliases. Composite registries
  include inherited reservations and overlap other certificates; do not sum
  those counts as additional evidence or interactions.
- **299 artifact root seed schemas** classified with **zero unclassified root
  seed fields**. Six artifact/version registrations contain explicit seed bases
  or block labels; every reported point lies inside an existing window. The
  Cline `[61000000,61100000]` labels are not silently converted into a closed
  interval, and query episode/transition counts are not mistaken for seeds.
  Per-seed prediction metrics and replication counts are explicitly descriptive
  fields; their outcome values are not inspected for this classification.
- **2,253 candidate seed-related call sites across284 source versions** are
  now inventoried, with function, line, callee and argument expression. This
  intentionally broad inventory includes metadata constructors, statistics
  functions and wrapper calls, not just RNG draws. It is not2,253 independent
  registrations or2,253 confirmed gaps. It excludes implicit interfaces with
  unrecognized naming and does not prove interprocedural dataflow completeness.
- The29 physics exclusions (including six ambiguous conservative exclusions),
  H17 draft and ledger hashes remain unchanged. All seven external manual-draft
  file hashes still match; no other worktree was edited.

The checker was captured successively at69/7,74/2,74/2,76/0 and76/0 certified/
unsupported function records as capabilities were added. Metadata initially
failed closed on three descriptive fields; their names were classified without
analyzing the stored performance values. These are source-tool revisions, not
repeated scientific evaluations or outcome-dependent H17 design changes.

Source-only capture times:7.851,7.787,8.182,13.071 and13.305 seconds. No simulator
construction or step, neural inference, training, imagined transition, new
physics choice, numerical H17 seed registration, lock or allocation occurred.
The scientific execution ledger remains **305.842 /3294.158 seconds**.

## Tests and independent checks

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h17_seed_dependency_closure.py tests/test_h17_reservation_closure.py tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider -o addopts='' -q
```

**171 passed in6.92 seconds**. Includes imported/local reference isolation,
same-history configuration/dependency hashing, guard handling, bounded loops,
tuple/product arithmetic, malformed/missing metadata rejection and all prior
source-only H16/H17 regressions. The final expected function grid is recomputed
from the locked **source inventory**, not from produced certificate rows; it
rejects omission/duplication. Artifact coverage is checked against all planned
artifact versions. Dependency/configuration bytes are independently re-read
from the recorded Git commit and their hashes verified. Tests require available
historical Git objects but no checkpoint binaries or scientific execution.
This is not a full scientific test-suite run or an external scientific replication.

Preserved hashes:

- Validated registry: `d823e9fd703076b543edeb74fc2c069282f92b9b7816cf6513bd0f01b6c9ef32`.
- Ledger: `ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117`.
- H17 draft: `4eb9401465744e2f29d026b9a42f6480015c1774cf66f676018eeaf256b45f0f`.

## Remaining gap and one next action

Complete a **source-only seed-ingress/dataflow coverage audit**: classify the
recorded call sites as true seed consumers, wrappers or descriptive metadata;
bind actual invocation configurations and offsets to the certified historical
sets; enumerate any calls not covered by a registry. Include every actual
collector reset/behavior and model/planner RNG purpose, rather than assuming
the presence of a registry function means all call sites obey it. Record
conservative exclusions or retain explicit blockers for unbounded cases.

This review establishes arithmetic/metadata coverage for its specified registry
and root-field schemas, not arbitrary nested fields, dynamic call paths,
deleted/unfetched history or undisclosed external reservations. The earlier
manual draft remains conservatively excluded and unauthorized regardless of
its unknown owner-finalization state. H17 target selection and numerical seed
registration must wait for the remaining coverage review. Its five-source/t12
design, proposed62,360/174,080/300s budget and all closed H14–H16 findings remain
unchanged. Nothing here is evidence for H17's scientific hypotheses.

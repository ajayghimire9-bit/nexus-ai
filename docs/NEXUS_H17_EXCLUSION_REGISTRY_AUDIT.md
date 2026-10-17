# H17 exclusion-registry audit — source metadata only

## Outcome

The H17 exclusion preparation now covers the fetched branch snapshot,
rather than relying only on the current checkout. The corrected inventory
contains **348 nonsymbolic refs**, **127 unique tip commits**, and **167
unique path/blob inputs**:165 configuration versions and2 MCC task-source
versions. It identifies **23 explicit/historically recorded MCC tuples**
and **6 additional ambiguous tuples**, excluded conservatively. All167
inputs parse without issues in the validated capture.

This is a metadata audit, not new research evidence about control. No new
physics or numerical seeds were chosen, no protocol was locked and no
allocation or authorization was created. H17 is still **not lock-ready**.
Zero real steps, imagined transitions, neural inference, checkpoint loads
or training updates. The ledger remains **305.842 s used /3294.158 s
remaining**, byte-for-byte unchanged. Historical results and main remain
unchanged.

## Provenance

Branch: `codex/h17-exclusion-registry-audit`.
Clean verified starting HEAD/GitHub readiness ref:
`ae5411dd411766f3fa231723ae78bde1c77987a0`.
Both Origin and GitHub were fetched without pruning or resetting work.
The inventory uses committed Git blobs from local and fetched remote
branch tips; it never imports their scientific implementations.

Implementation was committed as
`1ca0ae5c151e6485856e6398c77008543b32d80d` before the first audit.
Reader corrections and the unmodified first capture were then committed
as `1121246e96de5b2d54d3f3c477b3894c59504905` before the validated audit.
That second capture records this clean revision (`source_dirty=false`).

Captures are separate and preserved:

- `artifacts/h17_exclusion_registry_audit.json`, first capture with2 parsing
  issues, SHA256 `cb604b5de1dcdb16914773ad688c56e60ae47941192c2a9916c6b774e8a7fcbe`.
  It records `source_dirty=true`; do not relabel it a clean capture. Its
  configuration/task inputs were committed blobs, with hashes recorded.
- `artifacts/h17_exclusion_registry_audit_validated.json`, corrected reader,
  zero parsing issues, SHA256
  `d823e9fd703076b543edeb74fc2c069282f92b9b7816cf6513bd0f01b6c9ef32`.

The two captures contain exactly the same input path/SHA256 set and
exactly the same exclusion tuples. Their current audit-branch tip revision
differs; neither is a scientific rerun. No experiment seconds are charged
or reset. The historical H16 raw/parent/code hashes and consumed ledger
remain checked by the reused source-only provenance validator.

## What the inventory records

For every unique commit at the ref snapshot, list committed configuration
JSON/YAML and `src/nexus/tasks/mountaincar_continuous_family.py`. Read each
unique path/blob once. Record SHA256, Git blob ID, path and owning tip
commits, plus the full reference-name/commit snapshot. Symbolic remote
HEAD pointers are omitted; this explains348 rather than the earlier350
raw reference entries.

Read explicit source/target/evaluation physics from MCC-family configs
and MCC-named configs. Extract the task factory's literal physics rows
and keyword defaults with Python AST, **without executing functions**.
Add the previously recorded H16-feasibility exclusion list as historical
evidence, using its committed HEAD version. H16's consumed target is
also excluded through its configuration. No complement of the exclusion
set is drawn, ranked or evaluated.

Some older configurations concern discrete MountainCar or omit an
explicit family field. Plausible gravity/force-or-power/speed triples
from those files receive an **ambiguous_conservative** classification.
They are not relabeled as observed MCC experiments. The extra six are:

`(0.0015,0.0013,0.085)`, `(0.0022,0.0014,0.085)`,
`(0.0025,0.0013,0.07)`, `(0.0031,0.0007,0.09)`,
`(0.0035,0.0006,0.075)`, `(0.0037,0.0014,0.07)`.

Excluding these may reject a physically unused MCC configuration, but
does not admit a possibly used tuple as fresh. The plausibility bounds
are only a metadata-classification heuristic, not the future sampling
distribution or proof that every possible task parameterization is found.
The raw evidence gives paths and fields for each exclusion. Values are
preserved without rounding away distinctions.

## Seed-base reservations

The validated inventory records252 seed-base occurrences. For conservative
preparation, reserve each configured base through base+999,999 inclusive,
plus0–999,999 for legacy small training/collection seeds. Merge overlapping
or adjacent windows. This produces:

- 0–12,099,999
- 13,000,000–16,099,999
- 18,000,000–31,099,999
- 32,000,000–33,099,999
- 61,000,000–62,099,999
- 63,000,000–64,799,999
- 65,000,000–79,699,999

These are **conservative metadata reservations**, not an exact enumeration
of all seeds executed historically. Their large size is not a claim of
millions of consumed RNG streams. The H17 symbolic480-key schema is
unchanged. No numerical H17 seed mapping is generated or saved. A later
registration must still inspect implicit formulas/manual reservations and
validate the concrete mapping against the reviewed closed registry.

## Reader corrections and test results

The first capture rejected non-string keys in `v073_planning.yaml` and
`v08_adaptation.yaml`. Inspection showed that the issue was legitimate
numeric horizon keys (`candidates: {1:48,3:16,6:8}`). The initial suggestion
that on/off labels caused these two errors was premature and corrected.
The metadata reader now traverses integer-keyed mappings and retains their
type in evidence paths. This changes no historical configuration or runner.

The reader also locally restricts boolean resolution to true/false so
literal on/off/yes/no labels are preserved. It does not mutate PyYAML's
global loader or purport to implement every YAML1.2 feature. Duplicate
keys, invalid explicit physics, nonfinite/nonnumeric values and unsupported
key types still fail closed into recorded parsing issues. An issue is not
silently discarded or interpreted as a complete inventory.

Actual focused/regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider
```

**115 passed in0.92s**, final rerun **115 passed in0.90s**, including17 new registry tests and98 prior
source-only checks. New tests cover typed family evidence, ambiguous
exclusions, duplicate configs, malformed physics, AST-only literal
extraction, merged reservations, divergent-ref union, retained parse
failures, numeric keys, and local boolean-loader isolation. The existing
H16 provenance and source-only tests remain green. No simulator/training
suite was run or claimed.

The audit command (refuses output overwrite):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/audit_h17_exclusion_registry.py --output /new/path.json
```

A later invocation records its own fetched-ref snapshot, not an assertion
that today's refs never change. All code remains outside the world
package and performs no model/environment imports. The audit reads
configuration metadata, not confirmation outcome metrics.

## Remaining limits and lock status

`globally_complete_closed_registry` remains **false** deliberately. A
successful metadata parse cannot establish coverage of deleted/unfetched
branches, removed configurations, externally registered tasks, implicit
source-code physics or all manually reserved RNG streams. Frozen artifact
evidence, task-source review and branch ownership review must complete the
coverage argument before registering a new target.

The native-state runner gates, real checkpoint/tensor/data manifests and
independent protocol review also remain outstanding. No budget or
execution authority follows from this artifact. The proposed five-source
t12 counts remain62,360 real and174,080 imagined, not actual costs.

## One next recommendation

Review and accept the exclusion-coverage boundary, including implicit and
manual registrations, then use this versioned inventory for a separately
reviewed H17 target/seed registration before any scientific execution.

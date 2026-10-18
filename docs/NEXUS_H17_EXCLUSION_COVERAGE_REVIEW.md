# H17 exclusion coverage and registration readiness — source only

## Verdict

**BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE**

Provenance passes. The preserved29 exclusions cover every plausible literal
or recognized metadata tuple found by this review, including the named Cline
reservation. Nevertheless, complete parsing and covered seed-base literals
do not certify all generated seed ranges, uncommitted reservations or
unrecognized metadata. **Numerical H17 registration is not yet safe.**

No scientific execution, simulator, training, model inference, imagined
transition, new physics selection, numerical H17 registration, protocol
lock, allocation change, H14–H16 rerun or main merge occurred. The ledger
is byte-for-byte unchanged: **305.842 seconds used /3294.158 remaining**.
The date boundary does not reset that ledger.

## 1. Repository and input verification

Branch: `codex/h17-exclusion-coverage-review`.
Starting HEAD/local audit branch/GitHub audit ref all matched
`4a86031542229dbe738067c1d34532a553b1d69a`. The primary working tree was
clean. Both remotes were fetched. Origin has no dedicated Codex audit-branch
ref; its H16 results ref remains
`9474ec63bafbe03adb2b9557c03edfdca650a385`, verified as an ancestor of the
requested base. This is not a substitution or a provenance mismatch.

The repository is not shallow. Ancestry from readiness
`ae5411dd411766f3fa231723ae78bde1c77987a0` through the requested base passes.
Historical H16 parent/config/protocol/code hashes and the consumed ledger
pass the existing independent checker. The validated exclusion inventory
remains SHA256
`d823e9fd703076b543edeb74fc2c069282f92b9b7816cf6513bd0f01b6c9ef32`.
It was not edited; the six conservative ambiguous exclusions are retained.

Read AGENTS and the unchanged master-context/evidence sequence, H17
feasibility/readiness/exclusion reports, current draft/configuration and
review tools, and the relevant historical sources and reservation records.
The master context was read in full earlier in this continuing review
sequence; its unchanged hash and research vision remain preserved. This
review does not replace the long-term vision with MCC-specific claims.

New reviewer implementation: `f789230f26399959ca07e3c105a53b1aaa37ff30`.
The source-only first capture is preserved in
`artifacts/h17_exclusion_coverage_review.json` (SHA256
`89664121bac14ad3bff47de1bd7badd2ca4537b9737794fad9174ba01948609a`).
An uppercase manual-protocol filename was subsequently included by
case-insensitive matching; a behavior-based regression was added. The
corrected implementation was committed as
`0018d2a400d27fb98356a224131c0755aed3b54a` before the final capture:
`artifacts/h17_exclusion_coverage_review_validated.json`, SHA256
`0d3fe10e12fb5117c3d8c06ae7a8f54e5aba8faccae2f5ab1084882b85b25b1c`.
These are source audits, not experimental retries. Neither earlier capture
nor any historical research result was rewritten.

## 2. Reachable-history coverage

The old audit walked unique branch tips. The new reviewer walks **every
commit reachable from fetched local/remote refs**, then inventories unique
path/blob pairs. The final capture covers **302 reachable commits** and
**2,032 input versions**:

-208 configuration path/blob versions, including **43 absent from the
 previous tip-only inventory**;
-535 Python source/script versions;
-990 Markdown document versions, including root instructions/context;
-299 artifact JSON versions indexed; **42** MCC-specific or named
 manifest/provenance versions have registration metadata extracted.

All historical configuration versions parsed without issues. Thus removal
or alteration before a branch tip no longer hides those reachable config
versions. A synthetic regression deletes a config before the tip and
verifies that its historical reservation is still found.

This claim is limited to the fetched, non-shallow object graph. It does not
prove coverage of deleted/unfetched refs, unpublished files elsewhere or
external instructions. The final capture has one additional commit and
artifact relative to the first because the initial review was preserved.

## 3. Physics, source code, documents and manifests

The review retains **23 explicit/historical MCC tuples plus six ambiguous
conservative tuples**. It adds no new exclusion tuple: all plausible
literal/recognized metadata tuples found already belong to the existing29.
This is evidence of agreement, not proof of no implicit registrations.

Static review reads literals in relevant source/script ASTs, including
`CLOSED_*`, `LOCKED_TARGET`, inherited reservation declarations and task
factory rows. No functions such as `holdout_from_rule` are called. Source
selection grids are not evaluated to draw an H17 target. Documentation
scans identify existing tuple references and manual/open-ended seed lines;
they do not analyze return comparisons or use outcomes to choose physics.

The main code paths reviewed include:

- `src/nexus/tasks/mountaincar_continuous_family.py`;
- `src/nexus/world/xenv_transfer.py`, `xenv_context_code.py`,
  `xenv_deep_trunk.py`, `xenv_residual_context.py`, `xenv_prior_scale.py`,
  `xenv_low_budget.py`, `xenv_cartpole_target.py`;
- `src/nexus/world/mcc_native_rms.py`, `mcc_residual_scale.py`,
  `mcc_multitask_128.py`, `mcc_multitask_128_confirm.py`,
  `mcc_planning_ranking.py`, `mcc_planning_ranking_confirm.py`;
- `src/nexus/world/h14_candidate_reuse.py`, its runner,
  `h15_candidate_reuse_confirm.py`, `h16_same_state_library.py` and runner;
- `src/nexus/world/data.py`, `train.py`, `tree_reuse_lookahead.py` and
  `prefix_max_tree_reuse.py` for collection/RNG/registry context;
- current `src/nexus/h17_*` contracts, H17 draft JSON, historical configs,
  and `docs/NEXUS_XENV_CONTEXT_CODE_PROTOCOL.md`, prep/source-audit records.

Artifact review indexes every reachable JSON version and extracts only
registration fields/recognized wrappers from MCC-specific or named
manifest/provenance files. This includes H14/H15/H16 metadata,
`artifacts/nexus_evidence_manifest.json` and the control-replication
checkpoint manifest. Flat `target_physics: [g,p,v]` result metadata is
handled as well as config-style `[[g,p,v]]`. A regression ensures flat
metadata is not lost and scientific `cells`/`results` are not traversed.
No checkpoint tensors are loaded or inference performed.

**Remaining artifact limitation:**257 indexed JSON versions, including
the first coverage capture, are not in that metadata-read subset. Nested
registrations outside recognized metadata wrappers are not certified.
Most may be irrelevant to MCC; that is not a substitute for a recorded
family/registration classification. Literal scanning also does not resolve
arbitrary computed physics or manually maintained external records.

## 4. Manual/uncommitted reservation inspected without modification

The named worktree exists at
`/Users/ajayghimire/.cline/worktrees/xenv-context-adaptation/nexus-ai`.
It remains on `cline/xenv-context-adaptation` at
`9d3e5ce6389c7e64174896800df851925a87b457` with seven untracked files.
The other registered worktrees were clean at capture. This draft was not
imported, run, moved, staged or changed.

Read its YAML, protocol and source. Its existing target
**(0.0034,0.001,0.055)** is already one of the29 exclusions. Its configured
reset/candidate/prior/target bases are64,000,000,64,010,000,64,020,000 and
64,030,000. Each is inside the preserved conservative reservations. Its
allocation is `authorized=false`, `runs=0`; its historical usage placeholder
does not replace or reset the present305.842/3294.158 ledger.

The capture hashes all seven files, including the uppercase protocol.
Config hash: `ffb3e094d854c17b7c9176297873d34451a91236ab701b167d57984c8bf0f0f3`.
Protocol hash: `054174489ea42283911eae6e0aa8302d6b39a792c7248de1b50836ea9a4119ed`.
Source hash: `80d436dd428887fd406848b3cd85d3fa323207b5548f7169064d302c90a8cf53`.

These observations resolve whether this particular local draft is
available and whether its known tuple/bases were omitted: it is available,
and those known values were not omitted. They do **not** turn a moving,
uncommitted draft into a portable finalized reservation or establish its
complete generated RNG set. A GitHub-only clone cannot reconstruct these
untracked files from their hashes alone. A centralized reservation/closure
record is still needed; do not fabricate a cancellation or authorization.

## 5. Historical RNG bounds and H17 symbolic schema

No identified base/block literal lies outside the old conservative windows.
However, this checks literals, **not** their offsets or generated sets. The
review identifies **30 historical registry-function records across18 source
paths** (`seed_groups`, `seed_streams`, `check_seeds`) without a reviewed
range-bound certificate. They are enumerated with source blob, function,
line and body hash in the capture. This is not30 discovered bugs or30
independent experiments.

For example, H16 redraw uses
`redraw_base + 10000*s + 100*k + t`; H14/H15 use a different stride; source
collection, initialization and minibatch RNGs have separate rules. The
untracked Cline guard uses yet another reset/candidate/collection grid.
An exclusion window beginning at a base is not sufficient until those
domains and maximal offsets are reconciled against the window. Existing
guard functions discover additional registries via imports; no such imports
were executed here. Existing aliases remain historical facts, not retuned.

The H17 schema itself remains structurally sound: **480 distinct symbolic
keys**, with deliberate sharing of reset/L0 across state sources and
generator redraw across model arms, separate diagnostic redraw and separate
collection/training namespaces. Its validator detects missing keys,
duplicates, concrete aliases and overlap with a **supplied** closed set.
It cannot certify the completeness of that supplied set. Thus structural
soundness does not establish numerical-registration safety. No numerical
H17 mapping was generated or saved.

## 6. Design and resource invariance

The executable draft validator confirms the same five sources, ten
independent training pairs, one reset/pair, t12, H16,16 candidates and
equal-controller-mixture-minus-reference primary. Model arms are compared
at each identical source state with shared libraries/actual returns.
The joint state/L0 interpretation and causal limitations are unchanged.

Planned real steps:15,360 source +1,280 target train +320 target validation
+480 controller generation +120 reference generation +19,200 prefix replay
+25,600 candidate realization = **62,360**.
Planned imagined scoring:51,200 diagnostic +122,880 state generation =
**174,080**. Proposed wall cap remains **300 seconds**. These are proposals,
not allocated resources or executed counts. No cap or scientific rule changed.

## 7. Tests and commands actually run

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/review_h17_exclusion_coverage.py --output /new/path.json
```

**128 passed in1.02s**, final rerun **128 passed in0.98s**, after adding13 coverage tests to115 existing
source-only regressions. New behavior checks cover a configuration removed
before the branch tip, an uppercase uncommitted protocol, implicit literal
constants, manual reservations, flat artifact metadata, ignored result
metrics, seed-window endpoints, provenance-before-coverage verdicts and
fail-closed registration decisions. No simulator/training test suite was run.
Both review captures preserve blocked outcomes; all work was source-only.
Final read-only checks confirmed all seven local draft file hashes remain
unchanged, as do the validated registry and the session-ledger hash
`ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117`.

## 8. Exact missing evidence and minimum corrective action

Before a separate target/seed registration:

1. **Generated-seed coverage certificate:** reconcile the30 source-function
   records and imported registries against the preserved windows. Record
   source hashes, bounded domains, offsets and covered intervals. Any
   unresolved rule must receive a conservative bounded reservation or remain
   explicitly blocked. Checking only base literals is insufficient.
2. **Portable manual-reservation record:** commit an additive reservation
   entry for the seven-file Cline draft, citing its observed hashes, known
   target and reviewed seed extent, with an explicit owner/status or closure
   statement. Preserve the worktree and do not claim it was finalized/canceled
   without evidence. No historical allocation may be repurposed.
3. **Metadata classification/closure:** classify the remaining indexed
   artifact families and any registration fields outside recognized wrappers,
   reconcile implicit source rules and document the supported fetched/local
   coverage boundary. Do not equate a parse-success flag with completeness
   or invent assurance about unavailable external/deleted registrations.

These are evidence gaps, not a provenance failure and not proof that an
undiscovered collision actually exists. The existing29 exclusions and six
ambiguous conservative cases remain intact. H17 is still unlocked,
unallocated and unauthorized.

## One next scientifically justified action

Create and independently review an **additive authoritative reservation
closure manifest** covering those seed bounds, manual draft and metadata
classifications; only then re-evaluate readiness for separate H17 target/
seed registration. Do not select or run a new experiment in this step.

# Wave18 — M4 neuro-symbolic canonical evolution (Pre-Assessment Code Freeze)

**FROZEN PRE-ASSESSMENT PROTOCOL (Commit 1).** All Wave 8–18 unit tests, real MPS
smoke tests, and the 324-cell source efficiency gate have passed. No fresh Wave 18
definitions (`mechanism_wave18_fresh_assessment.py`) or results document exist in
this freeze commit.

## Starting revision and hardware

Requested branch:
`cursor/seed-wave18-m4-gpu-neuro-symbolic-canonical-evolution`.
Actual clean base `708310d9ed0a156ba6f52b0ff378f4b222bb097a`, fetched from both
Origin and GitHub. Existing worktrees and main are unchanged.

Hardware detection reports **Apple M4**, macOS26.6.2 arm64, PyTorch2.14.1,
`mps.is_built()==True`, `mps.is_available()==True`. PyTorch is already installed
in `/Users/ajayghimire/Projects/nexus-ai/.deps`; system Python without that
dependency path cannot import it. No installation or neural execution was
needed for detection. Detection reported0 allocated MPS bytes.

## Clarified physical boundary and approved resource limits

The request simultaneously requires `scripts/run_wave18_m4_neuro_symbolic_assessment.py`
in Commit1 and prohibits every filename matching `*wave18*assessment*` there.
The owner explicitly answered **"Allow runner only; forbid fresh definitions
and results"** for Wave18. Only that required runner may match the pattern at
Commit1. Fresh definitions and results remain absent until a passing freeze;
no literal zero-pattern claim will be made.

The owner explicitly answered **"Approve these exact limits"** to the proposed
allocation: MPS only;200 wall seconds and200 CPU seconds per
assessment;1GiB process memory;zero simulator interactions;one assessment
attempt;no increase to the carried session ceiling. Ordinary source-only
engineering tests and hardware detection are separate from this proposal.
This does not increase the carried session ceiling or permit automatic retries.

The existing generic `seed/experimental.py` host refuses GPU dispatch. Do not
change that historical contract to make tests pass. The dedicated Wave18
supervisor reuses E1 Journal/write_new, reserves before dispatch, launches only
the vetted worker, enforces wall deadlines externally and CPU via RLIMIT_CPU,
samples RSS every30ms and bounds the MPS allocator to256MiB. Source/fresh rows,
stdout/stderr and process receipts survive interruption. Unsettled reservations
remain fully charged. macOS sampled RSS has possible one-sample overshoot and
is **not** byte-exact kernel memory isolation; the approved1GiB cap terminates
the worker on an observed excess. This cannot promise an OS hard memory boundary.

Carried frozen ledger:3128.309460455996s used/471.690539544004s remaining.
Prior separately reported symbolic CPU: Wave15–17 total188.041673s. Subtracting
that entire subtotal conservatively leaves283.648866544004s, not a new grant.
No ledger reset is allowed. Engineering test CPU was historically unavailable;
do not represent that as zero or promise enough budget for two new full runs.
Track B stays closed, with0 model calls and0 debit; new GPU work needs its own
explicitly metered account. A200-second attempt is not automatically a200-second
allowance for each preparation, retry and fresh run independently.

## Hypotheses and non-guarantees

1. Guarded, boundary-safe canonicalization exposes useful shared internal cores
   across alternative AST factorizations.
2. Public-feedback neural proposal ordering reduces actual search work, after
   charging residual encoding, descriptor scoring, forwards, updates and expansion.
3. Their combination preserves correctness and improves both registered costs
   versus the strongest full-accuracy control on new authored tasks.

These are hypotheses. Do not force a neural baseline to hallucinate, guarantee
20% savings, claim that GPU execution alone makes Python enumeration fast, or
turn the requested under10-second runtime into a measured result. The neural-only
top16 decoder is a limited ablation, **not a representative LLM baseline**.
Online supervised fitting to verified public ASTs is not established meta-learning.

## Reuse and implementation boundaries

Reuse Wave17's immutable interpreter, exact cache semantics, active clarification,
lock-only archive restoration, typed macro/MDL owner, public-only environment and
standalone saved verifier. Do not edit or rerun historical fresh suites.

The new solver uses a task-local binding of the trusted frozen solver code object
to new cache/enumerator factories. It does not evaluate generated Python, copy
the large solver, modify its globals or monkeypatch historical modules.
Pure typed ASTs remain the only generated executable programs.

Canonicalization proposes explicit algebraic affix commutations and unequal-token
filter/affix commutations. It uses a deterministic normal-form preference, not two
opposite rewrite directions until timeout. Every changed expression is checked
against the original on all public inputs and **all** canonical boundaries,
including empty input. When certifying a full transform, strict support must
also match. Finite core signatures retrieve hypotheses; they are not proofs of
arbitrary-input equivalence. Native SWAP_ENDS is size2: do not pad it and call it
a genuine size5 core merely to satisfy a desired test assertion.

The source implementation preserves locked canonical program provenance, counts
distinct-task core support and uses the existing MDL owner to retain supported
cores. A bounded constant-free size4–5 table supplies metered peeled proposals.
Only verified locked references may restore cold ownership.

## Neural architecture and feedback boundary

Public observations yield24 predeclared scalar features: input-kind flags,
length means and shift min/max/mean/variance, first/last/reversed conservation,
token deletion/addition/substitution, repeated boundaries, empty fractions,
integer parity preservation and integer difference statistics. Arbitrary local
token equality codes are packed on CPU; feature statistics execute on MPS.
No task IDs, target ASTs or evaluator-only outcomes are inputs.

MLP:24→32 Linear, GELU, LayerNorm, Linear to14 opcode/schema labels plus dynamic
macro outputs. AdamW lr.003, weight decay.01, exactly3 steps after a publicly
verified unique solution. Dynamic output expansion copies prior rows and AdamW
moments, initializes only new rows deterministically and preserves step counts.
No private accuracy may choose labels, updates, optimizer settings or topology.
No CPU inference fallback is permitted. MPS reproducibility tolerance1e-6 is
tested explicitly; no universal bitwise-determinism claim is made.

## Conditions, measurements and gates

Six requested methods share the public-only24-read cap and bounded typed grammar:
neural top16 decoder; scratch; ordinary memoization; whole-macro;
neuro-symbolic without pruning; full neuro-symbolic with pruning. Symbolic-only
methods honestly record no GPU calls. Same upper budgets do not imply equal
consumed work. The baseline is not artificially modified until it fails.

Record accuracy, incorrect unique locks, ambiguity, actual delayed-task archive
reuse, mask errors, hierarchical reuse and complete per-task/seed traces.
Record both work identities plus forward/encoder/update/expansion counts,
linear MAC estimates, synchronized GPU-section wall time, process wall/CPU,
RSS and MPS allocator/driver peaks. GPU-section wall time includes dispatch and
synchronization overhead: it is not isolated hardware-kernel timing or energy.

Work identity is Wave17's nine fields plus `neural_proposer_work`; primitive
identity is the same five interpreter counters. Canonicalization and core-table
execution are charged in compression fields. Neural work includes raw public
packing elements, visited proposal-descriptor nodes, forwards, optimizer steps
and head expansion events. Those units are disclosed heterogeneous proxies;
linear MACs and measured time are reported separately, not disguised as equal
FLOPs. Every method's actual cost is retained.

Before freeze, require all Wave8–18 tests, real MPS tensor/update/expansion tests
and the measured source18-task gate. Full must preserve54/54 status/private
outcomes, zero mask errors/false locks/OOG piecewise evaluations,3/3 correct
ambiguity and actual delayed archive reuse. Require at least20% lower work and
opcode totals versus whole-macro and strict improvement against every other
full-accuracy method. A failed gate blocks Commit1; do not waive it or fake
baseline failure. Source engineering tests currently do not establish this gate.

Only after a passing physical freeze may new18-task/three-seed/six-method
definitions be authored. Keep the agreed interleaved third distractor to make
the archive block compatible with18 total tasks. Expected grid324 comes from
the locked manifest; missing cells/seeds fail, rather than reducing expectations.
Three vocabulary seeds are correlated, not independent pretrained models.
Use evaluator-only exact fixture semantics; private scoring happens after choices
and public feedback are locked. No holdout result can change Phase1 code.

Fresh gate: full54/54 and all correctness requirements, plus lowest work and
primitive costs among full-accuracy methods. Report the stronger source20%
threshold and under10s aspiration separately; do not redefine success afterward.
Any failure, incomplete execution or unsupported performance claim remains
visible. A cross-suite165.30s Wave17 versus new runtime comparison is descriptive,
not an isolated GPU speedup experiment: workloads and method counts differ.

## Freeze manifest (locked for Commit 1)

**Source eligibility passed.** All 134 Wave 8–18 unit tests, real MPS smoke checks,
and the complete 324-cell source comparison passed:
- `nexus_m4_neuro_symbolic_full`: `54/54` private accuracy, `573,165` total work
  (`-76.030847%` vs `nexus_whole_macro_only`'s `2,391,261`, passing the `<= 0.8 * whole`
  gate), and `1,694,043` primitive op steps (`-79.743454%` vs `nexus_whole_macro_only`'s
  `8,362,941`), strictly beating `nexus_typed_without_pruning` (`611,019` work,
  `2,393,481` primitive op steps).
- See the [source preflight](NEXUS_WAVE18_M4_SOURCE_PREFLIGHT.md) and
  [machine-readable receipt](../artifacts/seed_wave18_source_preflight.json).

Locked Phase-1 SHA-256 hashes:

- Learner (`src/nexus/seed/wave18_m4_gpu_neuro_symbolic_learner.py`): `4127f0063720180d4ac64a6b47d534d32e57d060346b0c1bf3568fe75dac3844`.
- Runner (`scripts/run_wave18_m4_neuro_symbolic_assessment.py`): `69a578f42c084e561b8cc9efabb9f482fa68f81ec23fef7097f3c6c2cda6434d`.
- Verifier (`scripts/verify_wave18_m4_neuro_symbolic.py`): `bc425467c5273e66c63db3803eae0f5629059c2c2ee31b5eba91dff7b4a44849`.
- Tests (`tests/test_seed_wave18_m4_neuro_symbolic.py`): `3ef4e808a0ed29bba831f9cb26dcfa11f7a105caaf1d1cd5dc37e38637043600`.
- Track B runtime (`src/nexus/seed/local_model_runtime.py`): `5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.

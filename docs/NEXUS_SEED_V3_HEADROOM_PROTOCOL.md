# v3 high-headroom investigation benchmark — protocol

Base: reviewed tip `490ab00` of `cursor/seed-worker-div-confirm`.
Branch `cursor/seed-v3-headroom`. Development design lock. Do not rescore
Depth 1–2 v1/v2, the capability audit, or conversation-capability
tools / `ordinary_cache` / `simple_frequency` grids. Those already sit
at 95–100% and have no ranking headroom. Do not edit
`src/nexus/seed/local_model_runtime.py`. Standing grant: 900 s this
experiment if a later transfer run is authorized, carried session
**3126.028358455996 used / 473.9716415440039 remaining**, local CPU.

This commit designs and structurally certifies the benchmark. It does
not train φ on Set A, does not evaluate Set B, and does not claim
learning-to-learn.

## Why a new benchmark

`simple_frequency`, tools, and ordinary cache already solve the locked
Depth 1–2 grammars. The v2 investigation policy also solved 24/24 under
`simple_frequency_active`. New ranking or widening code tested there
cannot show a gain. v3_headroom is the replacement testbed.

## Locked properties

1. **Orthogonal specialist regimes.** Four clusters — list-length /
   filtering, modular arithmetic, order / permutation, string-or-key
   grouping — each own three Set A and three Set B operators and one
   specialist probe. Operators are identity on a foreign cluster tag.
   The top Cluster-1 probe therefore has **zero disagreement** on all
   Cluster 2, 3 and 4 programs. Balanced `simple_frequency` interleaves
   the four slices and needs **4×** the support checks
   (3× extra calls) of query-conditioned selection to cover one
   specialist slice.
2. **Depth 3–4 under B = 35.** Targets are 3- and 4-step compositions.
   `|H| = 12³ + 12⁴ = 22 464 > 2 500`. One call per program covers
   35 / 22 464 < 30%. Brute-force and `no_widening` are expected to
   stay below a 30% solve rate on this H without learned contextual
   ranking and the `filter(P) -> map(F)` template. That solve-rate
   claim is a later measurement, not a result of this lock.
3. **φ keyed by algebraic invariants.** Weights map
   `(Support_IO_Invariant, Operator_Algebraic_Signature) → score`.
   Signatures are read from specialist-probe I/O, never from `op_name`.
   Train on Set A (12 operators). Freeze φ. Evaluate on disjoint Set B
   (12 new operators, same four automatic signatures).

## Transfer gate (not run here)

After φ is frozen, Set B mean candidate calls must be **≤ half** of
`untrained_default` on the same B tasks, same B = 35, same controller.
Only that comparison can establish investigation transfer. It is not
established by this design.

## Expected grid for this lock

Structural certificate only: orthogonality on A and B, `|H|`, call
budget, frequency-waste ratio, disjoint names, invariant φ keys.
Zero neural calls. Zero Depth 1–2 rescoring.

## Gates

`fixed_boundary` remains the default. Do not promote learned ranking.
Do not merge `main`.

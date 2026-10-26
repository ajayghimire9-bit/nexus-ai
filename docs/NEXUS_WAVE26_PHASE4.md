# Wave 26 Phase 4 — three-way failure router and mechanism synthesizer (locked before seeds 4001–4005 and Group A)

Branch `codex/wave26-phase4-invent-mechanisms` (from Phase 2 `3026ab3`). Code: `src/nexus/wave26_phase4.py`,
driver `scripts/phase4_invent.py`.

## Design

**Base M.** White-box F[p], S[k, o] and Sort[o] over the domain-free binding grammar: base bindings use 3
threshold quantiles and k ∈ {1, 2, 3}; base depth is 2.

**Synthesizer grammar.** `comp(ord(o), cond, transform)`, where:
* the order `o` is a slot: position asc/desc, or field asc/desc;
* `cond` ∈ {all, head k, tail k, first_occ path, pred p};
* `transform` ∈ {id, proj path}.

That gives 10 schemas. F, S and Sort are instantiations of them, so a deleted primitive can be
re-synthesised. An instantiation identical by construction to a present base mechanism is skipped.

**Router** (diagnosis = the first that applies):
1. **Proved ΔM barrier.** All library mechanisms have verified sub-multiset/permutation classes, so a public
   output that is not a sub-multiset of its input proves ΔM.
2. **Library schemas** (depth 2).
3. **ΔB.** An extended binding grammar (every observed threshold, k ≤ 5) at depth 2.
4. **ΔC.** Base bindings at depth 3.
5. **ΔM.** Exhaustive class-pruned synthesis otherwise.

**Answers.**
* When the base tier fits, the answer is certified over the base tier (Occam convention, declared).
* When it fails, the answer is certified over the **union** of the repair tiers. UNIQUE is issued only if
  every fitting tier agrees; otherwise the system probes across them (S3 objective, 3 probes per query) or
  stays AMBIGUOUS.
* A schema used by a certified ΔM answer is admitted to the library, with a verified class and its
  discovery cost recorded.
* Net benefit of an admitted schema = reuse tasks × mean ΔM cost − discovery cost − class check.

**Fault streams** (generator labels are used for scoring only):
* **Mixed stream:** ΔB, ΔC and pure ΔM faults, 3 of each per world per seed. "Pure" means the base tier,
  rebinding and deeper composition all provably fail.
* **Deletion streams:** Sort, F and S, each deleted from M, with 4 consecutive pure-ΔM tasks per world.
  They use 6–7-item lists, so S[k ≤ 5] cannot stand in for Sort.

## Dev history (seeds 721–725) and decisions

* **Run 1.** Routing 90 / 90. S's order variants were separate schemas, so S was "reinvented" up to three
  times. One false certificate: a depth-3 composition with a spuriously admitted schema beat invention under
  lexicographic tiers.
* **Decision 1.** Order is a slot (factored M × B), and base-equivalence is checked per instantiation.
* **Decision 2.** After a base-tier failure, the answer is certified over the union of repair tiers.
* **Run 2 (locked code).**
  * Routing: ΔB 30 / 30, ΔC 30 / 30, ΔM 30 / 30. Solved: 30, 24, 30.
  * Deletion streams: Sort routed ΔM 10 / 10, 40 / 40 solved, later cheaper 10 / 10 streams. F 39 / 40 solved,
    later cheaper 8 / 10, but mean later work is above first. S 35 / 40 solved, later cheaper 6 / 10.
  * The union check charges a full synthesis scan on every non-base task, which erodes reuse savings.
  * 1 false certificate. In an F-deletion stream, once F had been re-synthesised, a depth-1 program over the
    evolved library fit and was the minimal explanation. The generated teacher (depth 2) was not minimal for
    the evolved library. This is a limitation of minimal-size certificates over a growing library.

**Expected to fail:** the primitives gate (S, F reuse cost) and the zero-false-certificate standing gate.
Expected to pass: the router gate.

## Gates (as in the driver docstring)

1. Router accuracy ≥ 0.8 per class.
2. Per deleted primitive: ≥ 80% of first encounters routed ΔM, ≥ 80% solved, and later encounters cheaper on
   ≥ 80% of streams.
3. Group A: ≥ 50% of base-tier failures repaired, and second encounters cheaper than first (pooled).
4. ≥ 1 admitted schema with positive net benefit on later Group A tasks.
5. 0 false certificates.
6. G_tycho.
7. Identical fresh-process replays (synthetic and sealed, separate calls).

**Sealed run.** Group A seeds 3001–3010 are loaded only through the token-gated, hash-verified loader. The
library starts empty for Group A. Outputs are aggregates only, and errors are recorded by exception type.

## Confirmation results

### Synthetic (seeds 4001–4005, frozen `e9896e2`)

* Run: 398.5 s. Separate fresh-process replay with `PYTHONHASHSEED=271828`: 402.2 s, identical digest
  `d789b34d…73e4`.
* Artifact: `artifacts/wave26_phase4_confirmation.json`, sha256
  `9586baa6e2f7a93f835162610452c99a6fddff1beacc9236ac1a20a6f50d5adb`.

| Router class | Routed correctly | Solved |
| --- | --- | --- |
| ΔB rebind | 30 / 30 | 30 / 30 |
| ΔC recombine | 30 / 30 | 25 / 30 (5 stay AMBIGUOUS: depth-3 hypothesis sets are not enumerable for probing) |
| ΔM new mechanism | 30 / 30 | 30 / 30 |

| Deleted primitive | First encounter routed ΔM | Solved | Streams with cheaper later encounters | Mean work, first → later |
| --- | --- | --- | --- | --- |
| Sort | 10 / 10 | 40 / 40 | 10 / 10 | 169,822 → 40,483 |
| F | 10 / 10 | 40 / 40 | **4 / 10** | 64,155 → **329,622** |
| S | 10 / 10 | 40 / 40 | 8 / 10 | 66,605 → 47,651 |

* 0 false certificates; G_tycho 210 / 210.
* All 120 deletion tasks were solved. Every deleted primitive was diagnosed ΔM, re-synthesised from the
  lower-level grammar, admitted to the library and reused.
* **F's later encounters are more expensive.** After a base-tier failure, the sound union-of-repair-tiers
  certificate requires a full synthesis scan on every task, including tasks answered from the library. For
  F that scan outweighs the reuse saving. This is the price of the soundness fix made after dev run 1, where
  lexicographic tiers produced a false certificate.

### Sealed Vault Group A (seeds 3001–3010) — NOT EVALUATED

* The token-gated loader refused all 10 loads: "file hash mismatch" at manifest entry 5.
* With the owner's authorisation, the tuning agent re-ran the vault's `generate_manifest.py` (output
  discarded) and ran `shasum -c` on the manifest, printing only status words and counts. Results:
  * the regenerated manifest is byte-identical to the committed one (sha256 `36ae82fc…6609`);
  * 5 of 39 listed files verify;
  * the other **34 listed files do not exist** in the vault directory (all manifest paths are flat file names).
* No vault path or content was displayed. No task was loaded, executed or seen.
* The registry had claimed `phase3/vault_group_a` before loading. That ordering is fixed: the vault is now
  verified before any claim. A one-time owner override is recorded for the re-run.
* **Group A remains blocked until the owner's blind session makes the vault contents match the manifest.**
  Phase 6, which depends on Group B and the external family through the same manifest, is blocked the same way.

## Phase 4 gate check

| Gate | Result |
| --- | --- |
| Router ≥ 0.8 per class | **PASS** (1.00 / 1.00 / 1.00) |
| Primitives (route, solve, later cheaper on ≥ 80% of streams) | **FAIL** (F 4 / 10 streams cheaper) |
| Group A ≥ 50% of failures repaired; second encounters cheaper | **NOT RUN** (vault integrity) |
| ≥ 1 admitted schema with positive net benefit on later Group A tasks | **NOT RUN** |
| 0 false certificates (synthetic) | **PASS** |
| G_tycho / G_replay (synthetic) | **PASS** / **PASS** |

**Phase 4 overall: FAIL** (primitives gate), with the sealed part not evaluated. Per the owner's instruction
of 2026-10-26, the roadmap continues to Phase 5 regardless, with this result recorded as is.

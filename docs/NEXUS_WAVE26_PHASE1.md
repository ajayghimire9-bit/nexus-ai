# Wave 26 Phase 1 — economical-transfer crossover map

Branch `codex/wave26-phase1-crossover` (from Phase 0 `c9abac3`). Code: `src/nexus/wave26_phase1.py`,
driver `scripts/phase1_crossover.py`.

## Grid (dev seeds 701–705; complete)

* **Oracle cost:** `c_oracle ∈ {20, 200, 2000, 20000}`.
* **World cells:** depth 2 / 3 fields / small grammar; depth 2 / 5 / medium; depth 2 / 8 / large; depth 3 / 5 /
  medium. Records have 1 bool, 1 score, F−3 score-correlated distractors and 1 tag; names are randomised.
* **Infeasible cells:** depth 4 and 5. The exact certifier enumerates to depth 3, and depth-4 enumeration is
  outside the per-run budget.
* **Arms:** exact_eig_enum, s2_transferred_rule, myopic_s3, revisable_controller, full_nexus_vault, all
  exact-certified.
* **Amortised one-time costs:** S2 mining (~330k units per seed) and contract learning (~33k) are charged at
  episodes / 100 per cell.
* **Episodes:** multi-query (q1 ambiguous on the public pairs, q2 from the sampler); 4 per seed in depth-2
  cells, 2 in the depth-3 cell.

The first attempt (900 s, in-memory) was lost at the cap and fully charged. The checkpointed grid then
completed in two runs (850.6 s + 46.7 s) under the owner's additional 2,400 s allocation. Artifact:
`artifacts/wave26_phase1_dev_grid.json`, sha256
`7821d34b7a1bbe907d491fc51f9776438c289de26871e425865ede5bd3307e40`. 770 rows, **0 false certificates**.

**Fully-loaded cost relative to exact_eig_enum** (< 1 = cheaper). The c = 200 and c = 2000 rows lie between
the c = 20 and c = 20000 rows shown.

| Cell | c | S2 rule | myopic S3 | revisable | full vault | (a) | (b) | Solved, full / exact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d2/F3/small | 20 | 1.557 | 1.138 | 1.033 | 1.456 | no | no | 40 / 40 |
| d2/F3/small | 20000 | 1.117 | 1.097 | 1.045 | 1.180 | no | no | 40 / 40 |
| d2/F5/medium | 20 | 1.174 | 0.923 | 0.803 | **0.503** | yes | no | 40 / 40 |
| d2/F5/medium | 20000 | 1.125 | 0.926 | 0.879 | **0.822** | yes | no | 40 / 40 |
| d2/F8/large | 20 | 1.002 | 0.946 | 0.764 | **0.375** | yes | no | 40 / 40 |
| d2/F8/large | 20000 | 1.002 | 0.934 | 0.775 | **0.432** | yes | no | 40 / 40 |
| d3/F5/medium | 20 | 1.005 | 1.111 | 0.462 | 0.130 | yes* | no | **9 / 12** |
| d3/F5/medium | 20000 | 1.004 | 1.118 | 0.486 | 0.189 | yes* | no | **9 / 12** |

\* Cheaper partly because fewer queries were answered.

**Reading.**
* **Crossover (a) exists** once worlds have five or more fields or a larger grammar. There, proved-contract
  pruning repays its learning cost at every oracle cost tested.
* **No crossover in the smallest world.** Learning costs more than it saves.
* **(b) never holds.** The transferred S2 rule does not beat exact EIG anywhere on the grid once its ~330k
  mining cost is amortised.
* **Probes vs certification.** Raising the oracle cost narrows the vault's advantage, because probes become
  the dominant cost and all arms use similar numbers of probes.

## Locked confirmation cell and rule (committed before seeds 1001–1005 run)

**Selection-rule correction (disclosed).** The rule declared before the grid compared cost only and picked
d3/F5/medium at c = 20. There the vault arm answered 9 of 20 queries against exact EIG's 12, so it
partly wins by giving up. The rule now requires `solved(full) ≥ solved(exact)`, and the same condition is
added to the Phase 1 pass criterion. Under the corrected rule the selected cell is **d2/F8/large at
c_oracle = 20** (relative cost 0.375; it ties c = 200, and ties go to the lower cost).

**Confirmation.**

```
python3 scripts/phase1_crossover.py --confirm --cell d2/F8/large --c 20 --n 8 --out artifacts/wave26_phase1_confirmation.json
```

* Seeds 1001–1005 are one-use and registry-enforced.
* 8 multi-query episodes per seed.
* Fresh-process replay with `PYTHONHASHSEED=271828`.

**Phase 1 PASS iff:**
* full_nexus_vault fully loaded < exact_eig_enum,
* AND solved(full) ≥ solved(exact),
* AND 0 false certificates in every arm,
* AND an identical replay digest.

S2 vs exact (mark (b)) is reported as well. It is expected to fail, as on the whole dev grid.

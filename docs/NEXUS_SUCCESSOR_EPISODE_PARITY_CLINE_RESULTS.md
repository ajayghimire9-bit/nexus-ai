# Cline strict full-episode successor parity — results

## Decision

The locked 120-episode serial-versus-batched parity screen **passed**:
`episode_implementation_parity_established_on_tested_grid`. Across the complete
60-cell grid (ten decoders × three development tasks × archived-student and
zero contexts), **every one of the 60 paired 200-step episodes produced an
identical action sequence** (zero divergent cells, no first-divergence step).
The maximum Q deviation was **7.204433320140424e-05** (within the predeclared
2e-4 absolute / 2e-5 relative tolerance, which never excused an action), and
the **per-step reward and total-return deviations were exactly 0.0** in every
cell. Frozen fingerprints were stable in all cells and all 60 checkpoint files
hash-verified before and after.

This is **implementation parity on the tested grid**, the final gate the
committed proposal required before any controlled runner integration. It is
not universal bitwise parity on all unseen inputs, not a control-return
improvement, not cross-family weight transfer, not learning-to-learn and not
AGI. No default runner was switched here; the batched scorer remains opt-in
and integration remains a separate explicit engineering step.

## Execution provenance and honest attempt accounting

Branch `cline/successor-episode-parity`. Protocol/implementation locked and
tested at `f62da33`; the one-run allocation was explicitly authorized by the
user on 2026-10-16 and committed at
`c9480d44d2b3bbd29e7b83afd726944c398391f4` (clean tree before collection, as
required). The recorded execution is the **complete** run of the identical
locked configuration after that commit.

**Aborted first attempt, disclosed honestly:** the first launch of the same
locked command was killed externally at ~30 seconds by the agent tool's
command timeout — **not** by any protocol cap — before the runner saved
anything. No result, partial grid or outcome existed; nothing was observed,
tuned or selected from it. Its partial real environment steps are unrecorded
and bounded by that attempt's ~30-second wall clock (well below the 24,000
step grid; the complete run needed 65.7 s). The recorded run then executed the
full grid from the same fixed seeds. No other retries occurred.

## Cost

**65.672 s wall** (180 s hard cap), **24,000 fresh real environment steps**
(120 episodes × 200), **816,000 model calls** (12,000 × 51 + 12,000 × 17),
**18,504,000 imagined transitions** (24,000 × 771), **0 optimizer updates**,
CPU only, one Torch thread, allocation `configs/cline_successor_episode_parity_allocation.json`
(SHA256 below, one-run record consumed by this result).

## Per-step mechanics and evidence

Each cell loaded the hash-verified frozen decoder, the saved student encoder
(for archived-student cells) and the genuine archived context vector with
fingerprint agreement; each implementation ran its **own** environment from
the identical coupled reset seed `61_000_000+100d+t`, with candidate seeds
`61_100_000+10_000d+1_000t+k` identical across both implementations and both
context groups. Per-step call accounting held exactly (51 vs 17 calls at 771
imagined transitions). Example cell return: −127.7069 for both
implementations, return deviation 0.0. The simulator never entered the world
model or its candidate scores.

## Tests

- Pre-execution offline guards: 9 passed (locked configuration/budget, seed
  coupling and disjointness from all sixteen closed registries plus the
  config-scan floor, allocation gate and tampering, overwrite/dirty-tree
  refusals, meter caps, cell metrics, first-divergence logic, label rules).
- Post-execution Git-only recorded tests recompute the committed artifact:
  full 60-cell grid, per-step seed/observation/reward consistency, metric and
  summary recomputation, and corruption rejection. No binaries needed.
- The relevant offline repository suite was re-run after execution:
  **130 passed, 4 deselected** (120 prior relevant tests plus the 10 new
  episode-parity recorded tests; the deselections are the same
  environment-stepping and local-binary exclusions as before). The full
  repository suite was not run; it contains training and environment
  collection outside this task.

## Provenance

- Raw `artifacts/cline_successor_episode_parity.json` SHA256
  `88d34b323392f9be060c834087c0988ba257e41a8f988484bc933b8c6a417a19`.
- Config `configs/cline_successor_episode_parity.yaml` SHA256
  `a5be6018e321579ef8456727c8aeb6d663a69804038851c70a5c80211beeddc3`.
- Protocol `docs/NEXUS_SUCCESSOR_EPISODE_PARITY_CLINE_PROTOCOL.md` SHA256
  `65d5d6663cb001a6c2a23f9beaf432792a81c8a9582012471b7d5879148d7176`.
- Allocation `configs/cline_successor_episode_parity_allocation.json` SHA256
  `c32c327c19ce41ea412960bdbadb22fad8f60b57f5cecec4694c19f889e3a706`.

```sh
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 -m pytest \
  tests/test_cline_successor_episode_parity.py \
  tests/test_cline_successor_episode_parity_recorded.py -p no:cacheprovider
# The recorded execution refuses a repeated/overwriting run.
```

The original checkout's uncommitted MountainCarContinuous confirmation
preparation is untouched. `main` is unchanged; no closed screen, split or
budget was reopened.

## One next recommendation

With synthetic, archived-state and now full-episode implementation parity all
established on tested inputs, the evidence gate for **controlled integration
of the opt-in batched scorer into the experiment runners** is met. That
integration is a separate engineering step on a separate branch: switch the
runner's successor search to `PreparedSuccessorSearch` behind the existing
opt-in surface, keep the serial path available, and re-run the offline parity
suites. No control-improvement hypothesis is reopened by this report.

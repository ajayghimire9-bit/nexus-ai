# Evolution-2.17 — n=3 persist-versus-reset science

One authorized run. **COMPLETE. PRIMARY: inconclusive.**
Grant consumed. No retry. Not n=10. Not learning-to-learn.

Cited config `8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`.
Grant source commit `170dec7bcab2aa2074d46357315f033c8f7127dc`.
Execution HEAD at start `56f20c7e21dcf002c2a2698107655b097d272acd`.
Frozen request yaml/allocation/protocol hashes unchanged. H17 blocked.
H16 ledger file untouched (`ff4c51e2…`). This run used 22.027 s wall.

## Integrity

Four locked unused roles matched their SHA256 digests and stayed off
occupied, family-declared, and H17 exclusion lists. Occupied defaults
were not credited. `env_cap=17280` was fully used. The grant was unused
before this run and is now consumed (`runs=1`).

## Resources

| Item | Actual |
|---|---:|
| Real environment steps | **17,280** |
| Imagined transitions | 14,601,600 |
| Residual fits | 6 |
| Wall | 22.027 s |
| CPU | 25.077 s |
| Time cap | 900 s |
| Interrupt | none |

Source arrays used the named unused source physics
`(7.5, 1.35, 1.4)` and `(0.85, 1.3, 0.85)`, not `(10,1,1)` / `(1,1,1)`.

## Primary contrast

Persist minus reset on hidden development, n=3, Bonferroni t=9.924843,
practical margin 0.05:

| Bundle | persist | reset | difference |
|---|---:|---:|---:|
| 0 | 0.565 | 0.565 | 0.000 |
| 1 | 0.378 | 0.378 | 0.000 |
| 2 | 0.106 | 0.106 | 0.000 |

Mean **0.000**, interval **[0.000, 0.000]**. Label: **inconclusive**.
Random and evolution received the same hidden scores.

Raw hidden means: −794.3, −732.0, −753.4 (identical across methods).

## What this does and does not show

Hidden evaluation used the same two locked catalogue variants, the same
source-trained residual, and the same seeds for every method. Proposer
weights therefore could not change the development return. The zero
contrast is a property of that locked scoring rule, not evidence that
persist, reset, random, and evolution are interchangeable controllers.

This is not n=10 confirmation, not a general control improvement, and
not learning-to-learn. Do not start Evolution-3 from this result.

## Methodological diagnosis (E2.18) — does not rewrite the label

Root cause: `run_bundle` rolled out the same two locked hidden variants
and appended that return to every method. Hidden outcome did not depend
on the selected planner.

Replayed proposer choices from recorded revealed returns and locked
seeds (no new collection):

- Persist and reset selected the **same** 4-slot sequences on every
  family of every bundle.
- Evolution differed from persist. Random differed on some families.
- All methods shared persist's proposal seed.

Causal-sensitivity tests on synthetic fixtures now PASS: different
forced selections produce different hidden scores; swapped selections
move the scores; identical selection and seed match; hidden outcomes
cannot enter training. Equal logical hidden slots are 4 per method per
bundle; physical episodes are cached by `(bundle, family, slot, variant)`.

Completed E2.17 development outcomes are observed and cannot confirm a
repaired hypothesis. Fresh upper budget for a later independent n=3
screen: 7,680 + 7,200 + 9,600 = **24,480** real steps if every method
selects a distinct hidden planner; 17,280 if they all collide. The
E2.17 grant is consumed. `dispatch()` stays refused.

## Policy-state diagnostic (E2.19) — does not rewrite the label

Saved revealed feedback, same persist/reset seed and ties: weights
change; unconstrained first choice differs on all three bundles;
forced anchors restore identical training sequences; hidden order
flips on bundle 1. Synthetic conflict fixtures change free-slot
choices. That is a functioning memory-to-choice mechanism, not a
transfer result. Report `NEXUS_EVOLUTION2_PERSIST_RESET_POLICY_STATE.md`.

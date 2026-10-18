# Evolution-2.7 — source-array persist authorization request

Branch `cursor/evolution2.7-source-persist-request` from
`92d703594bed63abe6abeb792fb975527c47299e`.
Status: **REQUEST ONLY — COLLECTION UNAUTHORIZED**.
Does **not** rewrite v2, v2-pilot, or n=3. Does **not** collect.

This lock exists so the next human approval can bind one config hash
and one step budget. It is not a scientific result.

No collection. No named holdout. H17 blocked. Ledger
**305.842 / 3294.158**.

## 1. What would be persisted later

Matched residual-recipe arrays, one train and one val file per
`(family, bundle)`:

`artifacts/evolution2_source_arrays/{pendulum,acrobot}/bundle{k}_{train,val}.npz`

Required keys: `obs`, `action`, `next_obs`, `terminated`, `env_seeds`.
Sizes: 1024 train / 256 val. Family default source physics only.
Occupied defaults are the source, not a new unused instance.

This request does **not** name a holdout, touch confirmation or H17
files, or enable scientific dispatch.

## 2. Cost to request later

| option | real steps | files | standing fit |
|---|---|---|---|
| v2 / v2-pilot source | 10 × 2 × 1,280 = **25,600** | 40 | yes (100k) |
| n=3 matched source | 3 × 2 × 1,280 = **7,680** | 12 | yes |

Time is unmeasured. Fitting after persist is a separate disposable
clock and is not authorized here. This document authorizes
**0 s and 0 steps**.

A later approval must cite this configuration hash, set
`authorized: true`, and set `env_cap` to 7,680 or 25,600. The
standing grant alone does not start collection.

## 3. What this lock does not do

- No Gymnasium construction, `collect_transitions`, or file writes
  under `artifacts/evolution2_source_arrays/`.
- No rewrite of v2, v2-pilot, or n=3 hashes.
- No worksheet shrink and no H17 unlock.

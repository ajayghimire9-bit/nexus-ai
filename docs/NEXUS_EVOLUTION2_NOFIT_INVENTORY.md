# Evolution-2.4 — no-fit residual inventory

Branch `cursor/evolution2.4-nofit-inventory` from
`efd59b45e07860b6a2fb6c017ecd4d6cff487e07`.
Not a scientific result. Zero new environment steps. Checkpoints are
read-only. Ledger not debited. Frozen H16 scientific ledger remains
**305.842 / 3294.158**.

## Finding

**`NO_FIT_TEN_BUNDLE_UNAVAILABLE`.** A ten-bundle no-fit screen cannot
be assembled from existing residual weights.

| family | matched residual files | required | shortfall |
|---|---|---|---|
| Pendulum | 3 context-optimization `mlp_u1000` | 10 | 7 |
| Acrobot | 10 historical lookahead development seeds | 10 | 0 |

Those two sets are **not** one residual recipe. Acrobot files belong
to the closed lookahead development run. Confirmation,
latent-generalization, and control-replication weights stay excluded.

Seed0 identities match the residual timing probe. Files are not
rewritten.

## Worksheets (hypothetical, unauthorized)

Skipping source collection and fitting does not rescue v2:

| screen | real steps | imagined | planning | verdict |
|---|---|---|---|---|
| full v2 no-fit | 72,000 | 110,592,000 | ~764 s | **NO-GO** |
| v2-pilot no-fit | 32,000 | 49,152,000 | ~340 s | **BLOCKED** (Pendulum shortfall) |
| n=3 micro | 9,600 | 14,745,600 | ~102 s | **NOT_V2** |

n=3 would rewrite n and Bonferroni. It is not a silent v2 pass and
is not authorized here.

## What this lock does not do

- No Gymnasium construction, training, or env steps.
- No rewrite of v2 or v2-pilot hashes.
- No reuse of confirmation or H17 files.
- No named holdout and no dispatch.

## Next action

Do not collect replacements. Keep dispatch blocked. The next allowed
step remains a separately authorized persist of matched
Pendulum/Acrobot source arrays, or an explicit non-v2 n=3 lock.

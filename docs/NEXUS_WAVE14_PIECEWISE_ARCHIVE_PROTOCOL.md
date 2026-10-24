# NEXUS Wave 14 Pre-Registered Protocol: Piecewise Probe Allocation and Cold Archive Routing

**Branch:** `cursor/seed-wave14-piecewise-probe-allocation-and-cold-archive-routing`  
**Parent Commit:** `a48001e` (Wave 13 closed developmental / invalid)  
**Track B Policy:** LLM/coding closed (`model_calls == 0`, `frozen_debit_s == 0.0`)

Wave 12 (`e940b82` → `6bdf9ae`) and Wave 13 (`460a04a` → `a48001e`)
remain permanently closed. This protocol does not amend those commits
or reuse `w12f_*` / `w13f_*`.

## Two-commit physical separation

Commit 1 freezes the learner, runner, verifier, unit tests, Wave-13
postmortem, and this protocol. It must not contain
`mechanism_wave14_fresh_assessment.py` or any `*wave14*assessment*`
path. Commit 2 may create that assessment file once, run the single-shot
grid, and record results. Frozen Commit 1 files must stay byte-identical.

## Frozen SHA-256 digests (filled immediately before Commit 1)

- `src/nexus/seed/wave14_piecewise_archive_learner.py`: `f1e84a2e73d7e42be2bfb3d8a88f4a07840ba17303c07230a6c28c589396a17e`
- `scripts/run_wave14_piecewise_archive_assessment.py`: `af83319cd196147fb7a6bee41306ade0d2a601f365c4e629269f0c38660c54f4`
- `scripts/verify_wave14_piecewise_archive_enumerator.py`: `0df6238791a5493aee4e72cb738f7ad32e50b2e2a4e245eadd15b2217e69ad84`
- `tests/test_seed_wave14_piecewise_archive.py`: `8a8d885427ebdf4cdf3c6e8a529a1991b81725af8a7620019db3cad8233199c1`

## Architecture (two Wave-13 fixes)

1. Static constants are only INT `(0, 1, 2)` and empty SEQ `()`.
2. **Fix 1 — strict tier routing.** Tier-0 is EVEN/ODD plus size-1..2
   transforms only. Size-4+ guards (`SEQ_EQ`, `INT_GE`, `TOK_EQ`) and
   size-3+ transforms are not evaluated in Tier-0. Tier-1 is the
   relevance-gated macro / 1-wrapper beam. Tier-2 queries the cold
   signature archive *before* Tier-3. Tier-3 enumerates atomic guards
   of size 4..6 and transforms of size 3..7. Once-used macros with
   `inactive_age >= 3` move to `cold_archive`.
3. **Fix 2 — full-budget piecewise.** When single-branch synthesis
   fails, every remaining public probe is drawn before 2-guard search.
   Branch soundness is implication `G => T(x)==y`, not biconditional
   residual equality. `min_branch_support >= 2`. Distinct non-identity
   transforms. Confirmatory probes charged in `probe_work` /
   `probe_primitive_op_steps`.
4. Dual identities unchanged from Wave 13.
5. Five label-blind methods share one enumerator.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave14_piecewise_archive.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave14_piecewise_archive_assessment.py
PYTHONPATH=src:.deps python3 scripts/verify_wave14_piecewise_archive_enumerator.py
```

# Recovery-action policy — protocol

Development only. Baseline SHA
`e3d21b66785408a357d8f108231264ced4c0964b`
(`cursor/seed-lexicon-knowledge-vault`). Research branch
`cursor/seed-recovery-policy`. Do not merge main. Do not edit
`local_model_runtime.py`. Do not debit the frozen CPU ledger
**3564.568 s used / 35.432 s leftover / 0 s debit**. Do not write
`chat_usage.json` or `metal_ledger.json`. Ranking stays paused.

The previous diagnostic meta-policy (capability/evidence audit) lost to
fixed rules: learned 19/24 versus fixed 24/24. This study replaces those
internals for **post-failure coding recovery**. It reuses
`evaluate_python_payload`, `input_contract`, `public_failure`,
`plan_constrained_edit`, `KnowledgeVault` / `retrieve_for_question`, and
the equalized method / reconstructing-verifier design. It does not reuse
the symbolic investigation φ internals.

## Question

After source-task experience, can a compact linear policy choose better
recovery actions on unfamiliar authored tasks than the same tools under
strong fixed policies, at comparable accuracy and lower total cost?

Updating weights is not learning-to-learn. Fixture success is not model
competence.

## Episode

Shared initial public failure, then at most four actions from:

| Action | Implementation | Cost |
| --- | --- | --- |
| INSPECT_SCHEMA | `describe_input_contract` / `input_structure` | 1 tool |
| RETRIEVE_DOCS | vault ingest + `retrieve_for_question` | 1 retrieval |
| REQUEST_DISTINGUISHING_EXAMPLE | probe + explicit `reference` teacher | 1 teacher query or unavailable |
| REVISE | same public-evidence repair + worker | 1+ worker execs |
| STOP_UNRESOLVED | halt | 0 |

The controller sees the public task view only. Family labels, private
tests and reference functions stay outside features.

## Methods (equal access)

A. Immediate revision  
B. Fixed diagnostic rules on the same features  
C. Source-frequency action order  
D. Learned regularized linear scorers  
E. Reset weights and shuffled weights  
F. All cheap diagnostics first  

Same initial failed files, same repair operator, same budgets.

## Splits

Source 8, development 6, retention 2, locked assessment 4. Families are
separated by repair mechanism: schema, missing values, API docs, wrong
assumption, multi-step, immediate revise, stop, misleading cue, excluded
composition, excluded sort family.

## Metrics

Primary: identifiable private correctness. Secondary: tool executions,
teacher queries, wall, confident errors, appropriate stops. Report
accuracy and cost separately. Do not accept reset/shuffle alone.

Acceptance: learned identifiable private correctness strictly above the
strongest simple baseline (A/B/C/F), or tied with fewer tool executions.

## Live inference

Blocked. Closed ledger leftover is 35.432 s and frozen. A 1.5B grid
needs a separate ~900 s CPU allocation. See results `BLOCKED_BUDGET`.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_recovery_policy.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_recovery_policy.py artifacts/seed_recovery_policy
PYTHONPATH=src:.deps python3 scripts/verify_seed_recovery_policy.py artifacts/seed_recovery_policy/seed_recovery_policy.json
```

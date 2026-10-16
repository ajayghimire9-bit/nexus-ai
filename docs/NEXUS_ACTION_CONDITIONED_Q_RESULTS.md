# Action-conditioned first-action Q — incomplete execution

A later fail-closed resume completed a **separate** 60-cell artifact without modifying this file. See `docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS.md`. This incomplete capture remains the original one-run record.

## Registered decision

The one authorized run is **incomplete**. Label: `incomplete`.

The 240-second cap was reached at **240.000 s** during the last evaluation visitor. The locked grid requires 60 evaluation cells; **59** were saved. Missing: decoder 9, development task 2, zero visitor. Official complete-grid audit correctly rejects the capture. **No decoder-level 95% interval is a registered primary result.** A timeout is not a scientific negative, not equivalence, and not a gain.

This does not establish or refute a first-action return improvement versus H=16, does not close the score-correction branch by the registered failure rule, and is not control improvement, learning-to-learn or AGI.

## What completed

Source collection finished: **160/160** cells (10 decoders × 8 tasks × 2 states). The 16-coefficient action×observation Q and the 7-coefficient additive baseline were fit on those unique labels, frozen to disk at **179.904 s**, and reloaded before development steps. Config/protocol hashes match the locked files. Frozen world models, encoders and sequence-value V were not written. Checkpoint audit after the run: 120 verified, 0 missing, 0 mismatched.

Source-only fit RMSE (complete, before the timeout; not a decision screen):

- Action-conditioned Q: 69.99, 60.14, 68.76, 64.42, 63.71, 65.38, 73.87, 71.52, 71.21, 67.55
- Additive Q: 72.73, 62.24, 70.98, 66.15, 65.70, 67.13, 75.90, 72.86, 73.04, 69.17

Fifty-nine saved evaluation cells rebuild from stored traces, scores and the frozen Qs. They are not a substitute for the missing cell and were not used to retune features, ridge or the screen.

## Resources

One run, no retry. Real steps **45,143** of 45,240 (source 30,720, collection 3,000, first-action 11,423). Imagined transitions **11,587,768** of 11,612,160. Local CPU. Paid services unused.

The one-run authorization ledger is consumed (`remaining_session_allowance_s = 0`). The exhausted 3,600-second standing session file was not modified (SHA `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`).

- Protocol commit `28c8a3fab4e4b8396b12355fb16e760c733fbfbf`
- Execution commit `7a1f39176acd38f5592d055b7afaf735325ecc8f`
- Config SHA256 `3c260ac2f78278280de8ccaf9a91d6c0e456bcaaad50b95f31e91209b1cad14a`
- Protocol SHA256 `76c06fd1de355d7176f7165b6e2dc1cfceb0729b67ea5cac244e595207bfa597`
- Raw SHA256 `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680`
- Fit SHA256 `2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae`

The runner refuses overwrite. Completing the grid requires a **new** explicit approval (higher wall-clock cap and either overwrite permission or new artifact paths). This report does not authorize that run.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_action_conditioned_q.py tests/test_action_conditioned_q_feasibility.py tests/test_action_conditioned_q_recorded.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q.py --audit
```

The `--audit` path rejects this capture, as required for an incomplete grid.

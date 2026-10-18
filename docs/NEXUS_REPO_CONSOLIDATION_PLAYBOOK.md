# NEXUS repository consolidation playbook

Read-only operating plan. This file does not authorize deletion, merge,
history rewrite, or scientific execution.

## Purpose

Future agents must not repeat closed experiments or rebuild components
that already exist. Consult, in order:

1. `docs/NEXUS_CANONICAL_CURRENT_STATE.md`
2. `docs/NEXUS_CODE_REUSE_MAP.md`
3. `docs/NEXUS_FULL_RESEARCH_REUSE_AUDIT.md`
4. `docs/NEXUS_HYPOTHESIS_REGISTER.md`
5. `artifacts/nexus_branch_inventory.json`

## Allowed on a cleanup branch

- Documentation, generated indexes, read-only inventory tools
- Push of the cleanup branch

## Forbidden without a new explicit human approval

- Deleting or force-updating any branch
- Merging into `main`
- Rewriting history
- Removing scientific artifacts or closed splits
- Unlocking H17
- Debiting the scientific ledger
- Training, simulation, or new holdout selection

## Procedure used here

1. Stash unrelated WIP and untracked adapter drafts.
2. Branch from verified HEAD `4a08b26f81cbe314ae475e71419344e688ab571a`.
3. Run `python3 scripts/nexus_branch_inventory.py` (no checkout).
4. Read the hypothesis register and package surfaces.
5. Write the audit, current-state, and reuse-map documents.
6. Classify branches for later human-approved cleanup. Do not remove them.

## Recoverable backup

`artifacts/nexus_branch_inventory.json` records every seen name, SHA,
subject, family heuristic, and remotes. That is the pre-cleanup backup.
It is not a git tag and does not replace branch refs.

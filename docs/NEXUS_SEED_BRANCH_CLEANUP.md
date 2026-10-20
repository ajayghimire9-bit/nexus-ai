# Seed branch and duplicate-code cleanup

Owner request: delete unnecessary branches and code. Starting revision:
`ad8b65c155f20a71a82f1ee51bcde9e1fd353492`. Cleanup branch:
`codex/seed-repository-pruning`. This is repository maintenance, not research.

## Branch scope and safeguards

The [pre-deletion inventory](../artifacts/seed_branch_cleanup_plan.json) records
222 local branches and 187 GitHub branches. Of these, 211 local names and 179
GitHub names point to commits already reachable from the reviewed main revision.
Each retirement requires matching local/remote tips, ancestry, an unoccupied
worktree, and a durable annotated GitHub tag verified by its peeled commit ID.
GitHub branch deletion uses atomic exact-tip leases; local deletion uses
compare-and-delete refs. A changed tip aborts rather than discarding new work.

The read-only planner is `scripts/audit_seed_branches.py`. It does not authorize
or perform deletions. The [execution receipt](../artifacts/seed_branch_cleanup_receipt.json)
records what actually happened. The original retirement receipt remains intact.

Kept: main, this cleanup branch, six branches checked out in other worktrees,
and three branches with commits outside main. The existing open PR's branch is
among the occupied worktrees and is retained. No worktrees, ignored checkpoints,
run directories, source data or other-host branches are deleted. The root
checkout's two unrelated untracked adapter files remain unchanged.

All historical research commits remain reachable from main and exact-tip tags.
Archived branch links can be recovered using the receipt's branch/tag mapping.
Archive tags are durable history, not active research branches. Restoration:

```sh
git fetch github --tags
git switch -c cursor/context-adaptation-pilot archive/seed-cleanup/2026-10-20/cursor/context-adaptation-pilot
# Only if publishing the restored branch is desired:
git push -u github cursor/context-adaptation-pilot
```

No force-push of commit history, garbage collection, default-branch change or
merge into main is part of this task.

## Code actually removed

Five identical scalar finite-number predicates were removed from action-ranking,
contract, readout, learning-validation and nonlinear-learning evidence readers.
They now reuse the existing stdlib-only `grounded_audit.finite`. Public names
`finite` and `numeric` remain available through imports. Boolean values, numeric
strings, NaN and infinity remain rejected; finite Python integers/floats retain
the same behavior. Four unused math imports were also removed.

This avoids five competing copies of the same validation rule without deleting
reproduction modules or changing any model, score, experiment metric or result.
The [code-change receipt](../artifacts/seed_pruning_changes.json)
records exact before/after hashes. No original protected file required a new
preservation override. Historical bytes remain at the starting Git
revision; previous preservation receipts and result artifacts are untouched.

The existing source audit deliberately does not license deletion based solely
on an import graph. Historical reproduction runners and dynamic paths are not
dead code merely because Seed does not import them at startup. Shared Journal,
controller, neural factory and planning dependencies remain.

## Verification and resources

Cleanup tests exercise protected/occupied/unmerged/stale-tip rejection, remote
backup verification and unchanged scalar-validation semantics in a stdlib-only
process. Repository checks verify preservation overlays and current document
links; existing Seed/Lab/planning tests cover runtime compatibility. Exact test
outcomes:

- Initial focused cleanup checks: 10 passed in 0.06 seconds.
- Complete relevant suite, including two subsequent receipt checks: 304 passed
  in 27.77 seconds. Command: `python3 -m pytest -o addopts='' -q tests/test_seed*.py
  tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py
  tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py
  tests/test_factory.py`, with source/dependency paths and single-thread settings.
- `python3 -I -S scripts/check_repository.py`: valid; 38 documents, 151 local
  links, 2,013 original files unchanged and 17 pre-existing explicit evolutions.
- `python3 -I -S scripts/verify_seed_nonlinear_learning.py`: valid repository-only
  replay of the original failed screen; raw SHA256
  `c6c62c01d4b957c5928599884cdf499a462f6063b423fc45775515ac4763b650`.
  This command does not inspect binary checkpoints or run models.
- All 746 artifact files present at the starting revision verified unchanged;
  exact SHA256 inventory is in the receipt. `git diff --check` passed.

Actual retirement: 211 local branch refs and 179 GitHub branch refs. All 211
GitHub archive tags were verified before deletion. Immediately after retirement,
11 local and eight GitHub branches remained. Publishing this cleanup branch adds
one GitHub branch. Counts describe that dated operation, not a permanent limit.

No scientific experiment, model inference, training or environment collection.
Scientific ledger unchanged: 1916.6321034559958 seconds used and
1683.3678965440042 seconds remaining. This cleanup makes no new capability claim.

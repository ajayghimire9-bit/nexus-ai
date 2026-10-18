# NEXUS branch ancestry and cleanup proposal

Status: **review only**. No deletion, force-push, rewrite, or merge.
Inventory HEAD: `f9154f08e480db631d20f5594f51dcf8cac379cc`
`main`: `d36b49f519496f29282d1321d5314a623c2ee280`

Computed with `scripts/nexus_branch_inventory.py` against local heads,
Cursor Origin (`origin`), and GitHub (`github`). Ancestry is
`git merge-base` plus `rev-list --count`. Individual files inside
topic branches were not checked out.

Ledger unchanged: **305.842 / 3294.158**. H17 stays blocked.

## 1. Source-verified counts

| Quantity | Value |
|---|---|
| Unique names | **146** |
| Local | 146 |
| Local + Origin + GitHub | 101 |
| Local + GitHub only | 20 |
| Local + Origin only | 18 |
| Local only | 7 |
| Remote SHA mismatch | **0** |
| Shared tips | 5 groups / 8 extra names |
| Ancestor of `main` | 140 |
| Ahead of `main` | 1 |
| Diverged from `main` | 4 |
| Is `main` | 1 |
| Delete now | **0** |

`main` and GitHub/Origin `main` match `d36b49f`. After the authorized
research-tip merge, most historical topic tips are already reachable
from `main`. That does **not** make them disposable. They remain the
named provenance for closed results.

## 2. Duplicate tips

| SHA | Names | Proposal |
|---|---|---|
| `e4daa4e` | `codex/evolution1-resource-ledger`, `codex/evolution1-task-metadata` | Keep one name; optional alias archive |
| `0224391` | `codex/h17-seed-dependency-closure`, `codex/h17-seed-ingress-audit` | Keep both H17 review names |
| `ff26193` | `codex/action-value-alignment-audit`, `codex/replanning-aligned-readout` | Keep one name; optional alias archive |
| `2dc746b` | `cursor/late-control-gap-design`, `cursor/late-control-gap-execution` | Keep both; execution name is on a design SHA |
| `9d3e5ce` | `cline/xenv-context-adaptation`, `cline/xenv-deep-trunk` | Keep one name; optional alias archive |

## 3. Active and diverged

| Branch | Relationship | Ahead / behind | Proposal |
|---|---|---|---|
| `main` | is_main | 0 / 0 | Retain mainline |
| `cursor/evolution2-pendulum-acrobot-protocol` | ahead_of_main | 1 / 0 | Retain active |
| `cline/successor-episode-parity` | diverged | 10 / 99 | Retain unmerged |
| `cline/successor-search-archived-parity` | diverged | 6 / 99 | Retain unmerged |
| `codex/successor-search-archived-parity` | diverged | 4 / 99 | Retain unmerged |
| `codex/successor-search-efficiency-audit` | diverged | 2 / 99 | Retain unmerged |

## 4. Presence gaps (not unpublished science)

Local-only (7): `codex/evolution1-source-contracts`,
`codex/evolution1-task-metadata`, `codex/h17-seed-ingress-audit`,
`codex/replanning-aligned-readout`, `codex/commitment-value-diagnostic`,
`cursor/late-control-gap-execution`, `cline/xenv-context-adaptation`.

H14/H15/H16 execute branches are on Origin, not GitHub:
`cursor/h14-candidate-reuse-execute`,
`cursor/h15-candidate-reuse-confirm-execute`,
`cursor/h16-same-state-library-execute`.
Retain. Optional GitHub mirror is a human decision.

## 5. Proposal rules

1. **Do not delete** any branch.
2. Results and H17 review branches stay even if they are ancestors of `main`.
3. Optional remote archive means hide-from-default-clone after human
   approval, never `git branch -D` or force-push.
4. Duplicate-tip aliases may later keep one advertised name.
5. Diverged successor-search branches stay until independently merged
   or explicitly retired.
6. The active Pendulum→Acrobot protocol branch stays until a later
   review decides whether v2 supersedes it on `main`.

Machine-readable per-branch labels:
`artifacts/nexus_branch_inventory.json` field `cleanup_proposal`.
Every row has `"delete": false`.

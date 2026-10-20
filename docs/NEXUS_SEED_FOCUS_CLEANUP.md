# NEXUS Seed consolidation

Base: a3fe49adeb0040fc9c10b253f0fc86c4de125bb6. This cleanup follows the
human request to make Seed the active project and retire unnecessary clutter.
It is engineering,not a scientific result or permission expansion.

## Current guidance replaces contradictory scheduling

The old master mixed159,703bytes of chronology with current rules, including
outdated pending statuses and financial/legacy roadmaps. The new master is a
short current briefing. AGENTS now states Seed's learning-to-learn objective,
actual positive/negative evidence, reuse obligations and operational limits.
The complete standing authority section is preserved verbatim: no new budget,
main permission, shell access, cloud authority or evaluator privilege was added.

All five original context/instruction/index files were archived byte-for-byte
under [the dated context archive](history/seed-focus-2026-10-20/README.md).
Closed experiments, checkpoints,raw results and original scientific paths stay
unchanged. Old reproduction links may use their original relative locations;
the snapshot is historical evidence,not the active command guide.

## Actual code cleanup

Seed's existing bandit accidentally pulled historical PPO/experiment modules
through package initializers. Meta, evolution, RL and world package exports are
now lazy; explicit old imports still return the same classes/functions. The
planner's historical WorldModel annotation no longer imports that implementation
for Seed execution. No model weights, scoring equations or planner algorithms
changed. A fresh-process regression verifies that importing the Seed neural
runtime does not import Gymnasium,old training loops or legacy WorldModel.

The source-only AST audit reports a conservative73-module runtime closure and
260other retained modules. It includes conditional/type-only imports and flags
dynamic import sites. These counts do not prove unused code can be deleted.
Shared journal,canonical hashes,neural factory,expressions and controller modules
are reused by Seed despite their old directory names. Historical reproduction
code is retained rather than broken to shrink a folder list.

## One entry point and clear dependencies

`nexus` and `nexus-seed` now use the Seed CLI. `python -m nexus.seed` works from
source. Commands:serve,status,check,verify,audit-source. Default symbolic serving
and evidence inspection use stdlib only. Neural dependencies are optional
`.[seed]`; historical simulator/training dependencies are `.[research]`.
The old CLI remains as `nexus-research`,with its Python import path unchanged.
The former `nexus train` command becomes `nexus-research train`.

The CLI requires a source checkout with web/evidence assets; installed entry
points do not pretend to contain a standalone cloud application. Use
`--repository` when outside the checkout. No experiment is run by startup.

## Reversible branch retirement

Three ancestor tips were unoccupied by worktrees and backed up as exact-tip
GitHub tags before any branch deletion:

- codex/seed-hybrid-architecture → archive/seed/2026-10-20/seed-hybrid-architecture
- codex/seed-state-contract → archive/seed/2026-10-20/seed-state-contract
- codex/seed-action-ranking → archive/seed/2026-10-20/seed-action-ranking

All three local names were retired; only the latter two had GitHub branch
refs and those were retired with atomic exact-tip leases. Unique research and
active worktrees were not deleted. Latest Seed result branches stay published.
All other historical branches remain: they have not been declared disposable.
Exact hashes and checks are in
[the branch receipt](../artifacts/seed_branch_retirement.json).

Restore a retired branch explicitly,for example:

`git switch -c codex/seed-action-ranking archive/seed/2026-10-20/seed-action-ranking`

No main merge/default-branch change or Git garbage collection was performed.
The original checkout's two untracked adapter files were untouched.

## Next scientific gate

The useful action readout is ordinary supervised learning,not learning-to-learn.
Continue by testing its frozen decision quality on fresh spatial distributions.
A later separate learning-rule experiment must measure held-out1/2/4/8-example
adaptation against scaled replay,fixed protection,no adaptation and a strong
source-informed baseline,including forgetting and actual action outcomes.
No now-closed audit may select those rules. Cleanup itself spends zero new
scientific interactions,model inference or training; carried ledger remains
1905.6321034559958used /1694.3678965440042remaining seconds.

## Executed checks

223 relevant Seed/Lab/planning/expression/factory tests passed in11.73seconds.
The archive test matches all five original SHA256 values; the standing-authority
test compares the full original grant section verbatim. Fresh-process tests
exercise stdlib status without torch/numpy/Gym, and neural Seed import without
historical trainer/WorldModel imports. Public lazy exports retain class identity.
Repository verification checks31 active documents,123 links and the explicit
forward preservation overlay. Existing saved readout verification still passes;
no controller or model training was run. No additional security scope requested.

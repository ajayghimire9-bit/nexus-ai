# Seed-first repository organization

This is a documentation/developer-experience change from
`f1fdb2b3beb6f4fd3c1ed354792c1e4006905a75`, not a new scientific result.

## Current entry points

- [Root README](../README.md): project identity, quickstart and capability limits.
- [Documentation hub](README.md): active guides and evidence navigation.
- [Teaching walkthrough](seed/QUICKSTART.md) and [architecture](seed/ARCHITECTURE.md).
- [Charter](NEXUS_SEED_CHARTER.md), [roadmap](NEXUS_SEED_ROADMAP.md), and
  [results](NEXUS_SEED_RESULTS.md): scope and what was actually measured.
- [Contributing](../CONTRIBUTING.md) and [security boundaries](../SECURITY.md).
- [Historical index](history/README.md): previous research, kept accessible.

## Stable source and evidence paths

`src/nexus/seed/` owns finite concepts/programs/session records. The existing Lab
server and UI remain in `scripts/run_learning_lab.py` and `web/learning-lab/`.
No runtime engine, controller, learner, historical checkpoint or scientific
configuration changes are part of this cleanup.

All prior `artifacts/`, `configs/`, schemas, runtime source, scripts, tests and
historical documents stay in place. Their existing relative paths participate
in provenance. A preservation manifest in
[seed_repository_refresh.json](../artifacts/seed_repository_refresh.json) records
byte hashes; `python3 -I -S scripts/check_repository.py` verifies those files and
active documentation links. Historical verbatim snapshots are excluded from
modern link checking because their relative links were written for the root.

The old README is retained [verbatim](history/README_BEFORE_SEED_REFRESH.md).
The new README is not an erasure of prior negative findings. Agent instructions
and Cursor's vision/architecture rules gain concise Seed-current addenda while
preserving their existing safeguards and historical text.

## Quality workflow

Local `make check`, `make test-seed` and `make audit-seed` are optional shortcuts.
The inert template `docs/automation/seed-checks.yml.example` proposes a manual-only
workflow, five-minute timeout, read-only contents access, pinned action revisions
and only pytest as a dependency. It is **not installed** under .github/workflows
and cannot run. GitHub rejected the initial push for missing OAuth workflow scope;
no broader permission was requested. The unpublished initial draft is preserved
locally on codex/seed-refresh-local-workflow-draft. Local checks remain usable.
Existing scientific counters, grants and ledgers remain unchanged:
1845.6321034559958seconds used /1754.3678965440042remaining.

No license is selected, history deleted, repository visibility/default branch
changed, paid service installed, or branch merged. GitHub's existing `main` stays
unchanged; the refreshed front page appears on this feature branch until an
explicitly approved integration. A repository description/topic refresh may
describe this new direction without changing default-branch code.

## Limits of verification

Local acceptance: **228 tests passed in 11.64 seconds**, 73 local links in
12 active guides verified, and all 2,030 protected files matched. The old README
matches its original byte hash. See the
[acceptance record](../artifacts/seed_repository_refresh_validation.json).
GitHub's description/topics now identify Seed; default branch remains main.
No scientific run, model training/inference, cloud workflow or ledger debit.

The local checker validates file targets and byte hashes, not external website
availability or every Markdown anchor. Tests use source/authored fixtures only;
no old scientific suite is rerun. License choice, public deployment, packaging
as an independently installable Seed distribution and automated cloud CI policy
are separate decisions, not silently introduced by a professional README.

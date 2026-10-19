# Contributing to NEXUS

Seed is the current development direction. Start with the [quickstart](docs/seed/QUICKSTART.md),
[architecture](docs/seed/ARCHITECTURE.md), [current evidence](docs/NEXUS_SEED_RESULTS.md),
and [roadmap](docs/NEXUS_SEED_ROADMAP.md). Read [AGENTS.md](AGENTS.md), the
[master context](docs/MASTER_CONTEXT.md), reuse map and registry before research changes.

## Small, reviewable changes

1. Use a feature branch; keep unrelated work and historical artifacts intact.
2. Reuse the current Lab, journal and domain interfaces. Do not create another
   general memory, evolution or meta-controller framework.
3. Add focused tests. Distinguish supplied behavior from learned behavior.
4. Update the appropriate guide and report limitations. Keep claims tied to evidence.
5. Submit a pull request with exact commands and outcomes. Main merges require
   explicit maintainer approval; a green test is not scientific confirmation.

## Lightweight local verification

Seed runtime needs Python 3.11+ and a browser, no package installation.
For tests on macOS/Linux:

```sh
python3 -m venv .venv-seed
.venv-seed/bin/python -m pip install 'pytest>=8,<10'
python3 -I -S scripts/check_repository.py
.venv-seed/bin/python -m pytest tests/test_seed.py tests/test_repository_layout.py
python3 -I -S scripts/verify_seed_comparison.py --allow-partial
```

On Windows use the virtual environment's `Scripts/python.exe`. If pytest is
already available, use that interpreter; no need to download dependencies again.
Optional `make help` lists shortcuts. Do not run an unrestricted historical test
or benchmark command as a basic setup check: some older suites require local
weights, write scientific outputs, or run simulations.

An inert manual-workflow template is supplied at
`docs/automation/seed-checks.yml.example`. It is not installed or executable by
GitHub in this repository. GitHub refused the initial push because the current
OAuth credential lacks workflow scope; no broader permission was requested.
The template contains only these source/authored checks, no research execution.

## Research changes

Lock hypotheses, baselines, independent units, split boundaries, metrics and
resource limits before outcomes. Commit tested implementation/protocol before
evaluation; commit raw results separately. Never retune on confirmation results,
rewrite old captures, fabricate a positive outcome, or silently shrink a run.
The incomplete Seed comparison must remain incomplete. A new study needs its
own registered scope; this contribution guide grants no execution budget.

Preserve E2.17's consumed grant, H17's blocked status, F's unrun status and all
closed seeds. Keep historical paths stable. Local checkpoint audits must fail
clearly for missing binaries; ordinary repository checks must not require them.

## Privacy and security

Never commit session snapshots, personal teaching data, tokens, `.env` files or
private model binaries. Use ignored `runs/` for local sessions. Requests and
learned meanings must not create shell/file tools, alter permissions or authorize
research. See [security boundaries](SECURITY.md). No paid services, live trading,
unbounded loops or autonomous main merges.

No license file is supplied at the repository root. License selection remains
an owner decision; this cleanup does not introduce one.

# NEXUS Seed

**Teach. Remember. Act. Learn how to learn.**

A local research agent for learning finite concepts, using memory and making
decisions in a small authored world. Learning-to-learn is the goal, not a
capability we already claim. No external LLM or API key is required at runtime.

## Try it

Python3.11+ and a browser are enough for the symbolic teaching demo:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8766
```

Open http://127.0.0.1:8766/seed. Teach an invented word using positive/negative
examples, ask clarifying questions, execute a typed movement program, save the
session and correct a previous label. The local server stops after15minutes.

For the frozen neural model and tested action scorer:

```sh
python3 -m venv .venv-seed
. .venv-seed/bin/activate
python -m pip install -e ".[seed,dev]"
nexus serve --mode readout
```

Run from this checkout, or supply `nexus --repository /path/to/nexus-ai ...`.
Use **Learned one-step action**. Source assets and the tracked hash-bound JSON
checkpoints are required; this is not an asset-free wheel or cloud service.

## What the evidence says

The subsequent frozen spatial-transfer screen passed versus frozen ranking:
goals45.3% versus4.7% across four changed start/goal mixtures. Greedy remained
stronger; cross-diagonal goals trailed random. [Transfer results](docs/NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md).

The latest nonlinear action-readout development test improved goal completion
from frozen12.5% to64.6%. Known-grid greedy achieved100% and remains stronger.
The model uses supplied position/goal features; this is not pixels-only grounding.

The preceding learned-plasticity experiment lost to scaled replay. The
future-edit selector tied historical-best. Useful continual learning and
learning-to-learn are **not established**. Negative results stay visible.

[Latest results](docs/NEXUS_SEED_SURPRISE_READOUT_RESULTS.md) ·
[Learning failures](docs/NEXUS_SEED_LEARNING_VALIDATION_RESULTS.md) ·
[Current state](docs/NEXUS_CANONICAL_CURRENT_STATE.md)

## Understand and develop

- [Teaching walkthrough](docs/seed/QUICKSTART.md)
- [Architecture and shared dependencies](docs/seed/ARCHITECTURE.md)
- [Research and evidence index](docs/README.md)
- [Master context](docs/MASTER_CONTEXT.md) and [agent workflow](AGENTS.md)
- [Cleanup boundaries](docs/NEXUS_SEED_FOCUS_CLEANUP.md)
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md)

```sh
nexus status
nexus check
nexus verify
nexus audit-source
make test-seed
```

Help/status/data-only verification do not train or collect research data.
Neural mode needs the seed extras; historical research commands require
`pip install -e ".[research,dev]"` and remain accessible as `nexus-research`.
They are not the default next task. The old `nexus train` spelling is replaced
by `nexus-research train`; historical Python modules remain import-compatible.

## Research boundaries

The current world, finite grammar and supplied observations are a testbed, not
general intelligence. Frozen models stay frozen. Protocols are committed before
outcomes, assessment sets are not reused, and resource caps are enforced.
No paid services, real-money activity, main merge or unrestricted self-modifying
execution is enabled by this repository.

Historical research is indexed under [history](docs/history/README.md).
Original artifacts/configurations/source paths remain available for reproduction.
Redundant branch names can be retired only after exact-tip archival and
worktree/ancestry checks. Unique research and failed outcomes are not discarded.

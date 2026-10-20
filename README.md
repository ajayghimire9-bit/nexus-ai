# NEXUS Seed

**Teach. Remember. Act. Learn how to learn.**

A local research agent for learning finite concepts, using memory and making
decisions in a small authored world. Learning-to-learn is the goal, not a
capability we already claim. No external LLM or API key is required at runtime.

**Active research:** NEXUS Seed and measured learning-to-learn. The GitHub
`main` branch carries this work; earlier control and Evolution studies remain
preserved research. Future experiments use separate bounded research branches.

## Latest research result

[Frozen investigation transfer](docs/NEXUS_SEED_INVESTIGATION_TRANSFER_RESULTS.md)
completed and **failed its registered screen**. The learned question order used
3.375 questions versus fixed4.219/random4.563, but greedy/exhaustive used3.000.
This narrow authored result is not general learning-to-learn. Historical
results remain unchanged; no live-agent promotion.

## Try it

The new [executable foundation](docs/NEXUS_SEED_FOUNDATION.md) is available at
`/foundation` on the same server: six operator stages, bounded typed programs,
attributed document ingestion, conflict-preserving memory, checked program
abstractions and investigation tools. This is tested engineering, not a new
learning-to-learn result. Historical findings and frozen models are unchanged.

Python3.11+ and a browser are enough for the symbolic teaching demo:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8766
```

Open **http://127.0.0.1:8766/** for the new conversational workspace. Teach a word
or a checked skill, ask about memory, and explore the same authored world from
one conversation. It can also compose and execute small list programs: try
“Write code to sort and remove duplicates on [3, 1, 3, 2]”.
These are bounded supplied operators, not unrestricted coding. Open Evidence →
Latest investigation results to inspect the actual study. Start with “A dax means a red object” or “Teach you a skill
from examples.” [Conversation guide and screenshots](docs/NEXUS_SEED_CONVERSATION_WORKSPACE.md).

The original form-based interface remains at `/seed`. Teach an invented word using positive/negative
examples, ask clarifying questions, execute a typed movement program, save the
session and correct a previous label. The local server stops after15minutes.

The same server now has four [shared learning labs](docs/NEXUS_SHARED_LEARNING_LABS.md)
at `/labs`: language concepts, small typed programs, reasoning patterns/relations
and authored world goals. They share the existing Session and checked skill
library. This is a functional teaching playground; useful learning-to-learn and
neural cross-domain transfer remain unestablished. `nexus serve --mode labs`
loads the original hash-verified frozen encoder when its recorded core is present.

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

The same server provides a read-only experiment dashboard at `/experimental`,
including the saved 1/2/4/8-example learning curves and baseline comparisons.
Opening it does not train models or collect data. See the
[owner-controlled experimental workflow](docs/NEXUS_EXPERIMENTAL_MODE.md)
for bounded local development and explicit resource approvals.

## What the evidence says

The newest optional [executable-world-model study](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md)
passed its authored source history-feature screen. This is prediction on a supplied
grammar, with no control, transfer or live promotion. The prior utility studies
remain failed and closed.

The preceding ten-scalar **answer-free question-utility predictor failed** its
source screen. Primary next-update MSE at budgets1/2/4: .170313 learned versus
.173580 variance, .172771 uniform, .172599 original order and .173857 keep.
Gains are below5%, required intervals include zero, and6/12 tasks beat keep.
Retention passes. Budget8 is a singleton secondary result. No live promotion.
[Executable-model results](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md).

The preceding54-feature predictor also failed its source screen
([results](docs/NEXUS_SEED_QUESTION_UTILITY_RESULTS.md)). The larger independent
source query bank passed evaluator selection stability
([results](docs/NEXUS_SEED_QUERY_REPLICATION_RESULTS.md)); evaluator utility is
not learned question choice. Neither result establishes learning-to-learn.

An earlier evaluator-only audit found useful questions retrospectively: query
oracle MSE .174050 versus variance .193552. But selection using two query states
**failed on the third** (.194374 versus keep .194222). This is potential in
known source data, not a deployed question learner or learning-to-learn claim.
[Historical headroom results](docs/NEXUS_SEED_QUESTION_HEADROOM_RESULTS.md).

The previous fixed-learner question study **failed its source improvement screen**:
informative selection MSE .193552 versus random .191753; its interval includes
zero. Original-order constant damping remains .180187. No new collection or
live promotion. [Question-selection results](docs/NEXUS_SEED_QUESTION_SELECTION_RESULTS.md).

The previous learning-choice study **failed all improvement screens**: protected
learning error .210911 versus constant damping .180187. Observed-memory
protection passed, but asking mostly deferred learning. No live promotion.
[Learning-choice results](docs/NEXUS_SEED_LEARNING_CHOICE_RESULTS.md).

The earlier nonlinear-feature study also failed its development screen.
Average error after 1/2/4/8 new examples was .170873 for learned contextual
protection, .171423 for source-trained static protection and .128930 for scaled
replay. The small advantage over static was inconclusive; learned/static/fixed
protection produced identical tested control actions. No useful learning-to-learn
advantage was demonstrated. [Full results](docs/NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md).

The earlier frozen spatial-transfer screen passed versus frozen ranking:
goals45.3% versus4.7% across four changed start/goal mixtures. Greedy remained
stronger; cross-diagonal goals trailed random. [Transfer results](docs/NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md).

The earlier nonlinear action-readout development test improved goal completion
from frozen12.5% to64.6%. Known-grid greedy achieved100% and remains stronger.
The model uses supplied position/goal features; this is not pixels-only grounding.

The preceding learned-plasticity experiment lost to scaled replay. The
future-edit selector tied historical-best. Useful continual learning and
learning-to-learn are **not established**. Negative results stay visible.

[Executable-model results](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md) ·
[Action-readout results](docs/NEXUS_SEED_SURPRISE_READOUT_RESULTS.md) ·
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
outcomes for registered studies. Exploration iterations use lightweight manifests
and reusable development data; independent assessments and closed evaluations
remain protected. Resource caps are enforced, with backend limits documented.
No paid services, real-money activity, automatic main merge or unrestricted self-modifying
execution is enabled by this repository.

Historical research is indexed under [history](docs/history/README.md).
Original artifacts/configurations/source paths remain available for reproduction.
Redundant branch names can be retired only after exact-tip archival and
worktree/ancestry checks. Unique research and failed outcomes are not discarded.

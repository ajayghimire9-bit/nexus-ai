# NEXUS Learning Lab — reproducible local workflow

## Recorded replay: no third-party installation or model checkpoints needed

Use Python3.11 or later; verified locally with3.13.5. From this checkout:

```sh
python3 -m venv .venv-lab
.venv-lab/bin/python -I -S scripts/nexus_lab.py --port 8766 --max-runtime-s 900
```

Open http://127.0.0.1:8766 . The isolated standard-library-only path requires
no pip, Node, Torch, network download, paid service or untracked .pt file.
The launcher inserts only the checkout's src/scripts directories. For Windows
use the environment's Scripts/python.exe. Do not enable fixtures in this
minimal environment; they require the research dependencies. The server binds
loopback only and stops after at most900s. This is not public hosting.

Recorded JSON/config hashes are verified before display. Filter family/model,
scrub a recorded step, inspect revealed training feedback and compare the
recorded chosen return against parent. Failure labels remain visible. Opening
a recorded trajectory does not run MPC or collect another transition.

## Browser research notebooks

Save a title, notes, view filters and inspected step in browser-local storage.
Close/reopen the browser or reload the page and click Restore browser session.
Export/import JSON for portability. Restoring requires matching recorded
capture SHA256 references; stale or malformed notebooks fail visibly. Imports
accept only the declared schema, finite bounded indexes and≤32KiB. Notes render
as text, never HTML. Nothing in a notebook can authorize an experiment or
select a server-side filesystem path. Storage may be unavailable in private
mode; use JSON export instead. Do not store credentials in notes.

These notebooks are research review state, not learned network weights. No
fixture is automatically resumed by restoring a browser notebook.

## Durable learned fixture sessions (optional research environment)

This uses existing LearningCycle, TaskStream, StrategyGenerator, JSON checkpoint
codec and FixtureHost. Install the repository's research dependencies in a
separate environment using its existing pyproject recipe, or use the already
configured workspace (PYTHONPATH=src:.deps). This is NOT a promise of bitwise
reproducibility across arbitrary dependency versions. Checkpoint loading pins
catalogue/source hashes; saved learned state is not an execution authorization.

```sh
PYTHONPATH=src:.deps python3 scripts/run_learning_lab_session.py --new --directory .nexus-lab/persistent --seed 7 --method unified --blocks 2
# Exit the process. The next command is a genuine program restart.
PYTHONPATH=src:.deps python3 scripts/run_learning_lab_session.py --directory .nexus-lab/persistent --blocks 2
```

First invocation handles A→B, second A→C. Repeat in a DIFFERENT directory with
--method reset_memory for a functional control. Same seed/budgets and restored
host counters permit deterministic comparisons; their authored utilities are
not measured simulator returns or continual-learning evidence. The CLI charges
at most two task blocks/two attempts per block/invocation and preserves existing
choice/cost/evaluator allowances. It never creates a model/environment.

Each revision creates a new cycle checkpoint and hash-linked JSON manifest;
previous snapshots are not overwritten. The manifest carries task cursor,
evaluator calls/failures, charged costs, source provenance and checkpoint hash.
--expected-head adds an externally recorded chain anchor. Internal hashes detect
accidental damage, not malicious rewriting by someone who controls all files.
Resume rejects changed seed/method, altered/missing snapshots, truncated chain
against an external head, completed streams and concurrent writers. A crash
may leave .active or an orphan snapshot; inspect it instead of blindly retrying
or deleting records. Failed attempts are saved when the settled cycle permits
it. Local sessions/venv are ignored by Git and never committed as research data.

The browser's older opt-in --allow-fixtures playground remains separate and
bounded. It is not the durable CLI, and neither provides a live scientific
backend. No production deployment, user authentication or remote execution is
claimed. Real experiments still require committed protocols and exact budgets.

## Repeatable verification

```sh
PYTHONPATH=src:.deps python3 scripts/check_learning_lab_launch.py
NEXUS_PLAYWRIGHT_MODULE=/path/to/playwright node scripts/check_learning_lab_browser.cjs http://127.0.0.1:8766
```

Chrome/Playwright are optional QA tools, not runtime dependencies. The browser
check must include save/reload/restore and JSON notebook round trips in addition
to recorded-view filtering. No simulator or scientific model inference occurs.

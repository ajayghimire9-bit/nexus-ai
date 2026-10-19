# NEXUS Learning Lab 0.2.0 — local demonstration release

This release packages recorded B/D control evidence, E's training-only audit,
F's **unexecuted** preparation, browser notebooks and the existing optional
durable authored fixture sessions. It is a research demonstrator, not a live
scientific backend or a production hosting service. Failed results remain
visible. No network/model data collection occurs by opening a replay.

## Unpack and inspect without installing dependencies

Download/unpack `artifacts/nexus_learning_lab_demo_v0_2_0.zip` from this branch.
Use Python3.11 or newer. From the unpacked directory:

```sh
python3 -I -S scripts/verify_demo.py
python3 -I -S scripts/nexus_lab.py --port 8766 --max-runtime-s 900
```

Open http://127.0.0.1:8766 . The server is loopback-only, bounded and read-only
by default. No pip, Torch, NumPy, weights, cloud or payment is required for
recorded replay. `offline.html` also opens directly in a browser; fixture
requests are disabled there. Browser notebooks save filters/notes locally and
export/import hash-referenced JSON. The separate D query dropdown is not part
of the older v1 notebook's saved view schema.

Inspect what was observed, the frozen choice, and selected-minus-parent
return. D reports parent retained0/4 and a failed improvement screen; the E
section is training sensitivity, not query validation; F shows preparation
and prospective caps, never invented results. Recorded B/D data are closed
and must not be reused to retune selectors.

`DEMO_MANIFEST.json` lists every shipped file's byte hash, version and source
revision. Startup verifies it. This detects missing/changed files, not malicious
rewriting by someone controlling the entire package. No checkpoints, NPZ arrays,
credentials, untracked adapter work or experiment-execution scripts are bundled.

## Optional durable authored sessions

Create a separate Python environment and install `requirements-fixtures.txt`
if you want the existing fixture session CLI. This optional installation needs
ordinary third-party packages; it is not needed for replay, and no installation
or download is started automatically. The requirements use existing research
minimum versions, not a claim of bitwise equivalence on every future version.

```sh
PYTHONPATH=src python3 scripts/run_learning_lab_session.py --new --directory saved-session --seed 7 --method unified
PYTHONPATH=src python3 scripts/run_learning_lab_session.py --directory saved-session
```

Run these as separate processes: A→B, then restore→A→C. For a reset control use
a different folder and `--method reset_memory` on the first invocation. Keep
host counters, chain hashes and failure records. These are authored utilities,
not measured simulator returns, neural training or demonstrated continual
learning. The existing checkpoint codec rejects mismatched sources/settings.

## Rebuild and acceptance

From the research checkout with its already installed dependencies available:

```sh
PYTHONPATH=src:.deps python3 scripts/package_learning_lab.py --output /tmp/nexus-demo.zip
python3 scripts/check_learning_lab_release.py /tmp/nexus-demo.zip
python3 scripts/check_learning_lab_release.py /tmp/nexus-demo.zip --fixture-dependencies /absolute/path/to/research/.deps
```

The builder uses tracked Python source and an explicit evidence/asset allowlist;
it refuses to overwrite a release file. It does not install or publish anything.
Acceptance extracts to a temporary directory and creates a new venv with no
pip/site packages, starts the isolated stdlib replay, checks D/E and F boundaries
and terminates its owned server. Optional restart QA supplies only third-party
dependencies explicitly; that is **not** a clean dependency-install test.
Hashes and exact acceptance outcomes are recorded separately. Rebuilding from
the same file contents/revision produces a deterministic ZIP. A clean-machine
Python/browser/OS matrix and production deployment remain outside this release.

# NEXUS Seed S0–S1 — implementation and local use

## Optional grounded extension delivered

The newer eight-component prototype is implemented and trained in one bounded
authored pilot. Start with [grounded quickstart](seed/GROUNDED_QUICKSTART.md) and
[honest grounded results](NEXUS_SEED_GROUNDED_RESULTS.md). It requires PyTorch and
NumPy; the original stdlib-only mode described below remains unchanged. Trained
planning/language/concept quality is mixed or negative, not general intelligence.

New direction from verified fbee981, separate branch/worktree. Historical research
is preserved, including the negative five-family PPO screen. See charter, roadmap
and locked protocol. Results are recorded separately after the authored comparison.

Delivery:220relevant tests pass; real Chrome GUI/restart checks pass. The one
authored development comparison is **incomplete** at its fixed predicate-test
cap. Teaching functionality works; comparative sample efficiency is unestablished.
See [honest results](NEXUS_SEED_RESULTS.md). Do not rerun the captured comparison.

## Start locally (no installation or download)

Python3.11+ and a browser:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8766 --max-runtime-s 900
```

Open http://127.0.0.1:8766/seed . The existing historical Lab remains at `/`.
Default server stays replay-only unless --allow-seed is explicitly supplied.
Server automatically ends after at most900seconds; restart to continue. No model
weights, Torch, NumPy, Gym, Internet connection or GPU are needed for Seed.
Private evidence is saved under ignored `runs/seed-sessions`, never in artifacts.

Try an invented word: `move dax left`. Seed asks for teaching; the word has no
preinstalled meaning. Type it into the teaching field, select an object, and
label YES/NO. For a reproducible teaching example, intend **blue and small**:
in scene0 label o4 YES. Answer the actual question cards according to that rule.
Then switch to scene1 and try `move dax left then move o1 down`. This demo rule
is an instruction to the human, not target metadata given to the learner.
An ambiguous reference needs more labels or an object ID; empty version spaces
need corrected evidence. Primitive moves cannot leave the6×6grid.

Save, stop/restart Python, then **Resume saved** in the same browser. The browser
stores only saved ID/head; the server restores the typed JSON evidence and
replays actual programs. Keep the same CLI snapshot directory across restarts.
Corrections append an opposite label superseding a selected current record;
the original record remains visible. Save again creates a new immutable revision.
New session resets the active workspace without deleting earlier snapshots.
Export downloads typed JSON; arbitrary imported execution is not supported.

The `define` request/panel explicitly assigns one supplied grammar predicate.
That shortcut is labeled a definition, not induced learning. The normal teaching
path filters37candidate meanings from boolean evidence. Question cards can be
generated outside the displayed scene, within the declared18object property grid.

## Named reuse and scope

- `scripts/run_learning_lab.py`, `web/learning-lab`: same loopback server, Host,
  Origin, header and body checks; separate live Seed route, old replay untouched.
- `evolution1.fixtures.Journal`, `verify_journal`, `catalogue.canonical/digest`:
  same immutable evidence chain and canonical JSON. Journal's legacy hash domain
  says synthetic_fixture; Seed events additionally use seed-prefixed kinds.
- `evolution2.cycle_checkpoint` and `run_learning_lab_session`: reuse the
  append-only revision/expected-head/typed-reconstruction design, not incompatible
  catalogue/RNG class schemas. Seed records are domain-specific, not generic memory.
- `evolution1.resources` physical neural/environment counters are deliberately
  **not** charged for symbolic labels/predicate work. Seed's domain cost counters
  reserve work before execution; no invented scientific interactions. Existing
  strategy-memory and meta-controller stacks are not replaced or duplicated.

Limits: no general conversation, perception, physical inference, arbitrary new
skills, neural learning, continual/general learning or scientific self-improvement
claim. English parsing, object schemas and movement are supplied by code.
Hash chains are corruption checks, not a malicious-local-owner security boundary.
Cancellation is cooperative, not process isolation. User files and logs may
contain private teaching data; do not commit them. Energy is unmeasured.

## Verification

Focused core/HTTP/process-restart tests: `PYTHONPATH=src python3 -m pytest tests/test_seed.py`.
Existing Lab/session/fixture regression suites also apply. Browser QA uses real
headless Chrome through Playwright (`scripts/check_seed_browser.cjs`), optional
developer tooling only; ordinary use needs none of these packages.
One precommitted authored comparison: `python3 -I -S scripts/run_seed_comparison.py`;
it requires a clean tree and exclusive claim and must not be rerun after capture.
Independent arithmetic: `python3 -I -S scripts/verify_seed_comparison.py`.
The default verifier refuses this incomplete capture; use **--allow-partial**
to audit only its retained prefix without promoting completeness.

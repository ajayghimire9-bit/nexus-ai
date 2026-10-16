# Successor batching on archived observations and actual contexts

## Decision

The registered engineering grid passed: **2160/2160 first actions**, **2160/2160
full Q rankings**, and all2160 numerical comparisons matched the original
Pendulum successor scorer within the locked tolerance. Label:
`archived_decision_parity_established_on_tested_inputs`.

This includes **eight registered near-tie cases**, with minimum top-two reference
gap **0.0000489086**. Maximum absolute Q difference was **0.0000810850**, below
the2e-4 absolute tolerance even without the relative allowance2e-5. No tolerance,
action rule, candidate count, horizon, precision, network, context inference rule
or historical controller was changed after scoring. No mismatches were excluded.

This strengthens finite-input numerical parity evidence. It is **not universal
bitwise equivalence**, a new control-return result, cross-family weight transfer,
learning-to-learn or AGI. The optimized scorer remains opt-in.

## Exact archived coverage

Ten existing independent Pendulum decoders, three known development tasks, both
student-visited and zero-visited streams, phases0,16,50,100,150,199, and six scoring
contexts (all five saved epoch200 student codes plus zero) give2160 comparisons.
All50 actual saved student encoders were loaded without updates; their archived
task vectors were installed unchanged. Encoder inference and support collection
were not rerun.

The planned360 decoder/task/visitor/phase state slots include coincident visitor
observations. There are **322 distinct decoder/task/observation triples**. Each
observation is scored under six contexts; these cases are not new independently
trained models or statistical replications. No return confidence interval is
appropriate for this implementation check.

The archived observations came from the **older H=16 controllers**, not saved
successful-lookahead episodes. They cover early and late states actually reached
by those controllers, including large trajectory divergence, but do not establish
parity on every state the lookahead policy may visit. Acrobot and MountainCar logs
lack the needed matching observation streams. No simulator was used to reconstruct
them, and their prior synthetic parity evidence is not relabeled as archived parity.

Every candidate set was reconstructed from the original phase-specific candidate
seed. Both implementations scored the same16 H16 sequences. No old episode was
resimulated, no reward/query outcome selected the states, and no control-return
comparison was repeated. The verification checks each saved observation and seed
against its exact source-log location.

## Frozen-model and context integrity

All **60 requested checkpoint files** (10 decoders and50 broad students) matched
their recorded hashes before loading and after the audit. Missing/wrong files
would have failed, rather than being skipped or retrained. On all180 decoder/task/
context installations, the loaded encoder, decoder, normalization and z matched
the full frozen fingerprints from the original scoring archive. Before/after
fingerprints also matched in every one of the2160 scored cells.

The prior, already completed latent-generalization confirmation artifact was
read **only for its checkpoint metadata**, necessary for the original15 student
files. Its prediction/query outcomes did not enter state selection, scoring,
metrics or thresholds. No unused reserved split was evaluated or opened by the
audit. This is provenance reuse, not a new confirmation analysis.

Source observations and seeds came from
`artifacts/late_episode_decision_trajectory.json`; context vectors/fingerprints
came from `artifacts/source_scalar_calibration.json`. Both remain byte-identical.
All parent hashes and code/configuration hashes are recorded with the result.

## Sensitivity and computational accounting

Each decoder matched all216 cases; each task matched all720; each visitor group
matched all1080. Every phase and context matched all360 cases. Full ranking and
top-action agreement hold on all these subgroups.

Near ties: task0 four, task1 one, task2 three; student-visited five, zero-visited
three. Phase50 contained four, phase100 two, phase150 one and phase199 one. All
eight were in actual student scoring contexts; none in zero context. These are
descriptive counts, not evidence that student inference creates harmful decisions.
The near-tie threshold is a sensitivity flag, not a certified global error bound.

One audit completed in **13.442567917seconds**, inside its60-second cap:

- **Zero** real environment interactions, optimizer updates or new support rows.
- **3,330,720 imagined/model transitions**:2160 pairs×1542; no warmup/timing pass.
- **146,880 model calls**, with measured per-pair counts51 reference and17 batched.
- Each arm still predicts771 imagined states per decision. This task did not
  remeasure speed: the earlier2.53–2.61× synthetic CPU microtimings remain separate.

The cap covered input loading/validation, checkpoint loading, model scoring,
periodic saves and final validation. Unit tests and the independent arithmetic
check are reported separately. Peak memory was not measured; the new raw JSON is
about2.01MB. The original local binaries remain outside Git. This engineering
audit did not spend/reset an expired scientific environment-execution allocation.

## Tests and independent verification

Before execution, **61 focused tests passed in1.63seconds**, covering batching,
fixed-grid omission/duplication, nonfinite metrics, whole-dimension loss, checkpoint
hash failures, context identity, outcome-independent observation selection,
per-call time/state limits, and underlying entry-point overwrite/configuration guards.

After execution, the relevant repository-only suite passed **93 tests**, with
**4 deselected**, in4.21seconds. Two deselections are environment-stepping tests
explicitly excluded by `not dense_height`; two are separately marked local-binary
tests. Those local tests were explicitly requested against the original binary
location and **2 passed in0.53seconds**. There were no failing tests or execution
retries in this cycle. The full repository suite was not run because it contains
training/environment collection outside this engineering task.

`scripts/verify_successor_archived_parity.py` independently recomputes Q argmaxes,
rankings, numerical differences, near-tie flags, subgroup summaries and counter
totals using plain arithmetic. It also checks every observation/seed against the
original archive and all recorded provenance/checkpoint metadata. It made zero
neural or environment calls and agreed with the audit. Git-only regression tests
reject corrupted observations, seeds, Q values, subgroup summaries, missing whole
decoders and altered checkpoint lists. This is an independent arithmetic check,
not external scientific replication.

## Provenance

Branch **codex/successor-search-archived-parity**. GitHub-matched base
**f6230c5f87148986a42f612ff905353d1aa244f6**. Implementation/protocol and clean
execution revision **1ebb782b58a606e92c287d6c6bb174568e577021**, committed before
archived-state predictions. Results are committed separately.

- Raw `artifacts/successor_archived_parity.json` SHA256
  `4a0afd518d632b78451324dfbed89cfa2b17e644b60ef9aa0511b40d34454707`.
- Config SHA256
  `47803e17bd4bc15cdff3a37da121a134d225924f3f9f7f2dff3c861eb0380897`.
- Protocol SHA256
  `1e1412354c1a96591e023cb3f49174e53a2d07985d9ed5bef9a459fffa1ec7f4`.

The original checkout's MountainCarContinuous preparation is untouched; this
branch uses the separate worktree. Main, all historical artifacts, trained weights,
closed seeds and default controllers are unchanged.

```sh
# Executed once after the clean protocol commit; refuses a repeated/overwriting run:
PYTHONPATH=src:.deps python3 scripts/audit_successor_archived_parity.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai
# Offline arithmetic only, safely repeatable without checkpoint binaries:
PYTHONPATH=src:.deps python3 scripts/verify_successor_archived_parity.py
PYTHONPATH=src:.deps python3 -m pytest tests/test_successor_archived_parity.py \
  tests/test_successor_archived_recorded.py tests/test_successor_search.py \
  tests/test_successor_search_audit.py tests/test_successor_search_recorded.py \
  tests/test_bellman_backup_control.py tests/test_acrobot_lookahead.py \
  tests/test_mountaincar_lookahead.py tests/test_tree_reuse_lookahead.py \
  tests/test_prefix_max_tree_reuse.py -k 'not dense_height' -p no:cacheprovider
```

## One next recommendation

Validate **full-episode serial-versus-batched parity**, with paired fresh seeds
and unchanged frozen controllers, before changing a default runner. Archived
parity does not cover closed-loop divergence after an unseen near tie. The bounded
proposal is `NEXUS_SUCCESSOR_EPISODE_PARITY_PROPOSAL.md`; no episodes were run or
new scientific budget assumed here.

# Candidate identifiability: distinct programs, trivial separating probes

**Decision: prepare a different practical task family before a learning study.**
All seven distinct request cases contain meaningfully different programs, not
equivalents under the justified normal forms. Every pair is distinguished by
the first constructed input: a single row with all numeric fields zero. Median
probe construction was **20.5 microseconds**, with **two program executions**.
No new teacher answer was requested and no final assessment was rescored.

This supports a missing-boundary-probe diagnosis on the saved development cases.
It does not establish useful learned clarification, a latency improvement in the
live assistant, or learning-to-learn. The previous failed headroom and capsule
screens remain closed and unchanged.

## Provenance

Branch: `codex/seed-candidate-identifiability-audit`.
Starting local/GitHub revision: `a323805c1ec48e38442acb97718d0bd0db015f12`.
Tested protocol and implementation committed/pushed before analysis at
**`3a24ad55f70a12e6c35212e8a789a93233efa14e`**.
[Protocol](NEXUS_SEED_CANDIDATE_IDENTIFIABILITY_PROTOCOL.md),
[configuration](../configs/seed_candidate_identifiability.json),
[raw candidates and witnesses](../artifacts/seed_candidate_identifiability_raw.jsonl),
[result](../artifacts/seed_candidate_identifiability.json),
[independent audit/ledger](../artifacts/seed_candidate_identifiability_audit.json).

Config SHA256 `11833c1ae33a4d8e2f953710150450166d3c62639f7b7cafdcf54def55b19a9a`;
protocol `db0c5fdb0d57e0ef99334d5ac354181209e3ace3e42fce656b28ed8264f6e9c6`;
raw `ca456767a0fb729d77dd84d50adde1f15cc139cf7ac764df0bd3afecaa2979a1`.
All three pinned prior raw/config/result hashes passed. Persistent runtime
source remains `967842923d5e43c64732094f8e829d9b6995f07e80dce60ca1ce4c76ca0b3fda`.
No model server, inference, checkpoint load, weight replacement or main merge.

## What was recovered, without opening final outcomes

The exact nine unresolved records were reconstructed from demonstrations and
responses to already-selected probes. Seven are distinct original requests;
`renamed_2` and `repeat_2` are correlated controls of `task_02`, not additional
statistical replications. The evaluator bridge recovered eight old response
bodies from saved programs because the historical format omitted those bodies.
Only recorded asked inputs were evaluated for those reconstructions.

Final assessment rows and outcomes do not enter reconstruction or construction.
The constructor sees only the surviving programs, schema, threshold and public
domain. New input candidates are tested against program predictions, not a
teacher. No actual answer to the new probe was obtained. No claim of improved
observed accuracy or fewer actual user questions follows from partitioning.

## Findings by distinct request

Every pair below differs in threshold behavior; none is mathematically
equivalent. A zero-valued group survives without a threshold, whereas filtering
at 10 removes it. All countersamples lie in the declared 0..15 input domain.

- `task_02`: multiplication + mean, no filter versus post-aggregation filter.
- `task_04`: multiplication + maximum, no filter versus pre-aggregation filter.
- `task_07`: multiplication + sum, no filter versus post-aggregation filter.
- `task_11`: multiplication + mean, no filter versus post-aggregation filter.
- `task_12`: addition + maximum, no filter versus pre-aggregation filter.
- `task_14`: addition + sum, no filter versus post-aggregation filter.
- `task_15`: multiplication + maximum, no filter versus pre-aggregation filter.

The two task_02 controls show the same separation. Thus the descriptive primary
counts are **0 equivalent /7 meaningfully different /0 unknown**; all nine raw
records are complete. Expected worst-case remaining candidates drop from **2
to 1** with one truthful response per case, conditional on this candidate set.
This is a guaranteed hypothetical discrimination result, not an answered trial.

The old random 12-row probes made grouped sums, means or maxima large enough
that thresholding and not thresholding could agree. That agreement on finite
inputs was not equivalence. A legal singleton low-value boundary input exposes
the difference. More architecture or learned search is unnecessary for that
specific distinction.

## Measured costs and decision

New construction across the nine records: **18 program-prediction executions**
(14 on the seven primary requests), first input sufficient in every case.
Construction range **16.75–37.67 microseconds**; primary median **20.5
microseconds**. Total construction **0.196207 ms**. Candidate reconstruction
required **1,781 program executions**, plus the eight old-answer reconstructions;
total reconstruction time **13.002 ms**. Reconstruction is audit overhead, not
an omitted cost or a requirement for a live solver that already holds candidates.

Median recorded baseline discovery plus added probe-construction time is
**8.426208 ms**, below the existing 10 ms practical floor. This combines saved
and new timings; **it is not a fresh end-to-end timing measurement**. Microsecond
timings from one process are descriptive and have no replication interval.
Actual human-answer time and real-model inference costs remain unmeasured.

The registered decision is `PREPARE_DIFFERENT_PRACTICAL_TASK_FAMILY`.
We implemented a deterministic boundary-probe helper and tested its behavior;
it is not promoted into the live agent or used to change old benchmark scores.
No additional canonicalization is justified by these seven cases. A learned
abstraction comparison remains gated off.

## Tests and independent checks

**101 targeted tests passed before analysis (15.53 s). 107 passed afterward
(15.76 s)**, including saved-evidence corruption rejection. Commands:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_candidate_identifiability.py tests/test_seed_discovery_headroom.py \
  tests/test_seed_assistant_benchmark_v2.py tests/test_seed_experimental.py \
  tests/test_learning_lab_sessions.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 scripts/run_seed_discovery_headroom.py \
  --study identifiability
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 scripts/verify_seed_candidate_identifiability.py
```

Independent arithmetic reconstructed each candidate set and checked every new
witness without calling the AST executor or new constructor. It checked complete
IDs, primary units, partitions, count/timing arithmetic, input hashes and result
summary. Tests reject missing cases, false equivalence claims, forged predictions,
assessment access, changed summaries and booleans in numeric count fields.
Other tests cover no-search equivalence certificates, true multi-row distinctions,
bounded-search unknowns, answer-free choices and hidden-outcome independence.
Published attempts now refuse reruns even without the private ledger. This is
a targeted suite, not the entire historical repository suite.

One run: **0.123769 s wall**, **0.095871 s worker CPU**, **40.125 MiB** sampled
summed host/worker RSS. The 100 ms sampler can miss peaks; RSS can double-count
shared pages. Caps were 30 s CPU/wall and 1024 MiB sampled RSS. Conservative
debit **2 s**; E1 events 99–101 anchor to the prior published ledger head.
Latest accounted ledger: **2190.632103455996 s used /1409.367896544004 s remaining**.
The inherited v1 missing-debit gap is unchanged. Zero new answers, simulator
steps, imagined transitions, model inference or training.

## One next recommendation

Prepare the [baseline-first local repository-maintenance workload](NEXUS_SEED_PRACTICAL_DISCOVERY_NEXT.md).
First establish correctness and genuine discovery cost with strong direct,
static-analysis and ordinary-cache tools plus the unchanged persistent runtime.
Do not force search or begin retained-abstraction learning before that gate.
The proposal is written; no new practical-task experiment ran in this branch.

# NEXUS — Approved long-continuation execution

## Locked authorization and implementation

The user approved the prepared experiment with “yes.. do it” after its scope and cost were stated. The approval is recorded in `configs/long_continuation_approval.json`. Starting execution branch: `codex/long-continuation-execution`, based on `f12a5353e229c6acbac20e5213ed96a49a4b3405`. The numerical protocol remains unchanged at SHA256 `764afda08f1f614bc4e0151bf8ca203fd78caa043d6443a85467692599198918`.

The configuration's `awaiting_budget_approval` field is preserved as historical registration metadata; this separate approval record authorizes one local run. There is no training, paid service, architecture change, new physics or merge authorization. All prior artifacts and seeds remain closed.

The final collection driver uses the registered 64-step trace primitive, H=16/16 candidates, ten frozen decoders and five student seeds. It preserves original episode clocks at late states 50 and 100, harvests only 101 steps (explicit diagnostic cuts), and scores candidate sets before observing counterfactual returns. At zero-visited states zero-context continuations are executed once and reused for paired comparisons; cached reuse is not charged as a new interaction.

Both 64-step continuation types record each reward, action, planner seed, selected candidate index, predicted selected score and original episode step. Complete raw traces and all hashes are saved. Reward timing is checked against the published Pendulum reward on every real step. Original simulator states are used only for research restoration, never as model inputs. Context vectors and every encoder/decoder/FiLM/head/normalization hash must remain unchanged.

A complete result requires all 480 registered states, 800 paired metric cells, 240 harvest episodes and 40 task/decoder frozen checks, plus exact budget accounting and checkpoint verification. The driver rejects raw/summarized reward disagreement, incorrect candidates/actions, missing traces, reused/randomness drift, invalid numeric cells and cap violations. Timeout saves partial work and cannot yield a scientific label. The single primary label follows the registered full-policy tail rule; secondary results cannot change it.

An offline audit was implemented before evaluation. It independently recomputes the primary difference by summing raw per-step reward differences, without calling the collection runner's aggregation function. This is a separate arithmetic implementation, not external independent scientific replication.

Budget: **198,832 environment interactions**, **50,851,840 imagined model states**, **1800-second hard cap**. Integration tests and the regression suite are correctness checks outside the scientific sample and are reported separately. The run refuses to overwrite an existing result and has no automatic retry. Implementation and protocol are committed before any diagnostic outcomes are collected.

The approved primary comparison is full-policy student-minus-zero reward in local steps 16–63. Average students within visitor group, give both groups equal weight, then equally average phases and tasks inside each decoder. Use ten decoder means, Student-t 95% interval with df=9. Require mean <= −5 and upper bound < 0 for `long_policy_tail_worse`. The common-zero tail is secondary and unadjusted. No claim about general control improvement, learning-to-learn, AGI, or a unique cause of the earlier 184-step loss follows.

## Checks completed before scientific collection

Focused integration/preparation suite: **43 passed** in 3.15 s. Full regression suite: **440 passed, one local-checkpoint test deselected**, in 82.46 s. Explicit checkpoint test: **one passed, three deselected**, in 0.45 s. Standalone checkpoint audit verified **120 files**, zero missing and zero mismatched. Initial integration tests had two wrapper-access failures; these were corrected before scientific collection. No scientific run had started.

Commands:

```sh
PYTHONPATH=src:.deps python3 scripts/verify_checkpoint_integrity.py
PYTHONPATH=src:.deps python3 -m pytest tests/test_long_continuation.py tests/test_long_continuation_execution.py tests/test_late_control_gap_design.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest tests/test_checkpoint_integrity.py -m checkpoint_integrity -p no:cacheprovider
```

Approved run command, after this implementation is committed:

```sh
PYTHONPATH=src:.deps python3 scripts/run_long_continuation.py --approved-config-sha256 764afda08f1f614bc4e0151bf8ca203fd78caa043d6443a85467692599198918
```

## Completed locked experiment


All **480 states, 800 paired metric cells, 240 harvest episodes and 40 frozen task/decoder checks** completed in **781.77 seconds**. Implementation SHA: `dcbedf110f213132321459c84fb446003b1e7799`. The run was executed once and completed within the approved cap.

Primary full-policy tail, local steps 16–63: **-8.661 [-14.513, -2.809]**. Locked label: **`long_policy_tail_worse`**. The mean crosses the five-point practical screen and the 95% interval is entirely below zero. The interval is not entirely below −5, so the data do not establish that the loss is at least five points at that confidence level.

Full-policy prefix 0–15: **+0.066 [-0.094, +0.225]**. Full 0–63 sum: **-8.595 [-14.506, -2.685]**. Prefix plus tail equals total in every paired record. Nine of ten decoder tail means are negative; decoder 2 is positive.

Secondary shared-zero tail: **+0.627 [-1.448, +2.701]**, inconclusive. Its prefix is **-0.110 [-0.228, +0.008]** and total **+0.517 [-1.501, +2.534]**. This does not prove an absence of delayed first-action effects. It does not upgrade or overturn the primary outcome.


### Task and state-distribution sensitivity


- pendulum_ctrl_rp0 (g, m, length = [3.6, 0.42, 1.35]): **-0.392 [-0.836, +0.052]**.

- pendulum_ctrl_rp1 (g, m, length = [18.5, 1.85, 0.62]): **+1.924 [-0.950, +4.798]**.

- pendulum_ctrl_rp2 (g, m, length = [9.1, 3.1, 1.05]): **-33.945 [-57.296, -10.593]**.

- pendulum_ctrl_rp3 (g, m, length = [13.7, 0.22, 1.95]): **-2.231 [-6.547, +2.084]**.


The primary loss is concentrated in rp2. Removing rp2 gives **-0.233 [-1.594, +1.128]**, which includes zero. This is a predeclared sensitivity result, not permission to exclude or reweight rp2. The other task intervals include zero; this sample does not demonstrate uniform harm across physics.

- student-visited: -9.978 [-15.199, -4.757].

- zero-visited: -7.344 [-14.709, +0.020].

- Original phase 50: -9.308 [-13.981, -4.635].

- Original phase 100: -8.014 [-15.574, -0.454].


Per-decoder primary tail differences: 0: -2.322326, 1: -24.277721, 2: +2.282988, 3: -18.269633, 4: -9.862670, 5: -12.090976, 6: -1.221997, 7: -10.723333, 8: -7.011697, 9: -3.112744.


### Interpretation


The frozen student has a measured negative tail difference in the registered longer full-policy continuation, while the short prefix and the common-zero tail remain unseparated. The result supports investigating the combination of continued context-conditioned decisions and the state paths those decisions create, particularly on rp2. It does not uniquely distinguish poor later action choices from inherited state differences, and it does not causally explain the previous 184-step episode gap. The two continuation types use separate registered randomness, so subtracting their means is not a causal decomposition.

This is a development mechanism diagnostic on four already evaluated Pendulum physics, with one registered reset per task, not fresh physics confirmation. Episodes, overlapping windows and five student seeds do not increase the ten-decoder replication count. Student-t intervals describe model-seed uncertainty conditional on this finite physics/state sample. Secondary and sensitivity intervals are exploratory and unadjusted. Prediction improvement, control generalization and learning-to-learn remain distinct claims; the present result establishes neither general control improvement nor learning-to-learn.


### Integrity, costs and provenance


The exact expected metric/raw-state grids passed before classification. All saved continuation windows were rebuilt from their actual reward traces and matched the paired cells. All captured live decisions reproduced and all restored observations matched exactly. All six model/context entries passed each of the 40 frozen checks. Both checkpoint audits verified all **120 files** with no missing or mismatched files. All original checkpoints, global vectors, manifest and prior result artifacts were preserved.

The separately implemented offline audit reproduced the primary interval by summing raw per-step reward differences across all 800 pairs. An additional offline RNG integrity check regenerated candidate streams and matched **172,640 of 172,640 recorded replanning actions**. Neither audit generated environment experience. These are arithmetic/integrity audits, not external independent scientific replication.

Actual cost: **198,832 environment steps** and **50,851,840 imagined model states**, exactly the registered budget. Environment buckets: support 512; harvest 24,240; common continuation 92,160; full-policy continuation 81,920. Model buckets: harvest 6,205,440; live replay 122,880; shared scoring 327,680; common continuation 23,224,320; full-policy continuation 20,971,520. No new network training occurred. The 25,600 history rows processed while installing 200 student contexts are additional encoder inference, not imagined dynamics transitions. Prior checkpoint-training costs are inherited and not included in this diagnostic interaction count.

Saved raw JSON: 29,013,642 bytes. Artifact SHA256: `15e2c4ce461287f2df5686e7b346aafe5ecbe9f4aa7fd237d9e5cf94920af92a`. Configuration SHA256: `764afda08f1f614bc4e0151bf8ca203fd78caa043d6443a85467692599198918`. Protocol SHA256: `62710f939ae6d2d2b555f9e691f08e0d76c1932c21ab2244667df45c538f8075`. Approval SHA256: `bf627148360bd88c466525ac1ba5fa05bcb7a2280f02509668ec86845f4b6228`. Manifest SHA256: `265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b`. Parent artifact SHA256: `b3a0642e46890f0d6296d103ecd5ed1353cc6f2849b6dd61e46507f5f8dd5ea9`. The frozen protocol bytes can be recovered from the execution commit. Binaries remain outside tracked Git with their original recorded paths/hashes.

Dependencies: python=3.13.5 (main, Jun 11 2025, 15:36:57) [Clang 17.0.0 (clang-1700.0.13.3)], torch=2.14.1, numpy=2.5.4, gymnasium=1.4.0.


Post-run audit commands:

```sh
PYTHONPATH=src:.deps python3 scripts/audit_long_continuation.py
PYTHONPATH=src:.deps python3 scripts/verify_checkpoint_integrity.py
```

The separate RNG check used only saved decision seeds, selected indices and actions, regenerating `default_rng(seed).integers(0,3,size=(16,16))`; all first actions matched. No MPC was rerun.


### Documentation review requested during execution


AGENTS.md and docs/MASTER_CONTEXT.md were re-read in full. Both preserve the broad adaptive-intelligence/AGI research aspiration and explicit limits on demonstrated capability, but compactness and Pendulum-as-testbed should be more explicit. The V0.1 immediate-milestone label and blanket context-confirmation statement need historical qualification. **Neither file was changed.** Proposed wording and status corrections are in `docs/NEXUS_DOCUMENTATION_REVIEW.md`, pending user approval. Other historical status documents were also left unchanged in this results commit.


### One next scientific question (not executed)


On rp2, does the 64-step deficit persist when the student-controlled 16-step prefix is followed by zero-context control, or is continuing student control after that prefix necessary? A separately registered prefix/suffix policy-switch experiment could compare all four 16-step-prefix × 48-step-suffix combinations from fresh identical late states. The primary comparison would be full student versus student-prefix/zero-suffix over the tail; inherited-prefix effects would be secondary. This tests a narrower mechanism without changing trained weights or planner settings. It would still not uniquely explain the original 184-step loss.

A conservative proposal using ten decoders, five students, rp2 only, phases 50/100 and a fresh paired reset needs 52,268 environment steps and 13,378,560 imagined model states when identical zero baselines are cached. Scaling from the completed run suggests about 3.5 minutes, with a proposed ten-minute cap. These are estimates for a future protocol, not approved execution. No additional experiment has started.

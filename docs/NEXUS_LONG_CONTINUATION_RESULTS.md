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

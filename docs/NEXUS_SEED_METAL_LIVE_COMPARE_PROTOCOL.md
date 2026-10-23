# Metal independent-vs-revision comparison — protocol

Base: current `cursor/seed-lexicon-knowledge-vault`. Development smoke
only. Do not edit `local_model_runtime.py`. Do not debit the frozen CPU
ledger **3564.568 s**. Do not retune stepwise. Ranking stays paused.

The stubbed revision win at call 2 versus independent call 4 proves
control flow only. It is **not** a live advantage.

Commit this protocol and the tested runner **before** the live
artifact.

## Frozen comparison

One live batch, two fresh tasks, two arms, equal caps:

- `k = 4` generation calls maximum per arm
- `max_tokens = 128` per call
- Same 1.5B coder, ChatML, `json_body`, seed schedule
  `(0.0/42, 0.35/43, 0.35/44, 0.35/45)`, `n_gpu_layers = -1`
- Code: new `label(item)` over `hall` / `gate` (disjoint from the
  closed yard/slip smoke). Feedback may name undefined identifiers and
  public keys. No planted `.get` or finished body.
- Sentence: new `dockbinding` fact `seed-compare-1`. Revision may
  repeat verifier reasons, not a canned sentence.

Record for each arm: calls used, unique raw outputs, posted
temperature/seed hashes when live, public success, and independently
replayed success (sandbox / `verify_composed_response` / private 3/3).

## Cost

Grant accounting stays `MetalGrantEnforcer.guarded_call` wall only,
RSS sampled before/after each arm, process RSS ≠ Metal heap.

Also report the complete assistant cost that a user waits through:

startup + inference + retrieval + execution + verification + teardown

`user_total_s` is that runner wall. Do not treat grant seconds as the
only efficiency number.

## Verifier

Replay saved candidates. Reject a claimed live advantage flag, a CPU
ledger change, planted `.get`, or call counts above 4.

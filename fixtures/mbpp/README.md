# MBPP (vendored)

Mostly Basic Python Problems, Austin et al., "Program Synthesis with Large Language Models" (2021).
Source: https://github.com/google-research/google-research/tree/master/mbpp (`mbpp.jsonl`, 974 tasks).
The dataset is released under CC-BY-4.0 (see the upstream README). Human-written task descriptions,
reference solutions and test assertions are unchanged. NEXUS never shows the reference `code` to a
solver; it is not used anywhere in the v3 suite.

`split.json`: deterministic dev / eval split by sha256("mbpp-split:<task_id>") parity, fixed before
any solver was run on MBPP.

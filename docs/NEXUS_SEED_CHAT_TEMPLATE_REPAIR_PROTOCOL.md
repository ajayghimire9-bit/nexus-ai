# Chat template, equality-failure revision, and fresh functions — protocol

Base: reviewed tip `5b460e7` of `cursor/seed-function-format-compare`.
Branch `cursor/seed-chat-template-repair`. Development only. Do not rescore
the closed format-comparison grid. Do not edit
`src/nexus/seed/local_model_runtime.py`. Do not download a larger model.

The last results used instruct models on raw `/completion` prompts. They
do not establish either model’s coding ceiling. `json_body` stays the
output format. Standing grant: 900 s this experiment, carried session
**2566.777111455996 used / 1033.222888544004 remaining**, local CPU.

## Changes before scoring

1. Compare the current raw user prompt with Qwen2.5 ChatML
   (`<|im_start|>system/user/assistant`) using the official default system
   line. The user text is identical. Both still go to `/completion`. Record
   the exact string posted, whether ChatML tokens are present, and that the
   GGUF contains those tokens. No new coding heuristics.
2. On inclusive replace, a public failure at the equal-to-limit case must
   revise with the exact sentence “For value equal to limit, expected True,
   received False.” Do not supply `<=` or any replacement operator. Record
   whether that sentence reached the revision request and whether the
   comparison changed.
3. Confirm new-function work on three fresh insert tasks with different
   transforms and empty / mixed-case / varying private cases. Keep every
   failure. One prior `code(item)` pass is not broad coding ability.
4. Measure repository target discovery separately: NEXUS inspects files and
   symbols from the request and sources only. Gold labels score
   path/symbol/action. Discovery is not wired into the assembler, so a
   wrong target cannot hide coding scores. Implementation still uses the
   public-test entry, as in the last experiment.
5. Memory is parent RSS plus the `llama-server` child RSS from `ps`. Report
   per-task wall and that combined RSS. Weight-file size is not runtime
   memory.

Format is `json_body`. Placeholder rejection and `return None` stay as
before. After the 0.5B matched-task scores, the better prompt style
(tie-break: `chatml`) is used for the three fresh tasks on both models.

## Expected grid

1 inspect, 8 template cells (2 models × 2 styles × 2 matched tasks),
6 fresh cells (2 models × 1 style × 3 tasks), 6 discovery cells
(5 coding tasks + 1 two-file fixture).

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Learning-to-learn unestablished. Do not merge `main`.

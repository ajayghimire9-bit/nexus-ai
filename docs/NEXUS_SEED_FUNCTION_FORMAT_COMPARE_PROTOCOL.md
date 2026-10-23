# Function-output formats and placeholder rejection — development protocol

Base: reviewed tip `b6b70cf` of `cursor/seed-constrained-edit-workflow`.
Branch `cursor/seed-function-format-compare`. Development only. Do not
rescore the closed constrained-edit grid. Do not edit
`src/nexus/seed/local_model_runtime.py`.

The last pilot queued wrapped identifiers (`ok`, `echo`) because the JSON
`function` field accepted a one-word string. The same pattern appeared on
both tasks.

## Changes before scoring

1. Record the exact request: rendered prompt, chat template (none; raw
   `/completion` `prompt`), JSON schema, stop (none), `n_predict` 128,
   temperature 0, seed 42, and raw completion. Prompts now say the value
   is executable Python source.
2. Compare three formats on the same two development tasks and budget:
   complete function as plain code; complete function inside JSON;
   function body inside JSON.
3. Reject placeholder bodies (`pass`, `...`, bare identifier, returning
   the function’s own name) with a precise diagnostic, then one revision.
   `return None` is allowed. Score syntax, execution and functional
   correctness separately.
4. Choose the best 0.5B format by those scores (tie-break:
   `json_function`, `plain_code`, `json_body`). Repeat that format on
   installed qwen2.5-coder-1.5b (`cc324af0…`). Compare wall time and RSS.

Target selection still uses the public-test entry. That is appropriate
here. Real repository requests will also need NEXUS to discover which
function to edit or create; that is not implemented.

## Expected grid

1 inspect record, 6 format cells (0.5B), 2 coder cells (1.5B, best format).

## Gates

No ranking or memory promotion. Learning-to-learn unestablished. Do not
merge `main`.

# Explicit input contract, two-stage revision, wired discovery — protocol

Base: reviewed tip `7f9fbac` of `cursor/seed-chat-template-repair`.
Branch `cursor/seed-contract-two-stage`. Development only. Do not rescore
the closed chat-template grid. Do not edit
`src/nexus/seed/local_model_runtime.py`. Keep ChatML and `json_body`.
Standing grant: 900 s this experiment, carried session
**2696.503148455996 used / 903.496851544004 remaining**, local CPU.

The last fresh failures treated a dictionary as a string. A placeholder
also consumed the only revision, so the 0.5B model never saw execution
feedback. Equality-only text cannot separate `<=` from `>=`.

## Changes before scoring

1. Compare the existing user prompt with an explicit input contract on
   the same development tasks: signature, `item: {"field": type}`, and
   representative public inputs. The only intended difference is that
   contract block. ChatML, format, and budget stay equal.
2. Reserve two revision stages under a fixed cap of three `complete`
   calls per cell: initial, one format repair (placeholder or malformed),
   one behavioral revision (public failure). Charge every call. Format
   repair must not consume the behavioral slot.
3. Behavioral feedback lists every failed public case with input,
   expected, and actual or exception. Comparison tasks also include
   below / equal / above evidence. Do not name a replacement operator.
4. After the 0.5B contract comparison, run a fresh end-to-end set with
   the better prompt (tie-break: `contract`). Discovery selects the
   assembler target. Measure target selection, executable code, revision
   success and private correctness separately. Include numeric / counting
   functions, not only string formatting.

## Expected grid

1 inspect, 8 contract cells (2 models × 2 prompts × 2 tasks),
6 end-to-end cells (2 models × 1 prompt × 3 tasks).

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Learning-to-learn unestablished. Do not merge `main`.

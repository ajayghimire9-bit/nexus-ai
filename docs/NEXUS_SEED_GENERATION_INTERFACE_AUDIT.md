# Generation interface audit — closed live compare

Artifact `artifacts/seed_metal_live_compare/seed_metal_live_compare.json`.
Offline. 0 new model calls.

## Chat formatting

Every saved prompt is Qwen2.5 ChatML: system, user, then
`<|im_start|>assistant`. User text extracts cleanly. Code prompts ask
for `{"body": "..."}`. Sentence prompts ask for a sentence only (no
JSON schema). `.get` was not in the prompts.

## Feedback placement

Code revision reused `Public execution feedback:` with
`undefined_names` / `public_input_keys`. That is the intended channel.

Sentence revision appended a JSON object
`{"reasons": [...], "instruction": ...}` after the user text. Later
drafts echoed that JSON. That is an interface failure, not evidence
that revision search works. The corrected note is now a short English
block: “Write one new English sentence only. Do not repeat this note.”

## Termination

The artifact did not store llama.cpp `truncated` / `tokens_predicted`
per candidate. Mean generated tokens across the run were about 34
(546 / 16), so most drafts did **not** use the 128-token cap.

The revision `.get` body is malformed
(`return f'{item.get(\"hall\", \\\\\" }`) and is labeled
`malformed_or_possibly_truncated`. That is **not** a proven 128-token
hit. Echoed feedback is a schema/placement problem.

Future Metal completes now record `truncated`, `hit_token_cap`,
`termination`, and send `stop=["<|im_end|>"]`.

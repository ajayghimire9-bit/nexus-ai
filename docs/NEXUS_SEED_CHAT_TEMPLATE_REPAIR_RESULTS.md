# Chat template, equality-failure revision, and fresh functions — results

Branch `cursor/seed-chat-template-repair`. Protocol `26f3347` committed
before scoring. This results commit is separate. Base reviewed `5b460e7`.
Not confirmation. Not a coding ceiling. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 8 template / 6 fresh / 6 discovery
cells, 63 events (27 complete / 22 worker / 14 assessment). Wall
**129.726037 s**. Ledger after this run:
**2696.503148455996 used / 903.496851544004 remaining**.

`fixed_boundary` stays the default. Learned ranking and memory were not
resumed. `local_model_runtime.py` was not edited.

## 1. What reached the model

Both styles post `prompt` to `/completion`. `n_predict` 128, temperature
0, seed 42, no stop list, `json_body` schema. The ChatML user section
equals the raw user text. The 0.5B GGUF `tokenizer.chat_template` contains
`<|im_start|>` and the official default system line. Raw prompts do not
contain those tokens.

Best 0.5B style by the predeclared score, then tie-break: **`chatml`**.
Both 0.5B styles failed public and private tests on the matched pair.

## 2. Inclusive `<` and the equal-to-limit sentence

The sentence is added only when a public case has two equal numeric
fields, expected True, received False. The revision does not name `<=`.

| Model | Style | First body | Revision | Sentence reached | Public | Private |
|---|---|---|---|---|---|---|
| 0.5B | raw | `...` | `return None` | no (placeholder used the slot) | fail | fail |
| 0.5B | chatml | truncated `<` | copied `<` | no (placeholder used the slot) | fail | fail |
| 1.5B | raw | `<` | `<=` | **yes** | pass | pass |
| 1.5B | chatml | `>=` | `<=` | no (equal case already passed) | pass | pass |

On raw 1.5B, the sentence reached the revision request and the model
changed `Lt` to `LtE` without being given the operator. ChatML 1.5B first
wrote `>=`, so the equal-to-limit case passed and the sentence was
correctly withheld; other public failures still produced `<=`. The 0.5B
model never saw the sentence because the one allowed revision was spent
on a placeholder.

## 3. Fresh functions (ChatML, both models)

| Task | 0.5B | 1.5B |
|---|---|---|
| `slug` spaces → underscores | truncated / empty | `item.lower().replace(' ', '_')` (not `item['text']`) |
| `ready` status | `item.lower() == 'ready'` | same; no `item['status']` |
| `pair` left/right | `item + '/' + item` | `item[0]/item[1]`, then bare `left`/`right` |

All six cells failed private tests. The earlier `code(item)` pass does
not establish broad coding. Matched insert `mark(item)` passed private
tests only for 1.5B ChatML (`item['kind'].upper() + '-' + item['name']`).
1.5B raw used attribute access and failed. Keep that failure.

## 4. Target discovery (not wired to the assembler)

6/6 gold matches. Public tests were not read. The two-file fixture still
selected `beta.hold` while the public entry named `alpha.keep`.
Implementation still used the public-test entry, so a discovery error
could not hide a coding score.

## Resources

Parent RSS is ~35–40 MiB. Combined RSS is dominated by `llama-server`:
~816 MiB for 0.5B and ~2111 MiB for 1.5B. Weight-file size (491 MB /
1117 MB) is not that memory.

| Block | Wall | Typical combined RSS | Mean cell wall |
|---|---:|---:|---:|
| 0.5B template (4 cells) | 9.699 s | 856 MiB | 2.42 s |
| 0.5B fresh (3 cells) | 7.427 s | 856 MiB | 2.47 s |
| 1.5B template (4 cells) | 60.902 s | 2136–2146 MiB | 15.22 s |
| 1.5B fresh (3 cells) | 48.696 s | 2146 MiB | 16.22 s |

## Next

ChatML is the better request wrapper here; it is not a coding ceiling.
The 1.5B coder can repair `<` when the equal-to-limit failure actually
reaches it, and it can write one new function under ChatML. It still
failed three fresh transforms. Next: keep ChatML, give a public-failure
revision even after a placeholder so the 0.5B model is actually tested
on that sentence, and require dict-field access on the fresh family.
Do not resume ranking or memory. Do not merge `main`.

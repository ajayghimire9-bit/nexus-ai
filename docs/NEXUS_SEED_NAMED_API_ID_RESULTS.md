# Named API-ID schema — development results

Branch `cursor/seed-named-api-id`.
Protocol `443c2e9`. This results commit is separate.
Base `4def313`. Artifact hash
`26bc50700d2f001d1ed46bd2575694613d743c318fd50b0b5cd33aa7ecffa8d5`.
Verifier `valid: true` on 8/8 cells. Opened positional API cells were
not rescored. Not confirmation. Not learning-to-learn. Ranking stayed
paused.

Frozen weights `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
`sha256:cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
Weights were not written.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_named_api_id.py tests/test_seed_equal_inclusive.py tests/test_seed_capability_routes.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_named_api_id.py artifacts/seed_named_api_id
PYTHONPATH=src:.deps python3 scripts/verify_seed_named_api_id.py artifacts/seed_named_api_id/seed_named_api_id.json
```

## The three scores

| Method | schema_ok | bindings_correct | task_satisfied |
| --- | ---: | ---: | ---: |
| direct | n/a | n/a | 0/4 |
| named_id | 4/4 | 2/4 | 2/4 |

Direct received the same API/field/parameter brief and one call.
It wrote bodies that did not pass private tests.

Per named_id cell:

| Task | schema | bindings | assembled task | What happened |
| --- | --- | --- | --- | --- |
| `api_nb_band` (vals, lo, hi) | yes | yes | yes | `clip_band` with all three `field.*` |
| `api_nb_stamp` (optional mark) | yes | no | no | bound `mark` to `field.text`; assembled `stamp(text, text)` |
| `api_nb_over` (elem vs list) | yes | no | no | bound `value` to `field.loads`; `type_mismatch`, empty source |
| `api_nb_scale` (list, not elem) | yes | yes | yes | `scale` with `field.vals` and `field.factor` |

Selection was 4/4 on named_id. That is not a general API solve.
Invalid or mistyped bindings did not become a runnable wrong-arity
`all(...)` loop. The optional miss assembled a well-typed wrong call.
The list-vs-element miss was rejected before execution.

## Cost

8 model calls, 57.520 s, frozen debit **0**. Product chat unused.
Metal unused. Process cleaned up. RSS reports the parent only.

## Verdict

The named schema is usable: every named_id request satisfied it.
Correct field binding and assembled task satisfaction are the same
2/4 (multi-numeric list and whole-list scale). Optional omit and
list-versus-element remain unsolved. Direct, equally informed, is 0/4.
Not learning-to-learn.

## Next

1. Keep broader learning paused. This is an interface result.
2. Optional parameters: the model bound a defaulted name it should
   omit. A new grid would need a case where binding the optional is
   required and one where it must stay omitted. Do not rescore these
   four.
3. List versus element is still the hard miss (`field.loads` vs
   `elem.loads`). Keep scoring schema, bindings and assembled behavior
   separately.

Do not tune this grid and rescore it.

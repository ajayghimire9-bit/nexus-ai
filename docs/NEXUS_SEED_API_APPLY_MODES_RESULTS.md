# API apply modes — development results

Branch `cursor/seed-api-apply-modes`.
Protocol `4fdc5ec`. This results commit is separate.
Base `711549e`. Artifact hash
`bddb543efa3c8e41323a60289a45edf951507a08783d2bde061d8e7d01cfd56a`.
Verifier `valid: true` on 18/18 cells. Opened named (`api_nb_*`) and
positional API cells were not rescored. Not confirmation. Not
learning-to-learn. Ranking stayed paused.

Frozen weights `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
`sha256:cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
Weights were not written.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_api_apply_modes.py tests/test_seed_named_api_id.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_api_apply_modes.py artifacts/seed_api_apply_modes
PYTHONPATH=src:.deps python3 scripts/verify_seed_api_apply_modes.py artifacts/seed_api_apply_modes/seed_api_apply_modes.json
```

## Four scores

| Method | structural | type | bindings | task |
| --- | ---: | ---: | ---: | ---: |
| direct | n/a | n/a | n/a | 0/9 |
| named_id | 9/9 | 0/9 | 0/9 | 0/9 |

Direct received the same interface brief, apply rules and one call.
It wrote bodies that did not pass private tests.

Named-ID by role (structure / type / bindings / task):

| Role | n | structural | type | bindings | task |
| --- | ---: | ---: | ---: | ---: | ---: |
| optional omitted | 2 | 2 | 0 | 0 | 0 |
| optional supplied | 2 | 2 | 0 | 0 | 0 |
| whole-list | 2 | 2 | 0 | 0 | 0 |
| element-wise | 2 | 2 | 0 | 0 | 0 |
| ambiguous ask | 1 | 1 | 0 | 0 | 0 |

Per named_id cell:

| Task | gold | structural | type | bindings | task | What happened |
| --- | --- | --- | --- | --- | --- | --- |
| `api_ap_omit_badge` | `name→field.name`, omit tag | yes | no | no | no | keys `{param: field.title}`; `binding_names` |
| `api_ap_omit_wrap` | `body→field.body`, omit pad | yes | no | no | no | keys `{param, field}`; `binding_names` |
| `api_ap_use_tone` | `text,tone` | yes | no | no | no | `{param: field.tone}`; `binding_names` |
| `api_ap_use_bonus` | `n→count`, `extra→bonus` | yes | no | no | no | `{param: field.count}`; `binding_names` |
| `api_ap_list_stretch` | `nums,gain` whole_list | yes | no | no | no | `{gain: field.gain}` only; `apply=direct`; `binding_names` |
| `api_ap_list_join` | `parts,glue` whole_list | yes | no | no | no | keys `{param, field}`; `apply=direct`; `binding_names` |
| `api_ap_elem_tall` | `n→elem.heights`, `bar` | yes | no | no | no | keys `{param, field}`; `apply=direct`; `binding_names` |
| `api_ap_elem_wide` | `span→elem.planks`, `need` | yes | no | no | no | `{span: field.planks, need: field.need}`; `apply=direct`; `type_mismatch` |
| `api_ap_ask_limit` | ask loft vs width | yes | no | no | no | guessed `gate.over` with `{param, field}`; did not ask |

API selection was 8/9 on named_id (`api_ap_ask_limit` should have asked).
That is not a general solve. Every named proposal used `apply=direct`.
No cell used `whole_list`, `element` or `ask`.

The type column is not the same as structure. Eight cells failed
`binding_names` (invented keys `param`/`field`, or a missing required
parameter). One cell used real parameter names and bound a list field
to a scalar (`field.planks` on `span`) — structurally legal, type
rejected, empty source, not executed. Optional-omit versus optional-supply
cannot be scored when the keys are not parameter names.

## Cost

18 model calls, 151.204 s, frozen debit **0**. Product chat unused.
Metal unused. Process cleaned up. RSS reports the parent only.

## Verdict

The named apply schema is usable: every named_id request satisfied it.
Type validity, correct bindings and assembled behavior are all 0/9.
The previous “schema 4/4” number was structural only. Separating type
shows why: a legal field ID on the wrong shape, or a legal object whose
keys are not parameters, still looks like a schema hit. Direct, equally
informed, is 0/9. Not learning-to-learn.

## Next

1. Keep broader learning paused. This is an interface result.
2. Do not rescore this grid or the opened named/positional cells.
3. The generation schema still allows binding keys that are not
   parameter names. Constraining those keys to the selected API’s
   parameters would make optional-omit, optional-supply, whole-list
   and element-wise visible instead of collapsing to `binding_names`.
   That is a new frozen grid, not a rescore.

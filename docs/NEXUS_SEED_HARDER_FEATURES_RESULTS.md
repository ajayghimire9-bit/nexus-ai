# Frozen recipe on harder features — development results

Branch `cursor/seed-harder-features-acquisition`. Protocol `5f34a17`
committed before scoring. This results commit is separate. Base reviewed
`b23e49f`. Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 5 supplied / 5 acquire cells, 42
events (16 complete / 16 worker / 10 assessment). Wall **198.307848 s**.
Experience comparison **NOT_RUN**. Ledger after this run:
**3005.155682455996 used / 594.844317544004 remaining**.

The frozen recipe stayed 1.5B / ChatML / `json_body` / contract /
two-stage revision / wired discovery. Ranking and memory were not
resumed. `local_model_runtime.py` was not edited.

## Frozen recipe

Inspect recorded that recipe and the five locked requirements before any
completion. Discovery selected every gold target (10/10).

## Harder features (supplied contract)

| Task | Requirement | Body | Public | Private |
|---|---|---|---|---|
| `total` list of records | sum amounts; missing=0; empty=0 | `sum(item['rows'] or [0])` | fail | fail |
| `tag` missing fields | kind:name; missing is `""` | `item['kind']` / `item['name']` | fail | fail |
| `admit` two predicates | age and score gates | `age >= min_age and score >= floor` | pass | **pass** |
| `due` two-file | cents/100 on `quote.py` | `item['cents'] / 100` | rejected (`Div` forbidden) | fail |
| `fit` inclusive window | on or between lo and hi; missing value False | `value >= lo and value <= hi` | pass | fail (missing value) |

Keep every failure. 1/5 private pass. Interacting predicates worked.
Lists, missing fields, and the two-file dollar conversion did not. The
two-file body was the intended arithmetic; the worker rejected `Div`.

## Contract acquisition

| Task | Origin | Asked | Private |
|---|---|---|---|
| `total` | inferred from examples | no | fail |
| `tag` | inferred from examples | no | fail |
| `admit` | inferred from examples | no | **pass** |
| `due` | inferred from examples | no | fail (`Div`) |
| `fit` | **asked** (examples hidden; source had only `value` and `hi`) | yes | fail (missing value) |

Inferred contracts matched the supplied outcomes. The ask path fired
once, the teacher returned public fields, and coding still failed the
private missing-value case. NEXUS does not yet obtain useful contracts
by itself for practical repository work: inferred equals “read the
public examples,” and asking still used the benchmark as teacher.

## Persistent improvement

Gate: 4/5 supplied private passes including `total` and `due`. Observed
**1/5**, and both required tasks failed. Experience vs scratch was
**NOT_RUN**. Learning research stays paused.

## Resources

Harder block wall **196.146 s**. Combined RSS ~1967–2043 MiB, almost all
`llama-server`. Parent RSS is not that number. Weight-file size is not
runtime memory. Cell walls 11–26 s.

## Next

Fresh-task success is not reliable enough to compare acquired
experience. Keep the recipe frozen. Do not resume ranking or memory.
Do not merge `main`.

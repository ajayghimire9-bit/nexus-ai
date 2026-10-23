# Recovery-action policy — results

Branch `cursor/seed-recovery-policy` from reviewed baseline
`e3d21b66785408a357d8f108231264ced4c0964b`.
[Protocol](NEXUS_SEED_RECOVERY_POLICY_PROTOCOL.md).
Verifier `valid: true`. Policy hash
`b07de72ba6a15e9e53148b6a536e6a08f2a283dcc2ac4b23f05e010377f30082`.

**Verdict: negative on the desired transfer claim. Retain
`all_cheap_first`.** Offline authored fixtures only. Live 1.5B assessment
is **BLOCKED_BUDGET**. Not learning-to-learn. Fixture success is not
model competence.

## Ledger

Closed CPU ledger **3564.568 s used / 35.432 s leftover / 0 s debit**
(frozen). Product `chat_usage.json` unused. Metal unused. Zero model
calls. Offline wall is engineering time, not a scientific debit.

## Development (6 identifiable tasks × 7 methods)

| Method | Private correct | Tools | Teacher | Confident errors |
| --- | ---: | ---: | ---: | ---: |
| Immediate revise | 1 / 6 | 28 | 0 | 0 |
| Fixed diagnostic | 3 / 6 | 26 | 1 | 0 |
| Source frequency | 5 / 6 | 27 | 1 | 1 |
| **All cheap first** | **6 / 6** | **25** | **1** | **0** |
| Learned | 6 / 6 | 25 | 1 | 0 |
| Reset weights | 6 / 6 | 25 | 1 | 0 |
| Shuffled weights | 0 / 6 | 6 | 0 | 0 |

The predeclared gate requires a useful accuracy/cost gain against the
strongest simple baseline. That baseline is `all_cheap_first` (6/6, 25
tools). Learned ties it exactly. Reset matches learned. Shuffle
collapses to 0/6. Reset/shuffle are not proof; here they show the
trained weights are unnecessary because inspect-then-revise already
solves this fixture grid.

Retention (2 older tasks): immediate 1/2; every inspect-first method
2/2. No accuracy regression versus `all_cheap_first`.

Locked assessment (excluded composition, excluded sort family, fresh
assumption, stop) was not run.

## Live budget (not executed)

Proposed 1.5B grid: 4 assessment + 8 source + 7 methods, about 40–60
completions, **900 s** wall cap, CPU `PersistentLocalRuntime` only.
The leftover 35.432 s cannot host that grid. Do not spend product chat
or Metal.

## Next step

Keep `all_cheap_first` as the recovery default. Do not promote the
linear scorer. A live 1.5B run is justified only after an explicit CPU
allocation of the proposed 900 s, using the frozen policy hash as a
control rather than the candidate.

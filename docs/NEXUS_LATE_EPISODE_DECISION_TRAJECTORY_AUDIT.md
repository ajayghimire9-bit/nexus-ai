# Late-episode decision trajectory — source and artifact audit

Offline. Zero new real steps. Zero imagined transitions. Collection unauthorized. Does not retune closed labels. Not control improvement, not learning-to-learn, not AGI.

Parent `e2da92c` (`cursor/long-horizon-control-assessment`). Branch `cursor/late-episode-decision-trajectory`.

## Exact scientific question not answered

After H=16 ranking looks adequate at shared initial states, **does the frozen student’s one-step prediction of the transition it actually executes get worse after step 64, more than zero context on its own live path?**

That is not answered by:

- Return-phase: 200 rewards and a few observation distances. **No actions, scores, candidate sets, or predicted next-obs.**
- Horizon-alignment: 200-step development returns. **No per-step actions or scores.** Student and zero used different per-step candidate seeds, so disagreement cannot be reconstructed.
- PCG: one-shot ranking at registered states. **No receding 200-step log.** Confirmation closed.
- Late-control / long-continuation / policy-switch: restored late **same-state first-action or 16/64-step forks**. Those studies are complete. This protocol does **not** repeat three-action counterfactuals.
- Receding-consistency: 16-step source screen from `s0` only.
- Decision-aware ranking protocol: initial-state 16-set contrast, still unauthorized, not this question.

Matched-state 3-action forks are **not** included. Late-control already measured same-state 16-step first-action quality (`action_quality_not_separated`). Repeating that on development would not supply per-step receding logs.

## Incremental evidence this experiment would generate

Live paired 200-step H=16 receding on **development** physics, shared per-step candidate seeds, frozen models:

- Selected action, 16 planning scores, selected index, planned second action, reward, observation, executed one-step predicted next-obs, at every step.
- First student–zero mismatch (last same-state decision). Prefix-matched steps are same-state; later steps are different-state.
- Receding plan-consistency (action at t+1 versus planned a[1] at t) as exploratory.
- 200-step return as a **separate** control metric, cannot pass the mechanism screen.

## Missing in the archive (not invented)

| Need | Archive |
| --- | --- |
| Per-step actions / scores on 200-step episodes | Missing |
| Shared-seed student vs zero receding on development | Missing (horizon used visitor-specific seeds) |
| Executed-transition prediction error along the live path | Missing |
| Receding plan-consistency over 200 steps | Missing (only 16-step from `s0`) |
| 16-step actual of the unevaluated 15 candidates at each step | Missing; **not collected** (would be 16× forks) |
| Three first-action 64-returns at restored late states | Exists on confirmation; **not repeated** |

## Confirmation and leakage

Confirmation physics stay closed. `primarily_late` is not retuned. Scoring does not receive simulator returns. Decision-aware protocol remains `authorized: false`. Exhausted 3600 s ledger unmodified.

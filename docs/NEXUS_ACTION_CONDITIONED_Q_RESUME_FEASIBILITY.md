# Action-conditioned Q resume — offline feasibility

Base `36a9753ba1afcf49b50802bfe0fd7d85625629c0`. Branch `cursor/action-conditioned-q-resume`. Artifact `artifacts/action_conditioned_q_resume_feasibility.json`. Zero new environment steps. Collection unauthorized.

## Reconstruction

Exact reconstruction of the missing cell is **possible** under the original locked seeds and frozen fits. This is not a collected result.

- Parent capture SHA `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680` unchanged.
- Parent fit SHA `2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae` unchanged.
- Original protocol SHA `76c06fd1de355d7176f7165b6e2dc1cfceb0729b67ea5cac244e595207bfa597` unchanged.
- 160/160 source cells: complete 64-step traces, returns rebuild, fingerprints match the frozen parent contexts.
- Ten source-only `action_obs` (λ=0.1) and additive Q fits rebuild to the saved checksums. Decoder-9 conditioned digest `d647adba80084f2085219464969e86a732b14f143f5425a648f708bcb167d5be`.
- 59/60 evaluation cells: complete live actions/rewards/seeds, three first-action traces, model/context fingerprints, and metrics that rebuild from raw rewards. Frozen digest `6e8bff7dd117ab396811165d690d6c9f7a45d5959b4b1dd3db8aedaaca423e5a`.
- Missing cell: decoder 9, development task 2, zero visitor. Reset seed `6100902` (shared with the saved student sibling). Collection seeds visitor-independent. Candidate seed `6300921` and future seed `6492100` differ from the sibling visitor.
- Development outcomes were not used to select family, ridge, seeds or the screen.

If resume collection of that cell fails fingerprint, live replay or metric reconstruction, abort and run a fresh full 240 s / 45,240 / 11,612,160 experiment. Do not patch.

## Proposed budget (not authorized)

60 seconds, 242 real steps, 64,512 imagined transitions. Estimate 15–25 CPU seconds including frozen-model load. New artifacts only. Full 60-cell validation and independent raw-trace audit before any scientific label.

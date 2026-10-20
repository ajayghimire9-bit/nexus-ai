# Frozen Seed action-ranking diagnostic — development only

Parent 484321469cdc6020141005bef6d3a53c6ca904db, verified local/remote equality.
The original checkout's two untracked adapter files remain untouched. Reuse
SeedRSSM, AuthoredWorld, modalities and existing MPC; no parallel learner stack.
The previous 626-step pilot and both frozen JSON checkpoints remain immutable.

Competing explanations: poor action-conditioned reward prediction; value-head
distortion of pruning; boundary-sensitive prediction errors. Diagnose, do not
assume one cause. No general-learning or old control finding is reopened.

Single executable config: configs/seed_action_ranking.json. Register 64 new
states from seeds84110001–84110064, alternating boundary/interior; side cycles
over four boundaries, other coordinate seeded; interiors are coordinates1–4.
Use the seeded authored goal, shifting it one x-cell if initially satisfied.
All actions start from exact cloned state, identical across both models.
No support history: the existing runtime's zero initial h/z and previous-action
sentinel0 are used identically. This is a cold-start diagnostic, not a visited-
state or full-episode causal explanation.

Evaluate all nine actions exactly once/state:576 authored steps total, cached
across models. Infer reward/state/value/done without access to outcomes. Record
reward-only and reward+.9value rankings separately. Tie-aware optimal rate,
mean immediate regret, pairwise accuracy, score range, reward MAE and exact
uniform-action expected regret are descriptive. The value score is intentionally
compared with immediate reward to diagnose possible objective mismatch, not
labeled a calibrated long-horizon return forecast. Analyze boundary/interior.
Two already-trained configurations are not independent replications. No
population confidence interval over states is claimed.

Flag useful ranking as unestablished when either model fails >=80% tie-aware
optimal choices or mean regret <=.05. If ranking is weak, a justified next coding
step is a small supervised auxiliary action readout, learned from **separate**
source states, with fresh held-out ranking and control evaluation. It must keep
the frozen RSSMs unchanged, use only observed inputs, and have its own committed
protocol before data. Do not train on this diagnostic or tune on its follow-up
audit. No architectural search, retry, extra model training or old split access.

Cap60seconds,576 new authored steps, local CPU. At most1152 imagined candidate
transitions plus128 observation-prior transitions, logged separately. Start
ledger1860.6321034559958used/1739.3678965440042remaining. Exclusive claim/output,
clean precommitted code, finite complete grid and unchanged hashes required;
save failures/partials without calling them inconclusive valid science.
Unit fixtures are source/engineering checks, not additional training replications.

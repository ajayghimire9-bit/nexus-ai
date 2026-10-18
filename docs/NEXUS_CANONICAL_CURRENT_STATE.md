# NEXUS canonical current state

Authoritative snapshot for future agents. Not a scientific result.
Generated from HEAD `4a08b26f81cbe314ae475e71419344e688ab571a` plus the
read-only branch inventory. Consult before proposing work.

## What NEXUS is now

An experimental research repository. Ambition: test whether models can
improve their own learning and planning through measured experiments.
Completing a roadmap item is not AGI. No profitable trading system exists.

**`main` is not the research tip.** `main` is `8d7f288` (PPO/GAE and
architecture-ranking fixes). Closed science from V0.5 through H16 and
Evolution-1/2 lives on topic branches that were never merged back.

Scientific ledger: **305.842 s used / 3294.158 s remaining.**
H17 remains **BLOCKED**.

## Closed scientific labels that must not be retuned

| ID | Outcome | Must not reuse as a new train label |
|---|---|---|
| H8 MCC source RMS | not established | closed unused MCC split |
| H9 residual scale | **harm** established | same |
| H10 MCC multitask @128 | supported, one holdout | H10 sources/target |
| H11 H10 confirmation | not established | H11 unused MCC |
| H12 same-state ranking | supported | H12 unused MCC |
| H13 ranking confirmation | supported | H13 unused MCC |
| H14 candidate-library DiD | **+0.178** supported | H14 unused MCC |
| H15 H14 confirmation | **+0.230** supported | H15 unused MCC |
| H16 same-state library | **+0.023**, not established | unused MCC (0.0015, 0.0014, 0.055) |
| Seven xenv rungs | not established | those unused physics |
| Lookahead family copies | mixed; algorithm copy, not L2L | their confirmation holdouts |
| Reptile vs multitask | Reptile lost in that config | that split |

H14/H15 are LEVEL 1 ranking/reuse findings. They are not learning-to-learn.

## Designed, not scientifically tested

- Evolution-1 transferable proposal memory (real families)
- Evolution-2 persistent vs reset (synthetic contracts only)
- H17 occupancy/library factorial
- Runtime scientific dispatch (stub only)

## Engineering that exists at HEAD 4a08b26

- PPO actor–critic, factory, V0.1 architecture evolution
- V0.5 LinUCB experiment selector (`nexus.meta`)
- World models, family lookahead, H10–H16 runners
- Evolution-1 catalogue, broker, reservation ledger, toy loop
- Evolution-2 synthetic screen and runtime stub (adapters, meters, IPC)
- H17 exclusion/seed reviews (blocked)

## Standing limits

900 s / experiment, 100 k new real steps, local CPU, 3600 s session
with 3294.158 s remaining. A prior budget does not authorize a new
experiment.

## Entry rule for future work

If a proposal rebuilds a planner, proposer, memory, meter, or
cross-task screen, name the existing module it is not replacing.
If it needs MCC physics, read the 29 H17 exclusions first. If it
claims LEVEL 2 or learning-to-learn, it must beat reset, random,
retrieval, and weight-init baselines on a new family — not another
seed of Pendulum or a synthetic linear oracle.

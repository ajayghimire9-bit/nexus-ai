# NEXUS full research reuse audit

Status: **review only**. No experiment, merge, deletion, or ledger debit.
Auditor: independent principal research architect.

Reference HEAD: `4a08b26f81cbe314ae475e71419344e688ab571a`  
Cleanup branch: `cursor/nexus-research-reuse-audit`  
Inventory: `artifacts/nexus_branch_inventory.json` (145 unique names)

Untracked Evolution-1 adapter drafts and Evolution-2 integrity WIP were
stashed before this branch was created and are not part of this commit.

Scientific ledger remains **305.842 / 3294.158**. H17 stays blocked.

This document distinguishes **source-verified** findings from
**heuristic / incomplete coverage**.

---

## 1. Branch inventory and ancestry

### Source-verified

- Local unique names at inventory time: **145**.
- `origin` heads: **116**. `github` heads: **118**.
- `main` = `8d7f288`. Research HEAD used here = `4a08b26`.
- `main` is **not** an ancestor of the later H10–H16 / Evolution work in
  the sense of carrying those results; those results live on topic
  branches. Merging `main` forward is a human decision, not done here.
- Shared tips (same SHA, duplicate names) — source-verified:

| SHA | Branches | Reading |
|---|---|---|
| `e4daa4e` | `codex/evolution1-resource-ledger`, `codex/evolution1-task-metadata` | Same tip; one is redundant |
| `0224391` | `codex/h17-seed-dependency-closure`, `codex/h17-seed-ingress-audit` | Same tip |
| `ff26193` | `codex/action-value-alignment-audit`, `codex/replanning-aligned-readout` | Same tip |
| `2dc746b` | `cursor/late-control-gap-design`, `cursor/late-control-gap-execution` | Execution name on a design SHA |
| `9d3e5ce` | `cline/xenv-context-adaptation`, `cline/xenv-deep-trunk` | Same tip |
| `4a08b26` | `cursor/evolution2-runtime-gates`, `cursor/evolution2-runtime-integrity`, this cleanup branch | Integrity repairs were **not committed** at inventory time |

Name-heuristic family counts (incomplete by construction):

H17 7, H16 16, H15 5, H14 5, H12/H13 4, H8–H11/MCC 5, E2 4, E1 7,
V0.x 21, xenv 9, lookahead-named 6, latent/context 10, planning-value 21,
meta/CL 1, governance 3, other 21.

Many lookahead and MCC result branches are filed under “other” or
planning-value because the classifier is a name regex. **Do not treat
those counts as a complete H1–H17 map.**

### Incomplete coverage

- Individual commits inside each branch were not checked out.
- Worktree-attached branches (`+` in `git branch`) were not compared
  file-by-file to their recorded SHA.
- Cursor Origin vs GitHub membership is recorded when `ls-remote`
  succeeded; a name present only locally is not therefore unpublished
  science.
- Cline-prefixed branches may be archival copies of cursor/codex work.

### Superseded *roles* (heuristic, not a delete list)

Typical chain, repeated many times: feasibility → protocol-lock →
runner → readiness audit → execute/results. Later roles supersede
earlier *authorization* states, not earlier *evidence*. Keep the
results branch even if the lock branch is later considered archival.

---

## 2. Hypothesis register — closed vs open

Source: `docs/NEXUS_HYPOTHESIS_REGISTER.md`. Labels below are copied
from that register, not re-estimated.

### Positive (configuration-local)

- H10: MCC multitask @128 beats scratch (**+145.8**), one holdout.
- H12: H10 recipe ranks shared H=16 candidates better than scratch.
- H13: same ranking recipe confirms on a new unused MCC holdout.
- H14: fixed library helps multitask relative to redraw (**+0.178**).
- H15: same DiD confirms (**+0.230**).
- Several family lookahead-vs-H=16 **algorithm copies** passed
  development and some confirmations (Pendulum, Acrobot, MountainCar,
  MCC). Register: algorithm copy, **not** cross-family learning.
- Parameter-free H=16 lookahead raised some 200-step Pendulum
  development returns (receding-long-term-value). Not L2L.

### Negative or harmful

- H9: source residual scale **hurt** MCC control.
- Reptile lost to matched-data multitask in that pilot (not a general
  disproof of L2L; not L2L).
- Nested H=8 scoring hurt 200-step development return.
- Many context / latent / amortized-encoder screens lost to zero
  context or fine-tuning (see register).
- Seven shared-trunk xenv rungs failed to establish transfer.

### Inconclusive / not established

- H8 source RMS; H11 H10 confirmation; H16 D_same **+0.023** interval
  includes 0; most xenv primaries; CartPole H=3 lookahead (ceiling);
  Acrobot compute-matched H=16; several value/commitment diagnostics;
  receding vs commit; same-set replanning.

### Blocked / untested scientifically

- **H17** occupancy/library factorial: exclusion and seed reviews
  exist; registration incomplete; **do not execute**.
- Evolution-1 real-family proposal transfer: designed, not locked.
- Evolution-2 persistence: synthetic contracts only.
- Runtime scientific dispatch: stub only.

---

## 3. Implementation overlap

| Capability | `meta` | `evolution` | `evolution1` | `evolution2` | `world` | `memory` |
|---|---|---|---|---|---|---|
| Choose next **training experiment** | LinUCB / ε-greedy | — | — | — | — | logs PPO rows |
| Mutate **network architecture** | uses specs | `mutate_spec` / `run_evolution` | — | — | — | stores result |
| Choose **planning catalogue arm** | — | — | Adaptive/Fixed/Random | persist/reset/evo wrappers | — | — |
| Cross-task **weight reuse** | — | — | persist flag (toy) | PersistentAdaptive | multitask / Reptile / FiLM | WM snapshots |
| World-model train/plan | — | — | metadata only | stub IPC | **canonical** | WM memory |
| Env construction | — | — | reviewed metadata (untracked draft) | bindings table | `mpc_for_model` (unsafe dispatcher) | — |
| Resource meter | — | — | **ReservationLedger** | host reuses it | post-call `Meter` (known hole) | — |
| Promotion / rollback | champion ckpt | — | fixture harness | none | confirm_guard | — |

Verified conclusion: Evolution-1/2 did **not** replace `nexus.evolution`
or `nexus.meta`. They are a third stack aimed at planning-config
selection. `world` remains the only place real models and envs run.

---

## 4. Feature matrix

| Feature | Status | Notes |
|---|---|---|
| PPO actor–critic | implemented, historical | `nexus.rl` |
| Architecture factory | implemented | `nexus.nn` |
| V0.1 architecture evolution | implemented | `nexus.evolution` |
| V0.5 experiment bandit | implemented | `nexus.meta` |
| V0.6–0.6.6 CL / RMS transfer | implemented + closed results | `nexus.cl` |
| World-model residual + MPC | implemented | `nexus.world` |
| Family lookahead (4 families) | implemented | do not route through `mpc_for_model` |
| H10–H16 runners | implemented; H14–H16 executed | closed |
| H17 | reviews only | blocked |
| E1 catalogue / broker / ledger / toy loop | implemented | synthetic |
| E2 persist vs reset screen | implemented | **synthetic demonstration** |
| E2 trusted bindings + stub host | implemented at 4a08b26 | not scientific dispatch |
| Guarded-memory / retrieval baseline | **missing** | called out in E2 audit |
| Process sandbox | **missing** | documented BLOCKED |
| Worker CPU enforcement | **missing** | measured only |
| New operators (LEVEL 3) | **not implemented** | catalogue is closed |
| Duplicate: three evolution packages | **duplicated on purpose** | different objects |
| Duplicate: two memories | **duplicated** | do not merge blindly |
| Duplicate: meters | E1 ledger vs world post-call Meter | reuse E1 ledger for new work |

---

## 5. Reusable artifacts vs forbidden reuse

### Technically reusable code

- Family lookahead and reward wrappers (explicit family).
- Residual world-model and training loop.
- `ReservationLedger`, catalogue, fixture broker.
- E2 `validate_public_payload` / stub host for **fixture** tests.
- PPO trainer and eval.
- H17 exclusion inventory as a **blocklist**.

### Historical data that must not become new training labels

- Any unused-MCC tuple named in H8–H16 protocols, including H16
  `(0.0015, 0.0014, 0.055)`.
- H14/H15/H16 returns and DiD tables.
- Evolution-2 `FAMILY_SPEC` hidden weights.
- Closed V0.7–V0.8.9 CartPole/Pendulum confirmation physics.
- The 29 H17 physics exclusions (plus conservative ambiguous cases).

Checkpoints may be **hashed and read** for integrity. They may not be
retrained against their own holdouts or used to fabricate E2 success
labels.

---

## 6. Contradictions

1. **Evolution-1 original design** asked for Pendulum + Acrobot
   training and a new family for development, n=10 independent models,
   ~200 k real steps. That **exceeds** the standing 100 k / 900 s cap
   (`NEXUS_EVOLUTION1_FEASIBILITY.md`).
2. **Evolution-2 evaluation** substitutes authored linear oracles in
   the proposer’s own feature span. That cannot inherit E1’s family-
   level claim. The E2 independent audit verdict was **BLOCKED**.
3. **H12–H17 exclusions** reserve unused MCC physics and block new
   MCC seed registration. An E2 “real screen” that reaches for another
   MCC unused tuple conflicts with H17 closure. Prefer Pendulum/Acrobot
   unused instances, not MCC.
4. **Runtime gates PASS** only for metadata/stub. Scientific dispatch
   remains BLOCKED. Treating 4a08b26 as experiment-ready contradicts
   `NEXUS_EVOLUTION2_RUNTIME_GATES.md`.
5. **`main` does not contain H10–H16 or E1/E2.** A checkout of `main`
   will silently drop the research tip. That is the largest
   repository-level hazard.

---

## 7. Proposed canonical architecture

Keep one spine. Do not add a fourth evolution package.

```
tasks (explicit family) 
  → world.dynamics / train (LEVEL 1 models)
  → family lookahead + ReservationLedger (LEVEL 1 planning)
  → evolution1 catalogue + AdaptiveProposer (LEVEL 2 candidate)
  → evolution2 persist/reset/retrieval (LEVEL 2 experiment, when authorized)
  → meta LinUCB (LEVEL 2 experiment *selection*, V0.5 object)
  → memory.store (PPO bookkeeping) and world.memory (WM snapshots)
```

Remove *unnecessary parallel implementations* by policy, not by
deletion in this audit:

- Stop using `mpc_for_model` as a family switch.
- Stop writing new meters; extend `ReservationLedger`.
- Stop new SQLite memories; use the two that exist.
- Do not reimplement the 12-arm catalogue.
- Do not promote E2 synthetic scores to scientific labels.

`nexus.evolution` (architecture search) stays for V0.1-style PPO
work only.

---

## 8. One scientific next step (not infrastructure)

**Question.** On unused Acrobot instances that are not any closed
MCC/Pendulum holdout, does a proposer that retains weights from
Pendulum catalogue evaluations discover higher best-of-4 planner
configs than (a) memory reset, (b) equal-budget random, (c) retrieval
of the last Pendulum winner, and (d) H10-style frozen weight init?

That is the original Evolution-1 LEVEL 2 question. It is the first
comparison that could speak to learning-to-learn of a *proposal
policy*. It is **not** authorized here.

Why this, and not another stub:

- E2 synthetic persistence is already demonstrated and is not science.
- H14/H15 show library reuse can help **within** MCC ranking; they do
  not show a proposer that improves across families.
- H10 is a single-holdout weight-transfer screen; H11 did not confirm.
  Weight init must be a **baseline**, not the claim.
- H17 must stay blocked; this step should **avoid MCC**.
- Standing 100 k / 900 s likely force frozen models and short prefixes.
  If the budget cannot support n=10 independent models, say
  `incomplete` rather than shrinking after outcomes.

**Preconditions (already known, not waived):** scientific family
adapters, real planner metering, no closed-split labels, separate
one-run authorization, retrieval baseline implemented. Until those
exist, **do not collect** and do not add another synthetic family.

This audit does not lock that protocol.

---

## Branch cleanup classification (proposal only)

Requires human approval before any ref change.

| Class | Examples | Action requested later |
|---|---|---|
| `mainline_lagging` | `main` @ `8d7f288` | Do not fast-forward without an explicit merge review |
| `active_engineering` | `cursor/evolution2-runtime-gates` | Keep |
| `active_blocked_science` | H17 review branches | Keep; do not execute |
| `closed_results` | H10–H16 execute/results | Keep forever |
| `duplicate_tip` | pairs in §1 | May archive one name after approval |
| `role_superseded` | feasibility/lock/runner once results exist | Keep as history; do not delete |
| `this_cleanup` | `cursor/nexus-research-reuse-audit` | Documentation only |

**Still requires your approval:** delete or rename any remote branch,
merge anything into `main`, create annotated archive tags, authorize
the Pendulum→Acrobot screen, or unstash/commit the Evolution-2
integrity WIP onto its own branch.

---

## Tools and reproduction

```sh
python3 scripts/nexus_branch_inventory.py
```

Read-only. No checkout. Ledger unchanged.

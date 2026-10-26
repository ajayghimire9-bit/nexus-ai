# NEXUS architecture comparison (Wave 36, NOT LOCKED)

Branch `codex/nexus-architecture-comparison`, from ea75187.

**Corrections to the owner's brief:**

| Brief says | Actually |
| --- | --- |
| commit ea78107 | **ea75187** |
| Checker v3 `3c68220c…` | **`3c68230e…`** |
| search cost 34,800 B | **33,960.7 G** |
| baseline 9b5d488 | no such commit; the baseline is **SEED_PRIOR = g0c2**, frozen at **9950e88** |

main and final_sealed are untouched. Checkers v1, v2 and v3 are unchanged, and no v4 was needed.

## 1. Baseline (frozen at ea75187) and contribution categories

Every table separates four categories:
* **(a) generic engineering**, shared by every arm: Checker v3 shared evaluation, the lazy best-first engine, exact
  observational dedup, the sandbox, the 5 detectors, the OS meter;
* **(b) learned knowledge** from source or stream tasks;
* **(c) autonomous evolution** with zero human amendments;
* **(d) externally designed changes** (by Claude).

Reference controls:
* **Fresh-v3:** (a) only;
* **B-online:** SEED_PRIOR, the online fragment prior plus tool knowledge, (b) with a (d) seed;
* **Gen 0 ON, Gen 0 OFF and frozen a0c2** (fixed controllers);
* **Fixed-payoff:** (d).

## 2. Stage A screening on development data (results committed in 3bb… see git log)

| ID | What ran (fidelity) | Dev result | Stage B |
| --- | --- | --- | --- |
| R1 | Stitch **adaptation**: compression-ranked contiguous fragments as best-first moves. Stitch's lambda / hole search and branch-and-bound are missing. | Held-out vs MilestoneA 1.134 (0/5); all 1.039 (0/5). Beats FixedDSL 0.79 and its Placebo 0.87. | reject |
| R2 | not built: it needs new op semantics, i.e. a Checker v4 with validation (≈ 1–2 engineering days; ≈ 600–1,200 s of validation compute). F3/F4 were already 100% solvable, so the stated motivation (intractability) does not hold here. | NOT EVALUATED | — |
| R3 | qwen2.5-coder-7B on M4 Metal (verified), 3 attempts, public-demo feedback, menu of the 18 G_P ops. A parser bug (quoted names only) was fixed and disclosed. | Coder fits 4/32 (all correct). Coder + NEXUS solves 32/32 at 10.82 G vs Fresh's 10.77 G, plus 268 s of Metal and 52k / 0.8k tokens. | reject |
| E1 | Normal-Inverse-Gamma Thompson controller around B-online (d) | vs B-online: F4 0.987, F3 1.013, F2 1.034, mixed 1.013. Still loses to the fixed controls on F3 / F4. | reject |
| E2 | Wave 35 (not rerun, per the owner): an 84-program locked evolution | the winner was the seed; 2/4 families; 50.3× including search | (existing evidence) |
| E3 | DGM-**inspired** branching archive vs incumbent-only vs budget-matched random, 2 lineages × 12 evaluations each, DSL edits only (no code self-modification) | best scores: DGM 0.950 / 0.917, incumbent 0.950 / 0.926, random **0.914** / 0.950. No method separates. Best held-out (DGM-1): 0.969 / 0.970 vs B-online on dev F3 / F4. | shortlist the DGM-1 program |
| N1 | Exact BOCPD (Adams & MacKay) over a symbolic 4-goal model | change: return 140.0 vs fixed-model 97.8, delay 13.7 vs 90.3, Brier 0.017 vs 0.147; other conditions ≈ fixed-model; 5 G per 600 steps | shortlist |
| N2 | **reduced** PETS: a 5-member bootstrapped goal-belief ensemble with the repo's RandomShootingMPC (h = 10, 64 candidates). Two integration bugs were fixed and disclosed: termination p = 1, and h = 4. Neural dynamics, trajectory sampling and CEM are missing. | clean ≈ 91 vs 146; change ≈ 72 vs N1 140; 79 G per run (16× N1) | reject for this setting |
| N3 | DreamerV3 not run. An estimate: ≈ 10⁵–10⁶ environment steps, hours of GPU, and a JAX / torch port onto Metal. | NOT EVALUATED | — |

## 3. Stage C freeze (this commit; before any confirmation seed is drawn)

* **Online track:**
  * **Program:** the shortlisted E3 program (`artifacts/wave36_e3_shortlisted_program.json`; a deterministic
    replay of lineage DGM-1 gives a best score of 0.9178 against the recorded 0.9174, the difference being meter
    noise in fitness, disclosed). It always uses the online prior, refits every 8 certified tasks, and weights tasks
    ×100 in the prior fit, which sharpens it.
  * **Seeds and arms:** one-use `wave36 confirm_online` 7606–7610 (derived per-family seeds s·10 + k). Arms are E3,
    B-online, Fresh-v3, Placebo-v3 (placebo of E3) and the fixed controls.
  * **Pass per family:** E3 pooled < Fresh-v3, < Placebo-v3 and < the strongest of {Gen 0 ON, Gen 0 OFF, a0c2,
    Fixed-payoff, B-online} chosen on the confirmation data, each in ≥ 4/5 seeds, with 0 wrong and 0 flags.
* **World track:**
  * **Seeds and agents:** one-use `wave36 confirm_world` 7611–7620 (10 seeds); agents reactive, model-free,
    fixed-model and N1. N2 is excluded for cost (16× N1, not shortlisted).
  * **Pass:** in `change` and `all`, N1 mean return > every control, in ≥ 8/10 seeds, with a lower mean Brier than
    fixed-model. In `clean`, `obs_noise` and `slip`, N1 mean return ≥ 0.97 × fixed-model.
* **Stage D:** the shortlisted winners live in different tracks (a stream learner and a world agent), so there is
  no shared task on which to integrate them. Interference and router tests are **not applicable** and are reported
  as such.

## 4. Stage C confirmation results (one-use seeds, run once after the freeze)

### Online track (`artifacts/wave36_online_confirm.json`; seeds derived from 7606–7610)

Every arm in every family: 100% solved, 0 wrong, 0 flags, D4 held. Work is G retired instructions (operating cost,
including all online learning and refits).

| Family | E3 program | B-online | Fresh-v3 | Placebo-v3 | Strongest fixed (data-chosen) | E3 vs Fresh | E3 vs Placebo | E3 vs B-online | E3 vs strongest | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F2 IR-routed (250) | **99.13** | 101.96 | 109.20 | 111.79 | B-online 101.96 | 0.908 (5/5) | 0.887 (5/5) | 0.972 (5/5) | 0.972 (5/5) | **yes** |
| F3 unseen (200) | **77.41** | 79.15 | 79.17 | 81.51 | a0c2 77.60 | 0.978 (4/5) | 0.950 (5/5) | 0.978 (4/5) | 0.998 (4/5) | **yes** |
| F4 unseen counters (200) | 72.06 | 74.34 | **71.56** | 73.86 | Gen 0 OFF 72.28 | **1.007 (0/5)** | 0.976 (5/5) | 0.969 (5/5) | 0.997 (1/5) | no |
| mixed, non-stationary (980) | **381.84** | 400.92 | 449.33 | 463.66 | B-online 400.92 | 0.850 (5/5) | 0.824 (5/5) | 0.952 (5/5) | 0.952 (5/5) | **yes** |

**E3 program: 3 of 4 families pass.** It is better than the previous online baseline (B-online) in all 4 families
(18/20 seeds). On F4 it still does not beat *no learning* (Fresh-v3, 1.007).

### World track (`artifacts/wave36_world_confirm.json`; 10 seeds, 600 steps each)

| Condition | N1 BOCPD return | fixed-model | reactive | model-free | N1 seeds > best control | N1 Brier | fixed-model Brier | N1 delay (steps) | fixed-model delay |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 142.1 | 143.5 | 122.7 | 16.7 | — (0.990× fixed) | 0.0080 | 0.0065 | — | — |
| obs_noise 0.2 | 137.4 | 138.3 | 109.5 | 14.6 | — (0.994×) | 0.0340 | 0.0314 | — | — |
| slip 0.2 | 110.0 | 110.7 | 81.8 | 23.5 | — (0.994×) | 0.0300 | 0.0293 | — | — |
| **change 1/150** | **135.5** | 89.7 | 61.5 | 8.2 | **10/10** | **0.018** | 0.161 | **12.8** | 67.7 |
| **all combined** | **99.4** | 74.2 | 39.2 | 11.7 | **10/10** | **0.050** | 0.146 | **16.8** | 63.2 |

**N1: PASS.** It wins 10/10 seeds under unannounced changes, with lower Brier and 4–5× faster post-change adaptation.
It is within 1% of the fixed model in stationary conditions. Its compute is 5.03 G vs 41 M instructions per
600-step run (≈ 120×), and peak RAM is negligible (pure Python).

### Stage D

The two confirmed winners are in different tracks (an online program learner and an interactive world agent), so
there is no shared task. Module interference and a router are **not applicable**. No integrated configuration was
built.

## 5. Resource accounting (native units; this wave)

| Item | Cost |
| --- | --- |
| Session compute | 56,283 s of wall time used in total, 7,317 s left (ledger) |
| R3 coder | 535 s of Metal wall (two runs; 268 s each), 105k input / 1.5k output tokens, peak RSS < 5 GB |
| E3 search, all 6 lineages | ≈ 5.70 T instructions |
| E3, the shortlisted DGM-1 lineage | 0.91 T, plus a 0.91 T replay |
| E3 program, saving vs the data-chosen strongest fixed learner on confirmation | 22.3 G over 40 streams (0.56 G per stream) |
| Break-even, DGM-1 lineage only | ≈ 1,600 streams |
| Break-even, the whole E3 comparison | ≈ 10,200 streams |
| Source-task cost | none; all online arms start from an empty library |
| World track | N1 5.03 G and N2-reduced 79 G instructions per run; 600 environment steps per run |

## 6. Decision Table

| Method | Implementation fidelity | Families tested | Held-out success | Work / return vs strongest control | Full learning / evolution cost | Calibration or certificate quality | Variability | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 Stitch fragments | adaptation (contiguous fragments; no lambda / hole search, no branch-and-bound) | inc3 LODO (4 domains) | held_out 1.134 vs MilestoneA | 1.039 (dev) | fit 1.9 G (marginal) | exhaustive_UNIQUE 280/280 | 0/5 seeds | **REJECT FOR THIS SETTING** |
| R2 representation synthesis | not built (needs Checker v4 op semantics) | — | — | — | est. 1–2 days + 600–1,200 s validation | — | — | **NOT EVALUATED** |
| R3 coder + checking | faithful local control: Qwen2.5-Coder-7B Q4 on M4 Metal, matched proposals and feedback | F3, F4 (dev) | coder 4/32; with checking 32/32 | 1.005 vs Fresh (instructions) | 268 s Metal per run, 52k tokens | coder-only 0 wrong; checked: exhaustive certificates | one checkpoint | **REJECT FOR THIS SETTING** |
| E1 Bayesian payoff | as specified (NIG + Thompson), hand-designed | F2, F3, F4, mixed (dev) | F4 0.987 vs B-online, but > Fresh | 1.013–1.034 vs B-online in 3/4 | none beyond online | 0 wrong | 0–2/3 seeds | **REJECT FOR THIS SETTING** |
| E2 typed-learner evolution | Wave 35 locked run (not rerun) | F2, F3, F4, mixed | 2/4 families | 0.936 pooled | 33,961 G (50.3×; ≈ 31k streams) | 0 wrong | per family | **REJECT FOR THIS SETTING** |
| E3 DGM-inspired archive (method) | adaptation (DSL edits, not code; no coding agent) | dev training + F3 / F4 dev | the methods do not separate (random best) | best scores DGM 0.917, inc 0.926, random 0.914 | 5.70 T for the comparison | 0 wrong; no embedded solutions found | 2 lineages per method | **INCONCLUSIVE** |
| E3-found program (c) | the shortlisted DGM-1 program, frozen | F2, F3, F4, mixed (confirm) | 3/4 pass; F4 1.007 vs Fresh | 0.952–0.998 vs strongest; 0.969–0.978 vs B-online in every family | 0.91 T lineage; ≈ 1.6k-stream break-even | 1,630/1,630 exhaustive_UNIQUE, 0 wrong, 0 flags | 18/20 seeds vs B-online | **KEEP** (as the online baseline; not better than no learning on F4) |
| N1 BOCPD symbolic | faithful BOCPD (constant hazard, truncated run lengths) on a 4-goal model | SwitchGrid × 5 conditions | change and all 10/10 | +51% (change), +34% (all) return vs the best control | 5.03 G per run (≈ 120× fixed-model) | Brier 0.018 vs 0.161 (change) | 10/10 seeds | **KEEP** |
| N2 PETS-style | reduced (bootstrap belief ensemble + repo RandomShootingMPC; no neural dynamics, trajectory sampling or CEM); 2 integration bugs fixed | SwitchGrid (dev) | change ≈ 72 vs N1 140 | 0.62× fixed-model (clean) | 79 G per run | Brier 0.005 (clean), 0.048 (change) | 3 dev seeds | **REJECT FOR THIS SETTING** (reduced variant; does not refute PETS) |
| N3 DreamerV3 | not run | — | — | — | est. 10⁵–10⁶ steps, GPU hours | — | — | **NOT EVALUATED** |

**Next unresolved architectural question.** N1 shows that Bayesian change detection is what wins under unannounced
change. Every stream learner still fails on F4, where learning itself does not pay. Can a **BOCPD-style run-length
posterior over the stream's own payoff signal** (in place of fixed refit periods or raw ROI ledgers) decide when to
learn, refit or stop learning, so that a single learner is never worse than no learning on F4-like families while
keeping the mixed-stream gains? Answering it needs fresh one-use seeds and an owner go-ahead.

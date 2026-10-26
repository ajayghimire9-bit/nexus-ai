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

# NEXUS — Locked late-control diagnostic, execution protocol v2

<!-- execution-lock: late_control_v2_equal_visitors -->

Starting SHA: 2dc746b07a8bc61bd784e664cc3cd0a46b1a5cf1. The GitHub base matches. No outcomes have been collected when this protocol is committed.

## Correction and estimand

The original observation-distance equality claim was too restrictive. Equality in the Euclidean norm-of-mean bound also holds for positively aligned displacement vectors, with unequal lengths. This corrects prose, not historical numbers.

Version 2 explicitly resolves the design's ambiguous state weighting. Five student-visited states must not outweigh one zero-visited state five to one. For each decoder, task and phase: average the five paired student comparisons separately inside each visitor group, then take half of each visitor-group mean. Average the four phases equally, then the four tasks equally. The resulting ten decoder contrasts are the only statistical replications. This follows the intended original equal-visitor design, but is versioned as a potentially material clarification before outcomes. A raw unweighted state average is prohibited.

## Locked execution

The single executable numerical configuration remains configs/late_control_gap_design.yaml, validated against the original lock. Preserve all its seeds, physics, support hashes, ten decoders, five students, H=16, 16 candidates, discrete actions, phases 16/50/100/150, 16-step continuation and 1800-second cap. The old design_only marker describes the historical registration; this execution module is separately authorized. There is no model fitting.

Slot 5 is zero context, slots 0–4 are students. Use the registered slot-specific live reset and planner seeds. At each stored state, use the same 16 candidate sequences for both contexts. At zero-visited states score all five students. At student-visited states score the visiting student. Check exact restored observations and replayed live decisions before interpretation.

Primary: simulate all three possible first actions, followed by the same decoder's zero-context replanning for 15 further steps. Every branch uses the same action-independent continuation seed stream. Take the student-selected action's actual 16-step return minus the zero-selected action's return. Actual outcomes never enter planning.

Secondary: from the identical stored state, run 16 steps of each entire policy with shared per-step candidate seeds; future actions and states can differ. This comparison cannot upgrade the primary decision. Store open-loop regret, reward forecast errors and action agreement as secondary diagnostics. The regret difference and selected-sequence return difference are mathematically identical, not independent evidence.

## Decision and integrity

A complete run requires exactly 1600 paired comparison cells: 10 decoders × 4 tasks × 4 phases × 2 visitor groups × 5 students. There are 960 distinct restored states and 240 harvested episodes. Validate every required numeric cell as finite, reject duplicates and missing grid members, and require 40 successful all-model frozen/context checks. Run the complete checkpoint audit before collection; missing checkpoints block execution without substitution.

The decoder-level two-sided Student-t 95% interval has nine degrees of freedom. `same_state_action_worse` requires mean <= −1 and upper bound < 0. Otherwise an interval with nonnegative upper bound is `action_quality_not_separated`; an entirely negative interval with mean > −1 is `below_practical_threshold`. Missing, invalid or timed-out execution is `incomplete`, not scientific evidence of no effect. Secondary intervals are descriptive and unadjusted.

Preserve all closed artifact hashes and reject overlap with prior registered seed sets. Commit this protocol and source before collection; record the clean execution revision. Refuse to overwrite the output artifact. Persist partial work per task, enforce the deadline within environment/model stepping, and never reduce the grid to claim completion.

## Budget and proposed verification

The registered environment budget is 381,312: support 512, live 48,000, open-loop 245,760, common continuation 46,080, full-policy continuation 40,960. Model-state estimate is 34,488,320, plus 245,760 live-decision replay states for integrity checks; report the actual instrumented count. No new support beyond the registered closed recollections. Hash every saved network before and after each task, including encoder and normalization; check installed contexts separately.

Tests cover exact restoration, candidate equality, continuation randomness independent of first action, zero continuation shared across branches, reward timing, immutable contexts, equal visitor weighting, decoder CI, missing/invalid/duplicate cells, closed seeds and protocol/artifact integrity. Run focused and full regression tests plus explicit local checkpoint verification. No architecture or planner change is authorized.

A completed inconclusive comparison leaves earlier divergence and longer-term policy effects unresolved; an incomplete run cannot select any mechanism. Even a negative same-state result cannot causally explain the previously measured 184-step loss. No general control improvement, learning-to-learn or AGI claim follows.

## Completed execution


Execution finished in **557.8 seconds**, under 1800 seconds. All 960 restored states, 240 live episodes and 1600 comparison cells completed. The locked label is **`action_quality_not_separated`**. The implementation commit is `e1f35e268371c80f493bdfdc4168599366875371` on `codex/late-control-gap-execution`. No rerun or tuning was performed.


### Primary and secondary results


Primary common-zero-continuation student-minus-zero return: **+0.0312 [-0.0827, +0.1452]**. Student return is -62.0419; zero return is -62.0731. The 95% interval includes zero, and the mean does not meet the −1-point rule. This is a complete inconclusive result, not an incomplete execution and not evidence of equivalence.

Secondary full-policy continuation: **-0.0234 [-0.2236, +0.1767]**, also inconclusive. Therefore neither continuation comparison separates the competing explanations (outcome C). These are 16-step contrasts and do not causally explain the 184-step loss.

One-shot regret improvement (zero regret minus student regret): **-0.3401 [-0.6409, -0.0393]**; this favors zero on these late visited states. Candidate reward-forecast MAE improvement: **+9.3995 [+7.0808, +11.7183]**, favoring student. First-action agreement: **+0.5925 [+0.5589, +0.6261]**. Lower forecast error does not establish better candidate selection. The regret and selected-sequence-return differences are the same mathematical comparison, not separate evidence. Secondary intervals are exploratory and unadjusted.


### Sensitivity



Tasks, primary paired differences:


- pendulum_ctrl_rp0: +0.1902 [-0.2436, +0.6240].


- pendulum_ctrl_rp1: -0.0715 [-0.3098, +0.1668].


- pendulum_ctrl_rp2: +0.0410 [-0.0267, +0.1087].


- pendulum_ctrl_rp3: -0.0348 [-0.0801, +0.0106].


Visitor groups, primary paired differences:


- student: +0.0995 [-0.1601, +0.3591].


- zero: -0.0370 [-0.1496, +0.0756].


Episode phases, primary paired differences:


- 16: +0.1681 [-0.2981, +0.6342].


- 50: +0.0034 [-0.1175, +0.1242].


- 100: +0.0728 [-0.0096, +0.1552].


- 150: -0.1193 [-0.2766, +0.0380].


Per-decoder primary contrasts, after equal task/phase/visitor weighting: 0: +0.394619, 1: -0.243817, 2: +0.067738, 3: +0.040180, 4: +0.033777, 5: -0.076652, 6: -0.012897, 7: +0.009175, 8: +0.002764, 9: +0.097545.


Task × visitor sensitivity (descriptive, same ten decoder units):


- pendulum_ctrl_rp0, student-visited: +0.3737 [-0.4907, +1.2381].


- pendulum_ctrl_rp0, zero-visited: +0.0067 [-0.0490, +0.0625].


- pendulum_ctrl_rp1, student-visited: -0.0112 [-0.3183, +0.2960].


- pendulum_ctrl_rp1, zero-visited: -0.1317 [-0.5109, +0.2475].


- pendulum_ctrl_rp2, student-visited: +0.0780 [-0.0178, +0.1739].


- pendulum_ctrl_rp2, zero-visited: +0.0039 [-0.0728, +0.0807].


- pendulum_ctrl_rp3, student-visited: -0.0426 [-0.0771, -0.0081].


- pendulum_ctrl_rp3, zero-visited: -0.0269 [-0.1003, +0.0464].


### Integrity, resources and provenance


All 120 checkpoint files verified before and after execution. Provenance verification also checked ten decoder fingerprints, global vectors, student hashes and the manifest against the closed artifacts. All 960 captured live actions and scores replayed successfully. Exact restored observations matched; 40 task/decoder checks preserved every encoder, decoder and normalization hash and every context vector. No optimizer update occurred.

Actual environment interactions: **381,312**, comprising 512 registered support recollections, 48,000 live steps, 245,760 open-loop candidate steps, 46,080 common-continuation steps and 40,960 full-policy steps. The counter instrumented the combined open-loop/common bucket (291,840); its split follows the completed locked grid. Actual imagined model states: **34,734,080** = registered 34,488,320 plus 245,760 live-score replay states. Model and environment steps were counted at the actual calls. The final regression rerun briefly shared CPU resources with execution, so wall time is local throughput rather than an isolated benchmark.

Configuration SHA256: `c168db64a6fca2285a39ad93485d167a0e0792f3bc7590465369fc950fdd28c9`. Execution-protocol SHA256 at the implementation revision: `daa3f227670a06e8616c40751d87ff681d619ea4935a1e8d66dee99281cb7fdb`. The report now includes outcomes; reconstruct the protocol bytes with `git show e1f35e268371c80f493bdfdc4168599366875371:docs/NEXUS_LATE_CONTROL_GAP_RESULTS.md`.

Artifact SHA256: `b3a0642e46890f0d6296d103ecd5ed1353cc6f2849b6dd61e46507f5f8dd5ea9`. All checkpoint hashes are retained in the committed parent manifest, linked by its SHA256 in artifact provenance. Closed result hashes and support hashes remain unchanged.

Dependency versions: python=3.13.5 (main, Jun 11 2025, 15:36:57) [Clang 17.0.0 (clang-1700.0.13.3)], numpy=2.5.4, torch=2.14.1, gymnasium=1.4.0, pytest=9.1.1.


### Commands actually executed


```sh
PYTHONPATH=src:.deps python3 scripts/verify_checkpoint_integrity.py
PYTHONPATH=src:.deps python3 -m pytest tests/test_late_control_gap.py -q -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest tests/test_late_control_gap.py tests/test_late_control_gap_design.py tests/test_receding_horizon.py tests/test_checkpoint_integrity.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest tests/test_checkpoint_integrity.py -m checkpoint_integrity -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_late_control_gap.py
```

Initial focused tests: 15 passed. Expanded focused regressions: 34 passed, one local-checkpoint test deselected by default. Final full suite: **404 passed, one deselected**. Explicit checkpoint test: **one passed, three deselected**. Standalone audit: **120 verified, zero missing, zero mismatched**, both before and after execution. The first sandboxed full-suite invocation failed before collection because temporary directories were read-only; the approved rerun passed. The unavailable `.venv/bin/python` was replaced by the existing Python 3.13.5 with `.deps`, without changing numerical settings.


### Interpretation and limitations


No reliable primary same-state action disadvantage was detected. The secondary full-policy continuation is also unresolved. Open-loop regret worsened on these late states despite improved reward-forecast error; that descriptive pattern does not make the primary outcome negative. Ten decoder units, four known physics and one trajectory per controller slot limit precision. The five student seeds share each decoder and are not independent decoder replications. Overlapping states and candidate rollouts are not statistical units. Full policies diverge after restoration; live visitor slots use different registered initial seeds, so distances between those captured trajectories would mix initialization and visitation effects and must not be called paired trajectory divergence. The earlier paired return-phase divergence result remains unchanged. No fresh physics confirmation, model training or general control-success test was performed.


### One next scientific recommendation


Register a separate same-state, longer-horizon policy-continuation study with the existing frozen controllers to test whether disadvantage accumulates beyond 16 steps, because both completed 16-step contrasts remain near zero while the closed 184-step return deficit persists.

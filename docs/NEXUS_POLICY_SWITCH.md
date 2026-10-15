# NEXUS — rp2 prefix/suffix policy-switch diagnostic

## Locked before collection

Starting revision: 7b018ec764736ad33416c8075f853e8c3bd3b936. The user authorized continuing bounded local work without repeated small permission requests after this diagnostic and its conservative cost were proposed. This authorizes one development run capped at 600 seconds, 52,268 environment steps and 13,378,560 imagined model states. No paid service, merge, architecture search, new weights or unbounded run is authorized.

The mission clarifications previously proposed are applied: compact adaptive intelligence remains the long-term research goal, Pendulum is a testbed, and AGI/learning-to-learn are not demonstrated. All historical artifacts and safeguards remain intact.

## Question

The completed 64-step run showed student tail loss concentrated on rp2. Does continuing student control after a student-controlled 16-step prefix cause lower return than switching to zero control from the identical prefix endpoint? Competing possibilities are continued-policy disadvantage, inherited-prefix disadvantage, both, or unresolved differences. This is mechanism research on one known physics, not independent control confirmation or a deployable task-specific controller.

## Fixed conditions and fresh sample

Use the same ten frozen decoders and five saved broad students, original normalization/support, H=16 and 16 candidates. Verify all 120 checkpoint files, fingerprints and parent/manifest hashes before collecting data. rp2 only: g=9.1, mass=3.1, length=1.05. Do not expose physics or task labels to models. Do not open reserved confirmation physics.

One fresh reset (1000200) and live planner seed (1050200) are shared across the six live controllers and decoders. Harvest 101 steps, recording pre-action states at 50 and 100. This is a diagnostic cut, not natural termination. Check seeds against all prior registered groups. Prefix/suffix step RNG is switch_seed_base + phase_index*1024 + visitor_slot*128 + local_step; it is independent of controller/context and switch choice.

At each state run all four 64-step schedules: SS (student 16, student 48), SZ (student 16, zero 48), ZS (zero 16, student 48), ZZ (zero 16, zero 48). Preserve original episode clock. Reconstruct the prefix endpoint exactly before its suffix. Both models' contexts remain unchanged; switching selects a frozen model instance, never overwrites or trains it. Prefix rewards/actions/endpoints must match for SS/SZ and ZS/ZZ.

Student-visited states evaluate the visiting student. Zero-visited states evaluate all five students and execute identical ZZ only once. Log full rewards, actions, RNG, predicted selections, true research-only simulator states, context and frozen-network hashes. The cached ZZ reference has no extra interaction charge.

## Statistics and decisions

Primary is SS minus SZ tail return, local steps 16–63: changing only the suffix policy after the same student prefix. Average five students within visitor group, equally weight visitor groups, then phases, inside each decoder. Use ten independent decoder means and Student-t 95% interval (df=9). The known physics and single reset limit generalization; states/episodes/student seeds are not independent decoder replications.

Label continued_student_suffix_worse only if mean <= -5 and upper interval bound < 0, with a complete valid grid. An interval including zero is suffix_unseparated; a negative interval with mean > -5 is suffix_below_margin; a positive interval is student_suffix_favors_student. Do not change the threshold after outcomes.

Secondary contrasts, unadjusted: SZ-ZZ tail (prefix inheritance under common-zero suffix); SS-ZZ tail (overall schedule gap); ZS-ZZ tail (suffix choice after zero prefix); and (SS-SZ)-(ZS-ZZ) interaction. Check SS-ZZ = (SS-SZ)+(SZ-ZZ) numerically in every pair. Do not treat this identity as independent evidence. Prefix and total returns are descriptive. No data-dependent state/decoder exclusions or reruns.

A negative primary supports suffix-policy disadvantage under these specified rollouts, including the future state paths that policy induces. It does not show each later action is worse or explain the entire 184-step historical gap. A negative inheritance contrast points to prefix consequences under this continuation. Neither significance nor nonsignificance alone establishes that one mechanism dominates; report all intervals.

## Completeness, resources and reproducibility

Expect 120 captured states, 200 paired cells, 60 harvest episodes and ten all-model frozen checks. Four schedules per student-visited state, and 16 executions at each zero-visited state after caching ZZ, imply 720 full schedule traces. Support collection 128 + harvest 6060 + schedules 46,080 = 52,268 real steps. Model states: harvest 1,551,360 + live replay 30,720 + schedules 11,796,480 = 13,378,560. Extra context encoder work is disclosed separately. Estimate about 3.5 minutes; hard cap 10 minutes. Tests and checkpoint checks are outside the scientific sample.

Commit protocol and implementation before the one run. Enforce caps inside environment/model calls, save partial results on failure, and reject incomplete grids as invalid execution rather than a scientific negative. Recompute every contrast from raw traces, validate identical prefixes, reward timing, episode boundaries and paired RNG. Check all frozen weights/context/normalization before/after and checkpoint file hashes. Independent arithmetic audit uses per-step reward differences and decoder aggregation. Preserve all earlier results; no architecture or control-success claim follows just because tests pass.

## Pre-collection verification

Focused tests: **41 passed** in 3.13 s. Full regression suite: **453 passed, one explicit-local-checkpoint test deselected**, in 83.74 s. Standalone checkpoint verification: **120 files verified, zero missing/mismatched**. Tests include informative toy controller switching, exact real-environment split-versus-uninterrupted replay, complete synthetic factorial reconstruction, missing-axis and invalid-metric rejection, paired seeds and hard-budget behavior. Test success establishes implementation behavior, not useful adaptation.

Commands before collection:

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_policy_switch.py tests/test_long_continuation.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/verify_checkpoint_integrity.py
```

After this protocol and implementation are committed, execute exactly once:

```sh
PYTHONPATH=src:.deps python3 scripts/run_policy_switch.py
```

Then audit existing raw data only:

```sh
PYTHONPATH=src:.deps python3 scripts/audit_policy_switch.py
```

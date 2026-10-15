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

## Completed results


The one locked run completed in **201.95 seconds**. All 120 states, 200 paired cells, 60 harvest episodes, 720 schedule executions and ten all-model frozen checks finished. Implementation SHA: `1dcbe94a640cbb743258f782f951990b252e5c26`. Label: **`continued_student_suffix_worse`**. No rerun, tuning, new weights or architecture change occurred.

Primary SS-SZ suffix return: **-18.733 [-27.271, -10.195]**. Equivalently, switching to zero control after the identical student prefix recovers **+18.733 [10.195, 27.271]** points over this 48-step suffix. All ten decoder means favored switching. Both the mean and the entire interval exceed the five-point harm margin in magnitude on this registered sample. This is a diagnostic intervention benefit on rp2, not evidence for a general switching controller.

Inherited-prefix effect SZ-ZZ under a common-zero suffix: **-4.025 [-23.422, +15.373]**, inconclusive. It cannot rule out a large inheritance effect. Overall SS-ZZ is **-22.758 [-45.939, +0.424]**, also inconclusive on this new sample. The prior closed rp2 loss is not overwritten or reclassified.

Suffix effect after a zero prefix ZS-ZZ: **-13.078 [-26.544, +0.388]**, inconclusive. Prefix/suffix interaction: **-5.655 [-17.417, +6.106]**, inconclusive. These secondary intervals are unadjusted. They do not show that suffix harm exists only after student prefixes, nor that inheritance is absent.


Per-decoder primary SS-SZ: 0: -23.308872, 1: -36.540661, 2: -4.559580, 3: -37.183691, 4: -23.934537, 5: -12.045822, 6: -15.592440, 7: -18.966051, 8: -13.649830, 9: -1.549829.


### What improved in the project


The repository now has an exact, paired prefix/suffix intervention, rather than a comparison that mixes differing prefix states with differing continuation policies. The primary pair shares every prefix action, reward and simulator endpoint. Its continuation policy changes while both frozen context vectors and network parameters remain fixed. This is a reusable experimental capability and a clearer mechanism result. The model itself has not been retrained or generally improved.

The evidence supports the narrow conclusion that continued student control is worse than zero-context continuation from these same student-prefix endpoints. The future trajectory divergence caused by the suffix policy is part of this measured effect. It does not identify a particular faulty action, neural feature or loss component, and it does not causally explain the complete historical 184-step deficit. A hard-coded rp2 switch or a universal step-16 cutoff is not established and has not been deployed.


### Integrity and resource accounting


All 120 checkpoint files verified before and after the run. All six models per decoder preserved encoder, FiLM, trunk, heads, normalization and context hashes. The independent arithmetic implementation matched the interval from per-step rewards across all 200 pairs, and verified **46,080/46,080** schedule decisions against regenerated candidate RNG. All live captured decisions replayed. SS/SZ and ZS/ZZ prefixes matched exactly. Early/tail/total and suffix/inheritance/overall identities passed. These checks are not independent external scientific replication.

Real environment interactions: **52,268**, exactly the cap: source-support recollection 128, diagnostic harvest 6060, factorial schedules 46,080. Imagined model states: **13,378,560**, exactly the cap: harvest 1,551,360, live replay 30,720, schedule planning 11,796,480. All controller comparisons use H=16 and 16 candidates. The additional 6400 support-history rows encoded during 50 context installations are separate encoder compute, not real interactions or imagined dynamics states. No new model training; prior checkpoint creation costs are inherited, not included in this diagnostic budget.

Full regression tests: **453 passed**, one explicitly separate local-checkpoint test deselected; focused tests **41 passed**. All scientific collection stayed below the 600-second cap. The tests are outside the scientific sample. Offline audit generated **zero** additional environment interactions. Artifact size: 7,516,207 bytes.

Config SHA256: `a7167a07f9b2329f7116afed6df1bbb687274bc73809bea9971f3617f124d38f`. Frozen pre-run protocol SHA256: `7a722c951dc579f1414bcc5881a0854ce03be3b35cafbd3ad833e73f19f3994c` (recover it from the implementation revision). Parent artifact SHA256: `15e2c4ce461287f2df5686e7b346aafe5ecbe9f4aa7fd237d9e5cf94920af92a`. Manifest SHA256: `265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b`. Raw result SHA256: `123bd0fd168397c4f030b049217116f4c7b6678f3b78d0df3e3627a9747c01b5`. Original checkpoint paths and hashes remain in the unchanged manifest; binaries remain outside Git.

Dependencies: python=3.13.5 (main, Jun 11 2025, 15:36:57) [Clang 17.0.0 (clang-1700.0.13.3)], torch=2.14.1, numpy=2.5.4, gymnasium=1.4.0.


### Limitations


Ten decoder training seeds are the independent units. Five student seeds, two phases, overlapping continuations and cached zero baselines are averaged inside each decoder; they are not extra replications. This is one previously diagnosed physics configuration and one fresh reset per task, so uncertainty is conditional on this narrow suite. It does not establish control generalization, online learning or learning-to-learn. The model weights are unchanged. All historical confirmation splits remain closed.


### Single next research direction


Prepare a source-only, control-oriented planning-value diagnostic on fresh development physics: test whether the frozen planner’s action-sequence scores predict longer-horizon continuation value before training any larger encoder. The policy-switch result establishes suffix-policy harm at matched states, but does not yet identify whether the error lies in the state model, short-horizon score or search. Keep architecture fixed and use a separately locked protocol; do not turn the rp2 switch into a task-label-based deployment rule.

# NEXUS — Longer-continuation development diagnostic

Status: **protocol and coding preparation; budget approval required; no simulation executed**.
Starting commit: `9996af93b852c58b026aaa40c851686ccadf38c4`.
Executable numerical source: `configs/long_continuation.yaml`.

## Scientific question and competing hypotheses

The completed late-state study found common-zero 16-step difference +0.0312 [−0.0827,+0.1452] and full-policy difference −0.0234 [−0.2236,+0.1767]. Neither establishes equivalence or explains the closed 184-step deficit. The next question is whether a disadvantage appears beyond local step 15 when the frozen controllers start at identical late states.

- H-policy: later decisions and the state paths they induce produce a negative full-policy continuation tail after step 15.
- H-first-action: consequences of the initially selected action persist into that tail even under a common future decision rule.
- H-unresolved: neither bounded comparison separates the explanations, or signs vary across physics/decoders.

These hypotheses can coexist. Different state paths are part of policy rollout effects; this design does not uniquely separate later action quality from induced state distributions. No architecture, model-weight, reward, optimizer, horizon or candidate-count change is allowed.

## Frozen resources and fresh states

Use all ten saved independent decoders, all five saved broad students per decoder, fixed context dimension eight, original 584-parameter encoder, H=16 and 16 candidates. Recollect only the four original 128-row fresh supports and require their stored hashes. Verify all 120 required checkpoint files, original decoder fingerprints, global vectors, student hashes, the manifest and parent JSON before any rollout. Never substitute missing weights or fit a model.

The four previously evaluated physics are recorded exactly in the YAML; they are diagnostic tasks, not untouched confirmation. Register new environment seed base 600000, live planner base 650000, candidate base 700000, common-continuation base 750000 and full-policy base 800000. Reject collisions with all prior registered seed groups, including the closed late-control sample. For each task use one new reset and planner seed shared across the six live controller conditions and all decoders: base + task_index × 100. These common initializations improve pairing; the earlier late-state protocol used slot-specific initializations. This is a new state sample and estimand, not a relabeling of the old 16-step result.

Harvest through original step 100 inclusive, capture pre-action states at steps 50 and 100, and explicitly mark the rollout stopping at 101 steps as a diagnostic cut, not natural termination. Do not compute/select on full-episode returns. One zero-context episode and five student episodes per task/decoder yield 480 distinct restored states. Both 64-step continuations finish before original episode step 200. Restore exact simulator state and observation; preserve original phase for boundary checks. True simulator states are evaluation-only.

## Same-state comparisons

At each captured state, draw one shared set of sixteen H=16 sequences using base + task_index × 4096 + phase_index × 1024 + visitor_slot × 128. The same candidate set is scored under student and zero context. Replay captured live decisions and check exact restoration before interpreting any contrast.

1. Full-policy continuation: student and zero each replan for all 64 steps. Pair planner randomness at every local step using the full-policy state seed + local_step. Future states and decisions can differ. At zero-visited states evaluate five students and one cached zero; at each student-visited state evaluate the visiting student and zero. Cache only identical executed evaluations; do not charge cache reuse as new interactions.
2. Common-zero continuation: roll all three possible first actions once, followed by the same zero-context planner for 63 steps. Each branch uses the identical action-independent common-state seed + local_step. Index the returns by the student-selected and zero-selected first actions from the shared candidate set. This isolates the initial action choice under a specified common future policy; future states still differ.

Record every actual reward, action, phase, reset/planner seed, selected candidate, context fingerprint and model hash. Keep context fixed. Do not feed actual counterfactual outcomes into planning. Score candidates before simulating outcomes. The common and full-policy comparisons use separate seed streams; no statewise algebraic subtraction between them identifies a unique causal component.

## Primary estimand and locked decision

For each paired state/student compare the full-policy reward sum over local steps 16–63: student minus zero. This tail is the **one primary contrast**. Its total over 0–63 and its 0–15 prefix are secondary; verify early + tail = total to numerical tolerance. The 64-step sums come from one trace, not separately rerun windows.

Average five student comparisons within each decoder/task/phase/visitor group, weight the two visitor groups equally, then the two phases equally, then four tasks equally. All 800 paired comparison cells must be present. Form a two-sided Student-t 95% interval across the ten decoder means, df=9. Do not treat episodes, student seeds, or overlapping windows as decoder replications. Uncertainty is conditional on these four physics and the registered state sample.

Predeclare a five-return-point minimum disadvantage for the 48-step tail (about 0.104 points per step). Label `long_policy_tail_worse` only if the primary mean <= −5 and upper CI bound < 0 with complete valid data. If CI includes zero: `long_policy_tail_unseparated`. Entirely negative interval but mean > −5: `long_policy_tail_below_margin`. An entirely positive interval is `long_policy_tail_favors_student`; it is not a general control claim. No optional stopping, horizon choice, task exclusion or threshold revision after outcomes.

The common-zero tail is a prespecified secondary diagnostic with the same five-point descriptive screen. Report unadjusted intervals for it, all early/total differences, tasks, phases, visitors and leave-one-task-out sensitivity. Secondary results cannot upgrade the primary label. If both tails worsen, both hypotheses remain compatible. If only the full-policy tail worsens, later decision rules and induced trajectories are supported as a joint description; a non-significant common effect does not prove its absence. If neither separates, preserve the unresolved result and do not recommend a larger network merely because this test was negative.

## Completeness, cap and authorization

Reject a missing decoder/task/student/visitor/phase/trace or nonfinite required metric before aggregation. Require exact model/context preservation, every registered live replay, valid reward sums and all paired reset/planner seeds. Invalid/incomplete execution has no scientific outcome. Save partial results atomically on timeout; do not shrink the grid or rerun with altered settings.

Estimated cost: **198,832 environment steps**, including 512 support, 24,240 harvest, 92,160 common-continuation and 81,920 full-policy steps. **50,851,840 imagined model states**, including live replay and shared scoring. No simulator evaluation of every whole candidate sequence is included; the present question does not require repeating that costly open-loop measurement.

Scaling from the completed run projects about **817 seconds (14 minutes)** of local execution. This is an estimate, not measured performance. Proposed hard cap: **1800 seconds (30 minutes)**, one local CPU run, no paid service, no training. Tests/integrity checks are separate low-cost preparation. Obtain human approval of this exact configuration hash and budget before implementing the final collection driver and starting it. The preparation command has no execution option; the approval helper fails closed without the matching lock. A matching digest is a technical guard, not evidence of human consent.

After approval, implement the collection driver using the tested continuation primitive and existing verified model-loading/state-restoration helpers; add real-environment integration/replay checks, commit that implementation before outcomes, and execute once. This branch deliberately contains preparation, not an unattended runnable experiment.

## Checks implemented now and required before execution

Offline tests cover seed separation, budget arithmetic, reward-window identities, exact decoder CIs, fail-closed approval checks, raw-grid deletion/summary corruption, and the generalized 64-step continuation with a deterministic test double. No real environment is created by this preparation or its tests. The offline parent audit independently indexes saved actual-action returns and recomputes equal-group decoder statistics instead of calling the historical aggregation helper.

Before execution, test exact simulator restoration and original-episode boundaries, paired candidate generation, full-policy/common-policy RNG, context immutability and every frozen hash using the real environment/checkpoint path. Require a clean committed revision, protocol/config hashes, exact complete-grid validation and cap enforcement in the final driver. Existing tests of the 16-step helpers are retained; their success does not establish correctness of an as-yet-unimplemented full collection driver.

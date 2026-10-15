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

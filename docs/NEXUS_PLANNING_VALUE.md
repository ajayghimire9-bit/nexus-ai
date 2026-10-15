# Source planning-value diagnostic — locked protocol v1

Starting revision: `850dbaa9ebb3f00eb2bdb81d5b1209c43600e9c8`. Remote matched this local, clean revision. The user authorized another bounded local research cycle. No training, controller modification, closed-seed reuse, or independent control-success test is authorized here.

## Question and competing explanations

H-objective: even exact simulator H=16 reward ranking omits practically relevant consequences under a common later policy. H-model: learned-model score errors, rather than that short objective, dominate the selected sequence's longer-value regret. Both, neither, and task dependence are possible. Exact simulator scores are research comparisons only; they never enter deployed MPC or latent inference.

This is the smallest source-only planning-value diagnostic following the policy-switch result. It uses the eight **existing source physics**, not fresh physics confirmation. New initial-state, support and action seeds are fixed in `configs/planning_value.yaml`. It does not test the heavy-mass rp2 failure directly. Previously evaluated physics and artifacts stay closed. The fresh material is episode experience, not new independent physics.

## Frozen design

Ten independently trained decoders, five saved broad students each; unchanged normalization, weights, FiLM, H=16, 16 candidate sequences, actions −2/0/+2 and published Pendulum reward. Verify all 120 required checkpoint files and manifest before and after. No fitting of any kind. New 128-row random-behavior support per source task, shared across decoders/students. Source support is disjoint from diagnostic reset seeds.

One registered reset state per source task; all eight tasks weighted equally. At that identical simulator state draw one shared 16×16 candidate action array. Execute each full candidate block in the simulator once, recording all rewards, observations and endpoint state. Cache this model-independent prefix across decoders. Score the same block with zero and each student context using unchanged MPC rollout scoring.

From each actual prefix endpoint, execute 48 steps of the **same decoder's zero-context MPC**. Each local continuation step uses a preregistered seed independent of candidate index, selected action, student seed and previous outcomes. The continuation policy is identical across candidate comparisons within a decoder, but acts on different endpoint states. Preserve the original episode clock (suffix starts at 16). Never cross a 200-step boundary. Sum the actual 16+48 rewards to obtain this candidate's diagnostic 64-step value. Frozen contexts remain fixed.

Crucial distinction: committing a whole 16-action block before zero-policy continuation is **not** receding-horizon first-action execution or full-episode policy value. This diagnostic can reveal objective truncation under this intervention, but cannot causally explain the earlier negative episode transfer.

## Outcomes, aggregation and decision

Primary: 64-step regret of the candidate selected by **exact actual H=16 reward**, relative to the best 64-step candidate in this same 16-candidate set. Argmax ties use first index. Average eight tasks within decoder; t interval across ten decoder means, df=9 (critical value 2.262). Repeated states, candidates and student seeds are not independent replications. The eight initial states and shared support are fixed; uncertainty is conditional on this finite suite. Regret is nonnegative by construction, so an interval above zero alone is weak evidence. Declare `short_objective_misses_practical_value` only if complete integrity passes, mean regret ≥5 and 95% lower bound >0; otherwise `objective_mismatch_inconclusive`. This is a development screen, not generalization proof. No multiple primary outcomes.

Secondary, exploratory: student and zero 64-step regrets; student-minus-zero selected 64-step return; exact16-minus-model selected 64-step returns (may have either sign); H=16 predicted-versus-actual reward MAE; candidate-ranking correlation against actual16 and actual64; first-action/sequence disagreement; per-task and per-decoder results. Average five student seeds inside task/decoder first. Actual64-best is an in-set diagnostic reference, not an oracle controller. Actual16 and actual64 share prefix rewards and their differences/regrets are algebraically dependent; never count them as separate replications. Secondary intervals are unadjusted descriptive intervals. No retuning or follow-up run on these seeds.

## Compute cap and provenance

One run only. Cap 600 seconds (~4–6 minutes estimated from the preceding 202-second/13.38M-state run). Planned environment interactions: support 8×128=1,024; cached prefixes 8×16×16=2,048; suffixes 10×8×16×48=61,440; total **64,512**. Imagined transitions: score 10×8×6×16×16=122,880; continuation 61,440×16×16=15,728,640; total **15,851,520**. Support encoding adds 10×8×5×128=51,200 encoder rows, separately disclosed. No source-training interactions in this run. Checkpoint verification, JSON saving and CPU wall time included in cap. No paid services or unbounded retries.

Save partial results with `complete=false` on missing cells, nonfinite data, timeout, integrity discrepancy or other failure. Commit this protocol, executable configuration, tests and implementation before execution; require clean Git revision. Record SHA, hashes of configuration/protocol, source data, parent and manifests, exact dependency versions, counters and raw reward/action traces. Prior artifact files must remain byte-identical. A standalone offline audit checks raw reward arithmetic and candidate RNG without collecting new data.

## Planned correctness checks

Shared restoration and candidate arrays; correct prefix/suffix reward indexing; same continuation RNG across candidates; frozen weights/normalization/context; source-only task registry; closed seed rejection; exact planned decoder/task/student/condition grid; missing whole axes, numeric strings, bool, NaN/inf and truncated traces rejected; selected indices reconstructed from raw scores; ten-decoder aggregation and cap enforcement. Synthetic tests are correctness evidence only.

## Reproduction

`PYTHONPATH=src:.deps python3 -m pytest tests/test_planning_value.py -p no:cacheprovider`

`PYTHONPATH=src:.deps python3 scripts/run_planning_value.py`

`PYTHONPATH=src:.deps python3 scripts/audit_planning_value.py`

The runner refuses an existing result, dirty implementation or changed locked configuration. No results have been measured at protocol registration. After execution, results are reported below without changing the registered rules.

# Recorded-data value/candidate discrimination — exploratory protocol v1

Locked before calculating the contrasts below. This is reanalysis of the inspected frozen-calibration sample, **not independent confirmation**. Branch codex/value-candidate-discrimination, parent12ae8c7. Config SHA256 `737da7623b973f4ef176838dee742149f38a6d95ef3cc28fa859be099a635db8`.

The previous calibration improved RMSE against a source mean but the earlier first-action control test was inconclusive. Two falsifiable descriptive possibilities remain: value errors mainly reflect between-state offsets, or the readout can also distinguish better candidate sequences within a state. Neither is assumed.

## Locked data, rules and computation

Use only the existing calibration capture, complete offline validation, source-fit readouts and saved frozen contexts, checking exact file hashes. Keep all networks, normalizers, readouts, H16 planner logic and16 candidate opportunities unchanged. Re-score the exact original full16-candidate set with the original base-plus-survival-times-terminal formula. Preserve all model/context fingerprints and verify all120 checkpoint files. No training, support collection, new environment, initial state, simulator outcome, or optimization.

Only candidates0,4,8,12 have observed outcomes. Restrict every choice and regret comparison to **that same four-candidate set**. Actual64 return is recorded actual16-prefix reward plus the recorded48-step unchanged-zero continuation. This measures complete16-action commitment followed by zero-policy continuation; it does not measure committing only the first action, replanning with the corrected policy, the best of all16 actual sequences, or full-episode return. Actual outcomes never enter the frozen model inputs or scores.

For each of five student contexts and zero context compare in-set choices using:

1. Original predicted H16 scores.
2. Original scores plus frozen survival16×learned terminal value.
3. Original scores plus survival16×the fixed mean32 source tail targets (generic-offset control).
4. Actual simulator16-prefix reward ranking, research-only truncation diagnostic.

Argmax ties choose the lowest preselected candidate index. Compute return, regret versus the maximum actual64 return within these four, and best-in-set selection accuracy (actual-return tolerance1e−8). Identical source mean and all saved tail labels are shared across compared conditions, not fitted from query outcomes.

## Primary aggregation and decision

Primary descriptive contrast: learned-terminal chosen64 return minus original chosen64 return. Average the five students within each decoder/task and then average the three development tasks equally, producing ten independent decoder values. Report paired t95% interval, df9/critical2.262. Exploratory point-estimate screen: mean≥1 return point and lower bound>0. Negative interval means in-set ranking harm; otherwise inconclusive. This retrospective diagnostic cannot upgrade the previous control-success label. No new held-out evidence is claimed.

Source tasks, each development task, zero-context results and learned-versus-constant correction are secondary unadjusted paired intervals. Report all decoder values. Student seeds, candidate sequences and tasks are not additional decoder replications. Regret reduction is algebraically identical to chosen-return improvement and must not be counted as independent evidence.

## Error decomposition

For each task/context, let e_i=predicted48−actual48 across the four candidates. Verify MSE=mean(e)^2+mean((e−mean(e))^2) within numerical tolerance. Report bias-squared and centered error separately. A constant's centered MSE is the variance of those four actual tails. Report constant-centered MSE minus readout-centered MSE, positive means within-state discrimination of tail values. This is descriptive; do not infer causal control failure from correlation or a large mean-error component. Exact64 selection and actual16 selection form research diagnostics, not learned controllers.

## Bounds and failure rules

Zero new real interactions. Replaying full16 score and endpoint logic:10×11×6×(256+256)=**337,920 imagined transitions**, hard wall cap300 seconds, expected well under one minute locally. Save complete/partial outputs honestly. Require all110 decoder/task cells, all six contexts, all required finite metrics, exact candidate replay, locked data hashes, unchanged fingerprints, complete checkpoint audits and exact computation counts. Reject omitted axes, duplicate cells, booleans/strings/nonfinite metrics and corrupted score/value arithmetic. Confirm replayed selected endpoints reproduce saved calibration inputs within1e−6; failure blocks interpretation.

The latest two-hour simulation authorization expired during an interruption. This subsequent low-risk recorded-data/model-inference analysis is covered by the renewed instruction to continue; it does not launch additional simulation. It does not purchase compute, modify main, reopen confirmation, or authorize further environment collection. No change to agent permissions or scientific safeguards.

## Tests and outputs

Tests first: a toy example with good absolute calibration but reversed ranking; correct bias/centered decomposition; constant-correction survival weighting; actual64 endpoint/reward indexing; subset equality/tie handling; mean-inside-decoder aggregation; missing-grid/type rejection; no environment construction; and frozen context/readout preservation. Commit protocol and implementation before analysis. Save raw model scores, per-context metrics, paired summaries, hashes, dependencies, runtime and inference counts. Repository-only result verification must not require checkpoint binaries; explicit replay verification must fail on missing binaries. Do not overwrite any prior files.

If the readout lowers absolute error but does not improve candidate selection, investigate decision-relevant value evaluation before adding capacity. If it helps complete-sequence selection but not the earlier first-action intervention, the commitment/replanning mismatch remains a candidate explanation, not a causal finding. Preserve negative/inconclusive outcomes. Recommend one next step only after this analysis.

# E3.12E — Training-reset imbalance and selection stability, exploratory lock

Base72789256c0b9a7689f7cffbfb1183e01f336c188, branch
codex/e3-12e-training-stability-and-lab. Current human request authorizes only
existing-training-data analysis, no new simulations. D's query result is closed
and unchanged; its training data have been inspected, so this is an exploratory
diagnostic, not independent confirmation. Preserve unrelated adapter files.

Hypotheses: pooled raw return ordering can reflect reset-group difficulty;
alternatively choices may be stable despite that offset. A few observations
may dominate decisions, or estimates may be robust to their removal. Do not
assume that a different training rule improves unseen returns.

Use only32 registered revealed training rows from D, with parent and one child
per reset, four resets/child/model. Pin D raw/config hashes before analysis.
Hash and structurally scan the source container, but never deserialize query
row bodies or top-level analysis. Decode each row's role, then only training
row identity/protocol/paths. Project returns, measured costs and transition
hashes; refuse missing/duplicate models, resets, arms, nonfinite rewards or
inconsistent sums. Changing any query outcome must not change the training
projection hash or diagnostic. Container hash changes still fail input integrity.
Byte hashing/span skipping is not outcome access by the learner.

Predeclared calculations per frozen source model:

1. Existing parent-aware and two-child mean choices, matched-advantage parent
   guard, and existing StrategyGenerator mean/recent/conservative credit rules.
   All receive identical observed training receipts, in original order, with
   unchanged return scale100 and measured CPU costs. Reuse partial-feedback
   contracts and operator_headroom.replay_feedback; no new learner or memory.
2. For each arm, verify raw child minus pooled parent = matched child-minus-
   parent + parent-on-arm-group minus pooled parent. Report each term and
   positive-sign disagreements. An algebraic decomposition is not causation.
3. Delete each entire matched reset in turn (eight/model), refit only those
   training summaries and report changed choices. This gives3/4 arm counts;
   it is sensitivity analysis, not a proposed unequal-budget policy comparison.
4. Delete one reset from each child group (sixteen/model), leaving3/3 child
   observations. Report full traces/choice changes for every method.
5. Enumerate all70 balanced4/4 partitions of the eight observed PARENT returns.
   Compare the actual absolute parent-group gap with this descriptive reference.
   Never impute a missing child return, swap child labels or claim calibrated
   significance from this diagnostic partition count.

No query performance, policy-value estimate, selected best rule or success
promotion is allowed. Report all models; deletion cases and partitions are
dependent, not extra model replications. The independent source-model count
remains two/family. No confidence interval across deletions or pooling unlike
family return scales. Label complete finite findings as exploratory training
diagnostics; fail incomplete/invalid grids honestly. No scientific win threshold
is appropriate for this audit; it diagnoses estimates, not useful learning.

Reuse SAME run_e3_3_training_feedback_audit.py offline host with --stability,
exclusive one-run records, source/config/protocol hashes,60-second CPU-local cap,
zero environment/imagined transitions/neural inference/fits, and existing
write_new/verification helpers. selection_stability.py is diagnostic glue only.
Commit protocol, implementation and exact allocation before executing. Carry
ledger1806.2957189570038 used/1793.7042810429962 remaining; count audit and
verification time. No automatic retry, new seeds, physics or scientific grant.

Source-only tests must catch query decoding/leakage even with query role after
paths, altered query outcomes, missing training axes, invalid arm/sum, known
decomposition/selection flips, exact deletion counts, deterministic rule replay,
and conserved prior artifacts. Verify saved analysis by deterministic training-
only replay. Commit results separately and push, never merge main.

Parallel engineering may improve local Learning Lab install/session handling
and prepare separate matched continual-learning, rule and transfer protocols.
Authored fixtures/session restart tests are not measured continual-learning
evidence. Do not run simulator studies under this audit's allocation.

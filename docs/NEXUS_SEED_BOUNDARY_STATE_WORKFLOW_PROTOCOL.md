# Boundary evidence, conversation state and one workflow — development protocol

Base: reviewed tip `01a434b` of `cursor/seed-capability-milestone`.
Branch `cursor/seed-boundary-state-workflow`. Development only. Do not rescore
the closed capability-milestone grid. Do not edit
`src/nexus/seed/local_model_runtime.py`.

The last milestone accepted `>=` on an equality-only public suite, left
`fees` unselected after “use fees instead”, and could not say whether the
model produced no usable edit or the orchestrator discarded one.

## Changes before scoring

1. A boundary repair is accepted only when a teacher/requirement labels
   **below, equal and above**. Labels come from the explicit inclusive or
   exclusive request, not from candidate disagreement. Existing private
   assessments stay assessment-only.
2. “Use file … instead” updates the selected resource before any later
   answer. A selected-file topic change clears pending coding context.
   Last-tool / document answers name their source file.
3. Every local-model proposal records inference, raw excerpt, parse,
   validation and queue insertion. `usable_but_discarded` is distinct from
   `no_usable_edit`.
4. One development workflow (`py_width_three_point_dev`) is run, then a
   frozen pass on a fresh project (`py_height_three_point_fresh`). Stages:
   discovery → proposed edits → execution → failure feedback → revision →
   explanation. Structural validity stays separate from private-test pass.
5. Learned ranking is **not** re-run and not promoted. Inadequate
   distinguishing evidence was the bottleneck.

## Expected grid

2 boundary cells, 2 workflow cells, 4 language cells.

## Gates

No ranking or investigation promotion. Learning-to-learn unestablished.
Do not merge `main`.

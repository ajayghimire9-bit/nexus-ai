# E3.0 — bounded executable strategy generation

Explicitly authorized by the unified-learning task. Earlier no-Evolution-3
instructions remain history for their earlier tasks; this scope permits only
the bounded source-only prototype below. No scientific gate or grant changes.

`evolution2.generated_strategies` composes existing catalogue operators and
`planner_adapter.decide`. It preserves all twelve original variants, planner
and world-model code. No generated source, eval(), shells, LLM dependency,
new environment factory, second bandit/memory stack or arbitrary function.

The closed depth-one grammar contains342 canonical strategies:

- Twelve unchanged catalogue leaves.
- 264 ordered two-leaf switches: choose according to |observation[0]| crossing
  fixed0.25 or1.0. Gates use observations, not hidden task identifiers/physics.
- 66 unordered action-midrank blends. Score both existing operators at768
  imagined states each, convert to per-first-action midranks, sum ranks and
  choose the lowest-index maximum. Different horizon/reward scales are not
  added directly. A flat child uses its best candidate score per first action.

Switches use at most1536 imagined states; blends use at most1536 total.
Identical children collapse to a leaf; commutative blends canonicalize order.
Threshold/horizon variation alone is parameter search. State-dependent
operator selection and ranking composition are executable policy structures
outside a single fixed Variant, but structural novelty is not a performance
claim. Report actual action-vector novelty on registered source contexts.
If no new action vectors occur there, do not call those contexts behaviorally
novel even though a deterministic synthetic witness may distinguish the code.

`StrategyGenerator` reuses `AdaptiveProposer`'s six-weight normalized SGD.
Choose a favored leaf, inherit a complementary child from the best previously
observed parent when possible, and draw the composition/gate with a seeded
RNG. Bounded32-attempt deduplication rejects already-evaluated strategy IDs.
Parent/child definitions and all feedback updates enter the existing hash-chain
`Journal`. Active switches credit the active leaf; blends credit each child
equally. This coarse credit heuristic can fail. It does not learn gate or blend
parameters, discover arbitrary algorithms, or improve its own SGD rule.

Observed feedback can change later mutations; predicted quality is never fed
back as a reward. Random generation records but does not learn from scores.
Withheld feedback leaves proposal weights/parent unchanged. Shuffling uses a
permutation of already revealed training labels, then cyclic previously
revealed local labels. The latter is a lagged/reassigned-feedback ablation,
not independent random corruption of future query outcomes.

Two valid candidates are generated per free slot. Unified selection exploits
the ridge ranking on even-numbered free slots and explores the first candidate
on the others. This bounded composition reuses the existing memory and
evaluator contracts; it is not evidence of useful autonomous continual learning.
See the unified protocol for exact budgets, controls and separate A–E screens.

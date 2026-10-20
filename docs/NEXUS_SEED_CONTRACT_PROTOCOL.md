# Seed shared-state contract and capability separation — locked development

Starting point108af15 preserves the completed frozen action diagnostic and the
104-tested but UNRUN residual action-readout study. User now explicitly prioritizes
state/memory/value semantics. Do not execute the superseded readout protocol.
Reuse SeedRSSM, existing coherent trainer/factory/MPC, Session/Journal and finite
grammar. No generic parallel memory/learner/planning stack. Preserve all old
weights/results and the576-step diagnostic; only NEW scratch fits are authorized.

## Source-verified problems and corrections

GUI previously assimilated before and after an action, then again before its
next action; observe/speak also assimilated. Training fed within-query-batch
keys while evaluation used zero, and GUI could feed user-created keys. Value
was trained on remaining sampled-window returns from s_t but attached to the
predicted s_(t+1). Source code verifies these problems; their quantitative
contribution to past failure is not established.

New Belief contract: one posterior per integer observation time. Duplicate time
is a no-op only if encoded observation is identical. Blocked actions still
produce a new observed time. No hidden state crosses sampled sequence windows.
GUI read-only operations use a cloned/temporary belief; inspect/speak/observe
never commit time, h/z, world or evidence changes. Measured work counters may
change. Restore attaches cached sensors without assimilating history again.
Same Belief is used in aligned training, ranking, control and GUI.

Aligned world conditioning:32 initial SOURCE observation encodings, fixed before
optimization, saved with checkpoint. Same exact bank in every phase, source-only
and no learned parameter increase. Learned key/query retrieval feeds recurrent
h from this bank. User-taught prototypes/programs are still retrieved/audited
and can resolve concepts, but do not silently replace the trained world bank.
Legacy checkpoints remain loadable with empty inference bank. The old training
condition retains its historical within-batch memory to provide a comparator.

V3(s_t) is the discounted next-three task rewards under the recorded random
behavior. Attach its target to CURRENT observed posterior s_t, mask insufficient
truncated suffixes, and target terminal V3=0. Do not cross episodes. Pruning uses
r + .9*(1-p_done)*V3(s_next). It is a behavior-continuation estimate, not optimal
MPC value. Full H4 candidate scoring remains existing RandomShootingMPC.

Action flags mean attempts, not successful stored concepts. New source/control
reward equals GUI task reward (.2 distance reduction −.02 +1 on reaching goal),
without the old first-ask proxy. Actual human-label information gain remains a
separate delayed observed event, never an invented world-model reward.

## Experiment and baselines

Single executable config configs/seed_contract_study.json. Collect48 source
episodes max8 steps on seeds85110001–85110048, random behavior. Share identical
data across recipes/conditions/seeds. Train new legacy-contract and aligned_v1
models for120 Adam updates, batch8, lr .003, schedule5507, model seeds5511–5513,
both original trunk recipes (same parameter counts). Add untrained matched-init
models, not new trained replicas. This compares a BUNDLE of semantic fixes;
do not attribute any gain to only value, state caching or retrieval individually.

Register64 new boundary/interior states85210001–85210064. Exact nine-action
outcomes collected once and reused across all18 models. No oracle data enters
models or planner. Report reward-only regret, optimal rate, pairwise accuracy,
prediction error. Primary descriptive screen: aligned mean regret >=25% below
new legacy comparator in EACH recipe. Six aligned models are3 paired model
seeds per architecture, not six equal world-model replicas.

Control:8 paired resets85310001–85310008, max12 steps, each model with pruning
on/off, plus shared random and known-grid greedy references. Same candidate
RNG seed per episode/step across models. Pruned costs48 states; unpruned64,
so report different compute. No online weight update. Require aligned-minus-
legacy mean return>=.1 for BOTH recipes/pruning settings for the practical
control screen. Report untrained/random/greedy gaps and pruning-on-minus-off.
Paired t95% intervals across3 training seeds inside EACH recipe, df2; episodes
and states are not extra training replicas. Intervals are exploratory; no broad
success claim if intervals include0. No post-outcome hyperparameter selection.
GUI model fixed to tanh/aligned5511 before results regardless of performance.

## Separate capability audits

Perception: same held-out ranking states/actions, freeze each trained model;
pixels-only versus proprioception-only encoding, evaluating next non-goal sensor
dimensions [x,y,color3,shape3,size]. Both modalities contain these attributes.
Pixels do NOT contain goal coordinates or action flags, so do not claim a fair
pixel-only CONTROL comparison, or interpret this ablation as separately trained
vision competence. No extra real outcomes; encode/forward cost logged separately.

Language:24 registered phrases, four directions crossed with six templates:
"move o1 DIR", "move the o1 DIR", "please move o1 DIR", "push o1 SYNONYM",
"move o1 to the DIR", "shift o1 DIR". Labels are the corresponding typed Move.
No fitting or executing their actions. Existing parser is scored. The RSSM has
no instruction-to-program decoder, so report that neural language-understanding
comparison as unavailable rather than treating trace generation as understanding.
Templates are authored diagnostic inputs, not independent neural generalization.

Concepts:all37 known predicate tasks, same8 teaching examples sampled from18
distinct property combinations using seed85410001+i. Last6 of a disjoint test
subset score query labels. Neural top8 proposals vs symbolically shuffled first8
grammar candidates, each with max8 candidate checks×8 labels. Both choose the
first training-consistent candidate; abstention counts wrong on query. Actual
predicate checks and neural forwards reported, not called equal FLOPs. A full37
symbolic baseline is labeled larger-search-budget reference. Test labels cannot
choose programs. This is a known-grammar audit, NOT induction of new primitives
or genuinely withheld compositions. Shared authored label costs296, separately
from environment steps. Do not grow the concept language in this branch.

## Budget, integrity and stopping

Cap180seconds,7000 authored steps,300000 imagined planner/action transitions,
CPU only. Upper source384 + ranking576 + model control3456 + reference192 =4608
steps; unused cached opportunities charged only when executed. Up to12 trained
scratch fits (2 recipes×3 seeds×2 contracts),6 untrained snapshots. Retain partial
losses/raw rows if interrupted. Session carried1861.6321034559958used /
1738.3678965440042remaining; no reset due to date/branch/user-message changes.
Precommit all code/protocol/tests; exclusive claims/output and exact expected
grid, finite values, hashes, true reward accounting and frozen evaluation
required. Historical artifacts and checkpoint bytes must remain unchanged.
No repeats, old experiments, Gym, confirmation access, main merge or paid work.

## Deferred program-language growth

DreamCoder's learned program library and search-policy approach is a relevant
precedent ([original PLDI paper](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)).
NEXUS does not implement that system here. Typed composition search, new reusable
abstractions and genuinely withheld compositions require a separate protocol
after this loop is reliable; a37-label classifier result is not that evidence.

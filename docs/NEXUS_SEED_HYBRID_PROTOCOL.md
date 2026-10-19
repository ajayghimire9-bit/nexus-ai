# Seed hybrid architecture — bounded authored engineering pilot v1

Base053671c8497c80ad8a489ced8bb72ba68e45e9a6, branch codex/seed-hybrid-architecture.
This implements the user's seven-component architecture incrementally using the
existing Seed Session, E1 Journal, neural factory and meta-controller. No historical
world-model/control checkpoint, result, split or original comparison is reused.

## Working scope

Language perception: optional356-parameter bag-of-token MLP,17inputs,16tanh units,
4direction outputs. Existing build_mlp constructs its trunk; PyTorch/Adam trains
it offline on authored command labels. Fixed-shape JSON exports support lightweight
stdlib inference. Explicit local CLI path plus SHA256 enables it; ordinary Seed
does not import Torch or download a model. The exact parser remains authoritative.
Only eligible single-clause paraphrases enter the MLP; unknown syntax, negation,
multiple direction hints and low-margin outputs abstain. Scores are not confidence.

Working memory: a small recurrent **symbolic** state updated from existing journal
events, not a learned GRU. Last executed object can resolve it/that, with explicit
origin; scene/stop/teaching/definition events clear it. Existing JSON snapshots
restore it by replay, without granting optional CLI capabilities.

Concept induction: same finite version space, explicit evidence/corrections.
Reasoning: same typed executor plus domain-specific bounded BFS over authored
grid moves, max128expanded states, no hidden physics or new MPC framework.
Goal requests still require a unique referent and enforce primitive/action limits.

Questions: same disagreement chooser, random control, optional thin adapter using
existing EpsilonGreedyController statistics. Only an answered matching question
card can produce a computed version-space reduction reward. No client scalar
reward, held-out query, correction or mismatched card can update it. Controller
feedback/choices are journaled and checked on restore. Owner must opt in with
--seed-meta-questions. This is functional integration, not evidence of useful RL
or learning-to-learn. No neural concept learner or text generator is trained.
Response generation remains grounded templates and real executable traces.

## Locked neural pilot

Config: configs/seed_hybrid_architecture.json. Seeds101/102/103,120full-batch Adam
updates each,lr0.03,hidden16; no search. Four training templates ×two references
×eight direction words =64authored training labels, two held-out templates ×two
new references ×eight words =32evaluation labels. Vocabulary is authored; all
direction words occur in training. Templates/references are disjoint, not a
general language confirmation. No user sessions, scientific environments, closed
evaluations or previously failed teaching-comparison outcomes enter fitting.

Primary engineering screen: ≥95% held-out direction accuracy including abstentions
for **each** seed. Verify stdlib/PyTorch logits within1e−5. Report all outputs,
loss trajectories, exact parameter counts, hashes and failure/partial results.
Include a strong training-only hint-label lookup baseline; no claim that a neural
model is necessary merely because it fits these simple paraphrases.

Deployment candidate is seed101, fixed before evaluation, never the best held-out
seed. Enabling any model still requires explicit CLI hash opt-in. A passing screen
does not establish robust natural language or action safety beyond the sandbox.

One exclusive capture after protocol/tested implementation commit. Hard30s from
before Torch import through the pilot;360optimizer updates total,23040training
example presentations,96unique authored label rows, zero real scientific simulator
steps. No retries, larger model, extra epochs or retuning after seeing outcomes.
Keep partial results honestly. Standing grant carried ledger1845.6321034559958
used/1754.3678965440042remaining; debit actual execution and audit conservatively
afterward. Unit/browser fixture work is separately reported, not a scientific grant.

## Tests and provenance

Tests cover bounded interpretation, symbolic fallback, invalid/OOV/negated inputs,
zero weight changes during inference, hashes/nonfinite weight rejection, working
reference reset/replay, bounded goal search, and meta feedback isolation/replay.
Run old Seed/Lab source regressions. No old simulator or training suites.

The repository-refresh preservation manifest remains immutable. A versioned
code-evolution record explicitly lists intentional changes to core/lab/server/UI
and roadmap; original scientific artifacts/configurations/protocols stay frozen.
The checker must reject any unlisted or hash-mismatched change, not silently
rewrite history. All earlier research outcomes, E2.17/H17/F and main stay unchanged.

Later learned recurrent memory, neural-guided induction, policy improvement,
text generation and cross-domain learning require their own measured studies.

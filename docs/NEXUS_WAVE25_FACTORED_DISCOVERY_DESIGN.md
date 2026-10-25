# NEXUS Wave 25 — Factored Discovery & Self-Evolution: design (no outcomes)

Status: design only, 2026-10-25, branch `codex/wave25-factored-discovery-design` (from `d497ff0`).
No experiment has been run for this document. Paper characterisations (Bakermans et al. 2025;
Shirakami & Henderson 2026; Huang et al. 2025 "ALINE"; Wang, Dillig & Singh 2018 "ATLAS") follow the
owner's summaries; nothing here depends on details beyond those summaries.

## 0. What v4 actually says, and the one constraint this design keeps

v4 found that when every arm must certify exactly over the same small space, learning can only reorder
enumeration and choose probes (≈ 2% of work), and Tycho correctly refused every source procedure. Two
consequences shape everything below:

1. **Posteriors do not certify.** A particle posterior over hypotheses h = (M, C, B) can choose
   experiments and propose candidates, but `UNIQUE` still requires that every hypothesis in the declared
   space consistent with the evidence agrees on the query. Certification therefore stays with the exact
   ObsEGraph enumerator over the *factored* space (C × B), and the only sound way to make it cheaper is
   to **prune provably empty subtrees** (Interface C). Inference (Interfaces A, B) reduces *probes* and
   *proposal cost*; abstraction reduces *certification cost*. The two are billed separately.
2. **Learning must buy something an exact baseline cannot buy cheaply.** Every learned component has a
   named non-learned baseline at equal budget: exact EIG over enumerated probes (vs. ALINE-amortised
   proposals), discrete SMC with uniform rejuvenation (vs. latent gradient search), the v4 FD/Popper
   pruner (vs. learned abstract transformers).

## 1. Objects

**Values and slots.** A domain value is a multiset/sequence of *items* (list elements, records, nodes)
plus scalars. A **mechanism** m ∈ M is a typed operator with **slots**: `F[p]` (filter, slot p: item →
bool), `S[k, o]` (bounded selection: the k first items under total preorder o, stable by position,
output in o-order), `Sort[o]`, `Map[g]`, `Agg[r]`, … A **composition** C is a typed DAG (here: chain) of
mechanism instances. A **binding** B maps every slot to a *domain expression* from a domain-free
binding grammar 𝔅:

```
p ::= field(f) == c | field(f) op θ | ¬p | p ∧ p     (f ranges over observed field paths, c/θ over observed values)
o ::= position | by(field(f), asc|desc) | by(len(field(f)), ·)
k ::= small integer observed in outputs (|y|, |y| ± 1)
```

Field paths `f` are discovered from data (`common_keys`, nested keys, tuple positions), never named.
h = (C, B) with mechanisms drawn from M. Execution `exec(C, B, x)` is the white-box symbolic executor;
ObsEGraph classes are keyed by public outputs and keep one concrete (C, B) witness per distinct query
output (Y_q ⊆ Ŷ_q as in v4).

**Abstract domain 𝒜 (slot-relative).** Properties are defined relative to slots, not fields, so they
are domain-invariant by construction. For a composition C with bound slots, and input x:

| Property | Definition |
| --- | --- |
| `n(x)` | number of items |
| `V_s(x)` | items accepted by filter slot s (|V_s|, positions) |
| `T_s(x)` | items inside selection slot s's boundary (top-k under o_s) |
| `κ_{s,t}(x)` | cross-slot relation counts, e.g. `|¬V_s ∩ T_t|`, `|V_s \ T_t|` |
| `⊆`, `multiset=`, `order-preserved` | relations between input and output item multisets |
| learned atoms | φ-grammar predicates promoted by refinement (§2.3) |

## 2. The three hard interfaces

### 2.1 Interface A — a domain-invariant probe signature for an ALINE-style policy

ALINE needs fixed-size inputs and degrades under shift. NEXUS therefore never feeds raw values or field
schemas to the policy. The policy sees a **set of slot-relational tokens** computed by the exact
executor under each particle, and it outputs a distribution over **abstract probe constraints**, not over
concrete inputs.

*Particle set.* Π = {(h_i, w_i)}, h_i = (C_i, B_i), Σ w_i = 1.

*Token set for a candidate probe x* (computed exactly, charged):

```
tok(x) = { ( w_i,
             role(s), role(t),                     # slot roles from M's type signature: F, S, Sort, Map, ...
             κ^{(i)}_{s,t}(x)  (normalised by n(x)),  # cross-slot relational counts under B_i
             ⟦exec(h_i, x)⟧                         # output class id among particles (equality classes only)
           )  :  i ∈ Π,  (s, t) slot pairs in C_i }
```

Everything in a token is either a weight, a role symbol from a finite vocabulary, a normalised count, or
an *equality-class index* of outputs — no field names, no arity, no raw values. A permutation-invariant
set encoder (DeepSets / Set Transformer) gives a fixed-size embedding regardless of particle count,
composition length or record arity. Unknown arity only changes how many field paths 𝔅 enumerates, which
lives inside B_i and is invisible to the encoder.

*Flexible targeting.* Target ξ ⊆ {C, B, slot-specific B_s}. With deterministic hypotheses, the exact
targeted information is computable from particles:

```
I_ξ(x) = H(Y_x) − Σ_{θ_ξ} π(θ_ξ) H(Y_x | θ_ξ),
P(Y_x = y)        = Σ_i w_i 1[exec(h_i, x) = y],
P(Y_x = y | θ_ξ)  = Σ_{i: h_i|ξ = θ_ξ} w_i 1[exec(h_i, x) = y] / π(θ_ξ).
```

An optional attribution term prefers probes informative about ξ but not about the rest:
`score_ξ(x) = I_ξ(x) − λ · I_{¬ξ}(Y_x; θ_{¬ξ} | θ_ξ)`; with λ > 0 a failed prediction is attributable to
ξ (used by §4).

*Division of labour (the key to shift-robustness).* The amortised head **proposes** K abstract probe
constraints (e.g. "make `|¬V_F ∩ T_S| ≥ 1` and `|V_F \ T_S| ≥ 1`"); a **concretiser** turns each into
concrete inputs by minimal edits of observed inputs under the MAP binding (§3); the **exact** I_ξ above
scores them. Shift can only cost efficiency, never correctness or soundness. Shift is detected online:
calibration error `ε_cal = |Î_ξ − I_ξ|` averaged over proposals; if `ε_cal > τ_cal` the head is bypassed
for exact enumeration over a generic perturbation family (the v4 designed-probe baseline), and both paths
are billed.

*Training distribution.* The head is trained on synthetic episodes from the **source generative model**
with randomised field names, arity (1–6 fields), value ranges, distractor fields correlated with true
slot fields on public data, and both commuting and non-commuting mechanism pairs. Targets are the exact
I_ξ values (supervised amortisation) plus a terminal reward = −(probes + compute) to resolution (policy
head). Training compute is part of Discovery cost.

### 2.2 Interface B — nonparametric latents ↔ discrete (M, C, B) ↔ ObsEGraph

*Primary state is discrete.* SMC particles are concrete (C, B) tuples; every weight is an exact
likelihood from the symbolic executor (`ℓ(D | h) = Π_j 1[exec(h, x_j) = y_j]`, optionally with a noise
floor ε for noisy worlds). Latents never certify, never weight, never enter ObsEGraph.

*Latent proposal model.* A DP / stick-breaking mixture with components j = 1..J (J variable): component j
has an embedding e_j ∈ ℝ^d; a decoder gives `q(m_j, b_j | e_j)` over mechanisms × binding-grammar
productions; composition order comes from a relaxed permutation (Sinkhorn over component scores).
Inference-time gradient search maximises an ELBO under a **differentiable surrogate executor** (soft
filter `σ((value − θ)/τ)`, soft top-k via a sorting network, soft equality) — available only for
mechanisms with relaxations. Birth/death of components is the DP move (split/merge with
stick-breaking prior). Rounding: beam the decoder modes into ≤ B_round discrete tuples → exact execution
→ insertion into the particle set (with importance weights corrected by the proposal probability) and into
ObsEGraph.

*Hand-off rule (particle filter → gradient search).* After each observation:

```
ESS = 1 / Σ w_i²   (after reweighting)
Z   = Σ_i w_i^{prior} ℓ(D | h_i)                     # unnormalised evidence of the current particle cloud
if Z == 0 or ESS < η·N:
    run R rejuvenation moves (MCMC over (C, B): swap adjacent mechanisms, re-sample one slot binding,
                              insert/delete a mechanism)                        # cheap, discrete
    if still Z == 0 or ESS < η·N:
        if AbstractReach(M, D) == 1 and depth(C*) ≥ d_grad:  → gradient search in latent space
        elif AbstractReach(M, D) == 0:                       → §4 ΔM ∪ ΔA (no search helps)
        else:                                                → enumerate the factored space exactly
```

Gradient search is invoked only when discrete moves fail **and** the abstract layer says a solution exists
within M **and** the composition is deep enough that discrete enumeration is predicted to cost more
(predicted cost = Π_j |𝔅_slot_j| × |mechanism orders|, billed). In small worlds this rule will mostly
choose exact enumeration; the spike measures how often the gradient path is chosen at all before any GPU
work is built.

*GPU.* The existing `MetalGrantEnforcer` meters the llama-server process. Torch MPS gradient search needs
a new enforcer (allocated/driver memory via `torch.mps`, per-step wall, session MPS seconds) before any
M4 execution; until it exists and is approved, the surrogate runs on CPU (AGENTS.md: GPU requires an
enforcement backend).

### 2.3 Interface C — sound observational / guarded abstract transformers without SMT

Goal: prune a subtree rooted at a partial program π (prefix state σ = concrete values of π on the task
inputs, remaining depth r) **iff** no completion can reach the targets — with zero false certificates.

*Exact abstraction of the current state.* α(σ) is computed by evaluating 𝒜 on the concrete values of σ
(exact; no approximation at the root).

*Abstract transformers.* For each mechanism m and abstract value a, `T_m(a) ⊇ { α(m(v)) : α(v) = a }`
(over-approximation). Abstract reachability: `Reach_r(a) = a ∪ ⋃_m Reach_{r−1}(T_m(a))`; prune if
`α(targets) ∉ Reach_r(α(σ))` (checked per public pair; one failing pair suffices).

*Soundness ladder* (only tiers 1–2 may prune; tier 3 may only reorder):

| Tier | Where the transformer comes from | Soundness | Example |
| --- | --- | --- | --- |
| 1 Proved | Mechanisms are NEXUS's own white-box IR; transformers are derived by abstract interpretation of the IR in cardinality / multiset / order / interval domains | universal | `F`: |out| ≤ |in|, out ⊆ in, order kept; `S[k]`: |out| = min(k, |in|); `Sort`: multiset= |
| 2 Scope-verified | Opaque target tools (records/stdlib); a learned rule is checked exhaustively on a declared finite scope U (all values reachable within depth d from the task's inputs and observed probes, plus generated small values of the same shape) | sound for states in U; each use is **guarded** by a concrete membership check σ ∈ U and U's closure under the tool (checked at admission) | "tool `t` never increases the number of items" checked on U |
| 3 Empirical | Rules seen to hold on observed traces only | none | ordering heuristics |

Because certification is relative to the finite tuple of task inputs (public + query + probes), tier 2's
scope can be **task-local**: U = closure of the task's own inputs under the tool set up to the remaining
depth. A rule verified on U is exact for this task's search. That is what makes "no SMT" sound: the
quantifier ranges over a finite, enumerated set.

*Learning from spurious candidates (ATLAS analogue).* A candidate π is *spurious* when it passes the
abstract check but fails concretely. Observational interpolation: along π's concrete trace v_0 … v_r,
find the earliest step j and a φ-grammar atom q such that q(v_j) holds while q is false on every
abstract-consistent value that leads to the targets (computed on the task-local U). Promote q into 𝒜
and derive/verify transformers for it (tier 1 if q is expressible in the IR domains, else tier 2). Admit
q only via Tycho: `saving_per_task × H − (interpolation + verification + abstract-evaluation cost) > 0`
on validation tasks.

*Why this addresses the 4.3%.* v4's Popper only detected collapse (functional-dependency violation).
Cardinality/multiset/order transformers prune whole families that FD cannot see: e.g. target lists of
length 3, state of length 2, remaining mechanisms all non-increasing in length ⇒ prune, no execution.
Verdict preservation is tested exactly as v4 G4 (with vs without pruning, identical verdicts and witness
sets); the abstract-evaluation cost is billed against the evaluations saved.

## 3. The non-commutativity diagnostic rule and autonomous binding

### 3.1 Data structure

```python
@dataclass(frozen=True)
class RelationalDiagnosticRule:
    rule_id: str
    pattern: tuple[MechanismRole, MechanismRole]      # e.g. (F[p], S[k, o]) — slot-level, no fields
    competing: tuple[Composition, Composition]        # (F∘S, S∘F) as slot-level skeletons
    disagreement: AbstractFormula                      # Φ over slot-relative properties (𝒜)
    theorem: str                                       # Φ(x) ⇔ exec(c1, x) ≠ exec(c2, x)  (or ⇒)
    observable: AbstractFormula                        # how the difference shows in the output (e.g. |y|)
    feasibility: AbstractFormula                       # constraints a concretisation must satisfy
    concretiser: tuple[EditSchema, ...]                # minimal-edit recipes over bound slots
    soundness_tier: int                                # 1 proved / 2 scope-verified / 3 empirical
    provenance: tuple[str, ...]                        # source traces it was mined from
    stats: RuleStats                                   # uses, resolutions, mean probes saved, cost
    tycho: TychoRecord                                 # admission: net benefit, validation tasks, cost
```

### 3.2 The F/S law, stated exactly (and slightly stronger than the brief)

Let V = V_F(x) (items accepted by p), T = T_S(x) (first k under o), c1 = F∘S (select then filter),
c2 = S∘F (filter then select). Every item of V ∩ T is within the top k of V (fewer competitors), so
V ∩ T ⊆ top_k(V), and both outputs are in o-order. Hence

```
c1(x) ≠ c2(x)   ⇔   |V ∩ T| < min(k, |V|)   ⇔   (∃ i ∈ T: ¬p(i))  ∧  (∃ j ∉ T: p(j)),
observable:      |c1(x)| < |c2(x)|.
```

The brief's "ensure at least k valid items" is sufficient but not necessary; the minimal feasibility
constraint is one valid item outside the boundary. World 1 check: x = [−1, 5, 4], k = 2, o = position:
T = {−1, 5}, −1 ∈ T is invalid, 4 ∉ T is valid ⇒ c1 = [5], c2 = [5, 4]. The theorem is tier 1 (derived
from the IR semantics of F and S), and its observable is a cardinality, which is domain-invariant.

*How it is learned, not gifted.* In source worlds both orders occur with equal prior, and commuting pairs
(F∘F', Sort∘F, Map∘F for item-wise maps) occur as controls. A rule candidate arises when two particles
that differ only by swapping adjacent mechanisms survive the public data; the learner searches 𝒜 for a
formula Φ such that abstract transformers prove disagreement (tier 1) and concrete source probes
satisfying Φ resolve the pair. Pairs whose swapped compositions are provably equal (the abstract
transformers show identical outputs) yield no rule. The rule is stored at the slot level. A curriculum
requirement for honesty: source must contain S with more than one order type (position and by-value).
Otherwise "top-k by score" in World 2 is not a rebinding of o but a missing mechanism (§4, ΔM).

### 3.3 Walk-through: unfamiliar records, zero field labels

Hidden truth (unknown to NEXUS): items are records with fields `{u: bool, w: float, z: str}` (names
randomised per seed). Task c2' = S[k=2, o=by(w, desc)] ∘ F[p = (u == True)] ("remove inactive, then the 2
highest-scoring"). The public examples are drawn from the ordinary sampler.

1. **Entry (no labels).** Field paths are discovered from the data: `u` (bool), `w` (float), `z` (str),
   plus a distractor `q` (int) correlated with `w` on the public inputs. 𝔅 is instantiated for p (`u==c`,
   `q ≥ θ`, `w ≥ θ`, `z == c`, …), o (`position`, `by(w,±)`, `by(q,±)`, `by(len(z),±)`) and k ∈ {1, 2, 3}.
   Unlabeled tool probes are not needed: the mechanisms are NEXUS's own.
2. **Structural evidence prunes compositions abstractly.** Every public output is a sub-multiset of its
   input in o-order ⇒ only selection/filter/sort mechanisms are abstractly reachable (tier 1 transformers;
   `Map` cannot produce ⊆ outputs). Output sizes {2, 2, 1} ⇒ k ∈ {2} under S (k = 1 or 3 contradicts
   `|y| = min(k, |V|)` on some pair). Exact SMC over (C, B) with these constraints leaves particles,
   e.g. {c1', c2'} × p ∈ {u==True, q ≥ 4} × o ∈ {by(w, desc), by(q, desc)}.
3. **ξ = B (binding-targeted).** The binding posterior entropy H(B) is high and the composition
   posterior is irrelevant to it if the probe keeps Φ false under every particle (no inactive item inside
   any particle's boundary). The policy proposes the abstract constraint "decorrelate the competing p
   candidates and the competing o candidates while keeping Φ false". The concretiser edits a public
   record set: one record gets u = True, q small, w large; another gets u = False, q large, w small
   (values copied from observed ranges). Exact `I_B(x) > 0`, `I_C(x) = 0` ⇒ attributable. The oracle's
   answer eliminates `q ≥ 4` and `by(q, desc)`: H(B) → 0, binding `inactive ↦ ¬(u == True)`,
   `score ↦ by(w, desc)`, `2 ↦ k`.
4. **ξ = C (composition-targeted) with the transferred rule.** Particles {c1', c2'} under the MAP binding
   match the rule's `competing` pattern. Instantiate Φ under B: ∃ record with u = False inside the top-2
   by w, and ∃ record with u = True outside it. The concretiser takes a public input with ≥ 3 records,
   sets u = False on its highest-w record, and ensures some u = True record ranks third. The exact check
   gives I_C(x) = 1 bit (|c1'(x)| = 1 vs |c2'(x)| = 2). One oracle call resolves C.
5. **Certification.** ObsEGraph enumerates the full declared (C × B) space with tier-1/2 pruning on
   public + probe pairs. `UNIQUE` is issued only if every surviving hypothesis agrees on the query. If the
   binding posterior collapsed onto a wrong but observationally equivalent binding, the certificate is
   still sound because certification enumerates bindings rather than trusting the posterior.
6. **Robustness.** If step 3 was skipped and the binding was wrong, the instantiated Φ might not separate
   the true pair; this is caught before spending the oracle call, because the exact I_C(x) under the full
   posterior (which still mixes bindings) is < τ. The policy then returns to ξ = B.

What transfers is the slot-level rule (Φ, observable, concretiser, tier) plus the probe policy's
experience with ξ-targeting. Field identities never transfer.

## 4. The 3-way self-evolution decision

A **failure** is: after observation D, the exact particle evidence Z = 0 or ESS < ηN persists after R
discrete rejuvenation moves. Define:

```
R_M      = AbstractReach(M, D) ∈ {0, 1}
           1 iff ∃ slot-level skeleton C over M (depth ≤ D_max) with ∀ (x, y) ∈ D:
           α(y) ∈ Reach(C, α(x)), with slots left SYMBOLIC (binding-abstract transformers)
𝒞_feas   = { C : skeleton abstractly consistent }                       # tier-1/2 over-approximation
Bfeas(C) = 1 iff ∃ B ∈ 𝔅: exec(C, B) ⊨ D                                 # exact, within the binding grammar
Z_C^rel  = evidence after relaxing C only: enumerate 𝒞_feas with each particle's B fixed (exact)
Z_B^rel  = evidence after relaxing B only: keep each particle's C, enumerate 𝔅 (exact)
H_B      = binding-posterior entropy just before the failure
a_last   = target ξ of the probe whose outcome caused the collapse (attribution from §2.1)
core(C)  = minimal set of slots whose concrete bindings must be freed for C to become abstractly consistent
ρ_spur   = fraction of abstractly-consistent candidates that failed concretely in this episode
```

**Decision (tests run in increasing cost order; each test billed):**

```
1. if R_M == 0:                               → ΔM ∪ ΔA   (sound: no composition of known mechanisms can
                                                            realise the abstract transition, even with
                                                            free bindings; abstraction is an
                                                            over-approximation, so this is a proof)
       sub-route: the unreachable abstract step (minimal failing transition α(v) ↛ α(v')) is the spec of
       the missing mechanism; synthesise it in the IR (bounded search), admit via Tycho
2. elif Z_C^rel > 0:                          → ΔC  (recombine; M and B held fixed)
3. elif ∃ C ∈ 𝒞_feas: Bfeas(C) == 0 and core(C) ≠ ∅:
                                              → ΔB on the slots in core(C)  (extend 𝔅 for those slots:
                                                 derived fields, conjunctions, len(·), nested paths)
4. elif ρ_spur > ρ*:                          → ΔA  (abstraction too coarse for pruning: ATLAS-style
                                                 observational interpolation, §2.3)
5. else:                                      → enumerate the factored space exactly (no evolution);
                                                 record as an unexplained failure
```

Priors over causes sharpen the order when budgets are tight:
`P(ΔC | a_last = C) > P(ΔB | a_last = C)`, high `H_B` ⇒ ΔB first, while `Z_B^rel > 0` with `Z_C^rel = 0` is
direct evidence for ΔB. The decision is taken by expected net value,
`argmax_op P(op resolves | diagnostics) · V − Cost(op)`, with P estimated from source episodes and the
order above as the fallback. Every mode's output must pass ObsEGraph verification and Tycho admission
before it becomes reusable.

Soundness of the routing claims: step 1 is a proof (over-approximate reachability); step 2 is a
constructive witness (exact execution); step 3 is a proof that no binding in the current grammar works
for that skeleton, plus a localisation (`core`). Only step 4 is heuristic, and it changes efficiency,
not correctness.

## 5. Curriculum and the minimal falsifiable spike

### 5.1 Curriculum (non-rigged)

- **Source** (lists of ints, strings): generator over M = {F, S[k, o ∈ {position, by-value asc/desc}],
  Sort, Map, Agg} with random bindings from the φ grammar. Both orders of every pair occur with equal
  prior. Commuting pairs are negative controls. Public examples come from the ordinary sampler; nothing
  is selected for being diagnostic.
- **Targets** (two): records (randomised field names, 2–6 fields, distractor fields correlated on public
  data) and attributed graphs (node records + edges; selection by attribute, filtering by attribute or
  degree).
- **Control strata in every target stream** (fixed proportions, declared in advance):
  1. commuting compositions (the rule must not fire; false-fire rate reported);
  2. non-commuting F/S pairs (the rule should fire);
  3. **ΔB tasks**: the order key is a derived quantity outside the initial 𝔅 (e.g. `len(z)`, `w1 + w2`);
  4. **ΔM tasks**: a mechanism missing from M is required (e.g. dedup-by-field), checked by `R_M = 0`
     before any search;
  5. **ΔC tasks**: known mechanisms in a composition order unseen in the source prior;
  6. passive versions of 2 (no oracle: the correct verdict is AMBIGUOUS, never a fabricated answer).
- Ground-truth cause labels exist only in the generator. The router never sees them; they are used only
  for scoring.

### 5.2 Spike (dev seeds only, before any lock; each part has a kill criterion)

| Part | Question | Baseline at equal budget | Pass (dev) | Kill |
| --- | --- | --- | --- | --- |
| S1 Interface C | Do tier-1/2 abstract transformers + observational interpolation cut certification work with identical verdicts? | v4 exact certifier + Popper FD | ≥ 30% fewer candidate evaluations, net of abstract-evaluation cost, 100% identical verdicts and witness sets | < 15% net, or any verdict change |
| S2 Rule transfer | Does the mined F/S rule, rebound in records, resolve compositions with fewer oracle calls? | (a) v4 designed probes (generic perturbations + exact disagreement); (b) exact-EIG enumeration over the same perturbation family; (c) random | mean probes to UNIQUE lower than (a) and (b) on stratum 2; 0 false fires on stratum 1; Tycho net > 0 including rule mining amortised over the declared horizon | no probe reduction vs (b) |
| S3 ξ-targeting | Does targeted acquisition (ξ = B then ξ = C) beat untargeted EIG on joint (C, B) at equal probes? | untargeted exact EIG over (C, B) | fewer probes to binding + composition resolution; attribution accuracy of failures ≥ 0.8 | no difference |
| S4 Router | Does §4 route ΔC / ΔB / ΔM failures correctly? | always-recombine; always-enumerate | per-class routing accuracy ≥ 0.8 (confusion matrix on strata 3–5); each mode repairs ≥ 50% of its routed failures; 0 false certificates | any class < 0.5 |
| S5 Amortisation (only if S2–S3 pass) | Does an ALINE-style amortised head beat exact-EIG enumeration on **net** cost under field-name/arity shift? | exact-EIG enumeration (the head's own supervision target) | lower total cost (training amortised) at equal probe counts; calibration fallback rate reported | head never pays back its training |
| S6 Latent search (only if the S1–S4 traces show ESS collapse with `R_M = 1` on ≥ 10% of tasks) | Does DP-latent gradient search find consistent (C, B) cheaper than exact enumeration at depth ≥ d_grad? | exact enumeration; discrete rejuvenation | lower cost per consistent hypothesis found; requires an approved torch-MPS enforcer, else CPU | never invoked, or never cheaper |

Ordering logic: S1 and S2 test whether the factored representation pays at all, with no neural
components. If they fail, the learned heads (S5, S6) cannot rescue the result, because they only
accelerate what S1–S3 measure exactly. All spike runs are ledgered against the standing grant (dev
seeds, ≤ 900 s each).

### 5.3 Tycho ledger for the spike (every term billed)

`Discovery` = source generation + synthesis traces + rule mining + transformer derivation + head training;
`Binding` = 𝔅 instantiation + SMC reweighting/rejuvenation; `Probing` = oracle calls (fixed price) + exact
I_ξ evaluations + concretiser search; `Validation` = Tycho admission runs; `Verification` = ObsEGraph
enumeration + abstract evaluation + scope checks for tier-2 rules. `Downstream saved` is always measured
against a named exact baseline on the same tasks, never against a weakened one.

## 6. Risks stated in advance

- On small authored worlds the exact baselines (enumeration + exact EIG) may already be near-optimal,
  leaving the amortised and latent components with nothing to buy. S5 and S6 are gated for this reason.
- The binding grammar 𝔅 is a declared prior. ΔB extends it, and every extension enlarges the
  certification space; S1 must show that pruning keeps pace.
- Tier-2 scope verification is only as strong as the declared scope. Pruning outside the scope is
  disabled, not assumed.
- Ground-truth cause strata are generator artefacts. Routing accuracy on them does not establish
  open-world self-diagnosis.

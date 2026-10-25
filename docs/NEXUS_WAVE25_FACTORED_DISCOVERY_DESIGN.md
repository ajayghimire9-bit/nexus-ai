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

## 7. Spike results: S1 and S2 (dev only, 2026-10-25)

Code: `src/nexus/wave25_factored.py`, `scripts/spike_wave25.py`, `tests/test_wave25_spike.py`
(6 tests: exhaustive no-false-prune check of every abstract rule, verdict preservation, the hand-checked F/S
law, the rule learner, the rule probe on a record task with randomised field names, edit-space order).
Development happened on dev seeds 1–3. The code was frozen at `33ab762`, then run once, unchanged, on
dev seeds 4–6, which are the numbers below (artifact `artifacts/wave25_spike_s1_s2_dev.json`, sha256
`3bb10f18a4e47c863d2a48593f152477750756c97ae86feb75d1ee4a54719a64`). This is exploration evidence, not a
locked evaluation.

What was built:
* Mechanisms F, S, Sort, Map, Agg as white-box slot operators, with a binding grammar instantiated
  from each task's own unlabeled inputs. Record field names are randomised per seed, and a distractor
  field is correlated with the score field.
* Three tier-1 abstract rules (length, distinct-count, provenance / Map-closure), plugged into the v4
  ObsEGraph certifier through a new sound pruning hook.
* The κ slot-relative features, a conjunction learner over them, and an exhaustive source-scope check.
* A rule concretiser over field-value edits.
* Four baselines: v4 designed probes, exact-EIG over v4 perturbations, exact-EIG over the same edit
  space, and random probes.

**S1 — PASS (mechanism), Tycho negative at the declared horizon.** Over 180 tasks, certification work
including the abstract checks fell from 136,712 to 56,793 (−58%) on int lists and from 126,116 to 53,939
(−57%) on records. Candidate evaluations fell by 74% and 70%. Verdicts and witness sets were identical
on 180/180 tasks (seeds 1–3: −43% and −45%). Measuring the benefit on 20 validation tasks cost 597,809
units, against a saving of 845 units per task. At the 100-task horizon the projected net is therefore
−513k, and break-even is about 707 downstream tasks. Tycho admitted only `length`, on one seed of three.
Because these rules are proved (tier 1), validation is needed only to estimate benefit, not for
soundness. A cheaper benefit estimator is the obvious next lever, but it has not been tested.

**S2 — KILL criterion met.**
* The learner recovered exactly the F/S law, `(|K_s∖K_t| ≥ 1) ∧ (|K_t∖K_s| ≥ 1)`, from source int-list
  traces. It held with 0 violations on all 2,046 scope cases, and produced no rule for the commuting
  pairs (F,F) and (F,Sort).
* The rule transferred to records without any field mapping and fired 12 times.
* On the F/S composition-ambiguous stratum (9 tasks), it needed 12 probes against 11 for each of the
  two exact-EIG baselines and 12 for v4 designed probes. Work was 111k against 104–110k.
* On the other ambiguous record tasks (111): rule 151 probes, eig-edit 147, eig-perturb 122, v4 145
  (2 unsolved), random 218 (35 unsolved).
* Mining cost 637k units, so the projected net is −719k.
* Zero false certificates in every arm.

The reason it failed: in this world the exact EIG over generic perturbations already finds the
separating probe in one shot, so a rule can only save design cost, and with 2–4 hypotheses that cost is
small. Most ambiguity in the record world is binding ambiguity, not composition ambiguity: the F/S
stratum is 8% of active tasks.

Consequences for the plan:
1. Interface C (tier-1 abstract pruning) is the first factored component to pay on this benchmark
   family. It should be carried into the next locked suite as the certifier's default once Tycho's
   benefit estimate is made cheaper, and that estimator should be tested on dev first.
2. The non-commutativity rule is learnable and transferable but does not pay where exact EIG over cheap
   perturbations is available. It can only matter when probes are expensive or hypotheses are many.
   S3 (ξ-targeting over bindings) addresses the dominant binding ambiguity and is the next spike.
   S5 and S6 stay gated, since S2 shows no headroom for an amortised head here.

## 8. S1-Auto + S3 results (dev only, 2026-10-25)

Code: `src/nexus/wave25_contracts.py`, `src/nexus/wave25_s3.py`, `scripts/spike_wave25_s3.py`,
`tests/test_wave25_s3.py` (12 wave25 tests pass). Developed on dev seeds 1–3. Code and criteria were
frozen at `5e1c9a8`, then run once, unchanged, on dev seeds 4–6 with a full deterministic replay (digest
`fdff91b4…73c7` both times). Artifact: `artifacts/wave25_spike_s1auto_s3_dev.json`, sha256
`1ad78a174e5eadef5f917cb62425e5492dedb13a7be7f44db19913742a086ec6`. Caveat: seeds 4–6 were already
looked at in S1/S2 (with different task-generator salts), so this is a frozen-code dev check, not untouched
evaluation data.

### S1-Auto — mechanism passes; strict admission criterion FAILS on 1 of 3 seeds

* **Learner.** Role structural classes were verified on declared universes: F, S sub-multiset; Sort
  permutation; Map item-wise with `out[i] = g(in[i])` for its own bound g; Agg to-scalar; every role
  rejects scalars. From the six-property basis it proved 30 contracts and refuted the rest.
  * Distractors were filtered: `first_sign` was refuted everywhere, and `parity` was refuted for F/S, so
    it is unusable for pruning.
  * Provenance for Map was derived as `image_subset`, which recovers the hand-wired S1 Map closure.
  * Learning cost: 32.7k units, one-time.
* **Effect (seeds 4–6).** Certification work fell 58% on int lists (136,712 → 57,883) and 47% on records
  (126,116 → 66,395), net of check cost, with 180/180 verdicts identical. On seed 5 nothing was admitted,
  so these pooled figures include that seed at 0%.
* **Cheap Tycho.**
  * The overhead was 47–72k per seed (12-task stratified micro-sample twin plus learning, all billed),
    against ~600k in S1.
  * Seeds 4 and 6 admitted contracts (net +33k / +54k, break-even 68 / 57 tasks).
  * Seed 5's micro-sample happened to save only 107 units per task (break-even 439), so it admitted
    nothing.
  * The twin-free estimator's leave-one-out error is 0.42–2.7× the total saving: still not reliable
    enough to replace the twin.

### S3 — PASS (all predeclared criteria); kill criterion not met

180 active tasks (90 int lists, 90 records with randomised field names and a correlated distractor), all
arms on the S1-Auto certifier, shared stop rule (stop when the certificate is UNIQUE), 3-probe budget:

| Arm | Solved | Probes | Work | False certs |
| --- | --- | --- | --- | --- |
| **s3** (answer-directed I(Y_q;Y_x\|H), factored + standard candidates) | **180** | **180** | **1,160,444** | 0 |
| flat_eig (I(H;Y_x), standard perturbations) | 180 | 196 | 1,190,718 | 0 |
| flat_eig_union (I(H;Y_x), same candidates as s3) | 180 | 199 | 1,458,703 | 0 |
| b_first (I(B;Y_x) then I(C;Y_x), same candidates) | 180 | 198 | 1,453,229 | 0 |
| v4 designed probes | 179 | 206 | 1,241,898 | 0 |
| random | 124 | 390 | 2,187,178 | 0 |
| flat_eig, no contracts (reference) | 180 | 196 | 1,542,101 | 0 |

* By world: s3 used 90 + 90 probes, flat EIG 93 + 103, v4 92 + 114. The gain sits mostly on records,
  where the correlated distractor lives.
* **The answer objective is what helps, not the factored candidates alone.** The same candidates under
  the flat objective (flat_eig_union) were worse than flat EIG over standard perturbations. Combined with
  the answer objective, they gave the best result.
* **Staging.** The hard-coded bindings-first control never reached its composition stage: 198/198 of its
  probes were binding-stage. Raw binding entropy never reaches zero because observationally equivalent
  thresholds remain, so "resolve B first" spends probes on binding distinctions that don't matter. s3
  avoided this without any staging rule.
* **Answer-sufficient stopping.** 104/180 s3 tasks ended UNIQUE while (C, B) ambiguity remained; 76 of
  those still had composition ambiguity. 144 tasks started ambiguous in both B and C; in 68 of them one
  probe resolved both the composition and the answer.
* **Tycho.** Net vs the best other arm (flat EIG) is +16.8k at the 100-task horizon. Fully loaded, s3 with
  S1-Auto (overhead included) against flat EIG without contracts is +149k.

### What this does and does not establish

On this dev benchmark family:
* An answer-directed objective over an exactly enumerated factored hypothesis set gives one probe per
  task and the lowest total work, with no hard-coded stage order.
* Automatically acquired, verified operator contracts reproduce the hand-written pruning at about
  one-eighth of the old admission cost.

Not established:
* Robust admission on every seed: the micro-sample variance is the weak point.
* A twin-free benefit estimator.
* Any result on untouched data: seeds 4–6 are dev, and the next locked suite needs fresh seeds.

The record world is still small: 2–4 hypotheses' worth of answer clusters per task.

**Next:**
1. Lock a confirmation suite on fresh seeds containing the S1-Auto certifier plus the s3 controller.
2. Reduce the variance of Tycho's micro-sample before that lock (on dev): for example, a larger
   stratified sample, with its cost still billed.
3. Keep S5/S6 gated: s3 already reaches one probe per task here, which leaves no headroom for an
   amortised probe head on this family.

## 9. Locked confirmation protocol — answer-equivalence version spaces, dual-ledger vault, reasoning procedure

Locked before any seed 501–505 outcome. Code: `src/nexus/wave25_vault.py` (+ instrumentation in
`wave25_contracts.py`, `wave25_s3.py`, `wave24_v4_core.py`), tests `tests/test_wave25_vault.py`. Run once:
`python3 scripts/confirm_wave25_vault.py --seeds 501 502 503 504 505 --replay --out
artifacts/wave25_vault_confirmation.json` (the script refuses to overwrite).

**Episodes.** Per seed and world (int lists; records with randomised field names and a correlated
distractor), 30 multi-query episodes. Each episode is one latent teacher with public pairs, a first query
q1 selected so the exact certificate on the public pairs is AMBIGUOUS, and a second query q2 sampled
from the world. The declared space is fixed from the public inputs + q1. The oracle (teacher, 20 units
per call, never on a query) allows 3 probes per query. Episodes from both worlds are interleaved in a
seeded order, so the reasoning procedure evolves across worlds.

**Arms.**
1. `full`: S3 controller over the persistent version space; dual-ledger vault with online lower-bound
   utility gating per context (no batch twin); ReasoningProcedure (contextual activation, two-tier
   generator scheduling, soft op-order prior) with the sound early-ambiguity stop.
2. `s3_batch`: the previous wave25 S3 with static batch-twin admission.
3. `flat_eig`.
4. `b_first`.
5. `v4`.

Arms 2–5 use the batch-admitted certifier. Every arm keeps its own observations from q1 to q2. A
`full_no_reuse` counterfactual (q2 from public pairs only, on a frozen copy of the procedure) is reported
and not counted in any total.

**Fully loaded.** Total episode work, plus per seed the one-time contract learning (full) or learning +
batch twin (others). Net at horizon 100 = per-episode work difference × 100 − overhead difference.

**Gates.**
* C1: 0 false certificates in every arm, both queries.
* C2: the replay digest is identical.
* C3: full solved ≥ every arm, AND full probes ≤ s3_batch's AND < flat_eig, b_first and v4.
* C4: net benefit of full vs s3_batch at horizon 100 > 0.
* C5: full q2 probes < full_no_reuse q2 probes, with 0 false certificates on q2.
* C6: on every seed, the vault keeps every PROVED_SOUND contract, and the credited lower-bound net
  utility of the full arm's active checks is ≥ 0.

**Dev evidence (seeds 1–3; 180 episodes, 360 queries).**
* Probes: full 199, s3_batch 201, flat_eig 207, b_first 208, v4 233 (v4 left 1 unsolved).
* Work: full 1.135M, s3_batch 1.506M, flat_eig 1.420M.
* Net vs s3_batch +245k.
* q2 probes: full 19 vs 101 without reuse.
* 0 false certificates.

Declared risk: answer-directed q1 probing leaves more structure unresolved, so flat_eig and b_first pay
fewer q2 probes (11 and 6) than full (19). Full's margin on total probes is small (199 vs 201 for
s3_batch).

## 10. Confirmation result (seeds 501–505, frozen code `6e98f0b`) — 5 / 6 gates

Single run plus replay. The digest `53979b15…8167` was identical on both passes. Artifact:
`artifacts/wave25_vault_confirmation.json`, sha256
`1cdd80b1ad599ee69e3b3a8d079dbbb551c955af5e68b1a0b79591277d4a1443`. 300 episodes (150 int lists, 150
records), 600 queries.

| Arm | Solved / 600 | Probes (q1 + q2) | Work | Overhead | Fully loaded |
| --- | --- | --- | --- | --- | --- |
| **full** (S3 + vault + ReasoningProcedure) | 600 | 347 (300 + 47) | **1,999,293** | 163,285 | **2,162,578** |
| s3_batch (static batch-twin admission) | 600 | **346** (300 + 46) | 2,648,293 | 432,950 | 3,081,243 |
| flat_eig | 600 | 368 (335 + 33) | 2,534,285 | 432,950 | 2,967,235 |
| b_first | 600 | 347 (330 + 17) | 2,932,619 | 432,950 | 3,365,569 |
| v4 | 597 | 397 (355 + 42) | 2,723,409 | 432,950 | 3,156,359 |
| full_no_reuse (counterfactual, not in totals) | 600 | 477 (300 + 177) | 2,102,095 | — | — |

| Gate | Result |
| --- | --- |
| C1 zero false certificates (all arms, both queries) | **PASS** (0) |
| C2 deterministic replay | **PASS** |
| C3 full solved ≥ all AND probes ≤ s3_batch AND < flat_eig, b_first, v4 | **FAIL**: 347 > 346 (s3_batch) and 347 = 347 (b_first); solved 600 = best; fewer probes than flat_eig (368) and v4 (397) |
| C4 net vs s3_batch at H = 100 > 0 | **PASS** (+270,266) |
| C5 q2 probes with reuse < without, 0 false on q2 | **PASS** (47 vs 177; 253/300 q2 answered with 0 probes) |
| C6 vault keeps every PROVED_SOUND contract; lower-bound net utility ≥ 0 per seed | **PASS** (30 PROVED_SOUND kept on every seed; credited net +152k to +185k per seed) |

Contract activation rates in the full arm, over all certifications: kind 0.84–0.99, provenance 0.82–0.96,
max_atom 0.48–0.88, length 0.30–0.46, distinct_count 0.22–0.23, parity / first_sign 0 (never sound).
Batch admission admitted contracts on all five seeds here, so the earlier seed-5 failure did not recur.
The vault's advantage over batch admission is therefore cost (163k vs 433k overhead, and lower
certification work), not rescued seeds.

**Reading.**
* The upgrade is a large work win: 25% less operating work than s3_batch and 30% less fully loaded.
  That comes from no batch twin, contextual gating of unprofitable checks, and the soft order with the
  sound early-ambiguity stop.
* Version-space reuse is clearly real: 130 fewer q2 probes.
* It does **not** reduce probes relative to s3_batch or bindings-first, which C3 required. The declared
  risk materialised: answer-directed q1 probing leaves structure unresolved, which q2 then pays for.
  Bindings-first spends more on q1 (330) and almost nothing on q2 (17).
* Over two queries, answer-myopic and structure-resolving policies tie on probes. The answer-directed
  objective is only optimal per query.

**Next experiment (one):** make probing anticipate follow-up queries. Score probes by
I(Y_q ; Y_x | V_t) plus λ times the expected information on a sample of future queries from the world's
input distribution, with λ learned on dev from the observed follow-up rate. Test on fresh seeds whether it
beats both answer-myopic and bindings-first on total probes over a query sequence, without giving up the
work advantage.

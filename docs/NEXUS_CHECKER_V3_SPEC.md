# NEXUS Checker v3: specification (written before implementation)

**Authorisation.** Owner brief of 2026-10-26: "implement … Checker v3 (`src/nexus/checker_kernel_v3.py`) around
bottom-up shared computation and independently verified rewrite proofs". This is the RULE 2 owner approval for a
new, separately versioned checker.

**Unchanged.** Checker v1 (`5082402f…`) and v2 (`6ba0a268…`; the owner's brief says `b1d6c5d1…`, but no such pin
exists) are untouched.

**Independence.** v3 uses the standard library only and imports nothing from NEXUS. Its interpreter is written
anew, so it shares no code with the prover (which uses v2's interpreter) or with v2. Its **value semantics are
v2's contract** (types, bounds, op meanings, ERROR rules), so that verdicts can be compared. Where the v2 spec is
silent, v2's behaviour was read and re-implemented, and this is disclosed. Agreement with v2 is regression
evidence; it is not a proof of correctness.

## 1. Values, ops, evidence

* **Same as v2 §1–§4:** types and bounds, every v2 op including `seq`, chains of ≤ 4 ops, and ERROR semantics
  (ERROR is absorbing along a chain, never fits a public pair, and is a distinct query answer).
* **Evidence:** `checker_version: 3`; the other fields are as in v2.
* **v2 lemmas:** a non-empty `lemmas` field is refused with `ABSTAIN(v2_lemmas_not_accepted)`. v3 never relies on
  lemmas, and its pruning comes from shared computation and from `proofs` (§3).
* **Step bound:** one chain application has ≤ 100,000 steps. Each op charges `1 + size(input)`, where size is the
  list or string length, grid cells, objects' cells, graph edges or counter keys, and `seq` charges the sum over
  its body. This accounting differs from v2's, so v2 and v3 can differ only where a chain comes within one op of
  the bound. If members of one shared class would fall on both sides of the bound, the verdict is
  `ABSTAIN(step_bound_straddle)`.

## 2. Bottom-up shared evaluation (the verdict is v2's, computed without enumerating chains)

* **Observation points:** X = every public input and the query input.
* **Node:** a value vector over X (ERROR allowed per point). Nodes are keyed by the canonical JSON encoding
  (sorted keys, fixed separators), which is injective on JSON values, so key equality *is* exact value equality.
  Python dict lookup compares the full keys, so a hash collision can never merge distinct vectors. This gives
  invariant (a).
* **Edge** (node n, tool t): t applied to each value of n. It is evaluated once (memoised) and reused at every
  layer.
* **Layer k** (chains of exactly length k) maps node → (count of chains, lexicographically minimal chain, min/max
  accumulated steps per point). Layer 1 is the input vector extended by each tool. Layer k+1 is the image of
  layer k under every tool, with counts summed and minimal chains = min(prefix-min + t).
  * Chains of each length are kept in their own layer. This is invariant (b): exact depth and scope coverage,
    with every chain of length ≤ D represented exactly once by count.
  * No class is ever dropped or truncated (c).
* **Soundness argument (congruence).** Every op is a pure function of its input value (and its step cost is a
  function of the value). So two prefixes with identical value vectors on all of X give identical value vectors
  for every extension, on all of X. A class therefore represents its members exactly *on the observation points
  that the verdict depends on*. It makes no claim about other inputs, and none is needed. The step bound is the
  only path-dependent part, which is why min/max steps are tracked and a straddle abstains.
* **Probes (d).** Each `check` call rebuilds the graph from the evidence alone. There is no state between calls,
  so a new observation point re-partitions everything from scratch.
* **Verdict.**
  * For each layer, a node *fits* when every public point equals its target exactly (no ERROR).
  * The answer is the node's query point, with count = chains, and the witness = the minimal chain at the
    smallest layer.
  * k, k_exact, `fitting` (total chains), two witnesses (by sorted answer key), query_error and claimed_not_unique
    are defined exactly as in v2.
  * `chains_total` is the declared scope size. Work is reported as `node_evals` (edge evaluations × |X|), `nodes`
    and `steps`.
* **Budget:** ≤ 2,000,000 edge evaluations and ≤ 500,000 nodes, otherwise `ABSTAIN(budget_exhausted)`. Unlike v2,
  there is no limit on the declared chain count.

## 3. Rewrite proofs: proposed vs proved

* **Proposed equalities** (for example identities observed on source data) are solver-side only, for exploration
  and ordering. The checker never sees them.
* **Proved equalities** are citations `{"axiom": A, "tool": i}` of a fixed table of axioms, each with a written
  proof (below) and an applicability condition. On edge (n, tool i), if the cited axiom's condition holds on
  every non-ERROR value of n, v3 sets the edge's target to n itself, with step cost `1 + size(value)`, without
  executing the op. Otherwise it evaluates normally.
* **Rejections:** an unknown axiom, a tool index out of range, or an axiom whose op or parameters do not match the
  cited tool gives `ABSTAIN(bad_proof)`.
* **Effect:** proofs change only work, never the verdict (tested).

| Axiom | Cited tool must be | Condition on value v | Proof |
| --- | --- | --- | --- |
| `sort_fixpoint` | `Sort{path: ".", desc: false}` | v is a list whose elements are all non-bool ints, or all strings, and v[i] ≤ v[i+1] for every i | Sort is a stable sort by (value, index). A non-decreasing sequence is already in that order, so the permutation is the identity. |
| `runheads_fixpoint` | `run_heads` | v is a list and key(v[i]) ≠ key(v[i+1]) for every i | run_heads keeps v[i] iff i = 0 or key(v[i−1]) ≠ key(v[i]), so every element is kept. |
| `runmax_fixpoint` | `running_max` | v is a list of non-bool ints, non-decreasing | out[i] = max(out[i−1], v[i]) = v[i] by induction, since v[i−1] ≤ v[i]. |
| `top_fixpoint` | `ir_counter_top{k}` | v is a Counter with ≤ k keys whose `counts` are sorted by key | top keeps min(k, n) = n entries and re-sorts them by key, which is already their order. |

Each axiom's condition ⇒ op(v) = v is also checked bounded-exhaustively (all lists over small alphabets of length
≤ 5), against v3's own interpreter and against v2.

## 4. Validation plan

1. **Differential, bounded exhaustive:** random tasks over small tool sets at depths 1–4, with v3 against v2 on
   label, reason, k, k_exact, fitting, answers and witnesses.
2. **Targeted adversarial:**
   * two subexpressions that agree on all demonstrations, diverge on the query and are wrapped in parent ops
     (must give AMBIGUOUS);
   * a demo-only-keyed (unsound) variant must be shown to fail on the same evidence;
   * many distinct intermediate classes that collapse only after a parent op (no truncation);
   * a probe that splits a class must change the verdict;
   * step-bound behaviour;
   * bad proofs, v2 lemmas and a wrong version.
3. **v2's hand-worked and adversarial suites,** re-run on v3 (with lemma cases mapped to proof cases).
4. **Identity on every existing Wave 31 task:** increment 1 (dev), increment 2 (dev + admission_val) and
   increment 3 (dev + val_inc3). This covers source and target tasks: matched-scope evidence with the teacher as
   candidate, and macro-scope evidence with learned seq libraries. It must be 100%.
5. **Freeze:** sha256 pinned in `src/nexus/checker_kernel_v3.sha256`, and verified by the external runner from a
   git object.

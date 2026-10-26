# NEXUS Checker v4 (separately versioned; v1, v2 and v3 are unchanged)

**Authorisation:** owner brief of 2026-10-26: "Where new pure constructs require deterministic scope checking,
implement a separately versioned, independently tested, hash-pinned `src/nexus/checker_kernel_v4.py` (standard
library only, zero shared prover code, hand-worked + exhaustive + adversarial tests) while keeping v1–v3 untouched."

## Language (Wave 38)

* **Tools:** typed tools whose parameters are **lambda ASTs**, composed as chains of length ≤ 4
  (encode → transform → decode). The complete grammar is in `src/nexus/w38_lang.py`'s docstring; v4 implements the
  same grammar independently.
* **Lambdas** have:
  * a variable `x`;
  * record fields;
  * constants;
  * arithmetic (add, sub, mul, mod, max, min);
  * comparisons;
  * boolean operators;
  * `if`;
  * string functions (low, up, int, str, fst, lst, len, `bef` / `aft` delimiter);
  * predicates (even, isdig).
* **Higher-order tools:** map, filter, sortby, groupby, countby, best, plus **fold** and **scan**, which are bounded
  loops with an accumulator.
* **Representation tools:** split / join / words / chars (segments), enum (indices), pairs (adjacency relation), tjoin
  (a relation join over two tables), fill (missing values), objs / paint / recolor_if (a grid ↔ object-record
  encoder / decoder), reach / topo / indeg / outdeg (graph relations, dependency order).
* **Bounds:** ints |v| ≤ 10⁶, strings ≤ 64, lists ≤ 64, records ≤ 12 fields, nesting ≤ 5. Any failure is ERROR
  (absorbing).

## Verdicts

The semantics are v3's: exhaustive_UNIQUE, AMBIGUOUS(k) with two witnesses, and ABSTAIN with a reason. They are
computed by bottom-up shared evaluation over exact canonical value vectors on all public inputs and the query, with:
* per-depth counts and minimal witness chains;
* no truncation;
* statelessness, so a probe re-partitions everything from scratch;
* an all-ERROR vector never extended (it can only stay ERROR);
* a budget of 3·10⁶ edge evaluations and 4·10⁵ nodes, beyond which the verdict is ABSTAIN(budget_exhausted).

v4 accepts **no** lemmas or proofs.

## Validation (`tests/test_checker_kernel_v4.py`)

* a **differential** check between two independent implementations (v4 and the prover's `w38_lang`), over every tool
  of every declared scope × a broad value pool (> 50k pairs);
* verdicts against **brute-force enumeration** on small scopes, with witnesses identical;
* an **adversarial** case: two filters that agree on the demos and diverge on the query only after a parent fold
  (AMBIGUOUS, k = 2);
* rejections: wrong version, failing candidate, unsupported op, and lemmas / proofs;
* pins: v1–v4 hashes, and v4 imports only `json`.

# NEXUS Checker v5 specification (Wave 39)

**Status:** separately versioned and hash-pinned (`src/nexus/checker_kernel_v5.py`, pin in `src/nexus/checker_kernel_v5.sha256`).
**Authorisation:** owner request of 2026-10-27 ("Implement and validate these general constructs in a separately versioned,
hash-pinned `src/nexus/checker_kernel_v5.py` ... leaving Checkers v1–v4 untouched").
Covered by AGENTS.md RULE 2. Checkers v1–v4 are unchanged.

## What v5 adds to v4

Everything below came from the PROSE-dev failure audit (`artifacts/w39_step1_audit.json`). Each construct is general and
none is a task-specific macro.

| Construct | Kind | Semantics |
| --- | --- | --- |
| `["at", A, i]` | lambda | signed index into a string or list (error if out of range) |
| `["sl", A, a, b]` | lambda | signed slice `A[a:b]`, with `a` and `b` either ints or `None` |
| `["cap", A]` | lambda | first character upper-cased, the rest lower-cased |
| `["shape", A]` | lambda | character-class shape: ASCII digit → `9`, upper → `A`, lower → `a`; other characters kept |
| `["pad", A, n, ch]` | lambda | left-pad to width `n` with `ch` ∈ {`0`, space} |
| `["dsh", A, e]` | lambda | exact decimal shift `A × 10^e`; `A` must match `-?D+(.D+)?`; the result is in canonical form |
| `["drnd", A, k, m, s]` | lambda | exact rounding to a multiple of `s·10^-k` (`m`: `h` = half away from zero, `f` = floor, `c` = ceil); exactly `max(k,0)` decimals; never `-0` |
| `fn{f}` | tool | apply a lambda to the whole value |
| `toks{c}` | tool | maximal character-class runs: `d` digits, `a` letters, `w` alphanumerics, `s` non-space, `n` runs of `[0-9.]` with outer dots stripped |
| `first{p, v}` | tool | first list element satisfying `p`, else the constant `v` |
| `dflt{v}` | tool | `v` if the value is `""`, `[]` or `None`, else the value |

**Other changes from v4:**
* The string bound is raised from 64 to 256 characters.
* The internal error marker is a unique sentinel. v4 used `None`, which conflates a legitimate `None` result with an
  error; this was found by the v5 differential test. v4 is unchanged and the quirk is disclosed.
* **Sound type-reachability pruning.** At the final layer, tools whose result is always a list are skipped when no
  public output is a list, because they cannot fit. Every fitting chain is still counted; this is tested against brute
  force.

## Output contract

| Field | Meaning |
| --- | --- |
| `SCOPE_UNIQUE` | Every chain in the declared finite scope that fits all public pairs gives the same answer on the query. **Scope-relative:** it says nothing about the true mechanism if that mechanism lies outside the scope (`scope_relative: true`). |
| `AMBIGUOUS(k)` / `ABSTAIN` | As in v4. |
| `extra[i].answers` | For each supplied future input (≤ 16), the number of distinct answers that the fitting chains give. 1 means unique within the scope on that input. |
| `UNDER_SPECIFIED_WARNING` | Issued when any supplied future input has more than one such answer: the public examples do not pin the mechanism down on the inputs it will be used on. This calls for an active probe or an abstention instead of a silent answer. |
| `warning_reasons` | `extra_nonunique` (the count that triggers the warning), plus two signals that are reported but do not trigger it: `query_shape_novel` and `loo_fragile` (public examples whose removal makes the query answer ambiguous). On PROSE-dev the shape-novelty signal was uninformative and leave-one-out fragility fired on almost every task with 3 examples, so the warning rule uses only the per-input signal. |
| `HELD_OUT_VERIFIED` | Not issued by the kernel. The harness issues it after evaluating the chosen program on unseen held-out pairs. |

## Validation (`tests/test_checker_kernel_v5.py`)

* **Pins:** v1–v5 pins are checked, and the kernel imports only `json`.
* **Differential test:** 1,101,915 (tool, value) pairs, built from:
  * 1,563 tools, comprising every tool of every declared v5 scope over internal and PROSE-dev tasks plus full parameter
    grids of every new construct;
  * 705 values, comprising internal values, PROSE-dev values, random decimals, malformed decimals, Unicode digits and
    mixed strings.

  Checker v5 and the prover's `w39_lang` agree on every pair, on both values and errors.
* **Brute force:** verdicts, the answer count, the AMBIGUOUS witnesses, the per-extra-query answer counts, the
  leave-one-out sets and the warning were checked against brute-force enumeration (depth 2) on ≥ 20 internal and
  PROSE-dev cases.
* **Adversarial:** half-way rounding in both signs, negative zero, floor and ceil at negatives, step-5 rounding,
  malformed decimals (`1.`, `.5`, `1.2.3`, Unicode digits, `1e3`), out-of-range index and slice, the over-bound string,
  and type-pruning soundness.
* **Rejections:** wrong version, a failing candidate, an unsupported tool, lemmas or proofs, and more than 16 extra
  queries.

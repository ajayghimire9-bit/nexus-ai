# Wave 26 Phase 2 — oracle realism (noise, noise-tolerant certificates, opaque stdlib mechanisms)

Branch `codex/wave26-phase2-oracle-realism` (from Phase 3 `262917a`). Code: `src/nexus/wave26_phase2.py`, driver
`scripts/phase2_oracle.py`, tests `tests/test_wave26_phase2.py`. Cell: the Phase 1 confirmed crossover cell
(depth 2, 8 fields, large grammar, `c_oracle = 20`), single-query episodes (multi-query reuse was tested in
Phase 1 / wave 25).

## Design (locked)

* **Opaque mechanisms.** Every S[k, o] and Sort[o] is replaced by an opaque stdlib callable
  (`itertools.islice`, `heapq.nsmallest`, `heapq.nlargest`, `sorted` with `operator.itemgetter`) under an
  anonymous role.
  * Their structural class is observed on every executed transition (`EMPIRICAL_CONTRACT`).
  * Under the vault firewall, empirical contracts never prune. A property prunes only if it is PROVED_SOUND
    for every role that can appear, so **no contract prunes in this cell**.
  * `pandas` is not installed, so the opaque tools are stdlib only.
* **Noise.** Each probe response is corrupted independently with probability ε ∈ {0.01, 0.05, 0.10}: one
  random output item is dropped. Public pairs are noiseless.
* **Certificate `UNIQUE_WITHIN_NOISE(ε, δ = 0.01)`.**
  * The exact certifier runs on the public pairs only, giving the complete version space H.
  * Each h accumulates a disagreement count d(h) over the probes.
  * An answer group's evidence is the max over its members of εᵈ(1−ε)ⁿ⁻ᵈ (uniform prior).
  * The certificate is issued iff the leading group beats every other group by a likelihood ratio
    ≥ (1−δ)/δ.
  * Probes may repeat an input. Budget: 6 probes.
* **Arms.**
  * `exact_eig_noisy`: unlearned; flat likelihood-weighted EIG over standard perturbations.
  * `full_noisy`: vault plus answer-directed, likelihood-weighted I(Y_q;Y_x), with two-tier candidate
    scheduling (factored edits only when the cheap tier cannot split the answer groups completely).
  * `naive_exact_elim`: full's probing, but it eliminates a hypothesis on ANY disagreement (control).
  * Contract learning (~33k units per seed) is amortised over a 100-task horizon in full and naive.

## Gates

| Gate | Criterion |
| --- | --- |
| Calibrated soundness | For each noise-tolerant arm and each ε, false certificates ≤ the 99% upper quantile of Binomial(#certificates, 0.01) |
| Phase 2 PASS | Calibrated soundness AND full_noisy fully loaded < exact_eig_noisy AND solved(full) ≥ solved(exact) AND G_tycho AND identical fresh-process replay |

Cost per solve is reported as a secondary measure. It is **not** a gate: it was not declared before the dev
results were seen.

## Dev evidence (seeds 711–715, 30 episodes × 3 ε)

| Arm | Solved | False certificates | Probes | Fully loaded |
| --- | --- | --- | --- | --- |
| exact_eig_noisy | 82 / 90 | 0 | 257 | 5,786,824 |
| full_noisy | **90 / 90** | 0 | **192** | 5,837,322 (+0.9%) |
| naive_exact_elim | 87 / 90 | 0 | 90 | — |

* naive_exact_elim emptied the version space on 3 episodes (all at ε = 0.10); the truth was eliminated by
  noise.
* Dev change: two-tier scheduling, which cut full from 6.45M to 5.84M.
* **Expected to fail:** the total-cost criterion. Opacity removes all proved pruning, and at c = 20 the
  saved probes (65 × 20 units) cannot offset contract learning and candidate scoring.

## Confirmation

```
python3 scripts/phase2_oracle.py --confirm --n 8 --checkpoint runs/experimental/wave26_phase2_confirm.jsonl --out artifacts/wave26_phase2_confirmation.json
python3 scripts/phase2_oracle.py --replay-of artifacts/wave26_phase2_confirmation.json --n 8
```

Seeds 2001–2005 are one-use and registry-enforced.

## Confirmation result (seeds 2001–2005, frozen code `a7c4eb9`) — **PHASE 2 FAIL** (total-cost criterion)

* Call 1, confirmation: 155.7 s. Call 2, fresh-process replay with `PYTHONHASHSEED=271828`: 156.4 s.
* Digests `61373ef3…98e8` are identical.
* Artifact: `artifacts/wave26_phase2_confirmation.json`, sha256
  `91f927eaa7c78f65ad94bb140957818a42cbfc7680ea2221c55712be5c664ab2`.
* 40 episodes × 3 noise levels = 120 queries per arm.

| Arm | ε = 0.01 | ε = 0.05 | ε = 0.10 | Solved | False certs (≤ 99% bound) | Empty V | Probes | Fully loaded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| exact_eig_noisy | 40 | 39 | 31 | 110 / 120 | 0 (≤ 4) | 0 | 372 | **7,744,965** |
| full_noisy | 40 | 40 | 40 | **120 / 120** | 0 (≤ 4) | 0 | **256** | 7,933,737 (+2.4%) |
| naive_exact_elim | 40 | 40 | 35 | 115 / 120 | **1** (≤ 4) | **4** | 121 | 7,940,173 |

The ε columns count solved queries out of 40.

| Gate | Result |
| --- | --- |
| Calibrated soundness (noise-tolerant arms, every ε) | **PASS** (0 false certificates in 230 certificates) |
| full_noisy fully loaded < exact_eig_noisy | **FAIL** (+2.4%) |
| solved(full) ≥ solved(exact) | PASS (120 vs 110) |
| G_tycho | PASS (360 / 360 rows) |
| G_replay | PASS |

Secondary measure (not a gate): cost per solved query is 66.1k for full vs 70.4k for exact.

Opaque tools' empirical contract: 233k–260k observed transitions per seed, 0 sub-multiset violations. It
was used for ordering only and never for pruning.

**Reading.**
* The noise-tolerant certificate does what it is for. 0 false certificates over 230 certificates, at noise
  up to 10%.
* The naive exact-elimination control shows why the rule is needed. At ε = 0.10 it emptied the version
  space 4 times (the truth was eliminated by noise) and issued 1 false certificate.
* Answer-directed probing solves every query (vs 110 / 120) with 31% fewer probes.
* On total cost the system **does not** beat the unlearned baseline. With opaque mechanisms no proved
  contract can prune, which removes the pruning that produced Phase 1's −59%. At c_oracle = 20 the 116
  saved probes are worth ≈ 2.3k units, against contract learning and candidate scoring.

**Implication.** The Phase 1 advantage depends on white-box, provable mechanisms. To keep it with opaque
tools, NEXUS needs either a sound way to bound an opaque tool's behaviour (e.g. a verified wrapper
contract, or a library specification adopted as an explicit, audited assumption), or a regime where probes
are expensive. In the Phase 1 grid, the vault's margin shrank as c_oracle grew, while the probe saving
here grows with c_oracle.

**Phase 2 has not passed.** Per the roadmap's dependency order, Phases 4–6 should not start until it does,
or until the owner decides how to proceed.

## Phase 2b — owner option 2: re-run at a higher oracle cost on a fresh range (locked before seeds 2006–2010)

The owner chose option 2. The registry gets a new one-use range `("phase2", "confirm_b") = 2006–2010`,
disjoint from every other range. Phase 2 arms make no cost-dependent decisions, so the oracle cost was
selected by **re-pricing the dev artifact (seeds 711–715) only**. The spent 2001–2005 outcomes were not
used for the choice.

| c_oracle | full / exact (dev) | Solved full / exact |
| --- | --- | --- |
| 20 | 1.009 | 90 / 82 |
| 200 | 1.007 | 90 / 82 |
| **2000** | **0.988** | 90 / 82 |
| 20000 | 0.886 | 90 / 82 |

**Selection rule.** The smallest cost in the Phase 1 grid at which the dev re-pricing crosses →
**c_oracle = 2000**. The dev margin there is thin (1.2%); declared risk. At high oracle cost the naive
control is cheapest because it stops early, but it is not sound under noise (false certificates and empty
version spaces), so it is not a valid comparator for the gate.

The code is unchanged except that the oracle cost is now a parameter. Gates are identical to Phase 2.

```
python3 scripts/phase2_oracle.py --confirm-b --c 2000 --n 8 --checkpoint runs/experimental/wave26_phase2b_confirm.jsonl --out artifacts/wave26_phase2b_confirmation.json
python3 scripts/phase2_oracle.py --replay-of artifacts/wave26_phase2b_confirmation.json --n 8
```

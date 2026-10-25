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

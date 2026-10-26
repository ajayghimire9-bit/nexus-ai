# Wave 37 (NOT LOCKED): the frozen learner × N1 change detection, in one pipeline

* **Owner direction:** preserve the checker and the core architecture (no Checker v4 is needed). Retain N1 and the
  frozen learner, with applicability conditions. Test their interaction, including stationary periods, before any
  combined default. Keep autonomous architecture search experimental.
* **Setup:** branch `codex/nexus-architecture-comparison`; Checker v3 pinned (`3c68230e…`); sandbox, OS meter and
  detectors unchanged.

## Retained components and applicability conditions

| Component | Status | Apply when | Do not rely on it when |
| --- | --- | --- | --- |
| Frozen online learner (Wave 36 E3 program; online fragment prior + tool knowledge, sharpened, refit every 8) | retained (online-program baseline) | streams of certifiable program tasks over the G_P middle IR with recurring fragments: confirmed on F2, F3 and mixed / non-stationary streams | families like F4 (counter-valued outputs), where it was 1.007× *no learning*; scopes outside G_P depth 4; one-off tasks with no stream |
| N1 BOCPD over a symbolic hypothesis model | retained (world track) | interactive tasks with a small explicit hypothesis space and unannounced switches (10/10 seeds, Brier 0.018 vs 0.161) | stationary worlds (≈ 1% return loss, ≈ 120× compute); hypothesis spaces too large to enumerate; certificate-producing tasks (its outputs are probabilities, never certificates) |
| Autonomous architecture search (E2 / E3) | **experimental only** | — | any default: search methods did not separate from random search; discovery cost ≈ 1.6k–31k streams to break even |

## Interaction protocol (shared pipeline: online program streams from an empty library)

* **N1 in this pipeline:** BOCPD (Dirichlet-categorical, hazard 1/50) over each task's observable surface signature
  (input type → output type).
* **Arms:**
  * **base:** no learning, no detection;
  * **learner:** the frozen learner;
  * **n1:** detection with nothing to reset (pure overhead);
  * **both:** the learner forgets tasks before the declared change point and refits.
* **Streams:**
  * **stationary:** one family, two segments (stat_F2, stat_F3);
  * **non-stationary:** unannounced family switches (F2 → F4 → F3, and F3 → F2 → F4).

## Dev results (wave37 dev 831–833; `artifacts/wave37_dev.json`)

All arms: 0 wrong, 0 flags, D4 held.

| Streams | base | learner | n1 | both | learner / base | both / learner | n1 / base | declarations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stationary | 136.97 | 123.49 | 137.04 | 123.73 | 0.902 | 1.0019 (1/3) | 1.0005 | 6 (all false) |
| non-stationary | 178.97 | 169.27 | 179.11 | 169.02 | 0.946 | 0.9985 (2/3) | 1.0008 | 6 |

## FROZEN adoption rule (committed before the one-use confirmation 7701–7705)

Make **both** the combined default **only if**:
* on non-stationary streams, both < learner pooled and in ≥ 4/5 seeds; **and**
* on stationary streams, both ≤ 1.01 × learner pooled;
* with 0 wrong and 0 flags.

Otherwise keep the components separate under the applicability conditions above. Also reported: n1 / base (pure
detection overhead) and false declarations on stationary streams. The replay check is `both` on switch_A for seed
7703.

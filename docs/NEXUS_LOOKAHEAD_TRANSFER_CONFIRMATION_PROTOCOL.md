# Lookahead versus frozen H=16 transfer — locked protocol v1

Base `961e935cdf2a72c4221c640bd9ead1b2928cfac7`. Branch `cursor/lookahead-transfer-confirmation-prep`. Development lookahead result stays closed. Nested H=8 stays closed. Score-correction stays closed. Historically exposed confirmation splits stay closed. Reserved amortized confirmation hash `d1fa621351d286cf` is **not** consumed.

This is a **transfer** test of the frozen parameter-free one-step lookahead controller against unchanged H=16 receding. Successor value remains the frozen **open-loop** H=16 score from `s'`. Do not call it Bellman-consistent receding-policy value.

No fitting, reward shaping, horizon change, candidate-count change, or confirmation-outcome retune.

## 1. Confirmation eligibility

| Split | Hash | Status for this question |
|---|---|---|
| `pendulum_lat_cf*` | `baa655fcb94e61bc` | Historically exposed: H=16 student-versus-zero control and later 200-step studies. Not pristine. Not reused. |
| `pendulum_ctrl_rp*` | `053e8efca60fb4ac` | Historically exposed: negative-transfer H=16 control, return-phase, late-control. Not pristine. Not reused. |
| `pendulum_ctx_c*` | `87b83c41be34aa1a` | Historically exposed: direct-latent **prediction** confirmation. Not 200-step lookahead. Not pristine. Not reused. |
| `pendulum_amort_c*` | `d1fa621351d286cf` | Outcomes never collected, but reserved for a different failed-gate protocol. Untouched as data, not generated for this question. **Not consumed.** |

No historically registered confirmation split is both pristine and generated for lookahead-versus-H=16. This protocol therefore uses a **new** holdout from locked rule `lookahead_transfer_holdout_v1`.

Holdout tuples, first three accepted keys from SHA256(`lookahead_transfer_holdout_v1:{counter}`) over the discrete (g, m, l) grid, rejecting every previously registered physics key:

- `pendulum_look_tf0`: (17.1, 1.5, 0.8)
- `pendulum_look_tf1`: (12.5, 0.65, 0.9)
- `pendulum_look_tf2`: (4.2, 3.2, 1.7)

Split hash `73844661addfa11b`. Closed confirmation result files are not parents and must not be read for outcomes.

## 2. Frozen controller identity

Copied from the development-validated implementation without modification:

- Arm A: `h16_first_action` — score the shared 16×16 array from `s`, execute `seq[argmax, 0]`.
- Arm B: `lookahead_first_action` — for each of 3 first actions, one model step to `s'`, score the **same** 16×16 array from `s'`, execute `argmax_a [r + max_k score_H16]`.

Unchanged: 10 frozen FiLM decoders, 5 student encoders, normalization, 3 torques, published Pendulum reward, H=16, 16 candidates, `candidate_sequences(seed, 16, 16)`, argmax tie-break, student visitor `(d+t) mod 5`, zero-context visitor.

Student context on **new** physics: frozen encoder inference on 128 random-policy support rows of that holdout task (`set_context_from_dataset`). Inference only. Development used stored development codes because those physics already had them; new physics do not. Zero visitor stays `z = 0`. This is not a retune.

## 3. Computation confound

Lookahead uses **771** imagined model states per step versus **256** for H=16. This confirmation tests the complete controller package. A compute-matched control is **not** part of the primary comparison.

## 4. Primary versus secondary

Estimand A (primary): decoder mean of (lookahead 200-step return − H=16 200-step return), averaging three holdout tasks and both visitors. Student-t 95%, df 9. Practical margin **25**.

- Complete, mean ≥ 25, lo > 0: `lookahead_transfer_established`
- Complete, mean ≤ −25, hi < 0: `lookahead_transfer_harm_established`
- Else: `lookahead_transfer_not_established`
- Incomplete grid: `incomplete`

Estimand B (secondary, cannot upgrade A): student-minus-zero return **inside** each arm. Do not infer B from A.

Exploratory, cannot upgrade: student-only A; zero-only A; task-level A; disagreement; MAE.

If transfer is later established, the next recommendation is a different environment family, not Pendulum retuning. If it fails, do not retune this controller from confirmation outcomes.

## 5. Budget and authorization

Hard cap **180 seconds total process wall**, **27,840** new real steps, **12,324,000** imagined transitions, **0** optimizer updates.

- Support: 10 × 3 × 128 = **3,840**
- Control: 10 × 3 × 2 × 200 × 2 arms = **24,000**
- H=16 scoring: 10 × 3 × 2 × 200 × 16 × 16 = **3,072,000**
- Lookahead: 10 × 3 × 2 × 200 × (3 + 3 × 16 × 16) = **9,252,000**

Fresh seeds `14000000+` / `14100000+` / support `14200000+`. Local CPU. 120 read-only checkpoints.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash, protocol hash, and these caps.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_lookahead_transfer_confirmation.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_lookahead_transfer_confirmation.py
# Collection blocked:
PYTHONPATH=src:.deps python3 scripts/run_lookahead_transfer_confirmation.py --execute
```

Not a result, not general control improvement, not learning-to-learn, not AGI.

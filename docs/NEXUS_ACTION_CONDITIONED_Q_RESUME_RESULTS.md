# Action-conditioned first-action Q — resumed complete grid

## Registered decision

The fail-closed resume completed the locked 60-cell grid. Label: `action_conditioned_gain_not_established`.

Action-conditioned Q minus frozen H=16 first-action 64-return: **−4.293 [−15.751, +7.165]**. The mean is below the registered one-point threshold and the paired 95% interval includes 0. The screen required mean ≥ 1 and lower bound > 0. Neither passed. This is a valid, complete, inconclusive decision result. It is not a timeout, not harm, and not an equivalence claim.

Action-conditioned Q minus the 7-coefficient additive Q: **−3.050 [−17.210, +11.110]**. Action-conditioned Q minus frozen sequence-value V: **−2.952 [−11.844, +5.941]**. Both include 0. Neither secondary contrast can upgrade the failed primary screen.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify an architecture change. The original incomplete capture remains on disk unchanged.

## What was tested

The missing cell is decoder 9, development task 2, zero visitor. Collection used the original locked reset/collection/candidate/future seeds and the frozen decoder-9 models and Q fits. The 59 previously saved cells were copied byte-for-byte into a **separate** completed artifact. Family `action_obs`, ridge λ=0.1, H=16, 16 candidates and sequence-value V were not changed.

Primary aggregation: students, then equal visitor groups, then equal tasks, inside each of ten independently pretrained decoders. Intervals are Student-t 95%, df 9.

## Means and sensitivity

Pooled first-action 64-returns: H=16 **−162.784**; sequence-value **−164.125**; additive Q **−164.027**; action-conditioned Q **−167.077**. In-set first-action regrets: H=16 12.117, additive 13.360, sequence-value 13.458, conditioned 16.410. Conditioned first-action agreed with H=16 on **0.360 [0.237, 0.483]** of student selections, with additive on **0.417 [0.190, 0.643]**, and with sequence-value on **0.460 [0.278, 0.642]**.

Decoder conditioned-minus-H=16 point estimates: **5.30, 0.15, 22.00, 0.05, −19.49, −38.85, −9.39, 0.01, −0.77, −1.95**. Five of ten are positive. No task or visitor group establishes the registered gain:

- **dev0:** **−20.427 [−50.665, +9.810]**
- **dev1:** **7.127 [−5.851, +20.104]**
- **dev2:** **0.421 [−16.344, +17.187]**
- **Student-visited:** **−0.409 [−18.095, +17.277]**
- **Zero-visited:** **−8.177 [−20.456, +4.101]**
- **Zero scoring context:** **−3.592 [−16.758, +9.573]**

## Prediction is not a pass

Source-fit RMSE by decoder, frozen before this resume and unchanged: action-conditioned **69.99, 60.14, 68.76, 64.42, 63.71, 65.38, 73.87, 71.52, 71.21, 67.55**; additive **72.73, 62.24, 70.98, 66.15, 65.70, 67.13, 75.90, 72.86, 73.04, 69.17**. Development Q RMSE against the three actual first-action returns: conditioned **96.652 [85.404, 107.900]**; additive **88.064 [78.067, 98.061]**. Prediction accuracy cannot pass the decision screen.

## Integrity

Original incomplete capture SHA `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680` unchanged. Fit SHA `2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae` unchanged. Frozen 59-cell digest `6e8bff7dd117ab396811165d690d6c9f7a45d5959b4b1dd3db8aedaaca423e5a` unchanged after assembly. Checkpoints before/after: 120 verified, 0 missing, 0 mismatched. Independent raw-trace reconstruction reproduced the primary interval and the ten-decoder groups. The original `--audit` path still rejects the incomplete parent file, as required.

## Provenance, resources and tests

Branch `cursor/action-conditioned-q-resume`. Preparation SHA **01256ca6a8129dfd10b2458b729bf7e69c5f0393**. One-run allocation/execution SHA **45950e17a2eb736cce82f01e0bca786c2f2df07f**.

- Resume config SHA256 `32670b597cacf39a5c33bbb11a7e5558e01ccc0622aa4c8fa86f096884ab55c4`
- Resume protocol SHA256 `71322a1811d573a780f01f0194dfde57b3ca8707b94ef0c066fba3498d781006`
- Resume allocation SHA256 `86c489cf880c7b98ee6255d442e81d9ade6038c90301387025d5fd9fc853a681`
- Completed artifact SHA256 `aa78514a5a2bb560089453000d8049284aafe3136c83f03c1a88de9dc01a3793`
- New-cell artifact SHA256 `4ec58dfabe0e18f18ac2fadcbaa3b42420dceff5635995364dcf2d1e0b0a16c8`
- Parent raw SHA256 `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680`
- Parent fit SHA256 `2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae`

One resume collection completed in **1.061 s**, below 60. Exactly **242** new real steps (50 collection + 192 first-action) and **64,512** imagined transitions. The `--execute` process additionally spent offline CPU on pre-collection integrity and post-collection 60-cell reconstruction (process wall **117.329 s**); those steps used zero new environment interactions. No new support. No world-model, encoder, Q-fit, or original-capture writes. Python 3.13.5, NumPy 2.5.4, torch 2.14.1, gymnasium 1.4.0, local CPU.

The resume one-run remaining is 0. The exhausted 3,600-second standing session file was not modified (SHA `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`). No retry. Further experiments are not authorized by this allocation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_action_conditioned_q_resume.py tests/test_action_conditioned_q_resume_feasibility.py tests/test_action_conditioned_q_resume_recorded.py tests/test_action_conditioned_q_recorded.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q_resume.py --audit
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q.py --audit
```

The original `--audit` path still rejects `artifacts/action_conditioned_q.json`. The resume `--audit` path accepts the separate completed artifact.

## One next experiment

The locked original protocol says to **close terminal-value score-correction** rather than add layers, polynomials, or action×context terms. Next work should address receding-horizon policy consistency, action selection and online adaptation under a **new** protocol. That proposal has not been implemented and is not authorized here.

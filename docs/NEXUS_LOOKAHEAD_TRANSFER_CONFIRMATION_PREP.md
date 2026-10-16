# Lookahead transfer confirmation — preparation audit

Branch `cursor/lookahead-transfer-confirmation-prep` from `961e935`. Zero new environment steps. Closed confirmation outcomes were not read. Collection unauthorized.

This is not a result, not general control improvement, learning-to-learn, or AGI.

## Eligibility

A scientifically defensible **independent** confirmation split remains only if it is generated for this question. Existing registered confirmation physics are either historically exposed or reserved for a different protocol.

- `baa655fcb94e61bc` (`pendulum_lat_cf*`): used for H=16 student-versus-zero control. Not pristine.
- `053e8efca60fb4ac` (`pendulum_ctrl_rp*`): used for negative-transfer H=16 control and later 200-step diagnostics. Not pristine.
- `87b83c41be34aa1a` (`pendulum_ctx_c*`): used for direct-latent prediction confirmation. Not pristine.
- `d1fa621351d286cf` (`pendulum_amort_c*`): outcomes never collected, but reserved for amortized-encoder confirmation after a failed development gate. Untouched as data; **not consumed** here.

The locked holdout is rule `lookahead_transfer_holdout_v1`, split hash `73844661addfa11b`:

`(17.1, 1.5, 0.8)`, `(12.5, 0.65, 0.9)`, `(4.2, 3.2, 1.7)`.

## Frozen controllers

Arm A: development `h16_first_action`. Arm B: development `lookahead_first_action`. Same 16×16 candidates, published reward, 10 decoders, student `(d+t) mod 5` and zero. Lookahead still uses 771 imagined states per step versus 256. Student z on new physics is frozen-encoder inference from 128 support rows; zero stays cleared.

## Rules

Primary: lookahead minus H=16 200-step return, ten decoders, margin 25. Labels: `lookahead_transfer_established`, `lookahead_transfer_harm_established`, `lookahead_transfer_not_established`, `incomplete`. Student-versus-zero is secondary and cannot pass transfer.

## Budget

**180 s** total process wall, **27,840** new real steps (3,840 support + 24,000 control), **12,324,000** imagined transitions, **0** optimizer updates. Ten decoders × three holdout tasks × two visitors × two arms × 200 steps. Local CPU. Expected capture ~6 MB, matching the development lookahead JSON. Frozen identity: 120 read-only checkpoints via `configs/control_replication.yaml` confirmation catalog SHA256 `18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa`. Prep does not load confirmation return fields.

Config SHA256 `385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8`. Protocol SHA256 `5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942`. `authorized: false`. Previous 3600 s remainder 47.766 s is not transferred and cannot cover this 180 s cap.

If a later authorized run establishes transfer, the next recommendation is a different environment family, not Pendulum retuning. If it fails, do not retune this controller from confirmation outcomes.

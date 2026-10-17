# Within-family MCC multitask at 128 — confirmation prep

Preparation only. No environment collection, no training, no confirmation
outcomes. Authorization stays `false`.

## Source state verified before this lock

- Local, Cursor Origin, and GitHub `cursor/mcc-multitask-128` tip:
  `5f8cda330194786dfe450292ba34a01e7b42540c`.
- H10 was first pushed only to `origin.cursor.com`. That is why the
  connected GitHub repository did not list the branch. GitHub now has
  the same full three-commit line (lock `38469c4`, auth `f8d2a1d`,
  results `5f8cda3`).
- Closed H10 raw SHA256
  `caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`.
- Closed H10 report SHA256
  `9c8f0274ed3778f4197319e74217427a1432d05658b21c59676652eb4143d480`.

## Proposed confirmation

- Holdout `mcc_multitask_128_confirm_v1`: **(0.0022, 0.0016, 0.07)**.
- Caps: **600 s / 20,960 / 1,024,000**.
- Frozen H10 recipe; new seed block `73,000,000+`.
- Allocation `authorized: false`, `runs: 0`.

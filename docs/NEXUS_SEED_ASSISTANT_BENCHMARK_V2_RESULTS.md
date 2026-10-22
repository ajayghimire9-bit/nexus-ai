# Persistent assistant benchmark v2 — attempt 1 incomplete

Pre-run revision: `474661c94e147f1337b1b6cf0bb6ece51f5a88ec`.
The protocol and tested implementation were pushed before execution.
65 targeted tests passed in 16.01 s; mocked orchestration is not real inference.

The real-model integration startup failed before any completion or dataset
generation. The model server exited and its log was empty. No configuration
was scored: **0/144 trials**, zero generated task datasets, no comparison means,
no confidence intervals and no established break-even or speedup. This is an
infrastructure failure, not evidence for or against retained knowledge.

The independent saved-record verifier reconstructs this INCOMPLETE status.
Raw file `artifacts/seed_assistant_benchmark_v2_raw.jsonl` is intentionally empty;
the saved result records worker return code 1 and preserves the raw-file hash.
Logs and registration remain at
`runs/experimental/attempts/seed-assistant-benchmark-v2-1/` (untracked local data).

Measured host wall: 0.610806 s. Aggregate waited CPU: 0.433630 s. Peak sampled
summed RSS: 98.921875 MiB. Conservative debit: **2 s**. Ledger after settlement:
**2080.632103455996 s used / 1519.367896544004 s remaining**. No model-file bytes
are presented as resident memory. No model tokens were reported as generated;
the comparison did not start.

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 scripts/run_seed_assistant_benchmark_v2.py \
  --model "$NEXUS_MODEL_PATH" --executable llama-server
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 scripts/verify_seed_assistant_benchmark_v2.py artifacts/seed_assistant_benchmark_v2.json
```

No tasks or thresholds were changed; no automatic retry occurred. The original
study ID remains consumed. Diagnose process startup as development engineering
before considering a separately versioned, preregistered study. Previous
artifacts and frozen model weights remain unchanged; main was not modified.

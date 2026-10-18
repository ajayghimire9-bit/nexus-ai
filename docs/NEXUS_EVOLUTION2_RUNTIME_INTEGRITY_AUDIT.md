# NEXUS Evolution-2 runtime integrity audit

Status: **integrity repairs applied; scientific execution still BLOCKED**.
Not an experiment, allocation, protocol lock, or LEVEL 2 result.

Branch: `cursor/evolution2-runtime-integrity`  
Base: `4a08b26f81cbe314ae475e71419344e688ab571a`  
Untracked Evolution-1 adapter files were preserved and not committed.

Scientific ledger remains **305.842 s used / 3294.158 s remaining**.

---

## 1. Hypothesis outcomes

Inspected against base `4a08b26` before repair. Tests in
`tests/test_evolution2_runtime_integrity.py`.

| ID | Hypothesis | Base finding | After repair |
|---|---|---|---|
| H-R1 | Reserve one operation, dispatch a modified request | **Confirmed.** `MeteredHost.dispatch` reserved `eval_0` and sent whatever dict it was given. `Operation.cache_record_hash` was stored and never checked. | **Rejected by test.** Digest of the canonical request must match the reserved operation before reserve/dispatch. Substitution of successor→flat does not start a worker. |
| H-R2 | Skip trusted binding and send an unsupported variant | **Confirmed.** Worker accepted any catalogue fingerprint, including `BALANCED`. Host accepted raw request dicts. | **Rejected by test.** `validate_public_payload` is shared by host and worker. Balanced variants fail closed. Hand-built operations cannot bind an unsupported request. |
| H-R3 | CPU is measured after the fact and over-claimed as enforcement | **Confirmed.** `RUSAGE_CHILDREN` is cumulative; no per-worker CPU cap existed; gate status said the host **PASS**ed metering without distinguishing enforcement. | **Still BLOCKED for enforcement.** `enforce_worker_cpu=True` raises `cpu_enforcement_unavailable`. Measurement remains parent / cumulative children / this-dispatch children snapshot / wall. |
| H-R4 | Supervisor buffers unbounded stdout/stderr | **Confirmed.** `subprocess.run(..., capture_output=True)` collected the full pipe, then the parser rejected size. | **Rejected by test.** `flood` (64 KiB) is cut while reading. Returned stdout ≤ 4096. Receipt is refused. |
| H-R5 | Supervisor exceptions leave a pending reservation | **Confirmed.** `dispatch` reserved, then called `supervisor.run` with no `finally`. `OSError` left `_pending` set. Invalid context could also fail during encode after reserve. | **Rejected by test.** Launch exceptions settle `failed` with no receipt. Invalid context is rejected before reserve. `close()` has `pending_key is None`. |

Success condition: a reserved operation cannot be silently replaced; supervisor
failures cannot produce an accepted receipt; measurement and enforcement are
named separately.

---

## 2. Minimal source changes

| File | Change |
|---|---|
| `src/nexus/evolution2/bindings.py` | Shared request/response schema, derived request id, expected event id, `validate_public_payload` (IID-only, typed context). |
| `src/nexus/evolution2/host.py` | Bind reserved `cache_record_hash` to the canonical request; bounded Popen reads; settle on every post-reserve path; fail closed on CPU enforcement; verify response event ids. |
| `src/nexus/evolution2/evaluator_worker.py` | Use the shared validator; reject balanced variants; add `flood` behavior for bounded-read tests. |
| `tests/test_evolution2_runtime_integrity.py` | Nine adversarial checks. |
| `tests/test_evolution2_runtime_gates.py` | Lock the revised gate keys. |

Evolution-1 `ReservationLedger` is reused. No second ledger. No H12–H17 or
Evolution-2 screen/result edits.

---

## 3. Tests actually run

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest \
  tests/test_evolution2_runtime_integrity.py \
  tests/test_evolution2_runtime_gates.py \
  tests/test_evolution2_cross_task_screen.py \
  tests/test_evolution2_independent_readiness_audit.py \
  tests/test_evolution1_toy_loop.py \
  tests/test_evolution1_resources.py \
  -p no:cacheprovider -q
```

**112 passed.** Integrity collection: **9**. Runtime-gate collection: **17**.
No Gymnasium, checkpoint, or scientific collection.

---

## 4. Revised gate verdicts

| Gate | Verdict |
|---|---|
| Trusted adapter contracts | **PASS** |
| Request binding (reserved digest = dispatched request) | **PASS** |
| Metered execution host (pre-call reserve, wall timeout, declared work) | **PASS** |
| Bounded IPC | **PASS** |
| Process-separated evaluator stub | **PASS** |
| Worker CPU enforcement | **BLOCKED** |
| Hardened OS / filesystem sandbox | **BLOCKED** |
| Real planner / simulator / checkpoint execution | **BLOCKED** |
| Scientific experiment authorization | **BLOCKED** |

---

## 5. Unresolved limits

- Worker CPU is **measured**, not enforced. `RUSAGE_CHILDREN` can include
  unrelated subprocesses of the same parent. This-dispatch snapshots reduce
  but do not eliminate that attribution error.
- No reliable portable sub-second CPU quota is available here. Darwin
  `RLIMIT_CPU` is integer seconds and is not treated as a stub enforcement
  mechanism.
- Parent and child still share UID, environment, and filesystem. No seccomp
  or landlock. Process separation is not a security sandbox.
- Physical `real_steps` remain 0. The worker is still a synthetic fixture.

---

## 6. Scientific execution

Still **BLOCKED**. `authorized=False`, `scientific=False`. No holdout, grant,
H17 work, or ledger debit. Synthetic Evolution-2 illustrations are unchanged
and are not LEVEL 2 evidence.

H16 usage file remains 305.842 / 3294.158.

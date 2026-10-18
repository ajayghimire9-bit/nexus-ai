# NEXUS Evolution-2 runtime gates — source-only engineering milestone

Status: **engineering milestone complete; scientific execution still BLOCKED**.
Not an experiment, allocation, protocol lock, or LEVEL 2 result.

Branch: `cursor/evolution2-runtime-gates`  
Base: `cursor/evolution2-independent-readiness-audit` @
`551de6928523d0ca9852f4eee2a2f35776f2e983`  
This does not authorize a scientific screen. Synthetic Evolution-2
illustrations remain contracts only.

Scientific ledger remains **305.842 s used / 3294.158 s remaining**.

---

## What was implemented

New committed modules only. Untracked
`src/nexus/evolution1/adapters.py` and
`tests/test_evolution1_adapters.py` were preserved and not overwritten
or committed. Existing Evolution-1 `ReservationLedger` /
`Work` / `Operation` / `Clock` / `Limits` are reused. No second ledger
type was added. Evolution-2 `tasks.py`, `methods.py`, and `screen.py`
were not modified.

| File | Role |
|---|---|
| `src/nexus/evolution2/bindings.py` | Explicit family bindings and pre-dispatch rejection |
| `src/nexus/evolution2/host.py` | Metered host, process clock, supervisor, public IPC |
| `src/nexus/evolution2/evaluator_worker.py` | Process-separated synthetic fixture worker |
| `tests/test_evolution2_runtime_gates.py` | 17 source-only / short subprocess tests |
| `docs/NEXUS_EVOLUTION2_RUNTIME_GATES.md` | This report |

The worker is invoked as `python -m nexus.evolution2.evaluator_worker`.
It reads one JSON request on stdin and writes one JSON response on
stdout. It does not import `nexus.evolution2.tasks` or the host ledger.

---

## Runtime-gate verdicts

| Gate | Verdict | Meaning |
|---|---|---|
| Trusted adapter contracts | **PASS** | Explicit family, action decoding, observation layout, reward timing, termination/truncation, root survival, fixture world-model id, fixture checkpoint id, and planner-operator fingerprint. Family is never inferred from dimensions. Mismatch, unknown family, incompatible checkpoint, balanced generator, and unsupported decoding fail before dispatch. |
| Metered execution host | **PASS** | `ReservationLedger` reserves declared logical work before any worker start. Failed, timed-out, interrupted, and invalid attempts keep the reservation. Parent CPU, child CPU, and wall are measured separately and are not lookup counts. |
| Process-separated evaluator stub | **PASS** | Narrow request/response schema. Hidden Evolution-2 family scores are not in proposer IPC. Crash, hang, timeout, invalid, empty, extra-key, and oversized outputs fail closed. |
| Hardened OS / filesystem sandbox | **BLOCKED** | Parent and child share UID, environment, and filesystem. No seccomp, landlock, or hidden-data mount isolation. Process separation is not a security sandbox. |
| Real planner / simulator / checkpoint execution | **BLOCKED** | No Gymnasium env, no model load, no inference, no planner operator call. Physical `real_steps` remain 0. Fixture checkpoint ids are hashes, not loaded binaries. |
| Scientific experiment authorization | **BLOCKED** | `authorized=False`, `scientific=False`. H17 remains blocked. No holdout, grant, or protocol lock. |

Passing this milestone does **not** authorize a scientific experiment
and does not convert the Evolution-2 synthetic screen into LEVEL 2
evidence.

---

## Resource accounting (this milestone)

| Quantity | Amount |
|---|---|
| Real environment steps | 0 |
| Imagined scientific transitions | 0 |
| Model training / inference | 0 |
| Scientific ledger | unchanged 305.842 / 3294.158 |
| H16 usage-file SHA-256 | `ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117` |
| Stub physical reservation | `Work()` — cached fixture, no env/model |
| Stub logical reservation | `plan_bound` imagined count for the proposed variant |
| Measured clocks | parent CPU, child CPU (`RUSAGE_CHILDREN`), monotonic wall |

Declared imagined counts are **not** treated as CPU. Lookup count is
recorded separately and is not a meter.

---

## Platform limitations

Supported here: macOS/Darwin with Python `resource.RUSAGE_SELF` and
`RUSAGE_CHILDREN`, plus `time.monotonic_ns`. The host **fails closed**
if those readings are unavailable.

`subprocess.run(..., timeout=)` enforces the supervisor wall cap and
kills the child. That is a trusted-host timeout, not an in-kernel
job controller.

Remaining isolation limits, also stored on every `HostReport`:

- `same_filesystem_readable`
- `no_seccomp_or_landlock`
- `shared_uid_and_environment`
- `stderr_not_a_secret_channel_guarantee`
- `subprocess_is_not_a_security_sandbox`

A worker that can read the repository can still see hidden source
tables on disk. IPC omission is necessary, not sufficient.

---

## Tests actually run

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest \
  tests/test_evolution2_runtime_gates.py \
  tests/test_evolution2_cross_task_screen.py \
  tests/test_evolution2_independent_readiness_audit.py \
  tests/test_evolution1_toy_loop.py \
  tests/test_evolution1_resources.py \
  -p no:cacheprovider -q
```

**103 passed.** Focused runtime-gate collection: **17**.
Existing Evolution-2 (11), audit (13), Evolution-1 toy (24), and
resource-ledger tests were unchanged and green.

No model, simulator, or scientific collection was run.

---

## Next

Independent review of these gates may proceed. Do not lock a
scientific protocol, choose a holdout, or allocate experiment time
from this branch. H17 stays blocked.

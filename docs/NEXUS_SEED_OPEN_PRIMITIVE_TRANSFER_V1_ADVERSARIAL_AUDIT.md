# Open Primitive Transfer v1 — adversarial source audit

Reviewed base: `8d62ce23722bafea9c355cde4f306ca23dad3584`.
This supersedes the scientific interpretation of the v1 Stage-B report; it does
not alter its raw results, protocol, verifier or checkpoint files.

**Open Primitive Transfer v1 Stage-B results do not establish autonomous
primitive acquisition or learning-rule transfer.**

All nine reported issues are confirmed in
`src/nexus/seed/open_primitive_transfer.py` at the reviewed base. Its SHA-256 is
`c4f3f999d29196b7da2b6d24f750b9ec8591bcc56b67d9cd913859bd08ee923b`.

1. **Direct private-test access** (2597–2603):
   `heldout_helper_checks` iterates `env._private_hidden_tests[:3]`. Expected
   outputs are produced by `_execute_ulib_helper_only`, outside an isolated
   evaluator. Checking dictionary keys in learner views does not prevent this.
2. **Answer-bearing specifications** (2101–2224): `UNKNOWN_LIB_SPECS` includes
   `obfuscated_helper`, `helper_source`, `post_op` and `patched_target_body`.
   The initial source even comments on the required composition. Names alone
   are not the issue: the runner directly consumes solution-defining fields.
3. **Scripted success** (2566–2620): the runner inspects and calls the specified
   helper, constructs its proposal from the specified source and installs
   `spec["patched_target_body"]`. These choices do not result from discovery.
4. **Frozen rule not controlling Stage B** (2534–2620):
   `frozen_evolved_rule` is supplied for kernel retention, not an instruction
   interpreter selecting these actions. Passing a rule object is not rule transfer.
5. **Unevaluated baseline costs** (2670–2763): baseline rows reuse another
   method's `hidden_eval` and assign constants including experiments 4.0/3.0/6.0
   and compute 28.5/19.25/52.0 plus family offsets. The identical paired
   differences and zero-width intervals are consequences of construction,
   not independent measured efficiency evidence.
6. **Unpatched no-propose comparator** (2714–2738): the environment is restored
   to `snap0` and `unpatched_eval` is assigned to the ablation. It never attempts
   an inline helper/composition patch. Promotion removal is confounded with
   removing patching entirely.
7. **Hard-coded cross-lab meaning** (2639–2659): teaching and assessment call
   `_execute_ulib_helper_only` for the supplied family mapping. Calling a known
   implementation through two interfaces is not learned grounding or transfer.
8. **Development used for selection** (1667–1745, 2858 onward):
   `evaluate_rule_on_stage_a_suites` evaluates `dev_suite` for every candidate;
   its score enters admissibility and the lexicographic winner key. That suite
   is development/selection data, not independent held-out transfer evidence.
9. **Verifier checks consistency, not discovery independence**:
   `scripts/verify_seed_open_primitive_transfer.py` checks stored fields,
   digests, reported costs and lifecycle records. It does not establish the
   absent interpreter or independent executions of the reported baselines.

Additional confirmed accounting defect: the run result at 3460 onward assigns
`real_steps=c["max_authored_steps"]` and `updates=c["max_outer_updates"]`.
Limits are not measurements. The published 4,096 real steps and 16 updates
therefore cannot be accepted as receipt-derived executed counts.

## What remains valid

The original code contains useful typed views, a DSL, temporary code sandboxes,
proposal states, real executions and a hash journal. This audit does not say
that no execution took place. It says the claimed independent acquisition,
fair baseline efficiency and cross-lab transfer do not follow from those runs.
The Stage-A development-selection confound also limits Stage-A generalization
claims. No new success or failure estimate is substituted for the old numbers.

## Preservation and accounting

Original result SHA-256:
`384f050886442e6db07dd0388085a4070f754046e7c38fc654bcc7bfd4e68a02`.
Original audit SHA-256:
`aa1252dc686c53a29a1b313d17d3bb96708264ec2fb15b2a4683dc9f8d172722`.
Original verifier SHA-256:
`9090aeb7156e11b0f50a5c1011308c963f794c1d8972225cc441982e46a7a650`.

The independent v2 preservation tool compares every artifact and tracked binary
at the base against current bytes using streamed Git objects. It does not
execute v1 or rewrite any historical evaluation. Current documentation and the
read-only Lab apply an explicit superseding interpretation; historical data
remain inspectable.

Carry forward **2078.632103455996 s used / 1521.3678965440042 s remaining**,
from the latest original artifact, not the stale earlier master-context ledger.
Boundary unit tests and read-only source audits are not a registered scientific
run. No v2 allocation was created, no final target was generated and no scientific
execution debit was added.

## Tests actually performed

Final command (from the branch root; dependencies are local):

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
  python3 -m pytest -o addopts= -q \
  tests/test_seed_open_primitive_transfer_v2.py \
  tests/test_seed_experimental.py tests/test_learning_lab_sessions.py \
  tests/test_learning_lab_release.py
```

**167 passed in 20.43 s**, none skipped. This is a targeted regression run,
not the entire repository suite and not a scientific execution. Coverage includes
recursive forbidden-field injections, strict JSON/role schemas, unsafe/over-budget
AST rejection, actual public helper selection and patching, opcode ablation,
fixture renaming, failed-call costs, independent receipt reconstruction, missing
grid rejection, three separate OS-restricted subprocesses, denied private-module
reads/network calls, cleanup, legacy host/session/release behavior and HTTP
rendering of the superseding warning.

An earlier broader HTTP test attempted to load every unrelated archived study
through `/api/experimental` and hit its 10-second client timeout: that run had
166 passes and one failure in 41.96 s. The final HTTP test scopes its repository
to the changed route with the actual unchanged v1 artifact. It does not establish
acceptable full-archive latency, nor has a visual browser inspection been claimed.

Independent preservation command:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 scripts/verify_seed_open_primitive_transfer_v2.py
```

It verified **846** historical artifacts/tracked binaries unchanged. The readiness
command `python3 scripts/run_seed_open_primitive_transfer_v2.py --readiness`
exited **2**, correctly reporting `BLOCKED_INCOMPLETE_IMPLEMENTATION` and ten
missing capabilities. Audit record:
`artifacts/seed_open_primitive_transfer_v2_preparation_audit.json`.

## Current repair status

V2 is an **incomplete, unauthorized engineering preparation**. The new processes,
strict messages, bounded expression interpreter, public-helper patch fixture,
receipt reconstruction and preservation checks are implemented. They are not
the requested complete transfer experiment. `--readiness` exits nonzero and
lists the ten missing capabilities. In particular, the private evaluator only
exposes integrity/status, never final generation or scoring. There is no fallback
to the v1 runner, answer-bearing specs, or manual successful sequence.

Consequently there is no scientific Commit 2, Stage-A/B outcome, baseline table
or 17-gate pass claim in this repair revision. The next engineering milestone is
to complete the evaluator-owned generator and private proposal/retention/MDL
pipeline behind the tested process boundary, before enabling any run.

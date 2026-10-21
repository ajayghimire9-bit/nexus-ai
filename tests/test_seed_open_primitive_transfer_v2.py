"""Authored boundary fixtures only. Never generate registered final tasks."""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nexus.seed.primitive_transfer_v2 import contracts as c
from nexus.seed.primitive_transfer_v2.audit_view import CONCLUSION, audited_replay
from nexus.seed.primitive_transfer_v2.bounded import Program
from nexus.seed.primitive_transfer_v2.environment import PublicEnvironment
from nexus.seed.primitive_transfer_v2.learner import Learner
from nexus.seed.primitive_transfer_v2.processes import EnvironmentProcess, LearnerProcess, PrivateEvaluatorProcess
from nexus.seed.primitive_transfer_v2.readiness import review, require_execution_ready

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("independent_v2_verifier", ROOT / "scripts/verify_seed_open_primitive_transfer_v2.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def fixture():
    return {"task_id": "authored-unit-fixture", "signature": "int -> int",
            "source": "def am(x):\n return x-1\ndef bn(x):\n return x*2\ndef cx(x):\n return x+1\ndef dz(x):\n return x*3\ndef entry(x):\n return 0\n",
            "examples": [{"input": 2, "output": 4}, {"input": 3, "output": 6}],
            "action_budget": 64}


def fixture_rule():
    return {"instructions": ["OBSERVE", "GENERATE_TYPED_HYPOTHESES"] +
            ["PREDICT_EFFECTS", "FILTER_INCONSISTENT"] * 8 +
            ["COMPOSE_AST_PATCH", "RUN_VALIDATION", "STOP"]}


@pytest.mark.parametrize("key", sorted(c.FORBIDDEN | {"_private_hidden_tests", "correct-helper-identity"}))
@pytest.mark.parametrize("depth", (0, 1, 4))
def test_recursive_private_injection(key, depth):
    data = {key: "private-canary"}
    for _ in range(depth):
        data = {"public_envelope": [data]}
    with pytest.raises(ValueError, match="private field"):
        c.encode(data)


@pytest.mark.parametrize("raw", (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'))
def test_strict_json(raw):
    with pytest.raises(ValueError):
        c.decode(raw)


@pytest.mark.parametrize("key", ("hiddenInputs", "targetImplementation", "correctPatch"))
def test_camel_case_private_aliases(key):
    with pytest.raises(ValueError):
        c.encode({"observation": {key: "canary"}})


def test_no_python_objects_or_unbounded_messages():
    for value in (lambda: 1, object(), {"x": "z" * 20000}, {"x": [1] * 257}):
        with pytest.raises(ValueError):
            c.encode(value)
    with pytest.raises(ValueError):
        c.request("learner", {"id": True, "command": "next", "payload": {"receipt": None}})


def test_unknown_fields_and_role_capabilities_rejected():
    for role, command in (("learner", "score"), ("environment", "get_private"),
                          ("evaluator", "generate_final")):
        with pytest.raises(ValueError):
            c.request(role, {"id": 0, "command": command, "payload": {}})
    with pytest.raises(ValueError):
        c.task(dict(fixture(), extra="private-canary"))
    with pytest.raises(ValueError):
        c.response("learner", {"id": 0, "ok": False, "payload": {"error": "secret stack trace"}})


@pytest.mark.parametrize("source", (
    "import os\ndef f(x): return x", "def f(x): return open(x)",
    "def f(x): return x.__class__", "def f(x): return x**1000000",
    "def f(x):\n while True: pass", "def f(x): return [0]*1000000000",
    "def f(x): return __import__(x)", "def f(x): return lambda: x",
    "def f(x=open('x')): return x", "def f(x): return globals()",
))
def test_unsafe_or_unbounded_code_rejected(source):
    with pytest.raises((ValueError, SyntaxError)):
        p = Program(source)
        p.call("f", 1)


def test_bounded_recursion_and_comprehensions_and_determinism():
    p = Program("def f(x): return [y*2 for y in x if y>0]")
    assert p.call("f", [-1, 2, 3]) == [4, 6]
    steps = p.steps
    assert p.call("f", [-1, 2, 3]) == [4, 6] and p.steps == steps
    with pytest.raises(ValueError, match="depth"):
        Program("def f(x): return f(x)").call("f", 1)
    with pytest.raises(ValueError, match="budget"):
        Program("def f(x): return [y+1 for y in x]", max_steps=4).call("f", [1, 2, 3])


def run_local(public_task, frozen_rule):
    env = PublicEnvironment(deepcopy(public_task))
    learner = Learner()
    learner.start(deepcopy(public_task), frozen_rule)
    trace = []
    rec = None
    for _ in range(64):
        step = learner.next(rec)
        rec = env.execute(step["action"])
        trace.append((step, rec))
        if step["action"]["kind"] == "STOP":
            return env, trace
    raise AssertionError("nonterminating fixture")


def test_rule_constructs_real_patch_from_public_decoy_calls():
    env, trace = run_local(fixture(), fixture_rule())
    assert env.program.call("entry", 11) == 22
    calls = [s["action"]["payload"]["name"] for s, _ in trace if s["action"]["kind"] == "CALL"]
    assert calls == ["am", "bn", "bn"]
    patch = [s for s, _ in trace if s["action"]["kind"] == "APPLY_AST_PATCH"]
    assert len(patch) == 1 and patch[0]["instruction"] == "COMPOSE_AST_PATCH"
    # The prototype already permits real inline patches without promotion;
    # v1's unpatched no-propose comparator cannot be reused as a fair baseline.
    assert "PROPOSE_PRIMITIVE" not in fixture_rule()["instructions"]
    assert [r["observation"] for _, r in trace if r["action"]["kind"] == "RUN_VISIBLE_TESTS"] == [
        {"status": "ok", "passed": 2, "total": 2}]


def test_removing_filter_opcode_removes_learned_choice():
    rule = fixture_rule()
    rule["instructions"] = [op for op in rule["instructions"] if op != "FILTER_INCONSISTENT"]
    env, trace = run_local(fixture(), rule)
    assert not any(s["action"]["kind"] == "APPLY_AST_PATCH" for s, _ in trace)
    assert env.program.call("entry", 11) == 0


def test_renamed_identifiers_fixture_keeps_success_not_claimed_as_final_replay():
    task = fixture()
    for old, new in (("am", "zz"), ("bn", "yy"), ("cx", "xx"), ("dz", "ww")):
        task["source"] = task["source"].replace(old, new)
    env, _ = run_local(task, fixture_rule())
    assert env.program.call("entry", 11) == 22


def test_environment_cannot_evaluate_private_tests_or_reset_costs():
    env = PublicEnvironment(fixture())
    with pytest.raises(PermissionError):
        env.evaluate()
    with pytest.raises(PermissionError):
        env.restore({})
    env.execute({"kind": "STOP", "payload": {}})
    with pytest.raises(ValueError):
        env.execute({"kind": "INSPECT", "payload": {}})


def test_failed_calls_are_charged_and_receipts_reconstruct():
    env = PublicEnvironment(fixture())
    records = [env.execute({"kind": "CALL", "payload": {"name": "absent", "input": 3}}),
               env.execute({"kind": "RUN_VISIBLE_TESTS", "payload": {}})]
    assert records[0]["observation"]["status"] == "rejected"
    totals = verifier.reconstruct(records)
    assert totals["candidate_executions"] == 3
    assert totals["function_calls"] == 2  # absent function was never entered
    assert totals["visible_tests"] == 2
    assert totals["sandbox_actions"] == 2
    records[0]["costs"]["candidate_executions"] = 0
    with pytest.raises(ValueError):
        verifier.reconstruct(records)


@pytest.mark.parametrize("mutation", ("seed", "family", "method", "metric", "duplicate", "nan", "bool", "str"))
def test_expected_grid_not_derived_from_results(mutation):
    seeds, families, methods = [11, 12], ["a", "b"], ["x", "y"]
    rows = [{"seed": s, "family": f, "method": m, "metrics": {"accuracy": .5}}
            for s in seeds for f in families for m in methods]
    if mutation in ("seed", "family", "method"):
        excluded = rows[0][mutation]
        rows = [r for r in rows if r[mutation] != excluded]
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "metric":
        rows[0]["metrics"] = {}
    else:
        rows[0]["metrics"]["accuracy"] = {"nan": float("nan"), "bool": True, "str": ".5"}[mutation]
    with pytest.raises(ValueError):
        verifier.validate_grid(rows, seeds, families, methods, ["accuracy"])


def test_kernel_unchanged_and_scientific_run_fails_closed():
    result = review(ROOT)
    assert result["kernel_preserved"]
    assert not result["scientific_execution_enabled"]
    assert result["generated_final_tasks"] == 0
    assert len(result["missing_capabilities"]) == 10
    with pytest.raises(RuntimeError, match="blocked"):
        require_execution_ready(ROOT)


def test_rejected_input_does_not_reuse_previous_call_counters():
    p = Program("def f(x): return x+1")
    assert p.call("f", 2) == 3 and p.calls == 1
    with pytest.raises(ValueError):
        p.call("f", [0] * 65)
    assert p.calls == 0


def test_boolean_grid_seed_cannot_alias_integer_seed():
    rows = [{"seed": True, "family": "a", "method": "x", "metrics": {"accuracy": 1}}]
    with pytest.raises(ValueError):
        verifier.validate_grid(rows, [1], ["a"], ["x"], ["accuracy"])


def test_independent_verifier_and_runner_have_no_private_imports():
    for path in (ROOT / "scripts/verify_seed_open_primitive_transfer_v2.py",
                 ROOT / "scripts/run_seed_open_primitive_transfer_v2.py"):
        tree = ast.parse(path.read_text())
        imports = [n.module or "" for n in ast.walk(tree) if type(n) is ast.ImportFrom]
        assert not any("private_evaluator" in n or "open_primitive_transfer" in n for n in imports)
        assert not any(type(n) is ast.Attribute and n.attr.startswith("_private") for n in ast.walk(tree))


def test_gui_audit_does_not_mutate_historical_data():
    old = {"id": "historical", "status": "complete", "open_primitive_transfer": {"overall_pass": True}}
    row = audited_replay(old)
    assert old["status"] == "complete"
    assert "audit_status" not in old["open_primitive_transfer"]
    assert row["failure"] == CONCLUSION
    assert row["status"] == "unsupported_scientific_claim"
    html = (ROOT / "web/learning-lab/experimental.html").read_text()
    assert "UNSUPPORTED_V1_STAGE_B" in html


@pytest.mark.skipif(sys.platform != "darwin", reason="explicit macOS backend required, not a scientific test")
def test_three_fresh_processes_and_message_only_fixture():
    with LearnerProcess(ROOT) as learner, EnvironmentProcess(ROOT) as env, PrivateEvaluatorProcess(ROOT) as evaluator:
        assert len({learner.process.pid, env.process.pid, evaluator.process.pid}) == 3
        assert all(p.process.pid != __import__('os').getpid() for p in (learner, env, evaluator))
        assert evaluator.status()["state"] == "UNAUTHORIZED_IMPLEMENTATION_INCOMPLETE"
        records = [env.start(fixture())]
        step = learner.start(fixture(), fixture_rule())
        for _ in range(64):
            records.append(env.execute(step["action"]))
            if step["action"]["kind"] == "STOP":
                break
            step = learner.next_action(records[-1])
        assert records[-1]["action"]["kind"] == "STOP"
        assert verifier.reconstruct(records)["patches"] == 1
        with pytest.raises(ValueError):
            env._rpc("start", fixture())
        with pytest.raises(ValueError):
            learner._rpc("score", {})
        with pytest.raises(ValueError):
            evaluator._rpc("generate_final", {})
    assert all(p.process.poll() is not None for p in (learner, env, evaluator))


@pytest.mark.skipif(sys.platform != "darwin", reason="explicit macOS backend required")
def test_os_denies_learner_reading_private_module_and_network():
    import shutil
    with LearnerProcess(ROOT) as learner:
        for code in (
            "from pathlib import Path; Path('src/nexus/seed/primitive_transfer_v2/private_evaluator.py').read_text()",
            "import socket; socket.socket().connect(('127.0.0.1',9))",
        ):
            attempt = subprocess.run([shutil.which("sandbox-exec"), "-p", learner.profile,
                                      sys.executable, "-B", "-c", code], cwd=ROOT,
                                     capture_output=True, timeout=5)
            assert attempt.returncode != 0
            assert b"PermissionError" in attempt.stderr


@pytest.mark.skipif(sys.platform != "darwin", reason="explicit macOS backend required")
def test_failure_cleanup():
    actor = None
    with pytest.raises(RuntimeError):
        with LearnerProcess(ROOT) as actor:
            raise RuntimeError("authored failure fixture")
    assert actor.process.poll() is not None


def test_real_read_only_gui_route_supersedes_claim(tmp_path):
    """Exercise HTTP, not only a string fixture; never enable live playgrounds."""
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.request import urlopen
    lab_spec = importlib.util.spec_from_file_location("v2_lab_test", ROOT / "scripts/run_learning_lab.py")
    lab = importlib.util.module_from_spec(lab_spec)
    lab_spec.loader.exec_module(lab)
    # This integration test targets the changed replay branch. Loading every
    # unrelated archive through the legacy endpoint exceeded a 10-second client
    # timeout; that broader performance issue is recorded, not called a pass.
    scoped = tmp_path / "scoped-repository"
    (scoped / "artifacts").mkdir(parents=True)
    (scoped / "AGENTS.md").write_text("Authored read-only HTTP test repository\n")
    (scoped / "artifacts/seed_open_primitive_transfer.json").write_bytes(
        (ROOT / "artifacts/seed_open_primitive_transfer.json").read_bytes())
    lab.ROOT = scoped
    with ThreadingHTTPServer(("127.0.0.1", 0), lab.LabHandler) as server:
        server.experimental_directory = tmp_path / "read-only-test-store"
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/experimental", timeout=10) as response:
                data = json.load(response)
            row = next(r for r in data["experiments"] if "open_primitive_transfer" in r)
            assert row["status"] == "unsupported_scientific_claim"
            assert row["open_primitive_transfer"]["audit_status"] == "UNSUPPORTED_V1_STAGE_B"
            assert row["metrics"] is None
            assert "not establish" in row["failure"]
        finally:
            server.shutdown()
            worker.join(timeout=2)

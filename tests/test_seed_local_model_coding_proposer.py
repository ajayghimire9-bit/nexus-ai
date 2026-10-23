"""Deterministic tests for the local-model coding proposer and workspace route.

Live-model inference is optional. Scripted runtime is never counted as live.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.local_model_patch_proposer import (
    apply_patch,
    parse_model_patch,
    propose_with_runtime,
    validate_patch,
)
from nexus.seed.lab import SeedWorkspace
from nexus.seed.symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop


class ScriptedPatchRuntime:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete(self, prompt, schema, max_tokens=None):
        self.calls.append({"prompt": prompt, "schema": schema, "max_tokens": max_tokens})
        content = self.payloads.pop(0) if self.payloads else '{"edits":[]}'
        return dict(content=content, request_sha256="0" * 64, telemetry=dict(
            inference_ran=True, application_cache_hit=False, input_tokens=12,
            generated_tokens=20, prompt_cache_tokens=None, runtime_timings=None,
            request_wall_s=0.01, creation_request_sha256=None))


def test_validate_and_apply_new_function():
    files = {"math_util.py": "def add(a, b):\n    return a + b\n"}
    payload = parse_model_patch(json.dumps({
        "edits": [{
            "path": "math_util.py",
            "action": "replace",
            "old_text": "def add(a, b):\n    return a + b\n",
            "new_text": "def add(a, b):\n    return a + b\n\ndef midpoint(a, b):\n    return (a + b) / 2\n",
        }],
        "assumptions": ["Public tests define midpoint."],
    }))
    validated = validate_patch(payload, files)
    patched = apply_patch(files, validated)
    assert "def midpoint" in patched["math_util.py"]
    assert validated["semantic_correctness"] == "unverified"


def test_reject_path_escape_and_invalid_syntax():
    files = {"app.py": "def run(x):\n    return x\n"}
    try:
        validate_patch({"edits": [{"path": "../secret.py", "action": "create", "new_text": "x=1\n"}]}, files)
        raise AssertionError("escape allowed")
    except ValueError:
        pass
    try:
        validate_patch({"edits": [{"path": "app.py", "action": "replace", "new_text": "def run(x)\n"}]}, files)
        raise AssertionError("syntax allowed")
    except SyntaxError:
        pass


def test_missing_runtime_is_blocked_not_faked():
    task = AgentTaskPublicView(
        "t", "development", "python_repo", "python", "Add midpoint",
        {"m.py": "def add(a,b):\n    return a+b\n"},
        [{"entry": "m.midpoint", "input": [2, 4], "unpack_args": True, "expected": 3.0}],
    )
    out = propose_with_runtime(None, task, {"symbols": []}, {})
    assert out["status"] == "BLOCKED"
    assert out["proposal"] is None


def test_agent_loop_uses_scripted_model_for_new_function(tmp_path):
    runtime = ScriptedPatchRuntime([json.dumps({
        "edits": [{
            "path": "m.py",
            "action": "replace",
            "new_text": "def midpoint(a, b):\n    return (a + b) / 2\n",
        }],
        "assumptions": ["Uses public midpoint tests only."],
    })])
    task = AgentTaskPublicView(
        "midpoint_dev", "development", "python_repo", "python",
        "Create midpoint(a, b) returning the average.",
        {"m.py": "def noop(x):\n    return x\n"},
        [{"entry": "m.midpoint", "input": [2, 4], "unpack_args": True, "expected": 3.0}],
        budget_steps=4,
    )
    loop = SymbioticAgentLoop(
        tmp_path / "ws",
        local_runtime=runtime,
        allow_acquired_memory=False,
        proposal_sources=("local_model",),
    )
    res = loop.solve(task)
    assert runtime.calls, "model complete() must actually be invoked"
    assert any(c["tool_name"] == "local_model_propose" for c in res["tool_calls"])
    assert res["outcome_category"] in {"solved", "failed"}
    if res["outcome_category"] == "solved":
        assert "def midpoint" in res["final_files"]["m.py"]
        assert res["public_tests_passed"] is True


def test_workspace_coding_loop_cards(tmp_path):
    root = Path(tmp_path) / "coding_workspaces" / "demo_mid"
    root.mkdir(parents=True)
    (root / "m.py").write_text("def noop(x):\n    return x\n", encoding="utf-8")
    (root / "public_tests.json").write_text(json.dumps([
        {"entry": "m.midpoint", "input": [2, 4], "unpack_args": True, "expected": 3.0},
    ]), encoding="utf-8")
    runtime = ScriptedPatchRuntime([json.dumps({
        "edits": [{
            "path": "m.py",
            "action": "replace",
            "new_text": "def midpoint(a, b):\n    return (a + b) / 2\n",
        }],
        "assumptions": ["Public midpoint only."],
    })])
    store = SeedWorkspace(tmp_path, local_runtime=runtime, attach_local_runtime=False)
    sid = store.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    def send(text):
        ident = __import__("uuid").uuid4().hex
        return store.dispatch(dict(session_id=sid, request=dict(op="chat_send", text=text, id=ident)))

    listed = send("List coding workspaces")
    assert "demo_mid" in listed["response"]["text"]
    selected = send("use coding workspace demo_mid")
    assert selected["response"]["chat"]["messages"][-1]["status"] == "reply"
    ran = send("Implement midpoint(a, b) as the average of the two numbers.")
    titles = [c["title"] for c in ran["response"]["chat"]["messages"][-1]["cards"]]
    for needed in ("Model proposal", "Applied workspace edit", "Public-test outcome",
                   "Unverified assumptions", "Final diff"):
        assert needed in titles
    public = next(c for c in ran["response"]["chat"]["messages"][-1]["cards"] if c["title"] == "Public-test outcome")
    assert public["data"]["complete_correctness"] is False

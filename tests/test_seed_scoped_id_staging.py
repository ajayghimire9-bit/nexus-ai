"""Development checks for scoped identification, insertion, staging and repair memory."""
from __future__ import annotations

import ast
import json

from nexus.seed.local_model_patch_proposer import (
    apply_patch,
    insert_after_node,
    locate_symbol,
    parse_model_patch,
    source_sha256,
    validate_patch,
)
from nexus.seed.repair_schema_memory import (
    OrdinaryExactCache,
    PREDECLARED_FAMILIES,
    RepairSchema,
    RepairSchemaStore,
    capture_from_success,
    infer_family,
    transfer_success_rate,
)
from nexus.seed.staging_workspace import StagingWorkspace, inspect_completion_stop
from nexus.seed.symbiotic_agent_loop import AgentTaskPublicView, PythonASTMutationSynthesizer, SymbioticAgentLoop
from nexus.seed.workspace_conversation import score_workspace_reply, workspace_context_header


def test_insert_function_and_after_symbol():
    files = {"math_util.py": "def add(a, b):\n    return a + b\n"}
    digest = source_sha256(files["math_util.py"])
    payload = parse_model_patch(json.dumps({
        "edits": [{
            "path": "math_util.py",
            "action": "insert_after_symbol",
            "symbol": "add",
            "scope": "module",
            "source_sha256": digest,
            "new_text": "def scale(x):\n    return x\n",
        }],
        "assumptions": ["Public tests only."],
    }))
    validated = validate_patch(payload, files)
    patched = apply_patch(files, validated)
    assert "def scale" in patched["math_util.py"]
    ast.parse(patched["math_util.py"])


def test_stale_source_hash_and_duplicate_definition_rejected():
    files = {"m.py": "def add(a, b):\n    return a + b\n"}
    try:
        validate_patch({"edits": [{
            "path": "m.py", "action": "insert_function",
            "new_text": "def extra(x):\n    return x\n",
            "source_sha256": "0" * 64,
        }]}, files)
        raise AssertionError("stale hash accepted")
    except ValueError as exc:
        assert "stale_source" in str(exc)
    try:
        validate_patch({"edits": [{
            "path": "m.py", "action": "insert_function",
            "new_text": "def add(a, b):\n    return a\n",
        }]}, files)
        raise AssertionError("duplicate accepted")
    except ValueError as exc:
        assert "duplicate_definition" in str(exc)


def test_missing_end_lineno_is_handled():
    source = "def add(a, b):\n    return a + b\n"
    node = ast.FunctionDef(
        name="add",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=[ast.Pass()],
        decorator_list=[],
    )
    node.lineno = 1
    if hasattr(node, "end_lineno"):
        node.end_lineno = None
    out = insert_after_node(source, node, "def extra(x):\n    return x\n")
    ast.parse(out)
    assert "def extra" in out
    assert "\ndef extra" in out or out.startswith("def extra")


def test_generic_insert_function_is_not_handwritten_midpoint():
    files = {"stats.py": "def add(a, b):\n    return a + b\n"}
    cands = PythonASTMutationSynthesizer.generate_candidates(
        files, set(), "Create function midpoint(a, b) that returns the arithmetic mean.", {},
    )
    bodies = "\n".join(src["stats.py"] for _desc, src in cands)
    assert "return None" in bodies or "return a" in bodies or "return a + b" in bodies
    assert "(a + b) / 2" not in bodies
    assert "return (a + b) / 2" not in bodies


def test_revision_queue_executes_appended_candidate(tmp_path):
    class Scripted:
        def __init__(self):
            self.calls = []
            self.payloads = [
                json.dumps({"edits": [{
                    "path": "m.py", "action": "replace",
                    "new_text": "def add(a, b):\n    return a + b\n\ndef midpoint(a, b):\n    return a\n",
                }], "assumptions": []}),
                json.dumps({"edits": [{
                    "path": "m.py", "action": "replace",
                    "new_text": "def add(a, b):\n    return a + b\n\ndef midpoint(a, b):\n    return (a + b) / 2\n",
                }], "assumptions": []}),
            ]

        def complete(self, prompt, schema, max_tokens=None):
            self.calls.append(prompt)
            return dict(content=self.payloads.pop(0), request_sha256="0" * 64, telemetry=dict(
                inference_ran=True, application_cache_hit=False, input_tokens=4,
                generated_tokens=8, prompt_cache_tokens=None, runtime_timings=None,
                request_wall_s=0.01, creation_request_sha256=None))

    task = AgentTaskPublicView(
        "rev_q", "development", "python_repo", "python",
        "Create midpoint(a, b).",
        {"m.py": "def add(a, b):\n    return a + b\n"},
        [{"entry": "m.midpoint", "input": [2, 4], "unpack_args": True, "expected": 3.0}],
        budget_steps=4,
    )
    loop = SymbioticAgentLoop(
        tmp_path / "ws", local_runtime=Scripted(), allow_acquired_memory=False,
        proposal_sources=("local_model",), model_revision_budget=2,
    )
    res = loop.solve(task)
    assert len(res["patch_attempts"]) >= 2
    assert any(att["operator_name"].startswith("local_model_revise") for att in res["patch_attempts"])


def test_staging_publishes_only_after_validation():
    staging = StagingWorkspace({"a.py": "def run(x):\n    return x\n", "b.py": "def other(x):\n    return x\n"})
    staging.propose_coordinated("pair", ["a.py", "b.py"])
    staging.apply_edits({"edits": [{
        "path": "a.py", "action": "replace", "old_text": "",
        "new_text": "def run(x):\n    return x + 1\n",
    }]})
    syntax = staging.validate_syntax()
    assert syntax["ok"] is True
    published = staging.publish()
    assert staging.published is True
    assert "return x + 1" in published["a.py"]
    staging2 = StagingWorkspace({"a.py": "def run(x):\n    return x\n"})
    staging2.staged["a.py"] = "def run(x)\n"
    try:
        staging2.publish()
        raise AssertionError("invalid publish")
    except ValueError:
        assert staging2.published is False


def test_completion_stop_is_recorded_not_blamed():
    stop = inspect_completion_stop({
        "content": '{"edits":[]}',
        "truncated": True,
        "stopped_limit": True,
        "tokens_predicted": 256,
        "telemetry": {"generated_tokens": 256, "input_tokens": 40},
    })
    assert stop["truncated"] is True
    assert stop["stop_type"] == "length"
    assert stop["truncation_claimed_as_cause"] is False


def test_repair_schema_fair_transfer_is_not_one_success_equals_100():
    assert "missing_function" in PREDECLARED_FAMILIES
    store = RepairSchemaStore()
    cache = OrdinaryExactCache()
    source_files = {"w.py": "def inside(item):\n    return item['value'] < item['limit']\n"}
    patched = {"w.py": "def inside(item):\n    return item['value'] <= item['limit']\n"}
    family = infer_family("Allow the value equal to the window limit.", [])
    assert family == "comparison_boundary"
    schema = capture_from_success(
        family, "Allow the value equal to the window limit.",
        source_files, patched,
        [{"entry": "w.inside", "input": {"value": 5, "limit": 5}, "expected": True}],
        {"wall_s": 0.01},
    )
    store.remember(schema)
    cache.put("Allow the value equal to the window limit.", source_files, patched)
    later = {"w.py": "def inside(item):\n    return item['score'] < item['cap']\n"}
    reused = store.apply(schema, later)
    assert reused is None
    assert cache.get("new instance", later) is None
    rates = transfer_success_rate([True])
    assert rates["rate"] is None
    assert rates["one_success_is_not_100_percent"] is True
    rates2 = transfer_success_rate([True, False])
    assert rates2["rate"] == 0.5


def test_workspace_header_uses_real_state_not_keyword():
    class Store:
        def list_coding_workspaces(self):
            return ["demo_mid"]

        def runtime_status(self):
            return {"available": False, "reason": "offline"}

    ws = {
        "selected_coding_workspace": "demo_mid",
        "selected_file": None,
        "pending_clarification": {"kind": "coding_workspace", "detail": "Which allowed coding workspace should I use?"},
        "last_correction": None,
    }
    header, meta = workspace_context_header(Store(), ws)
    assert "demo_mid" in header
    assert meta["consumes_model_input_tokens"] is True
    assert meta["generation_tokens"] == 0
    scored = score_workspace_reply("Workspace state (generated from the store, not model output)", ws, meta)
    assert scored["repeats_header_keyword_only"] is True
    scored_ok = score_workspace_reply(
        "Selected resource: demo_mid. Which allowed coding workspace should I use?", ws, meta,
    )
    assert scored_ok["names_selected_resource"] is True
    assert scored_ok["asks_needed_question"] is True
    assert locate_symbol("def add(a, b):\n    return a + b\n", "add") is not None

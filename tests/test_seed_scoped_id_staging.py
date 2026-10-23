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


def test_non_unique_old_text_falls_back_to_complete_file_replace():
    files = {"levy.py": "def apply_levy(amount, rate):\n    return amount\n"}
    validated = validate_patch({"edits": [{
        "path": "levy.py", "action": "replace",
        "old_text": "amount",
        "new_text": "def apply_levy(amount, rate):\n    return amount + rate\n",
    }]}, files)
    patched = apply_patch(files, validated)
    ast.parse(patched["levy.py"])
    assert "amount + rate" in patched["levy.py"]
    try:
        validate_patch({"edits": [{
            "path": "levy.py", "action": "replace",
            "old_text": "amount",
            "new_text": "amount + rate",
        }]}, files)
        raise AssertionError("snippet fallback accepted")
    except ValueError as exc:
        assert "old_text_not_unique" in str(exc)


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


def test_docs_without_doc_id_do_not_crash_the_loop(tmp_path):
    class Boom:
        def complete(self, prompt, schema, max_tokens=None):
            return dict(
                content=json.dumps({"edits": [{
                    "path": "retry.py", "action": "replace",
                    "new_text": "def allowed(item):\n    return item['attempt'] <= item['retry_limit']\n",
                }]}),
                telemetry=dict(inference_ran=True, generated_tokens=4, input_tokens=4, request_wall_s=0.01),
            )

    task = AgentTaskPublicView(
        "retry_doc", "development", "python_repo", "python",
        "Honor the documented retry_limit.",
        {"retry.py": "def allowed(item):\n    return item['attempt'] < item['retry_limit']\n"},
        [{"entry": "retry.allowed", "input": {"attempt": 3, "retry_limit": 3}, "expected": True}],
        [{"title": "retry_limit", "content": "attempt == retry_limit must return True."}],
        budget_steps=2,
    )
    loop = SymbioticAgentLoop(
        tmp_path / "doc", local_runtime=Boom(), allow_acquired_memory=False,
        proposal_sources=("local_model",),
    )
    res = loop.solve(task)
    assert res["outcome_category"] in {"solved", "failed"}
    assert res.get("model_trace")


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


def test_insert_after_class_symbol_stays_inside_class():
    files = {"c.py": "class A:\n    def f(self):\n        return 1\n\ndef helper():\n    return 0\n"}
    validated = validate_patch({"edits": [{
        "path": "c.py", "action": "insert_after_symbol", "symbol": "A",
        "scope": "module", "new_text": "def g(self):\n    return 2\n",
    }]}, files)
    patched = apply_patch(files, validated)
    tree = ast.parse(patched["c.py"])
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "A")
    names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert names == {"f", "g"}
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "g" for n in tree.body)


def test_class_scope_insert_and_duplicate_method():
    files = {"c.py": "class A:\n    def f(self):\n        return 1\n"}
    validated = validate_patch({"edits": [{
        "path": "c.py", "action": "insert_function", "scope": "class:A",
        "new_text": "def g(self):\n    return 2\n",
    }]}, files)
    patched = apply_patch(files, validated)
    tree = ast.parse(patched["c.py"])
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "A")
    names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert names == {"f", "g"}
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "g" for n in tree.body)
    try:
        validate_patch({"edits": [{
            "path": "c.py", "action": "insert_after_symbol", "symbol": "f",
            "scope": "class:A", "new_text": "def f(self):\n    return 3\n",
        }]}, files)
        raise AssertionError("class duplicate accepted")
    except ValueError as exc:
        assert "duplicate_definition" in str(exc)
    assert validated["edits"][0]["source_sha256"] == source_sha256(files["c.py"])


def test_staging_requires_matching_passing_receipt():
    staging = StagingWorkspace({"a.py": "def run(x):\n    return x\n"})
    staging.apply_edits({"edits": [{
        "path": "a.py", "action": "replace", "old_text": "",
        "new_text": "def run(x):\n    return x + 1\n",
    }]})
    try:
        staging.publish()
        raise AssertionError("published without receipt")
    except ValueError as exc:
        assert "passing_receipt" in str(exc)
    staging.run_tests(lambda files: {"all_passed": False, "status": "failed"})
    try:
        staging.publish()
        raise AssertionError("published after failed tests")
    except ValueError as exc:
        assert "passing_receipt" in str(exc)
    staging.run_tests(lambda files: {"all_passed": True, "status": "ok"})
    published = staging.publish()
    assert staging.published is True
    assert "return x + 1" in published["a.py"]
    staging.apply_edits({"edits": [{
        "path": "a.py", "action": "replace", "old_text": "",
        "new_text": "def run(x):\n    return x + 2\n",
    }]})
    assert staging.receipt_matches() is False
    try:
        staging.publish()
        raise AssertionError("published after edit invalidated receipt")
    except ValueError as exc:
        assert "passing_receipt" in str(exc)
    staging.run_tests(lambda files: {"all_passed": True, "status": "ok"})
    staging.staged["a.py"] = "def run(x):\n    return x + 9\n"
    assert staging.receipt_matches() is False
    try:
        staging.publish()
        raise AssertionError("published after in-place mutation")
    except ValueError as exc:
        assert "passing_receipt" in str(exc)
    staging2 = StagingWorkspace({"a.py": "def run(x):\n    return x\n"})
    staging2.staged["a.py"] = "def run(x)\n"
    try:
        staging2.publish()
        raise AssertionError("invalid syntax published")
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


def test_repair_schema_fair_transfer_is_not_one_success_equals_100(tmp_path):
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
    assert reused is not None
    assert "<=" in reused["w.py"]
    assert schema.transformation == "compare_op_swap"
    assert cache.get("new instance", later) is None
    store.save(tmp_path / "repair")
    loaded = RepairSchemaStore.load(tmp_path / "repair")
    assert loaded.apply(next(iter(loaded.schemas.values())), later) is not None
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


def test_per_file_later_prompt_contains_earlier_staged_edit():
    from nexus.seed.local_model_patch_proposer import propose_coordinated_per_file

    class Scripted:
        def __init__(self):
            self.prompts = []

        def complete(self, prompt, schema, max_tokens=None):
            self.prompts.append(prompt)
            marker = "STAGED_FEE_MARKER"
            if "change only fee.py" in prompt:
                body = "def apply_fee(amount, rate):\n    return amount + rate  # " + marker + "\n"
                path = "fee.py"
            else:
                body = "from fee import apply_fee\ndef payable(item):\n    return apply_fee(item['amount'], item['fee'])\n"
                path = "quote.py"
            return dict(
                content=json.dumps({"edits": [{"path": path, "action": "replace", "new_text": body}],
                                    "assumptions": []}),
                request_sha256="0" * 64,
                telemetry=dict(inference_ran=True, generated_tokens=6, input_tokens=4, request_wall_s=0.01),
            )

    runtime = Scripted()
    task = AgentTaskPublicView(
        "pf", "development", "python_repo", "python",
        "Add the fee, then subtract the rebate.",
        {
            "fee.py": "def apply_fee(amount, rate):\n    return amount\n",
            "quote.py": "from fee import apply_fee\ndef payable(item):\n    return apply_fee(item['amount'], item['fee'])\n",
        },
        [],
        budget_steps=2,
    )
    result = propose_coordinated_per_file(runtime, task, {"symbols": []}, {}, None)
    assert result["model_generated_per_file"] is True
    assert result["used_prior_staged_context"] is True
    assert len(runtime.prompts) == 2
    assert "STAGED_FEE_MARKER" in runtime.prompts[1]
    assert result["traces"][1]["used_prior_staged_context"] is True
    assert "STAGED_FEE_MARKER" in result["traces"][1]["prompt_excerpt"]


def test_ordinary_template_and_genuine_capture_without_handwritten_patched():
    from nexus.seed.repair_schema_memory import ordinary_template_apply
    source = {"w.py": "def inside(item):\n    return item['value'] < item['limit']\n"}
    solved = {"w.py": "def inside(item):\n    return item['value'] <= item['limit']\n"}
    schema = capture_from_success(
        "comparison_boundary", "Allow equality at the limit.",
        source, solved,
        [{"entry": "w.inside", "input": {"value": 5, "limit": 5}, "expected": True}],
        {"wall_s": 0.01, "phase": "genuine_source"},
    )
    assert schema is not None
    later = {"g.py": "def ok(item):\n    return item['score'] < item['cap']\n"}
    store = RepairSchemaStore()
    store.remember(schema)
    transferred = store.apply(schema, later)
    assert transferred is not None
    assert "<=" in transferred["g.py"]
    template = ordinary_template_apply("comparison_boundary", later)
    assert template is not None
    assert "<=" in template["g.py"]
    cache = OrdinaryExactCache()
    cache.put("Allow equality at the limit.", source, solved)
    assert cache.get("new request", later) is None

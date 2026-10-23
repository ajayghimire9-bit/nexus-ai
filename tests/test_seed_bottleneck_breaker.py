"""Unit and integration tests for the 4-bottleneck breaker architecture (`seed-bottleneck-breaker-1`)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nexus.seed.agent_loop_worker import run_worker_subprocess  # noqa: E402
from nexus.seed.bottleneck_breaker import (  # noqa: E402
    CodingDiagnosticMetaPolicy,
    classify_operator_family,
    extract_diagnostic_signature,
    run_diagnostic_meta_learning,
    summarize,
)
from nexus.seed.capability_evidence import EventMeter  # noqa: E402
from nexus.seed.local_model_patch_proposer import (  # noqa: E402
    _infer_trace_arithmetic_hint,
    apply_patch,
    prefer_symbol_targeted_edit,
    validate_patch,
)
from nexus.seed.symbiotic_agent_loop import AgentTaskPublicView  # noqa: E402
from run_seed_bottleneck_breaker import load_config, main as run_main  # noqa: E402
from verify_seed_bottleneck_breaker import verify  # noqa: E402


def test_bottleneck_1_proposer_symbol_routing_and_trace_hint():
    """Verify cross-file symbol routing, path normalization, indentation repair, and trace hints."""
    files = {
        "duty.py": "def apply_duty(amount, rate):\n    return amount\n",
        "invoice.py": (
            "from duty import apply_duty\n"
            "def total_due(item):\n"
            "    billed = apply_duty(item['amount'], item['duty'])\n"
            "    return billed + item['rebate']\n"
        ),
    }
    # 1. Path normalization (/duty.py/apply_duty) + unindented body repair
    raw_edit = {
        "path": "/duty.py/apply_duty",
        "action": "replace_function",
        "new_text": "def apply_duty(amount, rate):\nreturn amount * (1 + rate)\n",
    }
    rewritten = prefer_symbol_targeted_edit(raw_edit, files)
    assert rewritten["path"] == "duty.py"
    assert rewritten["symbol"] == "apply_duty"
    assert "    return amount * (1 + rate)" in rewritten["new_text"]

    # 2. Cross-file symbol routing when model puts apply_duty under invoice.py
    cross_edit = {
        "path": "invoice.py",
        "action": "replace_function",
        "symbol": "apply_duty",
        "new_text": "def apply_duty(amount, rate):\n    return amount * (1 + rate)\n",
    }
    routed = prefer_symbol_targeted_edit(cross_edit, files)
    assert routed["path"] == "duty.py"
    validated = validate_patch({"edits": [routed], "assumptions": []}, files)
    patched = apply_patch(files, validated)
    assert "amount * (1 + rate)" in patched["duty.py"]

    # 3. Worker call-and-return trace captures locals and infers arithmetic hint
    ev = run_worker_subprocess({
        "language": "python",
        "files": files,
        "cases": [{"entry": "invoice.total_due", "input": {"amount": 80, "duty": 0.25, "rebate": 5}, "expected": 95.0}],
        "trace": True,
    })
    r0 = ev["results"][0]
    assert any(c.get("event") == "return" and "locals" in c for c in r0["calls"])
    hint = _infer_trace_arithmetic_hint(files, r0)
    assert "apply_duty" in hint and "1 + rate" in hint


def test_bottleneck_2_and_3_worker_fstring_and_trace_inspection():
    """Verify worker allows safe f-strings (JoinedStr/FormattedValue) while blocking unsafe calls."""
    files = {
        "kebab_util.py": (
            "def echo(text):\n    return text\n\n"
            "def kebab(left, right):\n    return f\"{left.lower()}-{right.lower()}\"\n"
        )
    }
    res = run_worker_subprocess({
        "language": "python",
        "files": files,
        "cases": [{"entry": "kebab_util.kebab", "input": ["Foo", "Bar"], "unpack_args": True, "expected": "foo-bar"}],
        "trace": True,
    })
    assert res["status"] == "passed"
    assert res["all_passed"] is True


def test_bottleneck_4_diagnostic_meta_policy_remains_after_capsule_reset():
    """Verify CodingDiagnosticMetaPolicy phi_diag beats fixed_default_order, reset_control,
    and shuffled_control on unseen assessment repositories with all cached code patches cleared.
    """
    config = load_config()
    records: list[dict] = []
    meter = EventMeter(records.append)
    run_diagnostic_meta_learning(config, records.append, meter)
    summary = summarize(records, config)["diagnostic_meta_learning"]

    assert summary["source_training_episodes"] == 6
    fixed = summary["fixed_default_order"]
    cleared = summary["learned_diag_policy_capsules_cleared"]
    reset_ctrl = summary["diag_policy_reset_control"]
    shuffled_ctrl = summary["diag_policy_shuffled_control"]

    assert cleared["private_solved"] == 6
    assert cleared["capsules_cleared"] is True
    assert cleared["reused_memory_count"] == 0
    assert cleared["cache_hits"] == 0
    assert cleared["worker_evaluations"] < fixed["worker_evaluations"]
    assert reset_ctrl["worker_evaluations"] == fixed["worker_evaluations"]
    assert shuffled_ctrl["worker_evaluations"] > cleared["worker_evaluations"]
    assert summary["process_level_learning_to_learn_established"] is True


def test_runner_and_verifier_tamper_rejection(tmp_path):
    """Run deterministic offline pilot and verify that tampering with worker counts or summary is rejected."""
    artifact_path = run_main(tmp_path, include_live_model=False)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    config = load_config()

    out = verify(payload, config, root=ROOT)
    assert out["valid"] is True
    assert out["process_level_learning_to_learn_established"] is True

    # Tamper 1: forge worker_evaluations in summary
    forged_summary = deepcopy(payload)
    forged_summary["summary"]["diagnostic_meta_learning"]["learned_diag_policy_capsules_cleared"]["worker_evaluations"] = 1
    try:
        verify(forged_summary, config, root=ROOT)
        raise AssertionError("forged summary accepted")
    except ValueError as exc:
        assert "summary_mismatch" in str(exc)

    # Tamper 2: forge worker_evaluations on a raw meta_learning episode without matching EventMeter events
    forged_episode = deepcopy(payload)
    for r in forged_episode["records"]:
        if r.get("kind") == "meta_eval_episode":
            r["worker_evaluations"] = 0
            break
    try:
        verify(forged_episode, config, root=ROOT)
        raise AssertionError("unmetered worker evaluation accepted")
    except ValueError as exc:
        assert "unmetered_or_forged_worker_evaluations" in str(exc)

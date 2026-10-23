"""Offline gates for the frozen independent-vs-revision comparison."""
from __future__ import annotations

from pathlib import Path

from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.function_format import prompt_for_format
from nexus.seed.metal_live_compare import (
    AssistantCost, code_prompt, code_spec, grant_from_config, load_config,
    run_comparison,
)
from nexus.seed.metal_model_runtime import MetalGrantEnforcer
from nexus.seed.metal_revision_compare import run_independent_code, run_revision_code

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "configs/seed_metal_live_compare.json")
FAIL = '{"body": "return hall.lower() + \'/\' + gate.lower()"}'
SAFE = (
    '{"body": "return (item[\'hall\'] if \'hall\' in item else \'\').lower() + \'/\' + '
    '(item[\'gate\'] if \'gate\' in item else \'\').lower()"}'
)
SENT_FAIL = "Dockbinding."
SENT_PASS = (
    "Dockbinding lists each stored crate label in the Seed dock catalog in 2026 [seed-compare-1]."
)


def test_fresh_tasks_are_disjoint_from_yard_slip_and_have_no_get():
    rendered, _plan, _task = code_prompt(CONFIG)
    assert ".get" not in rendered
    assert "yard" not in rendered
    assert "slip" not in rendered
    spec = code_spec(CONFIG)
    public = {str(row["input"]) for row in spec["public"]}
    private = {str(row["input"]) for row in spec["private"]}
    assert public.isdisjoint(private)


def test_stubbed_revision_cheaper_path_is_not_a_live_claim():
    spec = code_spec(CONFIG)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
    task = type("T", (), {"request": spec["request"], "public_tests": spec["public"], "docs": []})()
    rendered = prompt_for_format("json_body", task, plan, None)

    def independent_sampler(prompt, plan_row):
        del prompt
        return [FAIL, FAIL, FAIL, SAFE][plan_row.index]

    independent = run_independent_code(independent_sampler, rendered, spec, plan)
    assert independent["n_calls"] == 4
    assert independent["public_passed"] is True

    def revision_sampler(prompt, plan_row):
        return FAIL if plan_row.index == 0 else SAFE

    revision = run_revision_code(revision_sampler, rendered, spec, plan, task)
    assert revision["n_calls"] == 2
    assert CONFIG["stubbed_call2_vs_call4_is_not_live_advantage"] is True


def test_offline_compare_records_unique_outputs_and_cost(tmp_path: Path):
    grant = grant_from_config(CONFIG, ledger_path=str(tmp_path / "metal_ledger.json"))
    enforcer = MetalGrantEnforcer(grant, hardware_probe=lambda: True, rss_reader=lambda: 96.0)
    clock = AssistantCost()

    def code_sampler(prompt, plan):
        if "undefined_names" in prompt or "public_input_keys" in prompt:
            return SAFE
        return [FAIL, FAIL, FAIL, SAFE][plan.index]

    def sentence_sampler(prompt, plan):
        if "Verifier feedback" in prompt or plan.index == 1:
            return SENT_PASS
        return SENT_FAIL

    records = run_comparison(
        CONFIG, tmp_path, grant=grant,
        code_sampler=code_sampler, sentence_sampler=sentence_sampler,
        enforcer=enforcer, clock=clock,
    )
    kinds = [row["kind"] for row in records]
    assert kinds == [
        "code_independent", "code_revision", "sentence_independent", "sentence_revision",
    ]
    assert records[0]["n_calls"] == 4
    assert records[1]["n_calls"] <= 4
    assert records[0]["unique_outputs"] >= 1
    cost = clock.as_dict(0.5)
    assert "user_total_s" in cost
    assert cost["grant_includes"].startswith("MetalGrantEnforcer")

"""Persistent playground compounding; isolated temp brains only."""
from pathlib import Path

from nexus.wave24_quotient_core import WorkMeter
from nexus.wave24_unlimited_playground import PersistentNexusBrain, UnlimitedPythonGround, run_playground


def test_persistent_brain_compounds_skills_across_epochs(tmp_path):
    meter = WorkMeter(limit=400_000, wall_limit=1.)
    first = run_playground(tmp_path / "brain", epochs=3, meter=meter)
    assert first["epochs"] == 3
    assert first["toolbox"]
    assert abs(first["atp_total_sum"] - 100.0) < 1e-6
    assert 0.25 <= first["normalized_atp_entropy"] <= 0.98
    revived = PersistentNexusBrain(tmp_path / "brain", meter=WorkMeter(limit=100_000, wall_limit=1.))
    assert revived.toolbox_path.exists()
    assert (tmp_path / "brain" / "universal_meta_recipes.json").exists()
    assert (tmp_path / "brain" / "symptom_doctor_state.json").exists()
    assert revived.recipes and revived.doctor.rows
    second = run_playground(tmp_path / "brain", epochs=1, meter=WorkMeter(limit=200_000, wall_limit=1.))
    assert second["epochs"] == 1
    assert abs(second["atp_total_sum"] - 100.0) < 1e-6
    assert len(PersistentNexusBrain(tmp_path / "brain").toolbox_names) >= len(first["toolbox"])


def test_unlimited_ground_fingerprints_stdlib_and_toolbox(tmp_path):
    brain = PersistentNexusBrain(tmp_path, meter=WorkMeter(limit=50_000, wall_limit=1.))
    crawled = UnlimitedPythonGround().crawl(brain, meter=brain.meter, max_ops=16)
    assert crawled["operator_count"] >= 8
    assert crawled["fingerprint_ms"] < 5
    assert crawled["roles"]


def _prims():
    return {"operator_neg": lambda x: -x, "math_fabs": lambda x: abs(x), "operator_inv": lambda x: ~x}


def test_compiler_emits_multi_statement_chain_with_stepping_stones():
    from nexus.wave24_unlimited_playground import compile_verified_skill_ast
    plan = dict(kind="chain", steps=["operator_inv", "math_fabs", "operator_neg"])
    source, fn, record = compile_verified_skill_ast("skill_t_chain", plan, lineage={}, primitives=_prims(),
                                                    checks=range(-5, 6))
    assert "v_1 = _apply(operator.inv, x)" in source and "v_3 = _apply(operator.neg, v_2)" in source
    assert "return v_3" in source and fn(4) == -5
    assert record["layer"] == 1 and record["primitive_cost"] == 3 and record["statements"] >= 4


def test_compiler_emits_conditional_and_exception_guard_and_layer_two():
    from nexus.wave24_unlimited_playground import compile_verified_skill_ast, eval_plan
    prims = _prims()
    _, base_fn, base = compile_verified_skill_ast("skill_t_base", dict(kind="chain", steps=["operator_inv", "math_fabs"]),
                                                   lineage={}, primitives=prims, checks=range(-5, 6))
    lineage = {"skill_t_base": base}
    plan = dict(kind="try", body=dict(kind="if", guard="is_negative", then=dict(kind="chain", steps=["skill_t_base"]),
                **{"else": dict(kind="chain", steps=["operator_neg"])}), fallback=dict(kind="chain", steps=["operator_neg"]))
    source, fn, record = compile_verified_skill_ast("skill_t_branch", plan, lineage=lineage, primitives=prims,
                                                    checks=range(-5, 6), callables={"skill_t_base": base_fn})
    assert "if x < 0:" in source and "else:" in source and "except (ValueError, KeyError, ZeroDivisionError" in source
    assert "skill_t_base(x)" in source
    assert record["layer"] == 2 and record["callees"] == ["skill_t_base"]
    assert set(record["constructs"]) == {"chain", "if", "try"}
    # The stored expansion is pure stdlib and reproduces the compiled function.
    import json
    assert "skill_" not in json.dumps(record["pure_plan"])
    assert all(fn(x) == eval_plan(record["pure_plan"], x, prims) for x in range(-9, 10))
    assert fn(-3) == 2 and fn(3) == -3


def test_compiler_rejects_source_that_disagrees_with_its_unfolded_expansion():
    import pytest
    from nexus.wave24_unlimited_playground import compile_verified_skill_ast
    _, base_fn, base = compile_verified_skill_ast("skill_t_base", dict(kind="chain", steps=["operator_neg"]),
                                                   lineage={}, primitives=_prims(), checks=range(-3, 4))
    with pytest.raises(ValueError, match="unfolded primitive expansion"):
        compile_verified_skill_ast("skill_t_wrong", dict(kind="chain", steps=["skill_t_base"]),
            lineage={"skill_t_base": base}, primitives=_prims(), checks=range(-3, 4),
            callables={"skill_t_base": lambda x: x + 1})


def test_playground_reaches_layer_two_with_real_constructs_and_no_false_certificates(tmp_path):
    import ast
    report = run_playground(tmp_path / "brain", epochs=3, meter=WorkMeter(limit=500_000, wall_limit=2.))
    assert report["max_hierarchy_layer"] >= 2 and report["false_certificate_count"] == 0
    assert {"chain", "if", "try"} <= set(report["constructs"])
    brain = PersistentNexusBrain(tmp_path / "brain")
    tree = ast.parse(brain.toolbox_path.read_text())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("skill_")}
    assert any(any(isinstance(s, ast.If) for s in ast.walk(f)) for f in funcs.values())
    assert any(sum(isinstance(s, ast.Assign) for s in ast.walk(f)) >= 2 for f in funcs.values())
    callables = dict(brain.load_toolbox_callables())
    for name, entry in brain.lineage.items():
        pure = brain.unfold_to_primitives(name)
        assert pure == entry["pure_plan"]
    assert abs(report["atp_total_sum"] - 100.0) < 1e-6 and 0.25 <= report["normalized_atp_entropy"] <= 0.98


def test_nursery_skills_hold_no_atp_until_measured_savings(tmp_path):
    report = run_playground(tmp_path / "brain", epochs=8, meter=WorkMeter(limit=2_000_000, wall_limit=5.))
    brain = PersistentNexusBrain(tmp_path / "brain")
    for name in report["nursery"]:
        assert name not in brain.metabolic.atp
    for name in report["graduated"]:
        entry = brain.lineage[name]
        first = entry["uses"][:entry["graduated_after_uses"]]
        assert len(first) >= 2 and all(u["delta_w"] > 0 for u in first)
        assert name in brain.metabolic.delta_w


def test_primitives_raise_and_compiled_try_except_genuinely_fires(tmp_path):
    import pytest
    from nexus.wave24_unlimited_playground import UnlimitedPythonGround
    wrapped = UnlimitedPythonGround._unary(__import__("math").sqrt)
    with pytest.raises(ValueError):
        wrapped(-4)
    with pytest.raises(ValueError):
        wrapped(2)  # irrational result is outside the int domain, not silently x
    assert wrapped(9) == 3
    report = run_playground(tmp_path / "brain", epochs=4, meter=WorkMeter(limit=1_000_000, wall_limit=3.))
    assert report["except_fired_skills"] and report["false_certificate_count"] == 0
    brain = PersistentNexusBrain(tmp_path / "brain")
    fns = dict(brain.load_toolbox_callables())
    name = report["except_fired_skills"][0]
    entry = brain.lineage[name]
    assert entry["plan"]["kind"] == "try"
    body = entry["plan"]["body"]["steps"][0]
    x = entry["except_fired_on"][0]
    crawled = UnlimitedPythonGround().crawl(brain, meter=WorkMeter(limit=200_000, wall_limit=2.))
    with pytest.raises(ValueError):
        {**crawled["primitives"], **fns}[body](x)
    assert isinstance(fns[name](x), int)  # recovered through the except branch


def test_legacy_swallowing_toolbox_is_archived_not_rebound(tmp_path):
    (tmp_path / "evolved_toolbox.py").write_text("def _apply(fn, value):\n    return value\n")
    brain = PersistentNexusBrain(tmp_path)
    assert brain.archived_legacy is not None and (brain.archived_legacy / "evolved_toolbox.py").exists()

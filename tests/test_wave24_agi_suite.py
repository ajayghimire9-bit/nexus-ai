"""Eight-gap suite mechanisms: unwrapped faults, cost accounting, certificates, verifier."""
import copy
import json
import math
import random
import sys
from pathlib import Path

import pytest

from nexus.wave24_agi_suite import (BoundedProjector, DocstringRetriever, ForwardWorldModel, LawLibrary,
    NexusLearner, UNIQUE, abstract, grade, grounded_plan_solve, phase, recovery_tool, sign_test, solve,
    spearman, verify_witness)
from nexus.wave24_domains import (generate_task, ingest_stdlib, nested_domain, series_domain, source_domains,
    str_domain, target_domains, task_bank, vkey)
from nexus.wave24_quotient_core import WorkMeter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_domains_are_structurally_disjoint_and_tools_raise_real_faults():
    names = {d.name for d in (*source_domains(), *target_domains())}
    assert len(names) == 8 and len(target_domains()) == 5
    series = series_domain()
    check = next(t for t in series.tools if t.name == "check")
    with pytest.raises(ValueError):
        check([1.0, float("nan")])          # no wrapper swallows the fault
    tools = ingest_stdlib()
    assert len(tools) >= 8 and all(t.layer == 0 for t in tools)


def test_teacher_answers_never_reach_the_solver():
    import inspect
    params = set(inspect.signature(solve).parameters)
    assert "answer" not in params and "teacher" not in params
    t = task_bank(str_domain(), 5, (2,), 1)[0]
    blind = copy.copy(t)
    object.__setattr__(blind, "answer", "SENTINEL-NOT-USED")
    r1, r2 = solve(t, str_domain().tools, budget=3000), solve(blind, str_domain().tools, budget=3000)
    assert r1.status == r2.status and vkey(r1.answer) == vkey(r2.answer) and r1.work == r2.work


def test_every_tool_application_is_charged_and_budget_is_enforced():
    d = str_domain()
    t = task_bank(d, 9, (3,), 1)[0]
    r = solve(t, d.tools, budget=50)
    assert r.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" and r.work <= 51


def test_certificates_are_re_executed_and_a_forged_witness_is_rejected():
    d = str_domain()
    t = task_bank(d, 3, (2,), 1)[0]
    r = solve(t, d.tools, budget=6000)
    assert r.status == UNIQUE and r.certificate_valid is True
    wrong = [x for x in d.tools if x.name not in r.witness][:1]
    assert verify_witness(t, tuple(wrong), r.answer) is False


def test_recovery_composite_catches_a_real_exception():
    d = series_domain()
    tools = {t.name: t for t in d.tools}
    rt = recovery_tool(tools["check"], tools["drop_nan"])
    assert rt([1.0, float("nan"), 2.0]) == [1.0, 2.0] and rt.layer == 1 and rt.kind == "recovery"


def test_bounded_projector_cost_is_bounded_on_large_inputs():
    p = BoundedProjector(k=256)
    big = p.project(list(range(10_000)))
    assert big["mass"] == 10_000 and big["sampled"] is True
    small = p.project([1, 2, 3])
    assert small["sampled"] is False and small["mass"] == 3


def test_forward_world_model_predicts_type_before_execution():
    d = nested_domain()
    m = ForwardWorldModel()
    probes = d.inputs(random.Random(1), 10)
    m.fit_probes(d.tools, probes, WorkMeter(limit=10**6))
    size = next(t for t in d.tools if t.name == "size")
    pred = m.predict(size, [abstract(probes[0])], WorkMeter(limit=10))
    assert pred[0][0] == {"int"}
    keys = next(t for t in d.tools if t.name == "keys")
    assert not m.can_match(keys, [abstract(probes[0])], [("int", 2)], WorkMeter(limit=10))


def test_law_library_finds_involution_and_prunes_redundant_step():
    d = str_domain()
    forces = {t.name: "F_X" for t in d.tools}
    lib = LawLibrary().discover(list(d.tools), d.inputs(random.Random(2), 6), forces, WorkMeter(limit=10**6))
    assert "reverse" in lib.involution and "lower" in lib.idempotent
    assert lib.prune("reverse", "reverse") and lib.prune("lower", "lower")


def test_phase_flags_corruption():
    assert phase([1.0, float("nan")])[1] is True and phase({"a": None})[2] is True


def test_docstring_retrieval_grounds_degraded_text():
    d = str_domain()
    r = DocstringRetriever(d.tools)
    assert "lower" in r.rank("please convert letters lower case now", k=2)


def test_learner_meta_decisions_are_logged_and_learning_is_charged():
    L = NexusLearner(seed=1)
    m = WorkMeter(limit=10**9)
    for d in source_domains():
        L.enter(d, m)
        for t in task_bank(d, 1, (1, 2), 3):
            L.solve(t, budget=3000)
        L.close_domain(m)
    assert m.counts["law_validation_work_units"] > 0 and m.counts["world_model_probe_work_units"] > 0
    assert L.law_evidence and L.training_work > 0


def test_sign_test_and_spearman():
    assert sign_test([1] * 10)["p_value"] < 0.01 and sign_test([1, -1])["p_value"] == 1.0
    assert spearman([0, 1, 2, 3], [4, 3, 2, 1]) == pytest.approx(-1.0)


def test_verifier_fails_on_a_false_certificate(tmp_path):
    from scripts.run_wave24_agi_gap_suite import main as run
    from scripts.verify_wave24_agi_gap_suite import verify
    out = tmp_path / "suite.json"
    run(["--seeds", "3", "--out", str(out)])
    payload = json.loads(out.read_text())
    assert verify(payload)["gates"]["zero_false_certificates"] is True
    payload["gaps"]["gap7"][0]["rows"][0]["certificate_valid"] = False
    result = verify(payload)
    assert result["gates"]["zero_false_certificates"] is False and not result["all_passed"]
    with pytest.raises(SystemExit):
        run(["--seeds", "3", "--out", str(out)])   # one-use: refuses to overwrite

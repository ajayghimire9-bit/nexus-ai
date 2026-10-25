"""Wave 24 v2 mechanisms: skeletons, exact loop cost, wake-sleep gate, real-code repair, semantics, laws."""
import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus.wave24_agi_suite import NexusLearner, apply_tool, grade, macro_tool
from nexus.wave24_code_repair import (Meter, Program, enumerate_mutations, repair, run_tests, split_names,
                                      split_tests)
from nexus.wave24_domains import graph_domain, series_domain, str_domain
from nexus.wave24_quotient_core import WorkMeter
from nexus.wave24_semantic_spec import SemanticSpecParser, discover_law, law_tasks, solve_spec, spec_tasks
from nexus.wave24_skeletons import SkeletonSpec, fitted_constants, instantiate, skeleton_library
from nexus.wave24_wake_sleep import WakeSleep, generic_tool, idiom_library, idiom_stream


def test_skeleton_parameters_come_only_from_public_inputs():
    consts = fitted_constants([[1.0, 5.0], [9.0]])
    assert set(consts) <= {1.0, 5.0, 9.0, 1, 2}
    f = instantiate(SkeletonSpec("FILTER", ("gt",), (4.0,)))
    assert f([1.0, 5.0, 9.0]) == [5.0, 9.0]
    with pytest.raises(TypeError):
        instantiate(SkeletonSpec("FOLD", ("sum",), ()))(7)   # scalar: a real fault, not swallowed


def test_iterate_and_macro_costs_are_exact_not_static():
    d = str_domain()
    by = {t.name: t for t in d.tools}
    it = instantiate(SkeletonSpec("ITERATE", ("strip",), ()), by)
    m = WorkMeter(limit=10**6)
    apply_tool(it, ["  a  "], m)
    assert m.total == 2                     # strip once, then once more to detect stability
    mac = macro_tool({it.name: it, "lower": by["lower"]}, (it.name, "lower"))
    m2 = WorkMeter(limit=10**6)
    apply_tool(mac, ["  a  "], m2)
    assert m2.total == 3 and mac.layer == 2


def test_wake_sleep_promotes_only_with_shadow_gain_and_charges_sleep():
    d = graph_domain()
    stream = idiom_stream(d, 101, 18, idiom_library(d, 1))
    L = NexusLearner(seed=1, skeleton_mode="all", invent=False)
    L.enter(d, WorkMeter(limit=10**12))
    ws = WakeSleep(L, sleep_every=6)
    for t in stream:
        ws.wake(t)
    assert ws.sleep_work > 0
    for p in ws.promotions:
        assert p["gain"] > 0 and p["replay"] >= 2
    for r in ws.rejections:
        assert r["gain"] <= 0 or r["lost"] > 0 or r["containing"] < 2   # exactly the gate rule


def test_generic_tools_carry_no_domain_primitives():
    assert generic_tool(instantiate(SkeletonSpec("MAP", ("abs",), ())))
    by = {t.name: t for t in str_domain().tools}
    assert not generic_tool(instantiate(SkeletonSpec("ITERATE", ("strip",), ()), by))


def test_repair_sandbox_blocks_imports_and_cuts_infinite_loops():
    code = compile("import os\ndef f(x):\n    return x\n", "<candidate>", "exec")
    assert run_tests(code, "f", [[[1], 1]], Meter(10**6)) == [False]
    loop = compile("def f(x):\n    while True:\n        x += 1\n", "<candidate>", "exec")
    m = Meter(10**9)
    assert run_tests(loop, "f", [[[1], 1]], m) == [False] and m.total > 1000


def test_real_quixbugs_gcd_is_repaired_and_graded_on_hidden_tests():
    assert "gcd" in split_names("dev")
    p = Program.load("gcd")
    pub, hid = split_tests(p, 1)
    r = repair(p, pub, hid, learned=True, prior={})
    assert r.plausible and r.correct and r.edit_kind == "swap_args"


def test_semantic_parser_composes_clauses_and_extracts_edge_oracles():
    spec = SemanticSpecParser().parse("Count how many valid readings there are, discarding NaN values. If the list is empty return 0.")
    assert spec.stages == [["KEEP_FINITE"], ["FOLD(count)"]] and spec.edge_cases == [([], 0)]
    spec2 = SemanticSpecParser().parse("Report the average of the readings, excluding negative ones, rounded to two decimals.")
    assert spec2.stages == [["KEEP_NONNEG"], ["FOLD(mean)"]] and spec2.rounding == 2


def test_semantic_specs_solve_with_hidden_edge_cases():
    tasks = spec_tasks(1)
    assert sum(bool(solve_spec(t).get("correct")) for t in tasks) >= len(tasks) - 1


def test_law_discovery_recovers_power_and_exponential_laws():
    tasks = {t["name"]: t for t in law_tasks(1)}
    assert discover_law(tasks["kepler_third_law"])["form"] == "power"
    assert discover_law(tasks["radioactive_decay"])["form"] == "exponential"
    assert discover_law(tasks["kepler_third_law"])["correct"]


def test_v2_verifier_fails_on_tampered_false_certificate(tmp_path):
    from scripts.run_wave24_agi_gap_suite import main as run
    from scripts.verify_wave24_agi_gap_suite import verify
    out = tmp_path / "v2.json"
    run(["--suite", "v2", "--seeds", "5", "--out", str(out)])
    payload = json.loads(out.read_text())
    assert verify(payload)["gates"]["v2_zero_false_certificates"] is True
    payload["gaps_v2"]["gap4_6"][0]["rows"][0]["certificate_valid"] = False
    assert verify(payload)["gates"]["v2_zero_false_certificates"] is False

"""MI-2 unit tests (fast; no discovery, no evaluation data; development seeds only)."""
import importlib.util
import random
from pathlib import Path

import pytest

from nexus import mi2_learner as M2
from nexus import mi2_lpl as L2
from nexus import mi2_seeds  # noqa: F401
from nexus import mi_learner as ML
from nexus import mi_lpl as LP
from nexus import mi_ocean as M
from nexus import seed_registry as R


def test_empty_library_mutation_is_exactly_the_original_operator():
    rnd = random.Random(5)
    progs = [LP.random_program(rnd) for _ in range(20)] + [LP.SEED_BASELINE]
    for k, p in enumerate(progs):
        a = LP.mutate(p, random.Random(k))
        b = L2.mutate_lib(p, random.Random(k), [], 0.3)
        assert a == b


def test_library_insertion_copies_blocks_of_the_accepted_procedure_and_stays_executable():
    lib = [M2.A5_PROG]
    blocks = L2.library_blocks(lib)
    rnd = random.Random(1)
    seen = 0
    for k in range(80):
        p, e = L2.mutate_lib(LP.SEED_BASELINE, rnd, lib, 1.0)
        assert e.startswith("library_insert")
        d, st = LP.hypothesis_space(p, {"obs": [2.0, 5.0, 3.0], "n_trans": 6})
        assert d[0] == LP.ACC and st["steps"] <= LP.STEP_CAP
        seen += any(p["main"][i:i + len(b)] == b for b in blocks for i in range(len(p["main"])))
    assert seen > 0


def test_witness_domains_hold_the_truth_and_discovery_refuses_them():
    ep = M.Episode(25403, "SUBH")
    truth = {LP._sig(g) for g in M2.true_updates(ep)}
    assert truth <= {LP._sig(g) for g in M2.witness_domain(ep, "end")}
    spec = importlib.util.spec_from_file_location("mi2_discover", Path(__file__).resolve().parents[1] / "scripts/mi2_discover.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.evaluate(M2.witness_fn(ep, "end"), [])


def test_control_domains_and_restricted_parameter_space():
    ctx = {"obs": [3.0, 8.0, 13.0], "n_trans": 7}
    a5 = {LP._sig(n) for n in LP.hypothesis_space(M2.A5_PROG, ctx)[0]}
    for fam in ("MUL", "SUBH"):
        assert LP._sig(M.FAMILIES[fam](random.Random(0))) in a5
    assert LP._sig(("b", "+", LP.ACC, ("const", 5))) in a5                    # evidence-mined difference constant
    d6, _ = M2.a6_domain()(ctx)
    assert d6[0] == LP.ACC and len(d6) <= LP.POOL_CAP
    for b, k, _ in M2.PARAMS_GRID:
        d, _ = M2.params_domain(b, k)({})
        assert d[0] == LP.ACC and {n[1] for n in d if n[0] == "b"} <= {"+", "-"}


def test_cpu_cap_and_search_log():
    ep = M.Episode(25403, "SUBH")
    out, st = M2.full_space(ep, M2.a6_domain(), ep.seed, cap_s=0.05)
    assert out is None and st["outcome"] in ("cap_timeout", "register_search_failed") and st["cpu_s"] < 2.0
    ep = M.Episode(25403, "SUBH")
    out, st = M2.full_space(ep, M2.witness_fn(ep, "min"), ep.seed, cap_s=10.0)
    assert ML.score(ep, out)["exact"] and st["searches"] and st["explained"] > 0


def test_mi2_seed_ranges_are_fresh_and_one_use():
    for k in ("val", "test", "btest"):
        assert ("mi2", k) in R.ONE_USE
    assert not set(R.REGISTRY[("mi2", "test")]) & set(R.REGISTRY[("mi", "test")])

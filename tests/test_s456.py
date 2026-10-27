"""Stages 4-6 (NOT LOCKED): evaluator independence, exactly-once contract, check sensitivity, incident repair, library rules.
Uses de2 dev / src worlds only (no val / test world is generated here)."""
import ast, json, tempfile
from pathlib import Path

import pytest

from nexus import s456_seeds  # noqa: F401
from nexus import s4_checks as C, s4_env as E, s4_evaluator as V, s4_template as T, s5_incidents as I, s5_ops as O, s6_library as SL

ROOT = Path(__file__).resolve().parents[1]


def _imports(mod):
    out = set()
    for n in ast.walk(ast.parse((ROOT / f"src/nexus/{mod}.py").read_text())):
        if isinstance(n, ast.ImportFrom) and n.module:
            out |= {f"{n.module}.{a.name}" for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
    return out


def test_isolation():
    assert not any(x.startswith("nexus") for x in _imports("s4_evaluator"))
    assert not any(x.startswith("nexus") for x in _imports("s4_checks"))
    agent_side = _imports("s4_agent") | _imports("s4_checks") | _imports("s4_template") | _imports("s6_library")
    assert not any(k in x for x in agent_side for k in ("s4_evaluator", "s4_env", "s5_incidents"))


def test_withheld_classes_absent_outside_test():
    for split, seed in (("dev", 931), ("src", 921)):
        w = E.make_world(seed, split)
        assert not w["withheld"] and w["features"]["partition2_keys"] == 0
        assert not set(n for n, _ in I.schedule(seed, split)) & set(I.WITHHELD)


@pytest.fixture(scope="module")
def world():
    w = E.make_world(932, "dev")
    enc = E.encode(w, "build")
    d = Path(tempfile.mkdtemp())
    E.write_log(enc, d / "vis", E.VISIBLE)
    return w, enc, d


def _bundle(d, w, choice, tag):
    b = d / tag
    b.mkdir(exist_ok=True)
    (b / "pipeline.py").write_text(T.emit(choice))
    (b / "config.json").write_text(json.dumps(T.config_from_spec(w["spec"])))
    return b


def test_evaluator_passes_correct_and_detects_at_most_once(world):
    w, enc, d = world
    cfg = T.config_from_spec(w["spec"])
    (d / "bad.json").write_text(json.dumps(dict(cfg, fx={k: v * 10 for k, v in cfg["fx"].items()})))
    ok = V.evaluate(enc["truth"], V.run_protocol(_bundle(d, w, T.correct_choice(), "ok"), enc, d / "e1", E.write_log, E.retention, d / "bad.json"))
    assert ok["correct"] and ok["eo_failures"] == 0 and ok["eo_trials"] > 10 and ok["rollback_ok"]
    bad = V.evaluate(enc["truth"], V.run_protocol(_bundle(d, w, dict(T.correct_choice(), commit_protocol="offsets_first"), "of"),
                                                  enc, d / "e2", E.write_log, E.retention, d / "bad.json"))
    assert not bad["correct"] and "EXACTLY_ONCE_VIOLATION" in bad["reasons"]


def test_nexus_suite_catches_every_wrong_option_standard_suite_does_not(world):
    w, enc, d = world
    spec, full = w["spec"], d / "vis/log"
    assert all(x["ok"] for x in C.verify(_bundle(d, w, T.correct_choice(), "c"), spec, full, d / "vc", C.Runner()))
    missed_by_standard = 0
    for dd, opts in T.DECISIONS.items():
        if dd in ("partition_discovery", "ts_format"):
            continue                                          # withheld-class decisions: correct in dev worlds
        for o in opts:
            if o in T.CORRECT[dd]:
                continue
            b = _bundle(d, w, dict(T.correct_choice(), **{dd: o}), f"{dd}_{o}")
            assert not all(x["ok"] for x in C.verify(b, spec, full, d / f"v_{dd}_{o}", C.Runner())), (dd, o)
            missed_by_standard += all(x["ok"] for x in C.verify(b, spec, full, d / f"s_{dd}_{o}", C.Runner(), suite=C.STANDARD))
    assert missed_by_standard >= 5


def test_restart_does_not_repair_corruption_nexus_does():
    w = E.make_world(931, "dev")
    res = {}
    for name, op in (("conv", O.ConventionalOps("c")), ("nexus", O.NexusOps("n", detector="fixed_ratio"))):
        enc, incs = I.ops_world(w, "dev", 931, [("partial_deploy_corruption", 10)])
        d = Path(tempfile.mkdtemp())
        b = d / "b"
        b.mkdir()
        (b / "pipeline.py").write_text(T.emit(T.correct_choice()))
        (b / "config.json").write_text(json.dumps(T.config_from_spec(w["spec"])))
        env, service = O.run_ops(enc, incs, d / "w", b, op)
        res[name] = I.evaluate_ops(enc["truth"], env, service)
    assert res["conv"]["service_restored"] and not res["conv"]["data_ok"]
    assert res["nexus"]["correct"]


def test_library_rules():
    lib = SL.Library([], frozen=False)
    with pytest.raises(RuntimeError):
        lib.observe(["x"], ())
    procs = [dict(id="build:fx", kind="build", decision="fx", option="table", preconditions=["multi_currency"], agreement=1.0,
                  est_saving_cpu_s=2.0, active=True)]
    adm = SL.admit(procs, {}, dict(retrieval_cpu_s=0.001, applicability_cpu_s=0.001), maintenance_cpu_s=10, expected_uses=12)
    assert adm[0]["active"]
    adm = SL.admit(procs, {"build:fx": 1}, dict(retrieval_cpu_s=0.001, applicability_cpu_s=0.001), 10, 12)
    assert not adm[0]["active"]
    pl = SL.placebo([dict(p, active=True) for p in procs])
    assert pl[0]["option"] != "table" and pl[0]["preconditions"] == ["multi_currency"]

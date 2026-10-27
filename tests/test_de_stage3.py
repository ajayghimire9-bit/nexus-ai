"""Stages 2-3 (NOT LOCKED): evaluator independence, generator fault coverage, invariant sensitivity on dev projects, matched
arms. Uses development projects only (seed registry de1/dev); no validation or test project is generated here."""
import ast, json, tempfile
from pathlib import Path

import pytest

from nexus import de_agent as A, de_checks as C, de_env as E, de_evaluator as V, de_template as T

ROOT = Path(__file__).resolve().parents[1]


def _imports(mod):
    tree = ast.parse((ROOT / f"src/nexus/{mod}.py").read_text())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            out |= {f"{n.module}.{a.name}" for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
    return out


def test_evaluator_and_agent_are_isolated():
    ev = _imports("de_evaluator")
    assert not any(x.startswith("nexus") for x in ev), ev                       # evaluator: stdlib only
    ag = _imports("de_agent") | _imports("de_checks") | _imports("de_template")
    assert not any(k in x for x in ag for k in ("de_evaluator", "de_env")), ag   # agent side never sees evaluator / truth
    assert not any(x.startswith("nexus") for x in _imports("de_checks"))        # invariants ship standalone in bundles


@pytest.fixture(scope="module")
def projects():
    out = []
    for seed in (901, 902):
        p = E.make_project(seed, "dev")
        w = Path(tempfile.mkdtemp())
        E.write_project(p, w / "inputs", w / "truth")
        out.append((p, w, json.loads((w / "truth/truth.json").read_text())))
    return out


def test_every_fault_class_is_visible_and_held_out(projects):
    for p, _, truth in projects:
        v, h = truth["features"]["visible"], truth["features"]["batch3"]
        assert min(v.values()) >= 1 and min(h.values()) >= 0 and h["out_of_order_keys"] >= 1 and h["late_delivered_events"] >= 1


def test_coverage_asks_exactly_the_genuine_questions(projects):
    for p, w, truth in projects:
        spec = json.loads((w / "inputs/docs/spec.json").read_text())
        qs = {f"{t}:{v}" for t, v in C.coverage(spec, [w / "inputs/batch1", w / "inputs/batch2"])}
        assert qs == set(truth["answers"])


def _bundle(w, spec, choice, clar, tag):
    b = w / f"b_{tag}"
    b.mkdir(exist_ok=True)
    (b / "pipeline.py").write_text(T.emit(choice))
    (b / "config.json").write_text(json.dumps(T.config_from_spec(spec, clar)))
    return b


def test_invariants_pass_the_correct_pipeline_and_catch_every_single_wrong_option(projects):
    """For each decision with a project-independent right answer, every wrong option (alone) fails verify() and the failing
    check implicates that decision; the correct pipeline passes every check (no false alarm)."""
    for p, w, truth in projects:
        spec = json.loads((w / "inputs/docs/spec.json").read_text())
        batches = [w / "inputs/batch1", w / "inputs/batch2"]
        clar = dict(truth["answers"])
        r = C.verify(_bundle(w, spec, T.correct_choice(), clar, "ok"), spec, batches, w / "v_ok", C.Runner())
        assert all(x["ok"] for x in r) and [x["check"] for x in r] == C.CHECK_NAMES[1:], [x for x in r if not x["ok"]]
        for d, right in T.CORRECT_SHAPE.items():
            for o in T.DECISIONS[d]:
                if o == right:
                    continue
                r = C.verify(_bundle(w, spec, dict(T.correct_choice(), **{d: o}), clar, f"{d}_{o}"), spec, batches,
                             w / f"v_{d}_{o}", C.Runner())
                bad = next((x for x in r if not x["ok"]), None)
                assert bad is not None, f"{p['project']}: {d}={o} passed every invariant"
                assert d in bad["implicate"] or bad["check"] == "runs_without_error", (d, o, bad)


def test_arms_share_generator_proposer_and_caps():
    a, b = A.Proposer("dev-901"), A.Proposer("dev-901")
    assert a.perm == b.perm and A.Proposer("dev-902").perm != a.perm
    s = A.Proposer("dev-901", best_case=True)
    assert all(s.perm[d][0] == T.CORRECT_SHAPE[d] for d in T.CORRECT_SHAPE)
    assert set(A.ARMS) == {"Conventional_Agent_No_NEXUS_Checks", "NEXUS_Engineer_No_History"}


def test_evaluator_reference_is_not_the_pipeline(projects):
    """Correct pipeline == reference on every visible and held-out batch, and a guessed rule is caught even when lucky."""
    p, w, truth = projects[0]
    spec = json.loads((w / "inputs/docs/spec.json").read_text())
    sh = V.Stakeholder(truth)
    clar = {q: sh.ask(*q.split(":", 1)) for q in truth["answers"]}
    b = _bundle(w, spec, T.correct_choice(), clar, "eval_ok")
    r = V.evaluate(truth, V.run_protocol(b, w / "inputs", w / "e_ok"), sh.log)
    assert r["correct"] and r["heldout_batch_ok"] and r["recovered"] and r["idempotent"], r["reasons"]
    lucky = dict(T.correct_choice(), carrier_uncovered=truth["answers"]["carrier_volume:CANCELLED"])
    r = V.evaluate(truth, V.run_protocol(_bundle(w, spec, lucky, {}, "lucky"), w / "inputs", w / "e_l"), [])
    assert not r["correct"] and "UNASKED_AMBIGUITY" in r["reasons"]

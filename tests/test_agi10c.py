"""Phase 10C unit tests (no experiment is executed: no project is built, no search runs)."""
import json
import re
from pathlib import Path

import pytest

from nexus.de_phase10c import lineage10c as LC, manifest10c as MC, search10c as S10
from nexus.de_phase10c.rng10c import rng, seed_of

SRC = Path(__file__).resolve().parents[1] / "src/nexus/de_phase10c"


def test_seeds_are_numeric_only():
    assert seed_of(0, 3, 92001) == seed_of(0, 3, 92001) != seed_of(1, 3, 92001)
    with pytest.raises(TypeError):
        seed_of("rep0", 3)
    with pytest.raises(TypeError):
        seed_of(True, 3)
    assert rng(0, 1, 2).random() == rng(0, 1, 2).random()


def test_no_name_reaches_a_seed():
    for f in SRC.glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|seed_of|Random)\([^)]*name", s), f


def _steps():
    tok = lambda a, s: [f"op:{a}", f"op:{a}|pos:last", f"op:{a}|ev:{s}"]  # noqa: E731
    out = []
    for j in range(12):
        recs = [dict(stage=0, ctx=["pos:last", "fail:unique"], sym=["fail:unique", "here:clean"], pos=tok("dedup_latest", "fail:unique"),
                     negs=[tok(o, "fail:unique") for o in ("filter_file", "cast_fix", "exclude_value")],
                     abs=["dedup_latest", ["key", ["dupes", "text"]], ["order", ["int"]]]),
                dict(stage=0, ctx=["pos:last", "diff:extra_rows"], sym=["diff:extra_rows", "here:clean"], pos=tok("exclude_value", "diff:extra_rows"),
                     negs=[tok(o, "diff:extra_rows") for o in ("filter_file", "dedup_latest")], abs=["exclude_value", ["col", ["lowcard", "text"]], ["value", "'D'"]])]
        out.append([f"P6.P{1 + j % 7}.x.{j}", recs])
    return out


def _learner(tmp_path, name):
    L = LC.Learner(0, name, {"records": [], "weights": {}, "support": {}}, tmp_path / name, 1e18, tmp_path / name / "out", MC.train(0))
    L.mem["steps"] = _steps()
    L.mem["de"]["skills"] = {"L0": dict(edits=[["dedup_latest", ["key", ["dupes"]], ["order", ["int"]]], ["exclude_value", ["col", ["text"]], ["value", "'D'"]]],
                                         pre=["fail:unique"], canonical="c0")}
    return L


def test_renaming_a_clone_gives_identical_samples_and_splits(tmp_path):
    a, b = _learner(tmp_path, "rep0"), _learner(tmp_path, "rep0.clone.M_edit_renamed")
    a.train_rankers()
    b.train_rankers()
    assert json.dumps(a.mem["guides"], sort_keys=True) == json.dumps(b.mem["guides"], sort_keys=True)
    la = [json.loads(x) for x in (a.out / "rep0.ranker.jsonl").read_text().splitlines()]
    lb = [json.loads(x) for x in (b.out / "rep0.clone.M_edit_renamed.ranker.jsonl").read_text().splitlines()]
    assert la[0]["held_projects"] == lb[0]["held_projects"] and la[0]["L0"] == lb[0]["L0"]


def test_rewrite_replaces_matching_steps_with_the_macro_token():
    pairs, n_mac = LC.rewrite(_steps()[:1], {"L0": dict(edits=[["dedup_latest", ["key", ["dupes"]], ["order", ["int"]]],
                                                                ["exclude_value", ["col", ["text"]], ["value", "'D'"]]], pre=["fail:unique"], canonical="c0")})
    assert n_mac == 1 and all(p[1][0].startswith("mac:") for p in pairs)
    assert any(p[2][0] == "op:dedup_latest" for p in pairs)          # the macro's own first primitive is a negative
    pairs0, n0 = LC.rewrite(_steps()[:1], {})
    assert n0 == 0 and len(pairs0) == 5


def test_symptoms_are_position_invariant_and_paradigm_free():
    ev = dict(stage_fail=[["unique:x"], []], features={"fail:unique", "diff:dup_keys", "stage_fail:unique"})
    inner, last = S10.symptoms(ev, 0, 2), S10.symptoms(dict(ev, stage_fail=[[], ["unique:x"]]), 1, 2)
    assert inner == last == {"here:unique", "fail:unique", "diff:dup_keys"}
    toks = S10.tokens("op:dedup_latest", S10.ctx(ev, 0, 2))
    assert not any(re.search(r"\bP\d|X\d|H\d|stage:\d", t) for t in toks)


def test_held_out_compositions_never_reach_training():
    leak = MC.leakage()
    assert leak["violations"] == [] and leak["specs_checked"] == 2000
    man = MC.eval_manifest()
    assert len(man) == 48 and sum(t["group"] == "heldout" for t in man) == 24
    assert {t["family"] for t in man if t["group"] == "heldout"} == set(MC.HELD)
    assert {t["family"] for t in man if t["group"] == "ordinary"} <= set(MC.TRAIN_FAMILIES)
    assert all(t["seed"] in MC.RANGES[("agi10cde", "eval")] and t["names"] == "heldout" for t in man)
    assert all(t["seed"] in MC.RANGES[("agi10cde", "dev")] for t in MC.dev_manifest())


def test_arm_memories_share_trust_procedure_and_machinery():
    tr = {"records": [1], "weights": {"a": 1.0}, "support": {}}
    arms = [LC.arm_memory(tr), LC.arm_memory(tr, guide_w={"x": 1.0}), LC.arm_memory(tr, skills={"L0": {}}), LC.arm_memory(tr, skills={"L0": {}}, guide_w={"x": 1.0})]
    assert all(m["trust"] == tr and m["M"] == LC.M0 and m["guide"]["v10c"] and m["guide"]["bridge"] for m in arms)
    assert [m["guide"]["kind"] for m in arms] == ["fixed", "learned", "fixed", "learned"]
    assert [bool(m["de"]["skills"]) for m in arms] == [False, False, True, True]


def test_two_separate_draws_with_deliberately_withheld_pairs():
    a, b = MC.draw_manifest("A"), MC.draw_manifest("B")
    assert len(a) == len(b) == 16 and not {t["seed"] for t in a} & {t["seed"] for t in b}
    assert all(t["seed"] in MC.RANGES[("agi10cde", "eval")] for t in a + b)
    assert sum(t["group"] == "heldout" for t in a) == 10 and {t["family"] for t in a if t["group"] == "heldout"} == set(MC.HELD)
    train_mechs = {m for p in MC.TRAIN_MECH_PAIRS for m in p}
    for h, stages in MC.HELD.items():
        mechs = [MC.MECHS[p] for p, _ in stages]
        assert all(m in train_mechs or m in ("window", "parse") for ms in mechs for m in ms)   # every component mechanism is trained
        # some stage pair has ONLY withheld cross pairs, so every built target (>= 1 fault per stage) carries a withheld pair
        assert any(all(tuple(sorted((x, y))) not in MC.TRAIN_MECH_PAIRS for x in mechs[i] for y in mechs[j] if x != y)
                   for i in range(len(mechs)) for j in range(i + 1, len(mechs))), h
    assert MC.withheld_pairs([["tombstone"], ["window"]]) == [("tombstone", "window")] and MC.withheld_pairs([["latest", "tombstone"]]) == []


def test_clones_with_identical_M_share_streams(tmp_path):
    a, b = _learner(tmp_path, "cloneA"), _learner(tmp_path, "cloneB_other_name")
    assert a.M == b.M and [a._take("dream") for _ in range(5)] == [b._take("dream") for _ in range(5)]
    assert rng(a.rep, 1, 92005).sample(range(100), 8) == rng(b.rep, 1, 92005).sample(range(100), 8)

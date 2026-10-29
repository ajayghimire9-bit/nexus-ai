"""Phase 10B focused tests (NOT LOCKED): pure functions only."""
from nexus.de_phase4 import ir
from nexus.de_phase6 import engines6 as E
from nexus.de_phase10b import fixes10b, lineage10b as LB, manifest10b as MB, search10b  # noqa: F401


class Dom:
    header, unique_cols, int_like, dirty_cols, text_cols, num_range, files, rows, state, domain = ["id"], set(), set(), set(), set(), {}, [], [], {}, {}


def test_round_uncast_primitive():
    spec = dict(outputs=[["f", ["cast_int", ["div_real", ["cast_int", ["col", "a"]], ["nullif_zero", ["cast_int", ["col", "b"]]]]]], ["g", ["cast_int", ["col", "c"]]]])
    out = E.candidates("round_uncast", spec, Dom())
    assert "round_uncast" in E.OPS and len(out) == 1 and out[0][1] == "f" and out[0][0]["outputs"][0][1][0] == "round2"
    assert out[0][0]["outputs"][1] == spec["outputs"][1]


def test_bridge_signature_and_manifest():
    assert LB.bridge_sig([["dedup_first", ["col", ["dupes"]]], ["filter_file", ["col", ["int"]]]]) == '["dedup_first", "filter_file"]'
    E_ = MB.eval_manifest()
    assert len(E_) == 48 and all(85000 <= t["seed"] < 85048 for t in E_) and ("agi10bde", "eval") in MB.R.ONE_USE
    assert set(MB.train(0)["wake"]).isdisjoint(MB.train(1)["wake"])


def test_search_dispatch_registered():
    from nexus.de_phase7 import search7 as S7
    assert S7.search is search10b.search and search10b.search._phase7_original is not search10b.search

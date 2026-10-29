"""Phase 10 focused tests (NOT LOCKED): pure functions and fake backends only."""
import copy
import random

from nexus.de_phase10 import guide10 as G, manifest10 as MF, memory10 as MEM, procedure10 as PR10


def test_manifest_and_splits():
    E = MF.eval_manifest()
    assert len(E) == 48 and sum(t["group"] == "seen" for t in E) == 24 and sum(t["mc"] for t in E) >= 12
    assert all(t["names"] == "heldout" for t in E) and all(MF.train_spec(i, 1)["names"] == "base" for i in range(18))
    assert ("agi10de", "eval") in MF.R.ONE_USE and not any(MF.train_spec(i, 1)["paradigm"] in ("P8", "P9") for i in range(27))


def test_mdl_rule():
    assert MEM.delta_mdl(1, 2, 0) < 0 and MEM.delta_mdl(1, 4, 0) > 0 and MEM.delta_mdl(2, 2, 0) > 0


def test_pstar_counts_and_interval():
    P = MEM.empty_p()
    e = [["dedup_first", ["col", ["dupes", "int"]]]]
    MEM.add_hypothesis(P, e, "a", "partial")
    MEM.confirm(P, e, "b")
    h = next(iter(P["hypotheses"].values()))
    assert h["support"] == 2 and MEM.interval(h)[1] > 0 and MEM.strong(P)
    MEM.refute(P, "dedup_first", [])
    assert not MEM.strong(P)


def test_ranker_learns_a_separable_preference():
    pairs = [(["op:a", "op:a|ev:x"], ["op:b", "op:b|ev:x"]) for _ in range(30)]
    w = G.train(pairs)
    assert G.pair_accuracy(w, pairs) == 1.0


class Fake:
    def __init__(self, status):
        self.status = status

    def read(self, project, src):
        if src != "docs/ticket.json":
            return []
        return [dict(id="R1", subject=dict(state_ref=["file", "c.json", "off"]), effect_at_boundary="excluded", status=self.status,
                     provenance=dict(file=src, claim_id="R1"))]

    def search(self, project, mem, mode, skills):
        return dict(outcome="submitted", has_candidate=True, path=[], specs=[{}], dps=[], cost=dict(work=1), _cfg="x")

    def coverage(self, project, cand, skip_refs):
        ob = dict(stage=0, pos="cov8:x", op="requirement_boundary", options=["current pipeline", "reverse"], specs=[[{}], [{}]], probe={"o": "1"},
                  ref=["file", "c.json", "off"], col="o", resolved=None, via=None, conflict=False, undecided=False, claims=[], option_keys=["a", "b"],
                  effects=["kept", "excluded"], kind="implemented", legacy_effect="kept")
        return dict(obligations=[ob], equivalences=[], uncovered=[], probe_runs=1)

    def ask(self, project, dp):
        return dict(answer="undetermined")


def test_unapproved_claim_against_legacy_is_not_settled():
    st = PR10.investigate(dict(pid="x"), Fake("draft"), dict(M={}), PR10.F0)
    assert st.decision["kind"] == "abstain" and st.cost["questions"] == 1 and st.dps[0].get("legacy_conflict")


def test_approved_claim_overrides_legacy():
    st = PR10.investigate(dict(pid="x"), Fake("approved"), dict(M={}), PR10.F0)
    assert st.decision["kind"] == "submit" and st.decision["choices"]["0:cov8:x"] == "reverse"

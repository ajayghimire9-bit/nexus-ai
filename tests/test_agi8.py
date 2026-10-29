"""Phase 8 focused tests (NOT LOCKED). Pure functions and fake backends only: no project is generated, no engine runs."""
import copy

from nexus.de_phase8 import accept8 as AC8, procedure8 as PR8, seeds8 as S


def test_partitions_and_manifest():
    T = S.target_manifest()
    assert len(T) == 72 and [sum(t["tier"] == k for t in T) for k in (1, 2, 3)] == [24, 32, 16]
    assert all(76000 <= t["seed"] < 76200 for t in T) and sum(not t["answerable"] for t in T) == 5
    assert ("agi8de", "target") in S.R.ONE_USE and ("agi8de", "panel") in S.R.ONE_USE and ("agi8de", "source") not in S.R.ONE_USE
    b = S.block(1)
    assert len({s for r in b.values() for s in r}) == 1000


class Fake:
    def __init__(self, kind="absent", claim_effect="excluded"):
        self.kind, self.claim_effect = kind, claim_effect

    def read(self, project, src):
        if src != "contract.json":
            return []
        return [dict(id="R1", subject=dict(state_ref=["file", "c.json", "off"]), effect_at_boundary=self.claim_effect, status="approved",
                     provenance=dict(file=src, claim_id="R1"))]

    def search(self, project, mem, mode, skills):
        return dict(outcome="submitted", has_candidate=True, path=[], specs=[{}], dps=[], cost=dict(work=10), _cfg=f"{mode}|{skills}")

    def coverage(self, project, cand, skip_refs):
        ref = ["file", "c.json", "off"]
        if self.kind == "absent":
            ob = dict(stage=0, pos="cov8:x", op="requirement_absent", options=[], specs=[], probe=None, ref=ref, col=None, resolved=None, via=None,
                      conflict=False, undecided=False, claims=[], option_keys=[], effects=[], kind="absent")
        else:
            ob = dict(stage=0, pos="cov8:x", op="requirement_boundary", options=["current pipeline", "reverse"], specs=[[{}], [{}]], probe={"o": "1"},
                      ref=ref, col="o", resolved=None, via=None, conflict=False, undecided=False, claims=[], option_keys=["a", "b"],
                      effects=["kept", "excluded"], kind="implemented")
        return dict(obligations=[ob], equivalences=[], uncovered=[], probe_runs=6)

    def ask(self, project, dp):
        raise AssertionError("an absent obligation must never be asked about")


def test_absent_obligation_blocks_and_is_not_asked():
    st = PR8.investigate(dict(pid="x"), Fake("absent"), dict(M={}), PR8.F0)
    assert st.decision["kind"] == "abstain" and st.cost["questions"] == 0
    assert st.obligation_status == [dict(kind="absent", status="refuted")]


def test_implemented_obligation_discharged_by_document():
    st = PR8.investigate(dict(pid="x"), Fake("implemented", "excluded"), dict(M={}), PR8.F0)
    assert st.decision["kind"] == "submit" and st.decision["choices"]["0:cov8:x"] == "reverse"
    assert st.obligation_status == [dict(kind="implemented", status="satisfied")]


def test_status_classes():
    base = dict(kind="implemented", options=["a", "b"], effects=["kept", "excluded"], undecided=False, via=None, resolved=None,
                claims=[dict(effect_at_boundary="kept"), dict(effect_at_boundary="excluded")])
    assert AC8.status(base) == "conflict"
    assert AC8.status(dict(base, claims=[])) == "insufficient"
    assert AC8.status(dict(base, claims=[dict(effect_at_boundary="kept")], resolved="a", via="claim")) == "satisfied"
    assert AC8.status(dict(kind="absent", claims=[])) == "insufficient"


def test_read_cost_is_charged():
    assert PR8.cost_s(dict(work=0, probe_runs=0, questions=0, reads=3)) == 3 * PR8.READ_COST_S

"""Phase 7 focused tests (NOT LOCKED). Pure functions and fake backends only: no project is generated, no engine runs."""
import copy

from nexus.de_phase7 import accept7 as AC7, lineage7 as L7, procedure7 as PR7, seeds7 as S, skills7 as SK7


def rec(project, lit, roles=("dupes", "lowcard", "text")):
    return dict(project=project, stage_features=["fail:row_count"], edits=[["exclude_value", ["col", list(roles)], ["value", lit]]])


def test_invent7_keeps_literal_consistent_subgroup():
    lib = [rec("a", "'D'"), rec("b", "'D'"), rec("c", "'X'")]           # skills6.invent dropped the whole shape group here
    c = SK7.invent7(lib, min_support=2, max_len=1)
    assert [x["edits"][0][2] for x in c] == [["value", "'D'"]]
    assert c[0]["support"] == ["a", "b"] and c[0]["novelty"] == "single_operator_specialization"


def test_canonical_collapses_aliases_and_partials_counted_once():
    lib = [rec("a", "'D'", ("text", "dupes", "lowcard")), rec("a#partial", "'D'"), rec("b", "'D'")]
    c = SK7.invent7(lib, min_support=2, max_len=1)
    assert len(c) == 1 and c[0]["support"] == ["a", "b"] and c[0]["from_partial"]


def test_admit7_never_trades_a_completion_for_abstentions():
    base = {"p": dict(correct=True, completed=True, wrong=False, cost=dict(wall_s=1.0)), "q": dict(correct=False, completed=False, wrong=False, cost=dict(wall_s=1.0)),
            "r": dict(correct=False, completed=False, wrong=False, cost=dict(wall_s=1.0))}
    trial = copy.deepcopy(base)
    trial["p"].update(correct=False, completed=False)
    trial["q"].update(correct=True)
    trial["r"].update(correct=True)
    ok, why = PR7.admit7(base, trial)
    assert not ok and why["reason"] == "loses a verified completion"


def test_improver_edit_untested_unless_exercised_and_behaviour_changes():
    rows = {"p": dict(correct=True, completed=True, wrong=False, cost=dict(wall_s=1.0))}
    better = {"p": dict(correct=True, completed=True, wrong=False, cost=dict(wall_s=0.1))}
    assert L7.judge_edit("proc_cycles", {}, rows, better, "a", "b")[1]["reason"].startswith("untested: proc_cycles never")
    assert L7.judge_edit("proc_cycles", {"proc_cycles": 2}, rows, better, "a", "a")[1]["reason"].startswith("untested: behaviourally inactive")
    assert L7.judge_edit("proc_cycles", {"proc_cycles": 2}, rows, better, "a", "b")[0]


def test_partitions_and_target_manifest():
    T = S.target_manifest()
    assert len(T) == 72 and [sum(t["tier"] == k for t in T) for k in (1, 2, 3)] == [24, 32, 16]
    assert all(S.RANGES[("agi7de", "target")].start <= t["seed"] < S.RANGES[("agi7de", "target")].stop for t in T)
    assert len(S.panel_manifest()) == 18 and ("agi7de", "target") in S.R.ONE_USE and ("agi7de", "source") not in S.R.ONE_USE
    assert all(sp.get("paradigm") not in ("P8", "P9") for sp in L7.SOURCE_SPECS + S.pool_specs())


def test_group_cols():
    assert AC7.group_cols([dict(group=["region", ["col", "region"]]), dict(outputs=[])]) == {"region"}


class Fake:
    """A backend with one candidate and one coverage obligation (subject documented in one file)."""

    def __init__(self, claim_file="docs/ticket.json", effect="excluded"):
        self.claim = dict(id="R1", subject=dict(state_ref=["file", "b.json", "end"]), effect_at_boundary=effect, status="draft",
                          provenance=dict(file=claim_file, claim_id="R1"))
        self.claim_file = claim_file

    def read(self, project, src):
        return [copy.deepcopy(self.claim)] if src == self.claim_file else []

    def search(self, project, mem, mode, skills):
        return dict(outcome="submitted", has_candidate=True, path=[], specs=[{}], dps=[], cost=dict(work=10), _cfg=f"{mode}|{skills}")

    def coverage(self, project, cand, skip_refs):
        ob = dict(stage=0, pos="cov:x", op="requirement_boundary", options=["ts le end", "ts lt end"], specs=[[{}], [{}]], probe={"ts": "5"},
                  ref=["file", "b.json", "end"], col="ts", resolved=None, via=None, conflict=False, undecided=False, claims=[],
                  option_keys=["k1", "k2"], effects=["kept", "excluded"])
        return dict(obligations=[ob], equivalences=[], uncovered=[], probe_runs=4)

    def ask(self, project, dp):
        return dict(answer="undetermined")


def test_barrier_abstains_on_open_obligation_and_never_resolves_it():
    st = PR7.investigate(dict(pid="x"), Fake(), dict(M={}), PR7.SEED)
    assert st.decision["kind"] == "abstain" and "barrier" in st.decision["reason"] and st.barrier["computed"]


def test_fixed_strategy_discharges_obligation_from_documents():
    st = PR7.investigate(dict(pid="x"), Fake(), dict(M={}), PR7.FIXED_STRATEGY)
    assert st.decision["kind"] == "submit" and st.decision["choices"]["0:cov:x"] == "ts lt end" and not st.barrier["computed"]


def test_undetermined_answer_leaves_obligation_unresolved():
    prog = [["search", "whole", "off"], ["check_coverage"], ["ask", "first"], ["submit_or_abstain"]]
    st = PR7.investigate(dict(pid="x"), Fake(), dict(M={}), prog)
    assert st.decision["kind"] == "abstain" and st.cost["questions"] == 1

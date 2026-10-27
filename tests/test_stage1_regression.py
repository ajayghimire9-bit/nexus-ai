"""Stage 1 regression (NOT LOCKED): valid results, runtime errors and under-specified / unsupported requests stay strictly
distinguishable; Checker v5 is the pinned 622a29a object. The 175-case search-order invariance suite (state-dominance repair)
is run and pinned by scripts/de_stage1_regression.py. No experiment runs here."""
from nexus import checker_kernel_v5 as V5
from nexus import outcome_contract as OC
from nexus import w39_eval as E39
from nexus import w39_lang as L
from nexus import w39_scope as S

PUB = [["a;b", "a"], ["cc;d", "cc"], ["e;ff", "e"]]
BEF = [{"op": "fn", "f": ["bef", ["x"], ";"]}]


def _ev(pub, q, cand, depth, extra=()):
    return dict(checker_version=5, public=pub, query=q, claimed_answer=L.run(cand, q), candidate=cand,
                scope=S.scope(pub, q, depth), extra_queries=list(extra))


def test_v5_is_the_pinned_object():
    assert E39.verify_v5() == open("src/nexus/checker_kernel_v5.sha256").read().split()[0]


def test_raw_v5_conflates_error_with_unique_and_the_contract_separates_them():
    ev = _ev(PUB, "g;h", BEF, 1, extra=["gh", "k;l"])
    v = V5.check(ev)
    assert v["label"] == "SCOPE_UNIQUE"
    assert v["extra"][0]["answers"] == 1                     # the ERROR answer counted as one unique answer (the defect)
    assert L.run(BEF, "gh") == L.ERROR
    assert OC.input_outcomes(ev, v) == [OC.VALID_UNIQUE, OC.ABSTAIN_ERROR, OC.VALID_UNIQUE]


def test_query_error_is_abstain_error_not_valid():
    ev = dict(_ev(PUB, "g;h", BEF, 1), query="gh", claimed_answer=L.ERROR)
    v = V5.check(ev)
    assert v["label"] == "ABSTAIN" and v["reason"] == "candidate_fails"
    assert OC.input_outcomes(ev, v) == [OC.ABSTAIN_ERROR]


def test_under_specified_is_warning_or_clarification_never_valid():
    ev = _ev(PUB, "g;h", BEF, 2, extra=["gh", "k;l"])
    v = V5.check(ev)
    assert v["label"] == "SCOPE_UNIQUE" and v["warnings"] == ["UNDER_SPECIFIED_WARNING"]
    assert v["extra"][0]["answers"] == 2
    assert OC.input_outcomes(ev, v)[1] == OC.ABSTAIN_ERROR           # the candidate itself errors: error wins
    ev2 = _ev(PUB[:1], "g;h", BEF, 1, extra=["xy;z"])
    v2 = V5.check(ev2)
    assert v2["extra"][0]["answers"] == 2
    assert OC.input_outcomes(ev2, v2)[1] == OC.UNDER_SPECIFIED_WARNING
    assert OC.input_outcomes(ev2, v2, channel=True)[1] == OC.ASK_CLARIFICATION


def test_ambiguous_query_and_unsupported_operation():
    pub = [["ab cd", "ab"]]
    sc = S.scope(pub, "x yz", 1)
    fits = [[t] for t in sc["tools"] if L.run([t], "ab cd") == "ab"]
    ev = dict(checker_version=5, public=pub, query="x yz", claimed_answer=L.run(fits[0], "x yz"), candidate=fits[0], scope=sc)
    v = V5.check(ev)
    assert v["label"] == "AMBIGUOUS" and v["k"] > 1
    assert OC.input_outcomes(ev, v) == [OC.UNDER_SPECIFIED_WARNING]
    assert OC.input_outcomes(ev, v, channel=True) == [OC.ASK_CLARIFICATION]
    bad = dict(ev, candidate=[{"op": "exec", "code": "x"}])
    vb = V5.check(bad)
    assert vb["reason"] == "unsupported"
    assert OC.input_outcomes(bad, vb) == [OC.ABSTAIN_UNSUPPORTED]


def test_vocabulary_is_closed_and_only_checked_results_count_as_answers():
    assert len(set(OC.INPUT_OUTCOMES)) == len(OC.INPUT_OUTCOMES) == 5
    assert [o for o in OC.INPUT_OUTCOMES if OC.is_answer(o)] == [OC.VALID_UNIQUE]
    assert [o for o in OC.PROJECT_OUTCOMES if OC.is_answer(o)] == [OC.COMPLETED_VERIFIED]

"""Wave 24 v4: soundness and mechanism tests (dev data / authored fixtures only; no evaluation seeds)."""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_v4_agents import (CONFIG, FastMemory, V4Agent, labelled_stream, predicates_split, run_seed,
                                    source_training, tycho_admit)
from nexus.wave24_v4_core import (AMBIGUOUS, UNIQUE, Searcher, algebraic_signature, compose_witness_set,
                                  guard_tool, lossy_representative_set, meter, phi, predicates_for,
                                  propose_refinement, search, solve_exact, verify)
from nexus.wave24_v4_world import (Oracle, V4Task, dict_record_domain, int_seq_domain, source_domains,
                                   state_transition_domain, target_domains, task_stream)


# --------------------------------------------------------------------------- ObsEGraph witness conservation
def test_v_mod_2_witness_set_is_conserved():
    children = {0, 1, 2}                       # three sub-programs agree on public data, differ on the query
    lossy = lossy_representative_set(children)  # the old bug: keep min and max only
    assert lossy == {0, 2}
    assert compose_witness_set(lossy, lambda v: v % 2) == {vkey(0)}          # would be a false UNIQUE
    assert compose_witness_set(children, lambda v: v % 2) == {vkey(0), vkey(1)}   # conserved: ambiguous


def test_v_mod_2_search_reports_ambiguity_with_two_verified_witnesses():
    hs = [Tool(f"h{i}", (lambda x, i=i: x + 1 if x >= 10 else i), f"h{i}") for i in range(3)]
    p = Tool("p", lambda v: v % 2 + 100, "parity plus 100")
    public = ((10, 101), (11, 100))
    res = search(public, 5, hs + [p], max_depth=2, budget=10**6)
    assert res.status == AMBIGUOUS
    answers = {vkey(h[1]) for h in res.hypotheses}
    assert answers == {vkey(100), vkey(101)}
    for _, q, prog in res.hypotheses:          # every witness is a concrete program re-verified on public data
        assert verify(prog, public, 5, q)


# --------------------------------------------------------------------------- equal-signature traps
def _records_task(kind, oracle=True):
    d = dict_record_domain()
    T = {t.name: t for t in d.tools}
    xs = ([{"t": 1, "v": 5}, {"t": 4, "v": 2}], [{"t": 2, "v": 8}, {"t": 3, "v": 1}, {"t": 9, "v": 6}],
          [{"t": 5, "v": 0}, {"t": 7, "v": 3}])
    pub = tuple((x, T["latest"](x)) for x in xs)
    q = [{"t": 8, "v": 4}, {"t": 2, "v": 9}]
    if kind == "active":
        return d, V4Task(d.name, "active", pub, q, T["latest"](q), "latest", "UNIQUE",
                         oracle=("chain", (T["latest"],)), probe_budget=3)
    return d, V4Task(d.name, "trap", pub, q, T["latest"](q), "latest", "AMBIGUOUS")


def test_last_record_vs_latest_permutation_probe():
    d, task = _records_task("active")
    res = search(task.public, task.query, d.tools)
    assert res.status == AMBIGUOUS and {h[0] for h in res.hypotheses} == {("last_rec",), ("latest",)}
    plan = propose_refinement(res.hypotheses, dict(public=task.public, query=task.query), dict(tools=d.tools),
                              "disambiguate", 10**6, m=meter(10**9))
    assert plan.candidate_predicate.name == "sorted_by:t=True"          # the invented distinction
    fam, x = plan.distinguishing_test
    assert fam in ("reverse", "rotate", "swap01")                       # multiset-preserving permutation
    assert sorted(map(vkey, x)) == sorted(map(vkey, task.public[0][0]))
    agent = V4Agent("abstractions_fixed_refinement", seed=1)
    agent.enter(d, meter(10**9))
    row = agent.solve(task)
    assert row["status"] == UNIQUE and row["solved"] and row["probes"] >= 1


def test_passive_trap_never_fabricates_ground_truth():
    d, task = _records_task("trap")
    for arm in ("abstractions_fixed_refinement", "full_nexus_reusable_procedures"):
        agent = V4Agent(arm, seed=1)
        agent.enter(d, meter(10**9))
        row = agent.solve(task)
        assert row["status"] == AMBIGUOUS and row["truth_in_witness_set"] and row["probes"] == 0
        assert not row["false_certificate"]


def test_reverse_vs_rotate_left_two_step_disambiguation():
    s = int_seq_domain()
    S = {t.name: t for t in s.tools}
    probes = s.inputs(random.Random(0), 12)
    m = meter(10**9)
    assert algebraic_signature(S["rev"], probes, m)[0] is True          # involution
    assert algebraic_signature(S["rotl"], probes, m)[0] is False        # 2-step probe separates the roles
    pub = tuple((x, S["rotl"](x)) for x in ([3, 7], [5, 1], [0, 4]))    # length 2: reverse == rotate_left
    q = [1, 2, 3]
    res = search(pub, q, s.tools)
    assert res.status == AMBIGUOUS
    task = V4Task(s.name, "active", pub, q, S["rotl"](q), "rotl", "UNIQUE", oracle=("chain", (S["rotl"],)),
                  probe_budget=3)
    agent = V4Agent("abstractions_fixed_refinement", seed=1)
    agent.enter(s, meter(10**9))
    row = agent.solve(task)
    assert row["status"] == UNIQUE and row["solved"] and row["witness"] == ["rotl"]


def test_oracle_never_answers_the_query():
    o = Oracle(lambda x: x, [1, 2])
    with pytest.raises(PermissionError):
        o([1, 2])
    assert o([2, 1]) == [2, 1] and o.calls == 1


# --------------------------------------------------------------------------- subset failure / guards
def test_guard_does_not_swallow_exceptions():
    d = dict_record_domain()
    T = {t.name: t for t in d.tools}
    always = predicates_for([[{"t": 1}]], [])[0] if predicates_for([[{"t": 1}]], []) else None
    assert always is not None and always([{"t": 1}])
    g = guard_tool(always, (T["last_rec"], T["get_v"]), ("const", 0))
    with pytest.raises(KeyError):
        g([{"t": 1}])                           # routed to P, P raises: the exception propagates


def test_subset_failure_procedure_mined_on_sources_repairs_missing_key():
    trained, ledger, report = source_training(1)          # dev seed; sources INT_SEQ + STR_PARSE only
    mined = trained.procedures.summary()
    assert any(k.startswith("predicate:") for k in mined) and ledger["source_practice_work"] > 0
    d = dict_record_domain()
    pub = (([{"t": 1, "v": 5}, {"t": 2, "v": 7}], 7), ([{"t": 1, "v": 3}], 3),
           ([{"t": 1}, {"t": 2, "v": 4}], 0), ([{"t": 3, "v": 1}, {"t": 4}], 0))
    q = [{"t": 1, "v": 9}, {"t": 2, "v": 2}]
    task = V4Task(d.name, "subset", pub, q, 2, "guard[has:v?last_rec>get_v:0]", "UNIQUE")
    from nexus.wave24_v4_agents import make_arm
    agent = make_arm("full_nexus_reusable_procedures", 1, trained)
    agent.enter(d, meter(10**9))
    row = agent.solve(task)
    assert row["status"] == UNIQUE and row["solved"] and row["witness"][0].startswith("guard[has:v?")


# --------------------------------------------------------------------------- exactness of the shared space
def _streams(seed, names):
    return [(d, task_stream(d, seed, predicates_split)) for d in list(source_domains()) + list(target_domains())
            if d.name in names]


def test_naive_constrained_and_popper_certifiers_agree():
    n = 0
    for d, tasks in _streams(21, ("INT_SEQ", "DICT_RECORD", "STATE_TRANSITION", "NUM_SERIES")):
        for t in tasks:
            verdicts = []
            for kw in (dict(popper=False, naive=True), dict(popper=False), dict(popper=True)):
                r = solve_exact(t.public, t.query, d.tools, meter(10**8), **kw)
                verdicts.append((r.status, frozenset(vkey(h[1]) for h in r.hypotheses)))
            assert verdicts[0] == verdicts[1] == verdicts[2], (d.name, t.teacher)
            early = solve_exact(t.public, t.query, d.tools, meter(10**8), popper=True, early=True)
            assert early.status == verdicts[0][0]
            n += 1
    assert n >= 40


def test_popper_keeps_guard_partials_from_collapsed_prefixes():
    d = state_transition_domain()
    pub = ((("run", 2), ("run", 0)), (("idle", 2), ("run", 0)), (("idle", 0), ("run", 2)))
    q = ("run", 1)
    a = solve_exact(pub, q, d.tools, meter(10**8), popper=False)
    b = solve_exact(pub, q, d.tools, meter(10**8), popper=True)
    assert a.status == b.status == AMBIGUOUS
    assert {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}
    assert any("reset>toggle" in h[0][0] for h in b.hypotheses)       # partial built from a collapsing prefix


def test_fd_nogoods_prune_and_are_counted():
    d = int_seq_domain()
    t = next(t for t in task_stream(d, 22, predicates_split) if t.kind == "passive")
    s = Searcher(t.public, t.query, d.tools, popper=True, m=meter(10**8))
    s.run_to(3)
    assert s.res.pruned_popper > 0


# --------------------------------------------------------------------------- learning components
def test_ttt_memory_update_moves_toward_observation():
    mem = FastMemory(eta=0.5)
    p0 = mem.p("probe", "reverse")
    m = meter(10**6)
    mem.update("probe", "reverse", True, m)
    assert mem.p("probe", "reverse") > p0 and mem.updates == 1 and m.total == 2
    mem.update("probe", "rotate", False, m)
    assert mem.p("probe", "rotate") < 0.5


def test_tycho_gate_rejects_net_negative_and_unclean_procedures():
    net, ok = tycho_admit(-3.0, 500, 0, 10, 10)
    assert net < 0 and not ok
    net, ok = tycho_admit(10.0, 500, 0, 10, 10)
    assert net > 0 and ok
    assert not tycho_admit(10.0, 500, 1, 10, 10)[1]      # a false certificate blocks admission
    assert not tycho_admit(10.0, 500, 0, 9, 10)[1]       # losing a validation solve blocks admission


def test_tycho_library_gate_rejects_unhelpful_library():
    from nexus.wave24_helpers import HelperLibrary
    from nexus.wave24_v4_code import tycho_library, val_tasks
    gate = tycho_library(HelperLibrary(), val_tasks(3), work_per_solve=5000)
    assert gate["correct_hits"] == 0 and gate["net_benefit"] <= 0 and not gate["admitted"]


def test_arm_configs_are_cumulative_and_matched():
    assert set(CONFIG) >= {"literal_fixed_baseline", "abstractions_fixed_refinement", "learned_refinement_ttt_trm",
                           "full_nexus_reusable_procedures", "amnesiac_no_source_control",
                           "independent_proposal_ablation"}
    a4, a5, a6 = (CONFIG[k] for k in ("full_nexus_reusable_procedures", "amnesiac_no_source_control",
                                      "independent_proposal_ablation"))
    assert {k: v for k, v in a5.items() if k not in ("source", "persist")} == \
        {k: v for k, v in a4.items() if k not in ("source", "persist")}
    assert a6["probes"] == "random" and not a6["trm"] and a4["probes"] == "designed" and a4["trm"]


def test_labelled_stream_gold_matches_reference_and_kinds():
    d = dict_record_domain()
    st = labelled_stream(d, 23)
    assert st and {t.kind for t in st} <= {"passive", "trap", "active", "subset"}
    for t in st:
        if t.kind == "active":
            assert t.gold == "UNIQUE" and t.oracle is not None
        if t.kind == "trap":
            assert t.gold == "AMBIGUOUS"


def test_phi_is_total():
    for v in ([], {}, "", b"", (None, float("nan")), [{"t": 1}, {"v": None}], {"a": {"b": [1, "x"]}}, 0, None):
        phi(v)


# --------------------------------------------------------------------------- MBPP slices and twin fuzzer
def test_mbpp_v4_slices_are_fresh_and_disjoint():
    from nexus.wave24_mbpp import load_tasks, ordered
    from nexus.wave24_v4_code import (V3_EVAL_N, V3_EVAL_SALT, V3_TRAIN_N, V3_TRAIN_SALT, eval_tasks,
                                      val_tasks)
    v3_eval = {t.task_id for t in ordered(load_tasks("eval"), V3_EVAL_SALT)[:V3_EVAL_N]}
    v3_train = {t.task_id for t in ordered(load_tasks("dev"), V3_TRAIN_SALT)[:V3_TRAIN_N]}
    ev = {t.task_id for t in eval_tasks(32)}
    va = {t.task_id for t in val_tasks(12)}
    eval_ids = {t.task_id for t in load_tasks("eval")}
    dev_ids = {t.task_id for t in load_tasks("dev")}
    assert len(ev) == 32 and ev <= eval_ids and not ev & v3_eval
    assert len(va) == 12 and va <= dev_ids and not va & v3_train and not va & ev


def test_fuzz_inputs_are_generic_mutations():
    from nexus.wave24_v4_code import fuzz_inputs
    fz = fuzz_inputs(([1, 2, 3], 2))
    assert fz and all(len(x) == 2 for x in fz) and ([1, 2, 3], 2) not in fz
    assert fuzz_inputs(()) == []


# --------------------------------------------------------------------------- runner / verifier plumbing
def test_v4_verifier_on_dev_payload():
    import verify_wave24_agi_gap_suite as V
    res = run_seed(3, families=["DICT_RECORD", "STATE_TRANSITION"])
    payload = dict(schema="wave24_suite_v4", execution_status="COMPLETE", procedural=[res], mbpp=dict(rows=[]))
    out = V.verify_v4(payload)
    assert out["gates"]["v4_g1_zero_false_certificates"]
    assert set(out["gates"]) >= {"v4_g2_full_nexus_beats_controls", "v4_g3_disambiguation_and_repair_transfer",
                                 "v4_g4_popper_efficiency", "v4_g5a_nexus_vs_unverified_qwen",
                                 "v4_g5b_nexus_vs_verified_sampling", "v4_g5c_helpers_positive_net_validation_benefit"}
    assert out["report"]["g4"]["same_verdicts"]
    json.dumps(res)                                     # the payload is JSON-serialisable


def test_one_sided_sign_test():
    import verify_wave24_agi_gap_suite as V
    assert abs(V.one_sided_sign(5, 0) - 1 / 32) < 1e-12
    assert V.one_sided_sign(4, 1) > 0.05 and V.one_sided_sign(0, 0) == 1.0


def test_runner_session_allowance_counts_from_marker(tmp_path, monkeypatch):
    import run_wave24_agi_gap_suite as R
    led = tmp_path / "ledger.jsonl"
    led.write_text("\n".join(json.dumps(r) for r in (dict(run="old", wall_s=3000.0),
                                                      dict(run="session-start", wall_s=0, session_marker=True),
                                                      dict(run="dev", wall_s=100.0))) + "\n")
    monkeypatch.setattr(R, "LEDGER", led)
    assert R.session_remaining_v4() == 3500.0


def test_runner_refuses_to_overwrite_v4_output(tmp_path):
    import run_wave24_agi_gap_suite as R
    out = tmp_path / "x.json"
    out.write_text("{}")
    with pytest.raises(SystemExit):
        R.main(["--suite", "v4", "--out", str(out)])

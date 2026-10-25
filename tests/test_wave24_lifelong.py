"""Authored source-only mechanism tests; no final task bank or LLM/GPU run."""
from copy import deepcopy
import operator

import pytest

from nexus.wave24_auto_laws import AutoOperatorFingerprinter, OpenPythonToolboxSandbox
from nexus.wave24_quotient_core import (Operator, Grammar, WorkMeter, ParametricSkillMacro, apply,
    variable, typed_hole, eval_expr, primitive_cost, solve)
from nexus.wave24_self_evolving_loop import (PublicTask, ScratchpadWorkspaceEngine, UniversalPhenotypeCompass,
    SymptomToActionDoctor, SymptomJobCritic, JobTagRecipeEngine, ClosedLoopSelfAuditor,
    AutonomousToolInventor, DualMemoryLearner, JournalSkillView, verify_workspace_certificate,
    ShadowRollbackGuard)


def meter():
    return WorkMeter(limit=40_000_000, wall_limit=10.)


def fixture():
    op = Operator("op_0", ("INT",), "INT", lambda x:x+1)
    g = Grammar("INT", (op,)); probes = (-3, -1, 0, 1, 2, 7)
    roles = AutoOperatorFingerprinter().fingerprint_roles(g.operators, {"INT":probes}, meter=meter())
    return g, roles, probes


def task(amount=4):
    return PublicTask(((-2, -2+amount), (1, 1+amount)), 7, "INT")


def chain(op, count, leaf=None):
    e = variable(op.inputs[0]) if leaf is None else leaf
    for _ in range(count):
        e = apply(op, e)
    return e


def test_scratchpad_really_reaches_seven_primitive_nodes_and_rejects_unbounded_claim():
    g, roles, _ = fixture(); tr={}
    result = ScratchpadWorkspaceEngine(roles=roles, meter=meter()).run(g, task(6), trace=tr)
    assert result.query_values == (13,) and primitive_cost(result.witnesses[0], g.ops) == 7
    assert len(tr["workspace"]["hops"]) >= 2
    assert tr["workspace"]["lyapunov"] is True
    assert tr["workspace"]["primitive_cap"] == 9
    assert verify_workspace_certificate(g, task(6), result, tr["workspace"], meter=meter())
    too_deep = ScratchpadWorkspaceEngine(roles=roles, meter=meter()).run(g, task(12))
    assert not too_deep.witnesses  # primitive cap9 still blocks cost13; Lyapunov is not unbounded


def test_lyapunov_depth_ladder_terminates_by_deficit_not_hop_three():
    g, roles, _ = fixture()
    depths = {}
    for n in (2, 3, 4, 5):
        tr = {}
        result = ScratchpadWorkspaceEngine(2, roles=roles, meter=meter(), max_hops=16).run(g, task(n), trace=tr)
        depths[n] = len(tr["workspace"]["hops"])
        assert result.query_values == (7+n,)
        assert tr["workspace"]["lyapunov"] is True
        assert tr["workspace"]["hop_stop_reason"] == "solved"
        assert tr["workspace"]["max_hops"] == 16
    assert depths == {2: 2, 3: 3, 4: 4, 5: 5}


def test_shadow_rollback_rejects_nonimproving_weight_updates():
    guard = ShadowRollbackGuard()
    guard.record((1., 0., 0., 0., 0., 1., 0., 0., 0., 0.), 8)
    class Dummy:
        def __init__(self, models, score):
            self.models, self.score = models, score
        def predict(self, features, meter=None):
            return self.score
    before, worse, better = Dummy([1], (1., 1.)), Dummy([1], (.1, .1)), Dummy([1], (2., 2.))
    assert guard.accept(before, worse, meter()) is False
    assert guard.accept(before, better, meter()) is True
    assert ShadowRollbackGuard().accept(Dummy(None, (1., 1.)), better, meter()) is True


def test_job_fingerprints_are_deterministic_empirical_and_not_timing_promises():
    ops=(Operator("op_0", ("INT",), "INT", abs), Operator("op_1", ("INT",), "INT", operator.neg))
    profiler=AutoOperatorFingerprinter(); kwargs=dict(carriers={"INT":(-3,-1,0,1,3)}, meter=meter())
    jobs=profiler.fingerprint_jobs(ops, **kwargs)
    assert "CLEANER_IDEMPOTENT" in jobs["op_0"] and "FLIPPER_INVOLUTION" in jobs["op_1"]
    assert profiler.fingerprint_jobs(ops, carriers={"INT":(-3,-1,0,1,3)}, meter=meter()) == jobs


def test_doctor_uses_real_public_symptom_action_feedback_and_no_task_identifiers():
    g, roles, _=fixture(); d=SymptomToActionDoctor(); before=d.critic.fingerprint()
    assert len(d.features((0,2),(1,3),("STEPPER_ADVANCE",),meter=meter())) == 10
    report=d.learn_source(g, task(), roles, meter=meter())
    assert report["new_rows"] > 0 and d.critic.fingerprint()!=before
    assert {r["J_fit"] for r in d.rows} <= {0,1}
    with pytest.raises(ValueError,match="target"):
        d.learn_source(g,task(),roles,meter=meter(),frozen=True)


def test_promotion_then_reuse_is_real_and_source_feedback_is_one_use():
    g,roles,probes=fixture(); learner=DualMemoryLearner(meter=meter())
    learner.enter("UNIT_SOURCE",g,roles,probes)
    result,first=learner.solve_task("UNIT_SOURCE",task())
    assert result.query_values==(11,)
    update=learner.learn_last_source("UNIT_SOURCE",observed_query=11)
    assert update["accepted"], update
    again,later=learner.solve_task("UNIT_SOURCE",task())
    assert again.query_values==(11,) and later["total_work"] < first["total_work"]
    assert len(later["trace"]["workspace"]["hops"])==1
    learner.learn_last_source("UNIT_SOURCE",observed_query=11)
    with pytest.raises(ValueError,match="one-use"):
        learner.learn_last_source("UNIT_SOURCE",observed_query=11)


def test_job_recipes_transfer_without_target_training_and_frozen_feedback_fails():
    g,roles,probes=fixture(); recipe=JobTagRecipeEngine()
    # abs is the declared integer measure: mixed-sign +1 probes have a variable
    # measure shift. This positive-transfer unit uses a nonnegative seed carrier.
    roles=AutoOperatorFingerprinter().fingerprint_roles(g.operators,{"INT":(0,1,2,7)},meter=meter())
    skill=ParametricSkillMacro(chain(g.operators[0],2,typed_hole("INT")),("INT",))
    recipe.remember(skill,roles,source_domain="UNIT_SOURCE")
    target_op=Operator("op_0",("STR",),"STR",lambda s:s+"!")
    tg=Grammar("STR",(target_op,)); ts=("a","b","c")
    tr=AutoOperatorFingerprinter().fingerprint_roles(tg.operators,{"STR":ts},meter=meter())
    skills,lineage=recipe.instantiate(tg,tr,ts,meter=meter())
    assert skills and lineage[0]["target_training_tasks"]==0
    learner=DualMemoryLearner(meter=meter());learner.recipes=recipe
    learner.enter("BIT_CELLULAR_AUTOMATA",tg,tr,ts,frozen=True)
    assert learner.import_recipes("BIT_CELLULAR_AUTOMATA")
    before=learner.fingerprint()
    learner.solve_task("BIT_CELLULAR_AUTOMATA",PublicTask((("a","a!!!"),("b","b!!!")),"c","STR"))
    assert learner.fingerprint()==before
    with pytest.raises(ValueError):learner.learn_last_source("BIT_CELLULAR_AUTOMATA",observed_query="c!!!")
    with pytest.raises(ValueError):recipe.remember(skill,roles,source_domain="BIT_CELLULAR_AUTOMATA")


def test_self_audit_quarantines_three_measured_harmful_shortcuts():
    g,roles,probes=fixture(); learner=DualMemoryLearner(meter=meter())
    learner.enter("AUDIT",g,roles,probes);lib=learner.contexts["AUDIT"]["library"]
    for n in (2,3,4):
        s=ParametricSkillMacro(chain(g.operators[0],n,typed_hole("INT")),("INT",))
        lib.inject_for_audit(s,g,explicitly_enabled=True)
    records=learner.audit_shortcuts("AUDIT",task(0))
    assert len(records)==3 and all(r["quarantined"] and r["with_skill"]>r["without"] for r in records)
    assert not lib.snapshot() and len(lib._asts)==3  # archived, not erased


def test_exploration_tuning_changes_actual_portfolio_and_never_reads_targets():
    auditor=ClosedLoopSelfAuditor()
    for _ in range(3):auditor.observe_task(unresolved=True,hops=2)
    assert auditor.speculative_share>=.30 and auditor.adjustments
    old=list(auditor.adjustments);auditor.observe_task(unresolved=True,hops=3,source=False)
    assert auditor.adjustments==old
    # Directly exercise the selection hook with public-only candidate records.
    engine=ScratchpadWorkspaceEngine(meter=meter(),speculative_share=.35)
    g,_,_=fixture();engine._grammar=g
    rows=[dict(key=("INT",(i,)),outputs=(i,2*i,3*i),novelty=0.) for i in (1,2,3,7)]
    chosen=[("EXPLOIT",rows[0]),("ROLE_BRIDGE",rows[1]),("NOVELTY",rows[2])]
    changed=engine.rebalance_portfolio(chosen,rows,(),(1,2,3),(9,10))
    assert [r["key"] for _,r in changed]!=[r["key"] for _,r in chosen]


def test_invented_helper_is_actual_python_verified_in_child_and_registered_at_full_cost():
    g,roles,probes=fixture(); inventor=AutonomousToolInventor();m=meter()
    proposal=inventor.propose(g,task(3),chain(g.operators[0],3),meter=m)
    assert proposal["function"](5)==8 and "def invented_tool" in proposal["python_source"]
    assert proposal["isolation"]["external_actions_allowed"] is False
    with pytest.raises(ValueError):inventor.register(proposal,g,roles,probes,meter=m)
    updated,new_roles=inventor.register(proposal,g,roles,probes,meter=m,observed_source_passed=True)
    op=updated.operators[-1]
    assert op.fn(5)==8 and op.cost==3 and len(inventor.promoted)==1 and op.name in new_roles
    assert primitive_cost(apply(op,variable("INT")),updated.ops)==4


def test_helper_ast_rejects_external_names_and_child_denies_file_io(tmp_path):
    from nexus.wave24_resource_host import verify_pure_helper_isolated
    path=tmp_path/"forbidden"
    with pytest.raises(ValueError,match="isolated helper rejected"):
        verify_pure_helper_isolated(lambda x:open(path,"w"), (1,),meter=meter())
    assert not path.exists()


def test_raw_python_sandbox_connects_real_learning_and_preserves_target_boundary():
    sandbox=OpenPythonToolboxSandbox.from_callables((lambda x:x+1,),[-2,0,1,3,7],meter=meter())
    r,first=sandbox.solve(task().public_io,7)
    assert r.query_values==(11,)
    update=sandbox.learn_revealed_source(observed_query=11)
    assert update["accepted"]
    frozen=OpenPythonToolboxSandbox.from_callables((lambda x:x+1,),[-2,0,1,3,7],meter=meter(),frozen=True)
    frozen.solve(task().public_io,7)
    with pytest.raises(ValueError):frozen.learn_revealed_source(observed_query=11)


def test_durable_memory_round_trip_uses_an_external_hash_anchor_and_matching_toolbox(tmp_path):
    g,roles,probes=fixture(); old=DualMemoryLearner(meter=meter());old.enter("A",g,roles,probes)
    old.solve_task("A",task());old.learn_last_source("A",observed_query=11)
    from nexus.seed.experimental import read,write_new
    saved=old.export_state();write_new(tmp_path/"state.json",saved);saved=read(tmp_path/"state.json")
    new=DualMemoryLearner(meter=meter());new.enter("A",g,roles,probes)
    assert new.restore_state(saved,expected_digest=saved["state_sha256"])
    assert new.fingerprint()==old.fingerprint()
    assert new.contexts["A"]["protected"]==old.contexts["A"]["protected"]
    assert new.auditor.utility==old.auditor.utility and new.auditor.window==old.auditor.window
    assert new.history.snapshot()[:-1]==old.history.snapshot()
    r,_=new.solve_task("A",task());assert r.query_values==(11,)
    old.solve_task("A",task())
    a=new.learn_last_source("A",observed_query=11);b=old.learn_last_source("A",observed_query=11)
    assert a==b and new.fingerprint()==old.fingerprint()
    forged=deepcopy(saved);forged["source_updates"]+=1
    other=DualMemoryLearner(meter=meter());other.enter("A",g,roles,probes)
    with pytest.raises(ValueError,match="anchor"):other.restore_state(forged,expected_digest=saved["state_sha256"])

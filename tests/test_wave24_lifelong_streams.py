"""Authored orchestration fixtures, separate from procedural development tasks."""
from copy import deepcopy
import pytest

from nexus.wave24_quotient_core import WorkMeter, Operator, Grammar, variable, apply
from nexus.wave24_self_evolving_loop import World, PublicTask, GeneratedTask
from nexus.wave24_lifelong_streams import run_lifelong_streams, derive_capability_metrics, generate_stream_curriculum
from scripts.verify_wave24_azr_ruler_cegis import verify_lifelong_streams


def worlds_fixture():
    op=Operator("op_0",("INT",),"INT",lambda x:x+1)
    g=Grammar("INT",(op,));xs=(0,1,2,3,7)
    return tuple(World(n,g,"INT",xs,{"INT":xs}) for n in ("UNIT_A","UNIT_B","UNIT_C","UNIT_D","BIT_CELLULAR_AUTOMATA"))


def authored(world,seed,*,meter,purpose="source_training",include_followup=True,**kw):
    def record(n):
        p=variable("INT")
        for _ in range(n):p=apply(world.grammar.operators[0],p)
        t=PublicTask(((0,n),(1,n+1)),7,"INT")
        return GeneratedTask(world.name,p,t,7+n,n+1,"source_deep",None)
    a,b=record(4),record(5)
    return ((a,b,a) if include_followup else (a,)),dict(purpose=purpose)


@pytest.fixture
def audit(monkeypatch):
    import nexus.wave24_lifelong_streams as streams
    monkeypatch.setattr(streams,"generate_stream_curriculum",authored)
    return run_lifelong_streams(worlds_fixture(),{},991,WorkMeter(limit=40_000_000,wall_limit=10),None)


def test_streams_execute_real_updates_but_never_target_updates(audit):
    assert audit["execution_status"]=="COMPLETE",audit.get("execution_error")
    assert audit["source_feedback_events"]==15 and "BIT_CELLULAR_AUTOMATA" not in audit["source_update_domains"]
    assert audit["stream2"]["frozen_before"]==audit["stream2"]["frozen_after"]
    assert all(row["cache_hits"]==1 for row in audit["stream1"])
    flags=verify_lifelong_streams(audit,worlds_fixture(),{},991,WorkMeter())
    assert flags["arbitrary_depth_demonstrated"] is False
    assert audit["demonstrated_capability_count"]<7


def test_stream_verifier_rejects_missing_cells_target_feedback_and_fabricated_success(audit):
    for mutate in (lambda a:a["stream1"][0]["cells"].pop(),
        lambda a:a["stream2"].update(target_training_rows=1),
        lambda a:a.update(arbitrary_depth_demonstrated=True),
        lambda a:a.update(adaptive_training_inclusive_work=0)):
        changed=deepcopy(audit);mutate(changed)
        with pytest.raises(ValueError):verify_lifelong_streams(changed,worlds_fixture(),{},991,WorkMeter())


def test_target_generator_refuses_training_purpose_before_sampling():
    with pytest.raises(ValueError,match="evaluation-only"):
        generate_stream_curriculum(worlds_fixture()[-1],24,meter=WorkMeter())


def test_no_capability_can_be_inferred_from_an_empty_or_incomplete_stream():
    a={"execution_status":"INCOMPLETE"}
    result=derive_capability_metrics(a)
    assert result["demonstrated_capability_count"]==0
    assert not result["all_seven_general_capabilities_demonstrated"]


def test_saved_lifelong_attempt_preserves_negative_gates_and_exact_executed_source(monkeypatch):
    import hashlib
    from pathlib import Path
    from nexus.seed.experimental import read
    from scripts.verify_wave24_azr_ruler_cegis import verify_payload
    import scripts.run_wave24_azr_ruler_cegis as runner
    root=Path(__file__).resolve().parents[1]
    record=read(root/"docs/evidence/wave24_azr_dev_lifelong_v5.json")
    for path,source in record["executed_source_snapshot"].items():
        assert hashlib.sha256(source.encode()).hexdigest()==record["payload"]["source_hashes"][path]
    for path,sha in record["excluded_immutable_dependencies"].items():
        assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha
    report=verify_payload(record["payload"],replay=True)
    assert report["integrity_valid"],report["errors"]
    assert not report["ready_for_freeze"]
    assert not report["scientific_gates"]["lifelong_learning_demonstrated"]
    assert not report["scientific_gates"]["meta_learning_symptom_doctor_demonstrated"]
    monkeypatch.setattr(runner.Wave24ResourceHost,"supervise",lambda *a,**k:pytest.fail("second launch"))
    with pytest.raises(ValueError,match="already consumed"):
        runner.main(["--dev-preflight","--allocation-file",str(root/"configs/wave24_azr_dev_lifelong_allocation.json")])

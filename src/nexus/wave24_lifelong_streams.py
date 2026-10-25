"""Locked procedural SOURCE-development orchestration, not an AGI proof.

All behavior is implemented by the existing Wave24 owners. This module owns
only task generation, matched controls, saved traces and arithmetic gates.
"""
from dataclasses import asdict
import random

from nexus.evolution1.catalogue import digest
from nexus.wave24_auto_laws import AutoOperatorFingerprinter, OpenPythonToolboxAdapter
from nexus.wave24_quotient_core import (WorkExhausted, ParametricSkillMacro, apply, variable,
    typed_hole, eval_expr, primitive_cost, solve, expression_wire, freeze, skill_wire)
from nexus.wave24_self_evolving_loop import (World, PublicTask, GeneratedTask, generated_program,
    DualMemoryLearner, ScratchpadWorkspaceEngine, verify_workspace_certificate)


def seed_for(seed, purpose, world):
    return int(digest((seed, purpose, world)), 16)


def task_record(record):
    from scripts.run_wave24_azr_ruler_cegis import task_wire
    return dict(world=record.world, teacher=expression_wire(record.teacher),
        public=task_wire(record.public_view), teacher_query=freeze(record.teacher_query),
        teacher_primitive_cost=record.teacher_primitive_cost, tier=record.tier)


def generate_stream_curriculum(world, seed, *, meter, attempts=64, purpose="source_training", include_followup=True):
    """One deep task, one newly composed task, one exact-repeat cache control.

    Deep eligibility uses only the primitive bound, never the learner's result.
    A missing stratum is incomplete, not a reason to change inputs or retry.
    """
    if purpose not in ("source_training","frozen_evaluation") or world.name=="BIT_CELLULAR_AUTOMATA" and purpose!="frozen_evaluation":
        raise ValueError("fifth-world task generation is evaluation-only")
    rng = random.Random(seed)
    first = None
    for attempt in range(attempts):
        program = generated_program(world.grammar, rng, 6)
        cost = primitive_cost(program, world.grammar.ops)
        if cost <= 3:
            continue
        values = rng.sample(list(world.inputs), min(len(world.inputs), 7))
        public = tuple((x, eval_expr(program,x,world.grammar.ops,meter,"stream_generation_work_units")) for x in values[:-1])
        if len({freeze(y) for _,y in public}) < 2:
            continue
        view = PublicTask(public,values[-1],program.sort)
        static = solve(world.grammar,public,view.query,program.sort,3,quotient=False,meter=meter)
        if static.status != "NO_PROGRAM_IN_BOUNDED_GRAMMAR":
            continue
        answer = eval_expr(program,view.query,world.grammar.ops,meter,"stream_generation_work_units")
        first = GeneratedTask(world.name,program,view,answer,cost,"source_deep",None)
        break
    if first is None:
        raise WorkExhausted("source deep stratum unavailable within the locked generator attempt cap: "+world.name)
    if not include_followup:
        return (first,),dict(attempts=attempt+1,exact_repeat_indices=[],distinct_tasks=1,purpose=purpose,
            selection_rule="seeded_cost_stratum_and_exhaustive_B0_absence_no_proposed_performance_filter")
    options=[o for o in world.grammar.operators if o.inputs==(first.teacher.sort,)]
    program=apply(rng.choice(options),first.teacher)
    values=rng.sample(list(world.inputs),min(len(world.inputs),7))
    public=tuple((x,eval_expr(program,x,world.grammar.ops,meter,"stream_generation_work_units")) for x in values[:-1])
    view=PublicTask(public,values[-1],program.sort)
    second=GeneratedTask(world.name,program,view,eval_expr(program,view.query,world.grammar.ops,meter,"stream_generation_work_units"),
                         primitive_cost(program,world.grammar.ops),"source_composition",None)
    return (first,second,first), dict(attempts=attempt+1, exact_repeat_indices=[2], distinct_tasks=2,purpose=purpose,
        selection_rule="seeded_cost_stratum_and_exhaustive_B0_absence_no_proposed_performance_filter")


def grade(result, expected):
    unique = result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    return dict(unique_correct=unique and tuple(map(freeze,result.query_values))==(freeze(expected),),
                teacher_query_covered=any(freeze(y)==freeze(expected) for y in result.query_values),
                ambiguous=result.status=="AMBIGUOUS_WITNESS_FOUND")


def solve_record(result, report, *, record, method, index):
    from scripts.run_wave24_azr_ruler_cegis import result_wire
    return dict(method=method, index=index, task=task_record(record), result=result_wire(result),
                report=report, **grade(result,record.teacher_query))


def run_lifelong_streams(worlds, config, seed, meter, host, *, progress=None):
    """One bounded developmental cycle, 12 source feedback events, frozen target.

    Three open-toolbox source events are separate from the fifth-world task.
    No target outcomes are ever sent to an update/promotion method.
    """
    learner=DualMemoryLearner(meter=meter,resource_host=host,max_source_updates=16)
    output=dict(schema="wave24_lifelong_audit_v1", scope="finite_source_development_not_general_intelligence",
        execution_status="INCOMPLETE", stream1=[],stream2={},stream3={}, false_certificate_count=0,
        source_feedback_events=0,source_update_domains=[], unseen_world_selfplay_tasks=0,unseen_world_training_rows=0,
        all_seven_general_capabilities_demonstrated=False)
    start=meter.total
    def emit():
        if progress is not None:progress(output)
    try:
        # A fresh cold start for BOTH adaptive and fixed controls. The preceding
        # five-method matrix's library is not selectively supplied to one arm.
        for world in worlds[:-1]:
            roles=AutoOperatorFingerprinter().fingerprint_roles(world.grammar.operators,world.carriers,meter=meter)
            learner.enter(world.name,world.grammar,roles,world.inputs)
            reference=DualMemoryLearner(meter=meter)
            reference.enter(world.name,world.grammar,roles,world.inputs,frozen=True)
            tasks,generation=generate_stream_curriculum(world,seed_for(seed,"lifelong_source",world.name),meter=meter)
            row=dict(world=world.name,generation=generation,cells=[],updates=[], cache_hits=0)
            output["stream1"].append(row); cache={}
            for index,record in enumerate(tasks):
                result,report=learner.solve_task(world.name,record.public_view)
                row["cells"].append(solve_record(result,report,record=record,method="adaptive",index=index))
                baseline,base_report=reference.solve_task(world.name,record.public_view,guided=False)
                row["cells"].append(solve_record(baseline,base_report,record=record,method="fixed_no_learning",index=index))
                key=digest((record.public_view.public_io,record.public_view.query))
                if key in cache:
                    cached,old_report=cache[key];before=meter.total
                    meter.charge("ordinary_cache_lookup_work_units",1+len(record.public_view.public_io))
                    # A proof for this exact task and unchanged grammar can be
                    # reused. It is not forcibly re-searched to slow the baseline.
                    for e in cached.witnesses:
                        for x,_ in record.public_view.public_io:
                            eval_expr(e,x,world.grammar.ops,meter,"ordinary_cache_replay_work_units")
                    cost=meter.total-before
                    cached_report=dict(old_report,total_work=cost,search_work=0,verification_work=cost,
                        decision_total_work=cost,cache_hit=True,proof_scope="identical_task_unchanged_grammar")
                    row["cache_hits"]+=1
                else:
                    cached,cached_report=baseline,dict(base_report,cache_hit=False)
                    cache[key]=(cached,cached_report)
                row["cells"].append(solve_record(cached,cached_report,record=record,method="ordinary_exact_cache",index=index))
                # Answers are exposed only after ALL current choices are locked.
                update=learner.learn_last_source(world.name,observed_query=record.teacher_query)
                row["updates"].append(update);output["source_feedback_events"]+=1;output["source_update_domains"].append(world.name);emit()
            row["active_skills"]=[skill_wire(s) for s in learner.contexts[world.name]["library"].snapshot()]
        # Separate fifth-world arrival: startup operator probes, source recipes,
        # no self-play, no target training and no update calls.
        target=worlds[-1]
        roles=AutoOperatorFingerprinter().fingerprint_roles(target.grammar.operators,target.carriers,meter=meter)
        learner.enter(target.name,target.grammar,roles,target.inputs,frozen=True)
        lineage=learner.import_recipes(target.name)
        target_tasks,generation=generate_stream_curriculum(target,seed_for(seed,"lifelong_frozen_target",target.name),meter=meter,
                                                         purpose="frozen_evaluation",include_followup=False)
        record=target_tasks[0]; frozen_before=learner.fingerprint(); cells=[]
        for guided,name in ((True,"transferred_doctor"),(False,"transferred_unguided")):
            result,report=learner.solve_task(target.name,record.public_view,guided=guided)
            cells.append(solve_record(result,report,record=record,method=name,index=0))
        empty=DualMemoryLearner(meter=meter);empty.enter(target.name,target.grammar,roles,target.inputs,frozen=True)
        result,report=empty.solve_task(target.name,record.public_view,guided=False)
        cells.append(solve_record(result,report,record=record,method="source_free_same_hops",index=0))
        from scripts.run_wave24_azr_ruler_cegis import isolate_learned_guidance_benchmark
        output["guidance_benchmark"]=isolate_learned_guidance_benchmark(
            target.grammar,record.public_view,learner.contexts[target.name]["library"].snapshot(),
            roles,learner.doctor,meter)
        static=solve(target.grammar,record.public_view.public_io,record.public_view.query,record.public_view.output_sort,
                     3,quotient=False,meter=meter)
        from scripts.run_wave24_azr_ruler_cegis import result_wire
        output["stream2"]=dict(cells=cells,generation=generation,lineage=lineage,
            recipes=[asdict(r) for r in learner.recipes.recipes.values()],
            static_b0=result_wire(static),frozen_before=frozen_before,frozen_after=learner.fingerprint(),
            frozen_doctor_source_digest=learner.doctor.critic.source_digest,
            frozen_doctor_parameters=None if learner.doctor.critic.models is None else [(s.tolist(),b.tolist()) for s,b in learner.doctor.critic.models],
            target_feedback_updates=0,target_training_rows=0,target_selfplay_tasks=0)
        emit()
        # Stream3 uses a DIFFERENT raw Python toolbox and explicit source fault
        # injection. These are controlled diagnostics, not unseen confirmation.
        raw=OpenPythonToolboxAdapter().ingest((lambda x:x+1,operator_neg,lambda x:2*x),
            tuple(range(-4,8)),meter=meter)
        domain="OPEN_PYTHON_SOURCE"
        learner.enter(domain,raw.grammar,raw.roles,raw.seed_inputs)
        context=learner.contexts[domain];lib=context["library"]
        unary=raw.grammar.operators[0]
        for count in (2,3,4):
            expr=typed_hole(raw.grammar.input_sort)
            for _ in range(count):expr=apply(unary,expr)
            lib.inject_for_audit(ParametricSkillMacro(expr,(raw.grammar.input_sort,)),raw.grammar,explicitly_enabled=True)
        identity=PublicTask(tuple((x,x) for x in raw.seed_inputs[:-1]),raw.seed_inputs[-1],raw.grammar.input_sort)
        pre,pre_report=learner.solve_task(domain,identity)
        audit=learner.audit_shortcuts(domain,identity)
        post,post_report=learner.solve_task(domain,identity)
        open_world=World(domain,raw.grammar,raw.grammar.input_sort,raw.seed_inputs,{raw.grammar.input_sort:raw.seed_inputs})
        tasks,generation=generate_stream_curriculum(open_world,seed_for(seed,"lifelong_open",domain),meter=meter)
        open_cells=[]
        for index,record in enumerate(tasks):
            result,report=learner.solve_task(domain,record.public_view,invent=True)
            cell=solve_record(result,report,record=record,method="open_source",index=index)
            cell["update"]=learner.learn_last_source(domain,observed_query=record.teacher_query)
            open_cells.append(cell);output["source_feedback_events"]+=1;output["source_update_domains"].append(domain)
        output["stream3"]=dict(raw_operator_count=len(raw.grammar.operators),source_generation=generation,
            poison_audit=audit,quarantined_bad_shortcuts_count=sum(r.get("quarantined",False) for r in audit),
            pre_quarantine_work=pre_report["total_work"],post_quarantine_work=post_report["total_work"],
            pre_post_same_answer=pre.query_values==post.query_values,open_cells=open_cells,
            invented_tools=learner.inventor.promoted,self_audit_adjustments_log=learner.auditor.adjustments,
            final_learner_fingerprint=learner.fingerprint(),checkpoint=learner.export_state())
        output["execution_status"]="COMPLETE";emit()
    except Exception as exc:
        output["execution_status"]="INCOMPLETE" if isinstance(exc,WorkExhausted) else "INVALID"
        output["execution_error"]=type(exc).__name__+": "+str(exc)
    finally:
        output["total_stream_work_units"]=meter.total-start
        output.update(derive_capability_metrics(output))
    return output


def operator_neg(x):
    return -x


def derive_capability_metrics(output):
    """Saved arithmetic only. Never replace absent evidence by a passing flag."""
    streams=output.get("stream1",[]);target=output.get("stream2",{});shift=output.get("stream3",{})
    adaptive=[c for w in streams for c in w["cells"] if c["method"]=="adaptive"]
    fixed_cells=[c for w in streams for c in w["cells"] if c["method"]=="fixed_no_learning"]
    bounded=any(c["unique_correct"] and len(c["report"]["trace"]["workspace"]["hops"])>1 for c in adaptive)
    promoted=sum(len(w.get("active_skills",[])) for w in streams)
    adaptive_work=sum(c["report"]["total_work"] for c in adaptive)+sum(u["learning_work"] for w in streams for u in w["updates"])
    fixed_work=sum(c["report"]["total_work"] for c in fixed_cells)
    cache_work=sum(c["report"]["total_work"] for w in streams for c in w["cells"] if c["method"]=="ordinary_exact_cache")
    adaptive_correct=sum(1 for c in adaptive if c["unique_correct"])
    fixed_correct=sum(1 for c in fixed_cells if c["unique_correct"])
    hop_depths=[len(c["report"]["trace"]["workspace"]["hops"]) for c in adaptive if c["report"].get("trace",{}).get("workspace")]
    first=sum(c["report"]["decision_total_work"] for c in adaptive if c["index"]==0)
    reuse=sum(c["report"]["decision_total_work"] for c in adaptive if c["index"]==2)
    target_cells={c["method"]:c for c in target.get("cells",[])}
    guided=target_cells.get("transferred_doctor");unguided=target_cells.get("transferred_unguided");free=target_cells.get("source_free_same_hops")
    transfer=bool(guided and free and target.get("lineage") and guided["unique_correct"]
        and (not free["unique_correct"] or guided["report"]["total_work"]<free["report"]["total_work"]))
    bench=output.get("guidance_benchmark") or {}
    if bench:
        doctor=bool(guided and unguided and guided["unique_correct"] and unguided["unique_correct"]
            and bench.get("learned_guidance_same_library_work",10**9)<bench.get("fixed_same_library_work",-1))
    else:
        doctor=bool(guided and unguided and guided["unique_correct"] and unguided["unique_correct"]
            and guided["report"]["total_work"]<unguided["report"]["total_work"])
    complete=output.get("execution_status")=="COMPLETE"
    retained=bool(adaptive) and all(c["unique_correct"] for c in adaptive if c["index"]==2)
    flags=dict(arbitrary_depth_demonstrated=False,
        lifelong_learning_demonstrated=bool(complete and promoted and reuse<first and retained
            and adaptive_correct>=fixed_correct and adaptive_work<min(fixed_work,cache_work)),
        cross_domain_transfer_demonstrated=bool(complete and transfer),
        meta_learning_symptom_doctor_demonstrated=bool(complete and doctor),
        closed_loop_self_improvement_demonstrated=bool(complete and shift.get("quarantined_bad_shortcuts_count",0)>=3
            and shift.get("self_audit_adjustments_log") and shift.get("pre_post_same_answer")
            and shift.get("post_quarantine_work",0)<shift.get("pre_quarantine_work",0)),
        self_evolving_tool_invention_demonstrated=bool(complete and shift.get("invented_tools")),
        open_python_sandbox_demonstrated=bool(complete and any(c["unique_correct"] and c["report"]["certificate_valid"] is True
            for c in shift.get("open_cells",[]))))
    extra={}
    if output.get("guidance_benchmark") is not None:
        extra.update(adaptive_stream_correct_count=adaptive_correct,fixed_stream_correct_count=fixed_correct,
            lyapunov_hop_depths=hop_depths,lyapunov_max_hop=max(hop_depths) if hop_depths else 0)
    return dict(**flags, bounded_depth_demonstrated=bounded, bounded_memory_reuse_demonstrated=bool(promoted and reuse<first and retained),
        capability_scope="finite inspected source development; composite helpers; trusted pure callables; no general-AGI evidence",
        arbitrary_depth_limitation="Three hops and primitive cap9 cannot establish arbitrary/unbounded depth or solve every depth12 task.",
        intra_domain_promoted_skills_count=promoted,unseen_world_zero_shot_transferred_skills_count=len(target.get("lineage",[])),
        first_acquisition_work=first,repeated_use_work=reuse,adaptive_training_inclusive_work=adaptive_work,
        fixed_no_learning_work=fixed_work,ordinary_cache_work=cache_work,
        demonstrated_capability_count=sum(flags.values()),all_seven_general_capabilities_demonstrated=all(flags.values()),
        **extra)

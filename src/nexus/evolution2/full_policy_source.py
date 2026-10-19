"""Explicitly authorized, bounded source-physics development return screen.

Reuses trained models, typed compositions, TaskSpec/wrappers and the original
ReservationLedger. No proposer training, checkpoint replacement or old gate
modification. Not the historical H16x16 controller or n=10 confirmation.
"""
from dataclasses import asdict
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np

from nexus.evolution1.catalogue import Rule, digest, plan_bound
from nexus.evolution1.resources import Work, Operation, Clock, Limits, ReservationLedger, model_work
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution2.generated_strategies import leaf, compose, execute
from nexus.evolution2.persist_reset_path import disposable_model
from nexus.evolution2.fit_clock import LOCKED_ARRAYS
from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.rewards import pendulum_step_reward, acrobot_step_reward

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT/"configs/unified_full_policy_source.json"
ALLOCATION = ROOT/"configs/unified_full_policy_source_allocation.json"
PROTOCOL = ROOT/"docs/NEXUS_UNIFIED_FULL_POLICY_SOURCE.md"
RESULT = ROOT/"artifacts/unified_full_policy_source.json"
JOURNAL = ROOT/"artifacts/unified_full_policy_resources.jsonl.gz"
USAGE = ROOT/"artifacts/unified_full_policy_usage.json"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_file(path, expected):
    if sha(path)!=expected: raise ValueError("file_hash_mismatch")


def verify_checkpoints(rows,c):
    expected=set(itertools.product(c["families"],c["model_bundles"]))
    ids=[(r["family"],r["bundle"]) for r in rows]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError("checkpoint_grid")
    for r in rows:verify_file(ROOT/r["path"],r["sha256"])


def controllers():
    a,b = ANCHORS
    return {"flat_anchor":leaf(a),"successor_anchor":leaf(b),
            "switch":compose("switch",a,b,.25),"rank_blend":compose("rank_blend",a,b)}


def seeds(config,family,bundle,episode):
    f=config["families"].index(family)
    return (config["env_seed_base"]+f*10000+bundle*100+episode,
            config["planner_seed_base"]+f*10000+bundle*1000+episode*200)


def requested_seeds(c):
    env,planner=set(),set()
    for f,b,e in itertools.product(c["families"],c["model_bundles"],c["episodes"]):
        reset,base=seeds(c,f,b,e); env.add(reset)
        planner.update(range(base,base+c["episode_steps"]))
    if env & planner or len(env)!=8 or len(planner)!=1600: raise ValueError("seed_schedule_collision")
    return env|planner


def seed_collisions(value,candidates):
    """Inspect integer seed metadata only; never return historical outcomes."""
    found=set()
    def visit(x,in_seed=False):
        if type(x) is dict:
            for k,v in x.items(): visit(v,in_seed or "seed" in str(k).lower())
        elif type(x) in (list,tuple):
            for v in x: visit(v,in_seed)
        elif in_seed and type(x) is int and x in candidates: found.add(x)
    visit(value)
    return found


def state_hash(model):
    h=hashlib.sha256()
    for name,t in sorted(model.net.state_dict().items()):
        a=t.detach().cpu().numpy(); h.update(name.encode()); h.update(str((a.shape,a.dtype)).encode()); h.update(a.tobytes())
    for name,v in sorted({**model.obs_rms.state_dict(),"epsilon":model.obs_rms.epsilon}.items()):
        a=np.asarray(v);h.update(name.encode());h.update(str((a.shape,a.dtype)).encode());h.update(a.tobytes())
    return h.hexdigest()


def operation_plan(strategy,obs,n_actions):
    ops=[]
    for v,cap in strategy.components(obs):
        n=plan_bound(v,n_actions,cap).candidates_per_root
        for _ in range(1 if v.rule is Rule.FLAT else n_actions):
            if v.rule is Rule.SUCCESSOR: ops.append(model_work((1,len(obs)),1))
            ops.extend(model_work((n,len(obs)),n) for _ in range(v.horizon))
    return tuple(Operation(f"model_{i}","model",cost) for i,cost in enumerate(ops)) + (Operation("environment","environment",Work(real_steps=1)),)


def task_spec(family):
    if family=="pendulum":
        return TaskSpec("unified_source_pendulum",family,"Pendulum-v1",3,3,
                        {"g":10.,"m":1.,"l":1.,"torque_neg":-2.,"torque_zero":0.,"torque_pos":2.})
    if family=="acrobot":
        return TaskSpec("unified_source_acrobot",family,"Acrobot-v1",6,3,
                        {"LINK_MASS_1":1.,"LINK_MASS_2":1.,"LINK_LENGTH_1":1.})
    raise ValueError("source_family_only")


def validate_config(c):
    expected={"version":"full_policy_source_v1","families":["pendulum","acrobot"],"model_bundles":[0,1],
      "episodes":[0,1],"controllers":["flat_anchor","successor_anchor","switch","rank_blend"],"episode_steps":200,
      "env_seed_base":2103000000,"planner_seed_base":2104000000,"imagined_per_decision":1536,
      "env_cap":6400,"imagined_cap":9830400,"time_cap_s":180,"practical_margin":1.0}
    if json.dumps(c,sort_keys=True)!=json.dumps(expected,sort_keys=True): raise ValueError("locked_configuration_mismatch")


def validate_result(p,c):
    validate_config(c)
    expected=set(itertools.product(c["families"],c["model_bundles"],c["episodes"],c["controllers"]))
    rows=p["episodes"]
    ids=[(r["family"],r["model_bundle"],r["episode"],r["controller"]) for r in rows]
    if len(ids)!=len(expected) or set(ids)!=expected: raise ValueError("incomplete_episode_grid")
    for r in rows:
        if type(r["model_bundle"]) is not int or type(r["episode"]) is not int: raise ValueError("invalid_identity")
        if len(r["steps"])!=200 or [s["tick"] for s in r["steps"]]!=list(range(200)): raise ValueError("incomplete_step_grid")
        if any(type(s["reward"]) not in (int,float) or not math.isfinite(s["reward"]) for s in r["steps"]): raise ValueError("invalid_reward")
        if type(r["return"]) not in (int,float) or not math.isfinite(r["return"]):raise ValueError("invalid_return")
        if not math.isclose(sum(s["reward"] for s in r["steps"]),r["return"],abs_tol=1e-9): raise ValueError("reward_accounting")
        reset,base=seeds(c,r["family"],r["model_bundle"],r["episode"])
        if r["reset_seed"]!=reset or r["planner_base"]!=base:raise ValueError("seed_pairing")
        for i,s in enumerate(r["steps"]):
            if s["planner_seed"]!=base+i:raise ValueError("planner_pairing")
            if type(s["action"]) is not int or s["action"] not in range(3):raise ValueError("action_index")
            size=3 if r["family"]=="pendulum" else 6
            for key in ("obs","next_obs"):
                if np.asarray(s[key]).shape!=(size,) or not np.isfinite(s[key]).all():raise ValueError("observation_schema")
            if i and s["obs"]!=r["steps"][i-1]["next_obs"]:raise ValueError("transition_continuity")
            if s["terminated"] is not False or s["truncated"] is not (i==199):raise ValueError("termination_schedule")
        if digest(r["steps"][0]["obs"])!=r["initial_obs_hash"]:raise ValueError("initial_state_hash")
    if p["resources"]["completed"]["real_steps"]!=6400 or p["resources"]["unknown_upper"]!={k:0 for k in Work().payload()}:
        raise ValueError("incomplete_resource_work")
    for f,b,e in itertools.product(c["families"],c["model_bundles"],c["episodes"]):
        group=[r for r in rows if (r["family"],r["model_bundle"],r["episode"])==(f,b,e)]
        if len({r["initial_obs_hash"] for r in group})!=1 or len({r["reset_seed"] for r in group})!=1:
            raise ValueError("unpaired_reset")
    return True


def analyze(rows,c):
    contrasts={}
    for f in c["families"]:
        family={}
        for generated in ("switch","rank_blend"):
            checks={}
            for anchor in ("flat_anchor","successor_anchor"):
                pairs=[]
                for b in c["model_bundles"]:
                    diffs=[]
                    for e in c["episodes"]:
                        values={r["controller"]:r["return"] for r in rows if (r["family"],r["model_bundle"],r["episode"])==(f,b,e)}
                        diffs.append(values[generated]-values[anchor])
                    pairs.append(sum(diffs)/2)
                checks[anchor]={"per_model":pairs,"mean":sum(pairs)/2,
                    "point_screen":sum(pairs)/2>=c["practical_margin"] and all(x>0 for x in pairs)}
            family[generated]=checks
        contrasts[f]=family
    passed={g:all(contrasts[f][g][a]["point_screen"] for f in c["families"] for a in ("flat_anchor","successor_anchor")) for g in ("switch","rank_blend")}
    return {"paired_contrasts":contrasts,"point_screen_by_generated":passed,
            "scientific_control_success":False,"independent_model_count_per_family":2,
            "intervals":"Not reported: exploratory n=2 source-model pairs per family; no ten-decoder inference."}


def run(c):
    validate_config(c)
    t0,cpu0=time.perf_counter(),time.process_time()
    deadline=t0+c["time_cap_s"]
    old={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"artifacts").rglob("*.json") if p not in (RESULT,USAGE)}
    allocation=json.loads(ALLOCATION.read_text())
    if allocation["config_sha256"]!=sha(CONFIG) or allocation["protocol_sha256"]!=sha(PROTOCOL) or not allocation["authorized"]:
        raise ValueError("allocation_integrity")
    if allocation["time_cap_s"]!=c["time_cap_s"] or allocation["env_cap"]!=c["env_cap"] or allocation["imagined_cap"]!=c["imagined_cap"]:
        raise ValueError("allocation_cap_mismatch")
    if USAGE.exists() or JOURNAL.exists(): raise FileExistsError("one_run_already_started")
    with USAGE.open("x") as use:
        use.write(json.dumps({"consumed":True,"allocation_sha256":sha(ALLOCATION),"automatic_retry":False})+"\n")
    state={"reserved":Work(),"completed":Work(),"unknown_upper":Work()}
    limits=Work(real_steps=c["env_cap"],imagined_transitions=c["imagined_cap"],model_calls=428800,network_forwards=428800)
    p={"declared_complete":False,"development_only":True,"episodes":[],"models":[],"resources":{},
       "config":c,"historical_artifacts_sha256":old,"authorization":allocation}
    clock=lambda:Clock(int((time.process_time()-cpu0)*1e9),int((time.perf_counter()-t0)*1e9))
    try:
        candidates=requested_seeds(c)
        collisions={name:sorted(seed_collisions(json.loads((ROOT/name).read_text()),candidates)) for name in old}
        collisions={k:v for k,v in collisions.items() if v}
        registry=json.loads((ROOT/"artifacts/h17_exclusion_registry_audit_validated.json").read_text())
        if collisions or any(lo<=s<=hi for s in candidates for lo,hi in registry["conservative_seed_reservations"]):
            raise ValueError("historical_seed_collision")
        p["seed_audit"]={"historical_json_count":len(old),"explicit_seed_collisions":collisions,
            "conservative_h17_ranges_disjoint":True,"planned_unique_seed_count":len(candidates),
            "scope":"Reachable-tree seed metadata and preserved historical registry, not unavailable external runs."}
        manifest=json.loads((ROOT/"artifacts/evolution2_fit_clock_run.json").read_text())
        selected=[r for r in manifest["fits"] if r["bundle"] in c["model_bundles"]]
        verify_checkpoints(selected,c)
        p["source_arrays"]=[r for r in LOCKED_ARRAYS if r["bundle"] in c["model_bundles"]]
        for r in p["source_arrays"]:
            verify_file(ROOT/r["path"],r["sha256"])
            with np.load(ROOT/r["path"]) as source:
                if set(source["env_seeds"].reshape(-1).tolist()) & candidates:raise ValueError("source_episode_seed_collision")
        p["fit_manifest_sha256"]=sha(ROOT/"artifacts/evolution2_fit_clock_run.json")
        with gzip.open(JOURNAL,"xb") as journal:
            for r in selected:
                if time.perf_counter()>=deadline:raise TimeoutError("time_cap")
                f,b=r["family"],r["bundle"]
                model=disposable_model(f,b)
                if (str(model.device)!="cpu" or model.net.arch!="mlp" or model.kind!="residual"
                    or tuple(model.net.hidden)!=(64,64) or model.net.obs_dim!=task_spec(f).obs_dim or model.net.n_actions!=3):
                    raise ValueError("frozen_cpu_residual_mlp_required")
                model.net.eval()
                for param in model.net.parameters():param.requires_grad_(False)
                fingerprint=state_hash(model)
                for e in c["episodes"]:
                    reset,planner=seeds(c,f,b,e)
                    for label,strategy in controllers().items():
                        if time.perf_counter()>=deadline:raise TimeoutError("time_cap")
                        env=make_task_env(task_spec(f),seed=reset)
                        obs,_=env.reset(seed=reset)
                        episode={"family":f,"model_bundle":b,"episode":e,"controller":label,"reset_seed":reset,
                                 "planner_base":planner,"initial_obs_hash":digest(np.asarray(obs).tolist()),"steps":[],"return":0.}
                        p["episodes"].append(episode)
                        try:
                            for tick in range(c["episode_steps"]):
                                ops=operation_plan(strategy,obs,3)
                                upper=Work()
                                for op in ops:upper=upper.plus(op.cost)
                                if not state["reserved"].plus(upper).fits(limits): raise RuntimeError("global_work_cap")
                                ledger=ReservationLedger(ops,Limits(upper,upper,int(c["time_cap_s"]*1e9),int(c["time_cap_s"]*1e9)))
                                cursor=[0]
                                class MeteredModel:
                                    def step(self,o,a):
                                        if time.perf_counter()>=deadline:raise TimeoutError("time_cap")
                                        op=ops[cursor[0]]
                                        actual=model_work(np.asarray(o).reshape(-1,len(obs)).shape,int(np.asarray(a).size))
                                        if actual!=op.cost:raise ValueError("unplanned_model_call")
                                        ticket=ledger.reserve(op.key,clock());state["reserved"]=state["reserved"].plus(op.cost)
                                        try:out=model.step(o,a)
                                        except BaseException:ledger.settle(ticket,"interrupted",clock());raise
                                        ledger.settle(ticket,"success",clock());cursor[0]+=1
                                        return out
                                try:
                                    start=time.perf_counter()
                                    action=execute(strategy,f,obs,MeteredModel(),seed=planner+tick)
                                    latency=time.perf_counter()-start
                                    if cursor[0]!=len(ops)-1:raise ValueError("model_call_plan_incomplete")
                                    if time.perf_counter()>=deadline:raise TimeoutError("time_cap")
                                    ticket=ledger.reserve("environment",clock())
                                    state["reserved"]=state["reserved"].plus(Work(real_steps=1))
                                    try:nxt,reward,terminated,truncated,info=env.step(action)
                                    except BaseException:ledger.settle(ticket,"interrupted",clock());raise
                                    ledger.settle(ticket,"success",clock())
                                    published=pendulum_step_reward(obs,action,nxt) if f=="pendulum" else acrobot_step_reward(obs,action,nxt)
                                    # Gym's hidden float64 state is observed as float32.
                                    if not math.isclose(float(published[0]),float(reward),abs_tol=1e-5):raise ValueError("reward_timing_mismatch")
                                    episode["steps"].append({"tick":tick,"obs":np.asarray(obs).tolist(),"action":int(action),"reward":float(reward),
                                        "next_obs":np.asarray(nxt).tolist(),"planner_seed":planner+tick,"planning_s":latency,
                                        "terminated":bool(terminated),"truncated":bool(truncated)})
                                    episode["return"]+=float(reward);obs=nxt
                                finally:
                                    report=ledger.close(clock())
                                    state["completed"]=state["completed"].plus(report.physical_completed_reported)
                                    state["unknown_upper"]=state["unknown_upper"].plus(report.physical_unknown_upper_bound)
                                    journal.write((json.dumps({"family":f,"model":b,"episode":e,"controller":label,"tick":tick,
                                        "events":[asdict(x) for x in report.events],"status":report.status})+"\n").encode())
                                if report.status!="complete_execution":raise RuntimeError("incomplete_decision")
                                if terminated or truncated:
                                    if tick!=199:raise ValueError("unexpected_early_termination")
                                    break
                        finally:env.close()
                after=state_hash(model)
                if after!=fingerprint or sha(ROOT/r["path"])!=r["sha256"]:raise ValueError("frozen_model_changed")
                p["models"].append({**r,"before":fingerprint,"after":after})
        p["resources"]={k:v.payload() for k,v in state.items()}
        validate_result(p,c)
        p["analysis"]=analyze(p["episodes"],c)
        if any(sha(ROOT/n)!=h for n,h in old.items()):raise ValueError("history_changed")
        if time.perf_counter()>=deadline:raise TimeoutError("time_cap")
        p["declared_complete"]=True
    except Exception as exc:p["failure"]=f"{type(exc).__name__}: {exc}"
    p["resources"]={**{k:v.payload() for k,v in state.items()},"wall_s":time.perf_counter()-t0,"cpu_s":time.process_time()-cpu0}
    if JOURNAL.exists():p["resource_journal_sha256"]=sha(JOURNAL)
    start=json.loads((ROOT/"artifacts/unified_headroom_audit.json").read_text())["session_ledger"]["used_after_s"]
    p["session_ledger"]={"used_before_s":start,"used_after_s":start+p["resources"]["wall_s"],"remaining_after_s":3600-start-p["resources"]["wall_s"]}
    return p

"""x7 runner (NOT LOCKED): ONE (project, build group) per call; one atomic structured result file per arm.
  python scripts/x7_run.py SPLIT IDENT GROUP [TAG]
SPLIT: sc_dev | x7_dev (development; IDENT = seed; TAG = attempt directory) | x7_pcheck (HELPER only) | x7_val | x7_val_b |
       x7_test (one-use; IDENT = index; claimed whole by the first call; x7_test reads only sealed blobs whose sha256 match
       artifacts/x7_test_vault/MANIFEST.json and needs NEXUS_SEALED_HARNESS_TOKEN).
GROUP (arms that share one lifecycle build; every arm operates separately on a fresh copy):
  L    Expression_Learned (A), FieldOnly_Learned (B) [+ with TAG 'ablation': NoPrune_Learned, NoMapping_Learned]
  H    Expression_Hand (C)        S    Expression_Shuffled (D)
  SC   Frozen_SC (sc SchemaRepair_Learned at d23c9fa, unchanged code, own full build)
  F    Fixed_Policy, Conventional
  HELPER  platform check: corrected simulated human vs the reference on every tick (+ checkpoint resume), format counts
The A stream (status / value programs) is built ONCE per project by the first NEXUS x7 group and cached
(abuild_p<IDENT>.pkl); every x7 arm deploys it. All NEXUS x7 arms operate under the same operator randomness (paired spot
checks). One in-process alarm (840 s) per call: the running arm is TIMED_OUT, arms not started are NOT_RUN; a completed
(project, arm) never reruns. Writes artifacts/x7_<split>[/TAG]/p<IDENT>_<ARM>.json (temp file + rename)."""
import copy, hashlib, json, os, pickle, random, signal, sys, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from u5_run import learners
from nexus import x7_seeds, x7_platform as XP, sc_platform as SCP, seed_registry as R, u5_stateful as SF  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
ALARM_S = 840
SCHEMA_FAULTS = ("X6", "X6P", "X6D", "X6M", "XD1", "XD2", "XD3", "X7a", "X7b")
PRIMARY = {"Expression_Learned": ("learned", "expression", True), "FieldOnly_Learned": ("learned", "field", True),
           "Expression_Hand": ("hand", "expression", True), "Expression_Shuffled": ("shuffled", "expression", True),
           "NoPrune_Learned": ("learned", "expression", False), "NoMapping_Learned": ("learned", None, True)}
GROUPS = {"L": ["Expression_Learned", "FieldOnly_Learned"], "H": ["Expression_Hand"], "S": ["Expression_Shuffled"],
          "SC": ["Frozen_SC"], "F": ["Fixed_Policy", "Conventional"], "HELPER": ["HELPER"]}


class ArmTimeout(Exception):
    pass


_LEARNERS = []


def _learner():
    if not _LEARNERS:
        nx, _ = learners()
        _LEARNERS.append(nx["NEXUS_U5"][0])
    return _LEARNERS[0]


def x7_arm(name):
    growth, mapping, prune = PRIMARY[name]
    a = XP.NexusArmX7("x7", _learner())                       # one operator-randomness name for all x7 arms
    a.label, a.growth, a.mapping, a.prune = name, ba_eps.policy(growth, "bounded"), mapping, prune
    return a


def frozen_sc_arm():
    a = SCP.NexusArmSchema("SchemaRepair_Learned", _learner())
    a.growth, a.mapping_repair = ba_eps.policy("learned", "bounded"), True
    return a


def outcome(P, arm, prog, info, build_cost, label):
    c0, w0 = time.process_time(), time.perf_counter()
    base = dict(project=P.seed, domain=P.domain, fault=P.fault, lifecycle=P.sfam, arm=label)
    if prog is None:
        return dict(base, outcome="ABSTAIN", completed=False, data_ok=False, claims_healthy=False, silent=False, human_repairs=0,
                    independently_correct=False, build=info, log=getattr(arm, "log", []), queries=dict(P.queries), cost=build_cost,
                    solution_sources=dict(stage="abstain_at_build"))
    archive = dict(envs=[], status=[])
    for t in range(1, XP.PL.BUILD_TICKS + 1):
        reg = P.ticks[t]["registry"]
        archive["envs"] += [{"r": r, "t": reg} for r in P.ticks[t]["A"]]
        archive["status"] += [P.ref_A(r, reg)[0] for r in P.ticks[t]["A"]]
    crash_tick = random.Random(f"crash-{P.seed}").randint(10, 15)
    build_src = prog.source()
    res = XP.PL.operate(P, arm, prog, crash_tick, archive)
    truth = P.truth()
    served, who, per = {}, "nexus", {}
    for x in res["ledger"]:
        if x["kind"] == "escalated":
            who = "human"
        if x["kind"] in ("tick", "escalated", "repair_B", "repair_A"):
            served[x["tick"]] = who
    marker = 0
    for t, tr in truth.items():
        o = res["outputs"][t]
        bA = sum(not XP.PL._rowA_eq(g, w) for g, w in zip(o["A"], tr["A"]))
        bB = sum(not SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(o["B"], tr["B"]))
        mk = sum(any(r[0] == "?schema_mismatch" for r in g) for g in o["B"])
        marker += mk
        per[t] = dict(bad_A=bA, bad_B=bB, unresolved_rows=mk, served_by=served.get(t, who))
    data_ok = all(v["bad_A"] == 0 and v["bad_B"] == 0 for v in per.values())
    alarms = {x["tick"]: x["alarms"] for x in res["ledger"] if x["kind"] == "tick"}
    bdet = [t for t, a in sorted(alarms.items()) if any(s.startswith("B:") for s in a)]
    sdet = [t for t, a in sorted(alarms.items()) if "B:schema_mismatch" in a]
    shdet = [t for t, a in sorted(alarms.items()) if "B:shape_change" in a]
    rep = [x["tick"] for x in res["ledger"] if x["kind"] == "repair_B"]
    esc = [x["tick"] for x in res["ledger"] if x["kind"] == "escalated"]
    nexus_wrong = sum(v["bad_A"] + v["bad_B"] - v["unresolved_rows"] for v in per.values() if v["served_by"] == "nexus")
    human_wrong = sum(v["bad_A"] + v["bad_B"] for v in per.values() if v["served_by"] == "human")
    log = getattr(arm, "log", [])
    learns = [x for x in log if x.get("step") == "learn" and x.get("accepted")]
    maps = [x for x in log if x.get("step") == "mapping_repair"]
    accepted = [m for m in maps if str(m.get("outcome", "")).startswith("ADAPTER_ACCEPTED")]
    stages = []
    for m in accepted:
        tr = m.get("mapping", {}).get("tier")
        stages.append("lifecycle relearning (with adapter)" if tr == "relearn" else "field selection" if tr == 0 else "expression synthesis")
    if any(m.get("outcome") == "SHAPE_VERIFIED_BENIGN" for m in maps):
        stages.append("shape verified benign")
    if len(learns) > 1:
        stages.append("lifecycle relearning")
    if res["human_repairs"]:
        stages.append("human assistance")
    fault_tick = XP.PL.FAULT_TICK
    ops_cpu = time.process_time() - c0
    out = dict(base, outcome="COMPLETED", completed=True, data_ok=data_ok, claims_healthy=res["claims_healthy"],
               silent=res["claims_healthy"] and not data_ok, incorrect_healthy_claim=res["claims_healthy"] and not data_ok,
               human_repairs=res["human_repairs"], independently_correct=data_ok and res["human_repairs"] == 0, crash_ok=res["crash_ok"],
               fields=dict(wrong_machine_deployed=nexus_wrong > 0, nexus_served_wrong_rows=nexus_wrong, schema_fault=P.fault in SCHEMA_FAULTS,
                           first_B_alarm_tick=bdet[0] if bdet else None, schema_alarm_tick=sdet[0] if sdet else None,
                           shape_alarm_tick=shdet[0] if shdet else None,
                           detection_delay_ticks=(bdet[0] - fault_tick) if bdet else None,
                           recovery_delay_ticks=(rep[0] - bdet[0]) if rep and bdet else None,
                           schema_fault_missed=P.fault in SCHEMA_FAULTS and not bdet, escalation_ticks=esc,
                           wrong_accepted_adapters=sum(1 for m in accepted if nexus_wrong > 0),
                           false_schema_incidents=len(sdet) if P.fault not in SCHEMA_FAULTS else 0,
                           unresolved_rows_final=marker, human_repair_failed=human_wrong > 0, human_served_wrong_rows=human_wrong),
               solution_sources=dict(build=learns[0].get("learner") if learns else None, build_growth_steps=learns[0].get("growth_steps") if learns else None,
                                     relearns=[x.get("learner") for x in learns[1:]], mapping=[m.get("outcome") for m in maps],
                                     stages=stages or ["build only"], human=res["human_repairs"]),
               adapters=[m.get("mapping") for m in accepted], per_tick=per, ledger=res["ledger"], log=log, build=info,
               cost=dict(build_cost, ops_cpu_s=round(ops_cpu, 3), operator_ops_cpu_s=res["ops_cpu_s"],
                         ops_wall_s=round(time.perf_counter() - w0, 3), queries=dict(P.queries),
                         mapping_cpu_s=round(sum(m.get("cpu_s", 0) for m in maps), 3), mapping_mq=sum(m.get("mq", 0) for m in maps),
                         relearn_cpu_s=round(sum(x.get("cpu_s", 0) for x in learns[1:]), 3)),
               build_source=build_src)
    try:
        out["deployed_source"] = res["program"].source()
    except Exception:                                                # noqa: BLE001
        out["deployed_source"] = None
    return out


def project(split, ident):
    if split in ("sc_dev", "x7_dev"):
        return int(ident), XP.Project(int(ident), split)
    key = ("x7", split[3:])
    seeds = list(R.REGISTRY[key])
    s = seeds[int(ident)]
    if split != "x7_test":
        return s, XP.Project(s, split)
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
    man = json.loads((ROOT / "artifacts/x7_test_vault/MANIFEST.json").read_text())
    rel = f"x7_test/{int(ident)}.json"
    blob = (Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / rel).read_bytes()
    if hashlib.sha256(blob).hexdigest() != man["files"][rel]:
        raise SystemExit("vault blob does not match the manifest")
    return s, XP.PL.Project.from_json(blob.decode())


def helper_check(P):
    """Corrected simulated human (HumanRefX7) vs the reference, every tick, + resume from a mid-stream checkpoint."""
    allB = [e for t in range(1, XP.PL.TICKS + 1) for e in P.ticks[t]["B"]]
    want = P.ref_B(allB)
    h = XP.HumanRefX7(P)
    got = [h.ingest(e) for e in allB]
    bad = sum(not SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(got, want))
    h2 = XP.HumanRefX7(P)
    half = len(allB) // 2
    for e in allB[:half]:
        h2.ingest(e)
    st = h2.get_state()
    h3 = XP.HumanRefX7(P)
    h3.set_state(st)
    bad_resume = sum(not SF.rows_eq(list(map(tuple, h3.ingest(e))), w) for e, w in zip(allB[half:], want[half:]))
    f = P.schema.val
    fmt = {}
    for t in range(XP.PL.FAULT_TICK, XP.PL.TICKS + 1):
        for e in P.ticks[t]["B"]:
            k = ",".join(sorted(p for p in e if p.startswith(f) or p.endswith("_id")))
            fmt[k] = fmt.get(k, 0) + 1
    late = [w for e, w in zip(allB, want) if e[P.schema.seq] >= XP.PL.FAULT_TICK * 1000]
    nonzero = sum(1 for rows in late for r in rows if isinstance(r[1], (int, float)) and r[1] != 0)
    return dict(project=P.seed, domain=P.domain, fault=P.fault, events=len(allB), wrong_rows=bad, wrong_rows_after_resume=bad_resume,
                late_formats=fmt, late_rows_with_values=nonzero)


def main():
    split, ident, group = sys.argv[1], sys.argv[2], sys.argv[3]
    tag = sys.argv[4] if len(sys.argv) > 4 else None
    if split in ("x7_val", "x7_val_b", "x7_test"):
        fr = json.loads((ROOT / "artifacts/x7_freeze.json").read_text())
        for f, h in fr["files"].items():
            if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h:
                raise SystemExit(f"code differs from the freeze: {f}")
        if split == "x7_val_b" and not fr.get("revision"):
            raise SystemExit("val_b only after one disclosed revision")
        if split == "x7_test":
            gate = ROOT / ("artifacts/x7_val_b/gate.json" if fr.get("revision") else "artifacts/x7_val/gate.json")
            if not json.loads(gate.read_text())["passed"]:
                raise SystemExit("validation gate not passed: the confirmation stays closed")
        if group not in fr["groups"][split]:
            raise SystemExit(f"group {group} is not pre-registered for {split}")
        key = ("x7", split[3:])
        if not any(tuple(r["key"]) == key for r in R._spent() if "override" not in r):
            R.claim("x7", split[3:], list(R.REGISTRY[key]), run_id=f"x7-{split}")
    elif split == "x7_pcheck" and group != "HELPER":
        raise SystemExit("x7_pcheck is a platform check: no NEXUS arm runs on it")
    d = ROOT / f"artifacts/{split}" if split.startswith("x7_") else ROOT / "artifacts/x7_sc_dev"
    if tag:
        d = d / tag
    d.mkdir(parents=True, exist_ok=True)
    arms = list(GROUPS[group]) + (["NoPrune_Learned", "NoMapping_Learned"] if group == "L" and tag == "ablation" else [])
    outs = {a: d / f"p{ident}_{a}.json" for a in arms}
    if any(o.exists() for o in outs.values()):
        raise SystemExit("this (project, group) already ran: no rerun")
    s, P0 = project(split, ident)

    def write(a, r, status):
        tmp = outs[a].with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(split=split, ident=ident, seed=s, arm=a, group=group, status=status, result=r), indent=1, default=str))
        os.replace(tmp, outs[a])
        f = r.get("fields", {})
        print(s, r.get("domain"), r.get("fault"), a, r.get("outcome"), "OK" if r.get("data_ok") else "BAD",
              "indep" if r.get("independently_correct") else "-", "SILENT" if r.get("silent") else "", "human", r.get("human_repairs"),
              "alarm", f.get("first_B_alarm_tick"), "stages", (r.get("solution_sources") or {}).get("stages"), flush=True)

    if group == "HELPER":
        write("HELPER", helper_check(P0), "COMPLETE")
        return

    def _alarm(*_):
        raise ArmTimeout
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(ALARM_S)
    pending = list(arms)
    try:
        P = copy.deepcopy(P0)
        if group in ("L", "H", "S"):
            cache = d / f"abuild_p{ident}.pkl"
            builder = x7_arm(arms[0])
            c0 = time.process_time()
            if cache.exists():
                A = pickle.loads(cache.read_bytes())
                a_cached = True
            else:
                A = builder.build_A(P)
                A["build_labels_A"] = P.queries["build_labels"]
                cache.write_bytes(pickle.dumps(A))
                a_cached = False
            P.queries["build_labels"] = A["build_labels_A"]
            c1 = time.process_time()
            evs = [e for t in range(1, XP.PL.BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
            outs_b = P.oracle_B(evs, "build_labels")
            r = builder._learn(evs, outs_b, lambda x: P.oracle_B(x), P.seed)
            learn_log = list(builder.log)
            bcost = dict(build_A_cpu_s=A["info"]["build_A_cpu_s"], build_A_shared=True, build_A_cached_here=a_cached,
                         build_B_cpu_s=round(time.process_time() - c1, 3), build_B_shared_by=arms, build_wall_s=None,
                         build_queries=dict(P.queries))
            Pq = dict(P.queries)
            for a in arms:
                arm = x7_arm(a)
                arm.log = copy.deepcopy(learn_log)
                Pa = copy.deepcopy(P0)
                Pa.queries = dict(Pq)
                if r is None or A["status"] is None or A["value"] is None:
                    prog, info = None, dict(A["info"], unsolved=[n for n, x in (("status", A["status"]), ("value", A["value"]), ("lifecycle", r)) if x is None])
                else:
                    pl = arm._payload(r, evs)
                    prog = XP.PL.Program(A["value"], A["status"], arm.learner["lib"], "contract", pl)
                    info = dict(A["info"], n_modes=pl["n_modes"], n_regs=pl["n_regs"], b_queries=pl["queries"])
                write(a, outcome(Pa, arm, prog, info, bcost, a), "COMPLETE")
                pending.remove(a)
        else:
            for a in arms:
                arm = frozen_sc_arm() if a == "Frozen_SC" else XP.FixedArm(a) if a == "Fixed_Policy" else \
                    XP.FixedArm(a, monitored=False, handle_units=False)
                Pa = copy.deepcopy(P0)
                c0 = time.process_time()
                prog, info = arm.build(Pa)
                bcost = dict(build_cpu_s=round(time.process_time() - c0, 3), build_queries=dict(Pa.queries))
                write(a, outcome(Pa, arm, prog, info, bcost, a), "COMPLETE")
                pending.remove(a)
    except ArmTimeout:
        for i, a in enumerate(pending):
            write(a, dict(project=s, domain=P0.domain, fault=P0.fault, outcome="TIMED_OUT" if i == 0 else "NOT_RUN_TIMEOUT", completed=False,
                          data_ok=False, silent=False, human_repairs=0, independently_correct=False), "COMPLETE")
    except Exception as e:                                           # noqa: BLE001
        err = type(e).__name__ if split == "x7_test" else traceback.format_exc()
        for i, a in enumerate(pending):
            write(a, dict(project=s, domain=P0.domain, fault=P0.fault, outcome="CRASHED" if i == 0 else "NOT_RUN_CRASH", completed=False,
                          data_ok=False, silent=False, human_repairs=0, independently_correct=False, error=err), "CRASHED")
        print(err)
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()

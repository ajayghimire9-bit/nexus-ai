"""sc runner (NOT LOCKED): ONE (project, arm) per call; an atomic structured result per call; separated outcome fields.
  python scripts/sc_run.py SPLIT SEED_OR_INDEX ARM [DEV_TAG]
SPLIT: sc_dev (development; SEED) | val | val_b | test (one-use; INDEX; claimed whole by the first call; test reads only
sealed blobs whose sha256 match artifacts/sc_test_vault/MANIFEST.json and needs NEXUS_SEALED_HARNESS_TOKEN).
ARM: SchemaRepair_Learned | SchemaRepair_Hand | SchemaRepair_Shuffled | NoMapping_Learned | NEXUS_Confirmed (val/test: the
frozen choice in artifacts/sc_freeze.json) | NEXUS_U5 | Fixed_Policy | Conventional.
Each arm runs under an in-process 780 s alarm (TIMED_OUT outcome instead of a shell kill). A completed (project, arm) never
reruns. Writes artifacts/sc_<split>/p<k>_<ARM>.json (temp file + rename)."""
import hashlib, json, os, random, signal, sys, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from u5_run import learners
from nexus import sc_seeds, sc_platform as SCP, seed_registry as R, u5_stateful as SF  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
ALARM_S = 780
GROWTH = {"SchemaRepair_Learned": "learned", "SchemaRepair_Hand": "hand", "SchemaRepair_Shuffled": "shuffled",
          "NoMapping_Learned": "learned"}
X6_FAMILY = ("X6", "X6P", "X6D", "X6M")


class ArmTimeout(Exception):
    pass


def make_arm(name, fr=None):
    if name == "NEXUS_Confirmed":
        name = fr["nexus_confirmed_arm"]
    nx, _ = learners()
    L = nx["NEXUS_U5"][0]
    if name in GROWTH:
        a = SCP.NexusArmSchema(name, L)
        a.growth = ba_eps.policy(GROWTH[name], "bounded")
        a.mapping_repair = name != "NoMapping_Learned"
        return a
    if name == "NEXUS_U5":
        return SCP.NexusArm(name, L)
    if name == "Fixed_Policy":
        return SCP.FixedArm(name)
    return SCP.FixedArm(name, monitored=False, handle_units=False)


def run(P, arm):
    """u5 run_project + per-tick attribution (who served each tick) and the separated outcome fields."""
    c0, w0 = time.process_time(), time.perf_counter()
    prog, info = arm.build(P)
    build_cpu = time.process_time() - c0
    base = dict(project=P.seed, domain=P.domain, fault=P.fault, lifecycle=P.sfam)
    if prog is None:
        return dict(base, outcome="ABSTAIN", completed=False, data_ok=False, claims_healthy=False, silent=False, human_repairs=0,
                    independently_correct=False, build=info, log=getattr(arm, "log", []), queries=dict(P.queries))
    archive = dict(envs=[], status=[])
    for t in range(1, SCP.PL.BUILD_TICKS + 1):
        reg = P.ticks[t]["registry"]
        archive["envs"] += [{"r": r, "t": reg} for r in P.ticks[t]["A"]]
        archive["status"] += [P.ref_A(r, reg)[0] for r in P.ticks[t]["A"]]
    crash_tick = random.Random(f"crash-{P.seed}").randint(10, 15)
    build_src = prog.source()
    res = SCP.PL.operate(P, arm, prog, crash_tick, archive)
    truth = P.truth()
    served, who, per = {}, "nexus", {}
    for x in res["ledger"]:
        if x["kind"] == "escalated":
            who = "human"
        elif x["kind"] in ("repair_B",):
            who = "nexus"
        if x["kind"] in ("tick", "escalated", "repair_B", "repair_A"):
            served[x["tick"]] = who
    marker = 0
    for t, tr in truth.items():
        o = res["outputs"][t]
        bA = sum(not SCP.PL._rowA_eq(g, w) for g, w in zip(o["A"], tr["A"]))
        bB = sum(not SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(o["B"], tr["B"]))
        mk = sum(any(r[0] == "?schema_mismatch" for r in g) for g in o["B"])
        marker += mk
        per[t] = dict(bad_A=bA, bad_B=bB, unresolved_rows=mk, served_by=served.get(t, who))
    data_ok = all(v["bad_A"] == 0 and v["bad_B"] == 0 for v in per.values())
    alarms = {x["tick"]: x["alarms"] for x in res["ledger"] if x["kind"] == "tick"}
    det = [t for t, a in sorted(alarms.items()) if t >= SCP.PL.FAULT_TICK and any(s.startswith("B:") for s in a)]
    sdet = [t for t, a in sorted(alarms.items()) if "B:schema_mismatch" in a]
    nexus_wrong = sum(v["bad_A"] + v["bad_B"] - v["unresolved_rows"] for v in per.values() if v["served_by"] == "nexus")
    human_wrong = sum(v["bad_A"] + v["bad_B"] for v in per.values() if v["served_by"] == "human")
    log = getattr(arm, "log", [])
    src = [x.get("learner") for x in log if x.get("step") == "learn" and x.get("accepted")]
    maps = [x for x in log if x.get("step") == "mapping_repair"]
    out = dict(base, outcome="COMPLETED", completed=True, data_ok=data_ok, claims_healthy=res["claims_healthy"],
               silent=res["claims_healthy"] and not data_ok, incorrect_healthy_claim=res["claims_healthy"] and not data_ok,
               human_repairs=res["human_repairs"], independently_correct=data_ok and res["human_repairs"] == 0,
               crash_ok=res["crash_ok"],
               fields=dict(wrong_machine_deployed=nexus_wrong > 0, nexus_served_wrong_rows=nexus_wrong,
                           schema_fault=P.fault in X6_FAMILY, any_B_alarm_after_fault_tick=det[0] if det else None,
                           schema_alarm_tick=sdet[0] if sdet else None,
                           schema_fault_missed=P.fault in X6_FAMILY and not sdet and not det,
                           unresolved_escalations=res["human_repairs"], unresolved_rows_final=marker,
                           human_repair_failed=human_wrong > 0, human_served_wrong_rows=human_wrong, data_ok=data_ok,
                           incorrect_healthy_claim=res["claims_healthy"] and not data_ok),
               solution_sources=dict(build=src[0] if src else None, relearns=src[1:],
                                     mapping=[m.get("outcome") for m in maps], human=res["human_repairs"]),
               per_tick=per, ledger=res["ledger"], log=log, build=info,
               cost=dict(build_cpu_s=round(build_cpu, 3), ops_cpu_s=res["ops_cpu_s"], wall_s=round(time.perf_counter() - w0, 3),
                         queries=dict(P.queries)),
               build_source=build_src)
    try:
        out["deployed_source"] = res["program"].source()
    except Exception:                                                # noqa: BLE001
        out["deployed_source"] = None
    return out


def project(split, ident):
    if split == "sc_dev":
        return int(ident), SCP.Project(int(ident), "sc_dev")
    seeds = list(R.REGISTRY[("sc", split)])
    s = seeds[int(ident)]
    if split != "test":
        return s, SCP.Project(s, "sc_" + split)
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
    man = json.loads((ROOT / "artifacts/sc_test_vault/MANIFEST.json").read_text())
    rel = f"sc_test/{int(ident)}.json"
    blob = (Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / rel).read_bytes()
    if hashlib.sha256(blob).hexdigest() != man["files"][rel]:
        raise SystemExit("vault blob does not match the manifest")
    return s, SCP.PL.Project.from_json(blob.decode())


def main():
    split, ident, arm_name = sys.argv[1], sys.argv[2], sys.argv[3]
    fr = None
    if split != "sc_dev":
        fr = json.loads((ROOT / "artifacts/sc_freeze.json").read_text())
        for f, h in fr["files"].items():
            if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h:
                raise SystemExit(f"code differs from the freeze: {f}")
        if split == "val_b" and not fr.get("revision"):
            raise SystemExit("val_b only after one disclosed revision")
        if split == "test":
            gate = ROOT / ("artifacts/sc_val_b/gate.json" if fr.get("revision") else "artifacts/sc_val/gate.json")
            if not json.loads(gate.read_text())["passed"]:
                raise SystemExit("validation gate not passed: the confirmation stays closed")
        if not any(tuple(r["key"]) == ("sc", split) for r in R._spent() if "override" not in r):
            R.claim("sc", split, list(R.REGISTRY[("sc", split)]), run_id=f"sc-{split}")
    d = ROOT / f"artifacts/sc_{split.replace('sc_', '')}"
    if split == "sc_dev":                                            # dev attempts are kept per tag (debugN / ablation)
        d = d / (sys.argv[4] if len(sys.argv) > 4 else "debug")
    out = d / f"p{ident}_{arm_name}.json"
    if out.exists():
        raise SystemExit("this (project, arm) already ran: no rerun")
    s, P = project(split, ident)
    arm = make_arm(arm_name, fr)

    def _alarm(*_):
        raise ArmTimeout

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(ALARM_S)
    try:
        r, status = run(P, arm), "COMPLETE"
    except ArmTimeout:
        r, status = dict(project=s, domain=P.domain, fault=P.fault, outcome="TIMED_OUT", completed=False, data_ok=False, silent=False,
                         human_repairs=0, independently_correct=False, log=getattr(arm, "log", [])), "COMPLETE"
    except Exception as e:                                           # noqa: BLE001
        r, status = dict(project=s, domain=P.domain, fault=P.fault, outcome="CRASHED", completed=False, data_ok=False, silent=False,
                         human_repairs=0, independently_correct=False,
                         error=type(e).__name__ if split == "test" else traceback.format_exc()), "CRASHED"
    finally:
        signal.alarm(0)
    d.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(split=split, ident=ident, seed=s, arm=arm_name, status=status, result=r), indent=1, default=str))
    os.replace(tmp, out)
    f = r.get("fields", {})
    print(s, r["domain"], r["fault"], arm_name, r["outcome"], "OK" if r["data_ok"] else "BAD", "indep" if r["independently_correct"] else "-",
          "SILENT" if r["silent"] else "", "human", r["human_repairs"], "schema_alarm", f.get("schema_alarm_tick"),
          "src", r.get("solution_sources"), flush=True)
    if status == "CRASHED":
        print(r.get("error"))


if __name__ == "__main__":
    main()

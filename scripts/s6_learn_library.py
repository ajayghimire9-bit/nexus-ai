"""Stage 6 library learning + admission (NOT LOCKED; de2/src ONLY). Every CPU second here is charged to the Experienced arm as
source curriculum + maintenance (reported separately and in the break-even).
  1. NEXUS_Fresh build + ops on each src project (the source experience)
  2. candidate procedures from that experience (s6_library.candidates)
  3. leave-one-out admission trials: for each src project, a library from the OTHER src projects drives NEXUS_Experienced on
     it; failed reuse (a procedure's option or repair later rejected) and costs are recorded
  4. admission / retirement (s6_library.admit) with measured unit costs and the LOO CPU as maintenance; expected uses = 12
     (val 4 + test 8)
  5. a size-matched Placebo library
Writes artifacts/s6_library.json."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import s456_seeds  # noqa: F401
from nexus import s4_env as E, s6_library as SL, seed_registry as R
from nexus.wave31_evaluator import ledger_append
import s456_run as RUN


def cpu_of(arm_rec):
    b = arm_rec["build"]["cost"]["total_cpu_s"]
    o = sum(v["ops_cpu_s"] + v["cost"]["shadow_cpu_s"] for v in arm_rec["ops"].values())
    return b + o


def main():
    t0 = time.perf_counter()
    seeds = list(R.REGISTRY[("de2", "src")])
    R.claim("de2", "src", seeds, run_id="de2-src", record=False)
    art = ROOT / "artifacts/s6_src"
    fresh = {}
    c0 = time.process_time()
    for s in seeds:
        w = E.make_world(s, "src")
        fresh[s] = RUN.run_project(s, w, "src", ["NEXUS_Fresh"], art, detectors=False, lib=None, plc=SL.Library([], True))["arms"]["NEXUS_Fresh"]
        print("src", s, fresh[s]["build"]["outcome"], round(cpu_of(fresh[s]), 1), flush=True)
    curriculum_wall = time.perf_counter() - t0
    curriculum_cpu = sum(cpu_of(v) for v in fresh.values())
    build_recs = {s: dict(v["build"]) for s, v in fresh.items()}
    ops_recs = {s: dict(project=v["build"]["project"], ledger=v["ops"][RUN.OP_DETECTOR]["ledger"]) for s, v in fresh.items()}
    cands = SL.candidates(list(build_recs.values()), list(ops_recs.values()))
    loo, failures, unit = {}, {}, dict(retrieval_cpu_s=[], applicability_cpu_s=[], shadow_cpu_s=[])
    t1 = time.perf_counter()
    for s in seeds:
        others = [x for x in seeds if x != s]
        c = SL.candidates([build_recs[x] for x in others], [ops_recs[x] for x in others])
        lib = SL.Library([dict(p, active=p["agreement"] == 1.0) for p in c], True, f"loo-{s}")
        w = E.make_world(s, "src")
        r = RUN.run_project(s, w, "src", ["NEXUS_Experienced"], art / "loo", detectors=False, lib=lib, plc=None)["arms"]["NEXUS_Experienced"]
        loo[s] = dict(cpu=cpu_of(r), fresh_cpu=cpu_of(fresh[s]), outcome=r["build"]["outcome"], correct=r["build_eval"].get("correct"),
                      ops_correct=r["ops"][RUN.OP_DETECTOR]["eval"]["correct"])
        for h in r["build"]["history"]:
            for d in h.get("failed_reuse", []):
                failures[f"build:{d}"] = failures.get(f"build:{d}", 0) + 1
        oc = r["ops"][RUN.OP_DETECTOR]
        for e in oc["ledger"]:
            if e["kind"] == "repaired" and e.get("shadow_tests_before", 1) > 1 and lib.playbook(e["signature"]):
                failures["ops:" + "|".join(e["signature"])] = failures.get("ops:" + "|".join(e["signature"]), 0) + 1
        unit["retrieval_cpu_s"].append(r["build"]["cost"]["retrieval_cpu_s"] + oc["cost"]["library_retrieval_cpu_s"])
        unit["applicability_cpu_s"].append(r["build"]["cost"]["applicability_cpu_s"] + oc["cost"]["library_applicability_cpu_s"])
        unit["shadow_cpu_s"].append(oc["cost"]["shadow_cpu_s"] / max(1, oc["cost"]["shadow_tests"]))
        print("loo", s, loo[s], flush=True)
    maint_cpu = sum(v["cpu"] for v in loo.values())
    uc = {k: sum(v) / len(v) for k, v in unit.items()}
    procs = SL.admit(cands, failures, uc, maint_cpu, expected_uses=12)
    lib = SL.Library(procs, True, "experienced")
    plc = SL.placebo(procs)
    out = dict(library=lib.to_json(), placebo=plc, loo=loo, loo_failures=failures, unit_costs=uc,
               learning_cost=dict(source_curriculum_cpu_s=curriculum_cpu, loo_maintenance_cpu_s=maint_cpu,
                                  wall_s=time.perf_counter() - t0),
               admitted=[p["id"] for p in procs if p["active"]], retired={p["id"]: p["retired_because"] for p in procs if not p["active"]})
    (ROOT / "artifacts/s6_library.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    ledger_append(dict(run="de2-s6-learn-library", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    print("admitted", out["admitted"]); print("retired", out["retired"])


if __name__ == "__main__":
    main()

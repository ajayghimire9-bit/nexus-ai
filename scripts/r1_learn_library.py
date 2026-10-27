"""R1 library learning + admission (NOT LOCKED; de3/src ONLY). The Stage 6 procedure (s6_library, unchanged) over R1
experience. Every CPU second here is the Experienced arm's DEDICATED SOURCE-LEARNING cost (reported separately; there is
no learning during useful work: the library is frozen, observe() refuses).
  1. NEXUS_Fresh build + end-to-end ops on each src project (source experience; no component benchmark)
  2. candidate procedures (s6_library.candidates; a build counts as accepted when every check of the R1 suite passed,
     i.e. its Stage 4 label, since every R1 build is COMPLETED_UNVERIFIED for the two unexercised properties)
  3. leave-one-out admission trials (NEXUS_Experienced with a library from the other src projects)
  4. admission / retirement (s6_library.admit), expected uses = 12 (val 4 + test 8); 5. size-matched Placebo
Writes artifacts/r1_library.json. Resumable phases (each call < 900 s; raw per-seed records in artifacts/r1_src_raw/):
  python scripts/r1_learn_library.py --phase fresh|loo --seeds 941,942 [--mode B0]
  python scripts/r1_learn_library.py --phase admit [--mode B0]"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import r1_seeds  # noqa: F401
from nexus import r1_env as RE, s6_library as SL, seed_registry as R
from nexus.wave31_evaluator import ledger_append
import r1_run as RUN


def cpu_of(a):
    o = a["ops"] or {"cost": {}}
    return a["build"]["cost"]["total_cpu_s"] + o["cost"].get("agent_cpu_s", 0.0) + o["cost"].get("shadow_cpu_s", 0.0)


def brec(a):
    return dict(a["build"], outcome=a["build"].get("s4_outcome", a["build"]["outcome"]))


def orec(a):
    return dict(project=a["build"]["project"], ledger=(a["ops"] or {}).get("ledger", []))


RAW = ROOT / "artifacts/r1_src_raw"


def _save(kind, s, rec):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{kind}_{s}.json").write_text(json.dumps(rec, sort_keys=True, default=str))


def _load(kind, s):
    return json.loads((RAW / f"{kind}_{s}.json").read_text())


def phase_fresh(seeds, mode):
    t0 = time.perf_counter()
    R.claim("de3", "src", seeds, run_id="de3-src", record=False)
    for s in seeds:
        w = RE.make_world(s, "src")
        a = time.perf_counter()
        r = RUN.run_project(s, w, "src", ["NEXUS_Fresh"], ROOT / "artifacts/r1_src", lib=None, plc=SL.Library([], True),
                            mode=mode, component=False)["arms"]["NEXUS_Fresh"]
        r["wall_s"] = time.perf_counter() - a
        _save("fresh", s, r)
        print("src", s, r["build"]["outcome"], r["e2e_correct"], round(cpu_of(r), 1), flush=True)
    ledger_append(dict(run="r1-learn-library-fresh", wall_s=time.perf_counter() - t0, status="COMPLETE", seeds=seeds))


def phase_loo(seeds, mode):
    t0 = time.perf_counter()
    allseeds = list(R.REGISTRY[("de3", "src")])
    fresh = {s: _load("fresh", s) for s in allseeds}
    for s in seeds:
        others = [x for x in allseeds if x != s]
        c = SL.candidates([brec(fresh[x]) for x in others], [orec(fresh[x]) for x in others])
        lib = SL.Library([dict(p, active=p["agreement"] == 1.0) for p in c], True, f"loo-{s}")
        w = RE.make_world(s, "src")
        r = RUN.run_project(s, w, "src", ["NEXUS_Experienced"], ROOT / "artifacts/r1_src" / "loo", lib=lib, plc=None, mode=mode,
                            component=False)["arms"]["NEXUS_Experienced"]
        r["loo_library"] = [p["id"] for p in lib.procs if p.get("active")]
        _save("loo", s, r)
        print("loo", s, r["build"]["outcome"], r["e2e_correct"], round(cpu_of(r), 1), flush=True)
    ledger_append(dict(run="r1-learn-library-loo", wall_s=time.perf_counter() - t0, status="COMPLETE", seeds=seeds))


def phase_admit(mode):
    t0 = time.perf_counter()
    seeds = list(R.REGISTRY[("de3", "src")])
    fresh = {s: _load("fresh", s) for s in seeds}
    loo_r = {s: _load("loo", s) for s in seeds}
    curriculum_cpu = sum(cpu_of(v) for v in fresh.values())
    cands = SL.candidates([brec(v) for v in fresh.values()], [orec(v) for v in fresh.values()])
    loo, failures, unit = {}, {}, dict(retrieval_cpu_s=[], applicability_cpu_s=[], shadow_cpu_s=[])
    for s in seeds:
        r = loo_r[s]
        lib = SL.Library([p for p in cands if p["id"] in r["loo_library"]], True)
        oc = r["ops"] or {"cost": {}, "ledger": []}
        loo[s] = dict(cpu=cpu_of(r), fresh_cpu=cpu_of(fresh[s]), outcome=r["build"]["outcome"], correct=r["build_eval"].get("correct"),
                      e2e=r["e2e_correct"], fresh_e2e=fresh[s]["e2e_correct"])
        for h in r["build"]["history"]:
            for d in h.get("failed_reuse", []):
                failures[f"build:{d}"] = failures.get(f"build:{d}", 0) + 1
        for e in oc["ledger"]:
            if e["kind"] == "repaired" and e.get("shadow_tests_before", 1) > 1 and e.get("signature") and \
                    any(p["kind"] == "ops" and p["signature"] == "|".join(e["signature"]) for p in lib.procs):
                failures["ops:" + "|".join(e["signature"])] = failures.get("ops:" + "|".join(e["signature"]), 0) + 1
        unit["retrieval_cpu_s"].append(r["build"]["cost"]["retrieval_cpu_s"] + oc["cost"].get("library_retrieval_cpu_s", 0.0))
        unit["applicability_cpu_s"].append(r["build"]["cost"]["applicability_cpu_s"] + oc["cost"].get("library_applicability_cpu_s", 0.0))
        unit["shadow_cpu_s"].append(oc["cost"].get("shadow_cpu_s", 0.0) / max(1, oc["cost"].get("shadow_tests", 0)))
    maint_cpu = sum(v["cpu"] for v in loo.values())
    uc = {k: sum(v) / len(v) for k, v in unit.items()}
    procs = SL.admit(cands, failures, uc, maint_cpu, expected_uses=12)
    lib = SL.Library(procs, True, "experienced")
    plc = SL.placebo(procs)
    wall = sum(v.get("wall_s", 0.0) for v in fresh.values())
    out = dict(library=lib.to_json(), placebo=plc, loo=loo, loo_failures=failures, unit_costs=uc, mode=mode,
               learning_cost=dict(source_curriculum_cpu_s=curriculum_cpu, loo_maintenance_cpu_s=maint_cpu,
                                  during_useful_work_cpu_s=0.0, curriculum_wall_s=wall),
               admitted=[p["id"] for p in procs if p["active"]], retired={p["id"]: p["retired_because"] for p in procs if not p["active"]})
    (ROOT / "artifacts/r1_library.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    ledger_append(dict(run="r1-learn-library-admit", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    print("admitted", out["admitted"]); print("retired", out["retired"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="B0"); ap.add_argument("--phase", required=True); ap.add_argument("--seeds", default="")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(R.REGISTRY[("de3", "src")])
    {"fresh": lambda: phase_fresh(seeds, a.mode), "loo": lambda: phase_loo(seeds, a.mode), "admit": lambda: phase_admit(a.mode)}[a.phase]()

"""Trial 1, state arm (NOT LOCKED).  python scripts/t7_trial1_state.py dev SEEDS | decide | val K/N | valdecide
dev:    de5 worlds on t7/ddev seeds, the frozen OOP Phase 1 NEXUS_Synth operator (oop_run.run_project, natural run only);
        derived quantities recorded after every tick of the operations environment (shadow clones excluded).
decide: candidate monitors = quantities present in every dev project (levels + deltas); twins = tick-permuted; W = score
        difference on incident onset ticks; knockoff+ at q = 0.20 -> admitted monitors.
val:    claims t7/dval (one-use, 4 fresh projects); same operator + admitted monitors as extra alarms. Pass per project:
        no silent error (data wrong while the operator claims healthy AND no admitted monitor alarmed) and <= 1 false
        alarm (admitted-monitor alarm ticks with no incident onset at t or t - 1)."""
import json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, "scripts")
import oop_run as RUN  # noqa: E402
from nexus import t7_seeds, t7_monitors as TM, t7_knockoff as KO, seed_registry as R  # noqa: E402,F401
from nexus import oop_env as RE, oop_ops as OO  # noqa: E402

ART = RUN.ROOT / "artifacts/t7_dev"
ART.mkdir(exist_ok=True)
REC = {}
_adv = OO.O3.OpsEnvR1.advance


def advance(self):
    res = _adv(self)
    if str(self.work).endswith("ops_e2e"):
        try:
            REC[self.t] = TM.quantities(self, self.t)
        except Exception as e:                                       # noqa: BLE001
            REC[self.t] = {"_error": 1.0}
    return res


OO.O3.OpsEnvR1.advance = advance


def run(seed, split, ns):
    REC.clear()
    w = RE.make_world(seed, split)
    art = Path(tempfile.mkdtemp(prefix="t7s_"))
    out = RUN.run_project(seed, w, split, ["NEXUS_Synth"], art, forced=False, secondary=False)
    shutil.rmtree(art, ignore_errors=True)
    a = out["arms"]["NEXUS_Synth"]
    ops = a["ops"] or {}
    ev = ops.get("eval", {})
    res = dict(seed=seed, split=split, submitted=bool(a["build"].get("submitted")), data_ok=ev.get("data_ok"), claims_healthy=ev.get("claims_healthy"),
               silent=ev.get("silent"), e2e_correct=a["e2e_correct"], incidents=ops.get("incidents", []), x_class=out.get("x_class"),
               d_class=out.get("d_class"), per_tick={str(k): v for k, v in REC.items()})
    (ART / f"t1s_{ns}_{seed}.json").write_text(json.dumps(res, default=str))
    print(seed, "data_ok", res["data_ok"], "silent", res["silent"], "incidents", res["incidents"], "ticks", len(REC), flush=True)
    return res


def labels(res, ticks):
    on = {i["tick"] for i in res["incidents"]}
    return [t in on or (t - 1) in on for t in ticks]


cmd = sys.argv[1]
if cmd == "dev":
    for s in [int(x) for x in sys.argv[2].split(",")]:
        run(s, "dev", "ddev")
elif cmd == "decide":
    projs = [json.loads(f.read_text()) for f in sorted(ART.glob("t1s_ddev_*.json"))]
    tabs = []
    for p in projs:
        S, ticks = TM.series_table({int(k): v for k, v in p["per_tick"].items()})
        tabs.append((S, ticks, labels(p, ticks)))
    names = sorted(set.intersection(*[set(S) for S, _, _ in tabs]))
    Wv = []
    for j, n in enumerate(names):
        real = sum(TM.score(TM.alarms(S[n]), lab) for S, _, lab in tabs)
        twin = sum(TM.score(TM.alarms(TM.permuted(S[n], seed=f"{n}-{i}")), lab) for i, (S, _, lab) in enumerate(tabs))
        Wv.append(real - twin)
    T, adm = KO.knockoff_plus(Wv, 0.20)
    admitted = [names[j] for j in adm]
    (ART / "t1s_admitted.json").write_text(json.dumps(dict(n_candidates=len(names), threshold=T, admitted=admitted,
                                                            W={n: round(w, 4) for n, w in zip(names, Wv)}, n_dev=len(projs)), indent=1))
    print("candidates", len(names), "T", T, "admitted", admitted)
elif cmd == "val":                                   # val K/N: one-use seeds claimed whole at part 1; parts run once each
    k, n = map(int, sys.argv[2].split("/"))
    adm = json.loads((ART / "t1s_admitted.json").read_text())["admitted"]
    seeds = list(R.REGISTRY[("t7", "dval")])
    if k == 1:
        R.claim("t7", "dval", seeds, run_id="t7-t1s-val")
    rows = []
    for s in [x for i, x in enumerate(seeds) if i % n == k - 1]:
        p = run(s, "val", "dval")
        S, ticks = TM.series_table({int(kk): v for kk, v in p["per_tick"].items()})
        lab = labels(p, ticks)
        al = [any(TM.alarms(S[nm])[i] for nm in adm if nm in S) for i in range(len(ticks))]
        alarm_ticks = [t for t, a in zip(ticks, al) if a and t > 8]
        false = [t for t, a, l in zip(ticks, al, lab) if a and not l and t > 8]
        silent = bool(p["silent"]) and not alarm_ticks
        rows.append(dict(seed=s, frozen_silent=p["silent"], data_ok=p["data_ok"], incidents=p["incidents"], alarm_ticks=alarm_ticks,
                         false_alarm_ticks=false, silent_with_monitors=silent, passed=not silent and len(false) <= 1))
        print(rows[-1], flush=True)
    (ART / f"t1s_val_{k}of{n}.json").write_text(json.dumps(rows, indent=1))
else:
    adm = json.loads((ART / "t1s_admitted.json").read_text())
    rows = [r for f in sorted(ART.glob("t1s_val_*of*.json")) for r in json.loads(f.read_text())]
    keep = len(rows) == 4 and all(r["passed"] for r in rows) and len(adm["admitted"]) > 0 and adm["n_candidates"] >= 20
    (ART / "t1s_val.json").write_text(json.dumps(dict(admitted=adm["admitted"], rows=rows, verdict="KEPT" if keep else "REJECTED"), indent=1))
    print("VERDICT", "KEPT" if keep else "REJECTED", [(r["seed"], r["passed"], r["false_alarm_ticks"], r["silent_with_monitors"]) for r in rows])

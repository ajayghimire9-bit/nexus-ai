"""Phase 10C Stage 4: shared-random-stream improver (M*) test with discovery-cost accounting (NOT LOCKED).
  python scripts/agi10c_mstar.py round       identity check + M0 vs M' clone round -> artifacts/agi10c_mstar/round.json
  python scripts/agi10c_mstar.py downstream  fresh learners (M_selected, M_alternative) -> Draw C -> artifacts/agi10c_mstar/downstream.json
ROUND. Parent: stream rep0's N30 checkpoint (memory incl. library, step records, rankers). Clones share EVERY random stream:
the same 10 wake tasks (train_spec(0, 300 + i), seeds 93000+), dream seeds 93100+, admission seeds 93150+, the same numeric
(rep, step, task) sampling and split seeds; clone names never reach a seed. IDENTITY: clones idA / idB (both M0, different
names) must produce identical wake decisions / verdicts / paths and identical final memories (any difference is reported with
the searches that hit the 4 s wall cap, the only non-deterministic input). EDIT: M' = M0 with one field of lineage10c.SPACE
changed, drawn by rng(4, 0, 0). VALIDATION: 8 common training-family tasks (train_spec(0, 400 + j), seeds 93300+) solved by each
clone's frozen memory under the A4 configuration. ADOPT M' iff it verifies strictly more, >= 1, with no more wrong.
DOWNSTREAM. Fresh learners (empty learned memory, fixed trust) with M_selected and M_alternative train on one common stream of
20 tasks (train_spec(0, 600 + i), seeds 93400+; dreams 93500+, admission 93550+) and are evaluated with their own L* + G_L*
(A4 configuration) on DRAW C = one-use 96080-96091 (4 ordinary + 8 withheld; never opened before). The clone round's seconds
are the DISCOVERY COST charged to M_selected."""
import copy, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase10 import procedure10 as PR10  # noqa: E402
from nexus.de_phase10c import lineage10c as LC, manifest10c as MC  # noqa: E402
from nexus.de_phase10c.rng10c import rng  # noqa: E402
import agi10c_train as TRN  # noqa: E402
OUT = ROOT / "artifacts/agi10c_mstar"
PARENT = ROOT / "artifacts/agi10c_train/rep0.N30.json"
DRAW_C = [dict(t, names="heldout", dp_mode="explicit", seed=96080 + i, family=t["paradigm"], draw="C") for i, t in enumerate(
    [dict(paradigm="P1", engine="sqlite", group="ordinary"), dict(paradigm="P2", engine="duckdb", group="ordinary"), dict(paradigm="X1", group="ordinary"),
     dict(paradigm="X2", group="ordinary")] + [dict(paradigm=h, group="heldout") for h in ("H1", "H2", "H3", "H4", "H1", "H2", "H3", "H4")])]


def edit():
    r = rng(4, 0, 0)
    k = r.choice(sorted(LC.SPACE))
    return k, r.choice([v for v in LC.SPACE[k] if v != LC.M0[k]])


def clone(tag, M, deadline):
    ck = json.loads(PARENT.read_text())
    L = LC.Learner(0, f"clone_{tag}", TRN.fixed_trust()[0], ROOT / "var/agi10c_ws/mstar" / tag, deadline, OUT, dict(wake=range(93000, 93100), dream=range(93100, 93150),
                   admit=range(93150, 93300)), stream=lambda i: MC.train_spec(0, 300 + i), M=M)
    L.mem = copy.deepcopy(ck["memory"])
    L.mem["M"] = L.M = copy.deepcopy(M)
    t0 = time.time()
    for i in range(10):
        try:
            L.wake(i, 93000 + i)
        except RuntimeError as e:
            L.log("events", dict(kind="build_failed", err=str(e)[:80]))
    L.sleep()
    return L, time.time() - t0


def validate(mem, specs):
    v = w = 0
    per = {}
    for s, sp in specs:
        p = LC.build(sp, s, ROOT / "var/agi10c_ws/mstar/val")
        st = PR10.investigate(p, LC.Live(LC.WORK, LC.WALL), copy.deepcopy(mem), PR10.F0, {})
        o = PR10.outcome(p, st)
        v += o["verified"]
        w += o["wrong"]
        per[p["pid"]] = (o["verified"], o["wrong"])
    return v, w, per


def arm(mem):
    return LC.arm_memory(TRN.fixed_trust()[0], skills=mem["de"]["skills"], guide_w=(mem.get("guides") or {}).get("Lstar"))


def strip(path):
    return [{k: v for k, v in json.loads(l).items() if k not in ("t", "wall")} for l in Path(path).read_text().splitlines()] if Path(path).exists() else []


def round_():
    T0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "round.json").exists():
        raise SystemExit("the clone round is never rerun")
    k, v = edit()
    Medit = dict(LC.M0, **{k: v})
    res, cost = {}, {}
    val = [(93300 + j, MC.train_spec(0, 400 + j)) for j in range(8)]
    for tag, M in (("idA", LC.M0), ("idB", LC.M0), ("edit", Medit)):
        L, dt = clone(tag, M, T0 + 380)
        vv, ww, per = validate(arm(L.mem), val)
        res[tag] = dict(M=M, verified=vv, wrong=ww, per=per, library=len(L.mem["de"]["skills"]), tasks=L.n)
        cost[tag] = round(dt + 0, 1)
        res[tag]["memory_digest"] = __import__("hashlib").sha256(json.dumps(L.mem, sort_keys=True, default=list).encode()).hexdigest()
    wa, wb = strip(OUT / "clone_idA.wake.jsonl"), strip(OUT / "clone_idB.wake.jsonl")
    keys = ("decision", "verified", "wrong", "work", "macro_steps")
    identity = dict(wake_rows=len(wa), identical_rows=sum(json.dumps([a.get(x) for x in keys]) == json.dumps([b.get(x) for x in keys]) for a, b in zip(wa, wb)),
                    identical_memory=res["idA"]["memory_digest"] == res["idB"]["memory_digest"], identical_validation=res["idA"]["per"] == res["idB"]["per"],
                    differing=[(a["project"], [a.get(x) for x in keys], [b.get(x) for x in keys]) for a, b in zip(wa, wb) if [a.get(x) for x in keys] != [b.get(x) for x in keys]])
    adopt = res["edit"]["verified"] > res["idA"]["verified"] and res["edit"]["verified"] >= 1 and res["edit"]["wrong"] <= res["idA"]["wrong"]
    out = dict(edit=[k, v], identity=identity, results={t: {x: y for x, y in r.items() if x != "per"} for t, r in res.items()}, per={t: r["per"] for t, r in res.items()},
               adopted=adopt, M_selected=Medit if adopt else LC.M0, M_alternative=LC.M0 if adopt else Medit, clone_seconds=cost,
               discovery_cost_s=round(time.time() - T0, 1))
    (OUT / "round.json").write_text(json.dumps(out, indent=1, default=list))
    print(json.dumps({x: out[x] for x in ("edit", "identity", "results", "adopted", "discovery_cost_s")}, default=list)[:3000])


def downstream():
    T0 = time.time()
    rd = json.loads((OUT / "round.json").read_text())
    if (OUT / "downstream.json").exists():
        raise SystemExit("the downstream test is never rerun")
    if not any(tuple(x["key"]) == ("agi10cde", "eval") and x.get("run_id") == "agi10c-eval" for x in R._spent()):
        raise SystemExit("agi10cde/eval was not claimed by the Phase 10C evaluation")
    res = {}
    for tag in ("selected", "alternative"):
        M = rd[f"M_{tag}"]
        L = LC.Learner(0, f"down_{tag}", TRN.fixed_trust()[0], ROOT / "var/agi10c_ws/mstar" / f"down_{tag}", T0 + 1e9, OUT,
                       dict(wake=range(93400, 93500), dream=range(93500, 93550), admit=range(93550, 93700)), stream=lambda i: MC.train_spec(0, 600 + i), M=M)
        t = time.time()
        for i in range(20):
            try:
                L.wake(i, 93400 + i)
            except RuntimeError:
                L.n += 1
            if (i + 1) % L.M["batch"] == 0:
                L.sleep()
        train_s = time.time() - t
        mem = arm(L.mem)
        rows = []
        with open(OUT / f"drawC_{tag}.jsonl", "a") as fh:
            for tt in DRAW_C:
                try:
                    p = LC.build(tt, tt["seed"], ROOT / "var/agi10c_ws/mstar/drawC")
                except RuntimeError as e:
                    rows.append(dict(seed=tt["seed"], error=str(e)[:80]))
                    continue
                t1 = time.time()
                st = PR10.investigate(p, LC.Live(LC.WORK, LC.WALL), copy.deepcopy(mem), PR10.F0, {})
                o = PR10.outcome(p, st)
                r = dict(seed=tt["seed"], family=tt["family"], group=tt["group"], verified=o["verified"], wrong=o["wrong"], reason=st.decision.get("reason"),
                         work=st.cost["work"], wall=round(time.time() - t1, 2))
                fh.write(json.dumps(r) + "\n")
                fh.flush()
                rows.append(r)
        ok = [r for r in rows if "error" not in r]
        res[tag] = dict(M=M, train_s=round(train_s, 1), train_cost=L.cost, library=len(L.mem["de"]["skills"]), verified=sum(r["verified"] for r in ok),
                        wrong=sum(r["wrong"] for r in ok), withheld=f"{sum(r['verified'] for r in ok if r['group'] == 'heldout')}/{sum(r['group'] == 'heldout' for r in ok)}",
                        ordinary=f"{sum(r['verified'] for r in ok if r['group'] == 'ordinary')}/{sum(r['group'] == 'ordinary' for r in ok)}", build_failures=[r for r in rows if "error" in r])
    gain = res["selected"]["verified"] - res["alternative"]["verified"]
    out = dict(adopted=rd["adopted"], edit=rd["edit"], results=res, selected_minus_alternative=gain, discovery_cost_s=rd["discovery_cost_s"],
               discovery_s_per_extra_completion=round(rd["discovery_cost_s"] / gain, 1) if gain > 0 else None, wall=round(time.time() - T0, 1))
    (OUT / "downstream.json").write_text(json.dumps(out, indent=1, default=list))
    print(json.dumps(out, default=list)[:2500])


if __name__ == "__main__":
    {"round": round_, "downstream": downstream}[sys.argv[1]]()

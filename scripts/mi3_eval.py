"""MI-3 Stage 4 fresh winner evaluation (NOT LOCKED; ONE-USE mi3/winner_eval).
  python scripts/mi3_eval.py freeze          artifacts/mi3_freeze.json: the 13 arms (8 run winners + 5 references) + file hashes
  python scripts/mi3_eval.py plan            artifacts/mi3_eval_plan.json: N in {40, 28, 16} and the cap, from DEVELOPMENT
                                             measurements only (Stage 2 per-episode overhead, the calibrated cap)
  python scripts/mi3_eval.py run ARM         one arm on the N episodes (resumable per episode; never rerun)
  python scripts/mi3_eval.py score           tables, contrasts, amortised cost -> artifacts/mi3_winner_eval/result.json
Plan rule (frozen): per-arm bound = N x (CAP_S + overhead) + STARTUP_S with overhead = the largest per-episode non-learner CPU
seen in Stage 2 (+ 0.1 s margin) and STARTUP_S = 5; choose the largest N in {40, 28, 16} with 13 x bound <= 1400 s; if none,
winner_eval is not opened. Episodes: N/4 per family K / MUL / ADDC / SUBH = mi3/winner_eval seed indices 0..N/4-1 per family.
Each arm: mi3_search.eval_one (full_space3 with the arm's procedure, the Stage 1 check, fresh Episode3 and learner per episode).
Contrasts (predeclared): E-S vs E-F, R-S vs R-F, E-S vs R-S, E-F vs R-F on the dev-unfamiliar MUL / ADDC / SUBH episodes, paired by
lineage (L1 with L1, L2 with L2). Primary: per-seed differences, their mean, and a 95 % bootstrap interval (2000 resamples of
episodes, both pairs resampled together). Exploratory: one-sided sign test on discordant episodes pooled over the two pairs, Holm
over the 4 contrasts; N = 2 discovery seeds per arm limits any inference about the arms."""
import hashlib, json, random, sys, time
from math import comb
from pathlib import Path
from nexus import mi3_seeds, mi3_search as MS, seed_registry as R  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/mi3_winner_eval"
RUNS = [f"{a}_L{l}" for a in ("E-F", "E-S", "R-F", "R-S") for l in (1, 2)]
REFS = {"A0": dict(kind="baseline"), "MI1_17": dict(kind="file", file="artifacts/mi_dev/select_evolve.json"),
        "MI2_A4": dict(kind="file", file="artifacts/mi2_dev/select_a_params_L1.json"), "A5": dict(kind="a5"), "A6": dict(kind="a6")}
DISC_COST = {"A0": 0.0, "MI1_17": 390.0, "MI2_A4": 1311.0, "A5": 0.0, "A6": 0.0}   # charged s (MI-1 / MI-2 reports); humans 0
FAMS = ("K", "MUL", "ADDC", "SUBH")
CODE = ["src/nexus/mi3_accept.py", "src/nexus/mi3_search.py", "src/nexus/mi3_seeds.py", "scripts/mi3_eval.py",
        "artifacts/mi3_schedule.json", "src/nexus/mi2_learner.py", "src/nexus/mi_learner.py", "src/nexus/mi_lpl.py",
        "src/nexus/mi_ocean.py", "artifacts/mi_dev/select_evolve.json", "artifacts/mi2_dev/select_a_params_L1.json"]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def freeze():
    arms = {}
    files = list(CODE)
    for r in RUNS:
        f = f"artifacts/mi3_disc/{r}.json"
        st = json.loads((ROOT / f).read_text())
        if "winner" not in st:
            raise SystemExit(f"{r}: no frozen winner")
        arms[r] = dict(kind="lpl", prog=st["winner"]["prog"], source=f, winner_id=st["winner_id"], rule=st["winner_rule"])
        files.append(f)
    arms.update(REFS)
    save(ROOT / "artifacts/mi3_freeze.json", dict(arms=arms, files={f: sha(f) for f in files}))
    print("frozen", list(arms))


def plan():
    cal = json.loads((ROOT / "artifacts/mi3_cal/calibration.json").read_text())
    ovh = max(0.0, cal["per_episode_overhead_max"]) + 0.1
    out = None
    for n in (40, 28, 16):
        bound = n * (MS.CAP_S + ovh) + 5.0
        if 13 * bound <= 1400:
            out = dict(n=n, per_family=n // 4, cap_s=MS.CAP_S, overhead_s=round(ovh, 3), per_arm_bound_s=round(bound, 1),
                       total_bound_s=round(13 * bound, 1))
            break
    out = out or dict(n=None, reason="even 16 episodes do not fit 1400 s: winner_eval not opened")
    save(ROOT / "artifacts/mi3_eval_plan.json", out)
    print(out)


def episodes(n):
    seeds = list(R.REGISTRY[("mi3", "winner_eval")])
    return [(seeds[i], f) for f in FAMS for i in range(n // 4)]


def run(arm):
    fr = json.loads((ROOT / "artifacts/mi3_freeze.json").read_text())
    for f, h in fr["files"].items():
        if sha(f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    plan_ = json.loads((ROOT / "artifacts/mi3_eval_plan.json").read_text())
    if not plan_.get("n"):
        raise SystemExit("winner_eval not opened (plan)")
    if arm not in fr["arms"]:
        raise SystemExit(f"{arm} not frozen")
    key = ("mi3", "winner_eval")
    if not any(tuple(r["key"]) == key for r in R._spent() if "override" not in r):
        R.claim("mi3", "winner_eval", list(R.REGISTRY[key]), run_id="mi3-winner_eval")
    D.mkdir(parents=True, exist_ok=True)
    out = D / f"{arm}.jsonl"
    done = {(r["seed"], r["family"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    dom, max_s = MS.domain_of(fr["arms"][arm])
    with open(out, "a") as fh:
        for s, f in episodes(plan_["n"]):
            if (s, f) in done:
                continue
            r = MS.eval_one(dom, max_s, s, f, cap_s=plan_["cap_s"])
            fh.write(json.dumps(dict(r, arm=arm)) + "\n")
            fh.flush()
            print(arm, s, f, r["exact"], r["outcome"], r["cpu_s"], flush=True)


def sign_p(a, b):
    n = a + b
    return sum(comb(n, k) for k in range(a, n + 1)) / 2 ** n if n else 1.0


def score():
    fr = json.loads((ROOT / "artifacts/mi3_freeze.json").read_text())
    plan_ = json.loads((ROOT / "artifacts/mi3_eval_plan.json").read_text())
    eps = episodes(plan_["n"])
    T, missing = {}, {}
    for a in fr["arms"]:
        p = D / f"{a}.jsonl"
        rows = {(r["seed"], r["family"]): r for r in map(json.loads, p.read_text().splitlines())} if p.exists() else {}
        missing[a] = [e for e in eps if e not in rows]
        T[a] = rows
    ledger = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
    disc = {r: sum(x["wall_s"] for x in ledger if x["run"].startswith(f"mi-3-disc-{r}")) for r in RUNS}
    tab = {}
    for a, rows in T.items():
        rs = list(rows.values())
        unf = [r for r in rs if r["family"] != "K"]
        cost = disc.get(a, DISC_COST.get(a, 0.0))
        cpu = sum(r["cpu_s"] for r in rs)
        tab[a] = dict(exact={f: sum(r["exact"] for r in rs if r["family"] == f) for f in FAMS},
                      unfamiliar=sum(r["exact"] for r in unf), silent=sum(r["silent"] for r in rs),
                      abstain=sum(not r["accepted"] for r in rs), timeouts=sum(r["outcome"] == "cap_timeout" for r in rs),
                      interface_gap=sum(r["outcome"] == "interface_gap" for r in rs), cpu_s=round(cpu, 2),
                      queries=sum(r["queries"] for r in rs),
                      coverage_at={str(b): sum(r["exact"] and r["learner_cpu_s"] <= b for r in rs) for b in (0.1, 0.25, 0.5, 1.0)},
                      discovery_cost_s=round(cost, 1),
                      amortised_cost_per_episode={str(h): round(cpu / max(1, len(rs)) + cost / h, 3) for h in (len(eps), 1000, 10000)},
                      k_retention_vs_A0=None, missing=len(missing[a]))
    for a in tab:
        tab[a]["k_retention_vs_A0"] = tab[a]["exact"]["K"] - tab["A0"]["exact"]["K"]
    unf_eps = [e for e in eps if e[1] != "K"]
    contrasts = {}
    pvals = {}
    for x, y in (("E-S", "E-F"), ("R-S", "R-F"), ("E-S", "R-S"), ("E-F", "R-F")):
        per = {}
        ao = co = 0
        for l in (1, 2):
            a, b = f"{x}_L{l}", f"{y}_L{l}"
            ea = [bool(T[a].get(e, {}).get("exact")) for e in unf_eps]
            eb = [bool(T[b].get(e, {}).get("exact")) for e in unf_eps]
            per[f"L{l}"] = dict(primary=sum(ea), control=sum(eb), diff=sum(ea) - sum(eb),
                                primary_only=sum(p and not q for p, q in zip(ea, eb)), control_only=sum(q and not p for p, q in zip(ea, eb)),
                                silent_diff=tab[a]["silent"] - tab[b]["silent"], k_diff=tab[a]["exact"]["K"] - tab[b]["exact"]["K"],
                                cost_diff_s=round(tab[a]["cpu_s"] + tab[a]["discovery_cost_s"] - tab[b]["cpu_s"] - tab[b]["discovery_cost_s"], 1))
            ao += per[f"L{l}"]["primary_only"]
            co += per[f"L{l}"]["control_only"]
        rnd = random.Random(f"mi3-boot-{x}-{y}")
        d = [[int(bool(T[f"{x}_L{l}"].get(e, {}).get("exact"))) - int(bool(T[f"{y}_L{l}"].get(e, {}).get("exact"))) for l in (1, 2)]
             for e in unf_eps]
        boots = sorted(sum(sum(d[rnd.randrange(len(d))]) for _ in d) / 2 for _ in range(2000))
        mean = sum(v["diff"] for v in per.values()) / 2
        contrasts[f"{x} vs {y}"] = dict(per_seed=per, mean_diff=mean, ci95=[boots[49], boots[1949]],
                                        seeds_disagree=(per["L1"]["diff"] > 0) != (per["L2"]["diff"] > 0) or
                                        (per["L1"]["diff"] == 0) != (per["L2"]["diff"] == 0),
                                        pooled=dict(primary_only=ao, control_only=co, p_one_sided=sign_p(ao, co)))
        pvals[f"{x} vs {y}"] = sign_p(ao, co)
    order = sorted(pvals, key=pvals.get)
    holm, run_max = {}, 0.0
    for i, k in enumerate(order):
        run_max = max(run_max, min(1.0, (len(order) - i) * pvals[k]))
        holm[k] = round(run_max, 4)
    for k in contrasts:
        contrasts[k]["pooled"]["p_holm"] = holm[k]
    res = dict(plan=plan_, table=tab, contrasts=contrasts, missing={a: len(v) for a, v in missing.items()},
               complete=all(not v for v in missing.values()))
    save(D / "result.json", res)
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        {"freeze": freeze, "plan": plan, "score": score}[sys.argv[1]]()

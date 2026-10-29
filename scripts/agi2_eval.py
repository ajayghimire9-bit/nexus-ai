"""Phase 2 Stage 4 frozen evaluation (NOT LOCKED; ONE-USE agi2/eval_withheld, eval_ce_fresh, eval_untouched,
improver_panel; claimed under an fcntl file lock so concurrent workers cannot race).
  python scripts/agi2_eval.py freeze_source | freeze_meta | plan | run main|panel C N | score
Arms per repetition r:
  Full_r        frozen Full endpoint (R*, L*, P*, pi*, M*)
  SolvedOnly_r  the No-Incomplete-Experience ablation endpoint (P disabled in training; M0; Full's learned-task sequence)
  RL_r          R*, L* of Full_r with pi0, M0 and empty P        Pol_r   pi* of Full_r with empty R, L, P
  Placebo_r     pi* with an operationally matched random library (same kind / types / size / cost / utility as every
                R*, L* item; executable, non-constant; seeded from agi2/placebo); P irrelevant at solve time (never used)
  Rand_r        Random-Proposal endpoint        Fixed_r   Fixed-M0 endpoint
  Init          (empty, pi0, M0)
  Scratch       the strong scratch configuration chosen on source-world development data (artifacts/agi2_dev/
                scratch_tuning.json). It selected pi0 costs with the lambda cap 6, i.e. exactly Init's configuration, so
                Scratch's rows are Init's rows (run once; reported under both names).
  Meta_r_{Mstar,M0,Mrand} + Full_r@panel on the 12-task improver panel.
Every episode restores the frozen state (digest-checked); within-task queries only; the acceptance barrier is the locked
agent_loop.ACCEPT for every arm. Task-major chunks (each task under every arm in one process)."""
import copy, fcntl, hashlib, json, random, sys
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign2 import agent_loop as AL, improver as I, seeds as SD, state as ST, substrate as S
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/agi2_eval"
REPS = (0, 1, 2)
CODE = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/campaign2").glob("*.py")) + \
    sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/campaign/worlds").glob("*.py")) + \
    ["scripts/agi2_eval.py", "artifacts/agi2_dev/scratch_tuning.json"]
ONE_USE = sorted(SD.ONE_USE)
COH = ("Full", "Fixed-M0", "SolvedOnly", "Random-Proposal")


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=list))
    tmp.replace(p)


def load_state(p):
    doc = json.loads((ROOT / p).read_text())
    if not doc.get("final"):
        raise SystemExit(f"{p} is not a final endpoint")
    return ST.from_json(doc["state"])


def placebo_state(full, rep):
    st = copy.deepcopy(full)
    existing = {S.to_src(v["body"]) for v in list(full["L"].values()) + list(full["R"].values())}
    for tab in ("L", "R"):
        for iid, item in full[tab].items():
            rng = random.Random(f"agi2-placebo|{SD.RANGES[('agi2', 'placebo')].start + rep}|{iid}")
            b = I.placebo_for(dict(item, kind=tab), rng, existing)
            if b is None:
                raise SystemExit(f"no placebo for {iid}")
            existing.add(S.to_src(b))
            st[tab][iid] = dict(item, body=b, src=S.to_src(b), placebo_of=item["src"], uses=[])
    st["P"] = []
    return st


def freeze_source():
    arms, files = {}, list(CODE)
    for r in REPS:
        for coh in COH:
            f = f"artifacts/agi2_src/{coh}_r{r}.json"
            st = load_state(f)
            arms[f"{coh}_r{r}"] = dict(state=ST.to_json(st), digest=ST.digest(st), source=f)
            files.append(f)
        pl = placebo_state(ST.from_json(arms[f"Full_r{r}"]["state"]), r)
        arms[f"Placebo_r{r}"] = dict(state=ST.to_json(pl), digest=ST.digest(pl), source=f"placebo of Full_r{r}")
    save(ROOT / "artifacts/agi2_freeze_source.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def freeze_meta():
    arms, files = {}, []
    for r in REPS:
        for imp in ("Mstar", "M0", "Mrand"):
            f = f"artifacts/agi2_meta/r{r}_{imp}.json"
            st = load_state(f)
            arms[f"Meta_r{r}_{imp}"] = dict(state=ST.to_json(st), digest=ST.digest(st), source=f)
            files.append(f)
    save(ROOT / "artifacts/agi2_freeze_meta.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def arm_state(arm):
    if arm == "Init":
        return ST.empty_state(I.M0)
    if arm.startswith("Meta_"):
        e = json.loads((ROOT / "artifacts/agi2_freeze_meta.json").read_text())["endpoints"][arm]
        st = ST.from_json(e["state"])
        assert ST.digest(st) == e["digest"]
        return st
    fr = json.loads((ROOT / "artifacts/agi2_freeze_source.json").read_text())
    kind, r = arm.rsplit("_r", 1)
    src = {"Full": "Full", "RL": "Full", "Pol": "Full", "Placebo": "Placebo", "Rand": "Random-Proposal", "Fixed": "Fixed-M0",
           "SolvedOnly": "SolvedOnly"}[kind]
    e = fr["endpoints"][f"{src}_r{r}"]
    st = ST.from_json(e["state"])
    assert ST.digest(st) == e["digest"]
    if kind == "RL":
        st["pi"], st["M"], st["P"] = ST.pi0(), copy.deepcopy(I.M0), []
    elif kind == "Pol":
        st["R"], st["L"], st["P"] = {}, {}, []
        st["pi"]["costs"] = {k: v for k, v in st["pi"]["costs"].items() if k[:2] not in ("L:", "R:")}
    return st


def arms_main():
    return [f"{k}_r{r}" for r in REPS for k in ("Full", "SolvedOnly", "RL", "Pol", "Placebo", "Rand", "Fixed")] + ["Init"]


def arms_panel():
    return [f"Meta_r{r}_{m}" for r in REPS for m in ("Mstar", "M0", "Mrand")] + [f"Full_r{r}" for r in REPS]


def plan():
    t = json.loads((ROOT / "artifacts/agi2_dev/timing.json").read_text())
    per = AL.CAP_S + t["overhead_max"] + 0.05
    panel = len(arms_panel()) * 12 * per
    out = None
    for n in (48, 32, 24):
        total = len(arms_main()) * n * per + panel + 10 * 1.5
        if total <= 650 - 20:
            out = dict(n_main=n, per_episode_bound_s=round(per, 3), cap_s=AL.CAP_S, main_arms=len(arms_main()),
                       panel_arms=len(arms_panel()), predicted_total_s=round(total, 1))
            break
    out = out or dict(n_main=None, reason="even 24 tasks do not fit the 650 s stage ceiling")
    save(ROOT / "artifacts/agi2_eval_plan.json", out)
    print(out)


def claim_once():
    """Atomic claim of the one-use ranges: check-and-claim under an exclusive fcntl lock (fixes the Phase 1 race)."""
    lock = ROOT / "runs/experimental/agi2_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            for key in ONE_USE:
                if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                    R.claim(*key, list(R.REGISTRY[key]), run_id="agi2-eval")
                elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi2-eval" for x in R._spent()):
                    raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(kind, chunk, nchunks):
    chunk, nchunks = int(chunk), int(nchunks)
    plan_ = json.loads((ROOT / "artifacts/agi2_eval_plan.json").read_text())
    if not plan_.get("n_main"):
        raise SystemExit("evaluation not opened (plan)")
    for fz in ("artifacts/agi2_freeze_source.json",) + (("artifacts/agi2_freeze_meta.json",) if kind == "panel" else ()):
        for f, h in json.loads((ROOT / fz).read_text())["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
    arms = arms_main() if kind == "main" else arms_panel()
    tasks = (SD.reduced(plan_["n_main"]) if kind == "main" else SD.panels()["improver_panel"])[chunk::nchunks]
    claim_once()
    D.mkdir(parents=True, exist_ok=True)
    out = D / f"{kind}_c{chunk}.jsonl"
    done = {(x["arm"], x["tid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    frozen = {a: ST.to_json(arm_state(a)) for a in arms}
    digests = {a: ST.digest(ST.from_json(frozen[a])) for a in arms}
    with open(out, "a") as fh:
        for (w, f, lv, s, panel) in tasks:
            t = AL.task_of(w, f, lv, s)
            for a in arms:
                name = a if kind == "main" or a.startswith("Meta_") else f"{a}@panel"
                if (name, t.tid) in done:
                    continue
                st = ST.from_json(json.loads(json.dumps(frozen[a])))
                assert ST.digest(st) == digests[a]
                r = AL.safe_episode(t, st, AL.CAP_S)
                r.pop("_ast")
                r.pop("_partials")
                fh.write(json.dumps(dict(r, arm=name, panel=panel, descr=t.descr, state_digest=digests[a]), default=list) + "\n")
                fh.flush()
            print(kind, chunk, t.tid, len(arms), "arms", flush=True)


# ------------------------------------------------------------------ scoring
_ALL = None


def rows_of(arm):
    global _ALL
    if _ALL is None:
        _ALL = [json.loads(l) for p in sorted(D.glob("*_c*.jsonl")) for l in p.read_text().splitlines()]
    if arm == "Scratch":
        arm = "Init"
    return [x for x in _ALL if x["arm"] == arm]


def fam_diff(ra, rb, filt):
    a = {r["tid"]: r for r in ra if filt(r)}
    b = {r["tid"]: r for r in rb if filt(r)}
    fams = {}
    for tid in sorted(set(a) & set(b)):
        fams.setdefault(f"{a[tid]['world']}.{a[tid]['family']}", []).append(float(a[tid]["solved"]) - float(b[tid]["solved"]))
    return {k: sum(v) / len(v) for k, v in fams.items()}


def fam_rate(rs, filt):
    fams = {}
    for r in rs:
        if filt(r):
            fams.setdefault(f"{r['world']}.{r['family']}", []).append(float(r["solved"]))
    return {k: sum(v) / len(v) for k, v in fams.items()}


def boot(d, seed, n=2000):
    rnd = random.Random(seed)
    ks = sorted(d)
    if not ks:
        return None
    ms = sorted(sum(d[rnd.choice(ks)] for _ in ks) / len(ks) for _ in range(n))
    return [round(ms[int(0.025 * n)], 4), round(ms[int(0.975 * n) - 1], 4)]


PANELS = {"withheld": lambda r: r["panel"] == "withheld", "ce_fresh": lambda r: r["panel"] == "ce_fresh",
          "untouched": lambda r: r["panel"] == "untouched", "all": lambda r: r["panel"] != "improver_panel"}


def summary(rs):
    rate = lambda sub: (round(sum(r["solved"] for r in sub) / len(sub), 4) if sub else None)    # noqa: E731
    return dict(n=len(rs), solved=sum(r["solved"] for r in rs), silent=sum(r["silent"] for r in rs),
                abstain=sum(r["outcome"].startswith("abstain") for r in rs), queries=sum(r["queries"] for r in rs),
                cpu_s=round(sum(r["cpu_s"] for r in rs), 2), graded_mean=round(sum(r["graded"] for r in rs) / max(1, len(rs)), 4),
                by_panel={p: rate([r for r in rs if f(r)]) for p, f in PANELS.items()},
                by_world={w: rate([r for r in rs if r["world"] == w]) for w in "ABCDEF" if any(r["world"] == w for r in rs)},
                bd_solved=sum(r["solved"] for r in rs if r["world"] in "BD"), bd_n=sum(r["world"] in "BD" for r in rs),
                solved_tids=sorted(r["tid"] for r in rs if r["solved"]),
                solved_by_origin={o: sum(1 for r in rs if r["solved"] and r.get("origin") == o) for o in ("pure_synthesis", "draft_subtree")})


def score():
    plan_ = json.loads((ROOT / "artifacts/agi2_eval_plan.json").read_text())
    res = dict(plan=plan_, arms={}, missing={})
    T = {}
    for a in arms_main() + ["Scratch"]:
        T[a] = rows_of(a)
        res["missing"][a] = len(SD.reduced(plan_["n_main"])) - len(T[a])
        res["arms"][a] = summary(T[a])
    for a in arms_panel():
        key = a if a.startswith("Meta_") else f"{a}@panel"
        T[key] = rows_of(key)
        res["missing"][key] = 12 - len(T[key])
        res["arms"][key] = summary(T[key])
    contr = {}
    for pname, filt in PANELS.items():
        cp = {}
        for ctrl in ("Init", "Placebo", "Scratch", "SolvedOnly"):
            per, pooled = {}, {}
            for r in REPS:
                c = ctrl if ctrl in ("Init", "Scratch") else f"{ctrl}_r{r}"
                d = fam_diff(T[f"Full_r{r}"], T[c], filt)
                per[f"r{r}"] = dict(mean=round(sum(d.values()) / len(d), 4) if d else None, ci95=boot(d, f"{pname}|{ctrl}|{r}"))
                for k, v in d.items():
                    pooled.setdefault(k, []).append(v)
            pm = {k: sum(v) / len(v) for k, v in pooled.items()}
            cp[f"Full-{ctrl}"] = dict(per_rep=per, pooled=round(sum(pm.values()) / len(pm), 4) if pm else None,
                                      ci95=boot(pm, f"{pname}|{ctrl}|pooled"),
                                      reps_positive=sum(1 for v in per.values() if (v["mean"] or 0) > 0))
        per = {}
        for r in REPS:
            d = fam_diff(T[f"Fixed_r{r}"], T[f"SolvedOnly_r{r}"], filt)
            per[f"r{r}"] = round(sum(d.values()) / len(d), 4) if d else None
        cp["Fixed-SolvedOnly (pure P effect)"] = per
        contr[pname] = cp
        for a in ("Init",) + tuple(f"{k}_r{r}" for r in REPS for k in ("Full", "SolvedOnly", "Placebo")):
            fr = fam_rate(T[a], filt)
            cp.setdefault("family_rates", {})[a] = round(sum(fr.values()) / len(fr), 4) if fr else None
    res["contrasts"] = contr
    dec = {}
    for r in REPS:
        g = {k: fam_rate(T[f"{k}_r{r}"], PANELS["all"]) for k in ("Full", "RL", "Pol")}
        g["Init"] = fam_rate(T["Init"], PANELS["all"])
        m = {k: sum(v.values()) / len(v) for k, v in g.items()}
        dec[f"r{r}"] = dict(rates={k: round(v, 4) for k, v in m.items()}, interaction=round(m["Full"] - m["RL"] - m["Pol"] + m["Init"], 4))
    res["policy_vs_library"] = dec
    res["improver"] = {f"r{r}": {m: dict(solved=sum(x["solved"] for x in T[f"Meta_r{r}_{m}"]),
                                         silent=sum(x["silent"] for x in T[f"Meta_r{r}_{m}"]),
                                         graded=round(sum(x["graded"] for x in T[f"Meta_r{r}_{m}"]), 3))
                                 for m in ("Mstar", "M0", "Mrand")} | dict(pre_meta=sum(x["solved"] for x in T[f"Full_r{r}@panel"]))
                       for r in REPS}
    att = {}
    for r in REPS:
        F = T[f"Full_r{r}"]
        used = {}
        for x in F:
            if x["solved"]:
                for n in x["used_items"]:
                    used.setdefault(n, []).append(x["tid"])
        init_solved = {x["tid"] for x in T["Init"] if x["solved"]}
        att[f"r{r}"] = dict(items_used_in_solves=used, solved_not_by_init=sorted({x["tid"] for x in F if x["solved"]} - init_solved),
                            lost_vs_init=sorted(init_solved - {x["tid"] for x in F if x["solved"]}))
    res["attribution"] = att
    res["complete"] = all(v == 0 for v in res["missing"].values())
    save(D / "result.json", res)
    print(json.dumps({k: res[k] for k in ("contrasts", "improver")}, default=list)[:4000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(*sys.argv[2:5])
    else:
        {"freeze_source": freeze_source, "freeze_meta": freeze_meta, "plan": plan, "score": score}[sys.argv[1]]()

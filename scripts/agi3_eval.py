"""Phase 3 Stage 4 frozen evaluation (NOT LOCKED; ONE-USE agi3/eval_worlds, agi3/eval_untouched, agi3de/eval,
agi3/improver_panel, claimed under an fcntl lock).
  python scripts/agi3_eval.py freeze_source | freeze_meta | plan | run worlds C N | run de RUNTIME | run panel | score
Arms (per source repetition r; Init and Baseline once):
  Full_r        frozen Full endpoint (worlds R*, L*, P*, pi*, M*; DE pi_de*, L_de*, P_de*)
  SolvedOnly_r  the Solved-Only cohort endpoint (no failure memory from t = 0)
  Fixed_r       Fixed-M0 endpoint                 Rand_r   Random-Proposal endpoint
  LibOnly_r     worlds R*, L* with pi0 (P empty); DE skills L_de* with pi_de weights reset (empty)
  ProcOnly_r    worlds pi* with R = L = P = empty; DE pi_de* weights with no skills
  Placebo_r     worlds: matched random R / L (Phase 2 placebo_for); DE: every skill replaced by a random operator sequence of
                the same length with a random precondition of the same size, and the pi_de weight VALUES permuted onto
                random (feature, operator) pairs (matched magnitude, irrelevant content)
  Init          Memory-Reset: empty memory, pi0 / M0 (the same system with persistent memory reset)
  Baseline      Strong conventional baseline: no learning; worlds = the tuned scratch configuration (Init's, Phase 2
                tuning); DE = the same search and tools with an engineer-sensible FIXED operator order
                (de_learner.BASELINE_ORDER) and exact candidate caching (rendered-spec dedup)
  Meta_r_{Mstar,M0,Mrand} + Full_r@panel on the 12-task improver panel (worlds tasks).
World episodes: campaign2 solve under the locked barrier, 0.6 s CPU. DE episodes: de_learner.solve on the project's real
runtime (SQLite budget 0.4 s, Spark 1.2 s wall per arm-project after a warm session), submit only when every public
check passes; independent evaluator on 2 hidden batches. Every episode restores the frozen state (digest-checked)."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign2 import agent_loop as A2, improver as I, state as ST, substrate as S
from nexus.campaign3 import agent_loop as AL, seeds as SD, de_world as DW, de_learner as DL
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agi2_eval import fam_diff, fam_rate, boot  # noqa: E402
D = ROOT / "artifacts/agi3_eval"
REPS = (0, 1, 2)
COH = ("Full", "SolvedOnly", "Fixed-M0", "Random-Proposal")
DE_BUDGET = {"sqlite": 0.4, "spark": 1.2}
CODE = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/campaign3").glob("*.py")) + \
    sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/campaign2").glob("*.py")) + ["scripts/agi3_eval.py"]
WS = ROOT / "var/agi3_ws/eval"


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=list))
    tmp.replace(p)


def digest(st):
    return hashlib.sha256((ST.digest(st) + json.dumps(st.get("DE", {}), sort_keys=True, default=list)).encode()).hexdigest()[:16]


def de_placebo(de, rng):
    p = DL.empty_de()
    for sid, sk in de["skills"].items():
        r = DL.random_skill(rng)
        r["ops"] = [rng.choice(DL.OPS) for _ in sk["ops"]]
        feats = sorted({f for v in [de["w"]] for f in v} | {"fail:row_count", "fail:example_rows", "diff:value", "fail:unique"})
        r["pre"] = sorted(rng.sample(feats, min(len(sk["pre"]), len(feats))))
        p["skills"][sid] = r
    vals = [v for f in de["w"] for v in de["w"][f].values()]
    rng.shuffle(vals)
    feats = sorted(de["w"]) or ["fail:row_count"]
    for v in vals:
        p["w"].setdefault(rng.choice(feats), {})[rng.choice(DL.OPS)] = v
    return p


def freeze_source():
    sys.path.insert(0, str(ROOT / "scripts"))
    from agi2_eval import placebo_state
    arms, files = {}, list(CODE)
    for r in REPS:
        for coh in COH:
            f = f"artifacts/agi3_src/{coh}_r{r}.json"
            doc = json.loads((ROOT / f).read_text())
            if not doc.get("final"):
                raise SystemExit(f"{f} not final")
            st = ST.from_json(doc["state"])
            arms[f"{coh}_r{r}"] = dict(state=ST.to_json(st), digest=digest(st), source=f)
            files.append(f)
        full = ST.from_json(arms[f"Full_r{r}"]["state"])
        pl = placebo_state(full, r)
        pl["DE"] = de_placebo(full.get("DE", DL.empty_de()), random.Random(f"agi3-de-placebo|{SD.RANGES[('agi3', 'placebo')].start + r}"))
        arms[f"Placebo_r{r}"] = dict(state=ST.to_json(pl), digest=digest(pl), source=f"placebo of Full_r{r}")
    save(ROOT / "artifacts/agi3_freeze_source.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def freeze_meta():
    arms, files = {}, []
    for r in REPS:
        for imp in ("Mstar", "M0", "Mrand"):
            f = f"artifacts/agi3_meta/r{r}_{imp}.json"
            st = ST.from_json(json.loads((ROOT / f).read_text())["state"])
            arms[f"Meta_r{r}_{imp}"] = dict(state=ST.to_json(st), digest=digest(st), source=f)
            files.append(f)
    save(ROOT / "artifacts/agi3_freeze_meta.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def arm_state(arm):
    if arm in ("Init", "Baseline"):
        st = ST.empty_state(AL.M3)
        st["DE"] = DL.empty_de()
        return st
    if arm.startswith("Meta_"):
        e = json.loads((ROOT / "artifacts/agi3_freeze_meta.json").read_text())["endpoints"][arm]
    else:
        fr = json.loads((ROOT / "artifacts/agi3_freeze_source.json").read_text())
        kind, r = arm.rsplit("_r", 1)
        src = {"Full": "Full", "LibOnly": "Full", "ProcOnly": "Full", "Placebo": "Placebo", "Rand": "Random-Proposal",
               "Fixed": "Fixed-M0", "SolvedOnly": "SolvedOnly"}[kind]
        e = fr["endpoints"][f"{src}_r{r}"]
    st = ST.from_json(e["state"])
    st.setdefault("DE", DL.empty_de())
    assert digest(st) == e["digest"]
    if arm.startswith("LibOnly"):
        st["pi"], st["M"], st["P"] = ST.pi0(), copy.deepcopy(AL.M3), []
        st["DE"]["w"], st["DE"]["P"] = {}, []
    elif arm.startswith("ProcOnly"):
        st["R"], st["L"], st["P"] = {}, {}, []
        st["pi"]["costs"] = {k: v for k, v in st["pi"]["costs"].items() if k[:2] not in ("L:", "R:")}
        st["DE"]["skills"], st["DE"]["P"] = {}, []
    return st


def arms_main():
    return [f"{k}_r{r}" for r in REPS for k in ("Full", "SolvedOnly", "Fixed", "Rand", "LibOnly", "ProcOnly", "Placebo")] + ["Init", "Baseline"]


def arms_panel():
    return [f"Meta_r{r}_{m}" for r in REPS for m in ("Mstar", "M0", "Mrand")] + [f"Full_r{r}" for r in REPS]


def worlds_suite(n):
    p = SD.panels()
    un = p["untouched3"]
    if n >= 20:
        base = un
    else:
        base = [t for t in un if t[2] in (1, 2)]                   # 8: C7, C8, E7, E8 x L1-L2
    k = (n - len(base)) // 4
    return base + p["ce_instance"][:k] + p["phase2_comparison"][:k] + p["withheld"][:k] + p["retention"][:k]


def plan():
    n_arms = len(arms_main())
    de = SD.de_panel(1)
    per_w = AL.EVAL_CAP_S + 0.075
    de_cost = 35.0 + sum(n_arms * (DE_BUDGET[rt] + (0.1 if rt == "spark" else 0.02)) for (_, _, _, rt, _) in de)
    panel = len(arms_panel()) * 12 * per_w
    out = None
    for n in (20, 16, 12):
        total = de_cost + panel + n_arms * n * per_w + 6 * 1.5
        if total <= 650 - 20:
            out = dict(n_worlds=n, n_de=len(de), de_budget_s=DE_BUDGET, per_world_episode_s=per_w, arms=n_arms,
                       predicted_total_s=round(total, 1), de_predicted_s=round(de_cost, 1), panel_predicted_s=round(panel, 1))
            break
    out = out or dict(n_worlds=None, reason="does not fit 650 s")
    save(ROOT / "artifacts/agi3_eval_plan.json", out)
    print(out)


def claim_once():
    lock = ROOT / "var/agi3_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            for key in sorted(SD.ONE_USE):
                if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                    R.claim(*key, list(R.REGISTRY[key]), run_id="agi3-eval")
                elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi3-eval" for x in R._spent()):
                    raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _check_freeze(kind):
    for fz in ("artifacts/agi3_freeze_source.json",) + (("artifacts/agi3_freeze_meta.json",) if kind == "panel" else ()):
        for f, h in json.loads((ROOT / fz).read_text())["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")


def run(kind, *a):
    plan_ = json.loads((ROOT / "artifacts/agi3_eval_plan.json").read_text())
    if not plan_.get("n_worlds"):
        raise SystemExit("evaluation not opened (plan)")
    _check_freeze(kind)
    claim_once()
    D.mkdir(parents=True, exist_ok=True)
    arms = arms_panel() if kind == "panel" else arms_main()
    frozen = {a_: ST.to_json(arm_state(a_)) for a_ in arms}
    digs = {a_: digest(ST.from_json(json.loads(json.dumps(frozen[a_])))) for a_ in arms}
    if kind == "de":
        rtname = a[0]
        out = D / f"de_{rtname}.jsonl"
        rt = DW.RUNTIMES[rtname]()
        if rtname == "spark":
            t0 = time.time()
            DW.SparkRuntime.warm()
            print("spark warm", round(time.time() - t0, 1), flush=True)
        tasks = [t for t in SD.de_panel(1) if t[3] == rtname]
    elif kind == "worlds":
        c, n = int(a[0]), int(a[1])
        out = D / f"worlds_c{c}.jsonl"
        tasks = worlds_suite(plan_["n_worlds"])[c::n]
    else:
        out = D / "panel.jsonl"
        tasks = SD.panels()["improver_panel"]
    done = {(x["arm"], x["tid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in tasks:
            if kind == "de":
                fam, lv, s, rtn, panel = t
                proj = DW.make_project(fam, lv, s, rtn, WS)
                tid = proj["pid"]
            else:
                w, f, lv, s, panel = t
                task = AL.task_of(w, f, lv, s)
                tid = task.tid
            for a_ in arms:
                name = a_ if kind != "panel" or a_.startswith("Meta_") else f"{a_}@panel"
                if (name, tid) in done:
                    continue
                st = ST.from_json(json.loads(json.dumps(frozen[a_])))
                assert digest(st) == digs[a_]
                if kind == "de":
                    order = DL.BASELINE_ORDER if a_ == "Baseline" else None
                    rec = DL.solve(proj, st["DE"], rt, budget_s=DE_BUDGET[rtname], order=order, use_skills=a_ != "Baseline")
                    ev = DW.evaluate(proj, rec["spec"], rt) if rec["solved_visible"] else None
                    row = dict(tid=tid, world="DE", family=fam, level=lv, runtime=rtn, panel=panel, arm=name,
                               solved=bool(ev and ev["ok"]), silent=rec["solved_visible"] and not (ev and ev["ok"]),
                               outcome="submitted" if rec["solved_visible"] else "abstain", runs=rec["runs"], wall_s=rec["wall"],
                               edits=rec["edits"], reused=[x["skill"] for x in rec["trace"] if x.get("step") == "reuse"],
                               hidden=ev and ev["fails"], state_digest=digs[a_], legacy_failed=rec["start"]["failed"],
                               legacy_error=rec["start"].get("error"))
                else:
                    r = A2.safe_episode(task, st, AL.EVAL_CAP_S)
                    r.pop("_ast"), r.pop("_partials")
                    row = dict(r, arm=name, panel=panel, descr=task.descr, state_digest=digs[a_])
                fh.write(json.dumps(row, default=list) + "\n")
                fh.flush()
            print(kind, tid, len(arms), "arms", flush=True)


# ------------------------------------------------------------------ scoring
def _all():
    return [json.loads(l) for p in sorted(D.glob("*.jsonl")) for l in p.read_text().splitlines()]


def score():
    rows = _all()
    by = {}
    for x in rows:
        by.setdefault(x["arm"], []).append(x)
    res = dict(plan=json.loads((ROOT / "artifacts/agi3_eval_plan.json").read_text()), arms={})
    panels = ("retention", "withheld", "ce_instance", "phase2_comparison", "untouched3", "de_instance", "de_holdout", "improver_panel")
    for a, rs in by.items():
        sm = dict(n=len(rs), solved=sum(r["solved"] for r in rs), silent=sum(r["silent"] for r in rs),
                  abstain=sum(r["outcome"].startswith("abstain") for r in rs))
        for p in panels:
            sub = [r for r in rs if r["panel"] == p]
            if sub:
                sm[p] = dict(n=len(sub), solved=sum(r["solved"] for r in sub), silent=sum(r["silent"] for r in sub))
        de = [r for r in rs if r["world"] == "DE"]
        if de:
            sm["de"] = dict(n=len(de), solved=sum(r["solved"] for r in de), silent=sum(r["silent"] for r in de),
                            runs=sum(r["runs"] for r in de), wall_s=round(sum(r["wall_s"] for r in de), 2),
                            by_runtime={rt: dict(solved=sum(r["solved"] for r in de if r["runtime"] == rt),
                                                 n=sum(r["runtime"] == rt for r in de),
                                                 runs=sum(r["runs"] for r in de if r["runtime"] == rt)) for rt in ("sqlite", "spark")},
                            solved_runs=sum(r["runs"] for r in de if r["solved"]))
        res["arms"][a] = sm
    # contrasts (family-clustered; worlds panels and DE panels), Full vs each control, per repetition and pooled
    contr = {}
    for p in panels[:-1]:
        filt = lambda r, p=p: r["panel"] == p                      # noqa: E731
        cp = {}
        for ctrl in ("Init", "Placebo", "Baseline", "SolvedOnly", "Fixed"):
            per, pooled = {}, {}
            for r in REPS:
                c = ctrl if ctrl in ("Init", "Baseline") else f"{ctrl}_r{r}"
                d = fam_diff(by.get(f"Full_r{r}", []), by.get(c, []), filt)
                per[f"r{r}"] = round(sum(d.values()) / len(d), 4) if d else None
                for k, v in d.items():
                    pooled.setdefault(k, []).append(v)
            pm = {k: sum(v) / len(v) for k, v in pooled.items()}
            cp[f"Full-{ctrl}"] = dict(per_rep=per, pooled_pp=round(100 * sum(pm.values()) / len(pm), 1) if pm else None,
                                      ci95=boot(pm, f"agi3|{p}|{ctrl}"))
        contr[p] = cp
    res["contrasts"] = contr
    # DE cost at matched completion: total runtime executions on projects solved by BOTH Full and the control
    cost = {}
    for ctrl in ("Init", "Baseline", "Fixed", "SolvedOnly", "Placebo"):
        per = {}
        for r in REPS:
            F = {x["tid"]: x for x in by.get(f"Full_r{r}", []) if x["world"] == "DE"}
            c = ctrl if ctrl in ("Init", "Baseline") else f"{ctrl}_r{r}"
            Cc = {x["tid"]: x for x in by.get(c, []) if x["world"] == "DE"}
            both = [t for t in F if t in Cc and F[t]["solved"] and Cc[t]["solved"]]
            fr, cr = sum(F[t]["runs"] for t in both), sum(Cc[t]["runs"] for t in both)
            per[f"r{r}"] = dict(n_both=len(both), full_runs=fr, ctrl_runs=cr, saving=round(1 - fr / cr, 3) if cr else None,
                                full_solved=sum(x["solved"] for x in F.values()), ctrl_solved=sum(x["solved"] for x in Cc.values()),
                                full_silent=sum(x["silent"] for x in F.values()), ctrl_silent=sum(x["silent"] for x in Cc.values()))
        cost[ctrl] = per
    res["de_cost_at_matched_completion"] = cost
    res["improver"] = {f"r{r}": {m: sum(x["solved"] for x in by.get(f"Meta_r{r}_{m}", [])) for m in ("Mstar", "M0", "Mrand")} |
                       dict(pre_meta=sum(x["solved"] for x in by.get(f"Full_r{r}@panel", []))) for r in REPS}
    save(D / "result.json", res)
    print(json.dumps({k: res[k] for k in ("de_cost_at_matched_completion", "improver")}, default=list)[:3000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(*sys.argv[2:])
    else:
        {"freeze_source": freeze_source, "freeze_meta": freeze_meta, "plan": plan, "score": score}[sys.argv[1]]()

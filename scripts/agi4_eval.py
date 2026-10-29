"""Phase 4 Stage 4 frozen evaluation (NOT LOCKED; ONE-USE agi4de/eval and agi4de/panel, claimed under an fcntl lock).
  python scripts/agi4_eval.py freeze_source | freeze_meta | plan | run de CHUNK N_CHUNKS | run panel CHUNK N_CHUNKS | score
Targets: seeds.eval_manifest() (24 = 6 families x {SQLite k1, SQLite k3, Spark k1, Spark k3}; F7 normalize and F8 tombstone
are untouched mechanism families) and seeds.panel_manifest() (12 = the 6 source mechanisms x {SQLite, Spark}, k = 2).
Arms (per source repetition r; Init and Baseline once):
  Full_r        frozen Full endpoint (pi_de*, L*, P*, prefs*, M*)
  SolvedOnly_r  the Solved-Only cohort endpoint (failure memory off from t = 0, its own M)
  Fixed_r       Fixed-M0 endpoint (M0)                  Rand_r   Random-Proposal endpoint (its random M)
  Placebo_r     Full_r's procedure M* with MATCHED IRRELEVANT memory: every skill replaced by a random operator sequence of
                the same length / kind with a random precondition of the same size; pi_de weight values, preference values
                and P records permuted onto random (feature, operator) / choice-class / operator targets
  Init          Memory-Reset: empty memory, M0 (the same system with persistent memory wiped)
  Baseline      strong conventional baseline: no learning, no memory, the same search, tools, de_accept_v2 and budgets with
                the engineer-sensible FIXED operator order (ops.BASELINE_ORDER)
  Meta_r_{Mstar,M0,Mrand}  the 9 post-rollout improver clones (panel only)
Per arm-project: learner.solve at 2.5 s (SQLite) / 10 s (Spark) wall after a warm session, no exploration, de_accept_v2;
the repair is written as submission/pipeline.{sql,py} + PATCH.diff and the INDEPENDENT evaluator executes that file on 2
hidden batches. Every episode restores the frozen state (digest-checked)."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
from nexus import seed_registry as R
from nexus.de_phase4 import world as W, learner as L, lineage as LG, seeds as SD, adapter as AD, ops as O
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/agi4_eval"
REPS = (0, 1, 2)
COH = ("Full", "SolvedOnly", "Fixed-M0", "Random-Proposal")
BUDGET = {"sqlite": 2.5, "spark": 10.0}
CODE = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src/nexus/de_phase4").glob("*.py")) + ["scripts/agi4_eval.py"]
WS = ROOT / "var/agi4_ws/eval"


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=list))
    tmp.replace(p)


def digest(st):
    return hashlib.sha256(json.dumps(st, sort_keys=True, default=list).encode()).hexdigest()[:16]


def placebo(st, rng):
    """Matched irrelevant memory under the same procedure M."""
    de = st["DE"]
    p = L.empty_de()
    p["next_id"] = de["next_id"]
    for sid, sk in de["skills"].items():
        r = L.random_skill(rng)
        r["ops"] = [rng.choice(O.OPS) for _ in sk["ops"]]
        r["pre"] = sorted(rng.sample(L.FEATS, min(len(sk["pre"]), len(L.FEATS))))
        r["kind"] = sk.get("kind", "full")
        p["skills"][sid] = r
    feats = sorted(set(de["w"]) | set(L.FEATS))
    vals = [v for f in de["w"] for v in de["w"][f].values()]
    rng.shuffle(vals)
    for v in vals:
        p["w"].setdefault(rng.choice(feats), {})[rng.choice(O.OPS)] = v
    classes = sorted(set(de["prefs"]) | {f"{op}:{c}" for op in O.OPS for c in ("-", "absent")} |
                     {f"filter_file:{a}:{b}" for a in ("gt", "ge") for b in ("sub", "file")})
    pv = list(de["prefs"].values())
    rng.shuffle(pv)
    for v in pv:
        p["prefs"][rng.choice(classes)] = v
    for rec in de["P"]:
        q = dict(rec)
        if q.get("kind") == "partial":
            q["op"] = rng.choice(O.OPS)
            q["fixes"] = sorted(rng.sample(L.FEATS, min(len(rec.get("fixes", [])), len(L.FEATS))))
        p["P"].append(q)
    return dict(DE=p, M=copy.deepcopy(st["M"]))


def freeze_source():
    arms, files = {}, list(CODE)
    for r in REPS:
        for coh in COH:
            f = f"artifacts/agi4_src/{coh}_r{r}.json"
            doc = json.loads((ROOT / f).read_text())
            trunc = ROOT / f.replace(".json", ".truncation.json")
            if not doc.get("final") and not trunc.exists():
                raise SystemExit(f"{f} not final")
            arms[f"{coh}_r{r}"] = dict(state=doc["state"], digest=digest(doc["state"]), source=f, truncated=trunc.exists())
            if trunc.exists():
                files.append(str(trunc.relative_to(ROOT)))
            files.append(f)
        pl = placebo(arms[f"Full_r{r}"]["state"], random.Random(f"agi4-placebo|{SD.RANGES[('agi4de', 'placebo')].start + r}"))
        arms[f"Placebo_r{r}"] = dict(state=pl, digest=digest(pl), source=f"placebo of Full_r{r}")
    save(ROOT / "artifacts/agi4_freeze_source.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def freeze_meta():
    arms, files = {}, []
    for r in REPS:
        for imp in ("Mstar", "M0", "Mrand"):
            f = f"artifacts/agi4_meta/r{r}_{imp}.json"
            st = json.loads((ROOT / f).read_text())["state"]
            arms[f"Meta_r{r}_{imp}"] = dict(state=st, digest=digest(st), source=f)
            files.append(f)
    save(ROOT / "artifacts/agi4_freeze_meta.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def arms_main():
    return [f"{k}_r{r}" for r in REPS for k in ("Full", "SolvedOnly", "Fixed", "Rand", "Placebo")] + ["Init", "Baseline"]


def arms_panel():
    return [f"Meta_r{r}_{m}" for r in REPS for m in ("Mstar", "M0", "Mrand")]


def arm_state(arm):
    if arm in ("Init", "Baseline"):
        return dict(DE=L.empty_de(), M=copy.deepcopy(LG.M0))
    if arm.startswith("Meta_"):
        e = json.loads((ROOT / "artifacts/agi4_freeze_meta.json").read_text())["endpoints"][arm]
    else:
        kind, r = arm.rsplit("_r", 1)
        src = {"Full": "Full", "SolvedOnly": "SolvedOnly", "Fixed": "Fixed-M0", "Rand": "Random-Proposal", "Placebo": "Placebo"}[kind]
        e = json.loads((ROOT / "artifacts/agi4_freeze_source.json").read_text())["endpoints"][f"{src}_r{r}"]
    st = json.loads(json.dumps(e["state"]))
    assert digest(st) == e["digest"]
    return st


def plan():
    """Predicted Stage 4 cost from the Stage 1 eval-budget measurements (artifacts/agi4_cycle.json, dev projects): mean
    wall per arm-project by runtime, + evaluator runs, + one warm Spark session per worker."""
    cyc = json.loads((ROOT / "artifacts/agi4_cycle.json").read_text())["reuse"]["test"]
    walls = {"sqlite": [], "spark": []}
    for pid, conds in cyc.items():
        for v in conds.values():
            walls["spark" if ".spark." in pid else "sqlite"].append(v["wall"])
    mean = {k: sum(v) / len(v) for k, v in walls.items()}
    n_main, n_pan = len(arms_main()), len(arms_panel())
    m, pn = SD.eval_manifest(), SD.panel_manifest()
    per = lambda rt: mean[rt] + (0.15 if rt == "spark" else 0.01)          # noqa: E731  (+ 2 hidden-batch evaluator runs)
    pred_main = sum(n_main * per(t["runtime"]) for t in m)
    pred_pan = sum(n_pan * per(t["runtime"]) for t in pn)
    out = dict(arms_main=arms_main(), arms_panel=arms_panel(), budget_s=BUDGET, mean_wall_measured=mean,
               predicted_main_s=round(pred_main, 1), predicted_panel_s=round(pred_pan, 1), workers=6, warm_s_per_worker=3.0,
               predicted_total_s=round(pred_main + pred_pan + 6 * 4.0, 1), manifest=m, panel=pn, opened=True)
    save(ROOT / "artifacts/agi4_eval_plan.json", out)
    print({k: v for k, v in out.items() if k not in ("manifest", "panel")})


def claim_once():
    lock = ROOT / "var/agi4_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            for key in sorted(SD.ONE_USE):
                if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                    R.claim(*key, list(R.REGISTRY[key]), run_id="agi4-eval")
                elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi4-eval" for x in R._spent()):
                    raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _check_freeze(kind):
    for fz in ("artifacts/agi4_freeze_source.json",) + (("artifacts/agi4_freeze_meta.json",) if kind == "panel" else ()):
        for f, h in json.loads((ROOT / fz).read_text())["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")


def run(kind, chunk, n_chunks):
    chunk, n_chunks = int(chunk), int(n_chunks)
    if not json.loads((ROOT / "artifacts/agi4_eval_plan.json").read_text()).get("opened"):
        raise SystemExit("evaluation not opened (plan)")
    _check_freeze(kind)
    claim_once()
    D.mkdir(parents=True, exist_ok=True)
    arms = arms_panel() if kind == "panel" else arms_main()
    frozen = {a: arm_state(a) for a in arms}
    digs = {a: digest(frozen[a]) for a in arms}
    tasks = (SD.panel_manifest() if kind == "panel" else SD.eval_manifest())[chunk::n_chunks]
    out = D / f"{kind}_c{chunk}.jsonl"
    done = {(x["arm"], x["tid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    rts = {"sqlite": W.SQLiteCode(), "spark": W.SparkCode()}
    if any(t["runtime"] == "spark" for t in tasks):
        t0 = time.time()
        W.SparkCode.warm()
        print("spark warm", round(time.time() - t0, 2), flush=True)
    allowed = SD.SOURCE_FAMS + SD.UNTOUCHED_FAMS
    with open(out, "a") as fh:
        for t in tasks:
            proj = W.make_project(t["family"], t["k"], t["seed"], t["runtime"], WS / kind, allowed=allowed)
            rt = rts[t["runtime"]]
            for a in arms:
                if (a, proj["pid"]) in done:
                    continue
                st = json.loads(json.dumps(frozen[a]))
                assert digest(st) == digs[a]
                base = a == "Baseline"
                rec = L.solve(proj, st["DE"], rt, budget_s=BUDGET[t["runtime"]], M=st["M"], order=O.BASELINE_ORDER if base else None,
                              use_skills=not base, explore=False)
                ev = None
                if rec["outcome"] == "submitted":
                    path, _ = AD.write_patch(proj["ws"], rec["spec"], proj["lang"], out_dir=f"submission_{a}")
                    ev = W.evaluate(proj, path.read_text(), rt)
                row = dict(tid=proj["pid"], family=t["family"], k=t["k"], runtime=t["runtime"], panel=t["panel"], arm=a,
                           faults=proj["faults"], outcome=rec["outcome"], status=rec.get("status"), solved=bool(ev and ev["ok"]),
                           silent=rec["outcome"] == "submitted" and not (ev and ev["ok"]), runs=rec["runs"], runs_by=rec["runs_by"],
                           wall_s=rec["wall"], edits=rec["edits"], hidden=ev and ev["fails"], state_digest=digs[a],
                           reused=[x["skill"] for x in rec["trace"] if x.get("step") == "reuse"],
                           gate=[{k: g[k] for k in g if k != "edits"} for g in rec["gate"]][-2:], legacy=rec.get("start"))
                fh.write(json.dumps(row, default=list) + "\n")
                fh.flush()
            print(kind, proj["pid"], len(arms), "arms", flush=True)


# ------------------------------------------------------------------ scoring
def _rows():
    return [json.loads(l) for p in sorted(D.glob("*.jsonl")) for l in p.read_text().splitlines() if l.strip()]


def boot(per_fam, key, n=2000):
    """95 % family-clustered bootstrap interval of the mean of per-family differences (percentage points)."""
    fams = sorted(per_fam)
    if not fams:
        return None
    rng = random.Random(f"agi4-boot|{key}")
    ms = sorted(100 * sum(per_fam[rng.choice(fams)] for _ in fams) / len(fams) for _ in range(n))
    return [round(ms[int(0.025 * n)], 1), round(ms[int(0.975 * n)], 1)]


def fam_diff(a_rows, b_rows, filt):
    out = {}
    fa, fb = {}, {}
    for x in a_rows:
        if filt(x):
            fa.setdefault(x["family"], []).append(x["solved"])
    for x in b_rows:
        if filt(x):
            fb.setdefault(x["family"], []).append(x["solved"])
    for f in fa:
        if f in fb:
            out[f] = sum(fa[f]) / len(fa[f]) - sum(fb[f]) / len(fb[f])
    return out


def score():
    rows = _rows()
    by = {}
    for x in rows:
        by.setdefault(x["arm"], []).append(x)
    res = dict(plan={k: v for k, v in json.loads((ROOT / "artifacts/agi4_eval_plan.json").read_text()).items() if k not in ("manifest", "panel")},
               n_rows=len(rows), arms={})
    for a, rs in by.items():
        sm = dict(n=len(rs), solved=sum(r["solved"] for r in rs), silent=sum(r["silent"] for r in rs),
                  ambiguous=sum(r["outcome"] == "abstain_ambiguous" for r in rs), none=sum(r["outcome"] == "abstain_none" for r in rs),
                  unsupported=sum(r["outcome"] == "abstain_unsupported" for r in rs), runs=sum(r["runs"] for r in rs),
                  wall_s=round(sum(r["wall_s"] for r in rs), 2))
        for key, f in (("sqlite", lambda r: r["runtime"] == "sqlite"), ("spark", lambda r: r["runtime"] == "spark"),
                       ("de_instance", lambda r: r["panel"] == "de_instance"), ("de_untouched", lambda r: r["panel"] == "de_untouched"),
                       ("k1", lambda r: r["k"] == 1), ("k3", lambda r: r["k"] == 3)):
            sub = [r for r in rs if f(r)]
            if sub:
                sm[key] = dict(n=len(sub), solved=sum(r["solved"] for r in sub), silent=sum(r["silent"] for r in sub))
        res["arms"][a] = sm
    contr = {}
    for pname, filt in (("all", lambda r: True), ("spark", lambda r: r["runtime"] == "spark"), ("sqlite", lambda r: r["runtime"] == "sqlite"),
                        ("de_untouched", lambda r: r["panel"] == "de_untouched")):
        cp = {}
        for ctrl in ("Init", "Placebo", "Baseline", "SolvedOnly", "Fixed", "Rand"):
            per, pooled = {}, {}
            for r in REPS:
                c = ctrl if ctrl in ("Init", "Baseline") else f"{ctrl}_r{r}"
                d = fam_diff(by.get(f"Full_r{r}", []), by.get(c, []), filt)
                per[f"r{r}"] = round(100 * sum(d.values()) / len(d), 1) if d else None
                for k, v in d.items():
                    pooled.setdefault(k, []).append(v)
            pm = {k: sum(v) / len(v) for k, v in pooled.items()}
            cp[f"Full-{ctrl}"] = dict(per_rep_pp=per, pooled_pp=round(100 * sum(pm.values()) / len(pm), 1) if pm else None,
                                      ci95=boot(pm, f"{pname}|{ctrl}"))
        contr[pname] = cp
    res["completion_contrasts"] = contr
    cost = {}
    for ctrl in ("Init", "Baseline", "Fixed", "SolvedOnly", "Placebo", "Rand"):
        per = {}
        for r in REPS:
            F = {x["tid"]: x for x in by.get(f"Full_r{r}", [])}
            c = ctrl if ctrl in ("Init", "Baseline") else f"{ctrl}_r{r}"
            Cc = {x["tid"]: x for x in by.get(c, [])}
            both = [t for t in F if t in Cc and F[t]["solved"] and Cc[t]["solved"]]
            fr, cr = sum(F[t]["runs"] for t in both), sum(Cc[t]["runs"] for t in both)
            fw, cw = sum(F[t]["wall_s"] for t in both), sum(Cc[t]["wall_s"] for t in both)
            per[f"r{r}"] = dict(n_both=len(both), full_runs=fr, ctrl_runs=cr, saving_runs=round(1 - fr / cr, 3) if cr else None,
                                saving_wall=round(1 - fw / cw, 3) if cw else None)
        tot_f = sum(v["full_runs"] for v in per.values())
        tot_c = sum(v["ctrl_runs"] for v in per.values())
        cost[ctrl] = dict(per_rep=per, pooled_saving_runs=round(1 - tot_f / tot_c, 3) if tot_c else None)
    res["cost_at_matched_completion"] = cost
    res["improver_panel"] = {f"r{r}": {m: dict(solved=sum(x["solved"] for x in by.get(f"Meta_r{r}_{m}", [])),
                                               silent=sum(x["silent"] for x in by.get(f"Meta_r{r}_{m}", [])),
                                               runs=sum(x["runs"] for x in by.get(f"Meta_r{r}_{m}", [])),
                                               n=len(by.get(f"Meta_r{r}_{m}", []))) for m in ("Mstar", "M0", "Mrand")} for r in REPS}
    res["silent_total_main"] = sum(v["silent"] for a, v in res["arms"].items() if not a.startswith("Meta_"))
    save(D / "result.json", res)
    print(json.dumps({k: res[k] for k in ("completion_contrasts", "cost_at_matched_completion", "improver_panel", "silent_total_main")},
                     default=list)[:4000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(*sys.argv[2:])
    else:
        {"freeze_source": freeze_source, "freeze_meta": freeze_meta, "plan": plan, "score": score}[sys.argv[1]]()

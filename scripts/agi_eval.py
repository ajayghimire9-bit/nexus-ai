"""Multi-world campaign Stage 4 frozen target evaluation (NOT LOCKED; ONE-USE agi/eval_* and agi/improver_panel).
  python scripts/agi_eval.py freeze_source      artifacts/agi_freeze_source.json: the 9 source endpoints + file hashes
  python scripts/agi_eval.py freeze_meta        artifacts/agi_freeze_meta.json: the 9 post-meta learners
  python scripts/agi_eval.py plan               artifacts/agi_eval_plan.json: main-suite size N in {56, 36, 24} from the
                                                DEVELOPMENT timing calibration only (artifacts/agi_dev/timing.json)
  python scripts/agi_eval.py run main|panel C N   tasks C::N of the suite under every arm (task-major; resumable)
  python scripts/agi_eval.py score              -> artifacts/agi_eval/result.json
Arms (per source repetition r = 0, 1, 2; Init and Scratch are repetition-independent and run once):
  Full_r     frozen Full endpoint (R*, L*, pi*, M*)
  RL_r       R*, L* with pi0 / M0 (no policy transfer; L / R items at the default item cost)
  Pol_r      pi* (learned costs of primitives / constants and effort parameters) with R = L = empty
  Init       (R0 = L0 = empty, pi0, M0)
  Placebo_r  pi* with an operationally matched random library: every R* / L* item replaced by a random well-typed,
             executable, non-constant program of the same kind, hole / input types, output type and description length,
             keeping the item's learned cost and utility (generator seeded from agi/placebo)
  Rand_r     frozen Random-Proposal endpoint;  Fixed_r  frozen Fixed-M0 endpoint
  Scratch    strong scratch synthesis: the same typed bottom-up enumerator with subexpression sharing, observational-
             equivalence deduplication and the same acceptance loop (probes, queries, confirmation, chance-fit bound),
             with size-ordered costs (every production cost 1); no learned state
  Meta_r_{Mstar,M0,Mrand}  the 9 post-meta learners (improver panel only); Full_r also runs on the improver panel as the
             pre-meta reference.
Every episode restores the frozen state from the freeze file (state digests are checked) and runs agent_loop.episode
(solve steps 1-7 only; no cross-episode learning). Per-task CPU cap = agent_loop.CAP_S."""
import copy, hashlib, json, random, sys
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign import agent_loop as AL, improver as I, seeds as SD, state as ST, substrate as S
from nexus.campaign.worlds import make_task
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/agi_eval"
REPS = (0, 1, 2)
CODE = ["src/nexus/campaign/substrate.py", "src/nexus/campaign/agent_loop.py", "src/nexus/campaign/improver.py",
        "src/nexus/campaign/state.py", "src/nexus/campaign/seeds.py", "src/nexus/campaign/worlds/__init__.py",
        "src/nexus/campaign/worlds/base.py"] + [f"src/nexus/campaign/worlds/world_{w}.py" for w in
                                               ("a_data", "b_temporal", "c_spatial", "d_planning", "e_causal", "f_programs")] + \
       ["scripts/agi_eval.py"]
ONE_USE = [("agi", "eval_withheld"), ("agi", "eval_heldout"), ("agi", "eval_retention"), ("agi", "improver_panel")]


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
    return ST.from_json(doc["state"]), doc


def freeze_source():
    arms, files = {}, list(CODE)
    for r in REPS:
        for coh in ("Full", "Fixed-M0", "Random-Proposal"):
            f = f"artifacts/agi_src/{coh}_r{r}.json"
            st, doc = load_state(f)
            arms[f"{coh}_r{r}"] = dict(state=ST.to_json(st), digest=ST.digest(st), source=f)
            files.append(f)
        pl = placebo_state(ST.from_json(arms[f"Full_r{r}"]["state"]), r)      # the matched placebo is frozen here too
        arms[f"Placebo_r{r}"] = dict(state=ST.to_json(pl), digest=ST.digest(pl), source=f"placebo of Full_r{r}")
    save(ROOT / "artifacts/agi_freeze_source.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def freeze_meta():
    arms, files = {}, []
    for r in REPS:
        for imp in ("Mstar", "M0", "Mrand"):
            f = f"artifacts/agi_meta/r{r}_{imp}.json"
            st, doc = load_state(f)
            arms[f"Meta_r{r}_{imp}"] = dict(state=ST.to_json(st), digest=ST.digest(st), source=f)
            files.append(f)
    save(ROOT / "artifacts/agi_freeze_meta.json", dict(endpoints=arms, files={f: sha(f) for f in files}))
    print("frozen", {k: v["digest"] for k, v in arms.items()})


def scratch_state():
    st = ST.empty_state(I.M0)
    st["pi"]["costs"] = {k: 1 for k in st["pi"]["costs"]}
    return st


def placebo_state(full, rep):
    st = copy.deepcopy(full)
    existing = {S.to_src(v["body"]) for v in list(full["L"].values()) + list(full["R"].values())}
    for tab in ("L", "R"):
        for iid, item in full[tab].items():
            rng = random.Random(f"agi-placebo|{SD.RANGES[('agi', 'placebo')].start + rep}|{iid}")
            b = I.placebo_for(dict(item, kind=tab), rng, existing)
            if b is None:
                raise SystemExit(f"no placebo for {iid}")
            existing.add(S.to_src(b))
            st[tab][iid] = dict(item, body=b, src=S.to_src(b), placebo_of=item["src"], uses=[])
    return st


def arm_state(arm):
    if arm == "Init":
        return ST.empty_state(I.M0)
    if arm == "Scratch":
        return scratch_state()
    if arm.startswith("Meta_"):
        fr = json.loads((ROOT / "artifacts/agi_freeze_meta.json").read_text())
        e = fr["endpoints"][arm]
        st = ST.from_json(e["state"])
        assert ST.digest(st) == e["digest"]
        return st
    fr = json.loads((ROOT / "artifacts/agi_freeze_source.json").read_text())
    kind, r = arm.rsplit("_r", 1)
    src = {"Full": "Full", "RL": "Full", "Pol": "Full", "Placebo": "Placebo", "Rand": "Random-Proposal", "Fixed": "Fixed-M0"}[kind]
    e = fr["endpoints"][f"{src}_r{r}"]
    st = ST.from_json(e["state"])
    assert ST.digest(st) == e["digest"]
    if kind == "RL":
        st["pi"], st["M"] = ST.pi0(), copy.deepcopy(I.M0)
    elif kind == "Pol":
        st["R"], st["L"] = {}, {}
        st["pi"]["costs"] = {k: v for k, v in st["pi"]["costs"].items() if k[:2] not in ("L:", "R:")}
    return st


def arms_main():
    return [f"{k}_r{r}" for r in REPS for k in ("Full", "RL", "Pol", "Placebo", "Rand", "Fixed")] + ["Init", "Scratch"]


def arms_panel():
    return [f"Meta_r{r}_{m}" for r in REPS for m in ("Mstar", "M0", "Mrand")] + [f"Full_r{r}" for r in REPS]


def plan():
    t = json.loads((ROOT / "artifacts/agi_dev/timing.json").read_text())
    ovh = t["overhead_max"] + 0.05
    per = AL.CAP_S + ovh
    panel = len(arms_panel()) * 12 * per
    out = None
    for n in (56, 36, 24):
        total = len(arms_main()) * n * per + panel + (len(arms_main()) + len(arms_panel())) * 1.5
        if total <= 1000 - 60:
            out = dict(n_main=n, per_episode_bound_s=round(per, 3), overhead_s=round(ovh, 3), cap_s=AL.CAP_S,
                       main_arms=len(arms_main()), panel_arms=len(arms_panel()), predicted_total_s=round(total, 1))
            break
    out = out or dict(n_main=None, reason="even 24 tasks do not fit the 1,000 s stage ceiling")
    save(ROOT / "artifacts/agi_eval_plan.json", out)
    print(out)


def run(kind, chunk, nchunks):
    """kind main | panel: tasks[chunk::nchunks] of that suite, each task under EVERY arm of the suite (task-major, so any
    machine-speed variation hits all arms equally); rows -> artifacts/agi_eval/<kind>_c<chunk>.jsonl (append, resumable
    per (arm, task); a finished (arm, task) is never rerun)."""
    chunk, nchunks = int(chunk), int(nchunks)
    plan_ = json.loads((ROOT / "artifacts/agi_eval_plan.json").read_text())
    if not plan_.get("n_main"):
        raise SystemExit("evaluation not opened (plan)")
    fr = json.loads((ROOT / "artifacts/agi_freeze_source.json").read_text())
    for f, h in fr["files"].items():
        if sha(f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if kind == "panel":
        frm = json.loads((ROOT / "artifacts/agi_freeze_meta.json").read_text())
        for f, h in frm["files"].items():
            if sha(f) != h:
                raise SystemExit(f"differs from the freeze: {f}")
    arms = arms_main() if kind == "main" else arms_panel()
    tasks = (SD.reduced(plan_["n_main"]) if kind == "main" else SD.panels()["improver_panel"])[chunk::nchunks]
    for key in ONE_USE:
        if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
            R.claim(*key, list(R.REGISTRY[key]), run_id="agi-eval")
    D.mkdir(parents=True, exist_ok=True)
    out = D / f"{kind}_c{chunk}.jsonl"
    done = {(x["arm"], x["tid"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    frozen = {a: ST.to_json(arm_state(a)) for a in arms}
    digests = {a: ST.digest(ST.from_json(frozen[a])) for a in arms}
    with open(out, "a") as fh:
        for (w, f, lv, s, panel) in tasks:
            role = SD.role_of(w, f)
            t = make_task(w, f, lv, s, role, SD.partners_for(w, f, role))
            for a in arms:
                if (a, t.tid) in done:
                    continue
                st = ST.from_json(json.loads(json.dumps(frozen[a])))     # the frozen state, restored for every episode
                assert ST.digest(st) == digests[a]
                r = AL.safe_episode(t, st, AL.CAP_S)
                r.pop("_ast")
                fh.write(json.dumps(dict(r, arm=a if kind == "main" or a.startswith("Meta_") else f"{a}@panel", panel=panel,
                                         descr=t.descr, state_digest=digests[a]), default=list) + "\n")
                fh.flush()
            print(kind, chunk, t.tid, sum(1 for _ in arms), "arms", flush=True)


# ------------------------------------------------------------------ scoring
_ALL = None


def _rows(arm):
    global _ALL
    if _ALL is None:
        _ALL = [json.loads(l) for p in sorted(D.glob("*_c*.jsonl")) for l in p.read_text().splitlines()]
    return [x for x in _ALL if x["arm"] == arm]


def _fam_mean(rows, key="solved"):
    """Family-clustered mean: average within (world, family) first, then across families."""
    fams = {}
    for r in rows:
        fams.setdefault((r["world"], r["family"]), []).append(float(r[key]))
    return sum(sum(v) / len(v) for v in fams.values()) / len(fams) if fams else None, sorted(fams)


def _cluster_boot(diff_by_fam, n=2000, seed="agi-boot"):
    """95% interval of the mean family-level difference by resampling families (cluster bootstrap)."""
    rnd = random.Random(seed)
    fams = sorted(diff_by_fam)
    if not fams:
        return None
    ms = sorted(sum(diff_by_fam[rnd.choice(fams)] for _ in fams) / len(fams) for _ in range(n))
    return [round(ms[int(0.025 * n)], 4), round(ms[int(0.975 * n) - 1], 4)]


def _fam_diff(ra, rb, filt):
    a = {r["tid"]: r for r in ra if filt(r)}
    b = {r["tid"]: r for r in rb if filt(r)}
    fams = {}
    for tid in sorted(set(a) & set(b)):
        x, y = a[tid], b[tid]
        fams.setdefault((x["world"], x["family"]), []).append(float(x["solved"]) - float(y["solved"]))
    return {f"{w}.{f}": sum(v) / len(v) for (w, f), v in fams.items()}


def summary(rows):
    def rate(sub):
        return round(sum(r["solved"] for r in sub) / len(sub), 4) if sub else None
    out = dict(n=len(rows), solved=sum(r["solved"] for r in rows), silent=sum(r["silent"] for r in rows),
               abstain=sum(r["outcome"].startswith("abstain") for r in rows), queries=sum(r["queries"] for r in rows),
               cpu_s=round(sum(r["cpu_s"] for r in rows), 2), timeouts=sum(r["outcome"] == "abstain_timeout" for r in rows))
    out["by_panel"] = {p: rate([r for r in rows if r["panel"] == p]) for p in sorted({r["panel"] for r in rows})}
    out["by_world"] = {w: rate([r for r in rows if r["world"] == w]) for w in "ABCDEF" if any(r["world"] == w for r in rows)}
    out["by_level"] = {lv: rate([r for r in rows if r["level"] == lv]) for lv in (1, 2, 3, 4)}
    out["by_family"] = {f"{r['world']}.{r['family']}": rate([q for q in rows if q["family"] == r["family"]]) for r in rows}
    out["heldout_CE_family_mean"] = _fam_mean([r for r in rows if r["world"] in "CE"])[0]
    out["silent_by_world"] = {w: sum(r["silent"] for r in rows if r["world"] == w) for w in "ABCDEF"}
    return out


def score():
    plan_ = json.loads((ROOT / "artifacts/agi_eval_plan.json").read_text())
    res = dict(plan=plan_, arms={}, missing={})
    T = {}
    for a in arms_main():
        T[a] = _rows(a)
        res["missing"][a] = len(SD.reduced(plan_["n_main"])) - len(T[a])
        res["arms"][a] = summary(T[a])
    for a in arms_panel():
        key = a if a.startswith("Meta_") else f"{a}@panel"
        T[key] = _rows(key)
        res["missing"][key] = 12 - len(T[key])
        res["arms"][key] = summary(T[key])
    ce = lambda r: r["world"] in "CE"                      # noqa: E731
    prim = {}
    for r in REPS:
        F = T[f"Full_r{r}"]
        row = {}
        for ctrl in ("Scratch", f"Placebo_r{r}", "Init"):
            d = _fam_diff(F, T[ctrl], ce)
            row[ctrl.split("_")[0]] = dict(mean_family_diff=round(sum(d.values()) / len(d), 4) if d else None,
                                           ci95_cluster=_cluster_boot(d, seed=f"agi-boot|{r}|{ctrl}"), by_family=d)
        prim[f"r{r}"] = row
    pooled = {}
    for ctrl in ("Scratch", "Placebo", "Init"):
        d = {}
        for r in REPS:
            c = ctrl if ctrl in ("Scratch", "Init") else f"Placebo_r{r}"
            for k, v in _fam_diff(T[f"Full_r{r}"], T[c], ce).items():
                d.setdefault(k, []).append(v)
        dm = {k: sum(v) / len(v) for k, v in d.items()}
        pooled[ctrl] = dict(mean_family_diff=round(sum(dm.values()) / len(dm), 4) if dm else None,
                            ci95_cluster=_cluster_boot(dm, seed=f"agi-boot|pooled|{ctrl}"))
    crit = dict(
        gain_vs_scratch_pp=None if pooled["Scratch"]["mean_family_diff"] is None else round(100 * pooled["Scratch"]["mean_family_diff"], 1),
        gain_vs_placebo_pp=None if pooled["Placebo"]["mean_family_diff"] is None else round(100 * pooled["Placebo"]["mean_family_diff"], 1),
        reps_positive_vs_both=sum(1 for r in REPS if (prim[f"r{r}"]["Scratch"]["mean_family_diff"] or 0) > 0 and
                                  (prim[f"r{r}"]["Placebo"]["mean_family_diff"] or 0) > 0),
        silent_full_CE=sum(x["silent"] for r in REPS for x in T[f"Full_r{r}"] if ce(x)))
    crit["met"] = bool(crit["gain_vs_scratch_pp"] is not None and crit["gain_vs_scratch_pp"] >= 10 and
                       crit["gain_vs_placebo_pp"] >= 10 and crit["reps_positive_vs_both"] >= 2 and crit["silent_full_CE"] == 0)
    res["primary_CE"] = dict(per_rep=prim, pooled=pooled, criterion=crit)
    # policy transfer vs library reuse (all main-suite tasks, family-clustered)
    allr = lambda r: True                                  # noqa: E731
    dec = {}
    for r in REPS:
        g = {k: _fam_mean(T[f"{k}_r{r}"])[0] for k in ("Full", "RL", "Pol")}
        g["Init"] = _fam_mean(T["Init"])[0]
        e_full, e_rl, e_pol = g["Full"] - g["Init"], g["RL"] - g["Init"], g["Pol"] - g["Init"]
        dec[f"r{r}"] = dict(rates={k: round(v, 4) for k, v in g.items()}, full_minus_init=round(e_full, 4),
                            rl_minus_init=round(e_rl, 4), pol_minus_init=round(e_pol, 4),
                            interaction=round(e_full - e_rl - e_pol, 4))
    res["policy_vs_library"] = dec
    # improver vs improver (12-task panel)
    imp = {}
    for r in REPS:
        imp[f"r{r}"] = {m: dict(solved=sum(x["solved"] for x in T[f"Meta_r{r}_{m}"]), silent=sum(x["silent"] for x in T[f"Meta_r{r}_{m}"]),
                                cpu_s=round(sum(x["cpu_s"] for x in T[f"Meta_r{r}_{m}"]), 2)) for m in ("Mstar", "M0", "Mrand")}
        imp[f"r{r}"]["pre_meta_Full"] = dict(solved=sum(x["solved"] for x in T[f"Full_r{r}@panel"]),
                                             silent=sum(x["silent"] for x in T[f"Full_r{r}@panel"]))
    res["improver"] = imp
    # transfer attribution: L / R items used in solved target episodes, and negative transfer vs Init / Scratch
    att = {}
    for r in REPS:
        F = {x["tid"]: x for x in T[f"Full_r{r}"]}
        used = {}
        for x in F.values():
            if x["solved"]:
                for n in x["used_items"]:
                    used.setdefault(n, []).append(x["tid"])
        neg = [tid for tid, x in F.items() if not x["solved"] and any(y["tid"] == tid and y["solved"] for y in T["Scratch"] + T["Init"])]
        pos = [tid for tid, x in F.items() if x["solved"] and not any(y["tid"] == tid and y["solved"] for y in T["Scratch"] + T["Init"])]
        att[f"r{r}"] = dict(items_used_in_solves=used, solved_by_full_only=pos, lost_vs_init_or_scratch=neg)
    res["attribution"] = att
    res["complete"] = all(v == 0 for v in res["missing"].values())
    save(D / "result.json", res)
    print(json.dumps({k: res[k] for k in ("primary_CE", "policy_vs_library", "improver")}, indent=1, default=list)[:5000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(*sys.argv[2:5])
    else:
        {"freeze_source": freeze_source, "freeze_meta": freeze_meta, "plan": plan, "score": score}[sys.argv[1]]()

"""Phase 10D frozen matched 2x2 (+ DAG localisation) evaluation on 48 one-use out-of-sandbox projects (NOT LOCKED).
  python scripts/agi10d_eval.py freeze [--dev]
  python scripts/agi10d_eval.py run CHUNK N [--dev]     ONE-USE agi10dde/eval -> artifacts/agi10d_eval/rows_cCHUNK.jsonl
  python scripts/agi10d_eval.py score [--dev]
PRE-REGISTERED ARMS (identical procedure, M0, search10d bridge machinery; work 600 executions, wall 4 s per search; r = rep0 / rep1):
  A1     Fixed + L0                    (no learned component; shared by both repetitions)
  A2_r   Learned + L0                  ranker G_L0
  A3_r   Fixed + L0 U L*               library L*_r, fixed guide (bound macros first, capped)
  A4_r   Learned + L0 U L*             ranker G_L* + library L*_r (full wake-sleep)
  A5_r   A4_r + DAG stage-contract localisation (expand only the first failing node)   [bonus diagnostic]
  A4_r@N30 / A4_r@N60                  the learning curve on the 24 held-out compositions (N0 = A1, N3 = A4_r)
Every submission is verified on the project's DECLARED engine (DuckDB / SQLite / Polars / PySpark 4.0.1) on 2 hidden batches;
declared-engine results are cached per (project, spec, engine) inside a chunk (identical submissions are not re-executed).
Rows appended + flushed; a restarted chunk skips written rows (never rerun)."""
import fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase10d import dag10d as D, lineage10d as LD, manifest10d as MD, world10d as W  # noqa: E402
DEV = "--dev" in sys.argv
TR = ROOT / ("artifacts/agi10d_dev/train" if DEV else "artifacts/agi10d_train")
OUT = ROOT / ("artifacts/agi10d_dev/eval" if DEV else "artifacts/agi10d_eval")
FZ = ROOT / ("artifacts/agi10d_dev/freeze.json" if DEV else "artifacts/agi10d_freeze.json")
CODE = ["src/nexus/de_phase10d/" + f for f in ("ir10d.py", "engines10d.py", "legacy10d.py", "world10d.py", "dag10d.py", "search10d.py", "lineage10d.py", "manifest10d.py")] + \
       ["src/nexus/de_phase10c/search10c.py", "src/nexus/de_phase10c/lineage10c.py", "scripts/agi10d_eval.py", "scripts/agi10d_train.py"]


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def manifest():
    return MD.dev_manifest() if DEV else MD.eval_manifest()


def ck_files():
    out = {}
    for r in ("rep0", "rep1"):
        out[f"{r}.final"] = TR / f"{r}.final.json"
        for N in MD.CHECKPOINTS[:2] if not DEV else ():
            out[f"{r}.N{N}"] = TR / f"{r}.N{N}.json"
    return out


def freeze():
    files = {str(f.relative_to(ROOT)): sha(f) for f in ck_files().values() if f.exists()}
    FZ.write_text(json.dumps(dict(files=files, code={f: sha(ROOT / f) for f in CODE}, manifest=manifest(),
                                  N3={r: json.loads((TR / f"{r}.final.json").read_text())["n"] for r in ("rep0", "rep1") if (TR / f"{r}.final.json").exists()}), indent=1))
    print("frozen", files)


def arms():
    A = {"A1": dict(mem=LD.arm_memory(), mode="whole", groups=("ordinary", "heldout"))}
    for tag, f in ck_files().items():
        if not f.exists():
            continue
        m = json.loads(f.read_text())["memory"]
        r, N = tag.split(".")
        L, g = m["de"]["skills"], m.get("guides") or {}
        if N == "final":
            A[f"A2_{r}"] = dict(mem=LD.arm_memory(guide_w=g.get("L0")), mode="whole", groups=("ordinary", "heldout"))
            A[f"A3_{r}"] = dict(mem=LD.arm_memory(skills=L), mode="whole", groups=("ordinary", "heldout"))
            A[f"A4_{r}"] = dict(mem=LD.arm_memory(skills=L, guide_w=g.get("Lstar")), mode="whole", groups=("ordinary", "heldout"))
            A[f"A5_{r}"] = dict(mem=LD.arm_memory(skills=L, guide_w=g.get("Lstar")), mode="localize", groups=("ordinary", "heldout"))
        else:
            A[f"A4_{r}@{N}"] = dict(mem=LD.arm_memory(skills=L, guide_w=g.get("Lstar")), mode="whole", groups=("heldout",))
    return A


def claim_once(key):
    lock = ROOT / "var/agi10d_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10d-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10d-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


_CACHE = {}


def cached_engine(orig):
    def run(self, specs, prescreen=True):
        if prescreen:
            return orig(self, specs, prescreen)
        k = (self.p["pid"], self.engine, json.dumps(specs, sort_keys=True, default=str))
        if k not in _CACHE:
            _CACHE[k] = orig(self, specs, prescreen)
        else:
            self.runs[self.engine] += 1                            # the charged work is the same as an execution
        return _CACHE[k]
    return run


def run(chunk, n):
    chunk, n = int(chunk), int(n)
    fz = json.loads(FZ.read_text())
    for f, h in list(fz["files"].items()) + list(fz["code"].items()):
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if not DEV:
        claim_once(("agi10dde", "eval"))
    D.Inv10d.run = cached_engine(D.Inv10d.run)
    hid_cache = {}
    OUT.mkdir(parents=True, exist_ok=True)
    A = arms()
    names = sorted(A)
    out = OUT / f"rows_c{chunk}.jsonl"
    done = {(x["arm"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in manifest()[chunk::n]:
            try:
                p = W.make_project10d(t, t["seed"], ROOT / "var/agi10d_ws" / ("deveval" if DEV else "eval"))
            except RuntimeError as e:
                fh.write(json.dumps(dict(seed=t["seed"], arm="-", error=str(e)[:100])) + "\n")
                fh.flush()
                continue
            k0 = (t["seed"] * 7) % len(names)
            for name in names[k0:] + names[:k0]:
                a = A[name]
                if (name, t["seed"]) in done or t["group"] not in a["groups"]:
                    continue
                t0 = time.time()
                inv = D.Inv10d(p)
                r = LD.SD.search(inv, a["mem"], LD.WORK, LD.WALL, mode=a["mode"])
                verified = wrong = False
                if r["outcome"] == "submitted":
                    hk = json.dumps(r["specs"], sort_keys=True, default=str)
                    if hk not in hid_cache:
                        hid_cache[hk] = D.verify_hidden(p, r["specs"])
                    verified, wrong = hid_cache[hk]["ok"], not hid_cache[hk]["ok"]
                row = dict(seed=t["seed"], pid=p["pid"], arm=name, group=t["group"], family=t["family"], faults=t["faults"], engine=t["engine"], legacy=t["legacy"],
                           n_tables=p["n_tables"], n_cols=p["n_cols"], outcome=r["outcome"], verified=verified, wrong=wrong, work=r["work"],
                           runs={k: v for k, v in r["runs"].items() if v}, path=[list(e) for e in (r.get("path") or [])], macro_steps=r.get("macro_steps"),
                           via_skill=bool(r.get("via_skill")), events={k: r["events"].get(k, 0) for k in ("expanded", "macro_children", "macro_improvements", "bridges_marked",
                                                                                                     "bridge_expansions", "engine_verify_failed")},
                           row_wall=round(time.time() - t0, 3))
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
            print(p["pid"], flush=True)


def signflip(d, key):
    obs = abs(sum(d))
    if not any(d):
        return 1.0
    r = random.Random(key)
    return round((sum(abs(sum(x if r.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(20000)) + 1) / 20001, 4)


def score():
    rows = [json.loads(l) for f in sorted(OUT.glob("rows_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r.get("arm") != "-"]
    by = {}
    for r in ok:
        by.setdefault(r["arm"], {})[r["seed"]] = r
    res = dict(n_rows=len(ok), build_failures=[r for r in rows if r.get("arm") == "-"], arms={}, contrasts={}, attribution={}, curve={}, forgetting={})
    for a, v in sorted(by.items()):
        vv = list(v.values())
        g = lambda f: f"{sum(x['verified'] for x in vv if f(x))}/{sum(1 for x in vv if f(x))}"  # noqa: E731
        res["arms"][a] = dict(n=len(vv), verified=sum(x["verified"] for x in vv), wrong=sum(x["wrong"] for x in vv), heldout=g(lambda x: x["group"] == "heldout"),
                              ordinary=g(lambda x: x["group"] == "ordinary"), by_engine={e: g(lambda x, e=e: x["engine"] == e) for e in MD.ENGINES},
                              by_legacy={l_: g(lambda x, l_=l_: x["legacy"] == l_) for l_ in MD.LEGACY}, work_heldout=sum(x["work"] for x in vv if x["group"] == "heldout"),
                              work_ordinary=sum(x["work"] for x in vv if x["group"] == "ordinary"), macro_on_verified_path=sum(bool(x["macro_steps"]) and x["verified"] for x in vv),
                              eval_wall=round(sum(x["row_wall"] for x in vv), 1))
    for r in ("rep0", "rep1"):
        for grp in ("heldout", "ordinary"):
            ss = sorted(s for s, x in by.get("A1", {}).items() if x["group"] == grp)
            V = {a: {s for s in ss if by.get(a, {}).get(s, {}).get("verified")} for a in ("A1", f"A2_{r}", f"A3_{r}", f"A4_{r}", f"A5_{r}")}

            def diff(a, b):
                d = [float(s in V[a]) - float(s in V[b]) for s in ss]
                return dict(n=len(d), diff=int(sum(d)), gained=sorted(V[a] - V[b]), lost=sorted(V[b] - V[a]), p_signflip=signflip(d, f"10d|{r}|{a}|{b}|{grp}"))
            res["contrasts"][f"{grp} {r}"] = {"G_learned | L0 (A2 - A1)": diff(f"A2_{r}", "A1"), "G_learned | L* (A4 - A3)": diff(f"A4_{r}", f"A3_{r}"),
                                             "L* | G_fixed (A3 - A1)": diff(f"A3_{r}", "A1"), "L* | G_learned (A4 - A2)": diff(f"A4_{r}", f"A2_{r}"),
                                             "combined (A4 - A1)": diff(f"A4_{r}", "A1"), "localisation (A5 - A4)": diff(f"A5_{r}", f"A4_{r}"),
                                             "interaction": len(V[f"A4_{r}"]) - len(V[f"A3_{r}"]) - len(V[f"A2_{r}"]) + len(V["A1"])}
            a1, a2, a3, a4 = V["A1"], V[f"A2_{r}"], V[f"A3_{r}"], V[f"A4_{r}"]
            res["attribution"][f"{grp} {r}"] = dict(n=len(ss), fixed_L0=len(a1), guidance_alone=sorted(a2 - a1), macros_alone=sorted(a3 - a1),
                                                    only_with_both=sorted(a4 - a1 - a2 - a3), none=sorted(set(ss) - a1 - a2 - a3 - a4), A4_lost=sorted((a1 | a2 | a3) - a4))
        hs = sorted(s for s, x in by.get("A1", {}).items() if x["group"] == "heldout")
        pts = [("N0", "A1")] + [(f"N{N}", f"A4_{r}@N{N}") for N in MD.CHECKPOINTS[:2]] + [("N3", f"A4_{r}")]
        res["curve"][r] = {lab: dict(verified=sum(by[a][s]["verified"] for s in hs if s in by[a]), wrong=sum(by[a][s]["wrong"] for s in hs if s in by[a]),
                                     work=sum(by[a][s]["work"] for s in hs if s in by[a])) if a in by else None for lab, a in pts}
        seq = [{s for s in hs if by[a].get(s, {}).get("verified")} for _, a in pts if a in by]
        res["forgetting"][r] = sorted({s for i, x in enumerate(seq) for y in seq[i + 1:] for s in x - y})
        tw = TR / f"{r}.wake.jsonl"
        w = [json.loads(l) for l in tw.read_text().splitlines()] if tw.exists() else []
        res.setdefault("training", {})[r] = dict(tasks=len(w), verified=sum(x["verified"] for x in w), wrong=sum(x["wrong"] for x in w),
                                                 cost=json.loads((TR / f"{r}.final.json").read_text())["cost"] if (TR / f"{r}.final.json").exists() else None)
    res["eval_wrong_total"] = sum(v["wrong"] for v in res["arms"].values())
    (OUT / "result.json").write_text(json.dumps(res, indent=1, default=str))
    print({a: (v["heldout"], v["ordinary"], v["wrong"], v["macro_on_verified_path"]) for a, v in res["arms"].items()})
    print(json.dumps({k: res[k] for k in ("attribution", "curve", "forgetting", "eval_wrong_total", "training")}, default=str)[:3000])


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dev"]
    {"run": lambda: run(*a[1:]), "score": score, "freeze": freeze}[a[0]]()

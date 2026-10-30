"""Phase 10F one-use evaluation on a FRESH 48-target decoupled draw (NOT LOCKED).
  python scripts/agi10f_eval.py freeze [--dev]
  python scripts/agi10f_eval.py run CHUNK N [--dev]     ONE-USE agi10fde/eval -> artifacts/agi10f_eval/rows_cCHUNK.jsonl
  python scripts/agi10f_eval.py score [--dev]
PRE-REGISTERED ARMS (docs/NEXUS_PHASE10F_PROTOCOL.md; identical procedure, M0, search10e bridge machinery, dag10f acceptance;
work 600 executions, wall 4 s per search; r = rep0 / rep1; L*_r, G_L0_r, G_Lstar_r, G_atomic_r from rep{r}.subgroup.final.json):
  A1        fixed guide   + L0 (split dedup)                         shared by both streams
  A2_r      G_L0_r        + L0
  A3_r      fixed guide   + L0 U L*_r
  A4_r      G_Lstar_r     + L0 U L*_r                                 (full wake-sleep)
  A4f_r     G_Lstar_r     + L0 U (L*_r minus every macro containing add_partition)   = A4_frozen_no_replay: the SAME ranker as A4,
            only the replay macro(s) removed from the executable action set
  Bf        fixed guide   + ATOMIC dedup substrate (atomic10f)        = B_atomic_fixed, shared by both streams
  Bl_r      G_atomic_r    + ATOMIC dedup substrate                    = B_atomic_learned
SCORING (post-run, analysis only): every contrast and table uses the targets on which ALL arms have a row (a row a budget
cap prevented is MISSING, never counted as a failure); coverage is reported.
Every submission is verified on the project's DECLARED engine (DuckDB / SQLite / Polars / PySpark 4.0.1) on 2 hidden batches.
Shared pure caches (lineage10f change 5) across the arms of one target: parsed workspace, interpreter / domain memos, declared-engine
and hidden results; every execution is still charged to the arm's work counter. Rows appended + flushed; a restarted chunk skips
written rows (never rerun). PRIORITY (pre-registered, budget): each chunk runs its held-out targets before its ordinary targets,
and every arm of a target before the next target; a chunk stopped by its cap leaves the remaining rows MISSING (reported). SHORTCUT AUDIT: a verified row whose dedup on the item relation orders by the quantity column."""
import fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase10f import atomic10f as AT, lineage10f as LF, manifest10f as MF, world10f as W  # noqa: E402
DEV = "--dev" in sys.argv
TR = ROOT / ("artifacts/agi10f_dev/train" if DEV else "artifacts/agi10f_train")
OUT = ROOT / ("artifacts/agi10f_dev/eval" if DEV else "artifacts/agi10f_eval")
FZ = ROOT / ("artifacts/agi10f_dev/freeze.json" if DEV else "artifacts/agi10f_freeze.json")
CODE = ["src/nexus/de_phase10f/" + f for f in ("abstract10f.py", "atomic10f.py", "dag10f.py", "lineage10f.py", "manifest10f.py", "world10f.py")] + \
       ["src/nexus/de_phase10e/" + f for f in ("dag10e.py", "search10e.py", "lineage10e.py", "manifest10e.py")] + \
       ["src/nexus/de_phase10d/" + f for f in ("ir10d.py", "engines10d.py", "legacy10d.py", "world10d.py", "dag10d.py", "manifest10d.py")] + \
       ["src/nexus/de_phase10c/search10c.py", "src/nexus/de_phase10c/lineage10c.py", "scripts/agi10f_eval.py", "scripts/agi10f_train.py"]
REPS = ("rep0", "rep1")


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def manifest():
    return MF.dev_manifest() if DEV else MF.eval_manifest()


def ck(r, rule="subgroup"):
    return TR / f"{r}.{rule}.final.json"


def freeze():
    files = {str(ck(r, rule).relative_to(ROOT)): sha(ck(r, rule)) for r in REPS for rule in ("subgroup", "current") if ck(r, rule).exists()}
    FZ.write_text(json.dumps(dict(files=files, code={f: sha(ROOT / f) for f in CODE}, manifest=manifest(),
                                  N={r: json.loads(ck(r).read_text())["n"] for r in REPS if ck(r).exists()}), indent=1))
    print("frozen", files)


def is_replay(sk):
    return any(e[0] == "add_partition" for e in sk["edits"])


def arms():
    A = {"A1": dict(mem=LF.arm_memory(), atomic=False), "Bf": dict(mem=LF.arm_memory(), atomic=True)}
    for r in REPS:
        if not ck(r).exists():
            continue
        m = json.loads(ck(r).read_text())["memory"]
        L, g = m["de"]["skills"], m.get("guides") or {}
        A[f"A2_{r}"] = dict(mem=LF.arm_memory(guide_w=g.get("L0")), atomic=False)
        A[f"A3_{r}"] = dict(mem=LF.arm_memory(skills=L), atomic=False)
        A[f"A4_{r}"] = dict(mem=LF.arm_memory(skills=L, guide_w=g.get("Lstar")), atomic=False)
        A[f"A4f_{r}"] = dict(mem=LF.arm_memory(skills={k: v for k, v in L.items() if not is_replay(v)}, guide_w=g.get("Lstar")), atomic=False)
        A[f"Bl_{r}"] = dict(mem=LF.arm_memory(guide_w=g.get("atomic")), atomic=True)
    return A


def claim_once(key):
    lock = ROOT / "var/agi10f_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10f-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10f-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def dedup_order_cols(path, p):
    """Order columns of every item-relation dedup on the path (set_dedup params: rel|key|order|dir)."""
    return [e[2].split("|")[2] for e in path if e[1] == "set_dedup" and e[2].startswith("stg_order_items|")]


def run(chunk, n):
    chunk, n = int(chunk), int(n)
    fz = json.loads(FZ.read_text())
    for f, h in list(fz["files"].items()) + list(fz["code"].items()):
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if not DEV:
        claim_once(("agi10fde", "eval"))
    OUT.mkdir(parents=True, exist_ok=True)
    A = arms()
    names = sorted(A)
    out = OUT / f"rows_c{chunk}.jsonl"
    done = {(x["arm"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in sorted(manifest()[chunk::n], key=lambda t: t["group"] != "heldout"):     # pre-registered priority: held-out first
            try:
                p = W.make_project10d(t, t["seed"], ROOT / "var/agi10f_ws" / ("deveval" if DEV else "eval"))
            except RuntimeError as e:
                fh.write(json.dumps(dict(seed=t["seed"], arm="-", error=str(e)[:100])) + "\n")
                fh.flush()
                continue
            k0 = (t["seed"] * 7) % len(names)
            for name in names[k0:] + names[:k0]:
                a = A[name]
                if (name, t["seed"]) in done:
                    continue
                t0 = time.time()
                if a["atomic"]:
                    with AT.atomic():
                        inv, r, verified, wrong = LF.investigate(p, a["mem"])
                else:
                    inv, r, verified, wrong = LF.investigate(p, a["mem"])
                path = [list(e) for e in (r.get("path") or [])]
                row = dict(seed=t["seed"], pid=p["pid"], arm=name, group=t["group"], family=t["family"], faults=t["faults"], engine=t["engine"], legacy=t["legacy"],
                           n_tables=p["n_tables"], n_cols=p["n_cols"], outcome=r["outcome"], verified=verified, wrong=wrong, work=r["work"],
                           runs={k: v for k, v in r["runs"].items() if v}, path=path, macro_steps=r.get("macro_steps"), via_skill=bool(r.get("via_skill")),
                           item_dedup_order=dedup_order_cols(path, p), qty_col=p["names"]["qty"], seq_col=p["names"]["seq"],
                           wall_bound=r["outcome"] == "none" and r["work"] < LF.WORK,
                           events={k: r["events"].get(k, 0) for k in ("expanded", "macro_children", "macro_improvements", "bridges_marked", "bridge_expansions", "engine_verify_failed")},
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


def acquisition():
    """Per rule x stream x checkpoint: is a valid (unique_key, arrival_sequence) replay macro in the library?"""
    out = {}
    for r in REPS:
        for rule in ("current", "subgroup"):
            row = {}
            Ns = MF.CHECKPOINTS if not DEV else sorted({int(f.name.split(".N")[1].split(".")[0]) for f in TR.glob(f"{r}.{rule}.N*.json")})
            for N in Ns:
                f = TR / f"{r}.{rule}.N{N}.json"
                if not f.exists():
                    row[str(N)] = None
                    continue
                skills = json.loads(f.read_text())["memory"]["de"]["skills"]
                valid = [sid for sid, sk in skills.items() if is_replay(sk) and "ckey" in sk["edits"][0][2][1]
                         and any(e[0] == "set_dedup" and "arrival" in e[3][1] for e in sk["edits"])]
                row[str(N)] = dict(valid_replay_macro=valid, any_replay_macro=[sid for sid, sk in skills.items() if is_replay(sk)])
            out[f"{r}.{rule}"] = row
    return out


def score():
    rows = [json.loads(l) for f in sorted(OUT.glob("rows_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r.get("arm") != "-"]
    by = {}
    for r in ok:
        by.setdefault(r["arm"], {})[r["seed"]] = r
    res = dict(n_rows=len(ok), build_failures=[r for r in rows if r.get("arm") == "-"], arms={}, contrasts={}, attribution={}, replay_macro_paths={})
    for a, v in sorted(by.items()):
        vv = list(v.values())
        g = lambda f: f"{sum(x['verified'] for x in vv if f(x))}/{sum(1 for x in vv if f(x))}"  # noqa: E731
        res["arms"][a] = dict(n=len(vv), verified=sum(x["verified"] for x in vv), wrong=sum(x["wrong"] for x in vv), heldout=g(lambda x: x["group"] == "heldout"),
                              ordinary=g(lambda x: x["group"] == "ordinary"), by_engine={e: g(lambda x, e=e: x["engine"] == e) for e in MF.ENGINES},
                              work_heldout=sum(x["work"] for x in vv if x["group"] == "heldout"), work_ordinary=sum(x["work"] for x in vv if x["group"] == "ordinary"),
                              macro_on_verified_path=sum(bool(x["macro_steps"]) and x["verified"] for x in vv), wall_bound=sum(x["wall_bound"] for x in vv),
                              shortcut_qty_order=sorted(x["seed"] for x in vv if x["verified"] and x["qty_col"] in x["item_dedup_order"]),
                              shortcut_qty_order_submitted=sorted(x["seed"] for x in vv if x["outcome"] == "submitted" and x["qty_col"] in x["item_dedup_order"]),
                              eval_wall=round(sum(x["row_wall"] for x in vv), 1))
    V = lambda a, ss: {s for s in ss if by.get(a, {}).get(s, {}).get("verified")}             # noqa: E731
    for grp in ("heldout", "ordinary"):
        ss = sorted(s for s, x in by.get("A1", {}).items() if x["group"] == grp and all(s in by.get(a, {}) for a in by))   # complete targets only
        res.setdefault("coverage", {})[grp] = dict(complete_targets=len(ss), targets_with_any_row=len({x["seed"] for x in ok if x["group"] == grp}),
                                                   missing_rows=sum(1 for m in manifest() if m["group"] == grp for a in by if m["seed"] not in by[a]))
        for r in REPS:
            def diff(a, b):
                d = [float(s in V(a, ss)) - float(s in V(b, ss)) for s in ss]
                return dict(n=len(d), diff=int(sum(d)), gained=sorted(V(a, ss) - V(b, ss)), lost=sorted(V(b, ss) - V(a, ss)), p_signflip=signflip(d, f"10f|{r}|{a}|{b}|{grp}"))
            res["contrasts"][f"{grp} {r}"] = {
                "macro execution | frozen G_Lstar (A4 - A4f)": diff(f"A4_{r}", f"A4f_{r}"),
                "L* | G_fixed (A3 - A1)": diff(f"A3_{r}", "A1"), "L* + retrained guide (A4 - A2)": diff(f"A4_{r}", f"A2_{r}"),
                "G_learned | L0 (A2 - A1)": diff(f"A2_{r}", "A1"), "G_learned | L* (A4 - A3)": diff(f"A4_{r}", f"A3_{r}"),
                "split+macro vs atomic, learned (A4 - Bl)": diff(f"A4_{r}", f"Bl_{r}"), "split+macro vs atomic, fixed (A3 - Bf)": diff(f"A3_{r}", "Bf"),
                "atomic vs split, learned L0 (Bl - A2)": diff(f"Bl_{r}", f"A2_{r}"), "atomic vs split, fixed L0 (Bf - A1)": diff("Bf", "A1")}
            a4, a4f, a2 = V(f"A4_{r}", ss), V(f"A4f_{r}", ss), V(f"A2_{r}", ss)
            rmac = {sid for sid, sk in json.loads(ck(r).read_text())["memory"]["de"]["skills"].items() if is_replay(sk)} if ck(r).exists() else set()
            res["attribution"][f"{grp} {r}"] = dict(A4_not_A4f=sorted(a4 - a4f), A4f_not_A4=sorted(a4f - a4),
                                                    A4_not_A4f_with_replay_macro_on_path=sorted(s for s in a4 - a4f if any(m[2] in rmac for m in (by[f"A4_{r}"][s]["macro_steps"] or []))),
                                                    A4_not_A2=sorted(a4 - a2))
        res["contrasts"][f"{grp} unconditional"] = {a: dict(per_stream={r: len(V(f"{a}_{r}" if a not in ("A1", "Bf") else a, ss)) for r in REPS},
                                                            both_streams=len(set.intersection(*[V(f"{a}_{r}" if a not in ("A1", "Bf") else a, ss) for r in REPS])),
                                                            either_stream=len(set.union(*[V(f"{a}_{r}" if a not in ("A1", "Bf") else a, ss) for r in REPS])), n=len(ss))
                                                    for a in ("A1", "A2", "A3", "A4", "A4f", "Bf", "Bl")}
    for r in REPS:
        if not ck(r).exists():
            continue
        skills = json.loads(ck(r).read_text())["memory"]["de"]["skills"]
        rmac = {sid for sid, sk in skills.items() if is_replay(sk)}
        res["replay_macro_paths"][r] = dict(macros={sid: skills[sid]["canonical"] for sid in sorted(rmac)},
                                            **{a: sorted(x["seed"] for x in by.get(f"{a}_{r}", {}).values() if x["verified"] and any(m[2] in rmac for m in (x["macro_steps"] or [])))
                                               for a in ("A3", "A4")})
    res["acquisition"] = acquisition()
    res["training"] = {}
    for r in REPS:
        for rule in ("current", "subgroup"):
            tw = TR / f"{r}.{rule}.wake.jsonl"
            w = [json.loads(l) for l in tw.read_text().splitlines()] if tw.exists() else []
            res["training"][f"{r}.{rule}"] = dict(tasks=len(w), verified=sum(x["verified"] for x in w), wrong=sum(x["wrong"] for x in w),
                                                  wrong_tasks=[(x["seed"], x["family"], x["path"]) for x in w if x["wrong"]], wall_bound=sum(x.get("wall_bound", False) for x in w),
                                                  replay_wake_verified=sum(x["verified"] for x in w if x["family"] == "S_replay"), replay_wake=sum(x["family"] == "S_replay" for x in w))
    res["eval_wrong_total"] = sum(v["wrong"] for v in res["arms"].values())
    res["eval_shortcut_qty_order_total"] = sum(len(v["shortcut_qty_order"]) for v in res["arms"].values())
    (OUT / "result.json").write_text(json.dumps(res, indent=1, default=str))
    print({a: (v["heldout"], v["ordinary"], v["wrong"], v["macro_on_verified_path"], len(v["shortcut_qty_order"])) for a, v in res["arms"].items()})
    print(json.dumps({k: res[k] for k in ("acquisition", "attribution", "eval_wrong_total", "eval_shortcut_qty_order_total", "training")}, default=str)[:4000])


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dev"]
    {"run": lambda: run(*a[1:]), "score": score, "freeze": freeze}[a[0]]()

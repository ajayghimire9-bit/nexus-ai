"""Phase 10C (REVISED) frozen matched 2x2 evaluation on two separate one-use draws (NOT LOCKED).
  python scripts/agi10c_eval.py freeze [--dev]
  python scripts/agi10c_eval.py run DRAW CHUNK N [--dev]   DRAW A (stream rep0) | B (stream rep1) -> artifacts/agi10c_eval/rows_DRAW_cCHUNK.jsonl
  python scripts/agi10c_eval.py score [--dev]
PRE-REGISTERED ARMS (identical fixed trust = Phase 10B rep0 final trust, F0, M0, search10c bridge machinery and the shared
verifier fix fixes10c; work budget 1,500 executions and wall cap 4 s per search; r = the draw's stream):
  A1        Fixed + L0         (no learned component; runs on both draws)
  A2_r      Learned + L0       ranker G_L0 of stream r's final checkpoint, no library
  A3_r      Fixed + L0 U L*    fixed guide (bound macros first, capped), library L*_r
  A4_r      Learned + L0 U L*  ranker G_L* (traces rewritten over L0 U L*), library L*_r
  A4_r@N15 / A4_r@N30          the learning curve on the 10 withheld targets (N0 = A1, N3 = A4_r)
One-use agi10cde/eval (96000-96099) is claimed once by the first run; only 96000-96015 (A) and 96050-96065 (B) are used.
Rows appended + flushed; a restarted chunk skips rows already written (never rerun)."""
import copy, fcntl, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase10 import procedure10 as PR10  # noqa: E402
from nexus.de_phase10c import lineage10c as LC, manifest10c as MC  # noqa: E402
import agi10c_train as TRN  # noqa: E402
DEV = "--dev" in sys.argv
TR = ROOT / ("artifacts/agi10c_dev/train" if DEV else "artifacts/agi10c_train")
D = ROOT / ("artifacts/agi10c_dev/eval" if DEV else "artifacts/agi10c_eval")
FZ = ROOT / ("artifacts/agi10c_dev/freeze.json" if DEV else "artifacts/agi10c_freeze.json")
CODE = ["src/nexus/de_phase10c/search10c.py", "src/nexus/de_phase10c/lineage10c.py", "src/nexus/de_phase10c/manifest10c.py", "src/nexus/de_phase10c/rng10c.py",
        "src/nexus/de_phase10c/fixes10c.py", "src/nexus/de_phase10b/fixes10b.py", "src/nexus/de_phase10/guide10.py", "src/nexus/de_phase10/procedure10.py",
        "scripts/agi10c_eval.py", "scripts/agi10c_train.py"]
STREAM = {"A": "rep0", "B": "rep1"}


def sha(f):
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def manifest(draw):
    return MC.dev_draw(draw) if DEV else MC.draw_manifest(draw)


def ck_files(r):
    out = {"final": TR / f"{r}.final.json"}
    for N in MC.CHECKPOINTS[:2]:
        if (TR / f"{r}.N{N}.json").exists():
            out[f"N{N}"] = TR / f"{r}.N{N}.json"
    return out


def freeze():
    files = {str(f.relative_to(ROOT)): sha(f) for r in STREAM.values() for f in ck_files(r).values() if f.exists()}
    FZ.write_text(json.dumps(dict(files=files, code={f: sha(ROOT / f) for f in CODE}, trust=TRN.fixed_trust()[1], draws={d: manifest(d) for d in STREAM},
                                  N3={r: json.loads((TR / f"{r}.final.json").read_text())["n"] for r in STREAM.values() if (TR / f"{r}.final.json").exists()}), indent=1))
    print("frozen", files)


def arms(draw):
    trust = TRN.fixed_trust()[0]
    r = STREAM[draw]
    A = {"A1": dict(mem=LC.arm_memory(trust), groups=("ordinary", "heldout"))}
    for tag, f in ck_files(r).items():
        if not f.exists():
            continue
        m = json.loads(f.read_text())["memory"]
        L, g = m["de"]["skills"], m.get("guides") or {}
        if tag == "final":
            A[f"A2_{r}"] = dict(mem=LC.arm_memory(trust, guide_w=g.get("L0")), groups=("ordinary", "heldout"))
            A[f"A3_{r}"] = dict(mem=LC.arm_memory(trust, skills=L), groups=("ordinary", "heldout"))
            A[f"A4_{r}"] = dict(mem=LC.arm_memory(trust, skills=L, guide_w=g.get("Lstar")), groups=("ordinary", "heldout"))
        else:
            A[f"A4_{r}@{tag}"] = dict(mem=LC.arm_memory(trust, skills=L, guide_w=g.get("Lstar")), groups=("heldout",))
    return A


def claim_once(key):
    lock = ROOT / "var/agi10c_claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if not any(tuple(x["key"]) == key for x in R._spent() if "override" not in x):
                R.claim(*key, list(R.REGISTRY[key]), run_id="agi10c-eval")
            elif not any(tuple(x["key"]) == key and x.get("run_id") == "agi10c-eval" for x in R._spent()):
                raise SystemExit(f"{key} was claimed by another run")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(draw, chunk, n):
    chunk, n = int(chunk), int(n)
    fz = json.loads(FZ.read_text())
    for f, h in list(fz["files"].items()) + list(fz["code"].items()):
        if sha(ROOT / f) != h:
            raise SystemExit(f"differs from the freeze: {f}")
    if not DEV:
        claim_once(("agi10cde", "eval"))
    D.mkdir(parents=True, exist_ok=True)
    A = arms(draw)
    names = sorted(A)
    out = D / f"rows_{draw}_c{chunk}.jsonl"
    done = {(x["arm"], x["seed"]) for x in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with open(out, "a") as fh:
        for t in manifest(draw)[chunk::n]:
            try:
                p = LC.build(t, t["seed"], ROOT / "var/agi10c_ws" / ("deveval" if DEV else "eval"))
            except RuntimeError as e:
                fh.write(json.dumps(dict(seed=t["seed"], draw=draw, arm="-", error=str(e)[:100])) + "\n")
                fh.flush()
                continue
            sf = [st["faults"] for st in p["stages"]]
            k0 = (t["seed"] * 7) % len(names)
            for name in names[k0:] + names[:k0]:
                a = A[name]
                if (name, t["seed"]) in done or t["group"] not in a["groups"]:
                    continue
                t0 = time.time()
                st = PR10.investigate(p, LC.Live(LC.WORK, LC.WALL), copy.deepcopy(a["mem"]), PR10.F0, {})
                o = PR10.outcome(p, st)
                cand = st.cand or {}
                row = dict(draw=draw, seed=t["seed"], pid=p["pid"], arm=name, group=t["group"], family=t["family"], n_stages=len(p["stages"]), stage_faults=sf,
                           withheld_pairs=MC.withheld_pairs(sf), decision=o["decision"], verified=o["verified"], wrong=o["wrong"], reason=st.decision.get("reason"),
                           reachable=bool(st.has_candidate), work=st.cost["work"], questions=st.cost["questions"], cost_s=round(PR10.cost_s(st.cost), 4),
                           via_skill=bool(cand.get("via_skill")), macro_steps=cand.get("macro_steps"), path_len=len(cand.get("path") or []),
                           events={k: v for k, v in (cand.get("events") or {}).items() if k in ("macro_children", "macro_improvements", "bridges_marked", "bridge_expansions", "expanded")},
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
    rows = [json.loads(l) for f in sorted(D.glob("rows_*_c*.jsonl")) for l in f.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r.get("arm") != "-"]
    res = dict(n_rows=len(ok), build_failures=[r for r in rows if r.get("arm") == "-"], draws={})
    for draw, r in STREAM.items():
        by = {}
        for x in ok:
            if x["draw"] == draw:
                by.setdefault(x["arm"], {})[x["seed"]] = x
        if not by:
            continue
        out = dict(stream=r, arms={}, contrasts={}, attribution={}, targets={})
        for a, v in sorted(by.items()):
            vv = list(v.values())
            g = lambda f: f"{sum(x['verified'] for x in vv if f(x))}/{sum(1 for x in vv if f(x))}"  # noqa: E731
            out["arms"][a] = dict(n=len(vv), verified=sum(x["verified"] for x in vv), wrong=sum(x["wrong"] for x in vv), withheld=g(lambda x: x["group"] == "heldout"),
                                  ordinary=g(lambda x: x["group"] == "ordinary"), work_withheld=sum(x["work"] for x in vv if x["group"] == "heldout"),
                                  work_ordinary=sum(x["work"] for x in vv if x["group"] == "ordinary"),
                                  macro_on_verified_path=sum(bool(x["macro_steps"]) and x["verified"] for x in vv), eval_wall=round(sum(x["row_wall"] for x in vv), 1))
        for grp in ("heldout", "ordinary"):
            ss = sorted(s for s, x in by["A1"].items() if x["group"] == grp)
            V = {a: {s for s in ss if by.get(a, {}).get(s, {}).get("verified")} for a in ("A1", f"A2_{r}", f"A3_{r}", f"A4_{r}")}

            def diff(a, b):
                d = [float(s in V[a]) - float(s in V[b]) for s in ss]
                return dict(n=len(d), diff=int(sum(d)), gained=sorted(V[a] - V[b]), lost=sorted(V[b] - V[a]), p_signflip=signflip(d, f"10c|{draw}|{a}|{b}|{grp}"))
            out["contrasts"][grp] = {"G_learned | L0 (A2 - A1)": diff(f"A2_{r}", "A1"), "G_learned | L* (A4 - A3)": diff(f"A4_{r}", f"A3_{r}"),
                                     "L* | G_fixed (A3 - A1)": diff(f"A3_{r}", "A1"), "L* | G_learned (A4 - A2)": diff(f"A4_{r}", f"A2_{r}"),
                                     "combined (A4 - A1)": diff(f"A4_{r}", "A1"),
                                     "interaction (A4 - A3 - A2 + A1)": len(V[f"A4_{r}"]) - len(V[f"A3_{r}"]) - len(V[f"A2_{r}"]) + len(V["A1"])}
            a1, a2, a3, a4 = V["A1"], V[f"A2_{r}"], V[f"A3_{r}"], V[f"A4_{r}"]
            out["attribution"][grp] = dict(n=len(ss), fixed_L0=len(a1), not_A1_but_guidance_alone=sorted((a2 - a1)), not_A1_but_macros_alone=sorted((a3 - a1)),
                                           only_with_both=sorted(a4 - a1 - a2 - a3), solved_by_none=sorted(set(ss) - a1 - a2 - a3 - a4),
                                           A4_lost_vs_any=sorted((a1 | a2 | a3) - a4))
        hs = sorted(s for s, x in by["A1"].items() if x["group"] == "heldout")
        pts = [("N0", "A1")] + [(f"N{N}", f"A4_{r}@N{N}") for N in MC.CHECKPOINTS[:2]] + [("N3", f"A4_{r}")]
        out["curve_withheld"] = {lab: dict(verified=sum(by[a][s]["verified"] for s in hs if s in by[a]), wrong=sum(by[a][s]["wrong"] for s in hs if s in by[a]),
                                           eval_work=sum(by[a][s]["work"] for s in hs if s in by[a])) if a in by else None for lab, a in pts}
        seq = [{s for s in hs if by[a].get(s, {}).get("verified")} for _, a in pts if a in by]
        out["forgetting_withheld"] = sorted({s for i, x in enumerate(seq) for y in seq[i + 1:] for s in x - y})
        out["targets"] = {s: dict(family=x["family"], group=x["group"], withheld_pairs=x["withheld_pairs"], stage_faults=x["stage_faults"]) for s, x in by["A1"].items()}
        tr = TR / f"{r}.wake.jsonl"
        w = [json.loads(l) for l in tr.read_text().splitlines()] if tr.exists() else []
        cps = {c["N"]: c["cost"] for c in map(json.loads, (TR / f"{r}.checkpoints.jsonl").read_text().splitlines())} if (TR / f"{r}.checkpoints.jsonl").exists() else {}
        out["training"] = dict(tasks=len(w), verified=sum(x["verified"] for x in w), wrong=sum(x["wrong"] for x in w), wrong_projects=[x["project"] for x in w if x["wrong"]],
                               cost_at_checkpoints=cps, final_cost=json.loads((TR / f"{r}.final.json").read_text())["cost"] if (TR / f"{r}.final.json").exists() else None)
        res["draws"][draw] = out
    res["eval_wrong_total"] = sum(a["wrong"] for d in res["draws"].values() for a in d["arms"].values())
    res["training_wrong_total"] = sum(d["training"]["wrong"] for d in res["draws"].values())
    (D / "result.json").write_text(json.dumps(res, indent=1, default=str))
    for draw, d in res["draws"].items():
        print(draw, {a: (v["withheld"], v["ordinary"], v["wrong"], v["macro_on_verified_path"]) for a, v in d["arms"].items()})
        print(" attribution", json.dumps(d["attribution"]), "\n curve", d["curve_withheld"], "\n training", {k: v for k, v in d["training"].items() if k != "cost_at_checkpoints"})
    print("eval wrong", res["eval_wrong_total"], "training wrong", res["training_wrong_total"])


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dev"]
    {"run": lambda: run(*a[1:]), "score": score, "freeze": freeze}[a[0]]()

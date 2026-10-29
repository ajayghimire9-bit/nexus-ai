"""Phase 2 Stage 1 development checks (NOT LOCKED; agi2/dev seeds).
  python scripts/agi2_dev.py untouched     generator self-check of C5, C6, E5, E6: determinism, reference passes its own
                                           verifier, constants fail, non-degenerate - NO learner, no search, no outcome
  python scripts/agi2_dev.py scratch       strong-scratch tuning on SOURCE-world dev tasks only (A, B, D, F; 2 per family):
                                           candidate scratch configurations, the best (solves, then CPU) is frozen as Scratch
  python scripts/agi2_dev.py timing        per-episode overhead on source-world dev tasks (for the evaluation plan)
  python scripts/agi2_dev.py solve N       Init learner on N dev tasks per source-world family (smoke)"""
import json, random, sys, time
from pathlib import Path
from nexus.campaign2 import seeds as SD, agent_loop as AL, improver as I, state as ST
from nexus.campaign2.worlds2 import make_task2, UNTOUCHED
from nexus.campaign.worlds import verify, FAMILIES
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi2_dev"
DEV = SD.RANGES[("agi2", "dev")]

SCRATCH = {"pi0_lazy": dict(prim=2, leaf=1, lam=99), "pi0_lam6": dict(prim=2, leaf=1, lam=6),
           "uniform1": dict(prim=1, leaf=1, lam=99), "prim3": dict(prim=3, leaf=1, lam=99)}


def scratch_state(cfg):
    st = ST.empty_state(I.M0)
    st["pi"]["costs"] = {k: (cfg["leaf"] if (k in ("x", "a") or k.startswith("c:")) else cfg["prim"]) for k in st["pi"]["costs"]}
    if cfg["leaf"] == 1 and cfg["prim"] == 2:
        st["pi"]["costs"] = ST.pi0()["costs"]
    st["pi"]["lam_max"] = cfg["lam"]
    return st


def save(name, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str))
    tmp.replace(p)


def untouched():
    rows, bad = [], []
    for i, (w, f) in enumerate(UNTOUCHED):
        for lv in (1, 2, 3, 4):
            s = DEV.start + 100 + 10 * i + lv
            a = make_task2(w, f, lv, s, "untouched", SD.partners_for(w, f, "untouched"))
            b = make_task2(w, f, lv, s, "untouched", SD.partners_for(w, f, "untouched"))
            det = [a.ref(x) for x in a.hidden_x] == [b.ref(x) for x in b.hidden_x]
            ok = verify(a, a.ref)["ok"]
            const = verify(a, lambda x: 0)["ok"] or verify(a, lambda x: ())["ok"]
            r = dict(tid=a.tid, deterministic=det, reference_passes=ok, constant_passes=const, n_train=len(a.train_x))
            rows.append(r)
            if not det or not ok or const:
                bad.append(r)
    save("untouched_check", dict(rows=rows, bad=bad, note="generator self-check only; descriptors / outcomes not inspected"))
    print("untouched generator checks", len(rows), "bad", len(bad))
    return 1 if bad else 0


def _dev_tasks(off, per):
    out, k = [], 0
    for w in ("A", "B", "D", "F"):
        for f in FAMILIES[w]:
            for j in range(per):
                s = DEV.start + off + k
                k += 1
                out.append(AL.task_of(w, f, j % 4 + 1, s))
    return out


def scratch():
    tasks = _dev_tasks(200, 2)
    res = {}
    for name, cfg in SCRATCH.items():
        st = scratch_state(cfg)
        rs = [AL.safe_episode(t, st) for t in tasks]
        res[name] = dict(cfg=cfg, solved=sum(r["solved"] for r in rs), silent=sum(r["silent"] for r in rs),
                         cpu=round(sum(r["cpu_s"] for r in rs), 2), solved_tids=[r["tid"] for r in rs if r["solved"]])
        print(name, res[name]["solved"], "/", len(tasks), "silent", res[name]["silent"], flush=True)
    best = max(res, key=lambda k: (res[k]["solved"], -res[k]["silent"], -res[k]["cpu"]))
    save("scratch_tuning", dict(n_tasks=len(tasks), results=res, chosen=best, rule="max solves, then fewer silent, then less CPU"))
    print("chosen", best)


def timing():
    st = ST.empty_state(I.M0)
    over = []
    for t in _dev_tasks(600, 2):
        c0 = time.process_time()
        t2 = AL.task_of(t.world, t.family, t.level, t.seed)
        r = AL.safe_episode(t2, st, want_partials=True)
        over.append(time.process_time() - c0 - r["cpu_s"])
    doc = dict(n=len(over), overhead_mean=round(sum(over) / len(over), 4), overhead_max=round(max(over), 4))
    save("timing", doc)
    print(doc)


if __name__ == "__main__":
    sys.exit({"untouched": untouched, "scratch": scratch, "timing": timing}[sys.argv[1]](*sys.argv[2:]) or 0)

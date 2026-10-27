"""Wave 41 Track 1 (NOT LOCKED): unfamiliar compositions and internal hold-out folds. Leave-one-domain-out over the 4 program
domains (Wave 39/40 protocol): sources = SOURCE mechanisms of the other 3 domains (2 instances each), solved with the Flat
configuration (metered: extra curriculum); every arm's learned objects (Repr counts, routing, compiled skills) come from those
certified programs (metered: mandatory fit). Targets = all tasks of the held-out domain, labelled (evaluator-only)
  familiar   : a SOURCE mechanism (seen in other domains as a source mechanism type) on a new surface
  held_out   : a withheld mechanism
  novel_composition : the teacher's operator sequence matches no certified source program (the Wave 38 definition).
Arms: w41_common.ARMS; the two growing arms also learn online over the fold's targets (shadow vault, rent). Budget 4M executions;
curves at 0.25x-2x of 2M. --split dev | confirm (wave41/confirm_lodo, one-use, claimed whole). Resumable per fold."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w41_common as C
CAP2 = 4_000_000


def run_fold(ev, seed, h, arms):
    from nexus import w38_domains as D, w38_learn as K
    others = tuple(d for d in D.DOMAINS if d != h)
    src = D.stream(f"{seed}:src:{h}", others, "source", 2)
    srows, progs, sigs = C.learn_sources(ev, src, f"{seed}:{h}", CAP2)
    tpls = {tuple(t["op"] for t in p) for p in progs}
    tgt = D.stream(f"{seed}:tgt:{h}", (h,), "all", 2)
    out = {"source": dict(n=len(src), certified=len(progs), work=sum(r["work"] for r in srows),
                          wrong=sum(r["wrong"] for r in srows), work_by_task=[r["work"] for r in srows],
                          mech_by_task=[[t["domain"], t["mechanism"]] for t in src],
                          cert_by_task=[bool(r.get("certified")) for r in srows]),
           "fit_instr": {}, "learn_instr": {}, "skills": {}, "arms": {}}
    for arm in arms:
        ch = ev.child()
        fit = ev.call(ch, {"cmd": "reset", "cfg": C.arm_cfg(arm, progs, sigs, f"{seed}:{h}")})
        out["fit_instr"][arm], learn, rows = fit["_instr"], 0, []
        for j, t in enumerate(tgt):
            depth = len(t["teacher"])
            r = ev.solve(ch, t, depth, f"{seed}:{h}:t{j}", budget=CAP2)
            if arm in C.GROWS and r.get("certified"):
                u = ev.call(ch, C.update_job(r, t, depth)); learn += u["_instr"]
            r["category"] = "familiar" if t["source"] else "held_out"
            r["novel_composition"] = tuple(x["op"] for x in t["teacher"]) not in tpls
            for kk in ("candidate", "final_public", "snaps", "record"):
                r.pop(kk, None)
            rows.append(r)
        st = ev.call(ch, {"cmd": "state"})["state"]
        out["skills"][arm] = dict(start=fit.get("skills", 0),
                                  end=sum(1 for _, v in (st["lib"] or {}).get("skills", []) if v["active"]) if st["lib"] else 0,
                                  log=(st["lib"] or {}).get("log", []) if st["lib"] else [])
        ch.close()
        out["learn_instr"][arm], out["arms"][arm] = learn, rows
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", default="strings,tables,grids,graphs"); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(C.ARMS)); ap.add_argument("--max-s", type=float, default=800)
    a = ap.parse_args()
    from nexus import seed_registry as R, w41_eval as WE
    if a.split == "dev":
        R.claim("wave41", "dev", [a.seed], run_id="w41-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w41-confirm_lodo" for r in spent):
            R.claim("wave41", "confirm_lodo", list(R.REGISTRY[("wave41", "confirm_lodo")]), run_id="w41-confirm_lodo")
        if a.seed not in R.REGISTRY[("wave41", "confirm_lodo")]:
            raise SystemExit("seed outside wave41 confirm_lodo")
    ev = WE.Eval(); t0 = time.perf_counter()
    p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    for h in a.folds.split(","):
        if h in res:
            continue
        res[h] = run_fold(ev, a.seed, h, a.arms.split(","))
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
        print(a.seed, h, "%.0fs" % (time.perf_counter() - t0), {arm: (sum(r["correct"] for r in rs), len(rs), sum(r["wrong"] for r in rs),
                          round(sum(r["work"] for r in rs) / 1e9, 1)) for arm, rs in res[h]["arms"].items()}, flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    done = all(h in res for h in a.folds.split(","))
    WE.ledger_append(dict(run=f"w41-track1-{a.split}-{a.seed}", wall_s=time.perf_counter() - t0, status="COMPLETE" if done else "CHECKPOINT"))


if __name__ == "__main__":
    main()

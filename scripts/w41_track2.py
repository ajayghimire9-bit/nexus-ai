"""Wave 41 Track 2 (NOT LOCKED): 500-task continual stream, cost per solved task by quintile (1-100 ... 401-500).
Stream: the 6-phase cycle (strings, graphs, tables, strings, graphs, grids) repeated with fresh instances until 500 tasks
(w38_online.program_stream per phase block). Every arm starts from an EMPTY library and learns online from its own certified
programs (all: Repr counts refit every 8; C/D/Placebo: routing; D/Placebo: skill growth via shadow vault, rent, retirement).
Total work = search + certification + coordination (routing, decomposition evidence) + compilation (online updates, vault
trials), all on the child's instruction counter. Checkpoint (rows + learner state) every 50 tasks; resumable across calls.
--split dev (wave41 dev seed; --n tasks) | confirm (wave41/confirm_stream, one-use)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w41_common as C
PHASES = ["strings", "graphs", "tables", "strings", "graphs", "grids"]


def make_stream(seed, n):
    import w38_online as D
    ts, ph, b = [], [], 0
    while len(ts) < n:
        for i, dom in enumerate(PHASES):
            seg = D.program_stream(f"w41-stream:{seed}:{b}:{i}", (dom,), "all", 1)
            ts += seg; ph += [i] * len(seg)
        b += 1
    return ts[:n], ph[:n]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n", type=int, default=500); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(C.ARMS)); ap.add_argument("--max-s", type=float, default=840)
    a = ap.parse_args()
    from nexus import seed_registry as R, w41_eval as WE
    if a.split == "confirm":
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w41-confirm_stream" for r in spent):
            R.claim("wave41", "confirm_stream", list(R.REGISTRY[("wave41", "confirm_stream")]), run_id="w41-confirm_stream")
        if a.seed not in R.REGISTRY[("wave41", "confirm_stream")]:
            raise SystemExit("seed outside wave41 confirm_stream")
    else:
        R.claim("wave41", "dev", [a.seed], run_id="w41-dev", record=False)
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    tasks, phase = make_stream(a.seed, a.n)
    res["phase_of"] = phase
    ev = WE.Eval()
    for arm in a.arms.split(","):
        st = res.setdefault(arm, {"rows": [], "state": None, "learn": 0})
        if len(st["rows"]) >= len(tasks):
            continue
        ch = ev.child()
        if st["state"] is not None:
            ev.call(ch, {"cmd": "load", "state": st["state"]})
        else:
            ev.call(ch, {"cmd": "reset", "cfg": C.arm_cfg(arm, [], [], f"w41-stream:{a.seed}")})
        for j in range(len(st["rows"]), len(tasks)):
            t = tasks[j]
            depth = len(t["teacher"])
            r = ev.solve(ch, t, depth, f"w41-stream:{a.seed}:{j}")
            learn = 0
            if r.get("certified"):
                u = ev.call(ch, C.update_job(r, t, depth)); learn = u["_instr"]
                r["update"] = {k: u.get(k) for k in ("refit", "adopted", "rolled_back", "retired", "skills")}
            st["learn"] += learn
            r["learn_instr"] = learn
            for kk in ("candidate", "final_public", "snaps", "record"):
                r.pop(kk, None)
            st["rows"].append(r)
            if (j + 1) % 50 == 0 or j + 1 == len(tasks) or time.perf_counter() - t0 > a.max_s:
                st["state"] = ev.call(ch, {"cmd": "state"})["state"]
                p.write_text(json.dumps(res, sort_keys=True, default=repr))
                if time.perf_counter() - t0 > a.max_s:
                    break
        ch.close()
        rows = st["rows"]
        print(arm, len(rows), "solved", sum(r["correct"] for r in rows), "wrong", sum(r["wrong"] for r in rows),
              "work %.0fG" % ((sum(r["work"] for r in rows) + st["learn"]) / 1e9), "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    done = all(len(res.get(x, {}).get("rows", [])) >= len(tasks) for x in a.arms.split(","))
    WE.ledger_append(dict(run=f"w41-track2-{a.split}-{a.seed}", wall_s=time.perf_counter() - t0, status="COMPLETE" if done else "CHECKPOINT"))


if __name__ == "__main__":
    main()

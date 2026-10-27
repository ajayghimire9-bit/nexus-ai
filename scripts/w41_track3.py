"""Wave 41 Track 3 (NOT LOCKED): external tasks. --split dev (PROSE-dev + Split-dev, development data) | confirm (the sealed
PROSE Split.Text set: 92 never-used tasks -> field-extraction tasks; frozen runner; hashes verified; claim wave41/confirm_ext).
Learned objects come ONLY from internal source domains (solved here with the Flat configuration; metered as extra curriculum).
Every arm runs with k = 2 distinguishing queries to the user oracle; k = 0 / 1 / 2 are read from the per-round snapshots.
Guards are scored per input (w41_guards). Also runs Flat_noLemma (the Wave 40 engine) to price the base lemmas."""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w41_common as C
CAP2 = 4_000_000
MAN = ROOT / "artifacts/external/split_confirm/MANIFEST.json"


def load(split):
    if split == "dev":
        import w39_prose as P
        specs, _ = P.tasks_for("dev")
        ts = [C.prose_task(f"prose-dev/{n}", s) for n, s in sorted(specs.items())]
        d = ROOT / "artifacts/external/split_dev"
        for n in json.loads((d / "DEV_SELECTION.json").read_text())["dev"]:
            ts += C.split_tasks(f"split-dev/{n}", (d / n / "input.txt").read_text(), (d / n / "output.json").read_text())
        return ts
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("the sealed Split.Text set may be loaded only by the frozen runner (NEXUS_SEALED_HARNESS_TOKEN)")
    man = json.loads(MAN.read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave41_split"
    ts = []
    for n in man["tasks"]:
        b = {}
        for f in ("input.txt", "output.json"):
            raw = (vault / n / f).read_bytes()
            if hashlib.sha256(raw).hexdigest() != man["sha256"][f"{n}/{f}"]:
                raise SystemExit(f"manifest hash mismatch: {n}/{f}")
            b[f] = raw.decode("utf-8", "replace")
        ts += C.split_tasks(f"split/{n}", b["input.txt"], b["output.json"])
    return ts


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(C.ARMS + ("Flat_noLemma",))); ap.add_argument("--max-s", type=float, default=840)
    ap.add_argument("--k", type=int, default=2)
    a = ap.parse_args()
    from nexus import w38_domains as Dm, w41_eval as WE
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    if a.split == "confirm" and "claimed" not in res:
        from nexus import seed_registry as R
        R.claim("wave41", "confirm_ext", [7881], run_id="w41-confirm_ext")
        res["claimed"] = True
    tasks = load(a.split)
    ev = WE.Eval()
    if "source" not in res:
        src = Dm.stream("w39-src", Dm.DOMAINS, "source", 2)
        rows, progs, sigs = C.learn_sources(ev, src, "w41-src", CAP2)
        res["source"] = dict(n=len(src), certified=len(progs), work=sum(r["work"] for r in rows), programs=progs, sigs=sigs,
                             wrong=sum(r["wrong"] for r in rows))
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
    S_ = res["source"]
    res.setdefault("tasks", {t["name"]: {} for t in tasks})
    for arm in a.arms.split(","):
        if res.get("done", {}).get(arm):
            continue
        ch = ev.child()
        if arm in res.get("state", {}):                       # resume a capped arm with its learner state (growing arms)
            ev.call(ch, {"cmd": "load", "state": res["state"][arm]})
        else:
            fit = ev.call(ch, {"cmd": "reset", "cfg": C.arm_cfg(arm, S_["programs"], S_["sigs"], "w41-ext")})
            res.setdefault("fit", {})[arm] = dict(instr=fit["_instr"], skills=fit.get("skills", 0))
        learn = 0
        for t in tasks:
            if arm in res["tasks"][t["name"]]:
                continue
            if "label" in t:
                res["tasks"][t["name"]][arm] = {"label": t["label"]}; continue
            r = ev.solve(ch, t, 3, f"ext:{t['name']}", budget=CAP2, extra=[x for x, _ in t["heldout"][1:17]], mode="external",
                         k=a.k)
            if arm in C.GROWS and r.get("certified"):
                u = ev.call(ch, C.update_job(r, t, 3)); learn += u["_instr"]
            r["k"] = C.score_k(r, t, a.k)
            r.pop("candidate", None); r.pop("final_public", None)
            res["tasks"][t["name"]][arm] = r
            if time.perf_counter() - t0 > a.max_s:
                break
        res["fit"][arm]["online_learn_instr"] = res["fit"][arm].get("online_learn_instr", 0) + learn
        res.setdefault("state", {})[arm] = ev.call(ch, {"cmd": "state"})["state"]
        res["fit"][arm]["skills_end"] = (res["state"][arm].get("lib") or {}).get("skills") and \
            sum(1 for _, v in res["state"][arm]["lib"]["skills"] if v["active"])
        ch.close()
        if all(arm in v for v in res["tasks"].values()):
            res.setdefault("done", {})[arm] = True
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
        print(arm, "done" if res.get("done", {}).get(arm) else "partial", "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    WE.ledger_append(dict(run=f"w41-track3-{a.split}", wall_s=time.perf_counter() - t0,
                          status="COMPLETE" if all(res.get("done", {}).get(x) for x in a.arms.split(",")) else "CHECKPOINT"))


if __name__ == "__main__":
    main()

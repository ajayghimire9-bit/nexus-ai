"""Wave 31 increment 2 (NOT LOCKED): 4-domain leave-one-domain-out rotation through the independent evaluator.
Per fold (held-out domain h):
  1. Source learning: the source tasks of the 3 other domains are solved as Fresh/matched (with probing) in a
     sandboxed child. The evaluator returns the candidates it certified (exhaustive_UNIQUE) to the child, which
     builds the Useful library (skeleton macros) and the size-matched Placebo library.
  2. Adversarial tasks against the frozen Useful library (evaluator side).
  3. Five configs, each in its own sandboxed child: Fresh/matched, Useful/matched, Placebo/matched, Useful/macro,
     Placebo/macro, over the h-domain targets plus the adversarial tasks.
Reports: labels by category; target-only work and source-amortised total work (evaluator-metered kernel work
+ solver-reported prover work, with child CPU seconds alongside); oracle calls; wrong answers inside / outside
scope."""
import argparse, hashlib, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONFIGS = (("Fresh", "matched"), ("Useful", "matched"), ("Placebo", "matched"), ("Useful", "macro"), ("Placebo", "macro"))


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def run_seed(seed, split, hashseed, folds):
    from nexus import wave31_evaluator as E
    from nexus import wave31_tasks as T
    ev = E.Evaluator()
    out = dict(seed=seed, split=split, checker_v2=ev.pin, folds={})
    for h in folds:
        f = dict()
        src = T.source_stream(seed, h)
        ch = E.Child(hashseed)
        src_rows, progs = [], []
        for i, t in enumerate(src):
            r = ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:src{i}")
            src_rows.append(r)
            if r["label"] == "exhaustive_UNIQUE":
                progs.append(r["candidate"])
        lib = ev.library(ch, progs, f"{seed}:{h}")
        f["source"] = dict(n=len(src), certified=len(progs), cpu_s=round(ch.close(), 3),
                           kernel=sum(r["kernel"] for r in src_rows),
                           solver_reported=sum(sum(r["solver_reported"].values()) for r in src_rows),
                           oracle_calls=sum(r["oracle_calls"] for r in src_rows),
                           labels=dict(Counter(r["label"] for r in src_rows)),
                           wrong=sum(r["wrong"] is not None for r in src_rows))
        f["library"] = dict(useful=len(lib["useful"]), placebo=len(lib["placebo"]), skeletons=lib["skeletons"],
                            placebo_skeletons=lib["placebo_skeletons"],
                            digest=digest([lib["useful"], lib["placebo"]]))
        tgt = T.target_stream(seed, h)
        adv, gen_steps = T.adversarial_stream(seed, h, lib["useful"])
        f["adversarial_generation_steps"] = gen_steps
        f["configs"] = {}
        for arm, mode in CONFIGS:
            L = lib["useful"] if arm == "Useful" else lib["placebo"] if arm == "Placebo" else []
            ch = E.Child(hashseed)
            rows = [ev.solve(ch, t, arm, mode, L, f"{seed}:{h}:{k}") for k, t in enumerate(tgt + adv)]
            f["configs"][f"{arm}/{mode}"] = dict(cpu_s=round(ch.close(), 3), rows=rows)
        out["folds"][h] = f
    return out


def summarise(res):
    agg = defaultdict(lambda: defaultdict(Counter))
    src = Counter()
    for h, f in res["folds"].items():
        src.update(dict(kernel=f["source"]["kernel"], solver_reported=f["source"]["solver_reported"],
                        cpu_ms=int(1000 * f["source"]["cpu_s"]), oracle_calls=f["source"]["oracle_calls"],
                        n=f["source"]["n"], certified=f["source"]["certified"]))
        for cfg, c in f["configs"].items():
            agg[cfg]["_all"]["cpu_ms"] += int(1000 * c["cpu_s"])
            for r in c["rows"]:
                a = agg[cfg][r["category"]]
                a["n"] += 1
                a["label:" + r["label"]] += 1
                a["correct"] += r["correct"]
                a["wrong_outside"] += r["wrong"] == "wrong_teacher_outside_scope"
                a["wrong_inside"] += r["wrong"] == "wrong_teacher_inside_scope"
                a["kernel"] += r["kernel"]
                a["solver_reported"] += sum(r["solver_reported"].values())
                a["oracle_calls"] += r["oracle_calls"]
                a["probes"] += r["probes"]
                a["fallback"] += r["fallback"]
    return dict(source=dict(src), configs={k: {c: dict(v) for c, v in d.items()} for k, d in agg.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True); ap.add_argument("--split", default="dev")
    ap.add_argument("--hashseed", default="0"); ap.add_argument("--folds", default="records,strings,grids,graphs")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    R.claim("wave31", a.split, [a.seed], run_id=f"wave31b-{a.split}", record=False)
    if a.split == "admission_val" and a.hashseed == "0" and Path(a.out).exists():
        raise SystemExit("admission_val is run once; artifact already exists")
    t0 = time.perf_counter()
    res = run_seed(a.seed, a.split, a.hashseed, a.folds.split(","))
    wall = time.perf_counter() - t0
    res["summary"] = summarise(res)
    replay_view = {h: {cfg: [{k: v for k, v in r.items()} for r in c["rows"]] for cfg, c in f["configs"].items()}
                   for h, f in res["folds"].items()}
    res["digest"] = digest([replay_view, {h: f["library"]["digest"] for h, f in res["folds"].items()}])
    E.ledger_append(dict(run=f"wave31b-{a.split}-{a.seed}-hs{a.hashseed}", wall_s=wall, status="COMPLETE",
                         digest=res["digest"]))
    Path(a.out).write_text(json.dumps(res, default=repr, sort_keys=True))
    print(json.dumps(dict(seed=a.seed, wall_s=round(wall, 1), digest=res["digest"]), default=repr))
    print(json.dumps(res["summary"], default=repr))


if __name__ == "__main__":
    main()

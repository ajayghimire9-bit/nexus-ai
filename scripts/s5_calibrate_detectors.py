"""Stage 5 drift-detector calibration (NOT LOCKED; src + dev worlds ONLY). Streams: per-supplier manifest weights in offset
order. Clean streams measure false alarms; copies with a unit shift (x 2.2046, the lb case) injected after a random prefix
measure detection delay (records after the change) and misses. Selection rule (predeclared here): minimise mean delay
subject to <= 1 false alarm per 1,000 clean records and <= 10% misses (STRICT, infeasible on dev: recorded); operations then use
min misses, then false alarms, then delay (alarms are investigation-gated). Writes artifacts/s5_detector_calibration.json."""
import itertools, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import s4_env as E, s5_ops as O, s456_seeds as S, seed_registry as R
from nexus.wave31_evaluator import ledger_append


def streams():
    out = []
    for split in ("src", "dev"):
        R.claim("de2", split, list(R.REGISTRY[("de2", split)]), run_id=f"de2-{split}", record=False)
        for seed in R.REGISTRY[("de2", split)]:
            w = E.make_world(seed, split)
            enc = E.encode(w, "ops")
            by = {}
            for tk, parts in enc["log"].items():
                for (t, p), rs in parts.items():
                    if t == "manifests":
                        for x in rs:
                            if isinstance(x["weight"], (int, float)):
                                by.setdefault(x["supplier"], []).append((x["offset"], x["weight"]))
            out += [[v for _, v in sorted(xs)] for xs in by.values()]
    return out


def evaluate(make, ss, rng):
    fa = n = 0
    delays, miss = [], 0
    t0 = time.process_time()
    for xs in ss:
        d = make()
        fa += sum(d.update(x) for x in xs)
        n += len(xs)
        cut = rng.randint(len(xs) // 3, 2 * len(xs) // 3)
        d = make()
        hit = None
        for i, x in enumerate(xs[:cut] + [v / 0.45359237 for v in xs[cut:]]):
            if d.update(x) and i >= cut and hit is None:
                hit = i - cut
        if hit is None:
            miss += 1
        else:
            delays.append(hit)
    return dict(far_per_1000=1000 * fa / max(1, n), miss_rate=miss / len(ss), mean_delay=sum(delays) / max(1, len(delays)),
                cpu_s=time.process_time() - t0)


def main():
    t0 = time.perf_counter()
    ss = streams()
    grid = {"bocpd_merge_exact": [dict(H=h, p=p, short=s, warm=wm) for h in (1 / 20, 1 / 50, 1 / 100)
                                  for p in (0.5, 0.7, 0.9) for s in (3, 4, 6) for wm in (6, 8)],
            "fixed_ratio": [dict(w=w, k=k) for w in (3, 4, 5, 6) for k in (1.4, 1.6, 1.8, 2.0)]}
    res = {}
    for name, cands in grid.items():
        rows = []
        for c in cands:
            m = evaluate(lambda c=c: O.DETECTORS[name](**c), ss, random.Random(f"cal:{name}"))
            rows.append(dict(params=c, **m))
        ok = [r for r in rows if r["far_per_1000"] <= 1.0 and r["miss_rate"] <= 0.10]      # the strict rule written first
        # Revised on dev after the strict rule proved infeasible for every candidate (disclosed): alarms are investigation-
        # gated (a false alarm costs one investigation, never a repair), so operations select min misses, then false
        # alarms, then delay.
        best = min(rows, key=lambda r: (round(r["miss_rate"], 6), r["far_per_1000"], r["mean_delay"]))
        res[name] = dict(selected=best, strict_feasible=len(ok), selection_rule="min miss, then FAR, then delay", grid=rows)
        print(name, "strict-feasible", len(ok), "selected", best)
    res["operator_detector"] = min(("bocpd_merge_exact", "fixed_ratio"), key=lambda n: (round(res[n]["selected"]["miss_rate"], 6),
                                                                                   res[n]["selected"]["far_per_1000"]))
    res["streams"] = len(ss)
    (ROOT / "artifacts/s5_detector_calibration.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    ledger_append(dict(run="de2-s5-calibrate-detectors", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()

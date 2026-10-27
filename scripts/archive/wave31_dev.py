"""Wave 31 development diagnostics (NOT LOCKED): source learning on lists + strings, frozen library, then Fresh /
Useful / size-matched Placebo on grids + graphs. Certificates: Checker v2 only (pin verified from a git object)."""
import argparse, hashlib, json, random, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
V2_PIN_COMMIT = "01d84f6"


def verify_v2():
    pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V2_PIN_COMMIT}:src/nexus/checker_kernel_v2.sha256"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v2.py").read_bytes()).hexdigest()
    import nexus.checker_kernel_v2 as V
    if disk != pin or Path(V.__file__).resolve() != (ROOT / "src/nexus/checker_kernel_v2.py").resolve():
        raise SystemExit("checker v2 does not match its pin; refusing to run")
    return pin


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_ir as W
    R.claim("wave31", "dev", [a.seed], run_id="wave31-dev", record=False)
    pin = verify_v2()
    t0 = time.perf_counter()
    src = W.stream(a.seed, W.SOURCE_DOMAINS)
    tgt = W.stream(a.seed, W.TARGET_DOMAINS)
    # source learning (billed separately): Fresh-certify source tasks, keep only exhaustively certified programs
    src_rows, progs, src_work = [], [], 0
    for t in src:
        v, ev, meter, g = W.solve("Fresh", t["public"], t["query"], [])
        src_work += sum(meter.values())
        src_rows.append(W.evaluate(t, v, ev, meter, g))
        if v["label"] == "exhaustive_UNIQUE":
            progs.append(ev["candidate"])
    lib, skeletons = W.library_from(progs)
    plc = W.placebo_library(len(lib), [len(m["body"]) for m in lib], random.Random(f"w31-placebo:{a.seed}"))
    rows = {}
    for arm, L in (("Fresh", []), ("Useful", lib), ("Placebo", plc)):
        rows[arm] = []
        for t in tgt:
            ts = time.perf_counter()
            v, ev, meter, g = W.solve(arm, t["public"], t["query"], L)
            r = W.evaluate(t, v, ev, meter, g); r["wall_s"] = round(time.perf_counter() - ts, 2)
            rows[arm].append(r)
    with open(ROOT / "runs/experimental/wave24-agi/ledger.jsonl", "a") as f:
        f.write(json.dumps(dict(run=f"wave31-dev-{a.seed}", wall_s=time.perf_counter() - t0, status="COMPLETE")) + "\n")
    rep = dict(seed=a.seed, checker_v2=pin, source=dict(n=len(src), certified=len(progs), work=src_work,
                                                        summary=W.summarise(src_rows)),
               library=dict(macros=len(lib), skeletons=skeletons), placebo_macros=len(plc),
               arms={arm: W.summarise(rs) for arm, rs in rows.items()})
    Path(a.out).write_text(json.dumps(dict(report=rep, rows=rows, source_rows=src_rows), default=repr, sort_keys=True))
    print(json.dumps(rep["arms"], default=repr)[:3000]); print("source", rep["source"]["n"], rep["source"]["certified"], "library", len(lib))


if __name__ == "__main__":
    main()

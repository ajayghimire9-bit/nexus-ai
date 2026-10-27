"""Wave 40 Step 4.2 (NOT LOCKED): the Wave 39 6-phase stream protocol rerun with the REPAIRED search. Learners: Fresh-v5,
Ungated Online (= no-gate, BASELINE_80F9CC2), Hard-Gated (= regime-memory, Wave 38 RegimeLearner: a separate prior per
identified regime) and Hierarchical Stream Memory (hier-s1, frozen in Wave 39). Seeds: wave40 dev | confirm_stream.
Wave 39 text: hierarchical stream memory on the 6-phase continual program stream (strings -> graphs ->
tables -> strings (return) -> graphs (return) -> grids), fresh instances, EMPTY library, v5 language / Checker v5 for every
learner. Learners: Fresh, no-gate (BASELINE_80F9CC2), regime memory (Wave 38), hierarchical (global + regime residual,
shrink s). --split dev (wave39 dev seed) | confirm (confirm_stream, one-use; frozen learners)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
PHASES = ["strings", "graphs", "tables", "strings", "graphs", "grids"]


def learners(spec):
    from nexus import w38_online as O
    B = O.BASELINE_80F9CC2
    table = {"Fresh": (None, 4.0), "no-gate": (B, 4.0), "regime-memory": (dict(B, gate="regime"), 4.0)}
    for s in (1.0, 4.0, 16.0):
        table[f"hier-s{int(s)}"] = (dict(B, gate="hier"), s)
    return {k: table[k] for k in spec.split(",")}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--seed", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--learners", default="Fresh,no-gate,regime-memory,hier-s1")
    ap.add_argument("--max-s", type=float, default=850)
    a = ap.parse_args()
    from nexus import seed_registry as R, w40_eval as WE
    import w38_online as D
    if a.split == "confirm":
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w40-confirm_stream" for r in spent):
            R.claim("wave39", "confirm_stream", list(R.REGISTRY[("wave40", "confirm_stream")]), run_id="w40-confirm_stream")
        if int(a.seed) not in R.REGISTRY[("wave40", "confirm_stream")]:
            raise SystemExit("seed outside confirm_stream")
    else:
        R.claim("wave40", "dev", [int(a.seed)], run_id="w40-dev", record=False)
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    if "tasks" not in res:
        ts, ph = [], []
        for i, dom in enumerate(PHASES):
            seg = D.program_stream(f"w40-stream:{a.seed}:{i}", (dom,), "all", 1)
            ts += seg; ph += [i] * len(seg)
        res["tasks"], res["phase_of"] = ts, ph
    ev = WE.Eval()
    for name, (g, s) in learners(a.learners).items():
        if name in res:
            continue
        rows, learn, declared, _ = ev.stream(res["tasks"], g, f"w40-stream:{a.seed}", shrink=s)
        res[name] = dict(work=sum(r["work"] for r in rows) + learn, learn=learn, n=len(rows), correct=sum(r["correct"] for r in rows),
                         wrong=sum(r["wrong"] for r in rows), declared=declared, curve=[r["work"] for r in rows],
                         solved=[r["correct"] for r in rows], status=[r["status"] for r in rows], execs=[r["execs"] for r in rows],
                         phase_work=[sum(r["work"] for r, q in zip(rows, res["phase_of"]) if q == i) for i in range(len(PHASES))])
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
        x = res[name]
        print(name, round(x["work"] / 1e9, 1), [round(w / 1e9, 1) for w in x["phase_work"]], x["correct"], x["n"], "wrong", x["wrong"],
              "declared", declared, "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    WE.ledger_append(dict(run=f"w40-stream-{a.split}-{a.seed}", wall_s=time.perf_counter() - t0, status="CHECKPOINT"))


if __name__ == "__main__":
    main()

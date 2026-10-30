"""Phase 10G Stage 2: one training stream of the shared atomic-guided solver + the evidence-acquisition policy (NOT LOCKED).
  python scripts/agi10g_train.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: manifest10g.train(rep) / train_spec(rep, i) (Phase 10E families + designed ambiguity, world10g projects). Everything runs
inside atomic10f.atomic() (the shared substrate), with lineage10g (Abs_subgroup, k_min = 3 fixed; evidence-aware wake that explores
all 5 channels on every training tie). Sleep every 10 tasks; checkpoints at N = 60 / 120 (dev: n/2, n); N = 120 or the budget.
The learner's own time guards never fire (deadline beyond reach); BUDGET_S stops launching new tasks; the meter's cap is the hard
stop. At the end pi_ev is trained on memory["ev_records"] (ev10g.train_pi) and saved with the final checkpoint as guides["pi_ev"]
(the shared solver's ranker is guides["L0"]: atomic-substrate primitive guidance = B_atomic_learned). Rows appended + flushed."""
import json, shutil, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase10f import atomic10f as AT  # noqa: E402
from nexus.de_phase10g import ev10g as EV, lineage10g as LG, manifest10g as MG  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), MG.N_MAX)
    out = ROOT / ("artifacts/agi10g_dev/train" if dev else "artifacts/agi10g_train")
    cps = (n_max // 2, n_max) if dev else MG.CHECKPOINTS
    if dev:
        b = MG.RANGES[("agi10gde", "dev")].start + 300 * rep
        seeds = dict(wake=range(b, b + 100), dream=range(b + 100, b + 200), admit=range(b + 200, b + 300))
    else:
        seeds = MG.train(rep)
        if (out / f"rep{rep}.final.json").exists():
            raise SystemExit("repetitions are never rerun")
    root = ROOT / "var/agi10g_ws" / ("dev" if dev else "train") / f"rep{rep}"
    with AT.atomic():
        L = LG.Learner(rep, f"rep{rep}", root, T0 + 10 ** 6, out, seeds, stream=lambda i: MG.train_spec(rep, i), abs_mode="subgroup")
        L.log("events", dict(kind="start", rep=rep, n_max=n_max, checkpoints=list(cps)))
        wake = list(seeds["wake"])
        for i in range(n_max):
            if time.time() - T0 > budget:
                L.log("events", dict(kind="deadline", i=i))
                break
            try:
                L.wake(i, wake[i])
            except RuntimeError as e:
                L.log("events", dict(kind="build_failed", seed=wake[i], err=str(e)[:80]))
                L.n += 1
            n = i + 1
            if n % L.M["batch"] == 0 or n in cps:
                L.sleep()
            if n in cps:
                L.checkpoint(n)
        fin = out / f"rep{rep}.N{L.n}.json"
        if not (L.n in cps and fin.exists()):
            fin = L.checkpoint(L.n)
    tp = time.time()
    w, info = EV.train_pi(L.mem.get("ev_records", []), rep)
    L.cost["pi_training"] = round(time.time() - tp, 4)
    ck = json.loads(fin.read_text())
    ck["memory"]["guides"]["pi_ev"] = w
    ck["pi_ev"], ck["cost"] = info, L.cost
    (out / f"rep{rep}.final.json").write_text(json.dumps(ck, default=list))
    L.log("events", dict(kind="end", n=L.n, cost={k: round(v, 2) for k, v in L.cost.items()}, pi_ev=info, ev_execs=L.mem.get("ev_execs", 0), wall=round(time.time() - T0, 1)))
    w_ = [json.loads(l) for l in open(out / f"rep{rep}.wake.jsonl")]
    print(f"rep{rep}", "tasks", L.n, "verified", sum(x["verified"] for x in w_), "wrong", sum(x["wrong"] for x in w_), "ties", sum(bool(x["tie"]) for x in w_),
          "ties_resolved", sum(bool(x["tie"]) and x["tie"]["resolved"] for x in w_), "wall_bound", sum(x["wall_bound"] for x in w_), "pi_ev", info,
          "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main(*sys.argv[1:])

"""Freeze MI-2 Milestone A (NOT LOCKED).  python scripts/mi2_freeze.py
Representatives by the pre-registered rule (mi2_discover: the lineage winner with the best selection score, ties lower lineage):
A2 = evolve, A3 = random_struct, A4 = params; every other lineage winner is evaluated too (A2_L*, A3_L*) and reported as
replication evidence, never gating. Fixed arms: A0 baseline (GRAMMAR5), A1 MI-1's frozen procedure, A5 the human-written
procedure (mi2_learner.A5_PROG), A6 generic direct synthesis (mi2_learner.a6_domain). Records sha256 of every file the
evaluation depends on; mi2_eval refuses to run if any differs."""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
D = "artifacts/mi2_dev"
LINEAGES = {"evolve": (1, 2, 3), "random_struct": (1, 2, 3), "params": (1,)}
FILES = ["src/nexus/mi2_learner.py", "src/nexus/mi2_lpl.py", "src/nexus/mi2_seeds.py", "src/nexus/mi_learner.py", "src/nexus/mi_lpl.py",
         "src/nexus/mi_ocean.py", "src/nexus/x7_regsearch.py", "src/nexus/ba_accept.py", "src/nexus/t7_repair.py", "src/nexus/u5_statesplit.py",
         "scripts/mi2_eval.py", "scripts/mi2_score.py", "scripts/mi2_discover.py", "scripts/ba_eps.py", "scripts/mi_exec.py",
         "artifacts/mi_dev/select_evolve.json"]


def main():
    arms = {"A0": dict(kind="baseline"), "A1": dict(kind="file", file="artifacts/mi_dev/select_evolve.json"),
            "A5": dict(kind="a5"), "A6": dict(kind="a6")}
    reps = {}
    for arm, lins in LINEAGES.items():
        ws = []
        for L in lins:
            p = f"{D}/select_a_{arm}_L{L}.json"
            s = json.loads((ROOT / p).read_text())
            ws.append((s["winner_sel_fitness"][:2], -L, p))
            FILES.append(p)
        ws.sort(key=lambda w: (w[0], w[1]), reverse=True)
        reps[arm] = [w[2] for w in ws]
    for tag, arm in (("A2", "evolve"), ("A3", "random_struct"), ("A4", "params")):
        arms[tag] = dict(kind="file", file=reps[arm][0])
        for p in reps[arm][1:]:
            arms[f"{tag}_L{p.rsplit('_L', 1)[1].split('.')[0]}"] = dict(kind="file", file=p)
    fr = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              files={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
              arms={"val": arms, "test": arms}, representatives=reps)
    (ROOT / "artifacts/mi2_freeze.json").write_text(json.dumps(fr, indent=1))
    print(json.dumps(fr["arms"]["val"], indent=1))


if __name__ == "__main__":
    main()

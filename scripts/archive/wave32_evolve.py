"""Wave 32 stepping-stone archive evolution (bounded, NOT LOCKED). Resumable; every invocation is <= 900 s.
Fitness episodes: online streams from an EMPTY library on the evolution domains (records, strings, graphs; wave32
dev seeds 771-773; selection 774-775). The held-out test domain (grids) and the test seeds are never touched here.
Per generation:
  * lambda children, each from a tournament-picked archive parent, mutated (novel genomes only);
  * all 5 detectors on every child's rows, D4 fingerprint around the generation, and a fresh-process replay
    (PYTHONHASHSEED=1) of one child;
  * a child is ADMITTED to the archive only if no detector fired, the replay matched (if it was replayed) and
    wrong == 0. Rejected children are kept in the log with their reason.
Fitness uses only the evaluator's external meter (never solver-reported numbers)."""
import argparse, hashlib, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EVOL_DOMAINS = ("records", "strings", "graphs")
FIT_SEEDS = (771, 772, 773)
SEL_SEEDS = (774, 775)
STATE = ROOT / "artifacts/wave32_archive.json"
NOISY = ("ext", "solver_reported", "wall_s")


def stream(seed, domains, n_per=2):
    from nexus import wave31_tasks as T
    tasks = [t for d in domains for t in T.target_stream(seed, d, n_per)]
    random.Random(f"w32-order:{seed}").shuffle(tasks)
    return tasks


def run_genome(ev, genome, seeds, domains, hashseed="0", n_per=2):
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    rows, learn = [], 0
    for s in seeds:
        ch = E.Child(hashseed)
        r, li = A.episode(ev, ch, stream(s, domains, n_per), genome, f"w32:{s}")
        ch.close()
        rows += r; learn += li
    return rows, learn


def digest(rows):
    return hashlib.sha256(json.dumps([{k: v for k, v in r.items() if k not in NOISY} for r in rows],
                                     sort_keys=True, default=repr).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--gens", type=int, default=1); ap.add_argument("--lam", type=int, default=5)
    ap.add_argument("--max-gen", type=int, default=8)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    R.claim("wave32", "dev", list(FIT_SEEDS), run_id="wave32-evolve", record=False)
    t0 = time.perf_counter()
    ev = E.Evaluator(depth=3)
    st = json.loads(STATE.read_text()) if STATE.exists() else {"archive": [], "log": [], "gen": -1}
    seen = {e["key"] for e in st["log"]}
    for _ in range(a.gens):
        gen = st["gen"] + 1
        if gen > a.max_gen:
            break
        rng = random.Random(f"w32-evolve:{gen}")
        fp = D.fingerprint()
        if gen == 0:
            kids = [(None, dict(A.GEN0))]
        else:
            kids = []
            while len(kids) < a.lam:
                p = A.pick_parent(st["archive"], rng)
                g = A.mutate(p["genome"], rng)
                if A.gkey(g) not in seen and A.gkey(g) not in {A.gkey(k) for _, k in kids}:
                    kids.append((p["id"], g))
        rep_i = rng.randrange(len(kids))
        for i, (parent, g) in enumerate(kids):
            rows, learn = run_genome(ev, g, FIT_SEEDS, EVOL_DOMAINS)
            fit = A.fitness(rows, learn)
            det = D.scan(rows)
            replay = None
            if i == rep_i:
                rows2, _ = run_genome(ev, g, FIT_SEEDS[:1], EVOL_DOMAINS, hashseed="1")
                replay = digest(rows2) == digest(rows[:len(rows2)])
            ok = sum(det.values()) == 0 and fit["wrong"] == 0 and replay is not False
            ent = dict(id=f"g{gen}c{i}", gen=gen, parent=parent, genome=g, key=A.gkey(g), fit=fit, detectors=det,
                       replay=replay, admitted=ok, reason=None if ok else
                       ("detector" if sum(det.values()) else "wrong" if fit["wrong"] else "replay_mismatch"))
            st["log"].append(ent); seen.add(ent["key"])
            if ok:
                st["archive"].append(ent)
            print(json.dumps({k: ent[k] for k in ("id", "parent", "admitted", "replay")}), json.dumps(fit), flush=True)
        d4 = D.scan([], fp)["D4_integrity"]
        st.setdefault("integrity", []).append(dict(gen=gen, D4=d4))
        if d4:
            raise SystemExit("D4 integrity violation; evolution stopped")
        st["gen"] = gen
        STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
        if time.perf_counter() - t0 > 600:
            break
    E.ledger_append(dict(run=f"wave32-evolve-gen{st['gen']}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    best = min(st["archive"], key=lambda e: (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["work"]))
    print("gen", st["gen"], "archive", len(st["archive"]), "log", len(st["log"]), "best", best["id"], best["fit"])


if __name__ == "__main__":
    main()

"""Phase 10F Stage 2: paired abstraction training, Abs_current vs Abs_subgroup, on one numeric-seeded stream (NOT LOCKED).
  python scripts/agi10f_train.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: manifest10f.train(rep) / train_spec(rep, i) (Phase 10E families; replay only as S_replay; world10f projects).
PAIRING (lineage10f change 3): ONE learner (rule Abs_current) runs the stream; before every sleep both rules' selections are
computed on the same state, and at the FIRST sleep where they differ the learner is forked: `rep{r}.current` continues under
Abs_current and `rep{r}.subgroup` under Abs_subgroup, from the identical state. Until the fork every sleep is identical under
both rules, so the shared prefix is each arm's own history (it is computed once; both arms' logs and cost dicts include it).
If they never differ by N, the two arms are identical and `rep{r}.subgroup` is a copy (disclosed in the events log).
After the fork both branches see task i in turn; the branch that goes first alternates with i (shared pure caches give the
second a wall-time advantage only; searches bind on work, and every wake row records wall_bound).
TIME: the learner's deadline is set beyond reach, so lineage10e's time guards (skip abstraction / dreams with < 30 s left, stop with
< 25 s left) never fire in either arm; BUDGET_S only stops launching new tasks, and the meter's cap is the hard stop (checkpoints
are written as they are reached, so a kill leaves the reached checkpoints; disclosed as TIMEOUT).
Dream teacher, primitive substrate, admission gate, rankers: unchanged (lineage10f). Sleep every 10 tasks; checkpoints at
N = 50 / 100 (dev: n/2, n); the last checkpoint of each branch is also saved as rep{r}.{rule}.final.json with G_atomic (atomic10f,
the B_atomic_learned ranker on the same step records). Rows appended + flushed to artifacts/agi10f_train/ (dev: artifacts/agi10f_dev/train/)."""
import json, shutil, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase10f import atomic10f as AT, lineage10f as LF, manifest10f as MF  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), MF.N_MAX)
    out = ROOT / ("artifacts/agi10f_dev/train" if dev else "artifacts/agi10f_train")
    cps = (n_max // 2, n_max) if dev else MF.CHECKPOINTS
    if dev:
        b = MF.RANGES[("agi10fde", "dev")].start + 300 * rep
        seeds = dict(wake=range(b, b + 100), dream=range(b + 100, b + 200), admit=range(b + 200, b + 300))
    else:
        seeds = MF.train(rep)
        if any(out.glob(f"rep{rep}.*.final.json")):
            raise SystemExit("repetitions are never rerun")
    root = ROOT / "var/agi10f_ws" / ("dev" if dev else "train") / f"rep{rep}"
    force = next((int(f.split("=")[1]) for f in flags if f.startswith("--force-fork=")), None) if dev else None    # dev timing only
    deadline = T0 + 10 ** 6                       # the learner's time guards never fire (any arm); the meter's cap is the hard stop
    cur = LF.Learner(rep, f"rep{rep}.current", root, deadline, out, seeds, abs_mode="current")
    cur.log("events", dict(kind="start", rep=rep, n_max=n_max, checkpoints=list(cps)))
    sub = None
    wake = list(seeds["wake"])
    for i in range(n_max):
        if time.time() - T0 > budget:
            for L in (cur, sub) if sub else (cur,):
                L.log("events", dict(kind="deadline", i=i))
            break
        live = [cur] if sub is None else ([cur, sub] if i % 2 == 0 else [sub, cur])
        for L in live:
            try:
                L.wake(i, wake[i])
            except RuntimeError as e:
                L.log("events", dict(kind="build_failed", seed=wake[i], err=str(e)[:80]))
                L.n += 1
        n = i + 1
        if n % cur.M["batch"] == 0 or n in cps:
            if sub is None:
                a, b_ = [c["canonical"] for c in cur.select("current")], [c["canonical"] for c in cur.select("subgroup")]
                if a != b_ or n == force:
                    sub = cur.fork("subgroup", f"rep{rep}.subgroup")
                    for L in (cur, sub):
                        L.log("events", dict(kind="fork_selection", n=n, current=a, subgroup=b_))
            for L in (cur, sub) if sub else (cur,):
                L.sleep()
        if n in cps:
            for L in (cur, sub) if sub else (cur,):
                L.checkpoint(n)
    if sub is None:
        sub = cur.fork("subgroup", f"rep{rep}.subgroup")
        for L in (cur, sub):
            L.log("events", dict(kind="never_diverged", n=cur.n))
    for L in (cur, sub):
        fin = out / f"{L.name}.N{L.n}.json"
        if not (L.n in cps and fin.exists()):
            fin = L.checkpoint(L.n)
        ck = json.loads(fin.read_text())
        w, info = AT.atomic_guide(L.mem, rep, L.cycles)
        ck["memory"]["guides"]["atomic"] = w
        ck["atomic_guide"] = info
        (out / f"{L.name}.final.json").write_text(json.dumps(ck, default=list))
        L.log("events", dict(kind="end", n=L.n, cost={k: round(v, 1) for k, v in L.cost.items()}, atomic_guide=info, wall=round(time.time() - T0, 1)))
        w_ = [json.loads(l) for l in open(out / f"{L.name}.wake.jsonl")]
        print(L.name, "tasks", L.n, "verified", sum(x["verified"] for x in w_), "wrong", sum(x["wrong"] for x in w_), "wall_bound", sum(x.get("wall_bound", False) for x in w_),
              "skills", len(L.mem["de"]["skills"]), "replay_macros", [s["canonical"][:90] for s in L.mem["de"]["skills"].values() if s["edits"][0][0] == "add_partition"],
              "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main(*sys.argv[1:])

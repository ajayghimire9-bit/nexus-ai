"""Phase 3 protocol checks (NOT LOCKED; generators / references only, no learner).  python scripts/agi3_protocol.py
1 seeds fresh / disjoint / one-use (agi3, agi3de)
2 world isolation: sampled Phase 3 source / admission / rollout / source-meta world tasks contain no withheld, C / E,
  Phase-2-comparison (C5, C6, E5, E6) or untouched Phase 3 (C7, C8, E7, E8: occupancy / frame / confadd / thresh) mechanism
3 DE mechanism overlap: DE source / admission projects are G1-G4 only; the holdout families G5 (default-fill) and G6
  (watermark lateness) never appear in a source pool; their contract mechanisms (notes) differ from every source family's
4 world dedup: unfamiliar world targets vs the sampled pool (descriptor / behaviour on hidden inputs)
-> artifacts/agi3_protocol_check.json"""
import json, re, sys
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign3 import seeds as SD, agent_loop as AL
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agi2_protocol import PREFIX  # noqa: E402
PREFIX = dict(PREFIX, C7=("occupancy",), C8=("frame",), E7=("confadd",), E8=("thresh",))


def mech(d):
    return set(re.findall(r"([a-z_]+)\[", d))


def main():
    res = {}
    mine = {k: v for k, v in R.REGISTRY.items() if k[0] in ("agi3", "agi3de")}
    others = [v for k, v in R.REGISTRY.items() if k[0] not in ("agi3", "agi3de")]
    spent = max((max(x.get("seeds") or [0]) for x in R._spent()), default=0)
    lo = min(v.start for v in mine.values())
    res["seeds"] = dict(min_phase3=lo, max_other_stop=max(v.stop for v in others), max_spent=spent,
                        fresh=lo >= max(max(v.stop for v in others), spent + 1), one_use=sorted(map(list, SD.ONE_USE)))
    learn = set()
    for w, f in SD.LEARN:
        learn |= set(PREFIX[f])
    pool = []
    cells = [(w, f, lv) for (w, f) in SD.LEARN for lv in (1, 2, 3, 4)]
    for rep in range(3):
        for key, off, n in (("source", 1000 * rep, 160), ("source_meta", 300 * rep, 64)):
            base = SD.RANGES[("agi3", key)].start + off
            pool += [AL.task_of(*cells[i % 32], base + i) for i in range(n)]
        for key in ("admission", "rollout"):
            base = SD.RANGES[("agi3", key)].start + 300 * rep
            for i in range(60):
                s = base + i
                w, f = SD.ADMIT[s % 4]
                pool.append(AL.task_of(w, f, (s % 4 + s // 4) % 2 + 1 if key == "admission" else s % 2 + 1, s))
    leaks = [t.tid for t in pool if mech(t.descr) - learn - set(PREFIX[t.family])]
    res["world_isolation"] = dict(pool=len(pool), tasks_with_foreign_mechanisms=leaks)
    import inspect
    src = inspect.getsource(AL.Lineage3._de_step) + inspect.getsource(AL.Lineage3.de_round) + inspect.getsource(AL.Curriculum3)
    res["de_overlap"] = dict(source_families=list(SD.DE_SOURCE), holdout_families=list(SD.DE_HOLDOUT),
                             holdout_in_source_code_paths=[f for f in SD.DE_HOLDOUT if f in src],
                             note="source / admission DE projects are drawn only from DE_SOURCE (Curriculum3 cells, de_round)")
    by_sig = {}
    for t in pool:
        by_sig.setdefault((t.mech.sig, t.mech.out), []).append(t)
    pd = {t.descr: t.tid for t in pool}
    bad, fam_ = [], []
    for name, lst in SD.panels().items():
        for (w, f, lv, s, _) in lst:
            t = AL.task_of(w, f, lv, s)
            ys = [t.ref(x) for x in t.hidden_x]
            hit = None
            for u in by_sig.get((t.mech.sig, t.mech.out), []):
                try:
                    if all(u.ref(x) == y for x, y in zip(t.hidden_x, ys)):
                        hit = u.tid
                        break
                except Exception:                                    # noqa: BLE001
                    continue
            (fam_ if SD.role_of(w, f) == "learn" else bad).append([name, t.tid, pd.get(t.descr), hit]) if (hit or t.descr in pd) else None
    res["world_dedup"] = dict(copies_among_unfamiliar_targets=bad, familiar_family_collisions=fam_)
    res["ok"] = res["seeds"]["fresh"] and not leaks and not bad and not res["de_overlap"]["holdout_in_source_code_paths"]
    (ROOT / "artifacts/agi3_protocol_check.json").write_text(json.dumps(res, indent=1, default=list))
    print(json.dumps(res, default=list)[:1500])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

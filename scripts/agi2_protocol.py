"""Phase 2 protocol checks (NOT LOCKED; generators and references only - no learner).  python scripts/agi2_protocol.py
1 seeds: Phase 2 ranges fresh (above every registered range and every spent seed), disjoint, one-use set;
2 isolation: no sampled Phase 2 source / admission / rollout / source-meta task contains a withheld-family mechanism, a
  C / E mechanism, or an untouched C5 / C6 / E5 / E6 mechanism (hist / rays / mediate / mix);
3 dedup: every unfamiliar target (withheld, ce_fresh, untouched, panel) vs the sampled pool: identical descriptor or
  behavioural identity on all 30 hidden inputs fails the check (familiar learning-family panel tasks are listed only).
-> artifacts/agi2_protocol_check.json"""
import json, re, sys
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign2 import seeds as SD, agent_loop as AL
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agi_protocol import PREFIX  # noqa: E402
PREFIX = dict(PREFIX, C5=("hist",), C6=("rays",), E5=("mediate",), E6=("mix",))


def mech(d):
    return set(re.findall(r"([a-z_]+)\[", d))


def main():
    res = {}
    mine = {k: v for k, v in R.REGISTRY.items() if k[0] == "agi2"}
    others = [v for k, v in R.REGISTRY.items() if k[0] != "agi2"]
    spent = max((max(x.get("seeds") or [0]) for x in R._spent()), default=0)
    lo = min(v.start for v in mine.values())
    res["seeds"] = dict(min_phase2=lo, max_other_stop=max(v.stop for v in others), max_spent=spent,
                        fresh=lo >= max(max(v.stop for v in others), spent + 1), one_use=sorted(map(list, SD.ONE_USE)))
    learn = set()
    for w, f in SD.LEARN:
        learn |= set(PREFIX[f])
    pool = []
    for rep in range(3):
        for key, off, n in (("source", 1000 * rep, 160), ("source_meta", 300 * rep, 64)):
            base = SD.RANGES[("agi2", key)].start + off
            cells = [(w, f, lv) for (w, f) in SD.LEARN for lv in (1, 2, 3, 4)]
            pool += [AL.task_of(*cells[i % 32], base + i) for i in range(n)]
        for key, off in (("admission", 300 * rep), ("rollout", 300 * rep)):
            base = SD.RANGES[("agi2", key)].start + off
            for i in range(60):
                s = base + i
                w, f = SD.ADMIT[s % 4]
                pool.append(AL.task_of(w, f, (s % 4 + s // 4) % 2 + 1 if key == "admission" else s % 2 + 1, s))
    leaks = [t.tid for t in pool if mech(t.descr) - learn - set(PREFIX[t.family])]
    res["isolation"] = dict(pool=len(pool), tasks_with_foreign_mechanisms=leaks)
    by_sig = {}
    for t in pool:
        by_sig.setdefault((t.mech.sig, t.mech.out), []).append(t)
    pd = {t.descr: t.tid for t in pool}
    bad, familiar = [], []
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
            if SD.role_of(w, f) == "learn":
                if hit or t.descr in pd:
                    familiar.append([name, t.tid, pd.get(t.descr), hit])
            elif hit or t.descr in pd:
                bad.append([name, t.tid, pd.get(t.descr), hit])
    res["dedup"] = dict(copies_among_unfamiliar_targets=bad, familiar_family_collisions=familiar)
    res["ok"] = res["seeds"]["fresh"] and not leaks and not bad
    (ROOT / "artifacts/agi2_protocol_check.json").write_text(json.dumps(res, indent=1, default=list))
    print(json.dumps(res, default=list)[:1500])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

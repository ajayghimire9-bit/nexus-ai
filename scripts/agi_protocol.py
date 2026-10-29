"""Multi-world campaign protocol checks (NOT LOCKED; no learner runs here).
  python scripts/agi_protocol.py check    -> artifacts/agi_protocol_check.json
1 seed hygiene: the campaign ranges are fresh (above every registered range and every spent seed) and pairwise disjoint;
2 structural isolation: no sampled source / admission task contains a mechanism of a withheld family or of World C / E;
3 anti-leakage deduplication: every target task (withheld 16, held-out 32, retention 8, improver panel 12) is compared
  with a sample of the source / admission pool (3 reps x 32 learning cells x 10 seeds + 3 x 120 admission tasks):
  (a) identical mechanism descriptor (a renamed copy), (b) behavioural identity: the source reference reproduces the target
  reference on every one of the target's 30 hidden inputs (same input / output types). A hit on a withheld-family or
  held-out-world target fails the check. Retention and improver-panel tasks of LEARNING families are familiar by design;
  their parameter collisions with a possible source instance are listed separately (disclosed, not a failure).
Only task generators and references run (no learner, no outcome)."""
import json, re, sys
from pathlib import Path
from nexus import seed_registry as R
from nexus.campaign import seeds as SD, agent_loop as AL
ROOT = Path(__file__).resolve().parents[1]
PREFIX = {"A1": ("filter",), "A2": ("group",), "A3": ("semijoin", "join"), "A4": ("project", "route"),
          "B1": ("window",), "B2": ("latch", "hysteresis"), "B3": ("since", "cooldown"), "B4": ("registers",),
          "C1": ("stats",), "C2": ("transform",), "C3": ("restore",), "C4": ("act",), "D1": ("reach",), "D2": ("unlock",),
          "D3": ("fuel",), "D4": ("plan",), "E1": ("switch", "resp"), "E2": ("do", "resp"), "E3": ("chain", "lag"),
          "E4": ("control",), "F1": ("arith",), "F2": ("guard",), "F3": ("fold",), "F4": ("compose",)}


def mech(d):
    return set(re.findall(r"([a-z_]+)\[", d))


def check():
    res = {}
    spent_max = max((max(x.get("seeds") or [0]) for x in R._spent()), default=0)
    mine = {k: v for k, v in R.REGISTRY.items() if k[0] == "agi"}
    others = [v for k, v in R.REGISTRY.items() if k[0] != "agi"]
    res["seeds"] = dict(min_campaign=min(v.start for v in mine.values()), max_other_stop=max(v.stop for v in others),
                        max_spent=spent_max, fresh=min(v.start for v in mine.values()) >= max(max(v.stop for v in others), spent_max + 1),
                        one_use=sorted(map(list, SD.ONE_USE)))
    pool = []
    for rep in range(3):
        base = SD.RANGES[("agi", "source")].start + 1000 * rep
        cells = [(w, f, lv) for (w, f) in SD.LEARN for lv in (1, 2, 3, 4)]
        for i, c in enumerate(cells):
            for j in range(10):
                pool.append(AL.task_of(*c, base + (i * 10 + j) % 1000))
        abase = SD.RANGES[("agi", "admission")].start + 300 * rep
        lin = AL.Lineage("chk", None, 1, ROOT / "artifacts/agi_dev/tmp", iter(()), iter(range(abase, abase + 120)), rng_key="chk")
        pool += [lin._adm_task() for _ in range(120)]
    banned = set()
    for w, f in SD.WITHHELD + SD.HELDOUT:
        banned |= set(PREFIX[f])
    learn = set()
    for w, f in SD.LEARN:
        learn |= set(PREFIX[f])
    leaks = [t.tid for t in pool if mech(t.descr) - learn - set(PREFIX[t.family])]
    res["structural"] = dict(pool=len(pool), tasks_with_foreign_mechanisms=leaks, banned=sorted(banned))
    P = SD.panels()
    targets = []
    for name, lst in P.items():
        for (w, f, lv, s, panel) in lst:
            role = SD.role_of(w, f)
            targets.append((name, AL.task_of(w, f, lv, s)))
    by_sig = {}
    for t in pool:
        by_sig.setdefault((t.mech.sig, t.mech.out), []).append(t)
    dup_descr, dup_behav, familiar = [], [], []
    pool_descr = {t.descr: t.tid for t in pool}
    for name, t in targets:
        fam_known = SD.role_of(t.world, t.family) == "learn"          # retention / panel tasks of learning families
        ys = [t.ref(x) for x in t.hidden_x]
        hit = None
        for u in by_sig.get((t.mech.sig, t.mech.out), []):
            try:
                if all(u.ref(x) == y for x, y in zip(t.hidden_x, ys)):
                    hit = u.tid
                    break
            except Exception:                                      # noqa: BLE001
                continue
        if fam_known:
            if t.descr in pool_descr or hit:
                familiar.append([name, t.tid, pool_descr.get(t.descr), hit])
            continue
        if t.descr in pool_descr:
            dup_descr.append([t.tid, pool_descr[t.descr]])
        if hit:
            dup_behav.append([t.tid, hit])
    res["dedup"] = dict(targets=len(targets), unfamiliar_targets=sum(SD.role_of(t.world, t.family) != "learn" for _, t in targets),
                        descriptor_copies=dup_descr, behavioural_copies=dup_behav,
                        familiar_family_parameter_collisions=familiar)
    res["ok"] = res["seeds"]["fresh"] and not leaks and not dup_descr and not dup_behav
    p = ROOT / "artifacts/agi_protocol_check.json"
    p.write_text(json.dumps(res, indent=1, default=list))
    print(json.dumps({k: (v if k != "structural" else {kk: vv for kk, vv in v.items() if kk != "banned"}) for k, v in res.items()},
                     default=list)[:3000])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(check())

"""Multi-world campaign Stage 1 development checks (NOT LOCKED; agi/dev seeds only).
  python scripts/agi_dev.py worlds            world self-checks on all 24 families x 4 levels (World C / E included, but
                                              only the generators, references and verifiers run there - never a learner)
  python scripts/agi_dev.py solve N [CAP]     empty-state learner on N dev tasks per source-world family (A, B, D, F)
  python scripts/agi_dev.py timing            per-episode overhead calibration on source-world dev tasks (for the plan)
Writes artifacts/agi_dev/<mode>.json."""
import json, random, sys, time
from pathlib import Path
from nexus.campaign import seeds as SD, agent_loop as AL, improver as I, state as ST, substrate as S
from nexus.campaign.worlds import WORLDS, FAMILIES, verify, make_task
from nexus.campaign.worlds import world_f_programs as WF
from nexus.campaign.worlds.base import exhaustive_lists
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi_dev"
DEV = SD.RANGES[("agi", "dev")]


def worlds():
    res, bad = [], []
    k = 0
    for w, fams in FAMILIES.items():
        for f in fams:
            for lv in (1, 2, 3, 4):
                s = DEV.start + k
                k += 1
                role = SD.role_of(w, f)
                t = make_task(w, f, lv, s, role, SD.partners_for(w, f, role))
                t2 = make_task(w, f, lv, s, role, SD.partners_for(w, f, role))
                det = [t.ref(x) for x in t.hidden_x] == [t2.ref(x) for x in t2.hidden_x] and t.descr == t2.descr
                ref_ok = verify(t, t.ref)["ok"]
                const = verify(t, lambda x: ())["ok"] or verify(t, lambda x: 0)["ok"]
                row = dict(tid=t.tid, descr=t.descr, protocol=t.mech.protocol, verify_kind=t.mech.verify_kind,
                           n_train=len(t.train_x), q_budget=t.q_budget, deterministic=det, reference_passes=ref_ok,
                           constant_passes=const, n_verify=verify(t, t.ref)["n"])
                res.append(row)
                if not det or not ref_ok or const:
                    bad.append(row)
    # interpreter vs independent Python reference (World F intended programs, every exhaustive input)
    interp = []
    for f in FAMILIES["F"]:
        for j in range(25):
            py, ast = WF.intended(f, random.Random(f"interp|{f}|{j}"))
            xs = [(a, b) for a in range(10) for b in range(10)] if f in ("F1", "F2") else \
                exhaustive_lists(3, range(10))
            sig = ("i", "i") if f in ("F1", "F2") else ("l",)
            S.check_types(ast, sig)
            mism = sum(S.run(ast, x) != (py(*x) if f in ("F1", "F2") else py(x[0])) for x in xs)
            interp.append(dict(family=f, src=S.to_src(ast), mismatches=mism))
    doc = dict(n=len(res), bad=bad, rows=res, interpreter=interp, interp_bad=[r for r in interp if r["mismatches"]],
               split=SD.SPLIT)
    save("worlds", doc)
    print("tasks", len(res), "bad", len(bad), "interp checks", len(interp), "interp mismatches",
          sum(r["mismatches"] > 0 for r in interp))
    for r in bad[:10]:
        print("BAD", r)
    return 1 if bad or doc["interp_bad"] else 0


def solve(n, cap=None):
    cap = float(cap or AL.CAP_S)
    st = ST.empty_state(I.M0)
    rows = []
    k = 0
    for w in ("A", "B", "D", "F"):
        for f in FAMILIES[w]:
            for j in range(int(n)):
                s = DEV.start + 500 + k
                k += 1
                lv = j % 4 + 1
                role = SD.role_of(w, f)
                t = make_task(w, f, lv, s, role, SD.partners_for(w, f, role))
                r = AL.episode(t, st, cap)
                r.pop("_ast")
                r["descr"] = t.descr
                rows.append(r)
                print(t.tid, t.descr[:40], r["outcome"], "solved" if r["solved"] else "", "SILENT" if r["silent"] else "",
                      r["cpu_s"], r["n_cands"], r["level_reached"], r["queries"], r["prog"], flush=True)
    summ = dict(n=len(rows), solved=sum(r["solved"] for r in rows), silent=sum(r["silent"] for r in rows),
                mean_cpu=round(sum(r["cpu_s"] for r in rows) / len(rows), 3))
    save(f"solve_cap{cap}", dict(summary=summ, rows=rows))
    print(summ)


def timing():
    """Overhead per episode (task build + view + verify) beyond the solver CPU, on source-world dev tasks."""
    st = ST.empty_state(I.M0)
    over = []
    k = 0
    for w in ("A", "B", "D", "F"):
        for f in FAMILIES[w]:
            for lv in (1, 4):
                s = DEV.start + 900 + k
                k += 1
                c0 = time.process_time()
                role = SD.role_of(w, f)
                t = make_task(w, f, lv, s, role, SD.partners_for(w, f, role))
                r = AL.episode(t, st, AL.CAP_S)
                over.append(time.process_time() - c0 - r["cpu_s"])
    doc = dict(n=len(over), overhead_mean=round(sum(over) / len(over), 4), overhead_max=round(max(over), 4))
    save("timing", doc)
    print(doc)


def save(name, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str))
    tmp.replace(p)


def _main():
    m = sys.argv[1]
    if m != "arms":
        sys.exit({"worlds": worlds, "solve": solve, "timing": timing}[m](*sys.argv[2:]) or 0)


def arms():
    """Placebo / ablation construction on the dev Full and Random states (no target data)."""
    import agi_eval as E
    out = {}
    for name in ("Full_r2", "Random-Proposal_r2"):
        st = ST.from_json(json.loads((OUT / f"src/{name}.json").read_text())["state"])
        pl = E.placebo_state(st, 2)
        out[name] = [dict(id=k, orig=st[t][k]["src"], placebo=pl[t][k]["src"], size=(S.size(st[t][k]["body"]),
                                                                                    S.size(pl[t][k]["body"])))
                     for t in ("L", "R") for k in st[t]]
        t = make_task("A", "A2", 1, DEV.start + 990, "learn", SD.partners_for("A", "A2", "learn"))
        r = AL.episode(t, pl, AL.CAP_S)
        out[name + "_episode"] = r["outcome"]
    save("arms", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    _main()
    if sys.argv[1] == "arms":
        arms()

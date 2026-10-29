"""Phase 7 Stage 1 reachability diagnostic + timing rehearsal (NOT LOCKED; DEVELOPMENT DATA ONLY: agi7de/dev seeds,
Tiers 1-2 + composites; no Tier 3, no source / pool / target seed).  python scripts/agi7_diag.py N_PROJECTS OUT.json

Per project:
  p6      Phase 6 search (pipeline6.search, 1.0 s, whole, skills off)
  s7      Phase 7 archive search (search7, FIXED_W, work budgets W_LO / W_HI, whole and decompose)
  witness a REFERENCE-ASSISTED greedy witness (development diagnostic only - it reads the hidden truth specs; it never
          enters any learner memory and is never counted as an invented method): from the legacy pipeline, repeatedly
          apply the operator candidate that most increases structural agreement with the truth, to depth 8; success =
          the hidden evaluator accepts the witness. Each witness step is classified by the search score of its parent
          and child: improvement / neutral / worse / regression - a witness with a non-improving step is a pipeline that
          Phase 6's retention rule (keep only improving or check-passing children) could not reach along that route.
A witness failure is NOT proof of inexpressibility (greedy, depth-bounded)."""
import json, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import engines6 as E, ir6, pipeline6 as P6, world6 as W6  # noqa: E402
from nexus.de_phase7 import ops7, search7 as S7, seeds7 as S, world7 as W7  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
DEV_SPECS = [dict(paradigm="P1", engine="sqlite"), dict(paradigm="P2", engine="duckdb"), dict(paradigm="P3", engine="sqlite"),
             dict(paradigm="P4", engine="duckdb"), dict(paradigm="P5", engine="sqlite"), dict(paradigm="P6", engine="duckdb"),
             dict(paradigm="P7", engine="duckdb"), dict(paradigm="X1"), dict(paradigm="X2"), dict(paradigm="P1", engine="spark"),
             dict(paradigm="P4", engine="sqlite"), dict(paradigm="P6", engine="sqlite"), dict(paradigm="P2", engine="sqlite"),
             dict(paradigm="P5", engine="duckdb"), dict(paradigm="P3", engine="duckdb"), dict(paradigm="P7", engine="sqlite"),
             dict(paradigm="X1"), dict(paradigm="X2"), dict(paradigm="P4", engine="spark"), dict(paradigm="P6", engine="spark")]


def conj(f):
    if not f:
        return []
    return conj(f[1]) + conj(f[2]) if f[0] == "and" else [json.dumps(f)]


def agree(spec, truth):
    a = 0.0
    for k in set(spec) | set(truth):
        if k == "outputs":
            a += sum(1 for o in spec.get(k, []) if o in truth.get(k, [])) - 0.5 * sum(1 for o in spec.get(k, []) if o not in truth.get(k, []))
        elif k == "filter":
            cs, ct = conj(spec.get(k)), set(conj(truth.get(k)))
            a += len(set(cs) & ct) - 0.5 * len(set(cs) - ct) - 0.5 * (len(cs) - len(set(cs)))
        elif isinstance(spec.get(k), dict) and isinstance(truth.get(k), dict):
            ks = set(spec[k]) | set(truth[k])
            a += sum(spec[k].get(x) == truth[k].get(x) for x in ks) / len(ks)
        else:
            a += 1.0 if spec.get(k) == truth.get(k) else 0.0
    return a


def ok_hidden(p, specs):
    files = [ir6.lower(s, st["target_lang"]) for s, st in zip(specs, p["stages"])]
    try:
        return W6.evaluate6(p, files)["ok"]
    except Exception:                                          # noqa: BLE001
        return False


def witness(inv, p, truths, max_depth=8):
    specs, steps = list(inv.legacy), []
    ev = inv.run(specs, True)
    for _ in range(max_depth):
        if ok_hidden(p, specs):
            return dict(found=True, depth=len(steps), steps=steps)
        best = None
        for k in range(len(specs)):
            base = agree(specs[k], truths[k])
            for op in E.OPS:
                for s2, prm in E.candidates(op, specs[k], inv.dom(k, specs)):
                    g = agree(s2, truths[k]) - base
                    if g > 1e-9 and (best is None or g > best[0]):
                        best = (g, k, op, prm, s2)
        if best is None:
            return dict(found=False, depth=len(steps), steps=steps, note="no candidate increases agreement")
        _, k, op, prm, s2 = best
        specs = list(specs)
        specs[k] = s2
        ev2 = inv.run(specs, True)
        gain = ev2["score"] - ev["score"]
        lost = set(ev["passed"]) - set(ev2["passed"])
        kind = "error" if ev2.get("error") else "regression" if lost and gain < 0 else "improvement" if gain > 0 or ev2["ok"] else \
            "neutral" if abs(gain) < 1e-9 else "worse"
        steps.append(dict(stage=k, op=op, kind=kind, gain=round(gain, 3)))
        ev = ev2
    return dict(found=ok_hidden(p, specs), depth=len(steps), steps=steps)


def lang(extended):
    """Phase 6 operator language (extended=False) or with the disclosed Phase 7 dedup-on-id parameterisation."""
    E.candidates = ops7.candidates if extended else ops7._ORIG


def judge(p, r):
    if r["outcome"] != "submitted":
        return r["outcome"]
    return "verified" if ok_hidden(p, r["specs"]) else "wrong"


def main(n, out):
    W.SparkCode.warm()
    rows = []
    base = S.RANGES[("agi7de", "dev")].start
    for i, spec in enumerate(DEV_SPECS[:int(n)]):
        t = time.time()
        try:
            p = W7.make_project7(spec, base + i, ROOT / "var/agi7_ws/dev/diag")
            inv = P6.Inv6(p)
        except Exception as e:                                  # noqa: BLE001
            rows.append(dict(spec=spec, error=f"build/lift: {str(e)[:100]}"))
            continue
        tg = time.time() - t
        truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
        row = dict(pid=p["pid"], spec=spec, faults=p["faults"], n_stages=len(p["stages"]), gen_s=round(tg, 2))
        lang(False)
        t = time.time()
        r6 = P6.search(P6.Inv6(p), {}, 1.0, mode="whole", use_skills=False)
        row["p6"] = dict(outcome=judge(p, r6), wall=round(time.time() - t, 2), runs=sum(r6["runs"].values()))
        row["witness_phase6_language"] = witness(P6.Inv6(p), p, truths)
        lang(True)
        t = time.time()
        r6x = P6.search(P6.Inv6(p), {}, 1.0, mode="whole", use_skills=False)
        row["p6_ext"] = dict(outcome=judge(p, r6x), wall=round(time.time() - t, 2), runs=sum(r6x["runs"].values()))
        for wb, mode in ((1500, "whole"), (4000, "whole"), (4000, "decompose")):
            if True:
                inv7 = P6.Inv6(p)
                t = time.time()
                r7 = S7.search(inv7, {}, work_budget=wb, wall_cap=10.0, mode=mode, use_skills=False)
                row[f"s7_{mode}_{wb}"] = dict(outcome=judge(p, r7), wall=round(time.time() - t, 2), work=r7["work"], kinds=r7.get("solution_kinds"),
                                              events=r7["events"], exhausted=r7["work_exhausted"], partial=r7.get("best_partial"))
        t = time.time()
        row["witness"] = witness(P6.Inv6(p), p, truths)
        row["witness"]["wall"] = round(time.time() - t, 2)
        rows.append(row)
        print(i, p["pid"][:40], row["p6"]["outcome"], row["p6_ext"]["outcome"], {k: (v["outcome"], v["wall"], v["work"]) for k, v in row.items() if k.startswith("s7")},
              "witness6", row["witness_phase6_language"]["found"], "witness7", row["witness"]["found"], [s["kind"][0] for s in row["witness"]["steps"]],
              flush=True)
        if time.time() - T0 > float(sys.argv[3] if len(sys.argv) > 3 else 1e9):
            print("time limit: stopping early", flush=True)
            break
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(dict(rows=rows, wall=round(time.time() - T0, 1)), indent=1, default=str))
    print("wall", round(time.time() - T0, 1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

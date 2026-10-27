"""Checker v3 validation: verdict identity with Checker v2 on every existing Wave 31 task (NOT LOCKED).
--part inc1 | inc2 | inc3. Evidence per task: matched scope with the teacher as candidate; for increments 1-2 also
the macro scope (G_P + seq library built from that seed/fold's source teachers) with a first-fit candidate.
Records v2 and v3 retired instructions per check (evaluator process, OS counter)."""
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tests/support"))
from v3_diff import FIELDS
from nexus import checker_kernel_v2 as V2, checker_kernel_v3 as V3
from nexus.wave31_evaluator import instructions, ledger_append
from nexus import wave31_grammar as G, wave31_tasks as T, wave31_solver as S, wave31_ir as W1

DEV, ADM, VAL3 = (761, 762, 763, 764, 765), (7101, 7102, 7103, 7104, 7105), (7106, 7107, 7108, 7109, 7110)


def evid(t, tools, depth, cand=None):
    cand = cand or t["teacher"]
    a = V2.run(cand, t["query"])[0]
    return {"public": t["public"], "query": t["query"], "claimed_answer": a, "candidate": cand,
            "scope": {"kind": "exhaustive", "tools": tools, "max_depth": depth}, "lemmas": [], "trace": {}}


def compare(ev, stats, tag):
    pid = os.getpid()
    i0 = instructions(pid); a = V2.check(dict(ev, checker_version=2)); i1 = instructions(pid)
    b = V3.check(dict(ev, checker_version=3)); i2 = instructions(pid)
    ok = all(a.get(f) == b.get(f) for f in FIELDS)
    s = stats.setdefault(tag, {"n": 0, "identical": 0, "v2_instr": 0, "v3_instr": 0, "labels": {}, "mismatch": []})
    s["n"] += 1; s["identical"] += ok; s["v2_instr"] += i1 - i0; s["v3_instr"] += i2 - i1
    s["labels"][a["label"]] = s["labels"].get(a["label"], 0) + 1
    if not ok and len(s["mismatch"]) < 5:
        s["mismatch"].append({f: (a.get(f), b.get(f)) for f in FIELDS if a.get(f) != b.get(f)})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--part", required=True); a = ap.parse_args()
    t0 = time.perf_counter(); stats = {}
    if a.part == "inc1":
        for s in DEV:
            src, tgt = W1.stream(s, W1.SOURCE_DOMAINS), W1.stream(s, W1.TARGET_DOMAINS)
            lib, _ = W1.library_from([t["teacher"] for t in src])
            for t in src + tgt:
                prims = W1.primitives(t["public"], t["query"])
                if all(V2.key(x) in {V2.key(p) for p in prims} for x in t["teacher"]) and len(t["teacher"]) <= 4:
                    compare(evid(t, prims, 4), stats, "inc1_matched_d4")
                tools = prims + lib
                c = S.first_fit(t["public"], t["query"], tools, 2, {})
                if c is not None:
                    compare(evid(t, tools, 2, [tools[i] for i in c]), stats, "inc1_macro_d2")
    elif a.part == "inc2":
        for s in DEV + ADM:
            for h in G.DOMAINS:
                src, tgt = T.source_stream(s, h), T.target_stream(s, h)
                lib = S.build([t["teacher"] for t in src], f"{s}:{h}")["useful"]
                adv, _ = T.adversarial_stream(s, h, lib)
                for t in src + tgt + adv:
                    compare(evid(t, G.G_P, 3), stats, "inc2_matched_d3")
                    tools = G.G_P + lib
                    c = S.first_fit(t["public"], t["query"], tools, 2, {})
                    if c is not None:
                        compare(evid(t, tools, 2, [tools[i] for i in c]), stats, "inc2_macro_d2")
    else:
        seeds = DEV if a.part == "inc3_dev" else VAL3
        for s in seeds:
            for h in G.DOMAINS:
                for t in T.source_stream3(s, h) + T.target_stream3(s, h):
                    compare(evid(t, G.G_P, 4), stats, "inc3_matched_d4")
    wall = time.perf_counter() - t0
    ledger_append(dict(run=f"wave31-v3-identity-{a.part}", wall_s=wall, status="COMPLETE"))
    out = ROOT / f"artifacts/checker_v3_identity_{a.part}.json"
    out.write_text(json.dumps(stats, sort_keys=True, default=repr))
    for k, v in stats.items():
        print(k, "n", v["n"], "identical", v["identical"], "labels", v["labels"],
              "v2/v3 instr %.1f" % (v["v2_instr"] / max(1, v["v3_instr"])), v["mismatch"][:2])
    print("wall", round(wall, 1))


if __name__ == "__main__":
    main()

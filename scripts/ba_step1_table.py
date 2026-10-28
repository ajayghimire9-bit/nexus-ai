"""Forensic False-Acceptance Table from artifacts/ba_dev/step1_*.json (NOT LOCKED).  python scripts/ba_step1_table.py [--md]"""
import collections, json, sys
from pathlib import Path
ART = Path(__file__).resolve().parents[1] / "artifacts/ba_dev"


def rows():
    out = []
    for r in json.loads((ART / "step1_ocean.json").read_text()):
        out.append(("ocean ep_train", r["seed"], "random", r["diag"]))
    seen = set()
    for r in json.loads((ART / "step1_energy.json").read_text()):
        if r.get("diag"):
            out.append(("energy edev", r["seed"], r["arm"], r["diag"]))
    for f in sorted(ART.glob("step1_platform_*.json")):
        d = json.loads(f.read_text())
        for l in d["learners"]:
            if l.get("diag"):
                out.append((f"platform {d['result']['fault']}" + (" (pre-rev arm)" if "strong" in f.name else ""), d["result"]["project"],
                            f"learner {l['learner']}", l["diag"]))
    return out


def fmt(src, seed, arm, d):
    regs = "-"
    if d.get("before"):
        regs = f"ref {d['before']['ref']}→{d['after']['ref']}; cand {d['before']['learned']}→{d['after']['learned']}"
    fault = d.get("detail", "")
    if d["kind"] == "value" and d.get("fault_transition"):
        q, a = d["fault_transition"]
        fault = f"mode_{q} --{a}--> reg update `{d['learned_update']}` (ref {d['ref_update']} in ref mode {d['ref_mode']}); seen {d['delay']} event(s) later"
    return [src, str(seed), arm, " ".join(d["w_min"]), d["kind"], regs, fault, d["why_missed"]["reason"], d["origin"]]


if __name__ == "__main__":
    R = rows()
    H = ["set", "seed", "arm", "w_min", "error", "registers before→after (fault event)", "wrong transition / update", "why missed", "origin"]
    if "--md" in sys.argv:
        print("| " + " | ".join(H) + " |\n|" + "---|" * len(H))
        for r in R:
            print("| " + " | ".join(x.replace("|", "/") for x in fmt(*r)) + " |")
    else:
        for r in R:
            print(" | ".join(fmt(*r)))
    print()
    print("why missed:", dict(collections.Counter(d["why_missed"]["reason"] for *_, d in R)))
    print("origin:", dict(collections.Counter(d["origin"] for *_, d in R)))
    print("delay:", dict(collections.Counter(d.get("delay") for *_, d in R)))

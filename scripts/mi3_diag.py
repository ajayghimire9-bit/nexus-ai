"""MI-3 Stage 1 diagnosis of the shared acceptance gap (NOT LOCKED).  python scripts/mi3_diag.py SEED FAMILY [ARM]
Rebuilds an episode, runs the arm's full-space stage (default A5: the human reference, which can express acc + c), and prints
the reference machine, the accepted machine, the acceptance check's probes and the first held-out divergence. Exposed or dev
seeds only (26801 = the exposed MI-2 regression case); the reference machine is read here for DIAGNOSIS, never by a learner."""
import json, sys
from collections import Counter
from nexus import mi_ocean as M, mi_learner as ML, mi2_learner as M2, u5_statesplit as SP
from nexus import oop_synthesizer as S


def main(seed, fam, arm="A5"):
    ep = M.Episode(int(seed), fam)
    m = ep.machine
    print("REFERENCE modes", m["modes"], "regs", m["regs"], "base", m.get("base"))
    for (q, s), q2 in sorted(m["delta"].items()):
        ups = [S.src(m["upd"][i][(q, s)]) if (q, s) in m["upd"][i] else "-" for i in range(m["regs"])]
        print(f"  ({q},{s}) -> {q2}  lam {m['lam'][(q, s)]}  upd {ups}")
    kinds = Counter(e["kind"] for e in ep.train)
    print("train events", len(ep.train), "keys", len({e['key'] for e in ep.train}), "kinds", dict(kinds))
    dom = ML.lpl_domain(M2.A5_PROG) if arm == "A5" else ML.baseline_domain
    r, st = M2.full_space(ep, dom, ep.seed, cap_s=15.0)
    print("FULL_SPACE", {k: v for k, v in st.items() if k != "domain_sizes"})
    if r is None:
        return
    lm = r["machine"]
    print("ACCEPTED n", lm["n"], "regs", [{"field": rg.get("field"), "init": rg.get("init"),
                                            "upd": {str(t): S.src(g) for t, g in rg["upd"].items()}} for rg in lm["regs"]])
    print("scope", json.dumps(r["scope"], default=str)[:600])
    cls = SP.compile_class(r["source"], r["name"])
    want, got = M.run(m, ep.test), SP.run_class(cls, ep.test)
    nbad = 0
    for j, (e, g, w) in enumerate(zip(ep.test, got, want)):
        if not SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))):
            nbad += 1
            if nbad <= 3:
                hist = [(x["kind"], x.get("v")) for x in ep.test[:j + 1] if x["key"] == e["key"]]
                print(f"DIVERGE event {j} key {e['key']} history {hist}\n   want {w}\n   got  {g}")
    print("diverging events", nbad, "of", len(ep.test))
    # Did the training/probe streams ever exercise the divergent pattern? Per-key kind sequences in training:
    seqs = Counter()
    for k in {e["key"] for e in ep.train}:
        seqs[tuple(x["kind"] for x in ep.train if x["key"] == k)] += 1
    print("train per-key kind sequences (top 12):", seqs.most_common(12))


if __name__ == "__main__":
    main(*sys.argv[1:])

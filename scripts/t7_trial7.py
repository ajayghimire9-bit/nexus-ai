"""Trial 7 (NOT LOCKED).  python scripts/t7_trial7.py LINEAGE | decide
Lineage k (k = 0..4; seeds differ in genome init and task samples): generations on L, C, I (7 families x 2 t7/tsrc seeds
each; 2 s per task): wipe solutions -> decode genome -> solve (certified traces only) -> distill. Then regrowth on the
UNSEEN energy domain (7 families x 3 t7/theld seeds, one ordered stream; costs updated online from certified solutions;
2 s per task) for every arm:
  Evolved_64KB_Genome  the lineage's genome after 3 generations
  MAML_Style_Start     Reptile over L, C, I: the cost table moved toward each domain's certified-trace table in turn
  Hand_Written_Defaults uniform costs (default_config)
  Random_Genome        an untrained genome (random weights, uniform prior)
  Shuffled_Experience  the same 3-generation pipeline but distilled on traces with operators permuted (placebo)
  Full_Inheritance     no bottleneck: all certified solutions of L, C, I kept; costs from all their counts
Metric: CPU to reach the target (>= 80% of the energy stream solved, counted in stream order) and total solves.
KEEP iff the evolved genome reaches the target with less CPU than BOTH MAML and Defaults in >= 3 of 5 lineages, with
genome size <= 64 KB."""
import json, random, sys, time
sys.path.insert(0, "scripts")
from u5_common import ROOT, K, W
from nexus import t7_seeds, t7_world, t7_genome as GN, seed_registry as R  # noqa: F401
from collections import Counter
import numpy as np
ART = ROOT / "artifacts/t7_dev"
DOM = {"L": "L", "C": "C", "I": "I", "E": "E"}
src_seeds, held = list(R.REGISTRY[("t7", "tsrc")]), list(R.REGISTRY[("t7", "theld")])


def suite(prefix, seeds):
    return [W.Task(f"{f}#{s}", f, s) for f in W.FAMILIES if f[0] == prefix for s in seeds]


def cfg_of(ops, leaf):
    c = K.default_config("count")
    c["op_cost"], c["leaf_cost"] = dict(ops), dict(leaf)
    return c


def certified(tasks, cfg):
    sols = []
    for t in tasks:
        node, st, _ = K.solve_hybrid(t.train, t.y_train, cfg, [], 2.0)
        if node is not None and all(K._ok(K._safe_ev(node, e), y) for e, y in zip(t.train, t.y_train)):
            sols.append(node)
    return sols


def regrow(cfg, stream, target=0.8):
    counts, cpu, ok, reach = Counter(), 0.0, 0, None
    for i, t in enumerate(stream):
        node, st, _ = K.solve_hybrid(t.train, t.y_train, cfg, [], 2.0)
        cpu += st["cpu_s"]
        if node is not None and W.correct_on(t, node) == 1.0:
            ok += 1
            counts.update(K.op_counts([node]))
            cfg = dict(cfg, op_cost=dict(zip(GN.OPS, GN.target_costs(counts)[:len(GN.OPS)])))
        if reach is None and ok >= target * len(stream):
            reach = round(cpu, 3)
    return dict(solved=ok, cpu_s=round(cpu, 3), cpu_to_target=reach)


if sys.argv[1] != "decide":
    k = int(sys.argv[1])
    rnd = random.Random(f"t7-lineage-{k}")
    t0 = time.process_time()
    gens = {d: suite(d, rnd.sample(src_seeds, 2)) for d in "LCI"}
    descs = {d: GN.descriptor(ts) for d, ts in gens.items()}
    G, Gs = GN.Genome(seed=k), GN.Genome(seed=k)
    reptile = np.array([1.0] * GN.OUT)
    allsols = []
    for d in "LCI":
        ops, leaf = G.decode(descs[d])
        sols = certified(gens[d], cfg_of(ops, leaf))                     # wipe: only this generation's certified traces
        allsols += sols
        cnt = K.op_counts(sols)
        tgt = GN.target_costs(cnt)
        G.distill(descs[d], tgt)
        G.prior = [int(round(0.5 * p + 0.5 * q)) for p, q in zip(G.prior, tgt)]      # MDL-rounded symbolic prior
        perm = rnd.sample(GN.OPS, len(GN.OPS))                                        # shuffled-experience placebo
        Gs.distill(descs[d], GN.target_costs(Counter({perm[GN.OPS.index(o)]: c for o, c in cnt.items() if o in GN.OPS})))
        reptile += 0.5 * (np.array(tgt, float) - reptile)
    train_cpu = time.process_time() - t0
    E = suite("E", held[:3])
    rnd.shuffle(E)
    dE = GN.descriptor(E[:5])                                            # descriptor from 5 unlabelled-output E tasks' inputs
    rows = {}
    ops, leaf = G.decode(dE)
    rows["Evolved_64KB_Genome"] = regrow(cfg_of(ops, leaf), E)
    rr = np.clip(np.round(reptile), 1, 4).astype(int)
    rows["MAML_Style_Start"] = regrow(cfg_of(dict(zip(GN.OPS, map(int, rr[:len(GN.OPS)]))), dict(var=int(rr[-3]), key=int(rr[-2]), num=int(rr[-1]))), E)
    rows["Hand_Written_Defaults"] = regrow(K.default_config("count"), E)
    ops, leaf = GN.Genome(seed=100 + k).decode(dE)
    rows["Random_Genome"] = regrow(cfg_of(ops, leaf), E)
    ops, leaf = Gs.decode(dE)
    rows["Shuffled_Experience"] = regrow(cfg_of(ops, leaf), E)
    rows["Full_Inheritance"] = regrow(cfg_of(dict(zip(GN.OPS, GN.target_costs(K.op_counts(allsols))[:len(GN.OPS)])), dict(var=1, key=1, num=1)), E)
    out = dict(lineage=k, genome_bytes=G.size(), genome_params=G.n_params(), train_cpu_s=round(train_cpu, 3), arms=rows)
    (ART / f"t7_lineage{k}.json").write_text(json.dumps(out, indent=1))
    print(k, "bytes", out["genome_bytes"], "params", out["genome_params"], {a: (r["solved"], r["cpu_to_target"], r["cpu_s"]) for a, r in rows.items()}, flush=True)
else:
    L = [json.loads((ART / f"t7_lineage{k}.json").read_text()) for k in range(5)]
    def faster(r, a, b):
        x, y = r["arms"][a]["cpu_to_target"], r["arms"][b]["cpu_to_target"]
        return x is not None and (y is None or x < y)
    wins = sum(faster(r, "Evolved_64KB_Genome", "MAML_Style_Start") and faster(r, "Evolved_64KB_Genome", "Hand_Written_Defaults") for r in L)
    keep = wins >= 3 and all(r["genome_bytes"] <= GN.LIMIT for r in L)
    (ART / "t7.json").write_text(json.dumps(dict(lineages=L, wins_vs_both=wins, verdict="KEPT" if keep else "REJECTED"), indent=1))
    print("wins", wins, "/5", "VERDICT", "KEPT" if keep else "REJECTED")
    for a in L[0]["arms"]:
        print(a, [r["arms"][a]["cpu_to_target"] for r in L], [r["arms"][a]["solved"] for r in L])

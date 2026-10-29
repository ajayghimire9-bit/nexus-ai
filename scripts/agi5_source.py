"""Phase 5 source lineage (NOT LOCKED).  python scripts/agi5_source.py REP N_TRAIN N_VAL [--dev]
Training pass (real execution, sequential memory), validation caches with the frozen memory, automatic policy learning
from F0, development ablations by replay on the validation caches, and the placebo history + placebo policy.
Seeds: seeds5.lineage_block(REP) (dev: agi5de/dev 59400 + 200 REP). Output artifacts/agi5_src/r<REP>.json (never rerun;
--dev writes artifacts/agi5_dev/)."""
import copy, json, random, sys, time
from pathlib import Path
from nexus.de_phase4 import world as W
from nexus.de_phase5 import investigate as IV, lineage5 as L5, policy_learn as PL, seeds5 as S5, world5 as W5
ROOT = Path(__file__).resolve().parents[1]


def summarise(rows):
    return dict(n=len(rows), correct=sum(r["correct"] for r in rows.values()), completed=sum(r["completed"] for r in rows.values()),
                wrong=sum(r["wrong"] for r in rows.values()), questions=sum(r["questions"] for r in rows.values()),
                cost_s=round(sum(r["cost"]["wall_s"] + IV.QUESTION_COST_S * r["cost"]["questions"] for r in rows.values()), 3))


def stored_answer_policy(em):
    """Development ablation: remember ANSWERS instead of a procedure - every decision point is resolved to the boundary
    effect most often correct in the source history (no reading, no question)."""
    return [["search"], ["resolve", "stored_answer"], ["submit_or_abstain"]]


def main(rep, n_train, n_val, *flags):
    rep, n_train, n_val = int(rep), int(n_train), int(n_val)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi5_dev" if dev else "artifacts/agi5_src")
    out.mkdir(parents=True, exist_ok=True)
    if (out / f"r{rep}.json").exists() and not dev:
        raise SystemExit("source lineages are never rerun")
    if dev:
        b = S5.RANGES[("agi5de", "dev")].start + 400 + 200 * rep
        blk = dict(train=range(b, b + 100), val=range(b + 100, b + 180), admit=range(b + 180, b + 200))
    else:
        blk = S5.lineage_block(rep)
    rng = random.Random(f"agi5-src|{rep}|{dev}")
    specs_t = S5.source_specs(n_train)
    rng.shuffle(specs_t)
    specs_v = S5.source_specs(n_val)
    live = IV.Live()
    t0 = time.time()
    root = L5.WS / ("dev" if dev else "src") / f"r{rep}"
    train = [W5.make_project5(sp, blk["train"][i], root / "train") for i, sp in enumerate(specs_t)]
    val = [W5.make_project5(sp, blk["val"][i], root / "val") for i, sp in enumerate(specs_v)]
    log = []
    mem, em, em_so, entries_t = L5.train_pass(train, live, rng, list(blk["admit"]), log)
    t_train = time.time() - t0
    caches = {p["pid"]: PL.build_entry(p, live, mem) for p in val}
    for e in caches.values():
        e.pop("_rec", None)
    # PRIMARY learned procedure: composed automatically from the minimal seed program (not from the human-written F0)
    prog, lib, plog = PL.learn_policy(PL.SEED, val, caches, em, mem, random.Random(f"agi5-pl|{rep}|{dev}"),
                                      history_pids=[p["pid"] for p in train])
    prog_f0, lib_f0, plog_f0 = PL.learn_policy(IV.F0, val, caches, em, mem, random.Random(f"agi5-plf0|{rep}|{dev}"),
                                               history_pids=[p["pid"] for p in train])          # development information
    # development ablations (replay on the validation caches; no target data)
    abl = {}
    for name, (pr, lb, e_) in {"F0+empty_evidence": (IV.F0, {}, IV.empty_evidence()), "F0+evidence": (IV.F0, {}, em),
                               "F0+solved_only_evidence": (IV.F0, {}, em_so), "learned+evidence": (prog, lib, em),
                               "learned+solved_only_evidence": (prog, lib, em_so), "learned_minus_library": (IV.F0, {}, em),
                               "stored_answer_reuse": (stored_answer_policy(em), {}, em), "BEHAVE(newest)": (L5.BEHAVE, {}, em),
                               "SEED": (PL.SEED, {}, em), "learned_from_F0": (prog_f0, lib_f0, em)}.items():
        abl[name] = summarise(PL.score(pr, lb, val, caches, e_, mem))
    # placebo history and the placebo-trained procedure
    t1 = time.time()
    prng = random.Random(f"agi5-placebo|{S5.RANGES[('agi5de', 'placebo')].start + rep}|{dev}")
    em_pl, mem_pl = L5.placebo_history(em, caches, mem, prng)
    caches_pl = {p["pid"]: PL.build_entry(p, live, mem_pl) for p in val}
    for e in caches_pl.values():
        e.pop("_rec", None)
    caches_pl = L5.permute_labels(caches_pl, prng)
    prog_pl, lib_pl, plog_pl = PL.learn_policy(PL.SEED, val, caches_pl, em_pl, mem_pl, random.Random(f"agi5-pl-placebo|{rep}|{dev}"),
                                               history_pids=[p["pid"] for p in train])
    t_pl = time.time() - t1
    cov = {}
    for r in plog:
        if "type" in r:
            c = cov.setdefault(r["type"], dict(proposed=0, executed=0, admitted=0))
            c["proposed"] += r.get("proposed", True) is not False
            c["executed"] += bool(r.get("executed_in_projects"))
            c["admitted"] += bool(r.get("admitted"))
    doc = dict(rep=rep, dev=dev, train=[p["pid"] for p in train], val=[p["pid"] for p in val], mem=mem, evidence=em,
               evidence_solved_only=em_so, policy=prog, library=lib, policy_log=plog, coverage=cov, ablations=abl,
               learned_from_F0=dict(policy=prog_f0, library=lib_f0, log=plog_f0), val_caches=caches,
               placebo=dict(evidence=em_pl, mem=mem_pl, policy=prog_pl, library=lib_pl, policy_log=plog_pl),
               train_log=log, wall=dict(train=round(t_train, 2), placebo=round(t_pl, 2), total=round(time.time() - t0, 2)),
               search_cost=dict(n_live_searches=len(live.search_cache)))
    (out / f"r{rep}.json").write_text(json.dumps(doc, indent=0, default=list))
    print(f"r{rep}", "train", len(train), "verified", sum(x["verified"] for x in log if x["step"] == "train"), "claims", len(em["claim_outcomes"]),
          "trust", em["trust"], "| policy", json.dumps(prog)[:300], "| library", list(lib), "| coverage", cov, "| ablations",
          {k: (v["correct"], v["wrong"], v["questions"], v["cost_s"]) for k, v in abl.items()}, "| wall", doc["wall"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])

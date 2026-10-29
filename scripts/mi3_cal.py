"""MI-3 Stage 2 screening calibration (NOT LOCKED; development data mi3/screen_calibration).
  python scripts/mi3_cal.py run JOB NJOBS     full evaluation of candidates j with j % NJOBS == JOB (resumable, atomic per cand)
  python scripts/mi3_cal.py analyze           staged-schedule simulation, calibration gate, frozen schedule (if passed)
Fixed candidate pool (CANDS, committed before any calibration measurement; 24 procedures): the original seed (LPL transcription)
and the hard-wired baseline A0; frozen MI-1 #17; MI-2 A2 / A3 / A4; A5; A6; 8 random LPL programs; 3 human-written domain
specialists (MUL / ADDC / SUBH, calibration only - disclosed); 2 syntactic duplicates (A5, seed + a no-op statement); 3 known poor
procedures. Pool: 24 episodes = mi3/screen_calibration seed indices 0-7 x MUL / ADDC / SUBH; screen = indices 0-1 of each family.
Every candidate is evaluated on all 24 episodes (cap mi3_search.CAP_S); the staged schedule is simulated from these same per-
episode measurements (screening = the 6 screen episodes' CPU; survivors add the other 18; rejection audits add the other 18 of the
audited candidate), candidates processed in a seeded random order.
TAU menu (frozen): 0.75, 0.5, 0.25 - the chosen TAU is the one with the largest CPU saving among those meeting the gate; none ->
the gate fails. Gate (all required): saving >= 20 %; every top-quartile candidate (full fitness; ties at the boundary all
included) survives or is recovered by the rejection audit; ranking variance (>= 3 distinct full exact counts and < 80 % of
candidates at 0 exact); zero silent errors (accepted incorrect outputs) in every calibration evaluation."""
import json, random, sys, time
from pathlib import Path
from nexus import mi3_seeds, mi3_search as MS, mi_lpl as LP, mi2_learner as M2  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/mi3_cal"
A_, X_ = ["var", "acc"], ["var", "x"]


def b(op, p, q):
    return ["b", op, p, q]


def c(k):
    return ["const", k]


G5 = json.loads(json.dumps(MS.GRAMMAR))
NOOP = lambda prog: dict(main=prog["main"][:-1] + [("dedupe", "P5", "P5")] + prog["main"][-1:], helpers=prog.get("helpers", {}))  # noqa: E731
CANDS = (
    [dict(name="seed_lpl", kind="lpl", prog=LP.SEED_BASELINE), dict(name="A0_baseline", kind="baseline"),
     dict(name="MI1_17", kind="file", file="artifacts/mi_dev/select_evolve.json"),
     dict(name="MI2_A2", kind="file", file="artifacts/mi2_dev/select_a_evolve_L3.json"),
     dict(name="MI2_A3", kind="file", file="artifacts/mi2_dev/select_a_random_struct_L3.json"),
     dict(name="MI2_A4", kind="file", file="artifacts/mi2_dev/select_a_params_L1.json"),
     dict(name="A5", kind="a5"), dict(name="A6", kind="a6")]
    + [dict(name=f"random_{k}", kind="lpl", prog=LP.random_program(random.Random(f"mi3-cal-rand-{k}"))) for k in range(8)]
    + [dict(name="spec_MUL", kind="fixed", exprs=G5 + [b("*", A_, X_), b("*", X_, X_), b("+", b("*", A_, X_), X_), b("*", A_, A_)]),
       dict(name="spec_ADDC", kind="fixed", exprs=G5 + [b("+", A_, c(k)) for k in range(2, 11)]),
       dict(name="spec_SUBH", kind="fixed", exprs=G5 + [b("-", A_, b("/", X_, c(2))), b("+", A_, b("/", X_, c(2))), b("/", X_, c(2))]),
       dict(name="dup_A5", kind="lpl", prog=NOOP(M2.A5_PROG)), dict(name="dup_seed", kind="lpl", prog=NOOP(LP.SEED_BASELINE)),
       dict(name="poor_identity", kind="fixed", exprs=[A_]), dict(name="poor_consts", kind="fixed", exprs=[c(0), c(1), X_]),
       dict(name="poor_params3", kind="params", size_bound=3, max_lit=1, max_s=60.0)])
TAUS = (0.75, 0.5, 0.25)
POOL = MS.pool_of("screen_calibration", MS.FAMS_U, 8)


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def run(job, njobs):
    D.mkdir(parents=True, exist_ok=True)
    scr, rest = MS.screen_split(POOL)
    for j, cand in enumerate(CANDS):
        if j % njobs != job or (D / f"cand_{j:02d}.json").exists():
            continue
        dom, max_s = MS.domain_of(cand)
        sig, sizes = MS.space_signature(cand)
        c0 = time.process_time()
        rows = [MS.eval_one(dom, max_s, s, f) for s, f in scr + rest]
        save(D / f"cand_{j:02d}.json", dict(j=j, name=cand["name"], signature=sig, space_sizes=sizes, rows=rows,
                                            cpu_s=round(time.process_time() - c0, 3)))
        print(j, cand["name"], "exact", sum(r["exact"] for r in rows), "silent", sum(r["silent"] for r in rows),
              "cpu", round(time.process_time() - c0, 2), flush=True)


def spearman(a, b):
    def ranks(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra) ** .5, sum((y - mb) ** 2 for y in rb) ** .5
    return cov / (va * vb) if va and vb else float("nan")


def simulate(cs, tau):
    order = list(range(len(cs)))
    random.Random("mi3-cal-order").shuffle(order)
    rnd = random.Random("mi3-cal-raudit")
    screen_spent = full_extra = audit_spent = 0.0
    surv, rejected, audited = set(), [], set()
    for j in order:
        c = cs[j]
        sc_rows, rest_rows = c["rows"][:6], c["rows"][6:]
        sc_cpu = sum(r["cpu_s"] for r in sc_rows)
        screen_spent += sc_cpu
        if MS.survives(sc_rows, tau):
            surv.add(j)
            full_extra += sum(r["cpu_s"] for r in rest_rows)
        else:
            rejected.append(j)
        pend = [k for k in rejected if k not in audited]
        while pend:
            k = rnd.choice(pend)
            est = 3 * sum(r["cpu_s"] for r in cs[k]["rows"][:6])
            if audit_spent + est > AUDIT_FRAC_ * screen_spent:
                break
            audited.add(k)
            audit_spent += sum(r["cpu_s"] for r in cs[k]["rows"][6:])
            pend = [k for k in rejected if k not in audited]
    full_cpu = sum(r["cpu_s"] for c in cs for r in c["rows"])
    staged = screen_spent + full_extra + audit_spent
    return dict(tau=tau, survivors=sorted(surv), rejected=sorted(rejected), audited=sorted(audited), screen_cpu=round(screen_spent, 2),
                survivor_full_cpu=round(full_extra, 2), audit_cpu=round(audit_spent, 2), staged_cpu=round(staged, 2),
                full_cpu=round(full_cpu, 2), saving=round(1 - staged / full_cpu, 4) if full_cpu else 0.0)


AUDIT_FRAC_ = MS.AUDIT_FRAC


def analyze():
    cs = [json.loads((D / f"cand_{j:02d}.json").read_text()) for j in range(len(CANDS))]
    full = [MS.fitness(c["rows"]) for c in cs]
    scr = [MS.fitness(c["rows"][:6]) for c in cs]
    ex = [f[0] for f in full]
    order = sorted(range(len(cs)), key=lambda j: full[j], reverse=True)
    q = len(cs) // 4
    thr = full[order[q - 1]][:2]
    topq = [j for j in range(len(cs)) if full[j][:2] >= thr]
    variance_ok = len(set(ex)) >= 3 and sum(e == 0 for e in ex) / len(ex) < 0.8
    silent = sum(r["silent"] for c in cs for r in c["rows"])
    sims = []
    for tau in TAUS:
        s = simulate(cs, tau)
        lost = [j for j in topq if j not in s["survivors"] and j not in s["audited"]]
        s.update(top_quartile_lost=[cs[j]["name"] for j in lost],
                 discarded_strong=[dict(name=cs[j]["name"], full_exact=ex[j]) for j in s["rejected"] if ex[j] > 0 and j not in s["audited"]],
                 passes=s["saving"] >= 0.20 and not lost and variance_ok and silent == 0)
        sims.append(s)
    ok = [s for s in sims if s["passes"]]
    chosen = max(ok, key=lambda s: (s["saving"], s["tau"])) if ok else None
    useful = [j for j in range(len(cs)) if ex[j] > 0]
    res = dict(candidates=[dict(j=j, name=cs[j]["name"], full_fitness=full[j], screen_fitness=scr[j], signature=cs[j]["signature"],
                                space_sizes=cs[j]["space_sizes"], silent=sum(r["silent"] for r in cs[j]["rows"]),
                                per_family={f: sum(r["exact"] for r in cs[j]["rows"] if r["family"] == f) for f in MS.FAMS_U},
                                screen_per_family={f: sum(r["exact"] for r in cs[j]["rows"][:6] if r["family"] == f) for f in MS.FAMS_U})
                           for j in range(len(cs))],
               top_quartile=[cs[j]["name"] for j in topq], variance_ok=variance_ok, distinct_full_exact=sorted(set(ex)),
               silent_total=silent, spearman_screen_vs_full=round(spearman([f[0] + f[1] / 10 for f in scr], [f[0] + f[1] / 10 for f in full]), 4),
               spearman_screen_exact_vs_full_exact=round(spearman([f[0] for f in scr], ex), 4),
               useful=len(useful), useful_distinct_signatures=len({cs[j]["signature"] for j in useful}),
               useful_distinct_solved_sets=len({tuple(r["exact"] for r in cs[j]["rows"]) for j in useful}),
               simulations=sims, chosen_tau=chosen["tau"] if chosen else None, passed=chosen is not None,
               full_cpu_per_candidate_mean=round(sum(-f[2] for f in full) / len(full), 3),
               per_episode_overhead_mean=round(sum(r["cpu_s"] - r["learner_cpu_s"] for c in cs for r in c["rows"]) /
                                               sum(len(c["rows"]) for c in cs), 4),
               per_episode_overhead_max=round(max(r["cpu_s"] - r["learner_cpu_s"] for c in cs for r in c["rows"]), 4),
               per_episode_cpu_max=max(r["cpu_s"] for c in cs for r in c["rows"]))
    for s in sims:
        rej_fam = {f: 0 for f in MS.FAMS_U}
        for j in s["rejected"]:
            for f in MS.FAMS_U:
                rej_fam[f] += sum(r["exact"] for r in cs[j]["rows"] if r["family"] == f)
        s["full_solves_lost_by_family_if_rejected"] = rej_fam
    save(D / "calibration.json", res)
    if chosen:
        save(ROOT / "artifacts/mi3_schedule.json", dict(screen="first 2 episodes per family of the pool (6)", tau=chosen["tau"],
             survive="screen exact >= 1 or screen mean partial >= tau", audit_frac=MS.AUDIT_FRAC, cap_s=MS.CAP_S,
             source="scripts/mi3_cal.py analyze (frozen menu + rule)"))
    print(json.dumps({k: v for k, v in res.items() if k != "candidates"}, indent=1)[:5000])
    for cnd in res["candidates"]:
        print(cnd["j"], cnd["name"], cnd["full_fitness"], cnd["screen_fitness"], cnd["per_family"], "silent", cnd["silent"])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(int(sys.argv[2]), int(sys.argv[3]))
    else:
        analyze()

"""MI-3 Stage 3 discovery (NOT LOCKED; development data mi3/discovery, mi3/selection).
  python scripts/mi3_discover.py run ARM LIN        ARM in E-F E-S R-F R-S, LIN in 1 2 (one metered 400 s run)
  python scripts/mi3_discover.py finalize ARM LIN   apply the frozen winner rule to a saved run (no evaluation)
Frozen design (MI-3 protocol):
  * Pool: 24 episodes (mi3/discovery seed indices 0-7 x MUL / ADDC / SUBH); selection pool 12 (mi3/selection 0-3 x 3).
  * Same DSL / primitives (mi_lpl), same generic operators (mi_lpl.mutate / crossover / random_program; no new block operators,
    no A5 macro), same Stage 1 acceptance check (mi3_accept.full_space3), same per-episode cap (mi3_search.CAP_S), same matched
    start (k = 0 is the transcribed seed procedure) for every arm.
  * E-*: k = 1, 2 random programs; k >= 3 tournament over the top POP by rank (mutate 1-3 edits, or crossover with p 0.3).
    R-*: k >= 1 a random program (p 0.5) or the seed with 1-6 random edits; no selection, no ancestry from evaluated candidates.
    Paired seeds: proposal RNG "mi3-{E|R}-L{lin}-{k}" is shared by the F and S arm of the same family and lineage.
  * -F: every candidate is evaluated on all 24 episodes. -S: the frozen Stage 2 schedule (artifacts/mi3_schedule.json:
    screen 6, survive rule with TAU, 10 % rejection audit; mi3_search docstring).
  * Budget: 400 charged s per run (mi_exec wall cap 400). Internal deadline DEADLINE s after process start; a stage (screen /
    full / rest / audit) is launched only if elapsed + n_episodes x (CAP_S + OVH_S) + SEL_RESERVE <= DEADLINE; SEL_RESERVE =
    3 x 12 x (CAP_S + OVH_S) is kept for selection. Generation, signatures, evaluation and bookkeeping all count.
  * Selection: the top 3 fully evaluated candidates by rank are re-scored on the selection pool; winner = best (selection exact,
    selection partial, discovery rank, -id). If selection could not run, the winner is the top-ranked fully evaluated candidate
    (else candidate 0). One winner per run; no manual edit or curation.
State is saved atomically after every candidate and every selection evaluation (artifacts/mi3_disc/<ARM>_L<LIN>.json)."""
import copy, json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus import mi3_seeds, mi3_search as MS, mi_lpl as LP  # noqa: E402,F401
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/mi3_disc"
POP, DEADLINE, OVH_S = 8, 385.0, 0.25
POOL = MS.pool_of("discovery", MS.FAMS_U, 8)
SEL = MS.pool_of("selection", MS.FAMS_U, 4)
SEL_RESERVE = 3 * len(SEL) * (MS.CAP_S + OVH_S)


def elapsed():
    return max(time.time() - T_START, time.process_time())


def can(n_eps):
    return elapsed() + n_eps * (MS.CAP_S + OVH_S) + SEL_RESERVE <= DEADLINE


def save(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def schedule():
    return json.loads((ROOT / "artifacts/mi3_schedule.json").read_text())


def propose(fam, lin, cands):
    k = len(cands)
    rnd = random.Random(f"mi3-{fam}-L{lin}-{k}")
    if k == 0:
        return dict(kind="lpl", prog=copy.deepcopy(LP.SEED_BASELINE), lineage=dict(op="seed (transcribed existing procedure)"))
    if fam == "R":
        if rnd.random() < 0.5:
            return dict(kind="lpl", prog=LP.random_program(rnd), lineage=dict(op="random_program"))
        p, edits = copy.deepcopy(LP.SEED_BASELINE), []
        for _ in range(rnd.randint(1, 6)):
            p, e = LP.mutate(p, rnd)
            edits.append(e)
        return dict(kind="lpl", prog=p, lineage=dict(op="seed + random edits (no selection)", edits=edits))
    if k < 3:
        return dict(kind="lpl", prog=LP.random_program(rnd), lineage=dict(op="random_program"))
    ranked = sorted(range(k), key=lambda j: MS.rank_key(cands[j]), reverse=True)[:POP]

    def tour():
        a, b = rnd.sample(ranked, 2) if len(ranked) > 1 else (ranked[0], ranked[0])
        return a if MS.rank_key(cands[a]) >= MS.rank_key(cands[b]) else b
    if rnd.random() < 0.3:
        a, b = tour(), tour()
        p, e = LP.crossover(cands[a]["prog"], cands[b]["prog"], rnd)
        return dict(kind="lpl", prog=p, lineage=dict(op=e, parents=[a, b]))
    a = tour()
    p, edits = copy.deepcopy(cands[a]["prog"]), []
    for _ in range(rnd.randint(1, 3)):
        p, e = LP.mutate(p, rnd)
        edits.append(e)
    return dict(kind="lpl", prog=p, lineage=dict(op="mutate", parents=[a], edits=edits))


def ev(dom, max_s, eps):
    rows = []
    for s, f in eps:
        try:
            rows.append(MS.eval_one(dom, max_s, s, f))
        except Exception as e:                                       # noqa: BLE001
            rows.append(dict(seed=s, family=f, exact=False, silent=False, accepted=False, outcome="error:" + repr(e)[:80],
                             learner_cpu_s=0.0, cpu_s=0.0, queries=0, explained=0.0, updates=None))
    return rows


def compact(rows):
    return [dict(seed=r["seed"], family=r["family"], exact=r["exact"], silent=r["silent"], outcome=r["outcome"], cpu_s=r["cpu_s"],
                 explained=r["explained"], queries=r["queries"], updates=r["updates"] if r["exact"] else None) for r in rows]


def run(arm, lin):
    fam, staged = arm[0], arm.endswith("S")
    sch = schedule() if staged else None
    tau = sch["tau"] if staged else None
    D.mkdir(parents=True, exist_ok=True)
    p = D / f"{arm}_L{lin}.json"
    if p.exists():
        raise SystemExit(f"{p} exists: discovery runs are never rerun (use finalize)")
    st = dict(arm=arm, lineage=lin, tau=tau, cap_s=MS.CAP_S, deadline=DEADLINE, sel_reserve=SEL_RESERVE, cands=[], seen={},
              screen_spent=0.0, audit_spent=0.0, audited=[], curve=[])
    scr, rest = MS.screen_split(POOL)
    rnd_audit = random.Random(f"mi3-raudit-{arm}-L{lin}")
    best = 0
    while can(len(scr) if staged else len(POOL)):
        c = propose(fam, lin, st["cands"])
        c0 = time.process_time()
        c["id"] = len(st["cands"])
        try:
            c["signature"], c["space_sizes"] = MS.space_signature(c)
            c["invalid"] = all(n <= 1 for n in c["space_sizes"])      # degenerate: identity-only space
        except Exception as e:                                       # noqa: BLE001
            c["signature"], c["space_sizes"], c["invalid"] = None, None, repr(e)[:80]
        c["duplicate"] = c["signature"] in st["seen"]
        st["seen"].setdefault(c["signature"], c["id"])
        dom, max_s = MS.domain_of(c)
        if staged:
            r1 = ev(dom, max_s, scr)
            c["screen_rows"] = compact(r1)
            c["screen_fitness"] = MS.fitness(r1)
            sc_cpu = sum(r["cpu_s"] for r in r1)
            st["screen_spent"] += sc_cpu
            c["screen_cpu_s"] = round(sc_cpu, 3)
            if MS.survives(r1, tau) and can(len(rest)):
                r2 = ev(dom, max_s, rest)
                c["rest_rows"] = compact(r2)
                c["full_fitness"] = MS.fitness(r1 + r2)
                c["stage"] = "survived"
            else:
                c["full_fitness"] = None
                c["stage"] = "screen_reject" if not MS.survives(r1, tau) else "survived_no_time"
        else:
            r = ev(dom, max_s, POOL)
            c["screen_rows"], c["rest_rows"] = compact(r[:6]), compact(r[6:])
            c["screen_fitness"], c["full_fitness"], c["stage"] = MS.fitness(r[:6]), MS.fitness(r), "full"
        c["cpu_s"] = round(time.process_time() - c0, 3)
        st["cands"].append(c)
        if staged:                                                   # rejection audit (10 % of screening CPU)
            while True:
                pend = [x["id"] for x in st["cands"] if x["stage"] == "screen_reject" and x["id"] not in st["audited"]]
                if not pend:
                    break
                k = rnd_audit.choice(pend)
                x = st["cands"][k]
                if st["audit_spent"] + 3 * x["screen_cpu_s"] > MS.AUDIT_FRAC * st["screen_spent"] or not can(len(rest)):
                    break
                a0 = time.process_time()
                d2, ms2 = MS.domain_of(x)
                r2 = ev(d2, ms2, rest)
                x["rest_rows"] = compact(r2)
                x["full_fitness"] = MS.fitness(x["screen_rows"] + r2)
                x["stage"] = "audited"
                st["audited"].append(k)
                st["audit_spent"] += time.process_time() - a0
        best = max([best] + [x["full_fitness"][0] for x in st["cands"] if x.get("full_fitness")])
        st["curve"].append(dict(k=c["id"], elapsed=round(elapsed(), 2), cpu=round(time.process_time(), 2), best_full_exact=best))
        save(p, st)
        print(arm, lin, c["id"], c["lineage"]["op"][:30], c["stage"], "screen", c["screen_fitness"], "full", c.get("full_fitness"),
              "dup", c["duplicate"], "t", round(elapsed(), 1), flush=True)
    st["stopped_at"] = round(elapsed(), 2)
    save(p, st)
    select(st, p)


def select(st, p):
    full = [c for c in st["cands"] if c.get("full_fitness") is not None]
    top = sorted(full, key=lambda c: (MS.rank_key(c), -c["id"]), reverse=True)[:3]
    st.setdefault("selection", [])
    done = {e["id"] for e in st["selection"]}
    for c in top:
        if c["id"] in done:
            continue
        if elapsed() + len(SEL) * (MS.CAP_S + OVH_S) > DEADLINE + 10:
            st["selection_truncated"] = True
            break
        dom, max_s = MS.domain_of(c)
        r = ev(dom, max_s, SEL)
        st["selection"].append(dict(id=c["id"], sel_fitness=MS.fitness(r), rows=compact(r),
                                    per_family={f: sum(x["exact"] for x in r if x["family"] == f) for f in MS.FAMS_U}))
        save(p, st)
        print("select", c["id"], MS.fitness(r), flush=True)
    finalize_state(st)
    save(p, st)
    print("WINNER", st["winner_id"], st["winner_rule"], flush=True)


def finalize_state(st):
    full = [c for c in st["cands"] if c.get("full_fitness") is not None]
    rk = {c["id"]: MS.rank_key(c) for c in st["cands"]}
    if st.get("selection"):
        w = max(st["selection"], key=lambda e: (e["sel_fitness"][:2], rk[e["id"]], -e["id"]))
        st["winner_id"], st["winner_rule"] = w["id"], "best selection score of the top-3"
    elif full:
        st["winner_id"] = max(full, key=lambda c: (rk[c["id"]], -c["id"]))["id"]
        st["winner_rule"] = "top-ranked fully evaluated (selection did not run)"
    else:
        st["winner_id"], st["winner_rule"] = 0, "candidate 0 (nothing fully evaluated)"
    st["winner"] = {k: v for k, v in st["cands"][st["winner_id"]].items() if k in ("id", "kind", "prog", "lineage", "signature")}


def finalize(arm, lin):
    p = D / f"{arm}_L{lin}.json"
    st = json.loads(p.read_text())
    if "winner_id" not in st:
        finalize_state(st)
        st["finalized_offline"] = True
        save(p, st)
    print("WINNER", st["winner_id"], st["winner_rule"])


if __name__ == "__main__":
    (run if sys.argv[1] == "run" else finalize)(sys.argv[2], int(sys.argv[3]))

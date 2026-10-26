"""Wave 34 (NOT LOCKED): learner DSL v2. Payoff-driven learning ALGORITHMS, interpreted inside the sandboxed solver.

Primitives (all decisions are expressions that evolution writes):
  * Deterministic cost accounting: every interpreter operation the solver performs is counted in op units (a counting
    wrapper on the interpreter inside the child process; the pinned checker files are untouched). Checker work is read from
    Checker v3's own verdict fields (point_evals + steps). Decisions therefore replay exactly; the evaluator's OS meter still
    does all scoring.
  * Counterfactual payoff: an online cost model of plain primitive search, by solution length, sampled on tasks solved by
    plain search (and on forced exploration tasks, every `explore` tasks). Saving of a hit = model(len) - actual cost.
    Per-component ledgers (m = macros, p = fragment prior, x = proof citations) track saved, invested (extraction / refit
    units), lookup (cost of phases that missed) and uses/hits, over the lifetime and a recent window (multi-timescale).
  * Per-item ledgers for macros (support, hits, saved, age, len, survival, fit rate). Admission AND eviction use the
    evolved Score(item) formula: items with score > 0 are kept, best first, at most `cap`.
  * Proof citation (the only pruning Checker v3 accepts: its 4 proved fixpoint axioms; new pruning-rule kinds would need a
    new checker version): cite or not by an evolved expression over the proofs ledger (applied rate from verdicts).
Expressions:
  B := true | false | gt F c | lt F c | gtf F F | and B B | or B B | not B
  N := const c | feat f | add N N | sub N N | mul N N | div N N | max N N | min N N
  F (stream / component features): see SFEATS;  f (item features): see MFEATS
"""
from __future__ import annotations

import copy
import random

from nexus import checker_kernel_v2 as V
from nexus import wave31_grammar as G
from nexus import wave31_solver as S
from nexus import wave33_prior as P

COMP = ("m", "p", "x")
SFEATS = tuple(f"{c}_{k}" for c in COMP for k in ("roi", "roi_recent", "hit", "hit_recent", "uses")) + \
    ("n_tasks", "n_cert", "repeat_rate", "novel_recent", "lib_size", "est_bfs", "since_fit")
SCONST = (-1.0, -0.5, -0.1, 0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 100.0, 1000.0)
MFEATS = ("support", "hits", "saved", "age", "len", "survival", "fit_rate", "novel", "cost")
NCONST = (-5, -1, 0, 0.5, 1, 2, 5, 100)
MAX_NODES = 21
RECENT = 10

TRUE, FALSE = ["true"], ["false"]
# DSL v2.1 (dev iteration 2): the prior is itself under evolved learning mechanics:
#   pscore  N over per-solved-task features -> weight of that task in the prior (<= 0 excluded): evolved credit assignment
#   extract.p is the evolved refit trigger (it can read since_fit and the prior's ROI ledgers); alpha / lam evolvable
SEED_ON = {"use": {"m": TRUE, "p": FALSE, "x": FALSE}, "extract": {"m": TRUE, "p": FALSE},
           "score": ["const", 1], "pscore": ["const", 1], "alpha": 1.0, "lam": 0.8, "cap": 200, "refit": 4, "explore": 0,
           "macro_depth": 2, "max_holes": 1, "min_support": 1, "probe": {"mut": 2, "tries": 300}}
SEED_OFF = dict(copy.deepcopy(SEED_ON), use={"m": FALSE, "p": FALSE, "x": FALSE}, extract={"m": FALSE, "p": FALSE})
SEED_PRIOR = dict(copy.deepcopy(SEED_OFF), use={"m": FALSE, "p": TRUE, "x": FALSE}, extract={"m": FALSE, "p": TRUE})
# Hand-written FIXED net-payoff controller (a comparator, and the 4th fixed learner of the "strongest fixed" bar): every
# component is used / refreshed only while its measured net ROI (saved - invested - lookup) is positive, after a 5-use
# probation; macros are kept if they have earned hits or have majority support.
FIXED_PAYOFF = dict(copy.deepcopy(SEED_ON),
                    use={"m": ["or", ["lt", "m_uses", 5.0], ["gt", "m_roi_recent", 0.0]],
                         "p": ["or", ["lt", "p_uses", 5.0], ["gt", "p_roi_recent", -0.1]],
                         "x": ["or", ["lt", "x_uses", 5.0], ["gt", "x_hit_recent", 0.1]]},
                    extract={"m": ["and", ["gt", "n_cert", 2.0], ["or", ["lt", "m_uses", 5.0], ["gt", "m_roi", 0.0]]],
                             "p": ["and", ["gt", "since_fit", 2.0], ["or", ["lt", "p_uses", 5.0], ["gt", "p_roi_recent", -0.5]]]},
                    score=["add", ["feat", "hits"], ["sub", ["feat", "fit_rate"], ["const", 0.5]]], refit=1, explore=10)

# --------------------------------------------------------------------------- deterministic op-unit counter (child only)
UNITS = [0]
_raw_run = V.run


def _counted_run(chain, x):
    out, s = _raw_run(chain, x)
    UNITS[0] += s + 1
    return out, s


def install_counter():
    V.run = _counted_run


# --------------------------------------------------------------------------- DSL validation / generation / mutation
def _nodes(e):
    return 1 + sum(_nodes(x) for x in e[1:] if isinstance(x, list))


def _vb(e):
    if not isinstance(e, list) or not e:
        return False
    if e[0] in ("true", "false"):
        return len(e) == 1
    if e[0] in ("gt", "lt"):
        return len(e) == 3 and e[1] in SFEATS and isinstance(e[2], (int, float))
    if e[0] == "gtf":
        return len(e) == 3 and e[1] in SFEATS and e[2] in SFEATS
    if e[0] in ("and", "or"):
        return len(e) == 3 and _vb(e[1]) and _vb(e[2])
    if e[0] == "not":
        return len(e) == 2 and _vb(e[1])
    return False


def _vn(e):
    if not isinstance(e, list) or not e:
        return False
    if e[0] == "const":
        return len(e) == 2 and isinstance(e[1], (int, float))
    if e[0] == "feat":
        return len(e) == 2 and e[1] in MFEATS
    if e[0] in ("add", "sub", "mul", "div", "max", "min"):
        return len(e) == 3 and _vn(e[1]) and _vn(e[2])
    return False


def validate(p):
    try:
        ok = (set(p) == set(SEED_ON) and set(p["use"]) == set(COMP) and all(_vb(p["use"][c]) for c in COMP)
              and set(p["extract"]) == {"m", "p"} and all(_vb(p["extract"][c]) for c in ("m", "p")) and _vn(p["score"])
              and _vn(p["pscore"]) and p["alpha"] in (0.25, 0.5, 1.0, 2.0) and p["lam"] in (0.2, 0.5, 0.8, 1.0)
              and p["cap"] in (10, 40, 200) and p["refit"] in (1, 2, 4, 8) and p["explore"] in (0, 5, 10, 20)
              and p["macro_depth"] in (1, 2) and p["max_holes"] in (0, 1) and p["min_support"] in (1, 2, 3)
              and p["probe"]["mut"] in (1, 2, 3) and p["probe"]["tries"] in (50, 150, 300))
        exprs = [p["use"][c] for c in COMP] + [p["extract"]["m"], p["extract"]["p"], p["score"], p["pscore"]] if ok else []
    except (KeyError, TypeError):
        ok = False
    if not ok or any(_nodes(e) > MAX_NODES for e in exprs):
        raise ValueError("learner program outside DSL v2")
    return p


def rand_b(rng, d=2):
    r = rng.random()
    if d == 0 or r < 0.4:
        f = rng.choice(SFEATS)
        u = rng.random()
        if u < 0.12:
            return [rng.choice(("true", "false"))]
        if u < 0.25:
            return ["gtf", f, rng.choice(SFEATS)]
        return [rng.choice(("gt", "lt")), f, rng.choice(SCONST)]
    if r < 0.85:
        return [rng.choice(("and", "or")), rand_b(rng, d - 1), rand_b(rng, d - 1)]
    return ["not", rand_b(rng, d - 1)]


def rand_n(rng, d=2):
    if d == 0 or rng.random() < 0.35:
        return ["const", rng.choice(NCONST)] if rng.random() < 0.35 else ["feat", rng.choice(MFEATS)]
    return [rng.choice(("add", "sub", "mul", "div", "max", "min")), rand_n(rng, d - 1), rand_n(rng, d - 1)]


def _mut(e, rng, gen):
    kids = [k for k, x in enumerate(e) if k > 0 and isinstance(x, list)]
    if rng.random() < 0.3 or not kids:
        if e[0] in ("gt", "lt") and rng.random() < 0.6:
            return [e[0], e[1], rng.choice(SCONST)] if rng.random() < 0.6 else [e[0], rng.choice(SFEATS), e[2]]
        if e[0] == "const" and rng.random() < 0.6:
            return ["const", rng.choice(NCONST)]
        if rng.random() < 0.3 and e[0] not in ("true", "false", "const", "feat"):
            return [rng.choice(("and", "or")), copy.deepcopy(e), gen(rng, 1)] if gen is rand_b else \
                [rng.choice(("add", "mul", "min", "max")), copy.deepcopy(e), gen(rng, 1)]
        return gen(rng, 2)
    i = rng.choice(kids)
    return e[:i] + [_mut(e[i], rng, gen)] + e[i + 1:]


def mutate(p, rng):
    for _ in range(60):
        q = copy.deepcopy(p)
        for _k in range(rng.choice((1, 1, 2, 3))):
            site = rng.choice(("use_m", "use_p", "use_x", "ex_m", "ex_p", "ex_p", "score", "score", "pscore", "pscore",
                               "prior_hp", "cap", "refit", "explore", "depth", "skel", "probe"))
            if site.startswith("use_"):
                c = site[-1]; q["use"][c] = _mut(q["use"][c], rng, rand_b)
            elif site.startswith("ex_"):
                c = site[-1]; q["extract"][c] = _mut(q["extract"][c], rng, rand_b)
            elif site == "score":
                q["score"] = _mut(q["score"], rng, rand_n)
            elif site == "pscore":
                q["pscore"] = _mut(q["pscore"], rng, rand_n)
            elif site == "prior_hp":
                q["alpha"], q["lam"] = rng.choice((0.25, 0.5, 1.0, 2.0)), rng.choice((0.2, 0.5, 0.8, 1.0))
            elif site == "cap":
                q["cap"] = rng.choice((10, 40, 200))
            elif site == "refit":
                q["refit"] = rng.choice((1, 2, 4, 8))
            elif site == "explore":
                q["explore"] = rng.choice((0, 5, 10, 20))
            elif site == "depth":
                q["macro_depth"] = 3 - q["macro_depth"]
            elif site == "skel":
                q["max_holes"], q["min_support"] = rng.choice((0, 1)), rng.choice((1, 2, 3))
            else:
                q["probe"] = {"mut": rng.choice((1, 2, 3)), "tries": rng.choice((50, 150, 300))}
        try:
            return validate(q)
        except ValueError:
            continue
    return validate(copy.deepcopy(p))


def crossover(a, b, rng):
    q = copy.deepcopy(a)
    for k in ("use", "extract"):
        for c in q[k]:
            if rng.random() < 0.5:
                q[k][c] = copy.deepcopy(b[k][c])
    for k in ("score", "pscore", "alpha", "lam", "cap", "refit", "explore", "macro_depth", "max_holes", "min_support",
              "probe"):
        if rng.random() < 0.5:
            q[k] = copy.deepcopy(b[k])
    return validate(q)


# --------------------------------------------------------------------------- interpreter state (child side)
ST = {}


def reset(placebo=False):
    """placebo=True (comparator only): every fitted prior is permuted and macros are size-matched placebo macros."""
    ST.clear()
    ST.update(placebo=placebo, progs=[], views=[], pfeats=[], cores=set(), n_tasks=0, n_cert=0, repeats=0, recent_new=[], lib=[], items={}, prior=None,
              since_fit=0, cost_model={}, led={c: dict(saved=0.0, invested=0.0, lookup=0.0, uses=0, hits=0, recent=[])
                                               for c in COMP})


reset()


def _ledger_feats(c):
    L = ST["led"][c]
    roi = (L["saved"] - L["invested"] - L["lookup"]) / max(1.0, L["invested"] + L["lookup"])
    rec = L["recent"][-RECENT:]
    r_s = sum(x[0] for x in rec); r_c = sum(x[1] for x in rec)
    return {f"{c}_roi": roi, f"{c}_roi_recent": (r_s - r_c) / max(1.0, r_c), f"{c}_hit": L["hits"] / max(1, L["uses"]),
            f"{c}_hit_recent": sum(x[2] for x in rec) / max(1, len(rec)), f"{c}_uses": L["uses"]}


def est_bfs(length):
    cm = ST["cost_model"]
    if str(length) in cm:
        s, n = cm[str(length)]
        return s / n
    vals = [s / n for s, n in cm.values()]
    return max(vals) if vals else 0.0


def feats():
    f = {}
    for c in COMP:
        f.update(_ledger_feats(c))
    rn = ST["recent_new"][-RECENT:]
    f.update(n_tasks=ST["n_tasks"], n_cert=ST["n_cert"], repeat_rate=ST["repeats"] / max(1, ST["n_cert"]),
             novel_recent=sum(rn) / max(1, len(rn)), lib_size=len(ST["lib"]), est_bfs=est_bfs(4),
             since_fit=ST["since_fit"])
    return f


def ev_b(e, f):
    op = e[0]
    if op == "true":
        return True
    if op == "false":
        return False
    if op == "gt":
        return f[e[1]] > e[2]
    if op == "lt":
        return f[e[1]] < e[2]
    if op == "gtf":
        return f[e[1]] > f[e[2]]
    if op == "and":
        return ev_b(e[1], f) and ev_b(e[2], f)
    if op == "or":
        return ev_b(e[1], f) or ev_b(e[2], f)
    return not ev_b(e[1], f)


def ev_n(e, m):
    op = e[0]
    if op == "const":
        return e[1]
    if op == "feat":
        return m[e[1]]
    a, b = ev_n(e[1], m), ev_n(e[2], m)
    if op == "div":
        return a / b if b else 0.0
    return {"add": a + b, "sub": a - b, "mul": a * b, "max": max(a, b), "min": min(a, b)}[op]


# --------------------------------------------------------------------------- solve (phases individually metered)
def _phase_macro(public, query, depth):
    tools = [dict(t) for t in G.G_P] + list(ST["lib"])
    c = S.first_fit(public, query, tools, depth, {})
    if c is None:
        return None
    exp = S.expand([tools[i] for i in c])
    keys = {V.key(t) for t in G.G_P}
    if len(exp) > 4 or any(V.key(t) not in keys for t in exp):
        return None
    return exp


def _phase_prior(public, query):
    gp = [dict(t) for t in G.G_P]
    c = P.best_first(public, query, gp, 4, {}, ST["prior"])
    return None if c is None else [gp[i] for i in c]


def _phase_bfs(public, query):
    gp = [dict(t) for t in G.G_P]
    c = S.first_fit(public, query, gp, 4, {})
    return None if c is None else [gp[i] for i in c]


def solve(chan, view, prog, seed):
    f = feats()
    explore = prog["explore"] and ST["n_tasks"] % prog["explore"] == prog["explore"] - 1
    use = {c: (not explore) and ev_b(prog["use"][c], f) for c in COMP}
    use["m"] = use["m"] and bool(ST["lib"])
    use["p"] = use["p"] and ST["prior"] is not None
    public, query = [list(p) for p in view["public"]], view["query"]
    rng = random.Random(f"w34-probe:{seed}:{V.key(query)}")
    rec = {"phases": [], "explore": bool(explore), "checker": 0, "proofs_applied": 0, "proof_checks": 0, "use": use}
    probes, gp = 0, [dict(t) for t in G.G_P]
    while True:
        cand, hit = None, None
        for ph, on in (("m", use["m"]), ("p", use["p"]), ("b", True)):
            if not on:
                continue
            u0 = UNITS[0]
            cand = (_phase_macro(public, query, prog["macro_depth"]) if ph == "m" else
                    _phase_prior(public, query) if ph == "p" else _phase_bfs(public, query))
            rec["phases"].append([ph, UNITS[0] - u0, cand is not None])
            if cand is not None:
                hit = ph
                break
        if cand is None:
            return None, {"prover": 0}, {"probes": probes, "fallback": False, "checks": 0, "status": "none", "rec": rec}
        ans, _ = V.run(cand, query)
        ev = {"checker_version": 3, "public": public, "query": query, "claimed_answer": ans, "candidate": cand,
              "scope": {"kind": "exhaustive", "tools": gp, "max_depth": 4}, "lemmas": [],
              "proofs": S.proofs_for(gp, {a for a, _ in S.AXIOM_TOOLS}) if use["x"] else [], "trace": {}}
        v = chan.check(ev)
        rec["checker"] += v.get("point_evals", 0) + v.get("steps", 0)
        rec["proofs_applied"] += v.get("proofs_applied", 0); rec["proof_checks"] += v.get("proof_checks", 0)
        rec["hit"], rec["len"] = hit, len(cand)
        if v["label"] != "AMBIGUOUS" or probes >= G.MAX_PROBES:
            break
        x = S.design_probe(public, query, gp, v, rng, {}, prog["probe"]["tries"], prog["probe"]["mut"])
        if x is None:
            break
        y = chan.oracle(x)
        probes += 1
        if y.get("error"):
            break
        public = public + [[x, y["output"]]]
    return ev, {"prover": sum(p[1] for p in rec["phases"])}, {"probes": probes, "fallback": False, "checks": 1,
                                                                "status": v["label"], "rec": rec}


def _contains(seq, body):
    n = len(body)
    return any(seq[i:i + n] == body for i in range(len(seq) - n + 1))


def update(prog, candidate, view, certified, rec):
    """Payoff accounting + evolved extraction / admission / eviction. Every unit spent here is also on the OS meter."""
    ST["n_tasks"] += 1
    led = ST["led"]
    if rec:
        miss = {ph: u for ph, u, ok in rec["phases"] if not ok}
        hitc = {ph: u for ph, u, ok in rec["phases"] if ok}
        L = rec.get("len", 4)
        if "b" in hitc and not miss:                           # plain search solved it: a baseline sample
            s, n = ST["cost_model"].get(str(L), [0.0, 0])
            ST["cost_model"][str(L)] = [s + hitc["b"], n + 1]
        base = est_bfs(L)
        for c in ("m", "p"):
            if not rec["use"].get(c):
                continue
            led[c]["uses"] += 1
            saved = max(0.0, base - hitc[c]) if c in hitc else 0.0
            cost = miss.get(c, 0)
            led[c]["saved"] += saved; led[c]["lookup"] += cost; led[c]["hits"] += c in hitc
            led[c]["recent"].append([saved, cost, int(c in hitc)])
            if c == "m" and c in hitc and certified:
                core = [V.key(s_) for s_ in S.core(candidate)]
                used = [m for m in ST["lib"] if _contains(core, [V.key(b) for b in m["body"]])]
                for m in used:
                    it = ST["items"][V.key(m)]
                    it["hits"] += 1; it["saved"] += saved / max(1, len(used))
        if rec["use"].get("x"):
            led["x"]["uses"] += 1
            ap, ck = rec["proofs_applied"], rec["proof_checks"]
            led["x"]["hits"] += ap > 0
            led["x"]["recent"].append([float(ap), float(ck) * 0.1, int(ap > 0)])
            led["x"]["saved"] += ap; led["x"]["lookup"] += ck * 0.1
    if not certified:
        return {"rebuilt": False, "refit": False}
    core = [V.key(s_) for s_ in S.core(candidate)]
    k = "|".join(core)
    new = k not in ST["cores"]
    ST["repeats"] += not new; ST["cores"].add(k); ST["recent_new"].append(int(new)); ST["n_cert"] += 1
    ST["progs"].append(candidate); ST["views"].append(view); ST["since_fit"] += 1
    spent = sum(ph[1] for ph in rec["phases"]) if rec else 0
    saved_here = max(0.0, est_bfs(len(candidate)) - spent)
    ST["pfeats"].append({"support": 1, "hits": 0, "saved": saved_here, "age": 0, "len": len(candidate),
                         "survival": 0.0, "fit_rate": 0.0, "novel": int(new), "cost": spent})
    for pf in ST["pfeats"]:
        pf["age"] += 1
    for it in ST["items"].values():
        it["age"] += 1
    f = feats()
    rebuilt = refit = False
    if ev_b(prog["extract"]["m"], f):
        u0 = UNITS[0]
        cands = S.build(ST["progs"], "w34", max_holes=prog["max_holes"], depth=4,
                        min_support=prog["min_support"])["placebo" if ST["placebo"] else "useful"]
        cores = [[V.key(s_) for s_ in S.core(p_)] for p_ in ST["progs"]]
        scored = []
        for m in cands:
            body = [V.key(b) for b in m["body"]]
            it = ST["items"].setdefault(V.key(m), {"hits": 0, "saved": 0.0, "age": 0})
            sup = sum(_contains(c_, body) for c_ in cores)
            mf = {"support": sup, "hits": it["hits"], "saved": it["saved"], "age": it["age"], "len": len(body),
                  "survival": it["hits"] / max(1, it["age"]), "fit_rate": sup / max(1, len(cores)), "novel": 0,
                  "cost": 0}
            sc = ev_n(prog["score"], mf)
            if sc > 0:
                scored.append((-sc, V.key(m), m))
        ST["lib"] = [m for _, _, m in sorted(scored)[: prog["cap"]]]
        led["m"]["invested"] += UNITS[0] - u0 + len(cands)
        rebuilt = True
    if ev_b(prog["extract"]["p"], f) and ST["since_fit"] >= prog["refit"]:
        u0 = UNITS[0]
        w = [max(0.0, ev_n(prog["pscore"], pf)) for pf in ST["pfeats"]]
        keep = [i for i, x in enumerate(w) if x > 0]
        fitted = (P.fit_prior([ST["progs"][i] for i in keep], G.G_P, [ST["views"][i] for i in keep],
                              prog["alpha"], prog["lam"], weights=[w[i] for i in keep]) if keep else None)
        if fitted is not None:
            ST["prior"] = P.permuted_prior(fitted, f"pl{ST['n_cert']}") if ST["placebo"] else fitted
        led["p"]["invested"] += UNITS[0] - u0
        ST["since_fit"] = 0
        refit = True
    return {"rebuilt": rebuilt, "refit": refit, "lib_size": len(ST["lib"])}

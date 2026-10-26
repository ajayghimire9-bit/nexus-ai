"""Milestone B (NOT LOCKED): a compositional, programmatic meta-learner, interpreted inside the sandboxed solver.

A learner is a typed PROGRAM (JSON data, never executed as Python). Evolution writes and composes its parts:
  plan      proposal stages with guards: {"macro": {"depth": 1|2, "when": B}, "prior": {"when": B}} (the complete BFS / best-first
            fallback is always appended by the interpreter, so a learner can never lose completeness)
  extract   abstraction extraction triggers: {"macros": B, "prior": B} evaluated after each certified task
  skeleton  anti-unification heuristics {"max_holes": 0|1, "min_support": 1|2|3}
  admit     credit-assignment / admission scoring: N over per-macro features (support, hits, age, len); macros with score > 0
            are admitted, best first, at most `cap`
  refit     prior refit period (certified tasks)
  probe     active-probe policy {"mut": 1|2|3, "tries": 50|150|300}
  proofs    B: cite Checker v3's proved axioms (lemma generation) or not
Expressions:
  B := ["true"] | ["false"] | ["gt", F, c] | ["lt", F, c] | ["and", B, B] | ["or", B, B] | ["not", B]
  F (stream features) := repeat_rate | macro_hit_rate | prior_hit_rate | n_certified | lib_size | n_tasks
  N := ["const", c] | ["feat", f] | ["add", N, N] | ["sub", N, N] | ["mul", N, N] | ["max", N, N] | ["min", N, N],
       f (macro features) := support | hits | age | len
Credit assignment (fixed rule): a certified candidate credits a hit to every admitted macro whose body occurs contiguously in
its core.
Everything the learner does (solving, credit, rebuilding, refitting) runs in the child and is metered by the OS counter.
"""
from __future__ import annotations

import random

from nexus import checker_kernel_v2 as V
from nexus import wave31_grammar as G
from nexus import wave31_solver as S
from nexus import wave33_prior as P

SFEATS = ("repeat_rate", "macro_hit_rate", "prior_hit_rate", "n_certified", "lib_size", "n_tasks")
SCONST = {"repeat_rate": (0.1, 0.2, 0.3, 0.4, 0.5), "macro_hit_rate": (0.1, 0.25, 0.5), "prior_hit_rate": (0.1, 0.25, 0.5),
          "n_certified": (2, 5, 10, 20), "lib_size": (5, 20, 60), "n_tasks": (5, 10, 20, 40)}
MFEATS = ("support", "hits", "age", "len")
NCONST = (-2, -1, 0, 1, 2, 5)
MAX_NODES = 15

GEN0_ON = {"plan": {"macro": {"depth": 2, "when": ["true"]}, "prior": {"when": ["false"]}},
           "extract": {"macros": ["true"], "prior": ["false"]}, "skeleton": {"max_holes": 1, "min_support": 1},
           "admit": ["const", 1], "cap": 200, "refit": 4, "probe": {"mut": 2, "tries": 300}, "proofs": ["false"]}
GEN0_OFF = dict(GEN0_ON, plan={"macro": {"depth": 2, "when": ["false"]}, "prior": {"when": ["false"]}},
                extract={"macros": ["false"], "prior": ["false"]})
# a Milestone-A-style learner expressed in the DSL (an archive seed, not a test arm)
SEED_PRIOR = dict(GEN0_OFF, plan={"macro": {"depth": 2, "when": ["false"]}, "prior": {"when": ["true"]}},
                  extract={"macros": ["false"], "prior": ["true"]})


# --------------------------------------------------------------------------- validation / generation / mutation
def _nodes(e):
    return 1 + sum(_nodes(x) for x in e[1:] if isinstance(x, list))


def _vb(e):
    if not isinstance(e, list) or not e:
        return False
    if e[0] in ("true", "false"):
        return len(e) == 1
    if e[0] in ("gt", "lt"):
        return len(e) == 3 and e[1] in SFEATS and isinstance(e[2], (int, float))
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
    if e[0] in ("add", "sub", "mul", "max", "min"):
        return len(e) == 3 and _vn(e[1]) and _vn(e[2])
    return False


def validate(p):
    ok = (set(p) == set(GEN0_ON) and set(p["plan"]) == {"macro", "prior"} and p["plan"]["macro"]["depth"] in (1, 2)
          and _vb(p["plan"]["macro"]["when"]) and _vb(p["plan"]["prior"]["when"])
          and set(p["extract"]) == {"macros", "prior"} and all(_vb(p["extract"][k]) for k in ("macros", "prior"))
          and p["skeleton"]["max_holes"] in (0, 1) and p["skeleton"]["min_support"] in (1, 2, 3)
          and _vn(p["admit"]) and p["cap"] in (10, 40, 200) and p["refit"] in (1, 2, 4, 8)
          and p["probe"]["mut"] in (1, 2, 3) and p["probe"]["tries"] in (50, 150, 300) and _vb(p["proofs"]))
    exprs = [p["plan"]["macro"]["when"], p["plan"]["prior"]["when"], p["extract"]["macros"], p["extract"]["prior"],
             p["admit"], p["proofs"]] if ok else []
    if not ok or any(_nodes(e) > MAX_NODES for e in exprs):
        raise ValueError("learner program outside the DSL")
    return p


def rand_b(rng, d=2):
    r = rng.random()
    if d == 0 or r < 0.35:
        f = rng.choice(SFEATS)
        return rng.choice([["true"], ["false"], ["gt", f, rng.choice(SCONST[f])], ["lt", f, rng.choice(SCONST[f])]])
    if r < 0.8:
        return [rng.choice(("and", "or")), rand_b(rng, d - 1), rand_b(rng, d - 1)]
    return ["not", rand_b(rng, d - 1)]


def rand_n(rng, d=2):
    if d == 0 or rng.random() < 0.4:
        return ["const", rng.choice(NCONST)] if rng.random() < 0.4 else ["feat", rng.choice(MFEATS)]
    return [rng.choice(("add", "sub", "mul", "max", "min")), rand_n(rng, d - 1), rand_n(rng, d - 1)]


def _mut_expr(e, rng, gen):
    """Subtree replacement or local edit."""
    if rng.random() < 0.3 or len(e) == 1 or not any(isinstance(x, list) for x in e[1:]):
        if e[0] in ("gt", "lt") and rng.random() < 0.5:
            return [e[0], e[1], rng.choice(SCONST[e[1]])]
        if e[0] == "const" and rng.random() < 0.5:
            return ["const", rng.choice(NCONST)]
        return gen(rng, 2)
    i = rng.choice([k for k, x in enumerate(e) if k > 0 and isinstance(x, list)])
    return e[:i] + [_mut_expr(e[i], rng, gen)] + e[i + 1:]


def mutate(p, rng):
    import copy
    for _ in range(50):
        q = copy.deepcopy(p)
        for _k in range(rng.choice((1, 2))):
            site = rng.choice(("macro_when", "macro_depth", "prior_when", "ex_macros", "ex_prior", "skeleton", "admit",
                               "cap", "refit", "probe", "proofs"))
            if site == "macro_when":
                q["plan"]["macro"]["when"] = _mut_expr(q["plan"]["macro"]["when"], rng, rand_b)
            elif site == "macro_depth":
                q["plan"]["macro"]["depth"] = 3 - q["plan"]["macro"]["depth"]
            elif site == "prior_when":
                q["plan"]["prior"]["when"] = _mut_expr(q["plan"]["prior"]["when"], rng, rand_b)
            elif site == "ex_macros":
                q["extract"]["macros"] = _mut_expr(q["extract"]["macros"], rng, rand_b)
            elif site == "ex_prior":
                q["extract"]["prior"] = _mut_expr(q["extract"]["prior"], rng, rand_b)
            elif site == "skeleton":
                q["skeleton"] = {"max_holes": rng.choice((0, 1)), "min_support": rng.choice((1, 2, 3))}
            elif site == "admit":
                q["admit"] = _mut_expr(q["admit"], rng, rand_n)
            elif site == "cap":
                q["cap"] = rng.choice((10, 40, 200))
            elif site == "refit":
                q["refit"] = rng.choice((1, 2, 4, 8))
            elif site == "probe":
                q["probe"] = {"mut": rng.choice((1, 2, 3)), "tries": rng.choice((50, 150, 300))}
            else:
                q["proofs"] = _mut_expr(q["proofs"], rng, rand_b)
        try:
            return validate(q)
        except ValueError:
            continue
    return validate(copy.deepcopy(p))


# --------------------------------------------------------------------------- interpreter (child side)
ST = {}


def reset():
    ST.clear()
    ST.update(progs=[], views=[], cores=set(), n_tasks=0, n_cert=0, repeats=0, m_att=0, m_hit=0, p_att=0, p_hit=0,
              lib=[], mstats={}, prior=None, since_fit=0)


reset()


def feats():
    return {"repeat_rate": ST["repeats"] / max(1, ST["n_cert"]), "macro_hit_rate": ST["m_hit"] / max(1, ST["m_att"]),
            "prior_hit_rate": ST["p_hit"] / max(1, ST["p_att"]), "n_certified": ST["n_cert"], "lib_size": len(ST["lib"]),
            "n_tasks": ST["n_tasks"]}


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
    return {"add": a + b, "sub": a - b, "mul": a * b, "max": max(a, b), "min": min(a, b)}[op]


def solve(chan, view, prog, seed):
    f = feats()
    use_m = bool(ST["lib"]) and ev_b(prog["plan"]["macro"]["when"], f)
    use_p = ST["prior"] is not None and ev_b(prog["plan"]["prior"]["when"], f)
    pol = {"matched_depth": 4, "checker": 3, "macro_first": use_m, "macro_depth": prog["plan"]["macro"]["depth"],
           "probe_mut": prog["probe"]["mut"], "probe_tries": prog["probe"]["tries"],
           "proofs": "all" if ev_b(prog["proofs"], f) else "none"}
    if use_p:
        pol.update(search="best_first", prior=ST["prior"])
    h0 = S.ONLINE["macro_hits"]
    ev, meter, info = S.solve(chan, "Useful" if use_m else "Fresh", "matched", view, ST["lib"] if use_m else [], seed, pol)
    if use_m:
        ST["m_att"] += 1
        ST["m_hit"] += S.ONLINE["macro_hits"] > h0
    if use_p:
        ST["p_att"] += 1
        ST["p_hit"] += not info.get("prior_fallback", False)
    return ev, meter, dict(info, used_macros=use_m, used_prior=use_p)


def _contains(seq, body):
    n = len(body)
    return any(seq[i:i + n] == body for i in range(len(seq) - n + 1))


def update(prog, candidate, view, certified):
    ST["n_tasks"] += 1
    if not certified:
        return {"rebuilt": False, "refit": False}
    core = [V.key(s) for s in S.core(candidate)]
    k = "|".join(core)
    ST["repeats"] += k in ST["cores"]
    ST["cores"].add(k)
    ST["n_cert"] += 1
    ST["progs"].append(candidate)
    ST["views"].append(view)
    ST["since_fit"] += 1
    for m in ST["lib"]:                                        # credit assignment (fixed rule)
        body = [V.key(b) for b in m["body"]]
        if _contains(core, body):
            ST["mstats"].setdefault(V.key(m), {"hits": 0, "added": ST["n_tasks"]})["hits"] += 1
    f = feats()
    rebuilt = refit = False
    if ev_b(prog["extract"]["macros"], f):
        cands = S.build(ST["progs"], "meta", max_holes=prog["skeleton"]["max_holes"], depth=4,
                        min_support=prog["skeleton"]["min_support"])["useful"]
        cores = [[V.key(s) for s in S.core(p)] for p in ST["progs"]]
        scored = []
        for m in cands:
            body = [V.key(b) for b in m["body"]]
            stt = ST["mstats"].setdefault(V.key(m), {"hits": 0, "added": ST["n_tasks"]})
            mf = {"support": sum(_contains(c, body) for c in cores), "hits": stt["hits"],
                  "age": ST["n_tasks"] - stt["added"], "len": len(body)}
            sc = ev_n(prog["admit"], mf)
            if sc > 0:
                scored.append((-sc, V.key(m), m))
        ST["lib"] = [m for _, _, m in sorted(scored)[: prog["cap"]]]
        rebuilt = True
    if ev_b(prog["extract"]["prior"], f) and ST["since_fit"] >= prog["refit"]:
        ST["prior"] = P.fit_prior(ST["progs"], G.G_P, ST["views"], 1.0, 0.8)
        ST["since_fit"] = 0
        refit = True
    return {"rebuilt": rebuilt, "refit": refit, "lib_size": len(ST["lib"])}

"""Wave 41 sandboxed solver child (v5 language / scope; shared w41_search with base lemmas; Checker v5 and the oracle only
through the evaluator). One learner per child, configured by `reset` (arm), optionally learning online (`update`).

Solve loop (every arm):
  1. Level 1: compiled skills (Arms D / Placebo) are instantiated first; a skill whose composed summary fails is excluded O(1).
  2. Otherwise the shared search runs in the arm's order (Flat: Fixed+Repr-v5; B: + human routing; C/D: + learned routing;
     Placebo: + permuted routing), with the base lemmas (all arms; off only for the Flat_noLemma reference).
  3. Witness short-circuit (all arms, <= 48k executions in the same order): a fitting in-scope chain with a different query
     answer proves AMBIGUOUS without a kernel call. Internally the pair designs the next oracle probe directly (the Wave 40
     loop spent a full Checker v5 sweep on every ambiguous round); externally it designs a distinguishing query.
  4. Otherwise Checker v5 sweeps the ORIGINAL declared scope (the only source of GLOBAL_SCOPE_UNIQUE).
  5. Distinguishing queries (external, k <= job k): after a kernel verdict that is AMBIGUOUS or SCOPE_UNIQUE with an
     under-specified future input, ask the user oracle about one future input (the one with the most in-scope answers, or one
     on which the two witnesses disagree), add the pair, re-solve. A snapshot is recorded after every round (k = 0, 1, 2).
Every solve returns a Middle-IR record (w41_hier.record)."""
import json
import random
import resource
import sys

from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w40_learn as W
from nexus import w41_hier as H
from nexus import w41_lemmas as M
from nexus import w41_search as Q

WITNESS_BUDGET = 48_000
STATE = {}


class Chan:
    def ask(self, m):
        sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
        return json.loads(sys.stdin.readline())


def _ix(tools, chain):
    pos = {json.dumps(t, sort_keys=True): i for i, t in enumerate(tools)}
    return [pos[json.dumps(t, sort_keys=True)] for t in chain]


# --------------------------------------------------------------------------- learner state
def reset(cfg):
    STATE.clear()
    STATE.update(cfg=cfg, programs=list(cfg.get("programs", [])), sigs=list(cfg.get("sigs", [])), since=0, vault=[],
                 lib=None, perm=None)
    if cfg.get("skills"):
        perm = None
        if cfg.get("placebo"):
            ak = [K.akey(t) for p in STATE["programs"] for t in p]
            perm = H.placebo_permutation(ak, cfg.get("seed", "p"))
        lib = H.Library(permute=perm)
        for p in STATE["programs"]:
            tp = lib.observe(p)
            if tp is not None:
                lib.add(tp)                       # source-compiled skills (offline; charged by the caller's fit meter)
        STATE["lib"] = lib
    refit()


def refit():
    cfg, progs = STATE["cfg"], STATE["programs"]
    STATE["repr"] = K.fit_repr(progs) if progs else K.fit_repr([])
    r = cfg.get("routing")
    if r == "fixed":
        STATE["routing"] = "fixed"
    elif r in ("learned", "placebo"):
        lr = H.fit_routing(progs, STATE["sigs"]) if progs else None
        STATE["routing"] = H.placebo_routing(lr, cfg.get("seed", "p")) if (lr and r == "placebo") else lr
    else:
        STATE["routing"] = None


def cost_for(tools, public):
    base = W.cost_matrix_fast({"kind": "fixed_repr", "repr": STATE["repr"]}, tools)
    r = STATE.get("routing")
    if r is None:
        return base
    sig = H.signature(public)
    return H.routed_cost_matrix(base, tools, H.fixed_routing(sig) if r == "fixed" else r, sig)


def update(job, info):
    """A certified program (online learning). Refit every 8; skill growth through the shadow vault; rent / retirement."""
    cfg = STATE["cfg"]
    prog, pub = job["candidate"], job["public"]
    STATE["programs"].append(prog); STATE["sigs"].append(H.signature(pub))
    STATE["since"] += 1
    out = {"refit": False, "adopted": 0, "rolled_back": 0, "retired": 0}
    if STATE["since"] >= 8:
        refit(); STATE["since"] = 0; out["refit"] = True
    lib = STATE["lib"]
    if lib is not None and cfg.get("grow"):
        tp = lib.observe(prog, info.get("search_execs"))
        STATE["vault"].append(dict(public=pub, query=job["query"], depth=job["depth"], execs=info.get("search_execs") or 0))
        if tp is not None:                       # shadow vault = the 6 most recently certified tasks, this one included
            ok = lib.adopt(tp, STATE["vault"][-6:], lambda v: S.scope(v["public"], v["query"], v["depth"])["tools"],
                           lambda v, tools: M.TaskLemmas(v["public"], tools))
            out["adopted" if ok else "rolled_back"] += 1
        if len(STATE["programs"]) % 10 == 0:
            out["retired"] = len(lib.retire())
    return out


# --------------------------------------------------------------------------- solve
def solve(chan, job):
    cfg = STATE["cfg"]
    pub = [list(p) for p in job["public"]]
    q, depth = job["query"], job["depth"]
    sc = S.scope(job["public"], q, depth)
    tools = sc["tools"]
    cm = cost_for(tools, job["public"])
    lem = M.TaskLemmas(job["public"], tools) if cfg.get("lemmas", True) else None
    extra = list(job.get("extra") or [])
    rng = random.Random(f"w38-probe:{job['seed']}")
    meter, probes, queries, snaps, ev, v = {}, 0, [], [], None, None
    evidence = {}
    if cfg.get("routing") and cfg.get("decomp_evidence", True):
        evidence["decompositions"] = H.decomposition_exclusion(job["public"], tools, depth)
    skill_tp, skill_spent, from_skill = None, 0, False
    while True:
        lem_r = M.TaskLemmas(pub, tools) if lem is not None else None
        e0 = meter.get("execs", 0)
        cand = None
        if STATE.get("lib") is not None and probes == 0 and not queries:
            cand, skill_tp, skill_spent = STATE["lib"].instantiate(pub, q, tools, lem_r, meter)
            meter["skill_execs"] = meter.get("skill_execs", 0) + skill_spent
            if cand is not None:
                STATE["lib"].credit(skill_tp, skill_spent)
                from_skill = True
        if cand is None:
            cand = Q.search(pub, q, tools, depth, cm, budget=job.get("budget", 300000), meter=meter, lem=lem_r)
        meter.setdefault("iters", []).append([meter.get("execs", 0) - e0, cand is not None])
        chan.ask({"req": "tick", "what": "search"})
        if cand is None:
            snaps.append(dict(candidate=None, label="NO_CANDIDATE", extra=None, extra_inputs=list(extra), queries=list(queries),
                              kernel=False))
            meter["skill_won"] = False
            return None, meter, {"probes": probes, "status": "no_candidate", "snaps": snaps, "queries": queries,
                                 "record": H.record(None, [], {"queries": len(queries)}, H.scope_ref(tools, depth),
                                                    dict(lemma_skips=meter.get("lemma_skips", 0), **evidence),
                                                    dict(execs=meter.get("execs", 0)))}
        claimed = L.run(cand, q)
        wm = {}
        w = Q.disagreeing_witness(pub, q, tools, depth, cm, claimed, budget=WITNESS_BUDGET, meter=wm, lem=lem_r) \
            if cfg.get("witness", True) else None
        meter["witness_execs"] = meter.get("witness_execs", 0) + wm.get("execs", 0)
        meter["witness_found"] = meter.get("witness_found", 0) + (w is not None)
        chan.ask({"req": "tick", "what": "witness"})
        ev = {"checker_version": 5, "public": pub, "query": q, "claimed_answer": claimed, "candidate": cand, "scope": sc,
              "extra_queries": extra}
        if w is not None:
            pv = {"label": "AMBIGUOUS", "witnesses": [{"chain": _ix(tools, cand)}, {"chain": _ix(tools, w)}]}
            snaps.append(dict(candidate=cand, label="AMBIGUOUS", extra=None, extra_inputs=list(extra), queries=list(queries),
                              witness=True, kernel=False))
            v = None
        else:
            v = chan.ask({"req": "check", "evidence": ev})
            pv = v
            snaps.append(dict(candidate=cand, label=v["label"], extra=[e.get("answers") for e in v.get("extra", [])],
                              extra_inputs=list(extra), warnings=v.get("warnings", []), queries=list(queries), kernel=True))
        # ---- next observation: internal oracle probe, or external distinguishing query, or stop
        if job.get("mode") == "external":
            if len(queries) >= job.get("k", 0):
                break
            x = None
            if pv["label"] == "AMBIGUOUS":
                c1, c2 = [tools[i] for i in pv["witnesses"][0]["chain"]], [tools[i] for i in pv["witnesses"][1]["chain"]]
                for e in extra:
                    if L.key(L.run(c1, e)) != L.key(L.run(c2, e)):
                        x = e
                        break
            elif pv["label"] == "SCOPE_UNIQUE" and v is not None:
                cnt = [(ee.get("answers") or 0, i) for i, ee in enumerate(v.get("extra", []))]
                cnt = [c for c in cnt if c[0] > 1]
                if cnt:
                    x = extra[max(cnt)[1]]
            if x is None:
                break
            y = chan.ask({"req": "oracle", "input": x})
            if y.get("error"):
                break
            queries.append(x)
            pub = pub + [[x, y["output"]]]
            extra = [e for e in extra if L.key(e) != L.key(x)]
            continue
        if pv["label"] != "AMBIGUOUS" or probes >= 3:
            break
        xp = Q.design_probe(pub, q, tools, pv, rng)
        if xp is None:
            break
        y = chan.ask({"req": "oracle", "input": xp})
        probes += 1
        if y.get("error"):
            break
        pub = pub + [[xp, y["output"]]]
    status = (v or {}).get("label") or "AMBIGUOUS_WITNESS"
    rec = H.record(ev["candidate"], [wt["chain"] for wt in pv.get("witnesses", [])[1:]],
                   {"queries": len(queries), "probes": probes}, H.scope_ref(tools, depth),
                   dict(lemma_skips=meter.get("lemma_skips", 0), skill_excluded_summary=meter.get("skill_excluded_summary", 0),
                        **evidence), dict(execs=meter.get("execs", 0), witness_execs=meter.get("witness_execs", 0),
                                          skill_execs=meter.get("skill_execs", 0)))
    meter["skill_won"] = from_skill
    return (ev if v is not None else None), meter, {"probes": probes, "status": status, "snaps": snaps, "record": rec,
                                                    "queries": queries, "final_public": pub}


def main():
    chan = Chan()
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "reset":
            reset(job["cfg"])
            out = {"done": True, "skills": STATE["lib"].size() if STATE.get("lib") else 0}
        elif job["cmd"] == "solve":
            ev, meter, info = solve(chan, job)
            meter["rss"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            out = {"done": True, "evidence": ev, "meter": meter, "info": info}
        elif job["cmd"] == "update":
            out = dict(update(job, job.get("info", {})), done=True,
                       skills=STATE["lib"].size() if STATE.get("lib") else 0)
        elif job["cmd"] == "state":
            out = {"done": True, "state": {"cfg": STATE["cfg"], "programs": STATE["programs"], "sigs": STATE["sigs"],
                                           "since": STATE["since"], "vault": STATE["vault"],
                                           "lib": STATE["lib"].to_json() if STATE.get("lib") else None}}
        elif job["cmd"] == "load":
            st = job["state"]
            reset(dict(st["cfg"], programs=st["programs"], sigs=st["sigs"]))
            STATE["since"], STATE["vault"] = st["since"], st["vault"]
            if st["lib"] is not None:
                STATE["lib"] = H.Library.from_json(st["lib"])
            refit()
            out = {"done": True}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()

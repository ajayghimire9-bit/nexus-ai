"""Pillar 3 - learned functions ("OOP plasmids") and how they are admitted (NOT LOCKED).

Candidates come only from NEXUS's own solved programs (src searches). A candidate is a sub-program of size 3-9 whose
leaves are generalised into parameters (domain-free ports: a parameter is typed only by the values it received - dict /
str / number - never by a field or domain name), e.g.  def fn_ab12(p0, p1): return float(p0.get(p1)).

Three admission arms (the Pillar 3 comparison; held-out evaluation charges every CPU second of discovery, admission and
search with the library present):
  none         No_Learned_Functions: fresh primitive search every time
  mdl          Admitted_By_Compression: greedy minimum description length - admit while rewriting the src corpus with the
               function lowers  size(library) + sum size(rewritten programs)
  utility      Admitted_By_Separate_Task_Utility (AbstractBeam-style): greedy forward selection; a candidate is admitted
               only if, on SEPARATE admission tasks (never the src corpus, never the held-out tasks), searching with it
               solves more tasks, or the same tasks with >= 10% less total search CPU, than searching without it."""
from __future__ import annotations

import hashlib
import time
from collections import Counter

from nexus import u5_construct as K
from nexus.oop_synthesizer import size


def _subtrees(n):
    out = [n]
    if n[0] in ("u", "b"):
        for c in n[2:]:
            out += _subtrees(c)
    elif n[0] == "fn":
        for a in n[4]:
            out += _subtrees(a)
    return out


def _generalise(n, params, keep_num=True, seen=None):
    """Replace every leaf (var / string const; numeric consts too unless keep_num) by a positional parameter; identical
    leaves share one parameter (dev revision 1: without sharing, r.get(a) * r.get(b) needed 4 parameters)."""
    seen = {} if seen is None else seen
    if n[0] == "var" or (n[0] == "const" and (isinstance(n[1], str) or not keep_num)):
        if n not in seen:
            seen[n] = f"p{len(params)}"
            params.append(seen[n])
        return ("var", seen[n])
    if n[0] == "const":
        return n
    return (n[0], n[1]) + tuple(_generalise(c, params, keep_num, seen) for c in n[2:])


def fid_of(body, params):
    return "fn_" + hashlib.sha256(repr((body, tuple(params))).encode()).hexdigest()[:6]


def candidates(programs, min_size=3, max_size=9, max_arity=3):
    """{fid: (params, body, uses)}: uses = number of distinct programs containing an instance."""
    seen = {}
    for pi, prog in enumerate(programs):
        for t in _subtrees(prog):
            sz = size(t)
            if not (min_size <= sz <= max_size) or t[0] not in ("u", "b"):
                continue
            for keep in (True, False):
                params = []
                body = _generalise(t, params, keep)
                if not params or len(params) > max_arity:
                    continue
                fid = fid_of(body, params)
                ent = seen.setdefault(fid, [params, body, set()])
                ent[2].add(pi)
    return {fid: (p, b, len(u)) for fid, (p, b, u) in seen.items() if len(u) >= 2}


def _match(body, n, binding):
    if body[0] == "var" and body[1].startswith("p"):
        if body[1] in binding:
            return binding[body[1]] == n
        binding[body[1]] = n
        return True
    if body[0] != n[0] or len(body) != len(n):
        return False
    if body[0] == "const":
        return body[1] == n[1] and type(body[1]) is type(n[1])
    if body[1] != n[1]:
        return False
    return all(_match(b, c, binding) for b, c in zip(body[2:], n[2:]))


def rewrite(n, fid, params, body):
    """Replace every instance of body (top-down, non-overlapping) by fid(args)."""
    b = {}
    if n[0] in ("u", "b") and _match(body, n, b) and all(p in b for p in params):
        return ("fn", fid, tuple(params), body, tuple(rewrite(b[p], fid, params, body) for p in params))
    if n[0] in ("u", "b"):
        return (n[0], n[1]) + tuple(rewrite(c, fid, params, body) for c in n[2:])
    if n[0] == "fn":
        return n[:4] + (tuple(rewrite(a, fid, params, body) for a in n[4]),)
    return n


def dl(n):
    """Description length: nodes, with a library call costing 1 + its arguments."""
    if n[0] == "fn":
        return 1 + sum(dl(a) for a in n[4])
    if n[0] in ("var", "const"):
        return 1
    return 1 + sum(dl(c) for c in n[2:])


def admit_mdl(programs, cands, max_fns=12):
    lib, corpus = [], list(programs)
    total = sum(dl(p) for p in corpus)
    while len(lib) < max_fns:
        best = None
        for fid, (params, body, _) in cands.items():
            if any(f[0] == fid for f in lib):
                continue
            new = [rewrite(p, fid, params, body) for p in corpus]
            gain = total - (sum(dl(p) for p in new) + size(body))
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, fid, params, body, new)
        if best is None:
            break
        gain, fid, params, body, corpus = best
        total -= gain
        lib.append((fid, list(params), body))
    return lib


def evaluate(tasks, cfg, lib, budget_s):
    """Search every task; returns (n solved-and-generalising, total CPU, per-task rows)."""
    from nexus import u5_world as W
    rows, cpu, ok = [], 0.0, 0
    for t in tasks:
        node, st, _ = K.solve(t.train, t.y_train, cfg, lib, budget_s)
        g = W.correct_on(t, node) if node is not None else 0.0
        ok += g == 1.0
        cpu += st["cpu_s"]
        rows.append(dict(task=t.tid, solved=st["solved"], gen=round(g, 4), cpu_s=st["cpu_s"], size=st["size"]))
    return ok, cpu, rows


def admit_utility(cands, adm_tasks, cfg, budget_s, top_k=10, max_fns=8, min_cpu_gain=0.10, max_s=600.0):
    """Greedy forward selection by measured downstream utility on separate admission tasks. Returns (lib, log, cpu_s)."""
    t0 = time.process_time()
    order = sorted(cands.items(), key=lambda kv: (-kv[1][2], size(kv[1][1])))[:top_k]
    lib = []
    base_ok, base_cpu, _ = evaluate(adm_tasks, cfg, lib, budget_s)
    log = [dict(step="base", solved=base_ok, cpu_s=round(base_cpu, 3))]
    for fid, (params, body, uses) in order:
        if len(lib) >= max_fns or time.process_time() - t0 > max_s:
            break
        trial = lib + [(fid, list(params), body)]
        ok, cpu, _ = evaluate(adm_tasks, cfg, trial, budget_s)
        take = ok > base_ok or (ok == base_ok and cpu <= (1 - min_cpu_gain) * base_cpu)
        log.append(dict(step=fid, uses=uses, solved=ok, cpu_s=round(cpu, 3), admitted=take))
        if take:
            lib, base_ok, base_cpu = trial, ok, cpu
    return lib, log, time.process_time() - t0


def lib_source(lib):
    from nexus.oop_synthesizer import def_source
    return "\n".join(def_source(fid, params, body) for fid, params, body in lib)


def uses_in(nodes):
    c = Counter()
    for n in nodes:
        for t in _subtrees(n):
            if t[0] == "fn":
                c[t[1]] += 1
    return c

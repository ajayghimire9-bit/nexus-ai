"""Trial 5 - transferring the structure of uncertainty: symbolic experiment translation (NOT LOCKED).

Explanations = executable hypotheses: programs (from NEXUS's construction bank) consistent with the labelled examples and
observationally distinct on an unlabelled probe pool. An experiment = a constructed input; before it is spent, it is
EXECUTED against the live hypotheses and must separate at least two of them (the translator never invents an answer - the
oracle labels the experiment). Experiment templates (name-free; instantiated through field roles derived from the
hypotheses themselves): zero(f) one(f) scale10(f) swap(f, g) negate(f) bump(f) other_category(f), where f, g are ranked by
name-free descriptors: 'used by most hypotheses', 'used by fewest', 'largest spread'.
A procedure = an ordered list of (template, descriptor) types. Translation learns the order on source domains (mean
fraction of live hypotheses eliminated per query) and carries ONLY that list to the target domain (no solution programs)."""
from __future__ import annotations

import math
import random
from collections import Counter

from nexus import u5_construct as K
from nexus.oop_synthesizer import ERR, _canon

TEMPLATES = ("zero", "one", "scale10", "swap", "negate", "bump", "other_category")
DESCRIPTORS = ("most_used", "least_used", "widest")
TYPES = [(t, d) for t in TEMPLATES for d in DESCRIPTORS]


def hypotheses(lab_envs, lab_ys, pool, cfg, budget_s=2.0, cap=40):
    envs = lab_envs + pool
    dummy = list(lab_ys) + [lab_ys[0]] * len(pool)
    s = K.Search(envs, dummy, dict(cfg, cap=25000), [], budget_s)
    s.run()
    out = []
    n = len(lab_envs)
    for e in sorted(s.sig.values(), key=lambda e: e[2]):
        if all(K._ok(v, y) for v, y in zip(e[1][:n], lab_ys)):
            out.append(e[0])
            if len(out) >= cap:
                break
    return out


def _fields_used(h):
    out = set()

    def walk(n):
        if n[0] == "b" and n[1] == "get" and n[2] == ("var", "r") and n[3][0] == "const":
            out.add(n[3][1])
        for c in n[1:]:
            if isinstance(c, tuple):
                walk(c)
    walk(h)
    return out


def instantiate(ttype, live, base, pool, rnd):
    tmpl, desc = ttype
    r = dict(base["r"])
    use = Counter(f for h in live for f in _fields_used(h) if f in r)
    num = [f for f in r if isinstance(r[f], (int, float)) and not isinstance(r[f], bool)]
    cat = [f for f in r if isinstance(r[f], str)]
    cands = (cat if tmpl == "other_category" else num)
    if not cands:
        return None
    if desc == "most_used":
        order = sorted(cands, key=lambda f: -use[f])
    elif desc == "least_used":
        order = sorted(cands, key=lambda f: use[f])
    else:
        sp = {f: (max(p["r"].get(f, 0) for p in pool if isinstance(p["r"].get(f), (int, float))) -
                  min(p["r"].get(f, 0) for p in pool if isinstance(p["r"].get(f), (int, float)))) if f in num else 0 for f in cands}
        order = sorted(cands, key=lambda f: -sp[f])
    f = order[0]
    if tmpl == "zero":
        r[f] = 0
    elif tmpl == "one":
        r[f] = 1
    elif tmpl == "scale10":
        r[f] = r[f] * 10
    elif tmpl == "negate":
        r[f] = -r[f]
    elif tmpl == "bump":
        r[f] = r[f] + 1
    elif tmpl == "swap":
        if len(order) < 2:
            return None
        g = order[1]
        r[f], r[g] = r[g], r[f]
    elif tmpl == "other_category":
        vals = sorted({p["r"].get(f) for p in pool if p["r"].get(f) != r[f]}, key=repr)
        if not vals:
            return None
        r[f] = rnd.choice(vals)
    return dict(base, r=r)


def partition(live, x):
    return Counter(_canon(K._safe_ev(h, x)) for h in live)


def entropy(c):
    n = sum(c.values())
    return -sum(v / n * math.log(v / n) for v in c.values())


def identify(task, method, cfg, rnd, order=None, max_q=15, n_lab=3, n_pool=40):
    """Run one identification episode. Returns dict(queries, success, cpu_s, eliminated)."""
    import time
    t0 = time.process_time()
    lab = task.train[:n_lab]
    ys = task.y_train[:n_lab]
    pool = task.train[n_lab:n_lab + n_pool] if len(task.train) >= n_lab + n_pool else task.train[n_lab:] + task.test[:n_pool]
    H = hypotheses(lab, ys, pool, cfg)
    n0 = len(H)
    q, elim = 0, []
    while len(H) > 1 and q < max_q:
        x = None
        if method == "info_gain":
            best = max(pool, key=lambda p: entropy(partition(H, p)))
            x = best if len(partition(H, best)) > 1 else None
        else:
            seq = order if method in ("translation", "irrelevant") else rnd.sample(TYPES, len(TYPES))
            scored = []
            for tt in seq:
                for base in rnd.sample(pool, min(3, len(pool))):
                    cand = instantiate(tt, H, base, pool, rnd)
                    if cand is not None and len(partition(H, cand)) > 1:          # verified to separate before spending
                        scored.append((entropy(partition(H, cand)), cand))
                        break
                if method in ("translation", "irrelevant") and len(scored) >= 2:
                    break
                if method == "fresh" and scored:
                    break
            x = max(scored, key=lambda z: z[0])[1] if scored else None
        if x is None:
            break
        y = task.oracle(x)
        q += 1
        before = len(H)
        H = [h for h in H if K._ok(K._safe_ev(h, x), y)]
        elim.append((before - len(H)) / max(1, before))
    from nexus import u5_world as W
    ok = bool(H) and all(W.correct_on(task, h) == 1.0 for h in H)
    return dict(queries=q, success=ok, n_hyp=n0, left=len(H), cpu_s=round(time.process_time() - t0, 4), eliminated=elim)


def learn_order(tasks, cfg, rnd, max_q=8):
    """Source-domain learning: per experiment type, mean fraction of live hypotheses it eliminates (when it separates)."""
    gain, cnt = Counter(), Counter()
    for t in tasks:
        lab, ys = t.train[:3], t.y_train[:3]
        pool = t.train[3:]
        H = hypotheses(lab, ys, pool, cfg)
        for _ in range(max_q):
            if len(H) <= 1:
                break
            for tt in TYPES:
                base = rnd.choice(pool)
                c = instantiate(tt, H, base, pool, rnd)
                if c is None or len(partition(H, c)) < 2:
                    continue
                y = t.oracle(c)
                keep = [h for h in H if K._ok(K._safe_ev(h, c), y)]
                gain[tt] += (len(H) - len(keep)) / len(H)
                cnt[tt] += 1
            base = rnd.choice(pool)
            y = t.oracle(base)
            H = [h for h in H if K._ok(K._safe_ev(h, base), y)]
    score = {tt: gain[tt] / cnt[tt] for tt in TYPES if cnt[tt]}
    return sorted(score, key=lambda tt: -score[tt]), score

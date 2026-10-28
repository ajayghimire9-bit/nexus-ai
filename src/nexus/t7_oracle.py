"""Trial 2 - inventing what NEXUS can check: check concepts scored on a multiverse of mutant pipeline outputs (NOT LOCKED).
CPU / numpy only (no GPU: see the t7 report).

World: a u5 project's tick-9..16 inputs and its CORRECT output tables (record table A: id, status, value; lifecycle table
B: rows per event). Mutant classes (each a seeded, assumption-breaking edit of the correct outputs):
  W1          partition birth missed: every A row of one tick sub-batch (ids ending in the last third of the tick) dropped
  7953        count-preserving swap: one accepted row becomes quarantined and one quarantined row becomes accepted
  X1          aborted transaction applied: one lifecycle event that should be rejected (q:invalid) emits the valid-looking
              row of another event of the same key instead
  X2          segment gap: the outputs of a contiguous run of 5-15 lifecycle events are missing
  unit_shift  values of the ok rows of one tick multiplied by 100
  clock_skew  two lifecycle outputs of the same key swapped in order
  id_collision one A row's id replaced by another row's id
Check concepts (a typed grammar; each has a cost in oracle labels): relation x view, e.g.
  count_eq(input ids, output ids), set_eq(input ids, output ids), unique(output ids), b_aligned(events, outputs),
  q_identity(k): the oracle labels EVERY output-quarantined row + k random accepted rows; statuses must agree
  ok_identity(k): the oracle labels every accepted row of k random ticks ... (row-identity reconciliation family)
  spot(k): k random rows; status and value agree with the oracle
  range(f): accepted values inside the build range widened by factor f
  key_order(k): k random keys' outputs equal the oracle's for their histories (per-key conservation / ordering)
  terminal_unique: no key has more than one row of a build-time terminal label
A check FAILS (kills) when its relation does not hold. Admission (invented arm): 0 false rejections on clean runs,
kills >= 1 training mutant in >= 2 projects, and pays for itself (kills per oracle label >= the cheapest generic check)."""
from __future__ import annotations

import copy
import random

from nexus import u5_platform as PL
from nexus import u5_stateful as SF

MUTANTS = ("W1", "7953", "X1", "X2", "unit_shift", "clock_skew", "id_collision")


class World:
    def __init__(self, seed):
        P = PL.Project(seed, "dev")
        self.P = P
        tr = P.truth()
        self.ticks = sorted(tr)
        self.A_in = {t: P.ticks[t]["A"] for t in self.ticks}
        self.B_in = {t: P.ticks[t]["B"] for t in self.ticks}
        self.A = {t: [dict(id=r[P.id_field], status=s, value=v) for r, (s, v) in zip(P.ticks[t]["A"], tr[t]["A"])] for t in self.ticks}
        self.B = {t: [list(map(tuple, rows)) for rows in tr[t]["B"]] for t in self.ticks}
        bA = [P.ref_A(r, P.ticks[t]["registry"]) for t in range(1, 9) for r in P.ticks[t]["A"]]
        vals = [v for s, v in bA if s == "ok" and isinstance(v, (int, float))]
        self.vmin, self.vmax = (min(vals), max(vals)) if vals else (0.0, 1.0)
        allB = [e for t in range(1, 9) for e in P.ticks[t]["B"]]
        labs = [r[0] for rows in P.ref_B(allB) for r in rows]
        self.terminal = {l for l in set(labs) if l != "q:invalid" and labs.count(l) <= len({e[P.schema.key] for e in allB})}
        self.hist = {t: [e for tt in range(1, t + 1) for e in P.ticks[tt]["B"]] for t in self.ticks}

    def outputs(self):
        return copy.deepcopy(self.A), copy.deepcopy(self.B)


def mutate(w, cls, rnd):
    A, B = w.outputs()
    t = rnd.choice(w.ticks)
    if cls == "W1":
        n = len(A[t])
        A[t] = A[t][: n - n // 3]
    elif cls == "7953":
        ok = [(tt, i) for tt in w.ticks for i, r in enumerate(A[tt]) if r["status"] == "ok"]
        q = [(tt, i) for tt in w.ticks for i, r in enumerate(A[tt]) if r["status"] != "ok"]
        if not ok or not q:
            return None
        (t1, i1), (t2, i2) = rnd.choice(ok), rnd.choice(q)
        v = A[t1][i1]["value"]
        A[t1][i1].update(status=A[t2][i2]["status"], value=None)
        A[t2][i2].update(status="ok", value=v)
    elif cls == "X1":
        P = w.P
        cand = [(tt, i) for tt in w.ticks for i, rows in enumerate(B[tt]) if rows and rows[0][0] == "q:invalid"]
        good = [rows for tt in w.ticks for rows in B[tt] if rows and rows[0][0] != "q:invalid"]
        if not cand or not good:
            return None
        tt, i = rnd.choice(cand)
        B[tt][i] = list(rnd.choice(good))
        _ = P
    elif cls == "X2":
        evs = [(tt, i) for tt in w.ticks for i in range(len(B[tt]))]
        L = rnd.randint(5, 15)
        s = rnd.randrange(0, max(1, len(evs) - L))
        for tt, i in evs[s:s + L]:
            B[tt][i] = None
    elif cls == "unit_shift":
        for r in A[t]:
            if r["status"] == "ok" and isinstance(r["value"], (int, float)):
                r["value"] = r["value"] * 100
    elif cls == "clock_skew":
        key = w.P.schema.key
        bykey = {}
        for tt in w.ticks:
            for i, e in enumerate(w.B_in[tt]):
                if B[tt][i]:
                    bykey.setdefault(e[key], []).append((tt, i))
        ks = [k for k, v in bykey.items() if len(v) >= 2 and len({tuple(map(tuple, B[a][b])) for a, b in v}) > 1]
        if not ks:
            return None
        pos = bykey[rnd.choice(ks)]
        (a1, b1), (a2, b2) = rnd.sample(pos, 2)
        B[a1][b1], B[a2][b2] = B[a2][b2], B[a1][b1]
    elif cls == "id_collision":
        rows = [(tt, i) for tt in w.ticks for i in range(len(A[tt]))]
        (t1, i1), (t2, i2) = rnd.sample(rows, 2)
        A[t1][i1]["id"] = A[t2][i2]["id"]
    return A, B


# ------------------------------------------------------------------------------------------------ check concepts
def concepts():
    C = [("count_eq", None, 0), ("set_eq", None, 0), ("unique", None, 0), ("b_aligned", None, 0), ("terminal_unique", None, 0)]
    C += [("q_identity", k, None) for k in (0, 2, 5)]
    C += [("ok_identity", k, None) for k in (1, 2)]
    C += [("spot", k, None) for k in (3, 10, 30)]
    C += [("range", f, 0) for f in (1.5, 3.0, 10.0)]
    C += [("key_order", k, None) for k in (2, 5, 10)]
    return C


GENERIC = [("count_eq", None, 0), ("unique", None, 0), ("range", 1.5, 0), ("spot", 3, None)]      # Deequ-style + sampling


def run_check(c, w, A, B, rnd):
    """Returns (passes, oracle_labels_used)."""
    kind, k, _ = c
    P = w.P
    if kind == "count_eq":
        return sum(len(A[t]) for t in w.ticks) == sum(len(w.A_in[t]) for t in w.ticks), 0
    if kind == "set_eq":
        return {r["id"] for t in w.ticks for r in A[t]} == {r[P.id_field] for t in w.ticks for r in w.A_in[t]}, 0
    if kind == "unique":
        ids = [r["id"] for t in w.ticks for r in A[t]]
        return len(ids) == len(set(ids)), 0
    if kind == "b_aligned":
        return all(len(B[t]) == len(w.B_in[t]) and all(rows is not None for rows in B[t]) for t in w.ticks), 0
    if kind == "terminal_unique":
        cnt = {}
        for t in w.ticks:
            for e, rows in zip(w.B_in[t], B[t]):
                for r in rows or []:
                    if r[0] in w.terminal:
                        cnt[e[P.schema.key]] = cnt.get(e[P.schema.key], 0) + 1
        return all(v <= 1 for v in cnt.values()), 0
    byid = {r[P.id_field]: (t, r) for t in w.ticks for r in w.A_in[t]}
    if kind in ("q_identity", "ok_identity", "spot"):
        rows = [r for t in w.ticks for r in A[t]]
        if kind == "q_identity":
            pick = [r for r in rows if r["status"] != "ok"] + rnd.sample([r for r in rows if r["status"] == "ok"],
                                                                          min(k, sum(r["status"] == "ok" for r in rows)))
        elif kind == "ok_identity":
            ts = rnd.sample(w.ticks, k)
            pick = [r for t in ts for r in A[t] if r["status"] == "ok"]
        else:
            pick = rnd.sample(rows, min(k, len(rows)))
        used = 0
        for r in pick:
            if r["id"] not in byid:
                return False, used
            t, rec = byid[r["id"]]
            used += 1
            s, v = P.ref_A(rec, P.ticks[t]["registry"])
            if s != r["status"] or (s == "ok" and not PL._rowA_eq((r["status"], r["value"]), (s, v))):
                return False, used
        return True, used
    if kind == "range":
        lo, hi = w.vmin, w.vmax
        span = hi - lo
        return all(lo - k * span <= r["value"] <= hi + k * span for t in w.ticks for r in A[t]
                   if r["status"] == "ok" and isinstance(r["value"], (int, float))), 0
    if kind == "key_order":
        key = P.schema.key
        keys = sorted({e[key] for t in w.ticks for e in w.B_in[t]})
        used = 0
        for kk in rnd.sample(keys, min(k, len(keys))):
            h = [e for e in w.hist[w.ticks[-1]] if e[key] == kk]
            want = P.ref_B(h)
            used += len(h)
            got = []
            for t in w.ticks:
                for e, rows in zip(w.B_in[t], B[t]):
                    if e[key] == kk:
                        got.append(rows)
            if not all(g is not None and SF.rows_eq(list(map(tuple, g)), x) for g, x in zip(got, want[-len(got):])):
                return False, used
        return True, used
    raise KeyError(kind)


def kill_matrix(worlds, classes, concepts_, n_mut, seed):
    """K[c][(world, class, m)] = killed?; cost[c] = mean oracle labels; clean_fail[c] = false rejections on clean runs."""
    rnd = random.Random(seed)
    K, cost, clean_fail = {c: {} for c in concepts_}, {c: [] for c in concepts_}, {c: 0 for c in concepts_}
    for wi, w in enumerate(worlds):
        A0, B0 = w.outputs()
        for c in concepts_:
            ok, used = run_check(c, w, A0, B0, rnd)
            clean_fail[c] += not ok
            cost[c].append(used)
        for cls in classes:
            for m in range(n_mut):
                mut = mutate(w, cls, random.Random(f"{seed}-{wi}-{cls}-{m}"))
                if mut is None:
                    continue
                A, B = mut
                for c in concepts_:
                    ok, used = run_check(c, w, A, B, rnd)
                    K[c][(wi, cls, m)] = not ok
                    cost[c].append(used)
    return K, {c: sum(v) / max(1, len(v)) for c, v in cost.items()}, clean_fail


def critic_select(K, cost, clean_fail, budget, min_projects=2):
    """Blind-spot critic: greedily add the admissible concept with the most NEW kills (mutants no selected concept kills)
    per (1 + oracle labels), until the oracle-label budget is spent."""
    adm = [c for c in K if clean_fail[c] == 0 and len({k[0] for k, v in K[c].items() if v}) >= min_projects]
    chosen, covered, spent = [], set(), 0.0
    while True:
        best = None
        for c in adm:
            if c in chosen or spent + cost[c] > budget:
                continue
            new = {k for k, v in K[c].items() if v} - covered
            if not new:
                continue
            val = len(new) / (1.0 + cost[c])
            if best is None or val > best[0]:
                best = (val, c, new)
        if best is None:
            return chosen, spent
        chosen.append(best[1])
        covered |= best[2]
        spent += cost[best[1]]

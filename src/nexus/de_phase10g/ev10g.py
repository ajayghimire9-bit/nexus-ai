"""Phase 10G evidence layer (NOT LOCKED): what the shared solver does when several candidate repairs fit everything it can see.

TIE SET   after the shared solver (atomic dedup + learned guidance) reaches an accepted candidate c*, every ONE-FIELD alternative of
          every edit on c*'s path (same operator, same relation / join, exactly one parameter changed: e.g. another dedup order column,
          SUM -> MAX) is re-checked on the visible batches (each check = one charged execution). C = {c*} U the distinct alternatives
          that are also accepted. |C| = 1: submit c*. |C| > 1: a TIE (the ambiguity guard X2 forbids guessing).
EVIDENCE  an arm may spend up to B_ev requests on the K = 5 typed channels (world10g.CHANNELS). A request costs C_REQ = 10 executions
          plus one execution per live candidate (each is run on the channel's batch and checked against its expected rows / count).
RESOLVED  a request ELIMINATES >= 1 live candidate and the survivors are observationally EQUIVALENT (identical outputs of every node -
          each stg relation, int_orders, fct_out - on the visible batches and on every channel batch obtained): submit the first
          survivor (c* first). All eliminated: abstain. Otherwise (nothing eliminated - an irrelevant channel - or distinguishable
          survivors) the tie stands; after the budget the solver ABSTAINS.
POLICIES  E0 none (abstain on every tie) | E1 uniform random channel order (rng10c numeric) | E2 fixed operator-type rule (dedup ->
          1, filter -> 2, join / aggregation -> 3, otherwise 4; then the global order 1-5) | E3 learned pi_ev.
pi_ev     trained ONLY from training exploration: at every training tie all 5 channels are tried and Gain(e | C) = 1 iff channel e
          eliminated >= 1 tied candidate while leaving a survivor that VERIFIES on the hidden batches (the training feedback the
          wake-sleep learner already uses; never an evaluation target). Features: DiffSignature(C) = the differing operator, DAG node,
          relation roles, the differing parameter slot, the roles (or literals) of the tied values, and |C| (capped at 4). Model: the
          existing pairwise ranker (de_phase10.guide10.train) on (gainful channel, non-gainful channel) pairs over channel-conjoined
          feature tokens; ranking = score desc, ties by channel number."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from nexus.de_phase10 import guide10 as G
from nexus.de_phase10c.rng10c import rng, seed_of
from nexus.de_phase10d import dag10d as D10, ir10d as IR, world10d as W10D
from nexus.de_phase10e import dag10e as D

K, C_REQ = 5, 10
FIELDS = {"set_dedup": ("rel", "key", "order", "dir"), "pre_aggregate": ("j", "m", "f"), "add_filter": ("rel", "pos", "cond", "col", "val"),
          "json_coalesce_before": ("rel", "col")}
COLUMN_SLOTS = {"key", "order", "col", "m"}
E2_ORDER = {"dedup": [1, 2, 3, 4, 5], "filter": [2, 1, 3, 4, 5], "join": [3, 1, 2, 4, 5], "other": [4, 5, 1, 2, 3]}
OP_CLASS = dict(set_dedup="dedup", add_partition="dedup", add_filter="filter", move_filter="filter", pre_aggregate="join", set_join_type="join",
                cast_keys="join", asof_backward="join", coalesce_out="join")


def norm(specs):
    return json.dumps(specs, sort_keys=True, default=str)


def one_field(prm, prm2):
    a, b = prm.split("|"), prm2.split("|")
    return len(a) == len(b) and a[0] == b[0] and sum(x != y for x, y in zip(a, b)) == 1


def tie_set(inv, path):
    """-> (C, sigs): C = [(path, specs)] with c* first; sigs = one DiffSignature row per alternative."""
    path = [tuple(e) for e in path]
    star = D.replay(inv, path)
    C, sigs, seen = [(path, star)], [], {norm(star)}
    for i, (k, op, prm) in enumerate(path):
        before = D.replay(inv, path[:i])
        dom = inv.dom(k, before)
        for _, prm2 in D.candidates(op, before[k], dom):
            if prm2 == prm or not one_field(prm, prm2):
                continue
            alt = path[:i] + [(k, op, prm2)] + path[i + 1:]
            sp = D.replay(inv, alt)
            key = norm(sp)
            if key in seen:
                continue
            seen.add(key)
            if inv.run(sp, True)["ok"]:
                C.append((alt, sp))
                sigs.append(signature(inv, before, k, op, prm, prm2))
    return C, sigs


def _rel_of(before, k, op, parts):
    if k == 0:
        return parts[0]
    if op == "pre_aggregate":
        return before[1]["joins"][int(parts[0])]["rel"]
    return None


def signature(inv, before, k, op, prm, prm2):
    a, b = prm.split("|"), prm2.split("|")
    slot = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
    names = FIELDS.get(op, tuple(f"p{i}" for i in range(len(a))))
    field = names[slot] if slot < len(names) else f"p{slot}"
    dom = inv.dom(k, before)
    rel = _rel_of(before, k, op, a)
    roles, lits = set(), set()
    for v in (a[slot], b[slot]):
        if field in COLUMN_SLOTS and rel is not None:
            try:
                roles |= set(dom.roles(rel, v))
            except Exception:                                       # noqa: BLE001
                pass
        else:
            lits.add(v)
    rel_roles = list(D.rel_role(dom, rel)) if k == 0 and rel else ["node"]
    return dict(op=op, k=k, field=field, rel_roles=rel_roles, roles=sorted(roles), lits=sorted(lits))


def features(sigs, n):
    f = {f"n:{min(n, 4)}"}
    for s in sigs:
        f |= {f"op:{s['op']}", f"k:{s['k']}", f"slot:{s['field']}"} | {f"rel:{r}" for r in s["rel_roles"]}
        f |= {f"val:{s['field']}:{r}" for r in s["roles"]} | {f"lit:{s['field']}:{v}" for v in s["lits"]}
    return sorted(f)


# ------------------------------------------------------------------ channels
def load_channel(p, e):
    hid = Path(p["hidden_dir"])
    c = json.loads((Path(p["ws"]) / "contract.json").read_text())
    T = W10D.load_tables(hid, c["tables"], prefix=f"probe{e}_")
    S = json.loads((hid / f"probe{e}_state.json").read_text())
    exp_ = json.loads((hid / f"probe{e}_expected.json").read_text())
    return (T, S, exp_["rows"], len(exp_["rows"]))


def channel_inv(inv, e):
    q = copy.copy(inv)
    q.batches = [load_channel(inv.p, e)]
    q.runs = {k: 0 for k in inv.runs}
    q._memo, q._proj = {}, {}
    return q


def outputs(specs, batches):
    out = []
    for T, S, _, _ in batches:
        try:
            R = IR.interpret(D10.Inv10d.spec_of(specs), T, S)
        except Exception as e:                                      # noqa: BLE001
            out.append(f"error:{type(e).__name__}")
            continue
        rels = sorted(specs[0]) + ["int_orders", "fct_out"]
        out.append({r: sorted(json.dumps(x, sort_keys=True, default=str) for x in R.get(r, [])) for r in rels})
    return json.dumps(out, sort_keys=True)


def resolve(inv, C, order, b_ev, cache=None):
    """Apply up to b_ev channels of `order` to the tie C. -> dict(outcome, chosen, requests, ev_execs)."""
    cache = {} if cache is None else cache
    live, seen, reqs, cost = list(C), [], [], 0
    for e in list(order)[:b_ev]:
        if e not in cache:
            cache[e] = channel_inv(inv, e)
        q = cache[e]
        seen.append(e)
        surv = []
        for c in live:
            key = (e, norm(c[1]))
            if key not in cache:
                cache[key] = D10.Inv10d.run(q, c[1], True)["ok"]
            if cache[key]:
                surv.append(c)
        cost += C_REQ + len(live)
        elim = len(live) - len(surv)
        reqs.append(dict(channel=e, live=len(live), eliminated=elim))
        if not surv:
            return dict(outcome="abstain_all_eliminated", chosen=None, requests=reqs, ev_execs=cost)
        live = surv
        if elim > 0:
            bat = list(inv.batches) + [cache[x].batches[0] for x in seen]
            if len({outputs(c[1], bat) for c in live}) == 1:
                return dict(outcome="resolved", chosen=live[0], requests=reqs, ev_execs=cost)
    return dict(outcome="abstain_unresolved" if b_ev else "abstain_no_evidence", chosen=None, requests=reqs, ev_execs=cost)


# ------------------------------------------------------------------ policies
def order_E1(rep, seed):
    o = [1, 2, 3, 4, 5]
    rng(rep, seed, 77).shuffle(o)
    return o


def order_E2(sigs):
    return E2_ORDER[OP_CLASS.get(sigs[0]["op"], "other")] if sigs else E2_ORDER["other"]


def toks(e, feats):
    return [f"ch{e}"] + [f"ch{e}|{f}" for f in feats]


def order_E3(w, feats):
    return sorted(range(1, K + 1), key=lambda e: (-G.score(w or {}, toks(e, feats)), e))


def train_pi(records, rep):
    """records: [dict(features, gain={e: 0/1})] from training exploration -> (weights, info)."""
    pairs = []
    for r in records:
        pos = [e for e in range(1, K + 1) if r["gain"][str(e)]]
        neg = [e for e in range(1, K + 1) if not r["gain"][str(e)]]
        pairs += [(toks(a, r["features"]), toks(b, r["features"])) for a in pos for b in neg]
    w = G.train(pairs, seed=seed_of(rep, 9, 9)) if pairs else {}
    return w, dict(records=len(records), pairs=len(pairs), weights=len(w), train_pair_accuracy=G.pair_accuracy(w, pairs) if pairs else None)

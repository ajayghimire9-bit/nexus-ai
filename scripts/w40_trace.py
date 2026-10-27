"""Wave 40 Step 1 (NOT LOCKED; diagnostic replay, no claim is drawn from these seeds): trace where the valid solution path
disappeared in the solves lost by non-uniform priors under the Wave 38 / Wave 39 shared search (unchanged code).

Cases:
  * the 3 Hierarchical-Stream-Memory losses of Wave 39 C4 (confirm_stream 7842 #26, 7843 #26, 7845 #25): the stream is
    replayed IN-PROCESS up to the lost task (same tasks, same child solve loop, Checker v5 called directly, same oracle rule,
    same HierLearner updates on certified candidates), so the exact prior the learner held is reconstructed;
  * the Fixed losses of Wave 39 C2 (7831 / 7832 tables #6; w39 search, fixed5) and a sample of Wave 38 E3 (7801 tables #6, #7;
    7803 tables #6; w38 search, w38 'fixed').
For each case: the Fresh (uniform) solution chain is found; the non-uniform search is re-run with an INSTRUMENTED copy of the
shared best-first search (asserted to return exactly what the real search returns) that records, for every value state, the
first route that marked it seen (depth, score, chain). The trace reports the first prefix of the Fresh solution whose state
was discarded, the route that had marked it, and the pruning rule."""
import argparse, heapq, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))


def isearch(public, query, tools, depth, prior, budget, L, last_rule, target=None):
    """Instrumented copy of w39_search.search (last_rule=True) / w38_search.search (last_rule=False)."""
    from nexus import w39_search as Q
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [L.key(y) for _, y in public]
    nonlist = all(not isinstance(y, list) for _, y in public)
    last_ok = [t for t in range(len(tools)) if not (last_rule and nonlist and tools[t]["op"] in Q.LIST_OUT)]
    cost = prior["cost"]
    T = len(tools)
    root = tuple(L.key(x) for x in xs)
    seen = {root: (0, 0.0, ())}
    heap, tick, execs = [], 0, 0
    pre = {tuple(target[:i + 1]) for i in range(len(target))} if target else set()
    log = {}
    for t in (last_ok if depth == 1 else range(T)):
        heapq.heappush(heap, (cost[0][t], tick, (t,), xs)); tick += 1
    found = None
    while heap:
        c, _, chain, vals = heapq.heappop(heap)
        execs += 1
        if execs > budget:
            break
        spec = tools[chain[-1]]
        outs = []
        for v in vals:
            o = L.run([spec], v)
            if o == L.ERROR:
                break
            outs.append(o)
        if len(outs) < len(vals):
            if chain in pre:
                log[chain] = dict(event="error", depth=len(chain), score=c, execs=execs)
            continue
        kk = tuple(L.key(o) for o in outs)
        if list(kk[:n]) == targets:
            found = [tools[i] for i in chain]
            break
        if kk in seen:
            if chain in pre:
                d0, c0, ch0 = seen[kk]
                log[chain] = dict(event="discarded", depth=len(chain), score=round(c, 4), execs=execs,
                                  remaining_depth=depth - len(chain), state=str(kk)[:160],
                                  seen_by=dict(depth=d0, score=round(c0, 4), chain=[tools[i] for i in ch0],
                                               remaining_depth=depth - d0),
                                  rule="observational dedup: value state already in `seen` (raw value equality, any depth)")
            continue
        seen[kk] = (len(chain), c, chain)
        if chain in pre:
            log[chain] = dict(event="expanded", depth=len(chain), score=round(c, 4), execs=execs)
        if len(chain) < depth:
            row = cost[chain[-1] + 1]
            for t in (last_ok if len(chain) == depth - 1 else range(T)):
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
    return found, execs, log


def trace(public, query, tools, depth, cm, budget, L, last_rule, real_search):
    from nexus import w38_learn as K
    uni = K.cost_matrix(None, tools)
    fresh, fe, _ = isearch(public, query, tools, depth, uni, budget, L, last_rule)
    ix = {json.dumps(t, sort_keys=True): i for i, t in enumerate(tools)}
    target = [ix[json.dumps(t, sort_keys=True)] for t in fresh] if fresh else None
    got, ex, log = isearch(public, query, tools, depth, cm, budget, L, last_rule, target)
    real = real_search(public, query, tools, depth, cm, budget=budget, meter={})
    assert (real is None) == (got is None) and (real is None or real == got), "instrumented copy diverged"
    steps = []
    for i in range(len(target or [])):
        p = tuple(target[:i + 1])
        steps.append(dict(prefix=[tools[j] for j in p], **(log.get(p) or {"event": "never_popped (an earlier prefix was discarded)"})))
    lost_at = next((s for s in steps if s["event"] == "discarded"), None)
    return dict(fresh_solution=fresh, fresh_execs=fe, prior_result=got, prior_execs=ex, budget=budget, n_tools=len(tools),
                depth=depth, path=steps, lost_at=lost_at,
                verdict=("solved" if got else "lost: solution path discarded by dedup" if lost_at else
                         "lost: other (budget / not reached)"))


def stream_case(seed, k):
    """Replay a Wave 39 C4 stream (hier-s1) in-process up to task k; return (task, prior at task k, replay check)."""
    import w38_online as D
    import w39_child as C
    from nexus import checker_kernel_v5 as V5, w38_online as O, w39_lang as L, w39_online as H
    phases = ["strings", "graphs", "tables", "strings", "graphs", "grids"]
    ts = []
    for i, dom in enumerate(phases):
        ts += D.program_stream(f"w39-stream:{seed}:{i}", (dom,), "all", 1)
    art = json.loads((ROOT / f"artifacts/w39_stream_confirm_{seed}.json").read_text())
    assert L.key(art["tasks"]) == L.key(ts), "task regeneration differs from the artifact"

    class Chan:
        def __init__(self, t):
            self.t, self.log = t, []

        def ask(self, m):
            if m["req"] == "check":
                return V5.check(json.loads(json.dumps(m["evidence"])))
            x = m["input"]
            if L.key(x) == L.key(self.t["query"]) or len(self.log) >= 3:
                return {"error": True}
            y = L.run(self.t["teacher"], x)
            if y == L.ERROR:
                return {"error": True}
            self.log.append(x)
            return {"output": y}

    lr = H.HierLearner(dict(O.BASELINE_80F9CC2, gate="regime"), 1.0)
    replay = []
    for j, t in enumerate(ts[:k + 1]):
        view = {"public": t["public"]}
        prior = lr.current_prior(view)
        if j == k:
            return t, prior, replay, art["hier-s1"]["solved"][:k + 1]
        ev, meter, info = C.solve(Chan(t), {"public": t["public"], "query": t["query"], "depth": len(t["teacher"]),
                                            "seed": f"w39-stream:{seed}:{j}", "prior": prior, "budget": 2_000_000, "extra": []})
        ok = info["status"] == "SCOPE_UNIQUE"
        correct = ok and L.key(ev["claimed_answer"]) == L.key(t["answer"])
        replay.append(correct)
        if ok:
            lr.update(ev["candidate"], view)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(ROOT / "artifacts/w40_step1_trace.json"))
    a = ap.parse_args()
    from nexus import w38_domains as D, w38_lang as L4, w38_learn as K, w38_scope as S4, w38_search as Q4
    from nexus import w39_eval as WE, w39_lang as L5, w39_learn as W, w39_scope as S5, w39_search as Q5
    t0 = time.perf_counter()
    out = {"stream": [], "fixed_w39": [], "fixed_w38": []}
    for seed, k in ((7842, 26), (7843, 26), (7845, 25)):
        t, prior, replay, art_solved = stream_case(seed, k)
        sc = S5.scope(t["public"], t["query"], len(t["teacher"]))
        cm = W.cost_matrix(prior, sc["tools"])
        r = trace(t["public"], t["query"], sc["tools"], len(t["teacher"]), cm, 2_000_000, L5, True, Q5.search)
        out["stream"].append(dict(seed=seed, task=k, domain=t["domain"], mechanism=t["mechanism"],
                                  replay_matches_artifact=replay == art_solved[:k], **r))
        print("stream", seed, k, t["domain"], t["mechanism"], r["verdict"], "%.0fs" % (time.perf_counter() - t0), flush=True)
    for seed, j in ((7831, 6), (7832, 6)):
        t = D.stream(f"{seed}:tgt:tables", ("tables",), "all", 2)[j]
        sc = S5.scope(t["public"], t["query"], len(t["teacher"]))
        cm = W.cost_matrix({"kind": "fixed5"}, sc["tools"])
        r = trace(t["public"], t["query"], sc["tools"], len(t["teacher"]), cm, 4_000_000, L5, True, Q5.search)
        out["fixed_w39"].append(dict(seed=seed, task=j, mechanism=t["mechanism"], **r))
        print("fixed-w39", seed, j, t["mechanism"], r["verdict"], "%.0fs" % (time.perf_counter() - t0), flush=True)
    for seed, j in ((7801, 6), (7801, 7), (7803, 6)):
        t = D.stream(f"{seed}:tgt:tables", ("tables",), "all", 2)[j]
        sc = S4.scope(t["public"], t["query"], len(t["teacher"]))
        cm = K.cost_matrix({"kind": "fixed"}, sc["tools"])
        r = trace(t["public"], t["query"], sc["tools"], len(t["teacher"]), cm, 2_000_000, L4, False, Q4.search)
        out["fixed_w38"].append(dict(seed=seed, task=j, mechanism=t["mechanism"], **r))
        print("fixed-w38", seed, j, t["mechanism"], r["verdict"], "%.0fs" % (time.perf_counter() - t0), flush=True)
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True, default=repr))
    WE.ledger_append(dict(run="w40-step1-trace", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()

"""x7 Part 2 diagnosis of sc development project 13327 (NOT LOCKED; development data only).
Replays the frozen sc build lifecycle learner (BP.learn_class_bounded, growth = learned) step by step on the 13327 build data,
recording at every stage which failure mode applies: field discovery (key / ctrl / numeric fields), control learning (modes vs the
documented machine), register search (time-out vs exhausted), coverage counterexamples, bounded-acceptance counterexamples,
observations per transition. Writes artifacts/x7_dev/diag13327.json."""
import json, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import sc_platform as SCP, ba_accept as BA, ba_learn as BL, oc_learner as OL, t7_repair as TR, u5_statesplit as SP
from nexus import u5_stateful as SF
import ba_eps
ROOT = Path(__file__).resolve().parents[1]


def describe(L):
    m = L.machine
    if not m:
        return None
    return dict(n_modes=m["n"], regs=[dict(field=r["field"], upd={str(k): SP.S.src(g) for k, g in r["upd"].items()}) for r in m["regs"]],
                sources={str(k): v for k, v in m["sources"].items()})


def main(seed=13327):
    P = SCP.Project(seed, "sc_dev")
    view_arm = SCP.NexusArmSchema("diag", None)
    evs = [e for t in range(1, SCP.PL.BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
    outs = P.oracle_B(evs, "build_labels")
    view, filled = view_arm.learning_view(evs)
    q = lambda x: P.oracle_B(x)                                        # noqa: E731
    out = dict(seed=seed, domain=P.domain, fault=P.fault, sfam=P.sfam, n_events=len(evs), filled=filled,
               kinds=Counter(e[P.schema.kind] for e in evs), keys=len({e[P.schema.key] for e in evs}),
               out_labels=Counter(r[0] for rows in outs for r in rows))
    # observations per (reference mode, kind): how often each documented transition was seen in the build data
    st, obs = {}, Counter()
    for e in evs:
        k = e[P.schema.key]
        s = st.get(k, SF.INIT[P.sfam])
        obs[(s[0], e[P.schema.kind])] += 1
        st[k], _ = SF.step(P.sfam, s, e[P.schema.kind], e[P.schema.val], P.x3)
    out["ref_transition_observations"] = {f"{a}|{b}": c for (a, b), c in sorted(obs.items())}
    f = SP.discover_fields(view, outs, q)
    out["discover_fields"] = f
    # growth path (learned policy), as in learn_class_bounded
    growth = ba_eps.policy("learned", "bounded")
    ep = SCP.BP._Ep(view, outs, q)
    H, cache, rnd = dict(OL.H0), {}, __import__("random").Random(seed)
    steps = []
    t0 = time.process_time()
    for i in range(6):
        c = time.process_time()
        ok, L, cex, scope = BL.attempt(ep, H, "bounded", None, cache, seed)
        sig = OL.signature(L, cex)
        steps.append(dict(step=i, ok=ok, H={k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in H.items()},
                          machine=describe(L), n_cex=len(cex), cex_words=[list(w) for _, _, w in cex[:4]],
                          cex_rows=[[list(map(str, r)) for r in rows][:6] for _, rows, _ in cex[:2]],
                          signature=list(map(str, sig)), cpu_s=round(time.process_time() - c, 2), queries=L.n_mq if L else None))
        if ok or time.process_time() - t0 > 240:
            break
        a = growth(sig, H, rnd)
        steps[-1]["action"] = str(a)
        H, _ = OL.apply(a, H)
    out["growth_steps"] = steps
    # full-space fallback, instrumented
    c = time.process_time()
    L = TR.Learner2(view, outs, q, seed=seed, max_s=60.0)
    fs = dict(key=L.key, ctrl=L.ctrl, numeric=L.f["numeric"])
    m = L.learn()
    fs["learn"] = dict(ok=m is not None, cpu_s=round(time.process_time() - c, 2), hyp_states=L.hyp["n"] if getattr(L, "hyp", None) else None,
                       machine=describe(L) if m else None)
    rounds = []
    for r in range(6):
        if m is None:
            break
        c = time.process_time()
        cex = TR.coverage_cex(L)
        kind = "coverage"
        if not cex:
            cex, scope = BA.bounded_cex(L, seed=seed + r)
            kind = "bounded"
        rec = dict(round=r, cex_kind=kind if cex else None, n_cex=len(cex), cex_words=[list(w) for _, _, w in cex[:4]],
                   cex_rows=[[list(map(str, x)) for x in rows][:8] for _, rows, _ in cex[:2]])
        if cex:
            evs0, rows0, w0 = cex[0]
            rec["cex_got"] = [list(map(str, x)) for x in SP.run_machine(L.machine, evs0)][:8]
        if not cex:
            rec["accepted"] = True
            rounds.append(rec)
            break
        relabel = False
        for evs1, rows1, word in cex:
            if L._run_labels(L.hyp, word) != tuple(SP._labels(x) for x in rows1):
                relabel = True
                for i in range(len(word)):
                    if tuple(word[i:]) not in L.E:
                        L.E.append(tuple(word[i:]))
            else:
                L.extra_hist.append((evs1, rows1))
        rec["relabel"] = relabel
        hyp = L.learn_control_continue() if relabel else L.hyp
        c2 = time.process_time()
        regs = L.learn_registers(hyp)
        rec["register_search"] = dict(ok=regs is not None, cpu_s=round(time.process_time() - c2, 2), hyp_states=hyp["n"],
                                      n_hist=len(L.histories()) + len(L.extra_hist))
        rec["cpu_s"] = round(time.process_time() - c, 2)
        rounds.append(rec)
        if regs is None:
            m = None
            break
        L.machine = m = L._machine(hyp)
        rec["machine"] = describe(L)
    fs["rounds"] = rounds
    fs["queries"] = L.n_mq
    out["full_space"] = fs
    d = ROOT / "artifacts/x7_dev"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"diag{seed}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(dict(growth=[(s["step"], s["ok"], s["n_cex"], s["cpu_s"], s.get("action")) for s in steps],
                          full=[(r["round"], r.get("cex_kind"), r["n_cex"], r.get("register_search")) for r in rounds],
                          learn=fs["learn"]["ok"]), default=str))


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))

"""Pillar 1 dev experiment (NOT LOCKED): continuation-split class invention vs the flat per-key dictionary template vs a
stateless function, on the three lifecycle families x tdev seeds 0-4 (15 tasks; held-out streams of 200 keys).
Promotion (predeclared): StateSplit promoted iff exact on >= 12/15 AND mean key accuracy >= FlatDict's + 0.10.
Expressiveness gate (predeclared): FlatDict exact on <= 1/15 (the families are not dictionary-expressible)."""
import time
from u5_common import save, seeds
from nexus import u5_stateful as SF, u5_statesplit as SP

rows, code = [], {}
for fam in SF.STATEFUL:
    for s in seeds("tdev", range(5)):
        t = SF.StreamTask(fam, s)
        c0 = time.process_time()
        r = SP.learn_class(t.train, t.y_train, t.query, seed=s)
        cpu = time.process_time() - c0
        q = dict(queries=t.n_queries, query_events=t.n_query_events)
        if r is None or r["source"] is None:
            res = dict(exact=False, event_acc=0.0, key_acc=0.0, crashed=None)
            info = dict(modes=None, regs=None)
        else:
            cls = SP.compile_class(r["source"], r["name"])
            res = t.score(lambda evs: SP.run_class(cls, evs))
            info = dict(modes=r["machine"]["n"], regs=len(r["machine"]["regs"]),
                        witnesses=[[w[0], list(w[1]) if isinstance(w[1], tuple) else w[1], w[2] if not isinstance(w[2], tuple) else list(w[2]),
                                    list(w[3]) if w[3] else None] for w in r["witnesses"]])
            code.setdefault(fam, r["source"])
        f = r["fields"] if r else SP.discover_fields(t.train, t.y_train, t.query)
        flat = t.score(SP.FlatDict(t.train, t.y_train, f).run)
        stl = t.score(SP.Stateless(t.train, t.y_train, f).run)
        rows.append(dict(family=fam, seed=s, statesplit=res, flat=flat, stateless=stl, cpu_s=round(cpu, 3), **q, **info,
                         markov_witness=r.get("markov") if r else None))
        print(fam, s, res["key_acc"], flat["key_acc"], stl["key_acc"], info.get("modes"), info.get("regs"), q, flush=True)
agg = {a: dict(exact=sum(r[a]["exact"] for r in rows), key_acc=round(sum(r[a]["key_acc"] for r in rows) / len(rows), 4),
               event_acc=round(sum(r[a]["event_acc"] for r in rows) / len(rows), 4)) for a in ("statesplit", "flat", "stateless")}
promoted = agg["statesplit"]["exact"] >= 12 and agg["statesplit"]["key_acc"] >= agg["flat"]["key_acc"] + 0.10
gate = agg["flat"]["exact"] <= 1
save("p1.json", dict(rows=rows, aggregate=agg, promoted=promoted, expressiveness_gate=gate, code=code,
                     cpu_s=round(sum(r["cpu_s"] for r in rows), 3)))
print("AGG", agg, "promoted", promoted, "gate", gate)

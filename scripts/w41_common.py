"""Wave 41 shared driver pieces (NOT LOCKED): arm configurations, source learning, Split.Text conversion, per-k scoring.

Arms (identical v5 language, declared scope, depth, Checker v5, base lemmas, witness shortcut, per-task budget):
  Flat_NEXUS_v5                    Fixed+Repr-v5 order, no routing, no skills
  Fixed_Hierarchy                  + human-written specialist routing (w41_hier.FIXED_ROUTES)
  Learned_Hierarchy                + learned specialist routing (presence per signature + specialist bigrams)
  Learned_Hierarchy_PS_Growth      + compiled skills with composed summaries, growth through the shadow vault, rent, retirement
  Size_Matched_Placebo_Hierarchy   the PS_Growth machinery with permuted routing and permuted skill templates
  Flat_noLemma (reference only)    Flat_NEXUS_v5 with the base lemmas OFF (the Wave 40 engine), to price the lemmas themselves"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("Flat_NEXUS_v5", "Fixed_Hierarchy", "Learned_Hierarchy", "Learned_Hierarchy_PS_Growth", "Size_Matched_Placebo_Hierarchy")
GROWS = {"Learned_Hierarchy_PS_Growth", "Size_Matched_Placebo_Hierarchy"}


def arm_cfg(arm, programs, sigs, seed):
    base = dict(programs=programs, sigs=sigs, lemmas=True, witness=True, seed=str(seed))
    return {"Flat_NEXUS_v5": dict(base),
            "Flat_noLemma": dict(base, lemmas=False),
            "Fixed_Hierarchy": dict(base, routing="fixed"),
            "Learned_Hierarchy": dict(base, routing="learned"),
            "Learned_Hierarchy_PS_Growth": dict(base, routing="learned", skills=True, grow=True),
            "Size_Matched_Placebo_Hierarchy": dict(base, routing="placebo", skills=True, grow=True, placebo=True)}[arm]


def learn_sources(ev, tasks, tag, budget):
    """Solve source tasks with the Flat configuration (empty library); certified programs are the learning data. Metered."""
    from nexus import w41_hier as H
    ch = ev.child()
    ev.call(ch, {"cmd": "reset", "cfg": arm_cfg("Flat_NEXUS_v5", [], [], tag)})
    rows, progs, sigs = [], [], []
    for i, t in enumerate(tasks):
        r = ev.solve(ch, t, len(t["teacher"]), f"{tag}:s{i}", budget=budget)
        rows.append(r)
        if r.get("certified"):
            progs.append(r["candidate"]); sigs.append(H.signature(t["public"]))
    ch.close()
    return rows, progs, sigs


def update_job(r, t, depth):
    return {"cmd": "update", "candidate": r["candidate"], "public": t["public"], "query": t["query"], "depth": depth,
            "info": {"search_execs": (r["iters"][0][0] if r.get("iters") else r["execs"])}}


# --------------------------------------------------------------------------- Track 3 conversion (fixed on Split-dev)
def split_tasks(name, input_txt, output_json, max_heldout=50):
    """Each Split.Text task -> up to two string-extraction tasks (line -> its first / last non-delimiter field), harness as in
    Waves 39-40: public = first 3 rows, query = the 4th, held-out = rows 4.. (<= 50), extra queries = held-out inputs 2..17.
    Rows containing null or with a non-modal field count are dropped (headers / blank lines). < 4 rows -> NOT_EVALUABLE."""
    lines = input_txt.split("\n")
    rows = json.loads(output_json)["Rows"]
    pairs = [(l, r) for l, r in zip(lines, rows) if r and all(isinstance(f, str) for f in r)]
    if not pairs:
        return []
    from collections import Counter
    modal = Counter(len(r) for _, r in pairs).most_common(1)[0][0]
    pairs = [(l, r) for l, r in pairs if len(r) == modal]
    if len(pairs) < 4:
        return [dict(name=f"{name}#na", label="NOT_EVALUABLE")]
    r0 = pairs[0][1]
    content = [j for j, f in enumerate(r0) if any(c.isalnum() for c in f)]
    if not content:
        return [dict(name=f"{name}#na", label="NOT_EVALUABLE")]
    out = []
    for j in sorted({content[0], content[-1]}):
        ex = [(l, r[j]) for l, r in pairs][: 4 + max_heldout - 1]
        out.append(dict(name=f"{name}#f{j}", public=[[x, y] for x, y in ex[:3]], query=ex[3][0], answer=ex[3][1],
                        teacher=[{"op": "strip"}], heldout=[[x, y] for x, y in ex[3:]]))
    return out


def prose_task(name, spec):
    import w39_prose as P
    t, why = P.convert(spec, True)
    if t is None:
        return dict(name=name, label=why)
    return dict(t, name=name)


# --------------------------------------------------------------------------- per-k scoring (Track 3)
def score_k(row, t, kmax=2):
    """Per k in 0..kmax: certified (query GLOBAL_SCOPE_UNIQUE from a valid kernel call), HOV, certified-but-held-out-fail,
    silent failures raw (kernel-unique & wrong) and guarded (guard tier UNIQUE & wrong), answered-correct raw / guarded.
    Held-out excludes every input the system queried (same denominator for every k)."""
    from nexus import w39_lang as L
    from nexus import w41_guards as G
    asked = {L.key(x) for x in row.get("queries", [])}
    pool = {L.key(x): y for x, y in t["heldout"]}
    held = [(x, y) for x, y in t["heldout"] if L.key(x) not in asked]
    snaps, checks = row.get("snaps") or [], list(row.get("checks") or [])
    ci = 0
    for s in snaps:
        if s.get("kernel"):
            s["clean"] = checks[ci][1] if ci < len(checks) else False
            ci += 1
    out = {}
    for k in range(kmax + 1):
        cand = [s for s in snaps if len(s.get("queries", [])) <= k]
        s = cand[-1] if cand else None
        if s is None or s.get("candidate") is None:
            out[k] = dict(certified=False, hov=False, cbf=False, silent_raw=0, silent_guard=0, ans_raw=0, ans_guard=0, n_in=0)
            continue
        c = s["candidate"]
        pub = t["public"] + [[x, pool[L.key(x)]] for x in s.get("queries", []) if L.key(x) in pool]
        cert = bool(s.get("kernel") and s.get("clean") and s["label"] == "SCOPE_UNIQUE")
        ok = [L.key(L.run(c, x)) == L.key(y) for x, y in held]
        hov = cert and all(ok)
        ins = [(t["query"], t["answer"], cert)]
        if s.get("kernel") and s.get("extra"):
            for x, a in zip(s["extra_inputs"], s["extra"]):
                if L.key(x) not in asked:
                    ins.append((x, pool[L.key(x)], cert and a == 1))
        tiers = G.label_inputs(pub, c, [x for x, _, _ in ins], [u for _, _, u in ins])
        right = [L.key(L.run(c, x)) == L.key(y) for x, y, _ in ins]
        out[k] = dict(certified=cert, hov=hov, cbf=cert and not all(ok),
                      silent_raw=sum(u and not r for (_, _, u), r in zip(ins, right)),
                      silent_guard=sum(tr == "UNIQUE" and not r for tr, r in zip(tiers, right)),
                      ans_raw=sum(u and r for (_, _, u), r in zip(ins, right)),
                      ans_guard=sum(tr == "UNIQUE" and r for tr, r in zip(tiers, right)), n_in=len(ins) if cert else 0,
                      tiers={tr: tiers.count(tr) for tr in set(tiers)})
    return out

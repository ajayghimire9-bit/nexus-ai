"""Step 1 - forensic diagnosis of FALSE ACCEPTANCES on development failures (NOT LOCKED).

A false acceptance = the learner's acceptance check (t7_repair.coverage_cex, plus oc revision 1's random long words on the
platform) passed a machine that is wrong on the held-out stream. For each one this module records
  w_min        the smallest distinguishing event sequence found (iterative deepening over kind words up to `maxlen`,
               generic fresh values; if none, greedy delta-debugging of the first failing held-out key's sequence)
  fault        the first divergent output; for value errors the transition whose register update first diverges from the
               reference register that is emitted (learned mode/kind/update vs reference mode/kind/update), the
               register values before and after it, and the delay to the emission that exposes it
  why_missed   reconstructed from the acceptance check's own word set (same construction as coverage_cex on the final
               hypothesis): the fault transition never exercised / exercised only with degenerate (zero or coincident)
               register values / corruption created but never emitted within the probe suffix (delayed effect) /
               missing control split / register interaction (a learned register tracks a different reference register)
  origin       strict error separation: candidate machine (learner) vs candidate emission (compiled class disagrees with
               the learned machine) vs checker / oracle / scorer (oracle nondeterminism, tolerance-level differences, or a
               held-out failure that does not reproduce key-locally)
The diagnostician reads the reference mechanism (allowed on DEV); the learner never does."""
from __future__ import annotations

import itertools

from nexus import oc_ocean as OC
from nexus import t7_repair as TR
from nexus import u5_stateful as SF
from nexus import u5_statesplit as SP


# ------------------------------------------------------------------------------------------------ reference targets
class OceanTarget:
    def __init__(self, ep):
        self.m, self.ep = ep.machine, ep

    def rows(self, evs):
        return OC.run(self.m, evs)

    def eq(self, g, w):
        return SP._rows_eq(g, w)

    def trace(self, evs):
        m, q, r, out = self.m, 0, [0] * self.m["regs"], []
        for e in evs:
            s, x = e["kind"], e.get("v", 0)
            if (q, s) not in m["delta"]:
                out.append(dict(mode=q, kind=s, before=tuple(r), after=tuple(r), srcs=[], upd=None, valid=False))
                continue
            srcs = [tuple(None if v is None else (("cur",) if v[0] == "cur" else ("reg", v[1])) for v in (v1, v2))
                    for _, v1, v2 in m["lam"][(q, s)]]
            new = list(r)
            upd = []
            for i in range(m["regs"]):
                u = m["upd"][i].get((q, s))
                upd.append(u or "keep")
                if u:
                    new[i] = round(SP.S.ev(OC.UPDATES[u], {"acc": r[i], "x": x}), 6)
            out.append(dict(mode=q, kind=s, before=tuple(r), after=tuple(new), srcs=srcs, upd=upd, valid=True))
            r, q = new, m["delta"][(q, s)]
        return out


class EmeterTarget:
    """E.meter reference (t7_world.step) on a platform project; strips X5 '_V2' renames exactly as oc_platform.ref_B does."""

    def __init__(self, P):
        self.P, self.sc = P, P.schema

    def rows(self, evs):
        return self.P.ref_B(evs)

    def eq(self, g, w):
        return SF.rows_eq(list(map(tuple, g)), w)

    def trace(self, evs):
        st, out = SF.INIT[self.P.sfam], []
        for e in evs:
            kd = e.get(self.sc.kind)
            if getattr(self.P, "fault", None) == "X5" and isinstance(kd, str) and kd.endswith("_V2"):
                kd = kd[:-3]
            v = e.get(self.sc.val)
            v = v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
            s2, rows = SF.step(self.P.sfam, st, kd, v, self.P.x3)
            srcs = [(("cur",), None) if lab == "estimated" else (("reg", 0), ("reg", 1)) for lab, *_ in rows if lab != "q:invalid"]
            out.append(dict(mode=st[0], kind=kd, before=st[1:], after=s2[1:], srcs=srcs, upd=None, valid=rows != [SF.Q],
                            mode_after=s2[0]))
            st = s2
        return out


# ------------------------------------------------------------------------------------------------ learned machine trace
def learned_trace(m, evs):
    q, r, out = m["init"], [rg["init"] for rg in m["regs"]], []
    for e in evs:
        a = e.get(m["ctrl"])
        if (q, a) not in m["delta"]:
            out.append(dict(mode=q, kind=a, before=tuple(r), after=tuple(r), srcs=[], upd=None, valid=False))
            continue
        srcs = [tuple(m["sources"].get(((q, a), ri, vj)) for vj in (1, 2)) for ri, _ in enumerate(m["lam"][(q, a)])]
        new = list(r)
        upd = []
        for i, rg in enumerate(m["regs"]):
            g = rg["upd"].get((q, a))
            upd.append(g)
            if g is not None:
                x = e.get(rg["field"])
                new[i] = SP.S.ev(g, {"acc": r[i], "x": x if SP._isnum(x) else 0})
        out.append(dict(mode=q, kind=a, before=tuple(r), after=tuple(new), srcs=srcs, upd=upd, valid=True))
        r, q = new, m["delta"][(q, a)]
    return out


def _differs(T, m, evs):
    got, want = SP.run_machine(m, evs), T.rows(evs)
    return [i for i, (g, w) in enumerate(zip(got, want)) if not T.eq(g, w)]


def shortest_distinguishing(L, T, alpha, maxlen=5, cap=40000):
    """Iterative deepening over kind words (prefix-closed outputs, so words of length n also test their prefixes)."""
    n = 0
    for ln in range(1, maxlen + 1):
        for word in itertools.product(alpha, repeat=ln):
            n += 1
            if n > cap:
                return None, n
            evs = L.make_events(word, fresh_values=True)
            d = _differs(T, L.machine, evs)
            if d:
                return evs[: d[0] + 1], n
    return None, n


def ddmin_heldout(L, T, stream, key):
    """First failing held-out key -> its event sequence, greedily minimised while it still fails."""
    keys = []
    for e in stream:
        if e.get(key) not in keys:
            keys.append(e.get(key))
    for k in keys:
        seq = [e for e in stream if e.get(key) == k]
        if _differs(T, L.machine, seq):
            changed = True
            while changed:
                changed = False
                for i in range(len(seq)):
                    s2 = seq[:i] + seq[i + 1:]
                    if s2 and _differs(T, L.machine, s2):
                        seq, changed = s2, True
                        break
            d = _differs(T, L.machine, seq)
            return seq[: d[0] + 1]
    return None


def _fmt(g):
    return "keep" if g is None else SP.S.src(g)


def localise(L, T, evs):
    m = L.machine
    lt, tt = learned_trace(m, evs), T.trace(evs)
    got, want = SP.run_machine(m, evs), T.rows(evs)
    j = next(i for i, (g, w) in enumerate(zip(got, want)) if not T.eq(g, w))
    word = [e.get(m["ctrl"]) for e in evs]
    res = dict(w_min=word, len=len(word), j=j, got=[list(r) for r in got[j]], want=[list(r) for r in want[j]],
               learned_modes=[x["mode"] for x in lt], ref_modes=[x["mode"] for x in tt])
    if word[j] not in L.alpha:
        res.update(kind="out_of_alphabet", detail=f"event kind {word[j]!r} never occurred in the build data (alphabet {list(L.alpha)})")
        return res
    if [r[0] for r in got[j]] != [r[0] for r in want[j]]:
        res.update(kind="control", detail=f"at event {j} ({word[j]}) learned mode_{lt[j]['mode']} emits "
                   f"{[r[0] for r in got[j]]}, reference (mode {tt[j]['mode']}) emits {[r[0] for r in want[j]]}")
        return res
    ri, vj = next((ri, vj) for ri, (g, w) in enumerate(zip(got[j], want[j])) for vj in (1, 2) if not SP._veq(g[vj], w[vj]))
    lsrc = lt[j]["srcs"][ri][vj - 1] if ri < len(lt[j]["srcs"]) else None
    tsrc = tt[j]["srcs"][ri][vj - 1] if ri < len(tt[j]["srcs"]) else None
    res.update(slot=(ri, vj), learned_source=lsrc, ref_source=tsrc)
    if not (lsrc and lsrc[0] == "reg" and tsrc and tsrc[0] == "reg"):
        res.update(kind="value_source", detail=f"slot {vj} of row {ri} at event {j}: learned source {lsrc}, reference {tsrc}")
        return res
    i, k = lsrc[1], tsrc[1]
    p = next((p for p in range(j) if not SP._veq(lt[p]["after"][i], tt[p]["after"][k])), None)
    other = [kk for kk in range(len(tt[0]["after"])) if kk != k]
    tracks_other = bool(other) and p is not None and p > 0 and all(SP._veq(lt[q]["after"][i], tt[q]["after"][other[0]]) for q in range(p))\
        and any(not SP._veq(tt[q]["after"][k], tt[q]["after"][other[0]]) for q in range(j))
    res.update(kind="value", learned_reg=i, ref_reg=k, register_interaction=tracks_other)
    if p is None:
        res.update(detail="registers agree before the emission (value differs at emission only)")
        return res
    lu = lt[p]["upd"][i] if lt[p]["upd"] else None
    res.update(fault_pos=p, delay=j - p, fault_transition=(lt[p]["mode"], word[p]),
               learned_update=_fmt(lu), ref_update=(tt[p]["upd"][k] if tt[p]["upd"] else f"{tt[p]['before']}->{tt[p]['after']}"),
               ref_mode=tt[p]["mode"], before=dict(learned=[round(v, 4) for v in lt[p]["before"]], ref=[round(v, 4) for v in tt[p]["before"]]),
               after=dict(learned=[round(v, 4) for v in lt[p]["after"]], ref=[round(v, 4) for v in tt[p]["after"]]),
               x=evs[p].get(m["regs"][i]["field"]), modes_between=sorted({lt[q]["mode"] for q in range(p + 1, j + 1)}))
    return res


def acceptance_words(L, max_words=1200):
    """The word set coverage_cex builds from the final hypothesis (same construction, same cap)."""
    hyp, alpha = L.hyp, L.alpha
    sufs = list(dict.fromkeys([()] + [(a,) for a in alpha] + [e for e in L.E if len(e) <= 3]))
    words = []
    for q, acc in sorted(hyp["access"].items()):
        loops = [a for a in alpha if hyp["delta"].get((q, a)) == q and hyp["lam"].get((q, a)) != ("q:invalid",)]
        prefixes = [tuple(acc)] + [tuple(acc) + (a,) for a in loops] + [tuple(acc) + (a, b) for a in loops for b in loops]
        for pre in prefixes:
            for a in alpha:
                for w in sufs:
                    words.append(pre + (a,) + tuple(w))
    return list(dict.fromkeys(words))[:max_words]


def why_missed(L, T, loc, max_words=1200):
    if loc["kind"] != "value" or "fault_pos" not in loc:
        if loc["kind"] == "control":
            acc_len = max(len(a) for a in L.hyp["access"].values())
            return dict(reason="missing_control_split",
                        detail=f"distinguishing word of length {loc['len']} (deepest access {acc_len}); no acceptance word reached the "
                               f"divergent continuation - coverage probes 1 transition + suffixes of length <= 3 from each access path")
        if loc["kind"] == "out_of_alphabet":
            return dict(reason="input_outside_declared_alphabet", detail=loc["detail"])
        return dict(reason="wrong_value_source" if loc["kind"] == "value_source" else "other", detail=loc.get("detail", ""))
    t, i, k = loc["fault_transition"], loc["learned_reg"], loc["ref_reg"]
    words = acceptance_words(L, max_words)
    n_reach = n_nondeg = n_corrupt = n_zero = 0
    for w in words:
        evs = L.make_events(w, fresh_values=True)
        lt, tt = learned_trace(L.machine, evs), T.trace(evs)
        for p, (a, b) in enumerate(zip(lt, tt)):
            if (a["mode"], a["kind"]) != t:
                continue
            n_reach += 1
            if all(abs(v) < 1e-9 for v in b["before"]):
                n_zero += 1
            if not SP._veq(a["before"][i], b["before"][k]):
                continue
            if not SP._veq(a["after"][i], b["after"][k]):
                n_corrupt += 1
            else:
                n_nondeg += 1
    stats = dict(acceptance_words=len(words), reached=n_reach, reached_zero_regs=n_zero, corrupted=n_corrupt, agreed=n_nondeg)
    if loc.get("register_interaction"):
        return dict(reason="register_interaction", detail="the learned register tracks a different reference register until the fault; "
                    "their values coincided on every accepted probe", **stats)
    if n_reach == 0:
        return dict(reason="fault_transition_unexercised", detail=f"no acceptance word passes transition {t}", **stats)
    if n_corrupt:
        return dict(reason="delayed_effect_unemitted", detail=f"{n_corrupt} acceptance words corrupt the register at {t} but no word "
                    f"emits it afterwards before a reset (delay in w_min = {loc['delay']})", **stats)
    if n_zero == n_reach:
        return dict(reason="degenerate_zero_registers", detail=f"every acceptance word reaches {t} with all registers 0, where the "
                    f"learned update ({loc['learned_update']}) and the reference ({loc['ref_update']}) coincide", **stats)
    return dict(reason="coincident_values", detail=f"acceptance words reach {t} only in register states where both updates agree", **stats)


def origin(L, T, evs, stream=None):
    """Strict separation: learner machine vs emitted class vs checker / oracle / scorer."""
    m = L.machine
    src, name = SP.class_source(m, witnesses=L.witnesses)
    cls = SP.compile_class(src, name)
    chk = [evs] + ([stream] if stream else [])
    emit_bad = any(not all(SP._rows_eq(list(map(tuple, a)), list(map(tuple, b))) for a, b in zip(SP.run_class(cls, s), SP.run_machine(m, s)))
                   for s in chk)
    r1, r2 = T.rows(evs), T.rows(evs)
    oracle_nondet = not all(T.eq(a, b) for a, b in zip(r1, r2))
    got = SP.run_machine(m, evs)
    mag = max((abs(x - y) for g, w in zip(got, r1) for a, b in zip(g, w) for x, y in zip(a[1:], b[1:])
               if SP._isnum(x) and SP._isnum(y)), default=None)
    tol_artifact = mag is not None and all(g[0] == w[0] for gr, wr in zip(got, r1) for g, w in zip(gr, wr)) and len(got) == len(r1) and mag < 1e-3 \
        and all(len(gr) == len(wr) for gr, wr in zip(got, r1))
    if any(e.get(m["ctrl"]) not in L.alpha for e in evs):
        o = "scope_violation"
    elif emit_bad:
        o = "candidate_emission"
    elif oracle_nondet or tol_artifact:
        o = "checker_or_oracle"
    else:
        o = "candidate_machine"
    return dict(origin=o, emitted_class_matches_machine=not emit_bad, oracle_deterministic=not oracle_nondet,
                max_value_gap=None if mag is None else round(mag, 6))


def diagnose(L, T, alpha, stream=None, maxlen=5):
    evs, n = shortest_distinguishing(L, T, alpha, maxlen)
    how = "iterative_deepening"
    if evs is None and stream is not None:
        evs, how = ddmin_heldout(L, T, stream, L.key), "ddmin_heldout"
    if evs is None:
        return dict(found=False, searched=n)
    loc = localise(L, T, evs)
    loc.update(found=True, search=how)
    loc["why_missed"] = why_missed(L, T, loc)
    loc.update(origin(L, T, evs, stream))
    return loc

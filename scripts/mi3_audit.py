"""MI-3 Stage 1 acceptance audit (NOT LOCKED).
  python scripts/mi3_audit.py gen SPLIT FAMILY START N      SPLIT dev | accept_audit; episodes (seed index START.., FAMILY)
  python scripts/mi3_audit.py assemble SPLIT                quota assembly + gate (accept_audit) / summary (dev)
Candidate construction (frozen with the protocol; identical for dev and the audit). For each episode Episode3(seed, F), in seed
order, the CONSTRUCTOR (not a learner under test; it may use the reference, the checker never does):
  base   the x7 learner (LearnerMI2) learns from the FULL training stream with the privileged witness domain (GRAMMAR5 + the
         episode's true updates) and NO acceptance loop -> candidate "C" if the evaluator finds it exact, else "NAT" (natural
         under-determined error; reported, outside the 240).
  From a correct base (one perturbation each, constructor RNG "mi3-audit-{type}-{F}-{seed}"):
  CONST  wrong constant: one constant c in one register update -> c + d, d in {+1, -1, +2}; if no update has a constant, one
         non-identity update g -> g + 1
  DELAY  delayed effect: one non-identity update moved from transition (q, a) to a transition (q', b) leaving q' = delta(q, a)
  REG    nonzero register: one register's initial value 0 -> v, v in {1, 2, 5}
  KIND   the 26801 mechanism, freshly generated: every training event of one declared kind k that occurs in the held-out stream
         is removed, outputs recomputed by the reference, and the learner relearns -> its alphabet lacks k
Each candidate is checked by old_check and new_check FIRST (they receive the learner object - training data, oracle, hypothesis,
candidate machine - and, for new_check, the declared interface; never the reference, the held-out stream or a witness). Only then
the evaluator classifies it (exact on the held-out stream) and, for an incorrect candidate, records a counterexample WITNESS (the
held-out key's event prefix on which the candidate and the reference differ, re-verified by direct simulation) in a separate
private file. Rows are appended atomically per candidate (resumable).
Audit quotas (accept_audit, filled in seed order by evaluator class only; check outcomes never influence inclusion):
  correct 120 = C x 30 for each of K, MUL, ADDC, SUBH;  incorrect 120 = CONST, DELAY, REG, KIND x 30, each 8/8/7/7 over
  K/MUL/ADDC/SUBH. Gate: new accepts 0/120 incorrect; new accepts >= 114/120 correct; new accepts >= old - 2 on the 120 correct;
  all 240 accounted for within the stage budget."""
import copy, json, random, signal, sys, time
from pathlib import Path
from nexus import mi3_seeds, mi3_accept as A, mi_ocean as M, mi2_learner as M2, mi_learner as ML, seed_registry as R  # noqa: F401
from nexus import u5_statesplit as SP
ROOT = Path(__file__).resolve().parents[1]
FAMS = ("K", "MUL", "ADDC", "SUBH")
QUOTA_C = 30
QUOTA_I = {"CONST": dict(K=8, MUL=8, ADDC=7, SUBH=7), "DELAY": dict(K=8, MUL=8, ADDC=7, SUBH=7),
           "REG": dict(K=8, MUL=8, ADDC=7, SUBH=7), "KIND": dict(K=8, MUL=8, ADDC=7, SUBH=7)}
LEARN_CAP_S = 4.0


def out_dir(split):
    return ROOT / ("artifacts/mi3_dev/audit" if split == "dev" else "artifacts/mi3_accept_audit")


def witness_fn(ep):
    f = M2.witness_fn(ep, "end")
    return f


def learn(train, y, ep, seed):
    L = M2.LearnerMI2(train, y, ep.query, seed=seed, max_s=LEARN_CAP_S)
    L.domain_fn = witness_fn(ep)
    if L.key is None or L.ctrl is None:
        return None
    signal.signal(signal.SIGPROF, M2._raise)
    signal.setitimer(signal.ITIMER_PROF, 2 * LEARN_CAP_S)
    try:
        m = L.learn()
    except Exception:                                                # noqa: BLE001  (includes the CPU cap)
        m = None
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
    return L if m is not None else None


def _consts(g, path=()):
    if isinstance(g, tuple) and g and g[0] == "const":
        yield path
    elif isinstance(g, tuple):
        for j, s in enumerate(g):
            if isinstance(s, tuple):
                yield from _consts(s, path + (j,))


def _set(g, path, v):
    if not path:
        return v
    lst = list(g)
    lst[path[0]] = _set(g[path[0]], path[1:], v)
    return tuple(lst)


def _get(g, path):
    for j in path:
        g = g[j]
    return g


def perturb(m, kind, rnd, alpha):
    m = copy.deepcopy(m)
    ups = [(i, t, g) for i, rg in enumerate(m["regs"]) for t, g in sorted(rg["upd"].items(), key=str)]
    nonid = [u for u in ups if u[2] != ("var", "acc")]
    if kind == "CONST":
        withc = [(i, t, g, p) for i, t, g in ups for p in _consts(g)]
        if withc:
            i, t, g, p = rnd.choice(withc)
            c = _get(g, p)[1]
            d = rnd.choice([1, -1, 2])
            m["regs"][i]["upd"][t] = _set(g, p, ("const", c + d))
            return m, f"reg{i} {t}: const {c} -> {c + d}"
        if not nonid:
            return None, "no update"
        i, t, g = rnd.choice(nonid)
        m["regs"][i]["upd"][t] = ("b", "+", g, ("const", 1))
        return m, f"reg{i} {t}: g -> g + 1"
    if kind == "DELAY":
        opts = []
        for i, t, g in nonid:
            q2 = m["delta"].get(t)
            opts += [(i, t, g, (q2, b)) for b in alpha if (q2, b) in m["delta"] and (q2, b) != t]
        if not opts:
            return None, "no delayable update"
        i, t, g, t2 = rnd.choice(opts)
        del m["regs"][i]["upd"][t]
        m["regs"][i]["upd"][t2] = g
        return m, f"reg{i} update moved {t} -> {t2}"
    if kind == "REG":
        if not m["regs"]:
            return None, "no register"
        i = rnd.randrange(len(m["regs"]))
        v = rnd.choice([1, 2, 5])
        m["regs"][i]["init"] = v
        return m, f"reg{i} init 0 -> {v}"
    raise ValueError(kind)


def check_both(L, cand_m, interface, seed):
    """The ONLY place a checker runs: it gets the learner object with the candidate machine and the declared interface."""
    out = {}
    for name in ("old", "new"):
        L.machine = copy.deepcopy(cand_m)
        q0, c0 = L.n_mq, time.process_time()
        cex, rec = A.old_check(L, seed) if name == "old" else A.new_check(L, interface, seed)
        out[name] = dict(accept=not cex, tier=rec.get("tier"), queries=L.n_mq - q0, cpu_s=round(time.process_time() - c0, 4))
    L.machine = cand_m
    return out


def evaluate(ep, L, cand_m):
    """Evaluator side (after the checks): exactness on the held-out stream and a verified witness for an incorrect candidate."""
    try:
        src, name = SP.class_source(cand_m, witnesses=L.witnesses)
        cls = SP.compile_class(src, name)
        got = SP.run_class(cls, ep.test)
    except Exception as e:                                           # noqa: BLE001
        return False, dict(error=repr(e)[:200])
    want = M.run(ep.machine, ep.test)
    for j, (e, g, w) in enumerate(zip(ep.test, got, want)):
        if not SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))):
            prefix = [x for x in ep.test[:j + 1] if x["key"] == e["key"]]
            g2 = SP.run_class(cls, prefix)[-1]
            w2 = M.run(ep.machine, prefix)[-1]
            verified = not SP._rows_eq(list(map(tuple, g2)), list(map(tuple, w2)))
            return False, dict(event=j, key=e["key"], prefix=[(x["kind"], x.get("v")) for x in prefix],
                               want=w2, got=g2, verified=verified)
    return True, None


def gen(split, fam, start, n):
    seeds = list(R.REGISTRY[("mi3", split)])
    if split == "accept_audit":
        key = ("mi3", "accept_audit")
        if not any(tuple(r["key"]) == key for r in R._spent() if "override" not in r):
            R.claim("mi3", "accept_audit", seeds, run_id="mi3-accept_audit")
    d = out_dir(split)
    d.mkdir(parents=True, exist_ok=True)
    rows_p, wit_p = d / f"rows_{fam}.jsonl", d / f"witness_{fam}.jsonl"
    done = set()
    if rows_p.exists():
        done = {(r["seed"], r["type"]) for r in map(json.loads, rows_p.read_text().splitlines())}
    T0 = time.perf_counter()
    with open(rows_p, "a") as fr, open(wit_p, "a") as fw:
        for si in range(start, min(start + n, len(seeds))):
            s = seeds[si]
            if (s, "base") in done:
                continue
            c0 = time.process_time()
            ep = A.Episode3(s, fam)
            cands = []
            L = learn(ep.train, ep.y_train, ep, s)
            base_ok = False
            if L is not None:
                cands.append(("base", L, copy.deepcopy(L.machine), "learned from full training"))
            for typ, L_, cm, how in cands[:1]:
                chk = check_both(L_, cm, ep.interface, s)
                ok, wit = evaluate(ep, L_, cm)
                base_ok = ok
                emit(fr, fw, s, fam, "base", "C" if ok else "NAT", how, chk, ok, wit, L_, ep)
            if L is None:
                emit(fr, fw, s, fam, "base", "NONE", "learner returned no machine", None, None, None, None, ep)
            if base_ok:
                for typ in ("CONST", "DELAY", "REG"):
                    rnd = random.Random(f"mi3-audit-{typ}-{fam}-{s}")
                    cm, how = perturb(L.machine, typ, rnd, list(L.alpha))
                    if cm is None:
                        emit(fr, fw, s, fam, typ, "NA", how, None, None, None, None, ep)
                        continue
                    chk = check_both(L, cm, ep.interface, s)
                    ok, wit = evaluate(ep, L, cm)
                    emit(fr, fw, s, fam, typ, typ if not ok else "PERTURB_STILL_CORRECT", how, chk, ok, wit, L, ep)
            # KIND (independent of the base outcome): drop one declared, held-out-occurring kind from training and relearn
            rnd = random.Random(f"mi3-audit-KIND-{fam}-{s}")
            tr_kinds = sorted({e["kind"] for e in ep.train})
            te_kinds = {e["kind"] for e in ep.test}
            opts = [k for k in tr_kinds if k in te_kinds and len(tr_kinds) > 2]
            if opts:
                k = rnd.choice(opts)
                tr2 = [dict(e) for e in ep.train if e["kind"] != k]
                L2 = learn(tr2, M.run(ep.machine, tr2), ep, s)
                if L2 is None:
                    emit(fr, fw, s, fam, "KIND", "NONE", f"drop {k}: no machine", None, None, None, None, ep)
                else:
                    cm = copy.deepcopy(L2.machine)
                    chk = check_both(L2, cm, ep.interface, s)
                    ok, wit = evaluate(ep, L2, cm)
                    emit(fr, fw, s, fam, "KIND", "KIND" if not ok else "PERTURB_STILL_CORRECT", f"drop {k} from training", chk,
                         ok, wit, L2, ep)
            else:
                emit(fr, fw, s, fam, "KIND", "NA", "no droppable kind", None, None, None, None, ep)
            print(split, fam, si, s, "episode cpu", round(time.process_time() - c0, 2), "wall", round(time.perf_counter() - T0, 1),
                  flush=True)


def emit(fr, fw, s, fam, typ, cls, how, chk, ok, wit, L, ep):
    row = dict(seed=s, family=fam, type=typ, cls=cls, how=how, check=chk, evaluator_exact=ok,
               regs=len(L.machine["regs"]) if L is not None else None, interface_missing=
               (sorted(set(ep.interface) - set(L.alpha)) if L is not None else None))
    fr.write(json.dumps(row, default=str) + "\n")
    fr.flush()
    if wit is not None:
        fw.write(json.dumps(dict(seed=s, family=fam, type=typ, witness=wit), default=str) + "\n")
        fw.flush()


def assemble(split):
    d = out_dir(split)
    rows = []
    for f in FAMS:
        p = d / f"rows_{f}.jsonl"
        if p.exists():
            rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    wit = {}
    for f in FAMS:
        p = d / f"witness_{f}.jsonl"
        if p.exists():
            for l in p.read_text().splitlines():
                w = json.loads(l)
                wit[(w["seed"], w["family"], w["type"])] = w["witness"]
    sel = {"C": [], "I": []}
    for f in FAMS:
        fr = sorted([r for r in rows if r["family"] == f], key=lambda r: r["seed"])
        sel["C"] += [r for r in fr if r["cls"] == "C"][:QUOTA_C]
        for typ, q in QUOTA_I.items():
            sel["I"] += [r for r in fr if r["cls"] == typ][:q[f]]
    res = dict(split=split, generated=len(rows), by_cls={}, selected=dict(C=len(sel["C"]), I=len(sel["I"])))
    for r in rows:
        res["by_cls"][r["cls"]] = res["by_cls"].get(r["cls"], 0) + 1
    for k in ("old", "new"):
        res[k] = dict(correct_accepted=sum(r["check"][k]["accept"] for r in sel["C"]),
                      incorrect_accepted=sum(r["check"][k]["accept"] for r in sel["I"]),
                      incorrect_accepted_by_type={t: sum(r["check"][k]["accept"] for r in sel["I"] if r["cls"] == t) for t in QUOTA_I},
                      correct_accepted_by_family={f: sum(r["check"][k]["accept"] for r in sel["C"] if r["family"] == f) for f in FAMS},
                      cpu_s=round(sum(r["check"][k]["cpu_s"] for r in sel["C"] + sel["I"]), 2),
                      queries=sum(r["check"][k]["queries"] for r in sel["C"] + sel["I"]))
    res["witnesses_present"] = sum((r["seed"], r["family"], r["type"]) in wit for r in sel["I"])
    res["witnesses_verified"] = sum(bool(wit.get((r["seed"], r["family"], r["type"]), {}).get("verified")) for r in sel["I"])
    res["natural_errors"] = [dict(seed=r["seed"], family=r["family"], old=r["check"]["old"]["accept"], new=r["check"]["new"]["accept"])
                             for r in rows if r["cls"] == "NAT" and r["check"]]
    res["new_rejects_correct"] = [dict(seed=r["seed"], family=r["family"], tier=r["check"]["new"]["tier"],
                                       missing=r["interface_missing"]) for r in sel["C"] if not r["check"]["new"]["accept"]]
    res["old_accepts_incorrect"] = [dict(seed=r["seed"], family=r["family"], cls=r["cls"], how=r["how"]) for r in sel["I"]
                                    if r["check"]["old"]["accept"]]
    full = len(sel["C"]) == 4 * QUOTA_C and len(sel["I"]) == sum(sum(q.values()) for q in QUOTA_I.values())
    if split == "accept_audit":
        res["gate"] = dict(complete=full, zero_false_accepts=res["new"]["incorrect_accepted"] == 0,
                           correct_ge_114=res["new"]["correct_accepted"] >= 114,
                           within_2_of_old=res["new"]["correct_accepted"] >= res["old"]["correct_accepted"] - 2,
                           witnesses=res["witnesses_verified"] == len(sel["I"]))
        res["passed"] = all(res["gate"].values())
    p = d / "summary.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(res, indent=1, default=str))
    tmp.replace(p)
    print(json.dumps({k: v for k, v in res.items() if k not in ("natural_errors",)}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
    else:
        assemble(sys.argv[2])

"""Phase 8 Stage 1 development cases for coverage v8 (NOT LOCKED; agi8de/dev projects only). The harness reads the
generator's truth specs to CONSTRUCT candidate pipelines (development only; the learner and barrier never see them) and
uses the independent hidden evaluator to say whether each constructed pipeline is actually correct.
Cases (generic; no paradigm-specific rule in the barrier):
  absent       truth with the documented threshold filter removed                     -> obligation 'absent' (blocks)
  misleading   absent + a column-to-column comparison on two other integer columns     -> 'absent' (blocks)
  equivalent   the threshold comparison rewritten as an equivalent expression of another shape (x le t -> not(x gt t))
               -> 'implemented' with the correct boundary effect (discharged by the documents)
  moved        (multi-stage) the threshold filter moved to a later stage when its column reaches it -> 'implemented'
  conflict / legacy disagreement / underspecified   full F0 investigations on generated modes
python scripts/agi8_accept_dev.py OUT.json"""
import copy, json, sys
from pathlib import Path
from nexus.de_phase4 import world as W
from nexus.de_phase6 import pipeline6 as P6, world6 as W6, ir6
from nexus.de_phase7 import accept7 as AC7, world7 as W7
from nexus.de_phase8 import accept8 as AC8, lineage8 as L8, procedure8 as PR8, seeds8 as S
ROOT = Path(__file__).resolve().parents[1]
BASE = S.RANGES[("agi8de", "dev")].start + 1900
out = []


def hidden_ok(p, specs):
    try:
        return W6.evaluate6(p, [ir6.lower(s, st["target_lang"]) for s, st in zip(specs, p["stages"])])["ok"]
    except Exception:                                              # noqa: BLE001
        return False


def drop(spec, ref):
    s = copy.deepcopy(spec)

    def rw(e):
        if isinstance(e, list) and e and e[0] == "and":
            a, b = rw(e[1]), rw(e[2])
            return b if a is None else a if b is None else ["and", a, b]
        if isinstance(e, list) and e and e[0] in AC7.SWAP and len(e) == 3 and e[2] == ref:
            return None
        return e
    s["filter"] = rw(s.get("filter"))
    if s["filter"] is None:
        s.pop("filter")
    return s


def reshape(spec, ref):
    neg = {"le": "gt", "lt": "ge", "ge": "lt", "gt": "le"}
    s = copy.deepcopy(spec)

    def rw(e):
        if isinstance(e, list):
            if e and e[0] in neg and len(e) == 3 and e[2] == ref:
                return ["not", [neg[e[0]], e[1], e[2]]]
            return [e[0]] + [rw(x) for x in e[1:]]
        return e
    s["filter"] = rw(s.get("filter"))
    return s


def cov_case(name, p, specs):
    inv = P6.Inv6(p)
    c = AC8.coverage8(inv, specs, cost={})
    ok = hidden_ok(p, specs)
    row = dict(case=name, pid=p["pid"], hidden_correct=ok, obligations=[(o["kind"], o["col"], o["effects"]) for o in c["obligations"]], probe_runs=c["probe_runs"])
    out.append(row)
    print(row, flush=True)


i = 0
for spec in (dict(paradigm="P5", engine="sqlite", dp_mode="explicit"), dict(paradigm="P7", engine="duckdb", dp_mode="explicit"),
             dict(paradigm="P1", engine="sqlite", dp_mode="explicit")):
    p = W7.make_project7(spec, BASE + i, ROOT / "var/agi8_ws/dev/accept")
    i += 1
    truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
    inv = P6.Inv6(p)
    for key in sorted(inv.claim_refs):
        ref = json.loads(key)
        k = next((k for k, t in enumerate(truths) for n in AC7._filters_on(t, ref)), None)
        if k is None:
            continue
        absent = list(truths)
        absent[k] = drop(truths[k], ref)
        cov_case("absent", p, absent)
        d0 = inv.dom(0, inv.legacy)
        ints = sorted(c for c in d0.int_like if c not in {n[1] for n in W6.ir.walk(ref) if n and n[0] == "col"})[:2]
        if len(ints) == 2:
            mis = copy.deepcopy(absent)
            f = ["le", ["cast_int", ["col", ints[0]]], ["cast_int", ["col", ints[1]]]]
            mis[k]["filter"] = ["and", mis[k]["filter"], f] if mis[k].get("filter") else f
            cov_case("misleading", p, mis)
        eq = list(truths)
        eq[k] = reshape(truths[k], ref)
        cov_case("equivalent", p, eq)
        break
# moved: a multi-stage composite whose threshold column reaches the next stage
for j, spec in enumerate((dict(paradigm="X2", dp_mode="explicit"), dict(paradigm="X2", dp_mode="explicit"))):
    p = W7.make_project7(spec, BASE + 10 + j, ROOT / "var/agi8_ws/dev/accept")
    truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
    inv = P6.Inv6(p)
    done = False
    for key in sorted(inv.claim_refs):
        ref = json.loads(key)
        hits = [(k, n) for k, t in enumerate(truths) for n in AC7._filters_on(t, ref)]
        if not hits or hits[0][0] == len(truths) - 1:
            continue
        k, node = hits[0]
        mv = list(truths)
        mv[k] = drop(truths[k], ref)
        nxt = copy.deepcopy(truths[k + 1])
        nxt["filter"] = ["and", nxt["filter"], node] if nxt.get("filter") else node
        mv[k + 1] = nxt
        if hidden_ok(p, mv):
            cov_case("moved_to_later_stage", p, mv)
            done = True
            break
    if done:
        break
else:
    out.append(dict(case="moved_to_later_stage", note="no generated composite carries the threshold column into a later stage with an equivalent result"))
    print(out[-1])
# full investigations with F0 on generated modes
for name, spec in (("conflicting_documents", dict(paradigm="P5", engine="sqlite", dp_mode="conflict_approved")),
                   ("legacy_disagreement", dict(paradigm="P7", engine="duckdb", dp_mode="explicit", legacy_flip=True, fault_p=0.4)),
                   ("underspecified", dict(paradigm="P1", engine="duckdb", dp_mode="undecided"))):
    for tries in range(4):                                     # a project with a repair candidate (development seeds)
        p = W7.make_project7(spec, BASE + 20 + 10 * len(out) + tries, ROOT / "var/agi8_ws/dev/accept")
        st = PR8.investigate(p, PR8.Live(L8.W_SRC, L8.WALL_SRC), L8.empty_memory(), PR8.F0)
        if st.has_candidate:
            break
    o = PR8.outcome(p, st)
    row = dict(case=name, pid=p["pid"], decision=st.decision["kind"], reason=st.decision.get("reason"), verified=o["verified"], wrong=o["wrong"],
               obligations=st.obligation_status, questions=st.cost["questions"])
    out.append(row)
    print(row, flush=True)
Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=str))

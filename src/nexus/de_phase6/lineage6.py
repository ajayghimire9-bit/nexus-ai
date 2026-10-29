"""Phase 6 source lineages, cohorts and the evolvable improver M (NOT LOCKED).

M is NEXUS's LEARNING PROCEDURE (what the improver edits; every key is read by running code):
  skill_min_support / skill_max_len / skill_fine   how methods are invented (skills6.invent / roles)
  trust_margin / trust_support                     how strict calibrated trust is (trust6.decide)
  proc_cycles / typed_pairs                        how procedures are composed (procedure6.learn_policy)
  src_budget / stall_frac                          how much search effort a source project gets
  curriculum                                       tier_order | mixed | hard_first (order of the exogenous source stream)
Full lineages EVOLVE M: a not-yet-tried single-parameter edit M' is compared with M by two clones that each continue the
SAME next source projects under their M and are then evaluated on the same rollout projects; M' is adopted only by the
corrected rule (admission5: more verified, or the same non-empty verified set cheaper; never on equal zero) and the
lineage continues from the winning clone. Stage 3 then compares M*, M0 and a matched random M by full trajectories.

Source pass per project (real execution, Tiers 1-2 only): search under the current memory; read the documents; resolve
conflicts by calibrated trust (exploration uses 'newest' to obtain refutation feedback); one question for an unresolved
decision point; up to 2 submissions; hidden-batch verification (source feedback). Learning:
  pi weights   evidence feature -> operator, + from verified repairs, - from refutations (Full only)
  skills       verified repairs recorded in role form (skills6.record); Full ALSO records partial STAGE repairs of unsolved
               projects (a stage whose schema.yml tests became green) - learning from incomplete experience; invented and
               admitted every 6 projects
  trust        calibrated records from verified submissions, refuted submissions (Full only) and 'undetermined' answers
Cohorts: Full | SolvedOnly (no refutation / partial-stage learning, its own procedure and M) | Fixed (procedure F0, M0) |
Scrambled (the same executions with every feedback association permuted: verification labels, trust labels, skill
provenance)."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

from nexus.de_phase5 import admission5 as A5
from nexus.de_phase6 import pipeline6 as P6, procedure6 as PR, skills6 as SK, trust6 as T6, world6 as W6

M0 = dict(skill_min_support=2, skill_max_len=2, skill_fine=True, trust_margin=1.0, trust_support=2, proc_cycles=3, typed_pairs=True,
          src_budget=1.0, stall_frac=0.25, curriculum="tier_order")
SPACE = dict(skill_min_support=[1, 2, 3], skill_max_len=[1, 2, 3], skill_fine=[True, False], trust_margin=[0.5, 1.0, 2.0], trust_support=[1, 2, 3],
             proc_cycles=[2, 3, 5], typed_pairs=[True, False], src_budget=[0.7, 1.0, 1.5], stall_frac=[0.15, 0.25, 0.4],
             curriculum=["tier_order", "mixed", "hard_first"])
WS = Path(__file__).resolve().parents[3] / "var" / "agi6_ws"
EXPLORE = [["read_all"], ["search", "whole", "on"], ["resolve", "calibrated"], ["if", "unresolved", [["ask", "first"]]], ["submit_or_abstain"]]


def m_random(rng):
    return {k: rng.choice(v) for k, v in SPACE.items()}


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=list).encode()).hexdigest()[:16]


def empty_memory(M=None):
    m = dict(de=dict(w={}, skills={}), trust=T6.empty(), skill_src=[], M=copy.deepcopy(M or M0))
    m["_digest"] = digest({k: v for k, v in m.items() if k != "_digest"})
    return m


def redigest(m):
    m["_digest"] = digest({k: v for k, v in m.items() if k != "_digest"})
    return m


def order_stream(specs, M, rng):
    """The exogenous stream in cycles of the source paradigms: tier_order (Tier 1 first within each cycle), hard_first
    (Tier 2 first), mixed (shuffled within each cycle)."""
    by = {}
    for s in specs:
        by.setdefault(s["paradigm"], []).append(s)
    names = sorted(by, key=lambda p: (W6.TIER[p], p))
    if M["curriculum"] == "hard_first":
        names = sorted(by, key=lambda p: (-W6.TIER[p], p))
    out = []
    for i in range(max(len(v) for v in by.values())):
        cyc = [by[p][i] for p in names if i < len(by[p])]
        if M["curriculum"] == "mixed":
            rng.shuffle(cyc)
        out += cyc
    return out


class Lineage:
    def __init__(self, name, cohort, mem, seeds, adm_seeds, roll_seeds, root, deadline, rng_key):
        self.name, self.cohort, self.mem = name, cohort, mem
        self.seeds, self.adm, self.roll = list(seeds), list(adm_seeds), list(roll_seeds or [])
        self.root, self.deadline = Path(root), deadline
        self.rng = random.Random(f"agi6|{rng_key}")
        self.live = PR.Live(lambda p: self.mem["M"]["src_budget"])
        self.log, self.meta_log, self.rows, self.tried = [], [], [], set()
        self.failures = cohort in ("Full", "Fixed", "Scrambled")

    def left(self):
        return self.deadline - time.time()

    # ---- one source project
    def learn_project(self, spec, seed):
        p = W6.make_project6(spec, seed, self.root / "src")
        mem = self.mem
        st = PR.investigate(p, self.live, mem, EXPLORE)
        cand = st.cand or {}
        subs, verified = [], False
        if st.decision["kind"] == "submit":
            o = PR.outcome(p, st)
            subs.append(o["verified"])
            verified = o["verified"]
            if not verified and self.failures:                       # one more submission with the other trusted option
                tr = [d for d in st.dps if (d["via"] or "").startswith("trust") and len(d["options"]) == 2]
                if len(tr) == 1:
                    st.decision["choices"][f"{tr[0]['stage']}:{tr[0]['pos']}"] = [o_ for o_ in tr[0]["options"] if o_ != tr[0]["resolved"]][0]
                    o2 = PR.outcome(p, st)
                    subs.append(o2["verified"])
                    if o2["verified"]:
                        verified = True
                        tr[0]["resolved"] = st.decision["choices"][f"{tr[0]['stage']}:{tr[0]['pos']}"]
        if self.cohort == "Scrambled":
            verified = self.rng.random() < 0.5 if subs else False     # permuted feedback association
        # calibrated trust records
        for d in st.dps:
            if not d.get("claims"):
                continue
            eff = None
            if d["undecided"]:
                T6.record(mem["trust"], p["pid"], d["claims"], None, "stakeholder undetermined (negative evidence)")
                continue
            if verified and d["resolved"] is not None and d.get("effects"):
                eff = d["effects"][d["options"].index(d["resolved"])]
                how = "verified submission" if len(subs) == 1 else "refuted then verified submission"
                if how.startswith("refuted") and not self.failures:
                    continue
            elif d["via"] == "clarification" and d.get("effects"):
                eff = d["effects"][d["options"].index(d["resolved"])]
                how = "stakeholder answer"
            if eff is not None:
                if self.cohort == "Scrambled":
                    eff = self.rng.choice(["kept", "excluded"])
                T6.record(mem["trust"], p["pid"], d["claims"], eff, how)
        # repair memory: pi weights and skill sources
        feats = set(cand.get("start_features") or [])
        path = cand.get("path") or []
        if verified and path:
            for k, op, prm in path:
                for f in feats:
                    mem["de"]["w"].setdefault(f, {})[op] = mem["de"]["w"].get(f, {}).get(op, 0.0) + 1.0
            try:
                inv = P6.Inv6(p)
                SK.record(mem["skill_src"], p["pid"] if self.cohort != "Scrambled" else f"scr{self.rng.random():.6f}", inv,
                          [tuple(e) for e in path], feats, mem["M"]["skill_fine"])
            except Exception:                                     # noqa: BLE001
                pass
        if self.failures and self.cohort != "Scrambled":
            for r in (cand.get("refutations") or [])[:30]:
                for f in r["pre"]:
                    mem["de"]["w"].setdefault(f, {})[r["op"]] = mem["de"]["w"].get(f, {}).get(r["op"], 0.0) - 0.5
            if not verified and self.cohort == "Full":                # incomplete experience: verified partial STAGE repairs
                stage_fixes = [x for x in (cand.get("partials") or []) if "stage_fail:" in " ".join(x["fixes"])]
                if stage_fixes:
                    try:
                        inv = P6.Inv6(p)
                        SK.record(mem["skill_src"], p["pid"] + "#partial", inv, [(x["stage"], x["op"], x["prm"]) for x in stage_fixes[:2]],
                                  set(stage_fixes[0]["pre"]), mem["M"]["skill_fine"])
                    except Exception:                             # noqa: BLE001
                        pass
        redigest(mem)
        row = dict(project=p["pid"], paradigm=p["paradigm"], decision=st.decision["kind"], submissions=subs, verified=verified,
                   questions=st.cost["questions"], wall=st.cost["wall_s"], skills=len(mem["de"]["skills"]))
        self.rows.append(row)
        return row

    # ---- skill invention + corrected admission
    def invent_and_admit(self):
        cands = SK.invent(self.mem["skill_src"], self.mem["M"]["skill_min_support"], self.mem["M"]["skill_max_len"])
        known = {json.dumps(s["edits"]) for s in self.mem["de"]["skills"].values()}
        cands = [c for c in cands if json.dumps(c["edits"]) not in known][:2]
        if not cands or len(self.adm) < 2 or self.left() < 10:
            return
        projs = []                                     # admission projects whose initial evidence the skill applies to
        pre = set(cands[0]["pre"])
        for _ in range(6):
            if len(projs) == 2 or not self.adm:
                break
            s = self.adm.pop(0)
            try:
                p = W6.make_project6(SOURCE_SPECS[s % len(SOURCE_SPECS)], s, self.root / "adm")
                ev0 = P6.Inv6(p).run(P6.Inv6(p).legacy)
            except Exception:                                     # noqa: BLE001
                continue
            if not pre or len(pre & ev0["features"]) / len(pre) >= 0.5:
                projs.append(p)
        if len(projs) < 2:
            return

        def judge(de):
            rows = {}
            for p in projs:
                t = time.time()
                try:
                    inv = P6.Inv6(p)
                    r = P6.search(inv, de, self.mem["M"]["src_budget"], use_skills=True, skills_mod=self.live.proposer)
                except Exception:                                 # noqa: BLE001
                    r = dict(outcome="none")
                ok = False
                if r["outcome"] == "submitted":
                    files = [P6.ir6.lower(s, st["target_lang"]) for s, st in zip(r["specs"], p["stages"])]
                    ok = W6.evaluate6(p, files)["ok"]
                rows[p["pid"]] = dict(correct=ok, completed=ok, wrong=r["outcome"] == "submitted" and not ok,
                                      cost=dict(wall_s=time.time() - t, questions=0))
            return rows
        base = judge(self.mem["de"])
        for c in cands:
            trial = copy.deepcopy(self.mem["de"])
            trial["skills"]["tmp"] = c
            ok, why = A5.admit(base, judge(trial), min_saving=0.2)
            if ok:
                sid = f"S{len(self.mem['de']['skills'])}"
                self.mem["de"]["skills"][sid] = dict(c, admission=why, validated_on=sorted(base))
            self.log.append(dict(step="skill_admission", edits=c["edits"], support=c["support"], admitted=ok, why=why))
        redigest(self.mem)

    # ---- improver: paired rollout of M vs M'
    def meta_rollout(self, n_learn=3, n_eval=3):
        edits = [(k, v) for k, vals in SPACE.items() for v in vals if v != self.mem["M"][k] and (k, v) not in self.tried]
        if not edits or len(self.roll) < n_learn + n_eval or self.left() < 20:
            return False
        k, v = self.rng.choice(edits)
        self.tried.add((k, v))
        learn = [self.roll.pop(0) for _ in range(n_learn)]
        evs = [self.roll.pop(0) for _ in range(n_eval)]
        outs = []
        for tag, M in (("current", self.mem["M"]), ("edited", dict(self.mem["M"], **{k: v}))):
            c = Lineage(f"{self.name}|{tag}", self.cohort, copy.deepcopy(self.mem), learn, self.adm[:], [], self.root, self.deadline,
                        f"{self.name}|roll{len(self.meta_log)}")
            c.mem["M"] = copy.deepcopy(M)
            redigest(c.mem)
            for s in learn:
                c.learn_project(SOURCE_SPECS[s % len(SOURCE_SPECS)], s)
            c.invent_and_admit()
            rows = {}
            for s in evs:
                try:
                    p = W6.make_project6(SOURCE_SPECS[(s + 3) % len(SOURCE_SPECS)], s, self.root / "roll")
                except RuntimeError:
                    continue
                st = PR.investigate(p, c.live, c.mem, PR.F0)
                o = PR.outcome(p, st)
                rows[p["pid"]] = dict(correct=o["verified"] or (o["decision"] == "abstain" and bool(p["undecided"])), completed=o["verified"],
                                      wrong=o["wrong"], cost=dict(wall_s=st.cost["wall_s"], questions=st.cost["questions"]))
            outs.append((c, rows))
        (ca, ra), (cb, rb) = outs
        adopted, why = A5.admit(ra, rb, min_saving=0.1)
        win = cb if adopted else ca
        self.meta_log.append(dict(edit=[k, v], adopted=adopted, why=why, eval_projects=sorted(ra)))
        self.mem, self.rows = win.mem, self.rows + [dict(r, phase="rollout") for r in win.rows]
        self.log += win.log
        return True


SOURCE_SPECS = [dict(paradigm=p, engine=e) for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7") for e in ("sqlite", "duckdb", "duckdb", "spark")] + \
               [dict(paradigm=x) for x in ("X1", "X2") for _ in range(4)]

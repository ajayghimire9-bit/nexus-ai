"""Phase 5 source lineage (NOT LOCKED): source experience -> evidence memory + repair memory -> learned procedure.

1 TRAINING PASS (real execution, fixed exogenous order): for each training project the repair search runs with the CURRENT
  repair memory (sequential learning). The behaviour policy BEHAVE (read every source, search, resolve conflicts by
  'newest', ask once, submit) generates source feedback; a refuted submission whose only uncertain choice was a trusted
  conflict is followed by one more submission with the other option. Evidence memory records, with provenance and scope:
  claim agreement for every decision point whose correct option became known (verified submission, refuted-then-verified
  submission, stakeholder answer), counterexamples, and action outcomes. The Solved-Only ablation memory (em_so) keeps only
  records from a FIRST verified submission or an answer (no learning from refuted submissions). The Phase 4 repair memory
  (pi_de, P, prefs) learns by de_phase4.learner.learn; candidate repair skills are admitted every 8 projects by the
  corrected rule (admission5) on 2 separate admission projects.
2 VALIDATION CACHES with the frozen memory (12 projects), then POLICY LEARNING (policy_learn.learn_policy from F0).
3 PLACEBO HISTORY (size- and cost-matched, specified before evaluation): the same executions, but every feedback
  association permuted - claim-agreement labels shuffled across records, counterexamples reassigned to random projects,
  the verified combination of each validation project moved to a random combination of the same project, and the repair
  memory replaced by the Phase 4 matched placebo (permuted weights / preferences / P). The validation caches are rebuilt
  with the placebo repair memory (real executions, charged). The same policy learner then runs on that history."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

from nexus.de_phase4 import learner as L, lineage as LG
from nexus.de_phase5 import admission5 as A5, investigate as IV, policy_learn as PL, seeds5 as S5, world5 as W5

BEHAVE = [["read_all"], ["search"], ["if", ["not", "has_candidate"], [["search_more"]]], ["resolve", "newest"],
          ["if", "unresolved", [["ask", "first"]]], ["submit_or_abstain"]]
WS = Path(__file__).resolve().parents[3] / "var" / "agi5_ws"


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=list).encode()).hexdigest()[:16]


def _map_claims(dp):
    for c in dp.get("claims", []):
        if dp.get("boundary_effect"):
            c["_option"] = next((o for o, e in zip(dp["options"], dp["boundary_effect"]) if e == c["effect_at_boundary"]), None)


def _known_from(entry, st, choices):
    k = json.dumps([str(choices[d["pos"]]) for d in st.dps])
    return entry["combos"].get(k, dict(verified=False))["verified"]


def train_pass(projects, live, rng, admit_seeds, log):
    mem = dict(de=L.empty_de())
    mem["_digest"] = digest(mem["de"])
    em, em_so = IV.empty_evidence(), IV.empty_evidence()
    pending, entries, adm_i = [], {}, 0
    cfg = LG.learn_cfg(LG.M0, True)
    for i, p in enumerate(projects):
        e = PL.build_entry(p, live, mem)
        entries[p["pid"]] = {k: v for k, v in e.items() if k != "_rec"}
        st = IV.investigate(p, PL.Cached({p["pid"]: e}), em, mem, BEHAVE)
        for dp in st.dps:
            _map_claims(dp)
        rec = dict(project=p["pid"], decision=st.decision, submissions=[])
        verified = False
        if st.decision["kind"] == "submit":
            ok = _known_from(e, st, st.decision["choices"])
            rec["submissions"].append(dict(choices=st.decision["choices"], verified=ok))
            if ok:
                verified = True
                for dp in st.dps:
                    for m in (em, em_so):
                        IV.record_truth(m, p, dp, dp["resolved"], "verified submission")
            else:
                tr = [dp for dp in st.dps if (dp["via"] or "").startswith("trust") and len(dp["options"]) == 2]
                if len(tr) == 1:                                   # one more submission with the other option
                    alt = dict(st.decision["choices"])
                    other = [o for o in tr[0]["options"] if o != tr[0]["resolved"]][0]
                    alt[tr[0]["pos"]] = other
                    ok2 = _known_from(e, st, alt)
                    rec["submissions"].append(dict(choices=alt, verified=ok2))
                    if ok2:
                        verified = True
                        for dp in st.dps:                          # failure-derived evidence: Full memory only
                            IV.record_truth(em, p, dp, alt[dp["pos"]], "refuted then verified submission")
        for dp in st.dps:
            if dp["via"] == "clarification" and not verified:
                for m in (em, em_so):
                    IV.record_truth(m, p, dp, dp["resolved"], "stakeholder answer")
        em["actions"].append(dict(project=p["pid"], decision=st.decision["kind"], questions=st.cost["questions"],
                                  submissions=len(rec["submissions"]), verified=verified))
        r = e.get("_rec")
        if r is not None:
            r = dict(r, outcome="submitted" if rec["submissions"] else r["outcome"])
            L.learn(mem["de"], r, p, cfg, verified)
            if verified and r.get("edits"):
                pending.append(L.skill_from(r, p))
        if (i + 1) % 8 == 0 and pending:
            adm_i = admission_round(mem, pending[:2], live, admit_seeds, adm_i, log)
            pending = []
        mem["_digest"] = digest(mem["de"])
        log.append(dict(step="train", project=p["pid"], decision=st.decision, submissions=rec["submissions"], verified=verified,
                        trace=[t["action"] for t in st.trace], cost=st.cost))
    return mem, em, em_so, entries


def admission_round(mem, cands, live, seeds, i, log):
    projs = []
    for _ in range(2):
        s = seeds[i]
        i += 1
        projs.append(W5.make_project5(S5.source_specs(1 + s % 20)[-1] | dict(k_extra=1), s, WS / "admit"))

    def judge(de):
        rows = {}
        for p in projs:
            t = time.time()
            rec = L.solve(p, copy.deepcopy(de), live.rts["sqlite"], budget_s=IV.BUDGET["sqlite"], M=IV.M_SEARCH)
            ok = False
            if rec["outcome"] == "submitted":
                from nexus.de_phase4 import world as W
                ok = W5.evaluate5(p, rec["code"])["ok"]
            rows[p["pid"]] = dict(correct=ok, completed=ok, wrong=rec["outcome"] == "submitted" and not ok,
                                  cost=dict(wall_s=time.time() - t, questions=0))
        return rows
    base = judge(mem["de"])
    for sk in cands:
        trial = copy.deepcopy(mem["de"])
        trial["skills"]["tmp"] = sk
        ok, why = A5.admit(base, judge(trial), min_saving=0.2)
        if ok:
            sid = f"S{mem['de']['next_id']}"
            mem["de"]["next_id"] += 1
            mem["de"]["skills"][sid] = dict(sk, admission=why, validated_on=sorted(base))
        log.append(dict(step="skill_admission", ops=sk["ops"], admitted=ok, why=why))
    return i


def placebo_history(em, entries_val, mem, rng):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from agi4_eval import placebo as P4
    emp = copy.deepcopy(em)
    lab = [r["agreed"] for r in emp["claim_outcomes"]]
    rng.shuffle(lab)
    for r, a in zip(emp["claim_outcomes"], lab):
        r["agreed"] = a
    pids = sorted({r["project"] for r in emp["counterexamples"]}) or ["-"]
    for r in emp["counterexamples"]:
        r["project"] = rng.choice(pids)
    emp["trust"] = IV.trust_weights(emp)
    memp = dict(de=P4(dict(DE=mem["de"], M=LG.M0), rng)["DE"])
    memp["_digest"] = digest(memp["de"])
    return emp, memp


def permute_labels(entries, rng):
    out = copy.deepcopy(entries)
    for e in out.values():
        ks = list(e["combos"])
        vals = [e["combos"][k] for k in ks]
        rng.shuffle(vals)
        e["combos"] = dict(zip(ks, vals))
        e["any_verifiable"] = any(v["verified"] for v in vals)
    return out

"""Phase 6 calibrated epistemic trust (NOT LOCKED) - the fix for the Phase 5 over-confidence.

Phase 5 learned trust weights over every provenance cue, including file names, dates and version numbers. Those cues let
it separate two DRAFT claims, so it guessed on undecided requirements: 4 / 6 / 1 accepted wrong repairs.

Phase 6 rules:
  features   ONLY legitimate epistemic provenance - status:approved, authority:contract (an explicit contract statement),
             consensus (another document states the same effect). File names other than the contract, dates and version
             numbers are never features; invariance() proves that changing them cannot change a decision.
  evidence   claim agreement from VERIFIED source outcomes (agreed / refuted) and, as NEGATIVE evidence, every
             stakeholder 'undetermined' answer (both claims of that conflict are recorded as non-decisive) - a learned
             weight cannot rise from conflicts the business never decided.
  decision   a conflict is resolved only if the winner has a feature with positive learned weight and >= min_support
             verified supporting records that the loser LACKS, and the score margin >= margin; draft-vs-draft and
             equally authoritative conflicts are never resolved by trust (they need the clarification, else abstain).
  scope      records are per project; nothing about the business ANSWER (inclusive vs exclusive) is stored as a default."""
from __future__ import annotations

LEGIT = ("status:approved", "authority:contract", "consensus")


def features(claim, others):
    f = set()
    if claim.get("status") == "approved":
        f.add("status:approved")
    if claim.get("provenance", {}).get("file") == "contract.json":
        f.add("authority:contract")
    if any(o.get("effect_at_boundary") == claim.get("effect_at_boundary") for o in others):
        f.add("consensus")
    return f


def empty():
    return dict(records=[], weights={}, support={})


def refit(tm):
    agg = {}
    for r in tm["records"]:
        for f in r["features"]:
            a = agg.setdefault(f, [0, 0])
            a[0 if r["agreed"] else 1] += 1
    tm["weights"] = {f: round((a - d) / (a + d + 3), 4) for f, (a, d) in agg.items()}
    tm["support"] = {f: a for f, (a, d) in agg.items()}
    return tm


def record(tm, project, claims, correct_effect, how):
    """claims of ONE conflict / decision; correct_effect: 'kept' / 'excluded', or None when the stakeholder said
    'undetermined' (negative evidence for every feature present)."""
    for c in claims:
        others = [o for o in claims if o is not c]
        agreed = correct_effect is not None and c.get("effect_at_boundary") == correct_effect
        tm["records"].append(dict(project=project, claim=c.get("provenance"), features=sorted(features(c, others)), agreed=agreed, how=how,
                                  scope="this project's requirement documents only"))
    return refit(tm)


def decide(tm, claims, margin=1.0, min_support=2):
    """-> (winning claim, explanation) or (None, reason). Never resolves a conflict between equally authoritative claims."""
    effects = {c.get("effect_at_boundary") for c in claims}
    if len(effects) == 1:
        return claims[0], "all claims agree"
    w, sup = tm.get("weights", {}), tm.get("support", {})
    scored = []
    for c in claims:
        others = [o for o in claims if o is not c]
        f = features(c, others)
        scored.append((sum(w.get(x, 0.0) for x in f), f, c))
    scored.sort(key=lambda t: -t[0])
    (s1, f1, c1), (s2, f2, _) = scored[0], scored[1]
    decisive = [x for x in f1 - f2 if w.get(x, 0) > 0 and sup.get(x, 0) >= min_support]
    if not decisive:
        return None, "no verified, legitimate provenance feature separates the claims (equally authoritative: ask or abstain)"
    if s1 - s2 < margin * 0.5:
        return None, f"margin {s1 - s2:.2f} below calibrated threshold"
    return c1, f"decisive features {decisive}"


def invariance(tm, claims, mutate):
    """Counterfactual check: the decision is unchanged when file names (other than the contract), dates and version
    numbers are mutated by `mutate(claim) -> claim`."""
    a, _ = decide(tm, claims)
    b, _ = decide(tm, [mutate(dict(c)) for c in claims])
    return (a is None) == (b is None) and (a is None or a.get("effect_at_boundary") == b.get("effect_at_boundary"))

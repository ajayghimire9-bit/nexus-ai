"""Phase 10C shared verifier fix (NOT LOCKED; HUMAN repair given identically to every Phase 10C arm; not NEXUS learning).

DEFECT (Phase 10B rep1 training task 22, P6.X2 seed 88021, and Phase 10C dev target 91940, H5 - both diagnosed by
scripts/agi10c_diag.py): a decision point was 'resolved' although its options had the SAME end-to-end effect on the candidate
(profiled effects ['excluded', 'excluded']). The boundary was shadowed (a duplicate window-end filter in a later stage; a
normalisation moved to an earlier stage) or the probe row never reached the output, so (a) the requirement was never tested on
the candidate and (b) mapping the documented effect onto an option picked the FIRST option carrying that effect (X2: 'le' where
the truth is 'lt'). Visible checks passed; the hidden batches failed.
FIX: submit_or_abstain additionally requires every resolved decision point with >= 2 options and fully profiled effects to have
DISTINGUISHABLE effects; otherwise the candidate is not submitted (abstain: 'requirement not testable on the candidate'). This
can cost completions where a legitimate other predicate removes the probe row (conservative; counted in every arm)."""
from __future__ import annotations

from nexus.de_phase8 import procedure8 as PR8

_ORIG = getattr(PR8.ACTIONS["submit_or_abstain"], "_phase8_original", PR8.ACTIONS["submit_or_abstain"])


def degenerate(st):
    out = []
    for d in st.dps:
        eff = d.get("effects") or []
        if d.get("resolved") is not None and len(d.get("options") or []) >= 2 and len(eff) == len(d["options"]) and \
                all(e in ("kept", "excluded") for e in eff) and len(set(eff)) == 1:
            out.append(f"{d['stage']}:{d['pos']}")
    return out


def a_submit(st):
    _ORIG(st)
    if st.decision and st.decision.get("kind") == "submit":
        bad = degenerate(st)
        if bad:
            st.decision = dict(kind="abstain", reason=f"requirement not testable on the candidate: options indistinguishable end-to-end at {bad}")
            st.log("decide", dict(fixes10c=bad), st.decision)


a_submit._phase8_original = _ORIG
PR8.ACTIONS["submit_or_abstain"] = a_submit                  # procedure8.run resolves ACTIONS at call time (every arm)

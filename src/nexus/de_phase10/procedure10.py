"""Phase 10 procedures and the shared acceptance rules (NOT LOCKED; human infrastructure given to EVERY arm).

The owner's 'de_accept_v4' checks, versioned here as coverage v10 on top of coverage v8 (accept8):
  1 unimplemented documented requirements BLOCK (coverage v8 'absent' obligations - unchanged)
  2 LEGACY-BASELINE CONFLICT: for every implemented obligation the unedited legacy pipeline's boundary behaviour is
    profiled at the same threshold (accept8.profile on the legacy specs). If every attached claim is UNAPPROVED (no
    approved status, no contract authority) and the claimed effect disagrees with the legacy behaviour, the boundary is
    NOT settled by the claim: the point becomes a conflict for calibrated trust / the single question / abstention.
    Legacy behaviour is evidence, never authority: an approved or contract claim still overrides it.
Everything else is procedure8: F0, coverage-v8 barrier, read / question proxies, method queue (search8), replay screen.
The Live search cache key additionally covers the guide and the method queue contents (P* hypotheses), so arms with
different guides never share a search."""
from __future__ import annotations

import copy
import json

from nexus.de_phase6 import procedure6 as PR
from nexus.de_phase8 import accept8 as AC8, procedure8 as PR8
from nexus.de_phase10 import guide10  # noqa: F401  (registers the guided children generator)

F0 = PR8.F0


def search_digest(mem):
    return json.dumps(dict(w=mem.get("de", {}).get("w", {}), skills=sorted(mem.get("de", {}).get("skills", {}).items(), key=str), guide=mem.get("guide")),
                      sort_keys=True, default=str)


PR8.search_digest = search_digest                            # cache keys include the guide (all arms)


def _authoritative(c):
    return c.get("status") == "approved" or (c.get("provenance") or {}).get("file") == "contract.json"


class Live(PR8.Live):
    def coverage(self, project, cand, skip_refs):
        c = {}
        inv = self._inv(project)
        cov = AC8.coverage8(inv, cand["specs"], cost=c, skip_refs=skip_refs)
        for ob in cov["obligations"]:
            if ob.get("kind") != "implemented":
                continue
            pr = AC8.profile(inv, inv.legacy, ob["ref"], c)
            ob["legacy_effect"] = pr["dependent"][0][2] if pr["dependent"] else None
        cov["probe_runs"] = c.get("probe_runs", 0)
        return cov


def a_resolve(st, trust):
    held = []
    for d in st.unresolved():
        cl = d.get("claims") or []
        effs = {c["effect_at_boundary"] for c in cl}
        if d.get("legacy_effect") and len(effs) == 1 and not any(_authoritative(c) for c in cl) and next(iter(effs)) != d["legacy_effect"]:
            d["conflict"] = True
            d["legacy_conflict"] = True
            held.append((d, cl))
            d["claims"] = []
    PR.a_resolve(st, trust)
    for d, cl in held:
        d["claims"] = cl
        st.log("resolve", dict(stage=d["stage"], legacy_conflict=True), "unresolved: unapproved claim disagrees with the legacy baseline")


PR8.ACTIONS["resolve"] = a_resolve                           # shared by every arm (procedure8.run resolves ACTIONS at call time)
investigate, outcome, cost_s, Cached, build_entry, score = PR8.investigate, PR8.outcome, PR8.cost_s, PR8.Cached, PR8.build_entry, PR8.score


def with_hypotheses(mem, hyps):
    """C1: the method queue also tries the strongest P* hypotheses (after the trusted library)."""
    m = copy.deepcopy(mem)
    for i, h in enumerate(hyps):
        m["de"]["skills"][f"P*{i}"] = dict(edits=h["edits"], pre=[], canonical=json.dumps(h["edits"], default=list), support=h["sources"], uses=0, provisional=True)
    return m

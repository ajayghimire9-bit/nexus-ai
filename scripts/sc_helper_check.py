"""Validate the corrected simulated human repair (HumanRefMachine) independently of NEXUS on every sc_dev project (NOT LOCKED).
For each project: run the helper over all 16 ticks and over ticks 9-16 resumed from a tick-8 checkpoint, compare with the
oracle; also the ba helper (DocMachine, documented field) for contrast. Writes artifacts/sc_dev/helper_check.json."""
import json
from pathlib import Path
from nexus import sc_seeds, sc_platform as SCP, u5_stateful as SF, seed_registry as R  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
rows = []
for s in R.REGISTRY[("sc", "dev")]:
    P = SCP.Project(s, "sc_dev")
    ev = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
    n8 = sum(len(P.ticks[t]["B"]) for t in range(1, 9))
    want = P.ref_B(ev)
    h = SCP.HumanRefMachine(P)
    got = [h.ingest(e) for e in ev]
    h2 = SCP.HumanRefMachine(P)
    for e in ev[:n8]:
        h2.ingest(e)
    st = h2.get_state()
    h3 = SCP.HumanRefMachine(P)
    h3.set_state(st)
    resumed = [h3.ingest(e) for e in ev[n8:]]
    d = SCP.PL.DocMachine(P.sfam, P.schema, x3=P.x3)
    old = [d.ingest(e) for e in ev]
    bad = lambda g: sum(not SF.rows_eq(list(map(tuple, a)), b) for a, b in zip(g, want))  # noqa: E731
    n_new = sum(P.schema.val not in e for e in ev[n8:])
    rows.append(dict(seed=s, fault=P.fault, domain=P.domain, late_records=len(ev) - n8, late_records_without_documented_field=n_new,
                     helper_wrong_rows=bad(got), helper_resumed_wrong_rows=sum(not SF.rows_eq(list(map(tuple, a)), b)
                                                                                   for a, b in zip(resumed, want[n8:])),
                     ba_docmachine_wrong_rows=bad(old)))
by = {}
for r in rows:
    b = by.setdefault(r["fault"], dict(projects=0, helper_wrong=0, resumed_wrong=0, ba_doc_wrong=0, without_field=0))
    b["projects"] += 1
    b["helper_wrong"] += r["helper_wrong_rows"]
    b["resumed_wrong"] += r["helper_resumed_wrong_rows"]
    b["ba_doc_wrong"] += r["ba_docmachine_wrong_rows"]
    b["without_field"] += r["late_records_without_documented_field"]
(ROOT / "artifacts/sc_dev/helper_check.json").write_text(json.dumps(dict(by_condition=by, projects=rows), indent=1))
print(json.dumps(by, indent=0))

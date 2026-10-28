"""Post-hoc X6 harness diagnosis on NON-sealed generator seeds 0-3 (split 'ba_test' -> X6; outside every ba range; no sealed
blob is read) (NOT LOCKED). Measures, for ticks 9-16: (a) wrong lifecycle rows of a machine that is exactly right on the
documented (pre-fault) schema (the human patch DocMachine; also what any correct build machine does after the rename),
(b) whether the platform's human patch can repair X6 at all."""
import json
from pathlib import Path
from nexus import ba_platform as BP, u5_stateful as SF
ROOT = Path(__file__).resolve().parents[1]
out = []
for s in range(4):
    P = BP.Project(s, "ba_test")
    assert P.fault == "X6"
    ev = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
    n8 = sum(len(P.ticks[t]["B"]) for t in range(1, 9))
    want = P.ref_B(ev)
    m = BP.PL.DocMachine(P.sfam, P.schema, x3=P.x3)
    got = [m.ingest(e) for e in ev]
    bad = sum(not SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(got[n8:], want[n8:]))
    out.append(dict(seed=s, domain=P.domain, late_rows=len(ev) - n8, human_patch_wrong_rows=bad,
                    human_patch_reads=P.schema.val, late_value_field=P.schema.val + "_amount"))
    print(out[-1])
(ROOT / "artifacts/ba_test_x6_harness_diag.json").write_text(json.dumps(out, indent=1))

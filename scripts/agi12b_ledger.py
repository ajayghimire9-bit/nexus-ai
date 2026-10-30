"""Phase 12B-aware tracked compute ledger (NOT LOCKED): the frozen Phase 12 verifier (which runs the Phase 11 and 10C-10G verifiers) + a `phase12b` section.
  python scripts/agi12b_ledger.py export     runs/experimental/wave24-agi/ledger.jsonl -> docs/NEXUS_COMPUTE_LEDGER.json
  python scripts/agi12b_ledger.py verify     the frozen Phase 11 verifier (which runs the frozen 10C-10G verifier) AND the Phase 12 section
The copied segment stays VERBATIM and append-only. `phases` / `reconciliation` are computed by the frozen scripts/agi10f_ledger.py and
`phase11` by the frozen scripts/agi11_ledger.py, exactly as before; Phase 12 lives in its own `phase12` section (the NEW 1,500 s grant
as the whole pool; older surplus recorded, not consumed)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agi10f_ledger as L10  # noqa: E402
import agi11_ledger as L11  # noqa: E402
import agi12_ledger as L12  # noqa: E402

PREFIX = "a12b-"


def phase12b(lines):
    rows = [json.loads(l) for l in lines if json.loads(l).get("run", "").startswith(PREFIX)]
    g = json.loads((ROOT / "artifacts/agi12b_grant.json").read_text())
    a = json.loads((ROOT / "artifacts/agi12b_allocation.json").read_text())
    st = {}
    for r in rows:
        s = r["run"][len(PREFIX):].split("-")[0]
        st[s] = round(st.get(s, 0.0) + r["wall_s"], 3)
    used = round(sum(r["wall_s"] for r in rows), 3)
    return dict(prefix=PREFIX, pool_s=g["pool_s"], cap_s=float(a["total_cap_s"]), new_grant_s=g["new_amount_s"], older_surplus_not_consumed_s=g.get("older_surplus_not_consumed_s"),
                ceilings=a["ceilings"], rows=len(rows), used_s=used, child_cpu_s=round(sum(r.get("child_cpu_s", 0) for r in rows), 3), stage_used_s=st,
                status={k: sum(r["status"] == k for r in rows) for k in sorted({r["status"] for r in rows})}, remaining_of_cap_s=round(float(a["total_cap_s"]) - used, 3),
                checks=dict(pool_is_new_grant_only=abs(g["pool_s"] - g["new_amount_s"]) < 1e-9 and not g.get("released_balances"),
                            within_cap=used <= float(a["total_cap_s"]) + 1e-6, every_stage_within_ceiling=all(v <= a["ceilings"].get(s, 0) + 1e-6 for s, v in st.items())))


def export():
    L = L10.SRC.read_text().splitlines()
    i0 = next(i for i, l in enumerate(L) if json.loads(l).get("run", "").startswith("a10c-"))
    seg = L[i0:]
    allowed = tuple(L10.PHASES.values()) + (L11.PREFIX, L12.PREFIX, PREFIX)
    assert all(json.loads(l)["run"].startswith(allowed) for l in seg), "a foreign row inside the segment"
    info, rec = L10.summarise(seg)
    doc = dict(what="Phase 10C-12B charged compute, copied verbatim from the hash-chained ledger; verify with `python scripts/agi12b_ledger.py verify` "
                    "(the frozen `scripts/agi11_ledger.py verify` and `scripts/agi10f_ledger.py verify` also pass)",
               source=str(L10.SRC.relative_to(ROOT)), source_first_line_index=i0, source_total_lines=len(L), prev_sha256_of_first_line=json.loads(seg[0])["prev_sha256"],
               head_sha256=L10.h(seg[-1]), chain_ok=L10.chain_ok(json.loads(seg[0])["prev_sha256"], seg), phases=info, reconciliation=rec, phase11=L11.phase11(seg),
               phase12=L12.phase12(seg), phase12b=phase12b(seg), lines=seg)
    L10.OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({k: doc[k] for k in ("chain_ok", "head_sha256")}), json.dumps({k: v for k, v in doc["phase12"].items() if k != "ceilings"}))


def verify():
    old = L12.verify()
    doc = json.loads(L10.OUT.read_text())
    p = phase12b(doc["lines"])
    ok = dict(frozen_12_11_and_10c_10g_verifiers=old == 0, phase12b_matches=p == doc.get("phase12b"), **p["checks"])
    print(json.dumps(ok, indent=1))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit({"export": export, "verify": verify}[sys.argv[1]]() or 0)

"""Phase 11-aware tracked compute ledger (NOT LOCKED).
  python scripts/agi11_ledger.py export     runs/experimental/wave24-agi/ledger.jsonl -> docs/NEXUS_COMPUTE_LEDGER.json
  python scripts/agi11_ledger.py verify     re-checks the tracked file ALONE: the frozen 10C-10G verifier (scripts/agi10f_ledger.py
                                            verify, unchanged) AND the Phase 11 section
The copied segment stays VERBATIM and append-only (every historical line and hash link preserved; Phase 11 rows are appended by the
meter). The `phases` / `reconciliation` fields are computed exactly as scripts/agi10f_ledger.py computes them (Phase 10C-10G), so the
frozen verifier keeps passing; Phase 11 lives in its own `phase11` section: rows, charged seconds per stage, child CPU, the NEW
1,800 s grant as the whole pool (older surplus recorded, not consumed), and cap / ceiling checks."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agi10f_ledger as L10  # noqa: E402

PREFIX = "a11-"


def phase11(lines):
    rows = [json.loads(l) for l in lines if json.loads(l).get("run", "").startswith(PREFIX)]
    g = json.loads((ROOT / "artifacts/agi11_grant.json").read_text())
    a = json.loads((ROOT / "artifacts/agi11_allocation.json").read_text())
    st = {}
    for r in rows:
        s = r["run"][len(PREFIX):].split("-")[0]
        st[s] = round(st.get(s, 0.0) + r["wall_s"], 3)
    used = round(sum(r["wall_s"] for r in rows), 3)
    return dict(prefix=PREFIX, grant_file="artifacts/agi11_grant.json", allocation_file="artifacts/agi11_allocation.json", pool_s=g["pool_s"], cap_s=float(a["total_cap_s"]),
                new_grant_s=g["new_amount_s"], older_surplus_not_consumed_s=g.get("older_surplus_not_consumed_s"), ceilings=a["ceilings"], rows=len(rows), used_s=used,
                child_cpu_s=round(sum(r.get("child_cpu_s", 0) for r in rows), 3), stage_used_s=st,
                status={k: sum(r["status"] == k for r in rows) for k in sorted({r["status"] for r in rows})},
                remaining_of_cap_s=round(float(a["total_cap_s"]) - used, 3),
                checks=dict(pool_is_new_grant_only=abs(g["pool_s"] - g["new_amount_s"]) < 1e-9 and not g.get("released_balances"),
                            within_cap=used <= float(a["total_cap_s"]) + 1e-6, every_stage_within_ceiling=all(v <= a["ceilings"].get(s, 0) + 1e-6 for s, v in st.items())))


def export():
    L = L10.SRC.read_text().splitlines()
    i0 = next(i for i, l in enumerate(L) if json.loads(l).get("run", "").startswith("a10c-"))
    seg = L[i0:]
    allowed = tuple(L10.PHASES.values()) + (PREFIX,)
    assert all(json.loads(l)["run"].startswith(allowed) for l in seg), "a foreign row inside the segment"
    info, rec = L10.summarise(seg)
    doc = dict(what="Phase 10C-11 charged compute, copied verbatim from the hash-chained ledger; verify with `python scripts/agi11_ledger.py verify` "
                    "(the frozen 10C-10G verifier `python scripts/agi10f_ledger.py verify` also passes)",
               source=str(L10.SRC.relative_to(ROOT)), source_first_line_index=i0, source_total_lines=len(L), prev_sha256_of_first_line=json.loads(seg[0])["prev_sha256"],
               head_sha256=L10.h(seg[-1]), chain_ok=L10.chain_ok(json.loads(seg[0])["prev_sha256"], seg), phases=info, reconciliation=rec, phase11=phase11(seg), lines=seg)
    L10.OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({k: doc[k] for k in ("chain_ok", "head_sha256")}), json.dumps({k: v for k, v in doc["phase11"].items() if k != "ceilings"}))


def verify():
    old = L10.verify()
    doc = json.loads(L10.OUT.read_text())
    p = phase11(doc["lines"])
    ok = dict(frozen_10c_10g_verifier=old == 0, phase11_matches=p == doc.get("phase11"), **p["checks"])
    print(json.dumps(ok, indent=1))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit({"export": export, "verify": verify}[sys.argv[1]]() or 0)

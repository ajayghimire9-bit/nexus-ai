"""Tracked, independently verifiable Phase 10C-10F compute ledger (NOT LOCKED; Phase 10F audit finding 5).
  python scripts/agi10f_ledger.py export     runs/experimental/wave24-agi/ledger.jsonl (untracked) -> docs/NEXUS_COMPUTE_LEDGER.json
  python scripts/agi10f_ledger.py verify     re-checks docs/NEXUS_COMPUTE_LEDGER.json ALONE (no untracked file needed)
The export copies every ledger line from the first Phase 10C row onward VERBATIM (the ledger is hash-chained: each row's
prev_sha256 is the sha256 of the previous line, scripts/../wave31_evaluator.ledger_append). Since that line only a10c- / a10d- /
a10e- / a10f- rows exist, so the copied segment is a contiguous chain: anyone can re-hash the lines, re-sum every charged second
per phase and stage, and re-derive each phase's unused authorised surplus from the committed grant files."""
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runs/experimental/wave24-agi/ledger.jsonl"
OUT = ROOT / "docs/NEXUS_COMPUTE_LEDGER.json"
PHASES = {"10C": "a10c-", "10D": "a10d-", "10E": "a10e-", "10F": "a10f-"}


def h(line):
    return hashlib.sha256(line.encode()).hexdigest()


def phase_info():
    out = {}
    for ph, pre in PHASES.items():
        tag = ph.lower()
        g = json.loads((ROOT / f"artifacts/agi{tag}_grant.json").read_text())
        a = json.loads((ROOT / f"artifacts/agi{tag}_allocation.json").read_text())
        out[ph] = dict(prefix=pre, grant_file=f"artifacts/agi{tag}_grant.json", allocation_file=f"artifacts/agi{tag}_allocation.json",
                       cap_s=float(a["total_cap_s"]), ceilings=a["ceilings"], pool_s=g["pool_s"])
    return out


def summarise(lines):
    rows = [json.loads(l) for l in lines]
    info = phase_info()
    for ph, d in info.items():
        rs = [r for r in rows if r["run"].startswith(d["prefix"])]
        st = {}
        for r in rs:
            s = r["run"][len(d["prefix"]):].split("-")[0]
            st[s] = round(st.get(s, 0.0) + r["wall_s"], 3)
        d.update(rows=len(rs), used_s=round(sum(r["wall_s"] for r in rs), 3), child_cpu_s=round(sum(r.get("child_cpu_s", 0) for r in rs), 3),
                 stage_used_s=st, status={k: sum(r["status"] == k for r in rs) for k in sorted({r["status"] for r in rs})})
        d["unused_of_cap_s"] = round(d["cap_s"] - d["used_s"], 3)
    rec = dict(
        phase10e_pool="Phase 10C unused (1,800 cap - 10C used) + Phase 10D unused (2,400 cap - 10D used)",
        phase10e_pool_s=round(info["10C"]["unused_of_cap_s"] + info["10D"]["unused_of_cap_s"], 3),
        phase10e_surplus_after_s=round(info["10E"]["pool_s"] - info["10E"]["used_s"], 3),
        phase10f_pool="Phase 10E surplus + owner-authorised 300 s buffer (hard cap 950 s)",
        phase10f_pool_s=round(info["10E"]["pool_s"] - info["10E"]["used_s"] + 300.0, 3),
        phase10f_remaining_of_cap_s=round(info["10F"]["cap_s"] - info["10F"]["used_s"], 3))
    rec["checks"] = dict(phase10e_pool_matches_grant=abs(rec["phase10e_pool_s"] - info["10E"]["pool_s"]) < 1e-6,
                         phase10f_pool_matches_grant=abs(rec["phase10f_pool_s"] - info["10F"]["pool_s"]) < 1e-3,
                         every_phase_within_cap=all(d["used_s"] <= d["cap_s"] + 1e-6 for d in info.values()),
                         every_stage_within_ceiling=all(v <= info[ph]["ceilings"].get(s, 0) + 1e-6 for ph in info for s, v in info[ph]["stage_used_s"].items()))
    return info, rec


def chain_ok(first_prev, lines):
    prev = first_prev
    for l in lines:
        if json.loads(l)["prev_sha256"] != prev:
            return False
        prev = h(l)
    return True


def export():
    L = SRC.read_text().splitlines()
    i0 = next(i for i, l in enumerate(L) if json.loads(l).get("run", "").startswith("a10c-"))
    seg = L[i0:]
    assert all(any(json.loads(l)["run"].startswith(p) for p in PHASES.values()) for l in seg), "a foreign row inside the segment"
    info, rec = summarise(seg)
    doc = dict(what="Phase 10C-10F charged compute, copied verbatim from the hash-chained ledger; verify with `python scripts/agi10f_ledger.py verify`",
               source=str(SRC.relative_to(ROOT)), source_first_line_index=i0, source_total_lines=len(L), prev_sha256_of_first_line=json.loads(seg[0])["prev_sha256"],
               head_sha256=h(seg[-1]), chain_ok=chain_ok(json.loads(seg[0])["prev_sha256"], seg), phases=info, reconciliation=rec, lines=seg)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({k: doc[k] for k in ("chain_ok", "head_sha256", "reconciliation")}, indent=1))
    print({ph: (d["used_s"], d["cap_s"], d["stage_used_s"]) for ph, d in info.items()})


def verify():
    doc = json.loads(OUT.read_text())
    seg = doc["lines"]
    info, rec = summarise(seg)
    ok = dict(chain=chain_ok(doc["prev_sha256_of_first_line"], seg), head=h(seg[-1]) == doc["head_sha256"],
              sums={ph: info[ph]["used_s"] == doc["phases"][ph]["used_s"] for ph in info}, reconciliation=rec == doc["reconciliation"], **rec["checks"])
    print(json.dumps(ok, indent=1))
    return 0 if all(v if not isinstance(v, dict) else all(v.values()) for v in ok.values()) else 1


if __name__ == "__main__":
    sys.exit({"export": export, "verify": verify}[sys.argv[1]]() or 0)

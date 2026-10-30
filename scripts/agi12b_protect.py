"""Phase 12 protection snapshot (NOT LOCKED; scripts/agi10_protect.py extended to the frozen Phase 10, 10B-10G, 11 and 12 files).
  python scripts/agi12b_protect.py OUT.json [BEFORE.json]
Checks every committed protection manifest (912 protected / 157 sc-ba / 74 ba-oc / 390 x7-sc files; MI-1, MI-2, X7 freezes)
against the working tree, pins checkers v1-v5 to their .sha256 files, records `main`'s tip and the spent-registry rows for the
wave30 final_sealed split, and hashes every frozen MI-1 / MI-2 / X7 file (code + artifacts). With BEFORE, also exits 1 on any
difference from that snapshot."""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ["r1_protected_hashes_before", "sc_ba_hashes_before", "ba_oc_hashes_before", "x7_sc_hashes_before",
             "mi_freeze", "mi2_freeze", "x7_freeze"]
FROZEN_GLOBS = ["src/nexus/mi_*.py", "src/nexus/mi2_*.py", "src/nexus/x7_*.py", "scripts/mi_*.py", "scripts/mi2_*.py",
                "scripts/x7_*.py", "artifacts/mi_*", "artifacts/mi2_*", "artifacts/x7_*", "tests/test_mi.py", "tests/test_mi2.py",
                "tests/test_x7.py", "docs/NEXUS_METHOD_INVENTION_AND_RECURSIVE_IMPROVEMENT_REPORT.md",
                "src/nexus/mi3_*.py", "scripts/mi3_*.py", "artifacts/mi3_*", "tests/test_mi3.py",
                "docs/NEXUS_MI3_ACCEPTANCE_AND_DISCOVERY_DIAGNOSTIC.md",
                "src/nexus/campaign/*.py", "src/nexus/campaign/worlds/*.py", "scripts/agi_*.py", "artifacts/agi_*",
                "tests/test_agi_campaign.py", "docs/NEXUS_MULTI_WORLD_AGI_CAMPAIGN_REPORT.md",
                "src/nexus/campaign2/*.py", "scripts/agi2_*.py", "artifacts/agi2_*", "tests/test_agi2_campaign.py",
                "docs/NEXUS_MULTI_WORLD_PHASE2_REPORT.md", "src/nexus/de_*.py", "src/nexus/seed/shared_brain.py",
                "src/nexus/campaign3/*.py", "scripts/agi3_*.py", "artifacts/agi3_*", "tests/test_agi3_campaign.py",
                "docs/NEXUS_PHASE3_REAL_PIPELINE_AND_SPARK_REPORT.md",
                "src/nexus/de_phase4/*.py", "scripts/agi4_*.py", "artifacts/agi4_*", "tests/test_agi4_de.py",
                "docs/NEXUS_PHASE4_SPARK_AND_DE_SCALING_REPORT.md",
                "src/nexus/de_phase5/*.py", "scripts/agi5_*.py", "artifacts/agi5_*", "tests/test_agi5_investigation.py",
                "docs/NEXUS_PHASE5_INVESTIGATION_PROCEDURE_REPORT.md",
                "src/nexus/de_phase6/*.py", "scripts/agi6_*.py", "artifacts/agi6_*", "tests/test_agi6_arena.py",
                "docs/NEXUS_PHASE6_NINE_PARADIGM_HYBRID_REPORT.md", "docs/NEXUS_PHASE6_ERRATUM.md",
                "src/nexus/de_phase7/*.py", "scripts/agi7_*.py", "artifacts/agi7_*", "tests/test_agi7.py",
                "docs/NEXUS_PHASE7_DEEP_HORIZON_CONSOLIDATION_REPORT.md",
                "src/nexus/de_phase8/*.py", "scripts/agi8_*.py", "artifacts/agi8_*", "tests/test_agi8.py",
                "docs/NEXUS_PHASE8_FUTURE_LEARNING_AND_TRANSFER_REPORT.md",
                "src/nexus/de_phase9/*.py", "scripts/agi9_*.py", "scripts/agi9b_*.py", "artifacts/agi9_*", "artifacts/agi9b_*", "tests/test_agi9*.py",
                "src/nexus/de_phase10/*.py", "scripts/agi10_*.py", "artifacts/agi10_*", "tests/test_agi10.py",
                "docs/NEXUS_PHASE10_UNIFIED_WAKE_SLEEP_SELF_EVOLUTION_REPORT.md",
                "src/nexus/de_phase10b/*.py", "scripts/agi10b_*.py", "artifacts/agi10b_*", "tests/test_agi10b.py",
                "docs/NEXUS_PHASE10B_BRIDGE_EXPANSION_AND_CONFIRMATION_REPORT.md",
                "src/nexus/de_phase10c/*.py", "scripts/agi10c_*.py", "artifacts/agi10c_*", "tests/test_agi10c.py",
                "docs/NEXUS_PHASE10C_PROTOCOL.md", "docs/NEXUS_PHASE10C_AUDIT_AND_COMPOSITIONAL_REPORT.md",
                "src/nexus/de_phase10d/*.py", "scripts/agi10d_*.py", "artifacts/agi10d_*", "tests/test_agi10d.py",
                "docs/NEXUS_PHASE10D_PROTOCOL.md", "docs/NEXUS_PHASE10D_OUT_OF_SANDBOX_DAG_REPORT.md",
                "src/nexus/de_phase10e/*.py", "scripts/agi10e_*.py", "artifacts/agi10e_*", "tests/test_agi10e.py",
                "docs/NEXUS_PHASE10E_PROTOCOL.md", "docs/NEXUS_PHASE10E_REPLAY_MACROS_AND_EXTERNAL_INGESTION_REPORT.md",
                "src/nexus/de_phase10f/*.py", "scripts/agi10f_*.py", "artifacts/agi10f_*", "tests/test_agi10f.py",
                "docs/NEXUS_PHASE10F_PROTOCOL.md", "docs/NEXUS_PHASE10F_SUBGROUP_ABSTRACTION_AND_DECOUPLED_EVAL_REPORT.md",
                "src/nexus/de_phase10g/*.py", "scripts/agi10g_*.py", "artifacts/agi10g_*", "tests/test_agi10g.py",
                "docs/NEXUS_PHASE10G_PROTOCOL.md", "docs/NEXUS_PHASE10G_EVIDENCE_ACQUISITION_REPORT.md",
                "src/nexus/de_phase11/*.py", "scripts/agi11_*.py", "artifacts/agi11_*", "tests/test_agi11.py",
                "docs/NEXUS_PHASE11_PROTOCOL.md", "docs/NEXUS_PHASE11_ATOMIC_RELATIONAL_ENGINE_REPORT.md",
                "src/nexus/de_phase12/*.py", "scripts/agi12_*.py", "artifacts/agi12_*", "tests/test_agi12.py",
                "docs/NEXUS_PHASE12_PROTOCOL.md", "docs/NEXUS_PHASE12_ACTIVE_DISAMBIGUATION_REPORT.md"]
LIVING = set()
NEW_OK = "artifacts/mi_logs/a12b-"    # Phase 12 logs land in the shared log folder: additions there are expected


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def frozen_files():
    out = set()
    for g in FROZEN_GLOBS:
        for p in ROOT.glob(g):
            out |= {p} if p.is_file() else {q for q in p.rglob("*") if q.is_file()}
    return sorted(f for f in (str(p.relative_to(ROOT)) for p in out) if f not in LIVING)


def main(out, before=None):
    res, bad = {}, []
    for m in MANIFESTS:
        files = json.loads((ROOT / f"artifacts/{m}.json").read_text())["files"]
        diff = [f for f, h in files.items() if sha(ROOT / f) != h]
        res[m] = dict(n=len(files), differ=len(diff))
        bad += [f"{m}:{f}" for f in diff]
    for v in ["", "_v2", "_v3", "_v4", "_v5"]:
        k = ROOT / f"src/nexus/checker_kernel{v}.py"
        pin = (ROOT / f"src/nexus/checker_kernel{v}.sha256").read_text().split()[0]
        res[f"checker{v or '_v1'}"] = sha(k) == pin
        if sha(k) != pin:
            bad.append(str(k))
    res["main"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
    spent = ROOT / "runs/experimental/seed_registry_spent.jsonl"
    res["final_sealed_rows"] = sum("final_sealed" in l for l in spent.read_text().splitlines()) if spent.exists() else 0
    res["frozen"] = {f: sha(ROOT / f) for f in frozen_files()}
    res["frozen_aggregate"] = hashlib.sha256(json.dumps(res["frozen"], sort_keys=True).encode()).hexdigest()
    res["head"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if before:
        b = json.loads(Path(before).read_text())
        for k in ("main", "final_sealed_rows"):
            if b[k] != res[k]:
                bad.append(k)
        changed = [f for f in b["frozen"] if b["frozen"][f] != res["frozen"].get(f) and not f.startswith(NEW_OK)]
        added = sorted(set(res["frozen"]) - set(b["frozen"]))
        res["added_files"] = added
        bad += [f"frozen:{f}" for f in changed] + [f"added:{f}" for f in added if not f.startswith(NEW_OK)]
    res["violations"] = bad
    Path(out).write_text(json.dumps(res, indent=1, sort_keys=True))
    print({k: v for k, v in res.items() if k not in ("frozen", "violations")}, "frozen files", len(res["frozen"]),
          "violations", len(bad), bad[:5])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))

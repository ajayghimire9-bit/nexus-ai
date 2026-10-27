"""Wave 40 Step 1b completion (NOT LOCKED; audit runner, NEXUS_SEALED_HARNESS_TOKEN, hashes verified): for the 13 PROSE-confirm
(Wave 39, consumed) task files that contain a JSON null anywhere, does any null reach the data Checker v4 saw (the Wave 39 v4
harness converts Input[0] / Output only)? Prints counts only; if a null reached v4 data, runs the exact v4 vs shadow differential."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w39_prose as P
from w40_v4_none_audit import has_null, shadow_v4
from nexus import checker_kernel_v4 as V4, w38_scope as S4, w39_eval as WE
if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
    raise SystemExit("audit runner only")
man = json.loads((ROOT / "artifacts/external/prose_confirm/MANIFEST.json").read_text())
vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave39_prose_confirm"
raw = conv = aff = 0
sh = shadow_v4()
for n, h in sorted(man["sha256"].items()):
    b = (vault / f"{n}.json").read_bytes()
    assert hashlib.sha256(b).hexdigest() == h
    spec = json.loads(b)
    if not has_null(spec):
        continue
    raw += 1
    t, _ = P.convert(spec, False)
    if t is None or not has_null([t["public"], t["query"], t["answer"]]):
        continue
    conv += 1
    sc = S4.scope(t["public"], t["query"], 3)
    pub = [tuple(p) for p in t["public"]]
    sig = lambda r: (r["label"], r.get("k"), r.get("fitting"), r.get("answers"))
    aff += sig(V4._share(pub, t["query"], t["answer"], sc["tools"], 3, "exhaustive")) != sig(sh._share(pub, t["query"], t["answer"], sc["tools"], 3, "exhaustive"))
out = dict(raw_files_with_null=raw, null_in_v4_converted_data=conv, verdicts_changed=aff)
(ROOT / "artifacts/w40_v4_prose_confirm_nulls.json").write_text(json.dumps(out))
print(out)
WE.ledger_append(dict(run="w40-v4-prose-confirm-nulls", wall_s=0.0, status="COMPLETE"))

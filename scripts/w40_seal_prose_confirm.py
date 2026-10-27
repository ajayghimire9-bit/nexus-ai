"""Wave 40 (NOT LOCKED): blind acquisition of PROSE-confirm-2 for Step 5. Selection (fixed before any download, from task NAMES
only): EVERY Transformation.Text task that is neither in PROSE-dev nor in Wave 39's PROSE-confirm manifest (all remaining
tasks; their families all occur in PROSE-dev, because Wave 39 withheld every dev-absent family whole). Files are downloaded by
curl straight into the sealed vault ($NEXUS_SEALED_VAULT_DIR/wave40_prose_confirm2) and hashed by shasum; this process never
opens them and prints only counts. The manifest is committed; only the frozen Step 5 runner (NEXUS_SEALED_HARNESS_TOKEN) may
read the files, after verifying every hash (AGENTS.md RULE 1)."""
import glob, json, os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/microsoft/prose-benchmarks/main/Transformation.Text/{}/spec.json"


def main():
    names = json.loads((ROOT / "artifacts/external/prose_confirm/all_task_names.json").read_text())
    dev = {Path(f).stem for f in glob.glob(str(ROOT / "artifacts/external/prose/*.json"))}
    c1 = set(json.loads((ROOT / "artifacts/external/prose_confirm/MANIFEST.json").read_text())["sha256"])
    sel = sorted(n for n in names if n not in dev and n not in c1)
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave40_prose_confirm2"
    vault.mkdir(parents=True, exist_ok=True)
    man = {}
    for n in sel:
        out = vault / f"{n}.json"
        subprocess.run(["/usr/bin/curl", "-sfL", "--max-time", "60", "-o", str(out), RAW.format(n)], check=True)
        man[n] = subprocess.run(["/usr/bin/shasum", "-a", "256", str(out)], capture_output=True, text=True, check=True).stdout.split()[0]
    d = ROOT / "artifacts/external/prose_confirm2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "MANIFEST.json").write_text(json.dumps({"source": "microsoft/prose-benchmarks main Transformation.Text", "rule": __doc__,
                                                 "split": {n: "dev_family_untouched" for n in sel}, "sha256": man},
                                                indent=1, sort_keys=True))
    print("sealed", len(man), "tasks; families:", len({n.split(".")[0] for n in sel}))


if __name__ == "__main__":
    main()

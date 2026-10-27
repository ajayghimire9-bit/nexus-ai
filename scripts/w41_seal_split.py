"""Wave 41 (NOT LOCKED): blind acquisition of the Track 3 external split, PROSE Split.Text (never used before in NEXUS).
Selection (fixed from task NAMES only, before any download): every Split.Text task except the 5 development tasks chosen by
the 5 smallest sha256('w41-split-dev:' + name) (artifacts/external/split_dev/DEV_SELECTION.json). input.txt / output.json /
meta.json are downloaded by curl straight into the sealed vault ($NEXUS_SEALED_VAULT_DIR/wave41_split) and hashed by shasum;
this process never opens them. Only the frozen Track 3 runner (NEXUS_SEALED_HARNESS_TOKEN) may read them, after verifying
every hash (AGENTS.md RULE 1)."""
import json, os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/microsoft/prose-benchmarks/main/Split.Text/{}/{}"


def main():
    d = ROOT / "artifacts/external/split_dev"
    names = json.loads((d / "all_split_names.json").read_text())
    dev = set(json.loads((d / "DEV_SELECTION.json").read_text())["dev"])
    sel = [n for n in names if n not in dev]
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave41_split"
    man = {}
    for n in sel:
        (vault / n).mkdir(parents=True, exist_ok=True)
        for f in ("input.txt", "output.json", "meta.json"):
            out = vault / n / f
            subprocess.run(["/usr/bin/curl", "-sfL", "--max-time", "60", "-o", str(out), RAW.format(n, f)], check=True)
            man[f"{n}/{f}"] = subprocess.run(["/usr/bin/shasum", "-a", "256", str(out)], capture_output=True, text=True,
                                            check=True).stdout.split()[0]
    o = ROOT / "artifacts/external/split_confirm"
    o.mkdir(parents=True, exist_ok=True)
    (o / "MANIFEST.json").write_text(json.dumps({"source": "microsoft/prose-benchmarks main Split.Text", "rule": __doc__,
                                                 "tasks": sel, "sha256": man}, indent=1, sort_keys=True))
    print("sealed", len(sel), "tasks,", len(man), "files")


if __name__ == "__main__":
    main()

"""Wave 39 (NOT LOCKED): blind acquisition of PROSE-confirm. Selection (fixed before any download, from task NAMES only):
  * every task of the Transformation.Text families that have NO task in PROSE-dev (withheld external families), and
  * 63 untouched tasks of PROSE-dev families, chosen by ascending sha256("w39-prose-confirm:" + name).
Files are downloaded by curl straight into the sealed vault ($NEXUS_SEALED_VAULT_DIR/wave39_prose_confirm, outside the repo) and
hashed by shasum; this process never opens them and prints only counts. The manifest (name -> sha256) is committed; only the
frozen confirmation runner (with NEXUS_SEALED_HARNESS_TOKEN) may read the files, after verifying every hash (AGENTS.md RULE 1)."""
import glob, hashlib, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/microsoft/prose-benchmarks/main/Transformation.Text/{}/spec.json"


def main():
    names = json.loads(Path(sys.argv[1]).read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave39_prose_confirm"
    vault.mkdir(parents=True, exist_ok=True)
    dev = {Path(f).stem for f in glob.glob(str(ROOT / "artifacts/external/prose/*.json"))}
    fam = lambda n: n.split(".")[0]
    devf = {fam(n) for n in dev}
    rest = [n for n in names if n not in dev]
    withheld = sorted(n for n in rest if fam(n) not in devf)
    same = sorted((n for n in rest if fam(n) in devf), key=lambda n: hashlib.sha256(f"w39-prose-confirm:{n}".encode()).hexdigest())[:63]
    sel = {n: ("withheld_family" if n in withheld else "dev_family_untouched") for n in withheld + sorted(same)}
    man = {}
    for n in sel:
        out = vault / f"{n}.json"
        subprocess.run(["/usr/bin/curl", "-sfL", "--max-time", "60", "-o", str(out), RAW.format(n)], check=True)
        man[n] = subprocess.run(["/usr/bin/shasum", "-a", "256", str(out)], capture_output=True, text=True, check=True).stdout.split()[0]
    (ROOT / "artifacts/external/prose_confirm/MANIFEST.json").write_text(json.dumps(
        {"source": "microsoft/prose-benchmarks main Transformation.Text", "rule": __doc__, "split": sel, "sha256": man},
        indent=1, sort_keys=True))
    print("sealed", len(man), "tasks:", sum(v == "withheld_family" for v in sel.values()), "withheld-family,",
          sum(v != "withheld_family" for v in sel.values()), "dev-family untouched; families withheld:",
          len({fam(n) for n in withheld}))


if __name__ == "__main__":
    main()

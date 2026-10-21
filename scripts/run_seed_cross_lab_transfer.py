"""Execute the real cross-lab transfer study (Step 5: Language -> Coding -> Reasoning -> World)."""
import json
from pathlib import Path
from nexus.seed.cross_lab_transfer import run_cross_lab_transfer_study

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = run_cross_lab_transfer_study()
    out_path = ROOT / "artifacts" / "seed_cross_lab_transfer.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()

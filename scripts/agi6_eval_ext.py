"""Phase 6 Stage 4 extension (NOT LOCKED): the pre-registered size rule (report §0.6) extends the attribution arms A4 / A5 /
A6 to repetitions r1 and r2 when the evaluation budget covers them. This wrapper leaves the frozen scripts/agi6_eval.py
unchanged: it restricts arms() to those 6 extension arms and writes rows to targets_ext_c<CHUNK>.jsonl. Decided from the
measured primary-arm cost (589 s for 720 rows) BEFORE any target outcome was scored.
  python scripts/agi6_eval_ext.py CHUNK N"""
import copy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agi6_eval as E  # noqa: E402
from nexus.de_phase6 import lineage6 as L6  # noqa: E402


def ext_arms(kind, dev):
    src, _ = E.paths(dev)
    A = {}
    for r in (1, 2):
        full = E.endpoint(src, f"Full_r{r}")
        A[f"A4_solvedonly_r{r}"] = E.endpoint(src, f"SolvedOnly_r{r}")
        po = copy.deepcopy(full)
        po["mem"]["de"]["skills"] = {}
        L6.redigest(po["mem"])
        A[f"A5_procedure_only_r{r}"] = po
        A[f"A6_scrambled_r{r}"] = E.endpoint(src, f"Scrambled_r{r}")
    return A


if __name__ == "__main__":
    E.arms = ext_arms
    kind = "targets_ext"
    orig_manifest = E.manifest
    E.manifest = lambda k, dev: orig_manifest("targets", dev)
    E.run(kind, sys.argv[1], sys.argv[2])

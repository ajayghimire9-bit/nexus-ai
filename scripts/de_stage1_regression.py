"""Stage 1 regression run (NOT LOCKED): runs and pins the regression suites, writes artifacts/de_stage1_regression.json
(per-file sha256, collected / passed / failed counts) and one ledger row. Suites:
  search-order invariance (state-dominance repair, Wave 40 Step 3), Wave 40 components (witness soundness, O(T) rows),
  Checker kernels v1-v5 (pins + differential tests), Stage 1 outcome-contract distinguishability."""
import hashlib, json, re, subprocess, sys, tempfile, time
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SUITES = ["tests/test_search_order_invariance.py", "tests/test_w40_components.py", "tests/test_checker_kernel.py",
          "tests/test_checker_kernel_v2.py", "tests/test_checker_kernel_v3.py", "tests/test_checker_kernel_v4.py",
          "tests/test_checker_kernel_v5.py", "tests/test_stage1_regression.py"]


def main():
    from nexus.wave31_evaluator import ledger_append
    t0, out = time.perf_counter(), {}
    for s in SUITES:
        t = time.perf_counter()
        xml = Path(tempfile.mkdtemp()) / "j.xml"
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", s], cwd=ROOT,
                           capture_output=True, text=True)
        col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", s], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip().splitlines()[-1]
        su = ET.parse(xml).getroot().iter("testsuite").__next__().attrib
        cnt = dict(tests=int(su["tests"]), failed=int(su["failures"]), errors=int(su["errors"]), skipped=int(su["skipped"]))
        cnt["passed"] = cnt["tests"] - cnt["failed"] - cnt["errors"] - cnt["skipped"]
        found = [(cnt[k], k) for k in ("passed", "failed", "errors", "skipped")]
        cnt["collected"] = int(col.rsplit(":", 1)[1]) if ":" in col else None
        tail = ", ".join(f"{n} {k}" for n, k in found) + f" (collected {cnt['collected']})"
        out[s] = dict(sha256=hashlib.sha256((ROOT / s).read_bytes()).hexdigest(), returncode=p.returncode, summary=tail,
                      wall_s=round(time.perf_counter() - t, 1), **cnt)
        print(f"{s:45s} {tail}", flush=True)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res = dict(revision=git, python=sys.version.split()[0], suites=out,
               all_pass=all(v["returncode"] == 0 for v in out.values()),
               kernel_pins={f"v{i}" if i else "v1": (ROOT / f"src/nexus/checker_kernel{'_v%d' % i if i else ''}.sha256").read_text().split()[0]
                            for i in (0, 2, 3, 4, 5)})
    (ROOT / "artifacts/de_stage1_regression.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    ledger_append(dict(run="de-stage1-regression", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    print("ALL PASS" if res["all_pass"] else "FAILURES", "%.0fs" % (time.perf_counter() - t0))


if __name__ == "__main__":
    main()

"""Smoke test (conventional stop rule): the pipeline runs over the batches without an exception."""
import os, pathlib, subprocess, sys, tempfile

B = pathlib.Path(__file__).resolve().parents[1]


def test_runs_without_exception():
    st = pathlib.Path(tempfile.mkdtemp()) / "state"
    for b in os.environ["DE_BATCHES"].split(os.pathsep):
        subprocess.run([sys.executable, str(B / "pipeline.py"), "--landing", b, "--state", str(st), "--config",
                        str(B / "config.json")], check=True)

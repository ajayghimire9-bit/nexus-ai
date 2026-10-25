"""Wave 26 standing gates (every phase): soundness, cross-process replay, Tycho single-meter accounting."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

VAULT_ENV = "NEXUS_SEALED_VAULT_DIR"
HARNESS_ENV = "NEXUS_SEALED_HARNESS_TOKEN"


def json_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()


def g_soundness(rows, *, key="false_certificate"):
    """G_soundness: number of false UNIQUE certificates over all rows (must be 0)."""
    n = sum(bool(r.get(key)) for r in rows)
    return dict(passed=n == 0, false_certificates=n)


def g_replay(script, args, recorded_digest, *, hash_seed="271828"):
    """G_replay: re-invoke `script --digest-only ...` in a fresh process with a different string-hash seed."""
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    p = subprocess.run([sys.executable, script, *args, "--digest-only"], env=env, capture_output=True, text=True,
                       check=True)
    replayed = p.stdout.strip().splitlines()[-1]
    return dict(passed=replayed == recorded_digest, recorded=recorded_digest, replayed=replayed, hash_seed=hash_seed)


def g_tycho(rows, *, total_key="work", parts_key="work_by"):
    """G_tycho: every row's total equals the sum of its itemised single-meter categories (no off-meter work)."""
    bad = [i for i, r in enumerate(rows) if parts_key in r and abs(sum(r[parts_key].values()) - r[total_key]) > 1e-6]
    return dict(passed=not bad, rows=len(rows), mismatched=len(bad))


def install_vault_audit_hook(*, log_path=None):
    """Blind-vault firewall: any open() under $NEXUS_SEALED_VAULT_DIR raises unless the process carries the
    locked harness token (set only by the sealed single-shot runner). Every attempt is appended to log_path."""
    vault = os.environ.get(VAULT_ENV)
    if not vault:
        return False
    vault = os.path.realpath(vault)
    allowed = bool(os.environ.get(HARNESS_ENV))

    def hook(event, args):
        if event != "open" or not args:
            return
        path = args[0]
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        try:
            real = os.path.realpath(os.fsdecode(path))
        except Exception:
            return
        if real == vault or real.startswith(vault + os.sep):
            if log_path:
                with open(log_path, "a") as f:
                    f.write(json.dumps(dict(path=real, allowed=allowed)) + "\n")
            if not allowed:
                raise PermissionError(f"blind-vault firewall: {real} may only be read by the locked harness")
    sys.addaudithook(hook)
    return True

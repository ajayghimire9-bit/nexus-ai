"""Message-only capabilities with OS-denied learner filesystem/network access.

macOS sandbox-exec is required for these development fixtures. No permissive
fallback. Processes inherit the parent's process group for host cleanup.
This is NOT a hostile same-UID/root isolation claim.
"""
from __future__ import annotations

import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

from .contracts import MAX_MESSAGE_BYTES, decode, encode, request, response


class _Process:
    role = None

    def __init__(self, repository, deny_paths=(), timeout=5):
        self.root = Path(repository).resolve()
        binary = shutil.which("sandbox-exec")
        if binary is None or sys.platform != "darwin":
            raise RuntimeError("OS sandbox backend unavailable; no unsandboxed fallback")
        if not 0 < timeout <= 5:
            raise ValueError("bounded RPC timeout required")
        self.timeout = timeout
        self.next_id = 0
        self.started = False
        paths = list(deny_paths)
        if self.role in ("learner", "environment"):
            paths += [self.root / p for p in ("artifacts", "configs", "docs", ".git", "runs",
                       "src/nexus/seed/primitive_transfer_v2/private_evaluator.py")]
        if self.role == "learner":
            paths += [self.root / "src/nexus/seed/open_primitive_transfer.py"]
        # Explicit caller paths let tests demonstrate denied secret reads using
        # the actual child profile, rather than inferring privacy from key names.
        clauses = []
        for path in paths:
            path = str(Path(path).resolve())
            if any(c in path for c in ('"', "\\", "\n", "\r")):
                raise ValueError("unsafe sandbox path")
            clauses.append(f'(deny file-read* (subpath "{path}"))')
        self.profile = '(version 1)(allow default)(deny network*)(deny file-write*)' + ''.join(clauses)
        # Do not copy API tokens, private seed variables or other parent secrets.
        env = dict(PATH=os.environ.get("PATH", os.defpath), LANG="C.UTF-8",
                   PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1",
                   OMP_NUM_THREADS="1", PYTHONPATH=str(self.root / "src") + os.pathsep +
                   os.environ.get("PYTHONPATH", ""))
        self.process = subprocess.Popen(
            [binary, "-p", self.profile, sys.executable, "-B", "-m",
             "nexus.seed.primitive_transfer_v2.actor", self.role], cwd=self.root, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0)
        self._buffer = b""

    def _rpc(self, command, payload):
        message = {"id": self.next_id, "command": command, "payload": payload}
        request(self.role, message)
        self.next_id += 1
        self.process.stdin.write(encode(message) + b"\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + self.timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self._buffer:
                left = deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    self.close()
                    raise TimeoutError("actor response timeout")
                chunk = os.read(self.process.stdout.fileno(), 4096)
                if not chunk:
                    raise RuntimeError("actor exited without response")
                self._buffer += chunk
                if len(self._buffer) > MAX_MESSAGE_BYTES + 1:
                    self.close()
                    raise ValueError("actor response byte limit")
        raw, self._buffer = self._buffer.split(b"\n", 1)
        result = response(self.role, decode(raw))
        if result["id"] != message["id"]:
            raise ValueError("response id mismatch")
        if not result["ok"]:
            raise ValueError("actor rejected request")
        return result["payload"]

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class LearnerProcess(_Process):
    role = "learner"

    def start(self, task, rule):
        if self.started:
            raise ValueError("one task per process; cannot reset budget")
        self.started = True
        return self._rpc("start", {"task": task, "rule": rule})

    def next_action(self, receipt):
        if not self.started:
            raise ValueError("start required")
        return self._rpc("next", {"receipt": receipt})


class EnvironmentProcess(_Process):
    role = "environment"

    def start(self, task):
        if self.started:
            raise ValueError("one task per process; cannot reset budget")
        self.started = True
        return self._rpc("start", task)

    def execute(self, action):
        if not self.started:
            raise ValueError("start required")
        return self._rpc("execute", action)


class PrivateEvaluatorProcess(_Process):
    role = "evaluator"

    def status(self):
        return self._rpc("status", {})

"""Fresh-process role dispatcher. No pickle, shared objects, or fork inheritance."""
from __future__ import annotations

import os
import resource
import sys

from .contracts import MAX_MESSAGE_BYTES, decode, encode, request, response


def main():
    role = sys.argv[1]
    # Hard per-process CPU and descriptor limits for boundary fixtures only.
    # These do not implement aggregate scientific resource accounting.
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if role == "learner":
        from .learner import Learner
        state = Learner()
    elif role == "evaluator":
        from .private_evaluator import PrivateEvaluator
        state = PrivateEvaluator()
    elif role == "environment":
        state = None
    else:
        raise ValueError("unknown role")
    started = False
    for _ in range(256):
        raw = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 2)
        if not raw:
            return
        if len(raw) > MAX_MESSAGE_BYTES + 1 or not raw.endswith(b"\n"):
            return
        message_id = 0
        try:
            message = decode(raw)
            request(role, message)
            message_id = message["id"]
            cmd, p = message["command"], message["payload"]
            if role in ("learner", "environment"):
                if cmd == "start":
                    if started:
                        raise ValueError("cannot reset actor")
                    started = True
                elif not started:
                    raise ValueError("start required")
            if role == "learner":
                if cmd == "start":
                    state.start(p["task"], p["rule"])
                    payload = state.next(None)
                else:
                    payload = state.next(p["receipt"])
            elif role == "environment":
                if cmd == "start":
                    from .environment import PublicEnvironment
                    state = PublicEnvironment(p)
                    payload = state.execute({"kind": "INSPECT", "payload": {}})
                else:
                    payload = state.execute(p)
            else:
                payload = state.status()
            out = {"id": message_id, "ok": True, "payload": payload}
            response(role, out)
        except Exception:
            out = {"id": message_id, "ok": False, "payload": {"error": "rejected"}}
        sys.stdout.buffer.write(encode(out) + b"\n")
        sys.stdout.buffer.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

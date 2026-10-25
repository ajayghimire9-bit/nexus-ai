"""Torch-free spawn worker for vetted helper replay.

The child must not import wave24_quotient_core or torch: those modules can
exhaust the helper CPU rlimit during spawn import.
"""
from __future__ import annotations

import marshal
import math
import sys
import types


def _freeze(value):
    if value is None:
        return ("none",)
    if type(value) in (bool, int, str):
        return (type(value).__name__, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite value")
        return ("float", value.hex())
    if type(value) in (tuple, list):
        return (type(value).__name__, tuple(_freeze(v) for v in value))
    if type(value) is dict:
        return ("dict", tuple(sorted(((_freeze(k), _freeze(v)) for k, v in value.items()), key=repr)))
    raise TypeError(f"unsupported semantic value: {type(value).__name__}")


def spawn_helper_child(payload, conn):
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        def deny(event, args):
            if event == "open" or event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.system", "os.fork", "ctypes.")):
                raise PermissionError("helper verification denies external side effects")
        sys.addaudithook(deny)
        ns = {"__builtins__": {}}
        for name, code in payload.get("globals", {}).items():
            ns[name] = types.FunctionType(marshal.loads(code), {"__builtins__": {}})
        fn = types.FunctionType(marshal.loads(payload["code"]), ns)
        conn.send(dict(ok=True, outputs=[_freeze(fn(x)) for x in payload["inputs"]]))
    except BaseException as exc:
        try:
            conn.send(dict(ok=False, error=type(exc).__name__+": "+str(exc)))
        except Exception:
            pass
    finally:
        conn.close()

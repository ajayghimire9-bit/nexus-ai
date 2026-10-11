from __future__ import annotations

import random
from typing import Any, Literal

import numpy as np
import torch

ResumeFidelity = Literal["classic_control_state", "approximate"]


def capture_library_rng() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        payload["torch_cuda"] = torch.cuda.get_rng_state_all()
    return payload


def restore_library_rng(payload: dict[str, Any]) -> None:
    if payload.get("python") is not None:
        random.setstate(payload["python"])
    if payload.get("numpy") is not None:
        np.random.set_state(payload["numpy"])
    if payload.get("torch") is not None:
        torch.set_rng_state(payload["torch"])
    if payload.get("torch_cuda") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(payload["torch_cuda"])


def _wrapper_chain(env: Any) -> list[Any]:
    chain = [env]
    cur = env
    for _ in range(16):
        inner = getattr(cur, "env", None)
        if inner is None or inner is cur:
            break
        chain.append(inner)
        cur = inner
    return chain


def capture_vector_env(envs: Any) -> dict[str, Any]:
    """Best-effort env snapshot. Classic control `state` is restored when present."""
    sub = list(getattr(envs, "envs", []))
    physics: list[dict[str, Any]] = []
    supported = True
    for env in sub:
        rec: dict[str, Any] = {"kind": "unsupported"}
        unwrapped = env.unwrapped if hasattr(env, "unwrapped") else env
        if hasattr(unwrapped, "state"):
            rec = {
                "kind": "state",
                "state": np.asarray(unwrapped.state, dtype=np.float64),
            }
            for w in _wrapper_chain(env):
                if hasattr(w, "_elapsed_steps"):
                    rec["elapsed_steps"] = int(w._elapsed_steps)
            if hasattr(unwrapped, "np_random"):
                try:
                    rec["np_random"] = unwrapped.np_random.bit_generator.state
                except Exception:  # noqa: BLE001
                    pass
        else:
            supported = False
        physics.append(rec)
        if rec["kind"] != "state":
            supported = False
    fidelity: ResumeFidelity = "classic_control_state" if supported and sub else "approximate"
    return {
        "fidelity": fidelity,
        "physics": physics,
        "autoreset_envs": np.asarray(getattr(envs, "_autoreset_envs", np.zeros(len(sub), dtype=bool))),
        "note": (
            "classic_control_state restores CartPole-like `.state` and TimeLimit elapsed steps. "
            "Other Gymnasium internals are not a public snapshot API; those resumes are approximate."
        ),
    }


def restore_vector_env(envs: Any, snapshot: dict[str, Any]) -> str:
    fidelity = str(snapshot.get("fidelity") or "approximate")
    physics = list(snapshot.get("physics") or [])
    sub = list(getattr(envs, "envs", []))
    if len(physics) != len(sub):
        return "approximate"
    ok = fidelity == "classic_control_state"
    for env, rec in zip(sub, physics, strict=True):
        if rec.get("kind") != "state":
            ok = False
            continue
        unwrapped = env.unwrapped if hasattr(env, "unwrapped") else env
        if not hasattr(unwrapped, "state"):
            ok = False
            continue
        unwrapped.state = np.asarray(rec["state"], dtype=np.float64)
        if rec.get("elapsed_steps") is not None:
            for w in _wrapper_chain(env):
                if hasattr(w, "_elapsed_steps"):
                    w._elapsed_steps = int(rec["elapsed_steps"])
        if rec.get("np_random") is not None and hasattr(unwrapped, "np_random"):
            try:
                unwrapped.np_random.bit_generator.state = rec["np_random"]
            except Exception:  # noqa: BLE001
                ok = False
    if snapshot.get("autoreset_envs") is not None and hasattr(envs, "_autoreset_envs"):
        envs._autoreset_envs = np.asarray(snapshot["autoreset_envs"], dtype=bool)
    return "classic_control_state" if ok else "approximate"

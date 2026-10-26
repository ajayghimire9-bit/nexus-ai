"""Sealed vault loader (Wave 26 Phase 3; AGENTS.md RULE 1).

The vault lives OUTSIDE the repository ($NEXUS_SEALED_VAULT_DIR). The repository holds only its SHA-256
manifest (`vault/vault_manifest.sha256`, lines "<sha256> <relative path>"). Nothing here reads, greps or
imports a vault file unless:
  1. the locked-harness token NEXUS_SEALED_HARNESS_TOKEN is set (only the single-shot sealed runner sets it),
  2. the vault's own manifest is byte-identical to the committed manifest, and
  3. every file listed in the manifest hashes to its committed value (and no listed file is missing).
Then the vault's public entry point load_sealed_split(split_name, seed) is called. The entry module is found
by importing manifest-listed .py files (inside the harness only) until one exposes that function, so the
tuning agent never needs to know vault file names. Every access attempt, allowed or refused, is appended to
an audit log. Splits and seeds are bound by the seed registry.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import namedtuple
from pathlib import Path

from nexus.seed_registry import SeedHygieneError, owner_of
from nexus.standing_gates import HARNESS_ENV, VAULT_ENV

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_MANIFEST = ROOT / "vault" / "vault_manifest.sha256"
AUDIT_LOG = Path(os.environ.get("NEXUS_VAULT_ACCESS_LOG", ROOT / "runs" / "experimental" / "sealed_vault_access.jsonl"))
SPLITS = {"group_a": ("phase3", "vault_group_a"), "group_b": ("phase3", "vault_group_b"),
          "external_arc_1d_grid": ("phase3", "vault_external")}
SealedTask = namedtuple("SealedTask", "train_examples query_inputs oracle_fn hidden_ground_truth_metadata")


N_PHYSICAL = 5          # owner (2026-10-26): manifest lines 1-5 are files on disk; the rest are in-memory digests


class SealedVaultError(RuntimeError):
    pass


def _audit(event, **kw):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(dict(t=time.time(), event=event, **kw)) + "\n")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_manifest(text):
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        h, rel = line.split(None, 1)
        out.append((h.strip(), rel.strip().lstrip("*")))
    return out


def verify_vault(vault_dir=None, *, committed=COMMITTED_MANIFEST):
    """Token-gated integrity check. Returns the manifest entries; raises on any mismatch."""
    if not os.environ.get(HARNESS_ENV):
        _audit("refused", reason="no harness token")
        raise SealedVaultError("sealed vault access requires the locked harness token")
    vault = Path(vault_dir or os.environ.get(VAULT_ENV, ""))
    if not vault.is_dir():
        _audit("refused", reason="vault dir missing")
        raise SealedVaultError(f"vault directory not found: {vault}")
    committed_text = Path(committed).read_text()
    vm = vault / "vault_manifest.sha256"
    if not vm.exists() or vm.read_text() != committed_text:
        _audit("refused", reason="manifest differs from committed manifest")
        raise SealedVaultError("vault manifest differs from the committed manifest")
    entries = parse_manifest(committed_text)
    physical, virtual = entries[:N_PHYSICAL], entries[N_PHYSICAL:]
    for i, (h, rel) in enumerate(physical):
        p = vault / rel
        if not p.is_file() or _sha(p) != h:
            _audit("refused", reason="physical file hash mismatch", file_index=i)
            raise SealedVaultError("vault file hash mismatch (index %d)" % i)
    _audit("physical_verified", files=len(physical), manifest_sha256=_sha(committed))
    # The remaining entries are in-memory digests of split bundles / task objects (owner, 2026-10-26). They are
    # checked by the vault's own verify_vault_manifest(), whose module was hash-verified just above.
    mods = _modules(vault, physical)
    fn = next((getattr(m, "verify_vault_manifest") for m in mods if callable(getattr(m, "verify_vault_manifest", None))),
              None)
    if fn is None:
        _audit("refused", reason="no verify_vault_manifest in verified modules")
        raise SealedVaultError("vault exposes no verify_vault_manifest")
    form, ok = None, False
    for form, call in (("no_args", lambda: fn()), ("virtual_entries", lambda: fn(virtual)),
                       ("manifest_path", lambda: fn(str(vm)))):
        try:
            ok = bool(call())
            break
        except TypeError:
            continue
        except Exception as exc:                      # type only (RULE 1)
            _audit("refused", reason="virtual verification raised", error=type(exc).__name__, call_form=form)
            raise SealedVaultError("virtual manifest verification raised") from None
    if not ok:
        _audit("refused", reason="virtual verification failed", call_form=form)
        raise SealedVaultError("virtual manifest verification failed")
    _audit("verified", files=len(physical), virtual=len(virtual), call_form=form)
    return entries


_MODS = {}


def _modules(vault, physical):
    """Import the hash-verified physical .py files (harness only); cached per vault."""
    key = str(vault)
    if key in _MODS:
        return _MODS[key]
    sys.path.insert(0, str(vault))
    mods = []
    try:
        for i, (_, rel) in enumerate(physical):
            if not rel.endswith(".py"):
                continue
            spec = importlib.util.spec_from_file_location(f"_sealed_vault_mod_{i}", vault / rel)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            mods.append(mod)
    finally:
        sys.path.remove(str(vault))
    _MODS[key] = mods
    return mods


def _entry_point(vault, entries):
    for mod in _modules(vault, entries[:N_PHYSICAL]):
        if callable(getattr(mod, "load_sealed_split", None)):
            return mod.load_sealed_split
    raise SealedVaultError("no verified module exposes load_sealed_split")


def load_split(split_name, seed, *, vault_dir=None, committed=COMMITTED_MANIFEST):
    """Single-shot harness access: verify, then call the vault's load_sealed_split(split_name, seed)."""
    if split_name not in SPLITS:
        raise SealedVaultError(f"unknown split {split_name}")
    if owner_of(seed) != SPLITS[split_name]:
        raise SeedHygieneError(f"seed {seed} does not belong to split {split_name} ({owner_of(seed)})")
    entries = verify_vault(vault_dir, committed=committed)
    vault = Path(vault_dir or os.environ[VAULT_ENV])
    fn = _entry_point(vault, entries)
    raw = fn(split_name, seed)
    tasks = [t if isinstance(t, SealedTask) else SealedTask(*t) for t in raw]
    _audit("loaded", split=split_name, seed=seed, tasks=len(tasks))
    return tasks

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
    for h, rel in entries:
        p = vault / rel
        if not p.exists() or _sha(p) != h:
            _audit("refused", reason="file hash mismatch", file_index=entries.index((h, rel)))
            raise SealedVaultError("vault file hash mismatch (index %d)" % entries.index((h, rel)))
    _audit("verified", files=len(entries), manifest_sha256=_sha(committed))
    return entries


def _entry_point(vault, entries):
    sys.path.insert(0, str(vault))
    try:
        for i, (_, rel) in enumerate(entries):
            if not rel.endswith(".py"):
                continue
            spec = importlib.util.spec_from_file_location(f"_sealed_vault_mod_{i}", vault / rel)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if callable(getattr(mod, "load_sealed_split", None)):
                return mod.load_sealed_split
    finally:
        sys.path.remove(str(vault))
    raise SealedVaultError("no manifest-listed module exposes load_sealed_split")


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

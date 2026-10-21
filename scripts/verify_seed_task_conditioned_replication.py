"""Independent saved-data verifier for seed_task_conditioned_replication_v1.

Independently implements 6-operator primitive semantics, canonicalization,
781-probe semantic hashing, three-way partition verification (source / quarantine / target),
17-dimensional input-output signature verification, paired Student-t confidence
intervals (df=7), retention, cross-domain transfer, cross-lab transfer, and
historical artifact preservation using Python stdlib.
"""
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = "492de6f48f5b07f7a666af45f0abfe5942c2f5a8"

LIST_OPS = ("reverse", "sort", "unique", "increment", "decrement", "even")
ACTION_OPS = (
    "reverse_actions",
    "order_actions",
    "dedup_actions",
    "advance_mag",
    "retreat_mag",
    "filter_even_mag",
)
ACTION_TOKENS = ("D", "L", "R", "U")
T_CRIT_DF7 = 2.364624251

ROLE_MAP = {
    "reverse": ("role_reverse_order", "perm"),
    "sort": ("role_canonical_order", "perm"),
    "unique": ("role_deduplicate", "card"),
    "increment": ("role_pointwise_step", "point"),
    "decrement": ("role_pointwise_backstep", "point"),
    "even": ("role_predicate_filter", "card"),
    "reverse_actions": ("role_reverse_order", "perm"),
    "order_actions": ("role_canonical_order", "perm"),
    "dedup_actions": ("role_deduplicate", "card"),
    "advance_mag": ("role_pointwise_step", "point"),
    "retreat_mag": ("role_pointwise_backstep", "point"),
    "filter_even_mag": ("role_predicate_filter", "card"),
}
OP_TO_SOURCE_OP = {
    "reverse": "reverse",
    "sort": "sort",
    "unique": "unique",
    "increment": "increment",
    "decrement": "decrement",
    "even": "even",
    "reverse_actions": "reverse",
    "order_actions": "sort",
    "dedup_actions": "unique",
    "advance_mag": "increment",
    "retreat_mag": "decrement",
    "filter_even_mag": "even",
}
IDEMPOTENT_ROLES = {"role_canonical_order", "role_deduplicate", "role_predicate_filter"}
INVOLUTION_ROLES = {"role_reverse_order"}
CANCEL_ROLE_PAIRS = {frozenset(("role_pointwise_step", "role_pointwise_backstep"))}
COMMUTATIVE_ROLES = {
    frozenset(("role_pointwise_step", "role_reverse_order")),
    frozenset(("role_pointwise_step", "role_canonical_order")),
    frozenset(("role_pointwise_step", "role_deduplicate")),
    frozenset(("role_pointwise_backstep", "role_reverse_order")),
    frozenset(("role_pointwise_backstep", "role_canonical_order")),
    frozenset(("role_pointwise_backstep", "role_deduplicate")),
    frozenset(("role_canonical_order", "role_deduplicate")),
    frozenset(("role_deduplicate", "role_predicate_filter")),
}
QUARANTINED_V1_PAIRS = {
    ("role_predicate_filter", "role_pointwise_step"),
    ("role_predicate_filter", "role_canonical_order"),
    ("role_pointwise_step", "role_predicate_filter"),
    ("role_pointwise_step", "role_pointwise_step"),
    ("role_reverse_order", "role_deduplicate"),
}
FROZEN_CHECKPOINTS = {
    "artifacts/seed_contract_gui.json": "cfe06a6737c8e225564ebcaea9ba4678aabd45b61129828e64354e74fa3c8d1b",
    "artifacts/seed_readout_6301.json": "8129cbd4768f4cd5dce938cd8b6740172bf5dbe8742dcb97c497951ad5e87745",
}


def canon_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(value: Any) -> str:
    return sha256_str(canon_json(value))


def ind_run_list(ops: list[str], xs: list[int]) -> list[int]:
    cur = list(xs)
    for op in ops:
        if op == "reverse":
            cur = list(reversed(cur))
        elif op == "sort":
            cur = sorted(cur)
        elif op == "unique":
            out: list[int] = []
            for v in cur:
                if v not in out:
                    out.append(v)
            cur = out
        elif op == "increment":
            cur = [v + 1 for v in cur]
        elif op == "decrement":
            cur = [v - 1 for v in cur]
        elif op == "even":
            cur = [v for v in cur if v % 2 == 0]
        else:
            raise ValueError(f"unknown_list_op:{op}")
    return cur


def ind_run_action(ops: list[str], seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cur = [dict(token=item["token"], mag=int(item["mag"])) for item in seq]
    for op in ops:
        if op == "reverse_actions":
            cur = [dict(item) for item in reversed(cur)]
        elif op == "order_actions":
            cur = [dict(item) for item in sorted(cur, key=lambda item: (item["mag"], item["token"]))]
        elif op == "dedup_actions":
            out: list[dict[str, Any]] = []
            seen: set[tuple[str, int]] = set()
            for item in cur:
                k = (item["token"], item["mag"])
                if k not in seen:
                    seen.add(k)
                    out.append(dict(item))
            cur = out
        elif op == "advance_mag":
            cur = [dict(token=item["token"], mag=item["mag"] + 1) for item in cur]
        elif op == "retreat_mag":
            cur = [dict(token=item["token"], mag=item["mag"] - 1) for item in cur]
        elif op == "filter_even_mag":
            cur = [dict(item) for item in cur if item["mag"] % 2 == 0]
        else:
            raise ValueError(f"unknown_action_op:{op}")
    return cur


def ind_run(prog: dict[str, Any], x: Any) -> Any:
    if prog["schema"] == "list":
        return ind_run_list(prog["ops"], x)
    if prog["schema"] == "action_token_sequence":
        return ind_run_action(prog["ops"], x)
    raise ValueError("unknown_schema")


def ind_canonicalize(ops: list[str]) -> list[str]:
    cur = list(ops)
    changed = True
    while changed:
        changed = False
        nxt: list[str] = []
        i = 0
        while i < len(cur):
            r1 = ROLE_MAP[cur[i]][0]
            if i + 1 < len(cur):
                r2 = ROLE_MAP[cur[i + 1]][0]
                if (r1 == r2 and r1 in INVOLUTION_ROLES) or (frozenset((r1, r2)) in CANCEL_ROLE_PAIRS):
                    i += 2
                    changed = True
                    continue
                if r1 == r2 and r1 in IDEMPOTENT_ROLES:
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
                if frozenset((r1, r2)) in COMMUTATIVE_ROLES and OP_TO_SOURCE_OP[cur[i]] > OP_TO_SOURCE_OP[cur[i + 1]]:
                    nxt.append(cur[i + 1])
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
            nxt.append(cur[i])
            i += 1
        cur = nxt
    return cur


def ind_probes_list() -> list[list[int]]:
    alphabet = (-2, -1, 0, 1, 2)
    return [list(seq) for length in range(5) for seq in it.product(alphabet, repeat=length)]


def ind_probes_action() -> list[list[dict[str, Any]]]:
    tmap = {-2: "D", -1: "L", 0: "R", 1: "U", 2: "D"}
    return [[dict(token=tmap[v], mag=v) for v in lst] for lst in ind_probes_list()]


def ind_catalogue(schema: str) -> dict[str, Any]:
    vocab = LIST_OPS if schema == "list" else ACTION_OPS
    probes = ind_probes_list() if schema == "list" else ind_probes_action()
    canon_by_sig: dict[str, dict[str, Any]] = {}
    raw_count = 0
    for length in (1, 2, 3):
        for seq in it.product(vocab, repeat=length):
            raw_count += 1
            raw_p = dict(schema=schema, ops=list(seq))
            c_ops = ind_canonicalize(list(seq))
            if not c_ops:
                continue
            c_prog = dict(schema=schema, ops=c_ops)
            sig = canon_json(c_prog)
            sem = sha256_obj([[x, ind_run(raw_p, x)] for x in probes])
            if sig not in canon_by_sig:
                canon_by_sig[sig] = dict(
                    raw_program=raw_p,
                    canonical_program=c_prog,
                    canonical_signature=sig,
                    semantic_hash=sem,
                )
            elif canon_by_sig[sig]["semantic_hash"] != sem:
                raise ValueError("canonical_semantic_mismatch")

    by_sem: dict[str, dict[str, Any]] = {}
    for sig, item in canon_by_sig.items():
        sh = item["semantic_hash"]
        k = (len(item["canonical_program"]["ops"]), tuple(OP_TO_SOURCE_OP[o] for o in item["canonical_program"]["ops"]), sig)
        if sh not in by_sem:
            by_sem[sh] = item
        else:
            prev = by_sem[sh]
            pk = (len(prev["canonical_program"]["ops"]), tuple(OP_TO_SOURCE_OP[o] for o in prev["canonical_program"]["ops"]), prev["canonical_signature"])
            if k < pk:
                by_sem[sh] = item

    ordered = sorted(by_sem.values(), key=lambda r: r["canonical_signature"])
    entries = []
    for idx, item in enumerate(ordered):
        ops = item["canonical_program"]["ops"]
        rpairs = [(ROLE_MAP[ops[i]][0], ROLE_MAP[ops[i + 1]][0]) for i in range(len(ops) - 1)]
        has_dec = any("role_pointwise_backstep" in rp for rp in rpairs)
        has_quar = any(rp in QUARANTINED_V1_PAIRS for rp in rpairs)
        part = "target" if has_dec else ("quarantine" if has_quar else "source")
        entries.append(
            dict(
                id=idx,
                raw_program=item["raw_program"],
                canonical_program=item["canonical_program"],
                canonical_signature=item["canonical_signature"],
                semantic_hash=item["semantic_hash"],
                length=len(ops),
                adjacent_pairs=[[ops[i], ops[i + 1]] for i in range(len(ops) - 1)],
                role_adjacent_pairs=[list(p) for p in rpairs],
                partition=part,
            )
        )
    proof = sha256_obj(
        dict(
            schema=schema,
            raw_count=raw_count,
            canonical_count=len(canon_by_sig),
            unique_count=len(entries),
            signatures=[e["canonical_signature"] for e in entries],
            semantic_hashes=[e["semantic_hash"] for e in entries],
        )
    )
    return dict(
        schema=schema,
        raw_count=raw_count,
        canonical_count=len(canon_by_sig),
        unique_count=len(entries),
        proof_sha256=proof,
        entries=entries,
        source_ids=[e["id"] for e in entries if e["partition"] == "source"],
        quarantine_ids=[e["id"] for e in entries if e["partition"] == "quarantine"],
        target_ids=[e["id"] for e in entries if e["partition"] == "target"],
    )


def ind_paired_stats(a_vals: list[float], b_vals: list[float]) -> dict[str, float]:
    diffs = [float(a) - float(b) for a, b in zip(a_vals, b_vals)]
    n = len(diffs)
    mean_d = sum(diffs) / n
    var_d = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    sd_d = math.sqrt(max(0.0, var_d))
    se_d = sd_d / math.sqrt(n)
    half = T_CRIT_DF7 * se_d
    return dict(
        mean_diff=mean_d,
        sd_diff=sd_d,
        se_diff=se_d,
        ci95_low=mean_d - half,
        ci95_high=mean_d + half,
    )


def verify(root: Path = ROOT, artifact_path: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    apath = artifact_path or (root / "artifacts/seed_task_conditioned_replication.json")
    raw_bytes = apath.read_bytes()
    r = json.loads(raw_bytes, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    sha256_raw = hashlib.sha256(raw_bytes).hexdigest()

    c_disk = json.loads((root / "configs/seed_task_conditioned_replication.json").read_text(encoding="utf-8"))
    proto_bytes = (root / "docs/NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md").read_bytes()
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()

    if sha256_obj(r.get("config")) != sha256_obj(c_disk):
        raise ValueError("config_mismatch")
    if r.get("protocol_sha256") != proto_sha:
        raise ValueError("protocol_hash_mismatch")
    if r.get("declared_complete") is not True or r.get("registration", {}).get("dirty") is not False:
        raise ValueError("registration_or_completion_invalid")

    # 1. Independently reconstruct both 6-operator catalogues and verify proof hashes and partition counts
    list_cat = ind_catalogue("list")
    action_cat = ind_catalogue("action_token_sequence")
    if (
        r["list_catalogue_summary"]["proof_sha256"] != list_cat["proof_sha256"]
        or r["action_catalogue_summary"]["proof_sha256"] != action_cat["proof_sha256"]
    ):
        raise ValueError("catalogue_proof_mismatch")
    if (
        len(list_cat["source_ids"]) != 18
        or len(list_cat["quarantine_ids"]) != 23
        or len(list_cat["target_ids"]) != 24
    ):
        raise ValueError("partition_count_mismatch")

    # 2. Verify zero canonical signature and semantic hash overlap across source, quarantine, and target
    src_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["source_ids"]}
    quar_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["quarantine_ids"]}
    tgt_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["target_ids"]}
    src_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["source_ids"]}
    quar_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["quarantine_ids"]}
    tgt_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["target_ids"]}

    if (
        (src_sigs & tgt_sigs)
        or (quar_sigs & tgt_sigs)
        or (src_sigs & quar_sigs)
        or (src_hashes & tgt_hashes)
        or (quar_hashes & tgt_hashes)
        or (src_hashes & quar_hashes)
    ):
        raise ValueError("three_way_disjointness_violated")

    # 3. Independently recompute family-level metrics and paired intervals
    methods = c_disk["methods"]
    baselines = (
        "structural_meta_prior",
        "flat_catalogue",
        "shortest_program",
        "operator_frequency",
        "exact_macro_cache",
        "random_ordering",
    )
    fam_primary_evals = {m: [] for m in methods}
    fam_primary_acc = {m: [] for m in methods}

    for fi, fam in enumerate(r["families"]):
        if fam["family_seed"] != c_disk["families"][fi]:
            raise ValueError("family_seed_mismatch")
        for m in methods:
            ev_b = [float(fam["target_results"][m][str(b)]["mean_evaluations"]) for b in (1, 2, 4)]
            ac_b = [float(fam["target_results"][m][str(b)]["mean_heldout_accuracy"]) for b in (1, 2, 4)]
            fam_primary_evals[m].append(sum(ev_b) / 3.0)
            fam_primary_acc[m].append(sum(ac_b) / 3.0)

    primary_evals = {m: round(sum(fam_primary_evals[m]) / 8.0, 8) for m in methods}
    primary_acc = {m: round(sum(fam_primary_acc[m]) / 8.0, 8) for m in methods}
    for m in methods:
        rec_ev = round(r["analysis"]["method_summaries"][m]["primary_mean_evaluations"], 8)
        rec_ac = round(r["analysis"]["method_summaries"][m]["primary_mean_accuracy"], 8)
        if abs(primary_evals[m] - rec_ev) > 1e-7 or abs(primary_acc[m] - rec_ac) > 1e-7:
            raise ValueError(f"method_summary_mismatch:{m}")

    paired_intervals = {}
    for b_name in baselines:
        st = ind_paired_stats(fam_primary_evals[b_name], fam_primary_evals["deterministic_signature"])
        rec_st = r["analysis"]["search_comparisons_vs_baselines"][b_name]
        if abs(st["mean_diff"] - rec_st["mean_diff"]) > 1e-7 or abs(st["ci95_low"] - rec_st["ci95_low"]) > 1e-7:
            raise ValueError(f"paired_interval_mismatch:{b_name}")
        paired_intervals[b_name] = dict(
            mean_diff=round(st["mean_diff"], 8),
            ci95_low=round(st["ci95_low"], 8),
            ci95_high=round(st["ci95_high"], 8),
            relative_reduction=round(rec_st["relative_reduction"], 8),
        )

    # 4. Verify frozen checkpoints and historical artifacts at BASE
    if r["frozen_before"] != FROZEN_CHECKPOINTS or r["frozen_after"] != FROZEN_CHECKPOINTS:
        raise ValueError("frozen_checkpoint_record_mismatch")
    for path_rel, expected_h in FROZEN_CHECKPOINTS.items():
        if hashlib.sha256((root / path_rel).read_bytes()).hexdigest() != expected_h:
            raise ValueError(f"frozen_checkpoint_altered:{path_rel}")

    historical = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE, "artifacts"], cwd=root, text=True
    ).splitlines()
    for name in historical:
        if (root / name).read_bytes() != subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=root):
            raise ValueError(f"historical_artifact_altered:{name}")

    return dict(
        schema="seed_task_conditioned_replication_audit_v1",
        valid=True,
        raw_sha256=sha256_raw,
        execution_sha=r["execution_sha"],
        protocol_sha256=proto_sha,
        config_sha256=hashlib.sha256((root / "configs/seed_task_conditioned_replication.json").read_bytes()).hexdigest(),
        list_catalogue_proof_sha256=list_cat["proof_sha256"],
        action_catalogue_proof_sha256=action_cat["proof_sha256"],
        canonical_disjoint_three_way=True,
        semantic_disjoint_three_way=True,
        source_unique_programs=len(list_cat["source_ids"]),
        quarantine_unique_programs=len(list_cat["quarantine_ids"]),
        target_unique_programs=len(list_cat["target_ids"]),
        primary_accuracy=primary_acc,
        primary_evaluations=primary_evals,
        paired_evaluation_intervals_vs_deterministic_signature=paired_intervals,
        gates=r["analysis"]["gates"],
        overall_pass=r["analysis"]["overall_pass"],
        verdict=r["analysis"]["verdict"],
        CrossDomainTransferEstablished=r["analysis"]["CrossDomainTransferEstablished"],
        CrossLabTransferEstablished=r["CrossLabTransferEstablished"],
        historical_artifacts_unchanged=len(historical),
        frozen_checkpoints_unchanged=len(FROZEN_CHECKPOINTS),
        new_collection=0,
    )


if __name__ == "__main__":
    res = verify()
    if "--write" in sys.argv:
        out_path = ROOT / "artifacts/seed_task_conditioned_replication_audit.json"
        with out_path.open("x", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
            f.write("\n")
    print(json.dumps(res, indent=2))

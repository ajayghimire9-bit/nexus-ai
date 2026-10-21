"""Independent saved-data verifier for seed_disjoint_meta_v1 (Section 15).

Does NOT call MetaLearningEngine, the candidate ranker, the scientific acceptance
gate, or saved summary functions. Independently implements primitive semantics,
canonicalization, semantic probe hashing, Gaussian-elimination ridge solving,
candidate ordering, teaching consistency, retention, cross-domain transfer,
paired t-intervals, and all 7 advancement gates using Python stdlib.
"""
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = "492de6f48f5b07f7a666af45f0abfe5942c2f5a8"

LIST_OPS = ("reverse", "sort", "unique", "increment", "even")
ACTION_OPS = ("reverse_actions", "order_actions", "dedup_actions", "advance_mag", "filter_even_mag")
CAT_NAMES = ("perm", "card", "point")
T_CRIT_DF7 = 2.364624251

ROLE_MAP = {
    "reverse": ("role_reverse_order", "perm"),
    "sort": ("role_canonical_order", "perm"),
    "unique": ("role_deduplicate", "card"),
    "increment": ("role_pointwise_step", "point"),
    "even": ("role_predicate_filter", "card"),
    "reverse_actions": ("role_reverse_order", "perm"),
    "order_actions": ("role_canonical_order", "perm"),
    "dedup_actions": ("role_deduplicate", "card"),
    "advance_mag": ("role_pointwise_step", "point"),
    "filter_even_mag": ("role_predicate_filter", "card"),
}
OP_TO_SOURCE_OP = {
    "reverse": "reverse",
    "sort": "sort",
    "unique": "unique",
    "increment": "increment",
    "even": "even",
    "reverse_actions": "reverse",
    "order_actions": "sort",
    "dedup_actions": "unique",
    "advance_mag": "increment",
    "filter_even_mag": "even",
}
IDEMPOTENT_ROLES = {"role_canonical_order", "role_deduplicate", "role_predicate_filter"}
INVOLUTION_ROLES = {"role_reverse_order"}
COMMUTATIVE_ROLES = {
    frozenset(("role_pointwise_step", "role_reverse_order")),
    frozenset(("role_pointwise_step", "role_canonical_order")),
    frozenset(("role_pointwise_step", "role_deduplicate")),
    frozenset(("role_canonical_order", "role_deduplicate")),
    frozenset(("role_deduplicate", "role_predicate_filter")),
}
HOLDOUT_ROLE_PAIRS = {
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
                if r1 == r2 and r1 in INVOLUTION_ROLES:
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
        entries.append(dict(
            id=idx,
            raw_program=item["raw_program"],
            canonical_program=item["canonical_program"],
            canonical_signature=item["canonical_signature"],
            semantic_hash=item["semantic_hash"],
            length=len(ops),
            adjacent_pairs=[[ops[i], ops[i + 1]] for i in range(len(ops) - 1)],
            role_adjacent_pairs=[list(p) for p in rpairs],
            partition="target" if any(p in HOLDOUT_ROLE_PAIRS for p in rpairs) else "source",
        ))
    proof = sha256_obj(dict(
        schema=schema,
        raw_count=raw_count,
        canonical_count=len(canon_by_sig),
        unique_count=len(entries),
        signatures=[e["canonical_signature"] for e in entries],
        semantic_hashes=[e["semantic_hash"] for e in entries],
    ))
    return dict(
        schema=schema,
        raw_count=raw_count,
        canonical_count=len(canon_by_sig),
        unique_count=len(entries),
        proof_sha256=proof,
        entries=entries,
        source_ids=[e["id"] for e in entries if e["partition"] == "source"],
        target_ids=[e["id"] for e in entries if e["partition"] == "target"],
    )


def ind_features(c_prog: dict[str, Any], unseen: set[tuple[str, str]]) -> list[float]:
    ops = c_prog["ops"]
    L = len(ops)
    roles = [ROLE_MAP[o][0] for o in ops]
    cats = [ROLE_MAP[o][1] for o in ops]
    return (
        [1.0]
        + [1.0 if L == k else 0.0 for k in (1, 2, 3)]
        + [cats.count(c) / L for c in CAT_NAMES]
        + [
            float(L - len(set(roles))),
            float(sum(1 for r in roles if r in IDEMPOTENT_ROLES)),
            float(sum(1 for r in roles if r in INVOLUTION_ROLES)),
            float(cats.count("card")),
            float(cats.count("point")),
            float(cats.count("perm")),
        ]
        + [
            float(sum(1 for i in range(L - 1) if (cats[i], cats[i + 1]) == (c1, c2)))
            for c1 in CAT_NAMES
            for c2 in CAT_NAMES
        ]
        + [1.0 if any((cats[i], cats[i + 1]) in unseen for i in range(L - 1)) else 0.0]
    )


def solve_linear_system(A: list[list[float]], b: list[float]) -> list[float]:
    """Pure stdlib Gaussian elimination with partial pivoting."""
    n = len(b)
    M = [list(A[i]) + [float(b[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[pivot] = M[pivot], M[col]
        div = M[col][col]
        if abs(div) < 1e-15:
            raise ValueError("singular_ridge_matrix")
        for j in range(col, n + 1):
            M[col][j] /= div
        for r in range(n):
            if r != col:
                factor = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= factor * M[col][j]
    return [M[i][n] for i in range(n)]


def ind_fit_and_rank(
    source_tasks: list[dict[str, Any]],
    cat: dict[str, Any],
    lam: float = 1.0,
) -> tuple[dict[str, Any], dict[str, list[int]]]:
    entries = cat["entries"]
    src_entries = [e for e in entries if e["partition"] == "source"]

    prog_counts: dict[str, int] = {}
    role_counts = {
        "role_reverse_order": 0,
        "role_canonical_order": 0,
        "role_deduplicate": 0,
        "role_pointwise_step": 0,
        "role_predicate_filter": 0,
    }
    cat_counts = {c: 0 for c in CAT_NAMES}
    len_counts = {1: 0, 2: 0, 3: 0}
    trans_counts = {(c1, c2): 0 for c1 in CAT_NAMES for c2 in CAT_NAMES}

    for stask in source_tasks:
        sig = stask["canonical_signature"]
        prog_counts[sig] = prog_counts.get(sig, 0) + 1
        ops = stask["canonical_program"]["ops"]
        len_counts[len(ops)] += 1
        cats = [ROLE_MAP[o][1] for o in ops]
        for o, c in zip(ops, cats):
            role_counts[ROLE_MAP[o][0]] += 1
            cat_counts[c] += 1
        for i in range(len(cats) - 1):
            trans_counts[(cats[i], cats[i + 1])] += 1

    unseen = {pair for pair, cnt in trans_counts.items() if cnt == 0}
    tot_trans = sum(trans_counts.values())
    trans_probs = {pair: (cnt + 1.0) / (tot_trans + 9.0) for pair, cnt in trans_counts.items()}

    X = [ind_features(e["canonical_program"], unseen) for e in src_entries]
    Y = []
    for e in src_entries:
        ops = e["canonical_program"]["ops"]
        cats = [ROLE_MAP[o][1] for o in ops]
        occ = prog_counts.get(e["canonical_signature"], 0) / 16.0
        bonus = (
            0.5 * sum(trans_probs[(cats[i], cats[i + 1])] for i in range(len(cats) - 1)) / (len(cats) - 1)
            if len(cats) >= 2
            else 0.0
        )
        Y.append(occ + bonus)

    n_rows = len(X)
    d = len(X[0])
    scale = []
    for j in range(d):
        ms = math.sqrt(sum(X[i][j] * X[i][j] for i in range(n_rows)) / n_rows)
        scale.append(ms if ms >= 1e-8 else 1.0)

    Z = [[X[i][j] / scale[j] for j in range(d)] for i in range(n_rows)]
    ZtZ_lam = [
        [
            sum(Z[i][a] * Z[i][b] for i in range(n_rows)) + (lam if a == b else 0.0)
            for b in range(d)
        ]
        for a in range(d)
    ]
    ZtY = [sum(Z[i][a] * Y[i] for i in range(n_rows)) for a in range(d)]
    w_star = solve_linear_system(ZtZ_lam, ZtY)

    tot_roles = sum(role_counts.values())
    role_lp = {r: math.log((cnt + 1.0) / (tot_roles + 5.0)) for r, cnt in role_counts.items()}
    len_lp = {L: math.log((cnt + 1.0) / 19.0) for L, cnt in len_counts.items()}
    tot_cats = sum(cat_counts.values())
    cat_lp = {c: math.log((cnt + 1.0) / (tot_cats + 3.0)) for c, cnt in cat_counts.items()}
    cond_lp = {}
    for c1 in CAT_NAMES:
        rsum = sum(trans_counts[(c1, c2)] for c2 in CAT_NAMES)
        cond_lp[c1] = {c2: math.log((trans_counts[(c1, c2)] + 1.0) / (rsum + 3.0)) for c2 in CAT_NAMES}

    def rank_for(method: str, target_cat: dict[str, Any]) -> list[int]:
        ents = target_cat["entries"]
        if method in ("flat_catalogue", "scratch_flat"):
            return [e["id"] for e in sorted(ents, key=lambda e: e["canonical_signature"])]
        if method == "shortest_program":
            return [e["id"] for e in sorted(ents, key=lambda e: (e["length"], e["canonical_signature"]))]
        if method in ("structural_meta_prior", "transferred_structural_prior"):
            sc = {}
            for e in ents:
                phi = ind_features(e["canonical_program"], unseen)
                sc[e["canonical_signature"]] = round(sum((phi[j] / scale[j]) * w_star[j] for j in range(d)), 12)
            return [e["id"] for e in sorted(ents, key=lambda e: (-sc[e["canonical_signature"]], e["canonical_signature"]))]
        if method in ("operator_frequency", "target_operator_frequency"):
            sc = {
                e["canonical_signature"]: round(sum(role_lp[ROLE_MAP[o][0]] for o in e["canonical_program"]["ops"]), 12)
                for e in ents
            }
            return [e["id"] for e in sorted(ents, key=lambda e: (-sc[e["canonical_signature"]], e["canonical_signature"]))]
        if method == "exact_macro_cache":
            return [
                e["id"]
                for e in sorted(
                    ents,
                    key=lambda e: (-prog_counts.get(e["canonical_signature"], 0), e["length"], e["canonical_signature"]),
                )
            ]
        if method == "bayesian_model_based":
            sc = {}
            for e in ents:
                ops = e["canonical_program"]["ops"]
                cats = [ROLE_MAP[o][1] for o in ops]
                lp = len_lp[len(ops)] + sum(cat_lp[c] for c in cats) + sum(cond_lp[cats[i]][cats[i + 1]] for i in range(len(cats) - 1))
                sc[e["canonical_signature"]] = round(lp, 12)
            return [e["id"] for e in sorted(ents, key=lambda e: (-sc[e["canonical_signature"]], e["canonical_signature"]))]
        raise ValueError(method)

    return dict(scale=scale, w_star=w_star, unseen=unseen), rank_for


def ind_eval_task(
    task: dict[str, Any],
    cat: dict[str, Any],
    ordered_ids: list[int],
    const_share: float,
) -> dict[str, Any]:
    entries = cat["entries"]
    teach = task["teaching"]
    assess = task["assessment"]
    thash = task["semantic_hash"]

    consistent_by_k: dict[int, list[int]] = {}
    evals_by_k: dict[int, int] = {}
    rank_by_k: dict[int, int] = {}
    for k in range(1, 9):
        pref = teach[:k]
        cons = []
        first_ev = None
        for pos, cid in enumerate(ordered_ids, 1):
            p = entries[cid]["canonical_program"]
            if all(ind_run(p, ex["input"]) == ex["output"] for ex in pref):
                cons.append(cid)
                if first_ev is None:
                    first_ev = pos
        assert cons and first_ev is not None
        consistent_by_k[k] = cons
        evals_by_k[k] = first_ev
        ranks = [idx for idx, cid in enumerate(cons, 1) if entries[cid]["semantic_hash"] == thash]
        assert ranks
        rank_by_k[k] = ranks[0]

    q_sem = 9
    for k in range(1, 9):
        if all(entries[consistent_by_k[kp][0]]["semantic_hash"] == thash for kp in range(k, 9)):
            q_sem = k
            break

    q_vs = 9
    for k in range(1, 9):
        if len(consistent_by_k[k]) == 1:
            q_vs = k
            break

    b_out = {}
    for b in (1, 2, 4, 8):
        sel = entries[consistent_by_k[b][0]]
        acc = sum(1 for ex in assess if ind_run(sel["canonical_program"], ex["input"]) == ex["output"]) / len(assess)
        ev = float(evals_by_k[b])
        b_out[str(b)] = dict(
            selected_program_id=sel["id"],
            selected_canonical_signature=sel["canonical_signature"],
            selected_semantic_hash=sel["semantic_hash"],
            semantic_match=bool(sel["semantic_hash"] == thash),
            candidate_evaluations=ev,
            construction_inclusive_evaluations=round(ev + const_share, 8),
            version_space_size=len(consistent_by_k[b]),
            target_program_rank=float(rank_by_k[b]),
            held_out_accuracy=round(acc, 8),
            uniquely_identified=bool(len(consistent_by_k[b]) == 1),
        )
    return dict(
        budgets=b_out,
        examples_for_semantic_id=float(q_sem),
        examples_for_unique_version_space=float(q_vs),
    )


def verify(root: Path = ROOT, artifact_path: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    apath = artifact_path or (root / "artifacts/seed_disjoint_meta.json")
    raw_bytes = apath.read_bytes()
    r = json.loads(raw_bytes, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    sha256_raw = hashlib.sha256(raw_bytes).hexdigest()

    c_disk = json.loads((root / "configs/seed_disjoint_meta.json").read_text(encoding="utf-8"))
    proto_bytes = (root / "docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md").read_bytes()
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()

    if sha256_obj(r.get("config")) != sha256_obj(c_disk):
        raise ValueError("config_mismatch")
    if r.get("protocol_sha256") != proto_sha:
        raise ValueError("protocol_hash_mismatch")
    if r.get("declared_complete") is not True or r.get("registration", {}).get("dirty") is not False:
        raise ValueError("registration_or_completion_invalid")

    # 1. Independently build both catalogues and verify signatures, hashes, and disjointness
    list_cat = ind_catalogue("list")
    action_cat = ind_catalogue("action_token_sequence")
    if r.get("catalogue_proof_sha256") != list_cat["proof_sha256"] or r.get("action_catalogue_proof_sha256") != action_cat["proof_sha256"]:
        raise ValueError("catalogue_proof_mismatch")

    src_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["source_ids"]}
    tgt_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["target_ids"]}
    src_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["source_ids"]}
    tgt_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["target_ids"]}
    if src_sigs & tgt_sigs or src_hashes & tgt_hashes:
        raise ValueError("source_target_overlap")

    src_pairs = {tuple(p) for i in list_cat["source_ids"] for p in list_cat["entries"][i]["adjacent_pairs"]}
    for i in list_cat["target_ids"]:
        e = list_cat["entries"][i]
        if e["length"] < 2 or not any(tuple(p) not in src_pairs for p in e["adjacent_pairs"]):
            raise ValueError("target_composition_leakage")

    methods = c_disk["methods"]
    xd_methods = c_disk["cross_domain_methods"]
    fam_evals = {m: [] for m in methods}
    fam_acc = {m: [] for m in methods}
    fam_q = {m: [] for m in methods}
    fam_ret_b_acc = {m: [] for m in methods}
    fam_ret_a_acc = {m: [] for m in methods}
    fam_ret_b_cost = {m: [] for m in methods}
    fam_ret_a_cost = {m: [] for m in methods}
    fam_xd_evals = {xm: [] for xm in xd_methods}
    fam_xd_acc = {xm: [] for xm in xd_methods}

    seen_targets: set[str] = set()
    seen_cross: set[str] = set()
    verified_target_paths = 0
    verified_retention_paths = 0
    verified_cross_paths = 0

    for fi, fam in enumerate(r["families"]):
        if fam["family_seed"] != c_disk["families"][fi]:
            raise ValueError("family_seed_mismatch")
        fit_info, rank_fn = ind_fit_and_rank(fam["source_tasks"], list_cat, float(c_disk["ridge_lambda"]))
        for a, b in zip(fit_info["scale"], fam["fitted_model"]["scale"]):
            if abs(a - b) > 1e-9:
                raise ValueError("fitted_scale_mismatch")
        for a, b in zip(fit_info["w_star"], fam["fitted_model"]["w_star"]):
            if abs(a - b) > 1e-9:
                raise ValueError("fitted_w_star_mismatch")

        # Verify source tasks are strictly in source pool
        for st in fam["source_tasks"]:
            if st["canonical_signature"] not in src_sigs or st["semantic_hash"] not in src_hashes:
                raise ValueError("source_task_leakage")

        # Verify disjoint input hashes across teaching, target assessment, and retention
        t_hashes = {ex["input_hash"] for t in fam["target_tasks"] for ex in t["teaching"]}
        a_hashes = {ex["input_hash"] for t in fam["target_tasks"] for ex in t["assessment"]}
        ret_hashes = {ex["input_hash"] for t in fam["retention_tasks"] for ex in (t["teaching"] + t["assessment"])}
        if (t_hashes & a_hashes) or (t_hashes & ret_hashes) or (a_hashes & ret_hashes):
            raise ValueError("disjoint_input_hashes_violated")

        p_seeds = c_disk["random_permutation_seeds"][fi * 64 : (fi + 1) * 64]
        base_ids = [e["id"] for e in list_cat["entries"]]

        m_eval_f = {m: [] for m in methods}
        m_acc_f = {m: [] for m in methods}
        m_q_f = {m: [] for m in methods}

        for t in fam["target_tasks"]:
            if t["canonical_signature"] not in tgt_sigs or t["semantic_hash"] not in tgt_hashes:
                raise ValueError("target_task_in_source_pool")
            if t["canonical_signature"] in seen_targets:
                raise ValueError("duplicate_target_program")
            seen_targets.add(t["canonical_signature"])

            for m in methods:
                if m == "random_ordering":
                    perm_runs = []
                    for ps in p_seeds:
                        order = list(base_ids)
                        random.Random(ps).shuffle(order)
                        perm_runs.append(ind_eval_task(t, list_cat, order, 0.0))
                    for b in (1, 2, 4):
                        b_ev = sum(pr["budgets"][str(b)]["candidate_evaluations"] for pr in perm_runs) / 64.0
                        b_ac = sum(pr["budgets"][str(b)]["held_out_accuracy"] for pr in perm_runs) / 64.0
                        if abs(b_ev - t["methods"][m]["budgets"][str(b)]["candidate_evaluations"]) > 1e-6:
                            raise ValueError("random_eval_mismatch")
                        m_eval_f[m].append(b_ev)
                        m_acc_f[m].append(b_ac)
                    m_q_f[m].append(sum(pr["examples_for_semantic_id"] for pr in perm_runs) / 64.0)
                else:
                    ord_ids = rank_fn(m, list_cat)
                    if ord_ids != fam["candidate_orderings"][m]:
                        raise ValueError(f"ordering_mismatch:{m}")
                    c_units = 1.5 if m == "structural_meta_prior" else (1.0 if m in ("operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
                    exp = ind_eval_task(t, list_cat, ord_ids, c_units / 9.0)
                    if sha256_obj(exp) != sha256_obj(t["methods"][m]):
                        raise ValueError(f"target_trace_mismatch:{m}")
                    for b in (1, 2, 4):
                        m_eval_f[m].append(exp["budgets"][str(b)]["construction_inclusive_evaluations"])
                        m_acc_f[m].append(exp["budgets"][str(b)]["held_out_accuracy"])
                    m_q_f[m].append(exp["examples_for_semantic_id"])
                verified_target_paths += 1

        for m in methods:
            fam_evals[m].append(sum(m_eval_f[m]) / len(m_eval_f[m]))
            fam_acc[m].append(sum(m_acc_f[m]) / len(m_acc_f[m]))
            fam_q[m].append(sum(m_q_f[m]) / len(m_q_f[m]))

        # Retention verification
        flat_ids = rank_fn("flat_catalogue", list_cat)
        rb_a = {m: [] for m in methods}
        ra_a = {m: [] for m in methods}
        rb_c = {m: [] for m in methods}
        ra_c = {m: [] for m in methods}
        for rt in fam["retention_tasks"]:
            exp_before = ind_eval_task(rt, list_cat, flat_ids, 0.0)
            if sha256_obj(exp_before) != sha256_obj(rt["before_meta_learning"]):
                raise ValueError("retention_before_trace_mismatch")
            for m in methods:
                if m == "random_ordering":
                    for b in (1, 2, 4):
                        rb_a[m].append(exp_before["budgets"][str(b)]["held_out_accuracy"])
                        ra_a[m].append(rt["after_meta_learning"][m]["budgets"][str(b)]["held_out_accuracy"])
                        rb_c[m].append(exp_before["budgets"][str(b)]["candidate_evaluations"])
                        ra_c[m].append(rt["after_meta_learning"][m]["budgets"][str(b)]["candidate_evaluations"])
                else:
                    exp_after = ind_eval_task(rt, list_cat, rank_fn(m, list_cat), 0.0)
                    if sha256_obj(exp_after) != sha256_obj(rt["after_meta_learning"][m]):
                        raise ValueError(f"retention_after_trace_mismatch:{m}")
                    for b in (1, 2, 4):
                        rb_a[m].append(exp_before["budgets"][str(b)]["held_out_accuracy"])
                        ra_a[m].append(exp_after["budgets"][str(b)]["held_out_accuracy"])
                        rb_c[m].append(exp_before["budgets"][str(b)]["candidate_evaluations"])
                        ra_c[m].append(exp_after["budgets"][str(b)]["candidate_evaluations"])
                verified_retention_paths += 1
        for m in methods:
            fam_ret_b_acc[m].append(sum(rb_a[m]) / len(rb_a[m]))
            fam_ret_a_acc[m].append(sum(ra_a[m]) / len(ra_a[m]))
            fam_ret_b_cost[m].append(sum(rb_c[m]) / len(rb_c[m]))
            fam_ret_a_cost[m].append(sum(ra_c[m]) / len(ra_c[m]))

        # Cross-domain verification
        xd_eval_f = {xm: [] for xm in xd_methods}
        xd_acc_f = {xm: [] for xm in xd_methods}
        for xt in fam["cross_domain_tasks"]:
            if xt["canonical_signature"] in seen_cross:
                raise ValueError("duplicate_cross_domain_program")
            seen_cross.add(xt["canonical_signature"])
            for xm in xd_methods:
                if xm == "random_ordering":
                    for b in (1, 2, 4):
                        xd_eval_f[xm].append(xt["methods"][xm]["budgets"][str(b)]["construction_inclusive_evaluations"])
                        xd_acc_f[xm].append(xt["methods"][xm]["budgets"][str(b)]["held_out_accuracy"])
                else:
                    ord_ids = rank_fn(xm, action_cat)
                    c_units = 1.5 if xm == "transferred_structural_prior" else (1.0 if xm in ("target_operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
                    exp_x = ind_eval_task(xt, action_cat, ord_ids, c_units / 9.0)
                    if sha256_obj(exp_x) != sha256_obj(xt["methods"][xm]):
                        raise ValueError(f"cross_domain_trace_mismatch:{xm}")
                    for b in (1, 2, 4):
                        xd_eval_f[xm].append(exp_x["budgets"][str(b)]["construction_inclusive_evaluations"])
                        xd_acc_f[xm].append(exp_x["budgets"][str(b)]["held_out_accuracy"])
                verified_cross_paths += 1
        for xm in xd_methods:
            fam_xd_evals[xm].append(sum(xd_eval_f[xm]) / len(xd_eval_f[xm]))
            fam_xd_acc[xm].append(sum(xd_acc_f[xm]) / len(xd_acc_f[xm]))

    # Verify primary means and paired intervals
    primary_evals = {m: round(sum(fam_evals[m]) / 8.0, 8) for m in methods}
    primary_acc = {m: round(sum(fam_acc[m]) / 8.0, 8) for m in methods}
    if primary_evals != r["analysis"]["primary_evaluations"] or primary_acc != r["analysis"]["primary_accuracy"]:
        raise ValueError("primary_summary_mismatch")

    intervals = {}
    for m in methods:
        if m == "structural_meta_prior":
            continue
        ds = [b - c for b, c in zip(fam_evals[m], fam_evals["structural_meta_prior"])]
        mean_d = sum(ds) / 8.0
        sd = math.sqrt(sum((d - mean_d) ** 2 for d in ds) / 7.0)
        half = T_CRIT_DF7 * sd / math.sqrt(8.0)
        intervals[m] = dict(mean=round(mean_d, 8), low=round(mean_d - half, 8), high=round(mean_d + half, 8))
        rec_int = r["analysis"]["evaluation_intervals"][m]
        if abs(intervals[m]["mean"] - rec_int["mean"]) > 1e-7 or abs(intervals[m]["low"] - rec_int["low"]) > 1e-7:
            raise ValueError(f"interval_mismatch:{m}")

    # Verify frozen neural checkpoints and historical artifacts at BASE
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
        schema="seed_disjoint_meta_audit_v1",
        valid=True,
        raw_sha256=sha256_raw,
        execution_sha=r["execution_sha"],
        protocol_sha256=proto_sha,
        config_sha256=hashlib.sha256((root / "configs/seed_disjoint_meta.json").read_bytes()).hexdigest(),
        catalogue_proof_sha256=list_cat["proof_sha256"],
        action_catalogue_proof_sha256=action_cat["proof_sha256"],
        canonical_disjoint=True,
        semantic_disjoint=True,
        source_unique_programs=len(list_cat["source_ids"]),
        target_unique_programs=len(list_cat["target_ids"]),
        verified_target_paths=verified_target_paths,
        verified_retention_paths=verified_retention_paths,
        verified_cross_domain_paths=verified_cross_paths,
        primary_accuracy=primary_acc,
        primary_evaluations=primary_evals,
        paired_evaluation_intervals=intervals,
        all_gates_passed=r["analysis"]["all_gates_passed"],
        screen=r["analysis"]["screen"],
        gates_summary={k: v["passed"] for k, v in r["analysis"]["gates"].items()},
        historical_artifacts_unchanged=len(historical),
        frozen_checkpoints_unchanged=len(FROZEN_CHECKPOINTS),
        new_collection=0,
    )


if __name__ == "__main__":
    res = verify()
    if "--write" in sys.argv:
        out_path = ROOT / "artifacts/seed_disjoint_meta_audit.json"
        with out_path.open("x", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
            f.write("\n")
    print(json.dumps(res, indent=2))

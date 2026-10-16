#!/usr/bin/env python3
"""Independent saved-Q arithmetic and source-log mapping; no model or simulator calls."""
import json
import math
from pathlib import Path

import audit_successor_archived_parity as audit


def verify(payload=None):
    cfg = audit.load_config()
    p = json.loads(audit.OUTPUT.read_text()) if payload is None else payload
    if p.get("complete") is not True or p.get("source_dirty") is not False:
        raise ValueError("incomplete or dirty execution")
    if p["parents"] != cfg["parents"] or p["config_sha256"] != audit.common.sha(audit.CONFIG) or p["protocol_sha256"] != audit.common.sha(audit.PROTOCOL):
        raise ValueError("result provenance drift")
    for file, digest in p["code_hashes"].items():
        if audit.common.sha(file) != digest: raise ValueError("execution code changed")
    archive, _ = audit.inputs()
    expected = audit.expected_grid(cfg)
    seen = set(); matches = ranks = numeric = near = 0; maximum = 0.; minimum = math.inf
    groups = {}
    for r in p["rows"]:
        key = tuple(r[k] for k in ("decoder", "task", "visitor", "phase", "context"))
        if key not in expected or key in seen: raise ValueError("missing/duplicate grid")
        seen.add(key)
        trace = archive[r["decoder"], r["task"]][r["visitor"]]
        if r["observation"] != trace["obs"][r["phase"]] or r["candidate_seed"] != trace["seeds"][r["phase"]]:
            raise ValueError("observation or candidate seed not from the registered archive")
        old, new = r["reference_q"], r["batched_q"]
        if len(old) != 3 or len(new) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in old + new):
            raise ValueError("invalid Q data")
        order = sorted(range(3), key=lambda i: (old[i], i))
        new_order = sorted(range(3), key=lambda i: (new[i], i))
        old_action = max(range(3), key=lambda i: old[i])
        new_action = max(range(3), key=lambda i: new[i])
        gap = old[order[-1]] - old[order[-2]]
        threshold = 2 * (cfg["q_atol"] + cfg["q_rtol"] * max(abs(v) for v in old))
        # The registered runner calls np.allclose(old, new): new is argument two.
        within = all(abs(b - a) <= cfg["q_atol"] + cfg["q_rtol"] * abs(b) for a, b in zip(old, new))
        m = dict(action_equal=old_action == new_action, ranking_equal=order == new_order,
                 q_within_tolerance=within, max_absolute_q_difference=max(abs(a-b) for a,b in zip(old,new)),
                 reference_top_gap=gap, near_tie_threshold=threshold, near_tie=gap <= threshold)
        if m != r["metrics"] or old_action != r["reference_action"] or new_action != r["batched_action"]:
            raise ValueError("saved arithmetic or selected action differs")
        if r["fingerprint_before"] != r["fingerprint_after"]: raise ValueError("frozen fingerprint changed")
        for name, count in (("reference",51), ("batched",17)):
            if r[name+"_counts"] != dict(step_calls=count, forward_calls=count, imagined_transitions=771):
                raise ValueError("per-cell accounting changed")
        matches += m["action_equal"]; ranks += m["ranking_equal"]; numeric += within; near += m["near_tie"]
        maximum = max(maximum, m["max_absolute_q_difference"]); minimum = min(minimum, gap)
        for field in ("decoder", "task", "visitor", "phase", "context"):
            groups.setdefault(f'{field}_{r[field]}', []).append(m)
    if seen != expected: raise ValueError("incomplete grid")
    pooled = dict(cases=len(seen), action_matches=matches, ranking_matches=ranks,
                  numerical_matches=numeric, near_ties=near, max_absolute_q_difference=maximum, minimum_top_gap=minimum)
    if pooled != p["groups"]["pooled"]: raise ValueError("pooled summary differs")
    for name, rows in groups.items():
        rebuilt = dict(cases=len(rows), action_matches=sum(r["action_equal"] for r in rows),
                       ranking_matches=sum(r["ranking_equal"] for r in rows),
                       numerical_matches=sum(r["q_within_tolerance"] for r in rows),
                       near_ties=sum(r["near_tie"] for r in rows),
                       max_absolute_q_difference=max(r["max_absolute_q_difference"] for r in rows),
                       minimum_top_gap=min(r["reference_top_gap"] for r in rows))
        if rebuilt != p["groups"][name]: raise ValueError("subgroup summary differs")
    if set(p["groups"]) != {"pooled", *groups}: raise ValueError("unexpected/missing subgroup")
    if p["counts"] != dict(model_calls=len(seen)*68, imagined_transitions=len(seen)*1542):
        raise ValueError("execution totals changed")
    if not 0 < p["wall_clock_s"] <= cfg["time_cap_s"]: raise ValueError("audit exceeded budget")
    if p["new_environment_interactions"] != 0 or p["optimizer_updates"] != 0 or p["historical_controller_changed"] is not False:
        raise ValueError("unexpected experiment or integration")
    d, s = audit.metadata_records(); expected_records = list(d.values()) + list(s.values())
    if p["checkpoint_records"] != expected_records or p["checkpoint_after_verified"] != 60:
        raise ValueError("checkpoint grid differs from metadata")
    expected_label = "archived_decision_parity_established_on_tested_inputs" if matches == numeric == len(seen) else "archived_decision_parity_not_established"
    if p["label"] != expected_label: raise ValueError("decision label differs")
    return dict(verified=True, kind="independent_arithmetic_and_archive_mapping_not_control_evidence",
                raw_sha256=audit.common.sha(audit.OUTPUT), pooled=pooled,
                new_environment_interactions=0, new_model_inference_calls=0)


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))

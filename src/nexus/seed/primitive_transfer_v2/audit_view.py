"""Superseding scientific interpretation without modifying historical artifacts."""
from copy import deepcopy

CONCLUSION = ("Open Primitive Transfer v1 Stage-B results do not establish "
              "autonomous primitive acquisition or learning-rule transfer.")


def audited_replay(historical):
    row = deepcopy(historical)
    row["status"] = "unsupported_scientific_claim"
    row["scientific_claim"] = "unsupported_after_source_audit"
    row["failure"] = CONCLUSION
    # The original card mislabels a constructed execution-cost proxy as MSE.
    # Keep it in historical detail, not the current-result metric headline.
    row["metrics"] = None
    row["open_primitive_transfer"]["audit_status"] = "UNSUPPORTED_V1_STAGE_B"
    row["open_primitive_transfer"]["audit_conclusion"] = CONCLUSION
    return row

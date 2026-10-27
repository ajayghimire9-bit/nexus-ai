"""Outcome contract (Stage 1, NOT LOCKED): one closed outcome vocabulary shared by the symbolic solver and the Stage 3 data
engineering agent, so that a valid result, a runtime error and an under-specified request can never be conflated.

Checker v5 stays read-only (RULE 2). This layer only READS its verdict plus the candidate's own answers. It exists because v5
on its own conflates two cases: on an extra (future) input, v5's `extra[i].answers` counts the ERROR marker as an ordinary
answer, so an input whose only in-scope answer is ERROR has answers == 1 and looks unique (Wave 40 UserAgent.000007).

Per-input outcomes (first match wins):
  ABSTAIN_UNSUPPORTED      v5 ABSTAIN for unsupported / outside-scope / malformed evidence (semantics v5 cannot check)
  ABSTAIN_ERROR            the candidate's answer on this input is ERROR (never reported as a valid result)
  ASK_CLARIFICATION        more than one in-scope answer and a stakeholder channel exists: the only correct action is to ask
  UNDER_SPECIFIED_WARNING  more than one in-scope answer and no channel: reported as not unique, never as valid
  VALID_UNIQUE             v5 SCOPE_UNIQUE and exactly one non-ERROR in-scope answer, equal to the candidate's
Project-level outcomes for the Stage 3 agent reuse the same names plus COMPLETED_VERIFIED / COMPLETED_UNVERIFIED / HARD_FAIL."""
from __future__ import annotations

from nexus import checker_kernel_v5 as V5

VALID_UNIQUE = "VALID_UNIQUE"
ABSTAIN_ERROR = "ABSTAIN_ERROR"
UNDER_SPECIFIED_WARNING = "UNDER_SPECIFIED_WARNING"
ASK_CLARIFICATION = "ASK_CLARIFICATION"
ABSTAIN_UNSUPPORTED = "ABSTAIN_UNSUPPORTED"
INPUT_OUTCOMES = (VALID_UNIQUE, ABSTAIN_ERROR, UNDER_SPECIFIED_WARNING, ASK_CLARIFICATION, ABSTAIN_UNSUPPORTED)

COMPLETED_VERIFIED = "COMPLETED_VERIFIED"         # every declared invariant passed
COMPLETED_UNVERIFIED = "COMPLETED_UNVERIFIED"     # ran without exception; no invariant evidence (conventional stop rule)
HARD_FAIL = "HARD_FAIL"                           # no runnable pipeline within budget
PROJECT_OUTCOMES = (COMPLETED_VERIFIED, COMPLETED_UNVERIFIED, HARD_FAIL, ABSTAIN_ERROR, ASK_CLARIFICATION,
                    UNDER_SPECIFIED_WARNING, ABSTAIN_UNSUPPORTED)

_UNSUPPORTED = {"unsupported", "unsupported_value", "candidate_outside_scope", "malformed", "wrong_checker_version",
                "lemmas_or_proofs_not_accepted_in_v5", "budget_exhausted"}


def input_outcomes(evidence, verdict, channel=False):
    """Outcome for the query (first) and every extra query, from v5's verdict and the candidate's own answers."""
    inputs = [evidence["query"]] + list(evidence.get("extra_queries") or [])
    if verdict["label"] == "ABSTAIN" and verdict.get("reason") in _UNSUPPORTED:
        return [ABSTAIN_UNSUPPORTED] * len(inputs)
    many = UNDER_SPECIFIED_WARNING if not channel else ASK_CLARIFICATION
    counts = [verdict.get("k") if verdict["label"] == "AMBIGUOUS" else 1] + [e["answers"] for e in verdict.get("extra", [])]
    if len(counts) < len(inputs):                      # verdicts without per-input counts (ABSTAIN) carry no uniqueness
        counts += [None] * (len(inputs) - len(counts))
    out = []
    for x, n in zip(inputs, counts):
        a = V5.apply_chain(list(evidence["candidate"]), x)
        if a is V5.ERRK:
            out.append(ABSTAIN_ERROR)
        elif n is None:
            out.append(ABSTAIN_UNSUPPORTED)
        elif n > 1:
            out.append(many)
        elif verdict["label"] == "SCOPE_UNIQUE":
            out.append(VALID_UNIQUE)
        else:
            out.append(ABSTAIN_UNSUPPORTED)
    return out


def is_answer(outcome):
    """Only VALID_UNIQUE (inputs) or COMPLETED_VERIFIED (projects) may be presented as a checked result."""
    return outcome in (VALID_UNIQUE, COMPLETED_VERIFIED)

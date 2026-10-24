"""Three evaluator claims. Finite agreeing probes do not establish exact identity.

Catalogue identification, predictive competence and exact mechanism
identification are scored separately. Observational twins are an
equivalence class. Guessing the hidden generator's name is not success.
"""
from __future__ import annotations

from typing import Any

from .mechanism_compose import class_for_hidden, pipe_name
from .mechanism_world import LANGUAGE


def parse_pipe(name: str | None) -> tuple[str, ...] | None:
    if not name:
        return None
    return tuple(name.split("|"))


def score_claims(
    task: dict[str, Any],
    remaining_language: list[str],
    synthesized: dict[str, Any] | None,
    identified: str | None,
    stopped: str | None,
    holdout: list[dict[str, Any]],
) -> dict[str, Any]:
    gold = task["mechanism"]
    in_language = gold in LANGUAGE
    catalogue_identification = len(remaining_language) == 1
    predictive_competence = bool(holdout) and all(
        row.get("predicted") is not None and int(row["predicted"]) == int(row["observed"])
        for row in holdout
    )
    exact_mechanism_identification = False
    gold_class = class_for_hidden(gold, primitives=task.get("primitives"))
    reported = list((synthesized or {}).get("remaining") or [])
    if not reported and catalogue_identification:
        reported = list(remaining_language)
    scoped_match = bool(gold_class) and set(reported) == set(gold_class)
    if not gold_class and catalogue_identification:
        scoped_match = remaining_language[0] == gold
    claimed_exact = stopped == "STOP_IDENTIFY"
    guessed_generator = bool(identified == gold and not in_language)
    scoped_report = (
        "consistent with {0}; exact identity unresolved".format(
            remaining_language[0] if catalogue_identification else (
                (synthesized or {}).get("representative") or "empty"
            )
        )
        if (reported or catalogue_identification) else "unresolved"
    )
    useful_acquisition = bool(
        predictive_competence and not guessed_generator and task.get("role") != "reject"
    )
    correct_reject = bool(task.get("role") == "reject" and not predictive_competence
                          and not guessed_generator and not claimed_exact)
    return dict(
        catalogue_identification=catalogue_identification,
        predictive_competence=predictive_competence,
        exact_mechanism_identification=exact_mechanism_identification,
        exact_unrestricted_environment=False,
        equivalence_class=gold_class or list(remaining_language),
        reported_class=reported,
        scoped_match=scoped_match,
        scoped_report=scoped_report,
        claimed_exact=claimed_exact,
        guessed_generator=guessed_generator,
        useful_acquisition=useful_acquisition,
        correct_reject=correct_reject,
        demonstrated_inconsistency=bool(not remaining_language and not reported),
        unresolved_uncertainty=bool((remaining_language or reported) and not predictive_competence),
        gold_in_language=in_language,
    )

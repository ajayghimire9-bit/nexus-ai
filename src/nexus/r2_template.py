"""R2 pipeline generator (NOT LOCKED): the R1 template (r1_template, unchanged) plus two decisions for rules every de4 spec
declares (author-written handlers, disclosed in the R2 pre-registration):
  fx_unknown      error (an order in a currency outside the fx table fails the run) | quarantine (consumed with status
                  unknown_currency, listed in quarantine, never a bronze / silver row)
  discount_unit   percent_only (discount always read as percent) | registry_unit (a registry version declaring
                  discount_unit = fraction is converted: percent = value x 100)
Silver-stage exceptions are reported as stage=silver (the Stage 4 consumer reported them as stage=gold).
Exact, asserted text patches of r1_template.SRC."""
from __future__ import annotations

import json

from nexus import r1_template as RT

DECISIONS = dict(RT.DECISIONS, fx_unknown=["error", "quarantine"], discount_unit=["percent_only", "registry_unit"])
CORRECT = dict(RT.CORRECT, fx_unknown={"quarantine"}, discount_unit={"registry_unit"})
STAGE_OF = dict(RT.STAGE_OF, fx_unknown="silver", discount_unit="decode")
DEPLOY_DEFAULT = RT.DEPLOY_DEFAULT
config_from_spec = RT.config_from_spec

PATCHES = [
    ("""    elif sh == "registry_typed":
        disc = float(disc) if reg["types"].get("discount") == "float" else int(disc)""",
     """    elif sh == "registry_typed":
        disc = float(disc) if reg["types"].get("discount") == "float" else int(disc)
    if DEC["discount_unit"] == "registry_unit" and reg["types"].get("discount_unit") == "fraction":
        disc = float(disc) * 100"""),
    ("""                soft = 1 if row and row["deleted"] else 0
                if DEC["txn_isolation"] == "read_committed" and rec.get("txn_id"):""",
     """                soft = 1 if row and row["deleted"] else 0
                if DEC["fx_unknown"] == "quarantine" and row and row.get("currency") not in cfg["fx"]:
                    status = "unknown_currency"
                elif DEC["txn_isolation"] == "read_committed" and rec.get("txn_id"):"""),
    ("""WHEN 'future' THEN 'future_event' ELSE 'poison' END AS reason FROM _consumed "
                "WHERE status IN ('malformed', 'future', 'poison')")""",
     """WHEN 'future' THEN 'future_event' WHEN 'unknown_currency' THEN 'unknown_currency' ELSE 'poison' END AS reason "
                "FROM _consumed WHERE status IN ('malformed', 'future', 'poison', 'unknown_currency')")"""),
    ("""        changed, prev = build(con, cfg)""",
     """        try:
            changed, prev = build(con, cfg)
        except Exception as e:
            raise StageError(f"stage=silver {type(e).__name__}: {e}") from e"""),
]


def _src():
    s = RT.SRC
    for a, b in PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"R2 template patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    return s


SRC = _src()


def correct_choice():
    return {d: sorted(CORRECT[d])[-1] for d in DECISIONS}


def emit(choice):
    missing = set(DECISIONS) - set(choice)
    if missing:
        raise ValueError(f"missing decisions {sorted(missing)}")
    for k, v in choice.items():
        if v not in DECISIONS[k]:
            raise ValueError(f"{k}={v} not an option")
    return SRC.replace("{DECISIONS}", json.dumps({k: choice[k] for k in DECISIONS}, sort_keys=True))

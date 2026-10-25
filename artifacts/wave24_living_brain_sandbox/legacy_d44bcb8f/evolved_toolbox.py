# nexus evolved toolbox

import math

import operator

def skill_2_chain_e63f679a(x):
    if not isinstance(x, int):
        return x
    v_1 = _apply(operator.inv, x)
    v_2 = _apply(math.acos, v_1)
    return v_2

def _apply(fn, value):
    try:
        out = fn(value)
    except Exception:
        return value
    if type(out) is bool:
        return int(out)
    if type(out) is float and out == int(out) and abs(out) < 10 ** 6:
        return int(out)
    if type(out) is int and abs(out) < 10 ** 6:
        return out
    return value

def skill_2_branch_1ce1fd2c(x):
    if not isinstance(x, int):
        return x
    try:
        if x < 0:
            v_1 = _apply(math.acos, x)
            return v_1
        else:
            v_2 = skill_2_chain_e63f679a(x)
            return v_2
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
        v_3 = skill_2_chain_e63f679a(x)
        return v_3

# nexus evolved toolbox

import operator

def skill_0_chain_45d55644(x):
    if not isinstance(x, int):
        return x
    v_1 = _apply(operator.inv, x)
    v_2 = _apply(operator.neg, v_1)
    return v_2

def _apply(fn, value):
    out = fn(value)
    if type(out) is bool:
        return int(out)
    if type(out) is float and out == out and abs(out) < 10 ** 6 and out == int(out):
        return int(out)
    if type(out) is int and abs(out) < 10 ** 6:
        return out
    raise ValueError('non-integer result outside the int domain')

import math

def skill_0_branch_d220ad09(x):
    if not isinstance(x, int):
        return x
    if x < 0:
        v_1 = _apply(math.fabs, x)
        return v_1
    else:
        v_2 = skill_0_chain_45d55644(x)
        return v_2

def skill_0_recover_17ff9193(x):
    if not isinstance(x, int):
        return x
    try:
        v_1 = _apply(math.cbrt, x)
        return v_1
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
        v_2 = skill_0_branch_d220ad09(x)
        return v_2

def skill_1_chain_82f1719b(x):
    if not isinstance(x, int):
        return x
    v_1 = _apply(operator.inv, x)
    v_2 = _apply(operator.not_, v_1)
    return v_2

def skill_1_compound_6cb45d36(x):
    if not isinstance(x, int):
        return x
    v_1 = skill_0_chain_45d55644(x)
    v_2 = skill_1_chain_82f1719b(v_1)
    return v_2

def skill_1_branch_88319daf(x):
    if not isinstance(x, int):
        return x
    if x < 0:
        v_1 = skill_0_branch_d220ad09(x)
        return v_1
    else:
        v_2 = skill_0_recover_17ff9193(x)
        return v_2

def skill_2_chain_67c7515f(x):
    if not isinstance(x, int):
        return x
    v_1 = _apply(operator.inv, x)
    v_2 = skill_1_branch_88319daf(v_1)
    return v_2

def skill_2_compound_c29b968f(x):
    if not isinstance(x, int):
        return x
    v_1 = skill_0_chain_45d55644(x)
    v_2 = skill_2_chain_67c7515f(v_1)
    return v_2

def skill_2_branch_18d8f35f(x):
    if not isinstance(x, int):
        return x
    if x < 0:
        v_1 = _apply(math.isfinite, x)
        return v_1
    else:
        v_2 = skill_2_compound_c29b968f(x)
        return v_2

def skill_2_recover_88da0f12(x):
    if not isinstance(x, int):
        return x
    if x < 0:
        v_1 = skill_2_branch_18d8f35f(x)
        return v_1
    else:
        v_2 = _apply(math.exp2, x)
        return v_2

def skill_3_chain_45fc7dee(x):
    if not isinstance(x, int):
        return x
    v_1 = skill_1_chain_82f1719b(x)
    v_2 = _apply(operator.not_, v_1)
    return v_2

def skill_3_compound_1c0a234f(x):
    if not isinstance(x, int):
        return x
    v_1 = skill_0_chain_45d55644(x)
    v_2 = skill_2_branch_18d8f35f(v_1)
    return v_2

def skill_3_recover_9dc055f3(x):
    if not isinstance(x, int):
        return x
    if x < 0:
        v_1 = _apply(math.isinf, x)
        return v_1
    else:
        v_2 = skill_2_recover_88da0f12(x)
        return v_2

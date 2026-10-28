def value_fn(r, t):
    return (((100 * t.get('standing')) + (r.get('energy_kwh') * (r.get('rate_cents') / r.get('accrual_days')))) / (100 / r.get('accrual_days')))


def status_fn(r, t):
    if (not (((isinstance(r.get('accrual_days'), (int, float)) and not isinstance(r.get('accrual_days'), bool)) and (isinstance(r.get('energy_kwh'), (int, float)) and not isinstance(r.get('energy_kwh'), bool))) and (isinstance(r.get('rate_cents'), (int, float)) and not isinstance(r.get('rate_cents'), bool)))):
        return 'q:missing'
    elif (not (r.get('device_type') in t.get('allowed'))):
        return 'q:unknown_member'
    return 'ok'


class StateMachine_8d294bd7:
    """Invented by continuation splitting: 3 control modes (mode_0 = start), 2 data register(s).
    witness: histories ['OPEN'] vs [] differ after continuation ['ADJUST']
    witness: histories ['OPEN', 'DISPUTE'] vs [] differ after continuation ['OPEN']
    witness reg_0: in mode_1 histories ['OPEN'] / ['OPEN', 'CLOSE', 'OPEN', 'READ'] emit 0 / 1 after ['CLOSE']
    witness reg_1: in mode_1 histories ['OPEN'] / ['OPEN', 'CLOSE', 'OPEN', 'READ'] emit 0 / 405.93 after ['CLOSE']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}
        self.reg_1 = {}

    def ingest(self, rec):
        k, s = rec.get('trade_id'), rec.get('event')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        r1 = self.reg_1.get(k, 0)
        x1 = rec.get('qty_value')
        x1 = x1 if isinstance(x1, (int, float)) and not isinstance(x1, bool) else 0
        if m == 0:
            if s == 'ADJUST':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CLOSE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DISPUTE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'OPEN':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'READ':
                out = [('q:invalid', None, None)]
                return out
        elif m == 1:
            if s == 'ADJUST':
                out = []
                self.reg_1[k] = (r1 + x1)
                return out
            elif s == 'CLOSE':
                out = [('bill', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 0
                return out
            elif s == 'DISPUTE':
                out = []
                self.mode[k] = 2
                return out
            elif s == 'OPEN':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'READ':
                out = []
                self.reg_0[k] = (r0 + 1)
                self.reg_1[k] = (r1 + x1)
                return out
        elif m == 2:
            if s == 'ADJUST':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CLOSE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DISPUTE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'OPEN':
                out = [('disputed', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 1
                return out
            elif s == 'READ':
                out = []
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm

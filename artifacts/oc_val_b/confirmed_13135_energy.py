def value_fn(r, t):
    return (r.get('p_w') / (r.get('v') * r.get('amps')))


def status_fn(r, t):
    if (not (((isinstance(r.get('v'), (int, float)) and not isinstance(r.get('v'), bool)) and (isinstance(r.get('p_w'), (int, float)) and not isinstance(r.get('p_w'), bool))) and (isinstance(r.get('amps'), (int, float)) and not isinstance(r.get('amps'), bool)))):
        return 'q:missing'
    elif (not (r.get('venue') in t.get('allowed'))):
        return 'q:unknown_member'
    return 'ok'


class StateMachine_8d294bd7:
    """Invented by continuation splitting: 3 control modes (mode_0 = start), 2 data register(s).
    witness: histories ['OPEN'] vs [] differ after continuation ['ADJUST']
    witness: histories ['OPEN', 'DISPUTE'] vs [] differ after continuation ['OPEN']
    witness reg_0: in mode_1 histories ['DISPUTE', 'OPEN'] / ['OPEN', 'ADJUST', 'CLOSE', 'OPEN', 'READ', 'READ'] emit 0 / 2 after ['CLOSE']
    witness reg_1: in mode_1 histories ['DISPUTE', 'OPEN'] / ['OPEN', 'ADJUST'] emit 0 / 700.93 after ['CLOSE']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}
        self.reg_1 = {}

    def ingest(self, rec):
        k, s = rec.get('order_id'), rec.get('type')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        r1 = self.reg_1.get(k, 0)
        x1 = rec.get('amt')
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

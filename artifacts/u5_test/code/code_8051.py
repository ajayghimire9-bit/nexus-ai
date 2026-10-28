def value_fn(r, t):
    return (r.get('reading').get('value') - r.get('last'))


def status_fn(r, t):
    if (not (r.get('site') in t.get('allowed'))):
        return 'q:unknown_member'
    elif (not (((isinstance(r.get('last'), (int, float)) and not isinstance(r.get('last'), bool)) and (not isinstance(r.get('reading'), str))) and (not (r.get('reading') is None)))):
        return 'q:missing'
    return 'ok'


class StateMachine_19603a73:
    """Invented by continuation splitting: 2 control modes (mode_0 = start), 2 data register(s).
    witness: histories ['CONNECT'] vs [] differ after continuation ['CONNECT']
    witness reg_0: in mode_1 histories ['CONNECT', 'CONNECT', 'READ'] / ['CONNECT', 'CONNECT', 'READ', 'DISCONNECT', 'CONNECT', 'READ', 'CONNECT'] emit 1 / 0 after ['DISCONNECT']
    witness reg_1: in mode_1 histories ['CONNECT', 'CONNECT', 'READ'] / ['CONNECT', 'CONNECT', 'READ', 'DISCONNECT', 'CONNECT', 'READ', 'CONNECT'] emit 53.1 / 0 after ['DISCONNECT']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}
        self.reg_1 = {}

    def ingest(self, rec):
        k, s = rec.get('device_id'), rec.get('op')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        r1 = self.reg_1.get(k, 0)
        x1 = rec.get('value')
        x1 = x1 if isinstance(x1, (int, float)) and not isinstance(x1, bool) else 0
        if m == 0:
            if s == 'CONNECT':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'DISCONNECT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'READ':
                out = [('q:invalid', None, None)]
                return out
        elif m == 1:
            if s == 'CONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                return out
            elif s == 'DISCONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 0
                return out
            elif s == 'READ':
                out = []
                self.reg_0[k] = (r0 + 1)
                self.reg_1[k] = (r1 + x1)
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm

def value_fn(r, t):
    return (r.get('amps') * r.get('v'))


def status_fn(r, t):
    if (not ((isinstance(r.get('amps'), (int, float)) and not isinstance(r.get('amps'), bool)) and (isinstance(r.get('v'), (int, float)) and not isinstance(r.get('v'), bool)))):
        return 'q:missing'
    elif (not (r.get('warehouse') in t.get('allowed'))):
        return 'q:unknown_member'
    return 'ok'


class StateMachine_5b860c2e:
    """Invented by continuation splitting: 2 control modes (mode_0 = start), 2 data register(s).
    witness: histories ['CONNECT'] vs [] differ after continuation ['CONNECT']
    witness reg_0: in mode_1 histories ['CONNECT'] / ['CONNECT', 'DISCONNECT', 'CONNECT', 'CONNECT', 'READ'] emit 0 / 1 after ['DISCONNECT']
    witness reg_1: in mode_1 histories ['CONNECT'] / ['CONNECT', 'DISCONNECT', 'CONNECT', 'CONNECT', 'READ'] emit 0 / 27.3 after ['DISCONNECT']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}
        self.reg_1 = {}

    def ingest(self, rec):
        k, s = rec.get('ref'), rec.get('msg_type')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        r1 = self.reg_1.get(k, 0)
        x1 = rec.get('reading')
        x1 = x1 if isinstance(x1, (int, float)) and not isinstance(x1, bool) else 0
        if m == 0:
            if s == 'CONNECT':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'DISCONNECT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DISCONNECT_V2':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'READ':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'READ_V2':
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
            elif s == 'DISCONNECT_V2':
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
            elif s == 'READ_V2':
                out = []
                self.reg_0[k] = (r0 + 1)
                self.reg_1[k] = (r1 + x1)
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm

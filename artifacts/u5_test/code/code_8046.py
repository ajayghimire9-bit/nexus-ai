def value_fn(r, t):
    return (r.get('height') * (r.get('len_cm') * (r.get('w') / t.get('cm3_per_l'))))


def status_fn(r, t):
    if (not (((isinstance(r.get('len_cm'), (int, float)) and not isinstance(r.get('len_cm'), bool)) and (isinstance(r.get('height'), (int, float)) and not isinstance(r.get('height'), bool))) and (isinstance(r.get('w'), (int, float)) and not isinstance(r.get('w'), bool)))):
        return 'q:missing'
    elif (not (r.get('venue') in t.get('allowed'))):
        return 'q:unknown_member'
    return 'ok'


class StateMachine_e8d8e551:
    """Invented by continuation splitting: 7 control modes (mode_0 = start), 1 data register(s).
    witness: histories ['CREATE'] vs [] differ after continuation ['CANCEL']
    witness: histories ['CREATE', 'CANCEL'] vs [] differ after continuation ['CREATE']
    witness: histories ['CREATE', 'PACK'] vs ['CREATE'] differ after continuation ['PACK']
    witness: histories ['CREATE', 'PAY'] vs ['CREATE'] differ after continuation ['PACK']
    witness: histories ['CREATE', 'PACK', 'PAY'] vs ['CREATE', 'CANCEL'] differ after continuation ['DELIVER']
    witness: histories ['CREATE', 'PACK', 'PAY', 'DELIVER'] vs ['CREATE', 'CANCEL'] differ after continuation ['RETURN']
    witness reg_0: in mode_5 histories ['CREATE', 'PAY', 'DELIVER', 'PACK'] / ['CREATE', 'PACK', 'PAY'] emit 261.45 / 488.89 after ['DELIVER']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}

    def ingest(self, rec):
        k, s = rec.get('order_id'), rec.get('op')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        x0 = rec.get('qty_value')
        x0 = x0 if isinstance(x0, (int, float)) and not isinstance(x0, bool) else 0
        if m == 0:
            if s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CREATE':
                out = []
                self.reg_0[k] = x0
                self.mode[k] = 1
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PAY':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 1:
            if s == 'CANCEL':
                out = [('cancelled', r0, None)]
                self.mode[k] = 2
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = []
                self.mode[k] = 3
                return out
            elif s == 'PAY':
                out = []
                self.mode[k] = 4
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 2:
            if s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PAY':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 3:
            if s == 'CANCEL':
                out = [('cancelled', r0, None)]
                self.mode[k] = 2
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PAY':
                out = [('release', r0, None)]
                self.mode[k] = 5
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 4:
            if s == 'CANCEL':
                out = [('cancelled', r0, None)]
                self.mode[k] = 2
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = [('release', r0, None)]
                self.mode[k] = 5
                return out
            elif s == 'PAY':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 5:
            if s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('delivered', r0, None)]
                self.mode[k] = 6
                return out
            elif s == 'PACK':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PAY':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RETURN':
                out = [('q:invalid', None, None)]
                return out
        elif m == 6:
            if s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CREATE':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'DELIVER':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PACK':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PAY':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RETURN':
                out = [('returned', rec.get('qty_value'), None)]
                self.mode[k] = 2
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm

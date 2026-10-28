def value_fn(r, t):
    return (r.get('accrual_days') * (r.get('coupon') * (r.get('notional_amt') / t.get('day_count'))))


def status_fn(r, t):
    if (not (((isinstance(r.get('coupon'), (int, float)) and not isinstance(r.get('coupon'), bool)) and (isinstance(r.get('accrual_days'), (int, float)) and not isinstance(r.get('accrual_days'), bool))) and (isinstance(r.get('notional_amt'), (int, float)) and not isinstance(r.get('notional_amt'), bool)))):
        return 'q:missing'
    elif (not (r.get('desk') in t.get('allowed'))):
        return 'q:unknown_member'
    return 'ok'


class StateMachine_99635c95:
    """Invented by continuation splitting: 4 control modes (mode_0 = start), 1 data register(s).
    witness: histories ['NEW'] vs [] differ after continuation ['AMEND']
    witness: histories ['NEW', 'CANCEL'] vs [] differ after continuation ['NEW']
    witness: histories ['NEW', 'PREPARE'] vs ['NEW', 'CANCEL'] differ after continuation ['ABORT']
    witness reg_0: in mode_1 histories ['NEW'] / ['NEW'] emit 539.95 / 267.25 after ['CANCEL']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}

    def ingest(self, rec):
        k, s = rec.get('order_id'), rec.get('msg_type')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        x0 = rec.get('amt')
        x0 = x0 if isinstance(x0, (int, float)) and not isinstance(x0, bool) else 0
        if m == 0:
            if s == 'ABORT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'AMEND':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'COMMIT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'NEW':
                out = []
                self.reg_0[k] = x0
                self.mode[k] = 1
                return out
            elif s == 'PARTIAL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PREPARE':
                out = [('q:invalid', None, None)]
                return out
        elif m == 1:
            if s == 'ABORT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'AMEND':
                out = []
                self.reg_0[k] = x0
                return out
            elif s == 'CANCEL':
                out = [('cancelled', r0, None)]
                self.mode[k] = 2
                return out
            elif s == 'COMMIT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'NEW':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PARTIAL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PREPARE':
                out = []
                self.mode[k] = 3
                return out
        elif m == 2:
            if s == 'ABORT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'AMEND':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'COMMIT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'NEW':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PARTIAL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PREPARE':
                out = [('q:invalid', None, None)]
                return out
        elif m == 3:
            if s == 'ABORT':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'AMEND':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'CANCEL':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'COMMIT':
                out = [('settled', r0, None)]
                self.mode[k] = 2
                return out
            elif s == 'NEW':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'PARTIAL':
                out = [('partial', rec.get('amt'), None)]
                return out
            elif s == 'PREPARE':
                out = [('q:invalid', None, None)]
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm

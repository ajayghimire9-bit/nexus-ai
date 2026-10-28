def fn_5ba354e8(a, fields, types):
    return {
        'order_id': a.get('order_id'),
        'warehouse_id': a.get('warehouse_id'),
        'status': a.get('status'),
        'amount': a.get(fields.get('amount')),
        'currency': a.get('currency'),
        'discount': a.get('discount_pct'),
        'promised_ts': a.get('promised_ts'),
        'deleted': a.get('is_deleted')
    }


fn_decode = fn_5ba354e8


def fn_9977eb3b(p, fx):
    return round((p.get('amount') * (fx.get(p.get('currency')) * (1 - (p.get('discount') / 100)))), 2)


fn_net = fn_9977eb3b


def fn_2f20b2da(topic, rec, row, fx, whs):
    if ((not (row is None)) and (not (row.get('currency') in fx))):
        return 'q:unknown_currency'
    elif ((not (row is None)) and (not (row.get('warehouse_id') in whs))):
        return 'q:unknown_warehouse'
    elif isinstance(rec.get('weight'), str):
        return 'q:malformed_weight'
    return 'accepted'


fn_status = fn_2f20b2da


class StreamOrganelle_d512fd99:
    """Markov state violation: identical record content, different required outcome ([true, false]); state = dict keyed by 'key', order 'sv' >, tombstone"""

    def __init__(self):
        self.state = {}

    def ingest(self, r):
        k = r.get('key')
        cur = self.state.get(k)
        if cur is None or r.get('sv') > cur.get('sv'):
            self.state[k] = r

    def retract(self, k):
        self.state.pop(k, None)

    def flush(self):
        out = []
        n = 0
        for k in self.state:
            n += 1
            if n > 1000000:
                break
            r = self.state[k]
            if not (not ((not (r.get('payload') is None)) and (r.get('soft') == 0))):
                out.append(r)
        return out


SilverOrganelle = StreamOrganelle_d512fd99

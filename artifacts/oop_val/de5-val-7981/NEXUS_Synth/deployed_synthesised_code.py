def fn_fe972d63(a, fields, types):
    return {
        'order_id': a.get('ord_id'),
        'warehouse_id': a.get('wh_id'),
        'status': a.get('order_status'),
        'amount': ((a.get('total_value') / 100) if ('amount_unit' in types) else a.get(fields.get('amount'))),
        'currency': a.get('ccy'),
        'discount': a.get('disc'),
        'promised_ts': a.get('promised_ts'),
        'deleted': a.get('is_deleted')
    }


fn_decode = fn_fe972d63


def fn_9977eb3b(p, fx):
    return round((p.get('amount') * (fx.get(p.get('currency')) * (1 - (p.get('discount') / 100)))), 2)


fn_net = fn_9977eb3b


def fn_147cc3aa(topic, rec, row, fx, whs):
    if isinstance(rec.get('weight'), str):
        return 'q:malformed_weight'
    elif ((not (row is None)) and (not (row.get('currency') in fx))):
        return 'q:unknown_currency'
    elif ((not (row is None)) and (not (row.get('warehouse_id') in whs))):
        return 'q:unknown_warehouse'
    return 'accepted'


fn_status = fn_147cc3aa


class StreamOrganelle_7ae11363:
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


SilverOrganelle = StreamOrganelle_7ae11363

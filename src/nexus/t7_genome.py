"""Trial 7 - bounded pilot of a <= 64 KB neurosymbolic genome bottleneck (NOT LOCKED; numpy on CPU, no GPU).

Genome = neural half + symbolic half, serialised (float16 weights + JSON, zlib) and size-checked <= 65,536 bytes:
  neural    hyper-network MLP 8 -> 96 -> 96 -> 21 (~12 K parameters) mapping a NAME-FREE domain descriptor (mean column
            spectrum over the domain's tasks, numeric-column fraction, boolean-output fraction, mean record width) to the
            STARTING operator / leaf cost table of NEXUS's construction proposer (18 operator costs + 3 leaf costs)
  symbolic  MDL-rounded operator prior (integer cost table) and the decomposition split (construct_frac)
Generation boundary: the solution library is wiped; the genome is decoded on the new domain's descriptor; NEXUS trains
only on certified traces (verified solutions of that domain's tasks); the cost table those traces imply is distilled back
into the genome (a few SGD steps on (descriptor -> cost table), anchored to the previous weights), so task solutions cannot
pass - only how to set up learning does."""
from __future__ import annotations

import json
import math
import zlib

import numpy as np

from nexus import t7_transport as TR
from nexus.oop_synthesizer import BINARY, UNARY

OPS = list(UNARY + BINARY)
OUT = len(OPS) + 3
LIMIT = 65536


def descriptor(tasks):
    specs, num, width = [], [], []
    for t in tasks:
        cols = TR.columns(t.train)
        for v in cols.values():
            specs.append(TR.spectrum(v))
            num.append(all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v))
        width.append(len(cols))
    boolf = np.mean([isinstance(t.y_train[0], bool) for t in tasks])
    s = np.mean(specs, 0)
    return np.array([s[0], s[1], s[2], s[3], np.mean(num), boolf, np.mean(width) / 10, 1.0])


class Genome:
    def __init__(self, seed=0, hidden=96):
        r = np.random.RandomState(seed)
        self.W1, self.b1 = r.randn(8, hidden) * 0.3, np.zeros(hidden)
        self.W2, self.b2 = r.randn(hidden, hidden) * 0.1, np.zeros(hidden)
        self.W3, self.b3 = r.randn(hidden, OUT) * 0.1, np.zeros(OUT)
        self.prior = [1] * OUT
        self.split = 0.6

    def params(self):
        return [self.W1, self.b1, self.W2, self.b2, self.W3, self.b3]

    def n_params(self):
        return sum(p.size for p in self.params())

    def forward(self, x):
        h1 = np.tanh(x @ self.W1 + self.b1)
        h2 = np.tanh(h1 @ self.W2 + self.b2)
        return h2 @ self.W3 + self.b3, (x, h1, h2)

    def decode(self, desc):
        """Cost table = clip(round(prior + net(desc)), 1, 4)."""
        y, _ = self.forward(desc)
        c = np.clip(np.round(np.array(self.prior) + y), 1, 4).astype(int)
        return {o: int(c[i]) for i, o in enumerate(OPS)}, dict(var=int(c[-3]), key=int(c[-2]), num=int(c[-1]))

    def distill(self, desc, target, steps=200, lr=0.05, anchor=1e-3):
        """SGD on (desc -> target - prior), anchored to the current weights."""
        t = np.array(target, float) - np.array(self.prior, float)
        ref = [p.copy() for p in self.params()]
        for _ in range(steps):
            y, (x, h1, h2) = self.forward(desc)
            g = 2 * (y - t) / OUT
            gW3, gb3 = np.outer(h2, g), g
            d2 = (g @ self.W3.T) * (1 - h2 ** 2)
            gW2, gb2 = np.outer(h1, d2), d2
            d1 = (d2 @ self.W2.T) * (1 - h1 ** 2)
            gW1, gb1 = np.outer(x, d1), d1
            for p, gp, r0 in zip(self.params(), (gW1, gb1, gW2, gb2, gW3, gb3), ref):
                p -= lr * (gp + anchor * (p - r0))

    def serialise(self):
        blob = b"".join(p.astype(np.float16).tobytes() for p in self.params())
        meta = json.dumps(dict(prior=self.prior, split=self.split)).encode()
        return zlib.compress(blob + b"|" + meta, 9)

    def size(self):
        return len(self.serialise())


def target_costs(counts):
    """Cost table implied by certified traces (MDL rounding of -log2 frequency)."""
    tot = sum(counts.get(o, 0) + 0.5 for o in OPS)
    nl = {o: -math.log2((counts.get(o, 0) + 0.5) / tot) for o in OPS}
    m = min(nl.values())
    ops = [int(min(4, 1 + round((nl[o] - m) / 2))) for o in OPS]
    return ops + [1, 1, 1]

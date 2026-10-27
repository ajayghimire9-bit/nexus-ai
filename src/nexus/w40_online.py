"""Wave 40 payoff-gated online learning (SOLVER SIDE; NOT LOCKED), Step 5.3.

Wave 39's external online arm cost 1.20x Fresh. Decomposition (artifacts/w39_prose_confirm.json): refits cost 0.018 G in total;
the +462 G was child-side PRIOR EVALUATION (learned-mixture cost rows, O(T^2) per row in w38_learn) with no offsetting search
saving (certification is ~95% of work and identical across arms). So the gate counts both learning costs - refits AND prior
evaluation - against the measured search saving, all in deterministic execution-equivalent units (no wall clock; replayable):
  * uniform reference: every `period`-th task (and every task before a prior exists) is solved WITHOUT the prior; its search
    executions estimate what Fresh would spend (an A/B probe that costs nothing extra: the task is solved either way);
  * prior tasks: saving = mean(uniform executions so far) - executions with the prior; cost = C_ROW x cost-row entries computed;
  * refits: cost = C_FIT x program tokens refitted.
Net = sum(savings) - sum(costs). A refit is allowed only while Net > 0; after `warm` prior tasks, Net <= 0 switches the prior
OFF for the rest of the stream (no more refits, no more prior evaluation: the learner then costs what Fresh costs).
C_ROW / C_FIT are fixed constants (exec-equivalents), measured once on development data (scripts/w40_calibrate.py)."""
from __future__ import annotations

C_ROW = 0.052        # execution-equivalents per cost-row entry (scripts/w40_calibrate.py on PROSE-dev: 4.4k / 84.5k instructions)
C_FIT = 0.47         # execution-equivalents per program token refitted (w40_calibrate: 39.6k / 84.5k instructions)


class PayoffGated:
    def __init__(self, inner, period=4, warm=4, c_row=C_ROW, c_fit=C_FIT):
        self.inner, self.period, self.warm, self.c_row, self.c_fit = inner, period, warm, c_row, c_fit
        self.k, self.u, self.saved, self.cost, self.n_prior, self.off = 0, [], 0.0, 0.0, 0, False
        self.used = False
        self.log = []

    @property
    def declared(self):
        return self.inner.declared

    def net(self):
        return self.saved - self.cost

    def current_prior(self, view=None):
        probe = self.k % self.period == self.period - 1
        p = None if (self.off or probe) else self.inner.current_prior(view)
        self.used = p is not None
        return p

    def observe(self, execs, row_entries):
        if self.used:
            ref = sum(self.u) / len(self.u) if self.u else execs
            self.saved += ref - execs
            self.cost += self.c_row * row_entries
            self.n_prior += 1
            if self.n_prior >= self.warm and self.net() <= 0 and not self.off:
                self.off = True
                self.log.append(dict(task=self.k, event="prior_off", net=self.net()))
        else:
            self.u.append(execs)
        self.k += 1

    def update(self, prog, view):
        if self.off:
            return False
        inner = self.inner
        due = inner.since + 1 >= inner.g["refit"]
        if due and inner.glob is not None and self.net() <= 0:
            inner.since = -10**9                      # refit refused: savings do not exceed learning cost so far
            self.log.append(dict(task=self.k, event="refit_refused", net=self.net()))
        refit = inner.update(prog, view)
        if inner.since < 0:
            inner.since = 0
        if refit:
            self.cost += self.c_fit * sum(len(p) for p in inner.progs)
        return refit

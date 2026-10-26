"""Wave 36 noisy / changing-world track (NOT LOCKED). Interactive tasks with explicit observations, actions and rewards;
probabilistic predictions and empirical returns only (never uniqueness certificates).

SwitchGrid: a 5x5 grid, actions N/S/E/W, hidden goal among 4 candidate cells. Separately variable conditions:
  obs_noise : with this probability the observed position is a uniformly random neighbour (partial observability)
  slip      : with this probability the move goes in a uniformly random direction (stochastic transitions)
  hazard    : per-step probability that the goal switches to another candidate (unannounced; times hidden from agents)
Reward 1 when the agent's TRUE position is the goal; the agent is then respawned at a random cell.
Every agent outputs, before each step, its predicted probability that this step's move is rewarded (for the Brier score).

Agents (the same observation stream and action set; compute = OS retired instructions of the agent's own calls):
  reactive     : head for the observed position of the last reward (random walk before any reward)
  model-free   : tabular Q-learning on the observed position (eps 0.1, alpha 0.3, gamma 0.9)
  fixed-model  : exact Bayesian posterior over the 4 goals assuming NO change (stationary); greedy plan to the MAP goal
  N1 BOCPD     : the same symbolic goal model with Bayesian online change-point detection (Adams & MacKay 2007, arXiv:0710.3742)
                 over run lengths (constant hazard 1/100, truncated at 300); predictive goal distribution = run-length mixture
  N2 PETS-red. : REDUCED PETS variant (Chua et al. 2018, arXiv:1805.12114): an ensemble of 5 bootstrapped goal-belief models
                 with exponential forgetting (0.98), planned with the repo's RandomShootingMPC (horizon 10, 64 candidates; first runs returned termination p = 1, an integration bug, and horizon 4: both disclosed)
                 over a MeanEnsemble; deterministic grid dynamics model (slip not modelled); trajectory sampling, the CEM
                 optimiser and learned neural dynamics are MISSING."""
from __future__ import annotations

import math
import random

import numpy as np

N = 5
ACT = ((0, -1), (0, 1), (1, 0), (-1, 0))
GOALS = ((0, 0), (0, 4), (4, 0), (4, 4))


def clamp(p):
    return (min(N - 1, max(0, p[0])), min(N - 1, max(0, p[1])))


class SwitchGrid:
    def __init__(self, seed, obs_noise=0.0, slip=0.0, hazard=0.0):
        self.r = random.Random(f"w36-world:{seed}")
        self.obs_noise, self.slip, self.hazard = obs_noise, slip, hazard
        self.goal = self.r.randrange(4)
        self.pos = (self.r.randrange(N), self.r.randrange(N))
        self.changes = []

    def observe(self):
        if self.r.random() < self.obs_noise:
            d = ACT[self.r.randrange(4)]
            return clamp((self.pos[0] + d[0], self.pos[1] + d[1]))
        return self.pos

    def step(self, a, t):
        if self.r.random() < self.hazard:
            self.goal = self.r.choice([g for g in range(4) if g != self.goal])
            self.changes.append(t)
        d = ACT[self.r.randrange(4)] if self.r.random() < self.slip else ACT[a]
        self.pos = clamp((self.pos[0] + d[0], self.pos[1] + d[1]))
        rew = int(self.pos == GOALS[self.goal])
        if rew:
            self.pos = (self.r.randrange(N), self.r.randrange(N))
        return rew


def toward(p, g):
    if p[0] != g[0]:
        return 2 if g[0] > p[0] else 3
    if p[1] != g[1]:
        return 1 if g[1] > p[1] else 0
    return 0


def nxt(p, a):
    return clamp((p[0] + ACT[a][0], p[1] + ACT[a][1]))


class Reactive:
    def __init__(self, rng):
        self.rng, self.last, self.rate, self.n = rng, None, 0.0, 0

    def act(self, o):
        a = toward(o, self.last) if self.last and o != self.last else self.rng.randrange(4)
        return a, (self.rate if self.last else 0.04)

    def learn(self, o, a, rew, o2):
        self.n += 1
        self.rate += (rew - self.rate) / self.n
        if rew:
            self.last = nxt(o, a)


class ModelFree:
    def __init__(self, rng):
        self.rng, self.q = rng, {}

    def act(self, o):
        qs = [self.q.get((o, a), 0.0) for a in range(4)]
        a = self.rng.randrange(4) if self.rng.random() < 0.1 else int(np.argmax(qs))
        return a, max(0.0, min(1.0, max(qs)))

    def learn(self, o, a, rew, o2):
        best = max(self.q.get((o2, b), 0.0) for b in range(4)) if not rew else 0.0
        k = (o, a)
        self.q[k] = self.q.get(k, 0.0) + 0.3 * (rew + 0.9 * best - self.q.get(k, 0.0))


def _lik(rew, moved_to, g):
    """P(reward | goal g, believed landing cell): soft, to absorb observation noise and slips."""
    hit = moved_to == GOALS[g]
    return (0.85 if hit else 0.02) if rew else (0.15 if hit else 0.98)


class FixedModel:
    def __init__(self, rng):
        self.rng, self.b = rng, np.full(4, 0.25)

    def act(self, o):
        g = int(np.argmax(self.b))
        a = toward(o, GOALS[g]) if o != GOALS[g] else self.rng.randrange(4)
        land = nxt(o, a)
        return a, float(sum(self.b[k] * (0.85 if land == GOALS[k] else 0.02) for k in range(4)))

    def learn(self, o, a, rew, o2):
        land = nxt(o, a)
        self.b = self.b * np.array([_lik(rew, land, g) for g in range(4)])
        self.b /= self.b.sum()


class BOCPD(FixedModel):
    H, RMAX = 1 / 100, 300

    def __init__(self, rng):
        super().__init__(rng)
        self.runs = [(1.0, np.full(4, 0.25))]      # (run-length probability, goal posterior within that run)

    def _pred(self):
        b = sum(w * g for w, g in self.runs)
        return b / b.sum()

    def act(self, o):
        self.b = self._pred()
        return super().act(o)

    def learn(self, o, a, rew, o2):
        land = nxt(o, a)
        lik = np.array([_lik(rew, land, g) for g in range(4)])
        grown, cp = [], 0.0
        for w, g in self.runs:
            pred = float(g @ lik)
            post = g * lik
            post /= post.sum()
            grown.append([w * pred * (1 - self.H), post])
            cp += w * pred * self.H
        prior = np.full(4, 0.25)
        new = [[cp, prior * lik / (prior @ lik)]] + grown
        z = sum(w for w, _ in new)
        self.runs = [(w / z, g) for w, g in new[: self.RMAX]]


class _Member:
    """One ensemble member: a goal belief from a bootstrap-resampled reward history, with forgetting. StepModel for MPC:
    obs = position (x, y); deterministic move; step_reward reads the member belief."""

    def __init__(self, rng):
        self.rng, self.b = rng, np.full(4, 0.25)

    def update(self, rew, land):
        k = self.rng.choice((0, 1, 1, 2))                  # Poisson(1)-like bootstrap weight
        self.b = self.b ** 0.98
        for _ in range(k):
            self.b = self.b * np.array([_lik(rew, land, g) for g in range(4)])
        self.b /= self.b.sum()

    def step(self, obs, action):
        obs = np.asarray(obs, dtype=np.float32).reshape(-1, 2)
        act = np.asarray(action).reshape(-1).astype(int)
        d = np.array([ACT[a] for a in act], dtype=np.float32)
        return np.clip(obs + d, 0, N - 1), np.zeros(len(obs))     # 2nd output = TERMINATION probability (RandomShootingMPC)


class PETSReduced:
    def __init__(self, rng, seed):
        from nexus.world.planning import MeanEnsemble, RandomShootingMPC
        self.rng = rng
        self.members = [_Member(random.Random(f"w36-pets:{seed}:{i}")) for i in range(5)]
        ens = MeanEnsemble(self.members)

        def step_reward(s, a, nx):
            b = np.mean([m.b for m in self.members], axis=0)
            g = np.array(GOALS, dtype=np.float32)
            at = (np.abs(nx[:, None, :] - g[None, :, :]).sum(-1) < 0.5).astype(np.float64)
            return at @ b
        self.mpc = RandomShootingMPC(model=ens, n_actions=4, horizon=10, n_candidates=64, seed=int(seed) % 100000,
                                     enforce_time_budget=False, step_reward=step_reward)

    def act(self, o):
        a, _info = self.mpc.act(np.array(o, dtype=np.float32))
        b = np.mean([m.b for m in self.members], axis=0)
        land = nxt(o, int(a))
        return int(a), float(sum(b[k] * (0.85 if land == GOALS[k] else 0.02) for k in range(4)))

    def learn(self, o, a, rew, o2):
        for m in self.members:
            m.update(rew, nxt(o, a))


AGENTS = ("reactive", "model-free", "fixed-model", "N1-BOCPD", "N2-PETS-reduced")


def make(name, seed):
    rng = random.Random(f"w36-agent:{name}:{seed}")
    return {"reactive": Reactive, "model-free": ModelFree, "fixed-model": FixedModel, "N1-BOCPD": BOCPD}[name](rng) \
        if name != "N2-PETS-reduced" else PETSReduced(rng, __import__("zlib").crc32(str(seed).encode()) % 10**6)


def run(name, seed, cond, T=600, instr=None):
    env = SwitchGrid(seed, **cond)
    ag = make(name, seed)
    pid_instr = instr or (lambda: 0)
    total, brier, i0 = 0, 0.0, pid_instr()
    o = env.observe()
    hits = []
    for t in range(T):
        a, p = ag.act(o)
        rew = env.step(a, t)
        o2 = env.observe()
        ag.learn(o, a, rew, o2)
        total += rew; brier += (p - rew) ** 2; hits.append(rew)
        o = o2
    delays = []
    for c in env.changes:
        nxt_hit = next((t for t in range(c, T) if hits[t]), None)
        delays.append((nxt_hit - c) if nxt_hit is not None else T - c)
    return dict(ret=total, brier=brier / T, delay=(sum(delays) / len(delays)) if delays else None, n_changes=len(env.changes),
                instr=pid_instr() - i0)

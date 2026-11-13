"""Makes the pet less predictable: an energy level over the day, irregular timing and actions that avoid
repeating themselves."""

import math
import random
import time
from collections import deque

# energy by hour of the day: slow mornings, a lively late morning, an after-lunch dip, tired late evenings
CURVE = [
    0.45,
    0.4,
    0.35,
    0.35,
    0.4,
    0.5,
    0.65,
    0.8,
    0.95,
    1.1,
    1.15,
    1.1,
    0.95,
    0.85,
    0.9,
    1.0,
    1.05,
    1.0,
    0.95,
    0.9,
    0.8,
    0.7,
    0.6,
    0.5,
]

LIVELY = {"juggle", "yoyo", "paper_plane", "gaming", "bubblegum", "doodle"}
CALM = {"read", "coffee", "look_around", "bubbles", "yawn"}


class Mood:
    def __init__(self):
        self.recent = deque(maxlen=4)
        self.rested_until = 0.0

    def energy(self, active_s=0.0):
        """0.35 (tired) .. 1.3 (lively). Long stretches at the PC wear it out, a break refreshes it."""
        t = time.localtime()
        h = t.tm_hour + t.tm_min / 60
        a, b = CURVE[int(h) % 24], CURVE[(int(h) + 1) % 24]
        e = a + (b - a) * (h - int(h))
        e -= min(0.35, active_s / 3600 * 0.12)
        if time.time() < self.rested_until:
            e += 0.2
        return max(0.35, min(1.3, e))

    def rested(self):
        self.rested_until = time.time() + 20 * 60

    def wait(self, mean_s, lo_s, hi_s, energy=1.0):
        """Irregular waiting time: mostly around the mean, sometimes much shorter or longer."""
        mean = mean_s / max(0.35, energy)
        sigma = 0.55
        t = random.lognormvariate(math.log(mean) - sigma * sigma / 2, sigma)
        return max(lo_s, min(hi_s, t))

    def pick(self, options, energy=1.0, weights=None):
        """A random choice that avoids what was played lately and leans lively or calm with the energy."""
        ws = []
        for i, name in enumerate(options):
            w = weights[i] if weights else 1.0
            if name in self.recent:
                w *= 0.12 if self.recent[-1] == name else 0.35
            if name in LIVELY:
                w *= 0.5 + energy * 0.6
            elif name in CALM:
                w *= 1.6 - energy * 0.6
            ws.append(max(0.01, w))
        name = random.choices(options, ws)[0]
        self.recent.append(name)
        return name

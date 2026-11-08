"""Simulated tentacles for movement: four little chains of points that trail behind the body and settle when it
stops. The result is rounded to whole pixels so it keeps the pixel look."""
import math

SEGS = 4


class Tentacles:
    def __init__(self):
        self.reset()
        self.t = 0.0

    def reset(self):
        self.chains = [[(0.0, float(i)) for i in range(SEGS)] for _ in range(4)]

    def step(self, vx, vy, dt=0.016):
        """vx, vy: body speed in sprite pixels per step (clamped). Each tentacle is pulled down a little,
        dragged against the motion and swayed so the four never move in lockstep."""
        vx, vy = max(-3.0, min(3.0, vx)), max(-3.0, min(3.0, vy))
        self.t += dt
        for k, chain in enumerate(self.chains):
            new = [(0.0, 0.0)]
            for i in range(1, SEGS):
                x, y = chain[i]
                x += -vx * 0.35 * i / SEGS + math.sin(self.t * 2.2 + k * 1.3 + i * 0.7) * 0.18 * i
                y += -vy * 0.35 * i / SEGS + 0.6
                px, py = new[i - 1]
                dx, dy = x - px, y - py
                d = math.hypot(dx, dy) or 1.0
                new.append((px + dx / d, py + dy / d))
            self.chains[k] = new

    def ease(self, targets, rate=0.3):
        """Pulls every point toward the drawn tentacle shape; extra points fold onto its tip.
        Returns True once the pixels match the shape."""
        done = True
        for k, chain in enumerate(self.chains):
            goal = targets[k]
            new = []
            for i, (x, y) in enumerate(chain):
                gx, gy = goal[min(i, len(goal) - 1)]
                new.append((x + (gx - x) * rate, y + (gy - y) * rate))
            self.chains[k] = new
            if set(self.pixels()[k]) != set(goal):
                done = False
        return done

    def pixels(self):
        """Per tentacle the pixel offsets from its root, connected, as a hashable tuple."""
        out = []
        for chain in self.chains:
            pts = []
            for x, y in chain:
                p = (round(x), round(y))
                if pts and abs(p[0] - pts[-1][0]) > 1:
                    pts.append(((p[0] + pts[-1][0]) // 2, p[1]))
                if not pts or p != pts[-1]:
                    pts.append(p)
            out.append(tuple(pts))
        return tuple(out)

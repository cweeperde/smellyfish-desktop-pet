"""Sound effects, synthesised once into WAV files and played asynchronously."""
import math
import os
import random
import struct
import sys
import wave

from smellyfish.paths import HOME_DIR

RATE = 22050
DIR = os.path.join(HOME_DIR, "sounds")
VERSION = 3


def _square(freq, t):
    return 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0


def _sine(freq, t):
    return math.sin(2 * math.pi * freq * t)


def _tri(freq, t):
    p = (freq * t) % 1.0
    return 4 * abs(p - 0.5) - 1


def _tone(notes, wave_fn=_square, decay=6.0):
    """notes: list of (freq or (f0, f1) sweep, seconds)."""
    out = []
    for freq, dur in notes:
        n = int(RATE * dur)
        phase = 0.0
        for i in range(n):
            t = i / RATE
            f = freq if not isinstance(freq, tuple) else freq[0] + (freq[1] - freq[0]) * i / n
            phase += (f or 0) / RATE
            env = math.exp(-decay * t) * min(1.0, i / 60)
            out.append(wave_fn(1.0, phase) * env if f else 0.0)
    return out


def _bell(notes, partials=((1, 1.0), (2.01, 0.35), (3.02, 0.15)), decay=4.5, gap=0.0):
    """Soft chime: overlapping sine notes with a few partials."""
    total = int(RATE * (sum(d for _f, d in notes) + 0.6))
    out = [0.0] * total
    start = 0
    for f, dur in notes:
        for i in range(total - start):
            t = i / RATE
            env = math.exp(-decay * t) * min(1.0, i / 40)
            if i > 40 and env < 0.002:
                break
            out[start + i] += env * sum(a * math.sin(2 * math.pi * f * m * t) for m, a in partials) * 0.6
        start += int(RATE * (dur + gap))
    return out


def _noise(dur, decay=30.0, smooth=0.0, env=None, seed=7):
    rnd = random.Random(seed)
    n = int(RATE * dur)
    out, last = [], 0.0
    for i in range(n):
        v = rnd.uniform(-1, 1)
        last = last * smooth + v * (1 - smooth)
        e = env(i / n) if env else math.exp(-decay * i / RATE)
        out.append(last * e * (1 + smooth * 2))
    return out


def _mix(*parts):
    n = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]


def _seq(*parts):
    out = []
    for p in parts:
        out += p
    return out


def _silence(dur):
    return [0.0] * int(RATE * dur)


def _giggle():
    out = []
    for k, f in enumerate((900, 1000, 950, 1100, 1000)):
        out += _tone([((f, f * 1.25), 0.06)], wave_fn=_sine, decay=12) + _silence(0.035)
    return out


def _purr():
    n = int(RATE * 0.9)
    rnd = random.Random(3)
    out, last = [], 0.0
    for i in range(n):
        t = i / RATE
        last = last * 0.92 + rnd.uniform(-1, 1) * 0.08
        am = 0.5 + 0.5 * math.sin(2 * math.pi * 24 * t)
        env = min(1.0, t * 6) * min(1.0, (0.9 - t) * 5)
        out.append((last * 3 + 0.3 * math.sin(2 * math.pi * 70 * t)) * am * env)
    return out


def _droplets():
    out = _silence(0.5)
    for k, (start, f) in enumerate(((0.0, 1400), (0.12, 1700), (0.22, 1250), (0.33, 1900))):
        d = _tone([((f, f * 1.6), 0.07)], wave_fn=_sine, decay=30)
        s = int(RATE * start)
        for i, v in enumerate(d):
            out[s + i] += v * 0.7
    return _mix(out, _noise(0.45, smooth=0.6, env=lambda x: (1 - x) ** 2 * 0.35, seed=11))


def _munch():
    return _seq(*[_noise(0.06, smooth=0.5, env=lambda x: (1 - x) ** 3, seed=s) + _silence(0.07) for s in (1, 2, 3)])


SOUNDS = {
    # notifications (own volume)
    "done": lambda: _bell([(784, 0.11), (988, 0.11), (1319, 0.3)], decay=3.5),
    "question": lambda: _bell([(1047, 0.13), (1319, 0.3)], decay=5),
    "alarm": lambda: _bell([(1319, 0.14), (1568, 0.14), (1319, 0.14), (1568, 0.3)], decay=4),
    "message": lambda: _bell([(880, 0.08), (1175, 0.25)], decay=6),
    "warn": lambda: _bell([(660, 0.16), (523, 0.35)], partials=((1, 1.0), (3, 0.2)), decay=4),
    # fun sounds
    "jump": lambda: _tone([((300, 700), 0.09)], wave_fn=_sine, decay=8),
    "land": lambda: _noise(0.07, smooth=0.5),
    "poke": lambda: _tone([((900, 1300), 0.05)], wave_fn=_sine, decay=20),
    "angry": lambda: _tone([((180, 120), 0.25)], decay=3),
    "giggle": _giggle,
    "purr": _purr,
    "pop": lambda: _tone([((500, 1100), 0.05)], wave_fn=_sine, decay=25),
    "boing": lambda: [v * 0.8 for v in _tone([((220, 520), 0.35)], wave_fn=lambda f, p: math.sin(
        2 * math.pi * p + 2 * math.sin(2 * math.pi * p * 0.03)), decay=6)],
    "zap": lambda: _seq(_noise(0.05, decay=30, seed=21), _tone([((1800, 300), 0.08)], wave_fn=_tri, decay=6),
                        _noise(0.07, decay=20, seed=22), _tone([((1500, 250), 0.1)], wave_fn=_tri, decay=5),
                        _silence(0.1), _bell([(784, 0.08), (1047, 0.25)], decay=6)),
    "doorbell": lambda: _bell([(784, 0.2), (622, 0.45)], partials=((1, 1.0), (2, 0.35)), decay=4),
    "whoosh": lambda: _noise(0.3, smooth=0.85, env=lambda x: math.sin(math.pi * x) ** 2),
    "sweep": lambda: _seq(_noise(0.18, smooth=0.7, env=lambda x: math.sin(math.pi * x), seed=4), _silence(0.05),
                          _noise(0.18, smooth=0.7, env=lambda x: math.sin(math.pi * x), seed=5), _silence(0.05),
                          _bell([(1568, 0.06), (2093, 0.2)], decay=7)),
    "splash": _droplets,
    "munch": _munch,
    "shutter": lambda: _seq(_noise(0.025, decay=120, seed=8), _silence(0.06), _noise(0.04, decay=80, seed=9)),
    "fanfare": lambda: _tone([(523, 0.1), (659, 0.1), (784, 0.1), (1047, 0.32)], wave_fn=_tri, decay=2.5),
    "sneeze": lambda: _seq(_tone([((300, 700), 0.35)], wave_fn=_sine, decay=1), _noise(0.25, decay=10, seed=12)),
    "yawn": lambda: _tone([((520, 300), 0.6)], wave_fn=lambda f, p: math.sin(2 * math.pi * p) * 0.8, decay=1.5),
    "hello": lambda: _tone([((600, 900), 0.08), (0, 0.04), ((700, 1100), 0.1)], wave_fn=_sine, decay=6),
    "stink": lambda: _tone([((140, 110), 0.3)], wave_fn=_tri, decay=3),
    "sad": lambda: _tone([((500, 380), 0.3), ((420, 300), 0.4)], wave_fn=_sine, decay=2),
    "happy": lambda: _tone([((700, 900), 0.07), ((900, 1200), 0.1)], wave_fn=_sine, decay=7),
}
for _i, _f in enumerate((520, 600, 690, 780, 880)):
    SOUNDS[f"blip{_i}"] = (lambda f: lambda: _tone([((f, f * 1.08), 0.05)], wave_fn=_sine, decay=18))(_f)

NOTIFY = {"done", "question", "alarm", "message", "warn"}
MUTED = False


def set_muted(on):
    global MUTED
    MUTED = bool(on)


def _write(name, volume):
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f"{name}_{volume}_v{VERSION}.wav")
    if not os.path.exists(path):
        samples = SOUNDS[name]()
        peak = max(1e-6, max(abs(s) for s in samples))
        amp = 0.5 * (volume / 100) ** 1.5 / max(1.0, peak)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * amp)) * 32767)) for s in samples))
    return path


def play(name, volume=60):
    if MUTED or sys.platform != "win32" or name not in SOUNDS or volume <= 0:
        return
    try:
        import winsound
        winsound.PlaySound(_write(name, int(volume)),
                           winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass

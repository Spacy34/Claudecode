"""Bruitages et boucle musicale 100 % synthétisés (Python pur) : originaux, libres de droits, reproductibles.

Qualité volontairement « cartoon ». Ils remplacent toute banque de sons à licence incertaine ; une banque
CC0 vérifiée peut être ajoutée dans assets/sfx/ (le nom de fichier = nom du bruitage).
"""
import array
import math
import random
import wave
from pathlib import Path

SR = 48000


def _write(path, samples):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = max(1e-9, max(abs(s) for s in samples))
    k = 0.89 / peak
    data = array.array("h", (int(max(-1, min(1, s * k)) * 32767) for s in samples))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def _env(i, n, a=0.005, r=0.3):
    t = i / SR
    T = n / SR
    if t < a:
        return t / a
    return max(0.0, 1 - (t - a) / max(1e-6, (T - a))) ** (1 / max(r, 1e-3))


def _noise_filtered(n, rng, cutoff_fn):
    out, y = [], 0.0
    for i in range(n):
        c = cutoff_fn(i / n)
        alpha = min(1.0, 2 * math.pi * c / SR)
        y += alpha * (rng.uniform(-1, 1) - y)
        out.append(y)
    return out


def whoosh(rng):
    n = int(SR * 0.45)
    s = _noise_filtered(n, rng, lambda u: 300 + 5000 * math.sin(math.pi * u))
    return [v * math.sin(math.pi * i / n) ** 2 for i, v in enumerate(s)]


def boing(rng):
    n = int(SR * 0.6)
    out, ph = [], 0.0
    for i in range(n):
        t = i / SR
        f = 180 + 120 * math.exp(-t * 6) * math.cos(2 * math.pi * 9 * t)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 4))
    return out


def pop(rng):
    n = int(SR * 0.12)
    out, ph = [], 0.0
    for i in range(n):
        t = i / SR
        ph += 2 * math.pi * (900 * math.exp(-t * 40) + 200) / SR
        out.append(math.sin(ph) * math.exp(-t * 35))
    return out


def thud(rng):
    n = int(SR * 0.35)
    out, ph = [], 0.0
    nz = _noise_filtered(n, rng, lambda u: 400)
    for i in range(n):
        t = i / SR
        ph += 2 * math.pi * (60 + 80 * math.exp(-t * 30)) / SR
        out.append((math.sin(ph) + 0.4 * nz[i]) * math.exp(-t * 14))
    return out


def ding(rng):
    n = int(SR * 1.0)
    return [sum(a * math.sin(2 * math.pi * f * i / SR) for f, a in ((1320, 1), (2640, 0.4), (3960, 0.2))) * math.exp(-i / SR * 4) for i in range(n)]


def slide_whistle(rng):
    n = int(SR * 0.7)
    out, ph = [], 0.0
    for i in range(n):
        u = i / n
        ph += 2 * math.pi * (500 + 1300 * u) / SR
        out.append(math.sin(ph) * math.sin(math.pi * u) * (1 + 0.1 * math.sin(2 * math.pi * 7 * i / SR)))
    return out


def record_scratch(rng):
    n = int(SR * 0.4)
    nz = _noise_filtered(n, rng, lambda u: 1500 + 2500 * abs(math.sin(u * 14)))
    return [v * (0.5 + 0.5 * math.sin(2 * math.pi * 11 * i / SR)) * _env(i, n, 0.01, 0.8) for i, v in enumerate(nz)]


def explosion(rng):
    n = int(SR * 1.4)
    nz = _noise_filtered(n, rng, lambda u: 2500 * math.exp(-u * 5) + 120)
    out, ph = [], 0.0
    for i, v in enumerate(nz):
        t = i / SR
        ph += 2 * math.pi * (45 + 30 * math.exp(-t * 8)) / SR
        out.append((v * 1.6 + 0.8 * math.sin(ph)) * math.exp(-t * 2.6))
    return out


def crash(rng):
    n = int(SR * 0.9)
    nz = _noise_filtered(n, rng, lambda u: 6000)
    return [v * math.exp(-i / SR * 5) * (1 + 0.5 * math.sin(2 * math.pi * 330 * i / SR)) for i, v in enumerate(nz)]


def sparkle(rng):
    n = int(SR * 0.8)
    out = [0.0] * n
    for k in range(7):
        st = int(k * n / 9)
        f = rng.choice((2093, 2349, 2637, 3136, 3520))
        for i in range(st, min(n, st + int(SR * 0.25))):
            t = (i - st) / SR
            out[i] += math.sin(2 * math.pi * f * t) * math.exp(-t * 14)
    return out


def splat(rng):
    n = int(SR * 0.3)
    nz = _noise_filtered(n, rng, lambda u: 900 - 700 * u)
    return [v * math.exp(-i / SR * 12) for i, v in enumerate(nz)]


LIBRARY = {"whoosh": whoosh, "boing": boing, "pop": pop, "thud": thud, "ding": ding, "slide_whistle": slide_whistle,
           "record_scratch": record_scratch, "explosion": explosion, "crash": crash, "sparkle": sparkle, "splat": splat}

TRANSITION_SFX = {"whip": "whoosh", "smash_cut": "thud", "flash_white": "pop"}


def ensure_library(sfx_dir):
    sfx_dir = Path(sfx_dir)
    made = []
    for name, fn in LIBRARY.items():
        p = sfx_dir / f"{name}.wav"
        if not p.exists():
            _write(p, fn(random.Random(name)))
            made.append(name)
    return made


def music_loop(path, bpm=118, bars=8, seed=3):
    """Boucle 'goofy bounce' : basse sautillante + pizzicati + caisse claire légère. Originale (synthèse)."""
    path = Path(path)
    if path.exists():
        return path
    rng = random.Random(seed)
    beat = 60.0 / bpm
    n = int(SR * beat * 4 * bars)
    out = [0.0] * n
    scale = [0, 2, 4, 5, 7, 9, 11, 12]
    root = 110.0
    prog = [0, 5, 3, 4, 0, 5, 4, 0]
    for bar in range(bars):
        r = prog[bar % len(prog)]
        for b in range(8):   # croches
            t0 = (bar * 4 + b * 0.5) * beat
            i0 = int(t0 * SR)
            fb = root * 2 ** (scale[r % 8] / 12.0) * (1 if b % 2 == 0 else 2)
            for i in range(i0, min(n, i0 + int(SR * beat * 0.45))):
                t = (i - i0) / SR
                out[i] += 0.5 * math.sin(2 * math.pi * fb * t) * math.exp(-t * 7)
            if rng.random() < 0.6:
                fp = root * 4 * 2 ** (scale[(r + rng.choice((0, 2, 4))) % 8] / 12.0)
                for i in range(i0, min(n, i0 + int(SR * 0.18))):
                    t = (i - i0) / SR
                    out[i] += 0.22 * (math.sin(2 * math.pi * fp * t) + 0.3 * math.sin(4 * math.pi * fp * t)) * math.exp(-t * 18)
            if b in (2, 6):
                for i in range(i0, min(n, i0 + int(SR * 0.08))):
                    t = (i - i0) / SR
                    out[i] += 0.12 * rng.uniform(-1, 1) * math.exp(-t * 40)
    _write(path, out)
    return path

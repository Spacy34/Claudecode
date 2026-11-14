"""Calage d'une voix COMPLÈTE fournie par l'utilisateur (ElevenLabs, enregistrement…) sur les répliques du script.

Sans dépendance : FFmpeg détecte les pauses, puis une programmation dynamique choisit, parmi elles, les N-1
coupures entre répliques qui collent le mieux aux durées attendues (proportionnelles aux syllables), en
préférant les pauses longues (une fin de réplique respire plus qu'une virgule). Si le fichier contient moins de
pauses que de répliques, des coupures proportionnelles complètent (signalées « à vérifier »).
Le minutage des mots à l'intérieur d'une réplique reste proportionnel aux syllabes (comme pour la synthèse).
"""
import math
import re

from .util import run

NOISE_DB = -38
MIN_SIL = 0.12      # pause minimale détectée (s)
MIN_SEG = 0.30      # durée minimale d'une réplique (s)


def detect_silences(wav, noise_db=NOISE_DB, min_d=MIN_SIL):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"])
    out = r.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[0-9.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", out)]
    m = re.search(r"Duration:\s*(\d+):(\d+):([0-9.]+)", out)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    sil = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else dur
        sil.append((max(0.0, s), e))
    return sil, dur


def _syll(text):
    from .audio import syllables
    n = sum(syllables(w) for w in text.split())
    inner_ends = len(re.findall(r"[.!?…]+(?=\s+\S)", text))   # fins de phrase à l'intérieur de la réplique
    return max(1, n) + 0.6 * len(re.findall(r"[,;:]", text)) + 1.5 * inner_ends   # les pauses internes « coûtent » du temps


def align(texts, silences, duration):
    """-> (bornes [(début, fin)] par réplique, rapport). Temps en secondes dans le fichier."""
    n = len(texts)
    sp_start, sp_end = 0.0, duration
    inner = []
    for s, e in silences:
        if s <= 0.05:
            sp_start = max(sp_start, e)
        elif e >= duration - 0.05:
            sp_end = min(sp_end, s)
        else:
            inner.append((s, e))
    inner = [(s, e) for s, e in inner if sp_start + 0.05 < s and e < sp_end - 0.05]
    T = max(0.1, sp_end - sp_start)
    w = [_syll(t) for t in texts]
    tot = sum(w)
    cum, acc = [], 0.0
    for x in w[:-1]:
        acc += x
        cum.append(sp_start + T * acc / tot)
    if n == 1:
        return [(sp_start, sp_end)], {"speech": [sp_start, sp_end], "lines": [{"start": sp_start, "end": sp_end, "flag": ""}], "virtual_cuts": 0}
    cands = [{"mid": (s + e) / 2, "s": s, "e": e, "d": e - s, "v": False} for s, e in inner]
    # pas assez de pauses : coupures proportionnelles en renfort (pénalisées, signalées)
    if len(cands) < n - 1:
        for E in cum:
            if all(abs(c["mid"] - E) > 0.4 for c in cands):
                cands.append({"mid": E, "s": E, "e": E, "d": 0.0, "v": True})
        cands.sort(key=lambda c: c["mid"])
    m = len(cands)
    if m < n - 1:   # cas extrême : tout proportionnel
        bounds = [(sp_start if i == 0 else cum[i - 1], sp_end if i == n - 1 else cum[i]) for i in range(n)]
        return bounds, {"speech": [sp_start, sp_end], "lines": [{"start": a, "end": b, "flag": "proportionnel"} for a, b in bounds], "virtual_cuts": n - 1}
    # débit réel : temps de parole hors pauses inter-répliques (≈ les n-1 plus longues pauses) / poids total
    longest = sorted((c["d"] for c in cands), reverse=True)[:n - 1]
    rate = max(0.05, (T - sum(longest)) / tot)
    exp = [rate * x for x in w]
    pos_sigma = max(1.5, 0.15 * T)

    def seg_cost(k, a, b):
        d = b - a
        if d < MIN_SEG:
            return float("inf")
        return (math.log(d / exp[k]) / 0.3) ** 2

    def cut_cost(k, j):
        c = cands[j]
        return ((c["mid"] - cum[k]) / pos_sigma) ** 2 - 2.0 * math.log(1 + c["d"] / 0.15) + (4.0 if c["v"] else 0.0)

    INF = float("inf")
    # dp[k][j] : coût minimal si la coupure k (fin de la réplique k) est la pause j
    dp = [[INF] * m for _ in range(n - 1)]
    back = [[-1] * m for _ in range(n - 1)]
    for j in range(m):
        dp[0][j] = seg_cost(0, sp_start, cands[j]["s"]) + cut_cost(0, j)
    for k in range(1, n - 1):
        for j in range(m):
            cc = cut_cost(k, j)
            best, bi = INF, -1
            for i in range(j):
                if dp[k - 1][i] == INF:
                    continue
                v = dp[k - 1][i] + seg_cost(k, cands[i]["e"], cands[j]["s"])
                if v < best:
                    best, bi = v, i
            if bi >= 0:
                dp[k][j] = best + cc
                back[k][j] = bi
    finals = [(dp[n - 2][j] + seg_cost(n - 1, cands[j]["e"], sp_end), j) for j in range(m) if dp[n - 2][j] < INF]
    finals = [f for f in finals if f[0] < INF]
    if not finals:
        bounds = [(sp_start if i == 0 else cum[i - 1], sp_end if i == n - 1 else cum[i]) for i in range(n)]
        return bounds, {"speech": [sp_start, sp_end], "lines": [{"start": a, "end": b, "flag": "proportionnel"} for a, b in bounds], "virtual_cuts": n - 1}
    j = min(finals)[1]
    chosen = [0] * (n - 1)
    for k in range(n - 2, -1, -1):
        chosen[k] = j
        j = back[k][j]
    cuts = [cands[j] for j in chosen]
    bounds = []
    for i in range(n):
        a = sp_start if i == 0 else cuts[i - 1]["e"]
        b = sp_end if i == n - 1 else cuts[i]["s"]
        bounds.append((a, max(a + 0.05, b)))
    lines = []
    for i, (a, b) in enumerate(bounds):
        e_ = exp[i]
        ratio = (b - a) / e_ if e_ else 1.0
        flag = ""
        if (i > 0 and cuts[i - 1]["v"]) or (i < n - 1 and cuts[i]["v"]):
            flag = "coupure estimée (pas de pause nette)"
        elif ratio < 0.45 or ratio > 2.2:
            flag = "durée inhabituelle : vérifier le découpage"
        lines.append({"start": round(a, 3), "end": round(b, 3), "expected_s": round(e_, 2), "ratio": round(ratio, 2), "flag": flag})
    return bounds, {"speech": [round(sp_start, 3), round(sp_end, 3)], "lines": lines, "virtual_cuts": sum(c["v"] for c in cuts),
                    "pauses_detected": len(inner)}

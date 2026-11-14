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


def word_syll(w):
    """Syllabes PRONONCÉES : chiffres en lettres (« 50 » = cinquante), sigles épelés (« CDI » = 3)."""
    from .audio import syllables
    from .whisper_align import _spell
    core = re.sub(r"[^\w]", "", w)
    if re.fullmatch(r"[0-9][0-9 ,.]*", core or "x") or re.search(r"[0-9]", w):
        return sum(syllables(x) for x in _spell(w))
    if len(core) >= 2 and core.isupper() and core.isalpha():
        return len(core)
    return syllables(w)


def _syll(text):
    n = sum(word_syll(w) for w in text.split())
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


# ------------------------------------------------------------------ découpage par morceaux de phrase (v2)
PUNCT_STRENGTH = {"line": 7.0, "sentence": 4.0, "quote": 1.6, "comma": 1.0}


def phrases(texts):
    """Découpe chaque réplique en morceaux à la ponctuation. -> [(ligne, indices de mots, force de la coupure finale)]."""
    units = []
    for li, t in enumerate(texts):
        ws = t.split()
        cur = []
        for wi, w in enumerate(ws):
            if w in ("«", "»", "—", "-"):
                continue
            if w.startswith("«") and cur:
                units.append([li, cur, "quote"])
                cur = []
            cur.append(wi)
            last = wi == len(ws) - 1 or all(x in ("«", "»", "—") for x in ws[wi + 1:])
            if last:
                break
            if re.search(r"[.!?…]+[»\"]?$", w):
                units.append([li, cur, "sentence"])
                cur = []
            elif re.search(r"[,;:]$", w) or w.endswith("»"):
                units.append([li, cur, "comma" if not w.endswith("»") else "quote"])
                cur = []
        if cur:
            units.append([li, cur, "line"])
        elif units and units[-1][0] == li:
            units[-1][2] = "line"
    return [tuple(u) for u in units]


def align_phrases(texts, silences, duration):
    """Comme align(), mais sur des MORCEAUX DE PHRASE : chaque fin de réplique ou de phrase doit tomber sur une vraie
    pause (sinon forte pénalité), une virgule peut ne pas en avoir. Plus de contraintes = découpage plus sûr, et
    mots mieux placés à l'intérieur des répliques. -> (bornes des répliques, bornes des morceaux, rapport)."""
    units = phrases(texts)
    words = [t.split() for t in texts]
    n = len(units)
    sp_start, sp_end = 0.0, duration
    inner = []
    for s_, e_ in silences:
        if s_ <= 0.05:
            sp_start = max(sp_start, e_)
        elif e_ >= duration - 0.05:
            sp_end = min(sp_end, s_)
        else:
            inner.append((s_, e_))
    inner = [(s_, e_) for s_, e_ in inner if sp_start + 0.05 < s_ and e_ < sp_end - 0.05]
    T = max(0.1, sp_end - sp_start)
    w = [max(1.0, sum(word_syll(words[li][wi]) for wi in idx)) for li, idx, _ in units]
    tot = sum(w)
    if n == 1:
        bounds_u = [(sp_start, sp_end)]
    else:
        reals = [{"mid": (a + b) / 2, "s": a, "e": b, "d": b - a, "v": False} for a, b in inner]
        longest = sorted((c["d"] for c in reals), reverse=True)[:max(0, sum(1 for u in units[:-1] if u[2] in ("line", "sentence")))]
        rate = max(0.05, (T - sum(longest)) / tot)
        exp = [rate * x for x in w]
        # coupures « sans pause » possibles partout, positionnées au prorata (pénalisées selon la ponctuation)
        acc, virt = 0.0, []
        for x in w[:-1]:
            acc += x
            E = sp_start + T * acc / tot
            virt.append({"mid": E, "s": E, "e": E, "d": 0.0, "v": True})
        cands = sorted(reals + virt, key=lambda c: c["mid"])
        m = len(cands)
        INF = float("inf")

        def seg_cost(k, a, b):
            d = b - a
            if d < 0.12:
                return INF
            return (math.log(d / exp[k]) / 0.32) ** 2

        def cut_cost(k, j):
            c = cands[j]
            if c["v"]:
                return PUNCT_STRENGTH[units[k][2]]
            bonus = 2.0 * math.log(1 + c["d"] / 0.15)
            if units[k][2] == "comma":
                bonus *= 0.6
            return -bonus

        dp = [[INF] * m for _ in range(n - 1)]
        back = [[-1] * m for _ in range(n - 1)]
        for j in range(m):
            dp[0][j] = seg_cost(0, sp_start, cands[j]["s"]) + cut_cost(0, j)
        for k in range(1, n - 1):
            for j in range(m):
                best, bi = INF, -1
                for i in range(j):
                    if dp[k - 1][i] == INF:
                        continue
                    v = dp[k - 1][i] + seg_cost(k, cands[i]["e"], cands[j]["s"])
                    if v < best:
                        best, bi = v, i
                if bi >= 0:
                    dp[k][j] = best + cut_cost(k, j)
                    back[k][j] = bi
        finals = [(dp[n - 2][j] + seg_cost(n - 1, cands[j]["e"], sp_end), j) for j in range(m) if dp[n - 2][j] < INF]
        finals = [f for f in finals if f[0] < INF]
        if not finals:
            b_, rep = align(texts, silences, duration)
            return b_, None, rep
        j = min(finals)[1]
        chosen = [0] * (n - 1)
        for k in range(n - 2, -1, -1):
            chosen[k] = j
            j = back[k][j]
        cuts = [cands[j] for j in chosen]
        bounds_u = [(sp_start if k == 0 else cuts[k - 1]["e"], sp_end if k == n - 1 else cuts[k]["s"]) for k in range(n)]
    # bornes des répliques = premier / dernier morceau de chaque réplique
    bounds = []
    for li in range(len(texts)):
        us = [k for k, u in enumerate(units) if u[0] == li]
        bounds.append((bounds_u[us[0]][0], bounds_u[us[-1]][1]) if us else (sp_start, sp_start + 0.1))
    lines = []
    for li, (a, b) in enumerate(bounds):
        ws_ = sum(word_syll(x) for x in words[li])
        rate_l = ws_ / max(0.05, b - a)
        flag = "débit inhabituel : vérifier le découpage" if (rate_l > 7.5 or rate_l < 2.6) else ""
        lines.append({"start": round(a, 3), "end": round(b, 3), "syll_per_s": round(rate_l, 1), "flag": flag})
    rep = {"speech": [round(sp_start, 3), round(sp_end, 3)], "lines": lines, "method": "phrases",
           "virtual_cuts": 0, "pauses_detected": len(inner), "units": len(units)}
    return bounds, (units, bounds_u), rep


def word_times_from_phrases(texts, units, bounds_u):
    """Temps des mots : répartis au prorata des syllabes À L'INTÉRIEUR de chaque morceau de phrase."""
    words = [t.split() for t in texts]
    out = [[None] * len(ws) for ws in words]
    for (li, idx, _), (a, b) in zip(units, bounds_u):
        sy = [max(1, word_syll(words[li][wi])) for wi in idx]
        tot, acc = float(sum(sy)), 0.0
        for wi, x in zip(idx, sy):
            out[li][wi] = (a + (b - a) * acc / tot, a + (b - a) * (acc + x) / tot)
            acc += x
    for li, ws in enumerate(out):   # guillemets isolés et mots ignorés : collés au voisin
        for wi in range(len(ws)):
            if ws[wi] is None:
                ref = next((ws[k] for k in range(wi + 1, len(ws)) if ws[k]), None) or next((ws[k] for k in range(wi - 1, -1, -1) if ws[k]), None)
                ws[wi] = (ref[0], ref[0] + 0.01) if ref else (0.0, 0.01)
    return out


def best(texts, silences, duration):
    """Découpage de secours (sans Whisper) : calcule le découpage par répliques et par morceaux de phrase, et garde
    celui dont les fins de réplique tombent sur les pauses les plus nettes avec le débit le plus régulier.
    -> (bornes, mots [(début, fin)] par réplique ou None, rapport)."""
    import statistics

    def score(bounds):
        rates = [math.log(max(1.0, sum(word_syll(w) for w in t.split())) / max(0.05, b - a)) for t, (a, b) in zip(texts, bounds)]
        gaps = sum(math.log(1 + max(0.0, c - b) / 0.15) for (_, b), (c, _) in zip(bounds, bounds[1:]))
        return gaps - 6.0 * (statistics.pstdev(rates) if len(rates) > 1 else 0.0)
    b1, rep1 = align(texts, silences, duration)
    b2, extra, rep2 = align_phrases(texts, silences, duration)
    if extra is not None and score(b2) > score(b1) + 1e-6:
        units, bu = extra
        rep2["chosen"] = "morceaux de phrase"
        return b2, word_times_from_phrases(texts, units, bu), rep2
    rep1["chosen"] = "répliques"
    return b1, None, rep1

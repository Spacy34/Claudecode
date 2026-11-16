"""Formes de bouche par son (visèmes) à partir des mots EXACTS et de leurs temps (Whisper / alignement).

Déterministe et sans dépendance : une lecture graphème → son simplifiée du français, suffisante pour une bouche
cartoon. Cinq formes, lisibles même petites à l'écran :
  A  bouche ouverte (a, an, en)            E  large et peu ouverte (é, è, i, in, ai)
  O  ronde (o, au, eau, on, eu)            U  petite et projetée (ou, u, oi→U puis A)
  M  lèvres fermées pincées (m, b, p)      F  dents sur la lèvre (f, v)
Le moteur affiche ces formes ; entre deux mots séparés par une pause, la bouche revient à l'expression.
"""
import re

# groupes reconnus du plus long au plus court : (graphème, suite de visèmes)
GROUPS = [
    ("eaux", "O"), ("eau", "O"), ("ain", "E"), ("ein", "E"), ("oin", "UE"), ("ien", "EE"),
    ("ou", "U"), ("où", "U"), ("oû", "U"), ("oi", "UA"), ("oy", "UA"), ("au", "O"), ("ai", "E"), ("ei", "E"),
    ("eu", "O"), ("œu", "O"), ("œ", "O"), ("on", "O"), ("om", "O"), ("an", "A"), ("am", "A"), ("en", "A"),
    ("em", "A"), ("in", "E"), ("im", "E"), ("un", "E"), ("ym", "E"), ("yn", "E"),
    ("ph", "F"), ("qu", ""), ("gn", ""), ("ch", "U"),
]
SINGLE = {"a": "A", "à": "A", "â": "A", "e": "E", "é": "E", "è": "E", "ê": "E", "ë": "E", "i": "E", "î": "E",
          "ï": "E", "y": "E", "o": "O", "ô": "O", "u": "U", "û": "U", "ù": "U", "ü": "U",
          "m": "M", "b": "M", "p": "M", "f": "F", "v": "F"}
VOWELS = set("AEOU")
SHAPES = ("A", "E", "O", "U", "M", "F")


def _norm(word):
    w = word.lower().replace("’", "'")
    w = re.sub(r"[^a-zàâäéèêëîïôöùûüçœ'-]", "", w)
    return w


def phonemes(word):
    """'bonjour' -> ['M', 'O', 'U'] (une entrée par son visible). Mots sans lettres (chiffres déjà épelés en amont)."""
    w = _norm(word)
    if not w:
        return []
    out = []
    for part in re.split(r"['-]", w):
        if not part:
            continue
        # e muet final / terminaisons muettes : « une », « elles », « parlent »
        m = re.search(r"(es|e)$", part)
        stop = m.start() if m and any(c in "aeiouyéèêàâôûî" for c in part[:m.start()]) else len(part)   # e muet final
        i = 0
        while i < stop:
            for g, v in GROUPS:
                if part.startswith(g, i):
                    nxt = part[i + len(g):i + len(g) + 1]
                    # « an », « on », « in » ne sont nasals que devant consonne ou en fin de mot (pas « ami », « bonne »)
                    if len(g) == 2 and g[1] in "nm" and g not in ("gn",) and nxt and (nxt in "aeiouyéèêàâôûînm"):
                        continue
                    out += list(v)
                    i += len(g)
                    break
            else:
                v = SINGLE.get(part[i], "")
                if v:
                    out.append(v)
                i += 1
    # consonnes identiques consécutives (« pomme » -> M) et doublons inutiles
    dedup = []
    for p in out:
        if not dedup or dedup[-1] != p:
            dedup.append(p)
    return dedup


def word_visemes(word, t0, t1, fps, min_frames=2):
    """-> [(temps_s, forme)] pour un mot prononcé entre t0 et t1. Si le débit est trop rapide pour tout montrer,
    les consonnes disparaissent d'abord, puis une voyelle sur deux (une bouche qui tremble est pire qu'une approximation)."""
    ph = phonemes(word)
    if not ph:
        return [(t0, "A")] if t1 - t0 > 2.0 / fps else []
    dur = max(t1 - t0, 1.0 / fps)
    slots = max(1, int(dur * fps / min_frames))
    if len(ph) > slots:
        ph = [p for p in ph if p in VOWELS] or ph[:1]
    while len(ph) > slots and len(ph) > 1:
        ph = ph[::2]
    # les consonnes (M, F) sont brèves : poids 0,6 ; les voyelles portent la durée
    w = [0.6 if p not in VOWELS else 1.0 for p in ph]
    tot = sum(w)
    out, t = [], t0
    for p, k in zip(ph, w):
        out.append((round(t, 4), p))
        t += dur * k / tot
    return out


def for_words(words, fps):
    """words : [{text, start_s, end_s}] -> [(temps_s, forme | 'rest')]. 'rest' = retour à l'expression (pause)."""
    out = []
    for i, w in enumerate(words):
        out += word_visemes(w["text"], w["start_s"], w["end_s"], fps)
        nxt = words[i + 1]["start_s"] if i + 1 < len(words) else None
        if nxt is None or nxt - w["end_s"] > 0.12:
            out.append((round(w["end_s"], 4), "rest"))
    return out

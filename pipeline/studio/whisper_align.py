"""Synchro EXACTE des mots : transcription locale de la voix avec faster-whisper (horodatage par mot), puis
alignement sur le texte du script. Le texte du script fait foi : Whisper ne sert qu'à HORODATER.

- Whisper est guidé par le texte du script (initial_prompt) : il écrit les mots comme le script.
- Alignement par séquence sur des sous-mots (traits d'union, apostrophes découpés des deux côtés) ; les nombres
  écrits en chiffres par Whisper (« 28 », « 3 000 000 », « 50 % », « 20 € ») sont convertis en lettres.
- Mots non entendus : interpolés entre voisins reconnus, au prorata de leurs syllabes.
- Bords de mots recalés sur les silences réels du fichier (un mot ne commence jamais dans un silence).
- Voix complète (ElevenLabs…) : les répliques sont découpées À PARTIR DES MOTS (début du 1er mot, fin du dernier),
  la détection des pauses n'étant plus qu'un secours.
Sans faster-whisper : minutage proportionnel aux syllabes (comportement historique), jamais bloquant.
"""
import difflib
import hashlib
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

from .util import sha256_file


def available():
    importlib.invalidate_caches()   # installé pendant que le tableau de bord tournait : le voir quand même
    return importlib.util.find_spec("faster_whisper") is not None


def status(load_model=False, model_size="small"):
    """Diagnostic : quel Python, module trouvé ?, importable ?, modèle chargeable ? -> dict lisible."""
    import sys
    out = {"python": sys.executable, "version": sys.version.split()[0], "installed": available()}
    if not out["installed"]:
        out["error"] = (f"faster-whisper n'est pas installé pour CE Python ({sys.executable}). "
                        "Installer avec : scripts\\studio.cmd install-whisper")
        return out
    try:
        import faster_whisper
        out["module"] = getattr(faster_whisper, "__version__", "?")
    except Exception as e:   # ex. DLL manquante sous Windows (ctranslate2)
        out["error"] = f"faster-whisper est installé mais ne se charge pas : {type(e).__name__}: {e}"[:500]
        return out
    if load_model:
        try:
            from faster_whisper import WhisperModel
            WhisperModel(model_size, device="cpu", compute_type="int8")
            out["model"] = f"{model_size} : chargé"
        except Exception as e:
            out["error"] = f"modèle « {model_size} » non chargé (téléchargement ? espace disque ?) : {type(e).__name__}: {e}"[:500]
    return out


def norm(tok):
    t = unicodedata.normalize("NFKD", str(tok).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t)


# ------------------------------------------------------------------ nombres en lettres (français)
_U = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize",
      "quatorze", "quinze", "seize"]
_T = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _below100(n):
    if n < 17:
        return _U[n]
    if n < 20:
        return "dix-" + _U[n - 10]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base = "soixante" if t == 7 else "quatre-vingt"
        rest = 10 + u
        if t == 7 and u == 1:
            return "soixante et onze"
        return base + "-" + (_U[rest] if rest < 17 else "dix-" + _U[rest - 10])
    if t == 8:
        return "quatre-vingts" if u == 0 else "quatre-vingt-" + _U[u]
    if u == 0:
        return _T[t]
    if u == 1:
        return _T[t] + " et un"
    return _T[t] + "-" + _U[u]


def _below1000(n):
    c, r = divmod(n, 100)
    parts = []
    if c == 1:
        parts.append("cent")
    elif c > 1:
        parts.append(_U[c] + (" cents" if r == 0 else " cent"))
    if r:
        parts.append(_below100(r))
    return " ".join(parts) if parts else "zéro"


def fr_number(n):
    """Nombre entier en lettres (orthographe traditionnelle), ex. 28 -> « vingt-huit »."""
    n = int(n)
    if n == 0:
        return "zéro"
    out = []
    for value, sing, plur in ((10 ** 9, "milliard", "milliards"), (10 ** 6, "million", "millions")):
        q, n = divmod(n, value)
        if q:
            out.append(f"{_below1000(q)} {sing if q == 1 else plur}")
    q, n = divmod(n, 1000)
    if q:
        out.append("mille" if q == 1 else f"{_below1000(q)} mille")
    if n:
        out.append(_below1000(n))
    return " ".join(out)


def _spell(token):
    """Jeton Whisper -> mots (chiffres, pourcentages, euros convertis)."""
    t = token.strip()
    m = re.fullmatch(r"([0-9][0-9  .]*)(?:,([0-9]+))?\s*(%|€|euros?)?[.,!?…]*", t)
    if m and re.search(r"[0-9]", m.group(1)):
        whole = int(re.sub(r"[^0-9]", "", m.group(1)))
        words = fr_number(whole)
        if m.group(2):
            words += " virgule " + fr_number(int(m.group(2)))
        if m.group(3) == "%":
            words += " pour cent"
        elif m.group(3):
            words += " euros"
        return words.split()
    return [t]


def _subtokens(word):
    return [x for x in re.split(r"[-'’\s]+", word) if norm(x)]


def _syll(word):
    from .audio import syllables
    return max(1, syllables(word))


# ------------------------------------------------------------------ transcription
def transcribe_words(wav, model_size="small", cache_dir=None, prompt=None):
    """-> [(mot, début, fin)] de faster-whisper (cache par contenu du fichier, modèle et texte guide)."""
    wav = Path(wav)
    ph = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:8]
    key = f"{sha256_file(wav)[:16]}_{model_size}_{ph}"
    cache = Path(cache_dir or wav.parent) / f"whisper_{key}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text(encoding="utf-8"))]
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    kw = {"language": "fr", "word_timestamps": True, "vad_filter": False, "beam_size": 5}
    if prompt:
        kw["initial_prompt"] = prompt[-900:]   # le texte attendu oriente l'orthographe et les mots
    segments, _info = model.transcribe(str(wav), **kw)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append((w.word.strip(), float(w.start), float(w.end)))
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


# ------------------------------------------------------------------ alignement texte du script <-> mots entendus
def align_words(lines, asr_words, silences=None, span=None):
    """lines : textes des répliques. -> (temps [(début, fin)] par mot du script, par réplique ; stats).

    span : (début, fin) de la parole dans le fichier, pour les mots non entendus en tête/queue.
    """
    # sous-jetons du script, rattachés à (réplique, mot)
    sub, owner = [], []
    for li, txt in enumerate(lines):
        for wi, w in enumerate(txt.split()):
            for x in _subtokens(w) or [w]:
                sub.append(norm(x))
                owner.append((li, wi))
    # sous-jetons entendus (chiffres en lettres), temps répartis
    heard = []
    for tok, st, en in asr_words:
        parts = [p for w in _spell(tok) for p in _subtokens(w)]
        parts = parts or [tok]
        d = max(0.0, en - st) / len(parts)
        for k, p in enumerate(parts):
            heard.append((norm(p), st + d * k, st + d * (k + 1)))
    sm = difflib.SequenceMatcher(a=sub, b=[h[0] for h in heard], autojunk=False)
    t_sub = [None] * len(sub)
    last = -1.0
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            i, j = blk.a + k, blk.b + k
            if sub[i] and heard[j][1] >= last - 0.02:   # jamais de retour en arrière
                t_sub[i] = (heard[j][1], heard[j][2])
                last = heard[j][2]
    # regroupement par mot du script
    words = [[None] * len(t.split()) for t in lines]
    for i, (li, wi) in enumerate(owner):
        if t_sub[i] is None:
            continue
        cur = words[li][wi]
        words[li][wi] = (t_sub[i][0], t_sub[i][1]) if cur is None else (min(cur[0], t_sub[i][0]), max(cur[1], t_sub[i][1]))
    flat = [(li, wi) for li, ws in enumerate(words) for wi in range(len(ws))]
    known = [k for k, (li, wi) in enumerate(flat) if words[li][wi] is not None]
    stats = {"matched": len(known), "total": len(flat),
             "per_line": [sum(1 for x in ws if x is not None) for ws in words]}
    if not known:
        return None, stats
    s0 = span[0] if span else words[flat[known[0]][0]][flat[known[0]][1]][0]
    s1 = span[1] if span else words[flat[known[-1]][0]][flat[known[-1]][1]][1]
    texts = [t.split() for t in lines]
    # interpolation des mots non entendus, au prorata des syllabes, entre voisins reconnus
    k = 0
    while k < len(flat):
        li, wi = flat[k]
        if words[li][wi] is not None:
            k += 1
            continue
        j = k
        while j < len(flat) and words[flat[j][0]][flat[j][1]] is None:
            j += 1
        lo = words[flat[k - 1][0]][flat[k - 1][1]][1] if k > 0 else s0
        hi = words[flat[j][0]][flat[j][1]][0] if j < len(flat) else s1
        gap = flat[k:j]
        ws = [_syll(texts[a][b]) for a, b in gap]
        tot, acc = float(sum(ws)), 0.0
        span_ = max(0.0, hi - lo)
        for (a, b), x in zip(gap, ws):
            words[a][b] = (lo + span_ * acc / tot, lo + span_ * (acc + x) / tot)
            acc += x
        k = j
    # bords recalés sur les silences réels (un mot ne commence ni ne finit au milieu d'un silence)
    if silences:
        for li, ws in enumerate(words):
            for wi, (st, en) in enumerate(ws):
                for a, b in silences:
                    if a < st < b:
                        st = b
                    if a < en < b and a > st + 0.03:
                        en = a
                ws[wi] = (round(st, 3), round(max(en, st + 0.03), 3))
    return words, stats


def refine(segments, asr_words, max_shift=0.6, silences=None):
    """Synthèse ligne par ligne (bornes des répliques exactes) : remplace les temps des mots par ceux de Whisper.

    Garde-fous : un mot ne s'éloigne pas de plus de `max_shift` s de son estimation et reste dans sa réplique
    (± 0,25 s). -> stats {matched, total}.
    """
    lines = [" ".join(w["text"] for w in s["words"]) for s in segments]
    words, stats = align_words(lines, asr_words, silences=silences, span=(segments[0]["start_s"], segments[-1]["end_s"]) if segments else None)
    if words is None:
        return {**stats, "matched": 0}
    matched = 0
    for s, ws in zip(segments, words):
        for w, (st, en) in zip(s["words"], ws):
            if abs(st - w["start_s"]) > max_shift and not (s["start_s"] - 0.25 <= st <= s["end_s"] + 0.25):
                continue
            if st < s["start_s"] - 0.25 or en > s["end_s"] + 0.25:
                continue
            w["start_s"], w["end_s"] = round(st, 3), round(max(en, st + 0.03), 3)
            matched += 1
        s["start_s"] = round(min(s["words"][0]["start_s"], s["start_s"] + 0.25), 3)
        s["end_s"] = round(max(s["words"][-1]["end_s"], s["end_s"] - 0.25), 3)
    return {**stats, "matched": min(matched, stats["matched"])}

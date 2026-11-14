"""Synchro EXACTE des mots (facultatif) : transcription locale de la narration avec faster-whisper, puis
alignement sur le texte du script (le texte du script fait foi : Whisper ne sert qu'à HORODATER les mots).

Sans faster-whisper installé, rien ne change : minutage proportionnel aux syllabes (comportement historique).
Gain : bouches et sous-titres calés au mot près sur une vraie voix (ElevenLabs, enregistrement, Piper).
Installation : `pip install faster-whisper` (le modèle, ~150 Mo pour « base », est téléchargé au premier usage).
"""
import difflib
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

from .util import sha256_file


def available():
    return importlib.util.find_spec("faster_whisper") is not None


def norm(tok):
    t = unicodedata.normalize("NFKD", str(tok).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t)


def transcribe_words(wav, model_size="base", cache_dir=None):
    """-> [(mot, début, fin)] de faster-whisper (mis en cache par contenu du fichier et modèle)."""
    wav = Path(wav)
    key = f"{sha256_file(wav)[:16]}_{model_size}"
    cache = Path(cache_dir or wav.parent) / f"whisper_{key}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text(encoding="utf-8"))]
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(wav), language="fr", word_timestamps=True, vad_filter=False, beam_size=5)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append((w.word.strip(), float(w.start), float(w.end)))
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def refine(segments, asr_words, max_shift=0.6):
    """Remplace les temps des mots (et bornes de répliques) par ceux de Whisper quand les mots correspondent.

    segments : timeline (modifiée sur place). Les mots non reconnus sont interpolés entre voisins reconnus.
    Garde-fous : un mot reconnu ne peut pas s'éloigner de plus de `max_shift` secondes de son estimation, ni
    sortir de sa réplique de plus de 0,25 s (une voix enregistrée ne « saute » pas d'une réplique à l'autre).
    -> statistiques {matched, total}.
    """
    flat = [(si, wi, w) for si, s in enumerate(segments) for wi, w in enumerate(s["words"])]
    a = [norm(w["text"]) for _, _, w in flat]
    b = [norm(x[0]) for x in asr_words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    match = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            if a[blk.a + k]:
                match[blk.a + k] = asr_words[blk.b + k]
    matched = 0
    new = [None] * len(flat)
    for i, (si, wi, w) in enumerate(flat):
        m = match.get(i)
        s = segments[si]
        if m is None:
            continue
        st, en = m[1], max(m[2], m[1] + 0.04)
        if abs(st - w["start_s"]) > max_shift or st < s["start_s"] - 0.25 or en > s["end_s"] + 0.25:
            continue
        new[i] = (st, en)
        matched += 1
    # interpolation des mots non reconnus entre voisins reconnus, réplique par réplique
    for si, s in enumerate(segments):
        idx = [i for i, (sj, _, _) in enumerate(flat) if sj == si]
        if not idx:
            continue
        known = [i for i in idx if new[i] is not None]
        if not known:
            continue
        for i in idx:
            if new[i] is not None:
                continue
            prev = max([k for k in known if k < i], default=None)
            nxt = min([k for k in known if k > i], default=None)
            lo = new[prev][1] if prev is not None else s["start_s"]
            hi = new[nxt][0] if nxt is not None else s["end_s"]
            gap = [k for k in idx if (prev is None or k > prev) and (nxt is None or k < nxt)]
            n = len(gap)
            j = gap.index(i)
            step = max(0.0, hi - lo) / max(1, n)
            new[i] = (lo + step * j, lo + step * (j + 1))
        for i in idx:
            w = flat[i][2]
            w["start_s"], w["end_s"] = round(new[i][0], 3), round(max(new[i][1], new[i][0] + 0.03), 3)
        # bornes de la réplique : du premier au dernier mot (sans dépasser les bornes acoustiques connues)
        s["start_s"] = round(min(s["words"][0]["start_s"], s["start_s"] + 0.25), 3)
        s["end_s"] = round(max(s["words"][-1]["end_s"], s["end_s"] - 0.25), 3)
    return {"matched": matched, "total": len(flat)}

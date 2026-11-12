"""Import d'un script IMPOSÉ par l'utilisateur : textes conservés mot pour mot et verrouillés.

Format du fichier (texte brut, UTF-8) :
- une réplique par ligne ; lignes vides et lignes commençant par `#` ignorées ;
- `Prénom: texte` (deux-points COLLÉ au prénom, 1 à 3 mots avec majuscule) = réplique d'un personnage ;
  `Narrateur:` / `Narratrice:` / `Voix off:` ou pas de préfixe = narrateur ;
  (une phrase de narration « Il m'a dit : bonjour » n'est pas prise pour un personnage : espace avant « : ») ;
- seule normalisation : la ponctuation détachée « ! ? : ; » est recollée au mot (« danse ! » -> « danse! »),
  car les ancrages d'animation comptent les mots ; une réplique > 240 caractères est coupée entre deux phrases.
"""
import re
import unicodedata

from .util import sha256_json

SPEAKER = re.compile(r"^([A-ZÀ-ÖØ-Þ][\w'À-ÿ-]*(?: [A-ZÀ-ÖØ-Þ][\w'À-ÿ-]*){0,2}):\s+(.+)$")
NARRATOR = {"narrateur", "narratrice", "voix off", "voix-off", "narration"}
MAXLEN = 240
WORDS_PER_S = 2.6


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return ("ch_" + s)[:35] if len(s) >= 2 else "ch_" + (s + "xx")[:2]


def _normalize(text):
    text = re.sub(r"\s+", " ", text.strip())
    return re.sub(r"\s+([!?:;»%])", r"\1", re.sub(r"([«])\s+", r"\1", text))


def _split_long(text):
    if len(text) <= MAXLEN:
        return [text]
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?…])\s+", text):
        if cur and len(cur) + 1 + len(sent) > MAXLEN:
            parts.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        parts.append(cur)
    out = []
    for p in parts:   # phrase unique trop longue : coupe sur une virgule
        while len(p) > MAXLEN:
            cut = p.rfind(",", 0, MAXLEN)
            cut = cut + 1 if cut > 40 else MAXLEN
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        out.append(p)
    return out


def parse(raw):
    """-> (lignes [{"speaker","text"}], personnages {id: nom})."""
    lines, chars = [], {}
    for row in raw.splitlines():
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        speaker = "narrator"
        m = SPEAKER.match(row)
        if m:
            name, row = m.group(1), m.group(2)
            if name.lower() not in NARRATOR:
                speaker = slug(name)
                chars.setdefault(speaker, name)
        for part in _split_long(_normalize(row)):
            lines.append({"speaker": speaker, "text": part})
    if len(lines) < 2:
        raise ValueError("le script doit contenir au moins 2 répliques (une par ligne)")
    return lines, chars


def estimate_duration(lines):
    words = sum(len(l["text"].split()) for l in lines)
    return round(words / WORDS_PER_S + 0.3 * len(lines) + 1.0, 1)


def skeleton(episode_id, lines, now):
    """story_script.json squelette : textes verrouillés, tout le reste « À DÉFINIR » par le story-architect."""
    n = len(lines)
    roles = ["hook"] + ["setup"] * max(0, round(n * 0.2)) + ["escalation"] * max(0, n - 3 - round(n * 0.2)) + ["climax", "payoff"]
    roles = roles[:n] if n >= 3 else ["hook", "payoff"]
    beat_of, beats = [], []
    for r in roles:
        if not beats or beats[-1]["role"] != r:
            beats.append({"id": f"b{len(beats) + 1:02d}", "role": r, "summary": "À DÉFINIR par le story-architect"})
        beat_of.append(beats[-1]["id"])
    while len(beats) < 3:
        beats.append({"id": f"b{len(beats) + 1:02d}", "role": "button", "summary": "À DÉFINIR par le story-architect"})
    return {
        "contract": "story_script", "contract_version": "1.0", "episode_id": episode_id, "status": "draft",
        "provenance": {"created_by": "studio import (script utilisateur verrouillé)", "created_at": now, "revision": 1},
        "title": "À DÉFINIR", "logline": "À DÉFINIR par le story-architect", "language": "fr-FR",
        "target_duration_s": max(8, min(180, estimate_duration(lines))),
        "hook": {"line_id": "l001", "technique": "absurd_claim", "why_it_works": "À DÉFINIR"},
        "beats": beats,
        "lines": [{"id": f"l{i + 1:03d}", "beat_id": beat_of[i], "speaker": l["speaker"], "text": l["text"],
                   "visual_intent": "À DÉFINIR par le story-architect"} for i, l in enumerate(lines)],
        "content_review": {"platform_risk": "medium", "notes": "À DÉFINIR par le story-architect"},
    }


def lock(lines):
    return {"lines": lines, "sha256": sha256_json(lines)}

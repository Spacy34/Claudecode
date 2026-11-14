"""Synchro Whisper : alignement des mots transcrits sur le texte du script (transcription simulée)."""
import copy

from studio import whisper_align


def _segs():
    # bornes ACOUSTIQUES des répliques (connues : synthèse ligne par ligne ou découpage sur les pauses) ;
    # mots répartis proportionnellement à l'intérieur (estimation avant Whisper)
    lines = [("Kevin a vingt-huit ans, aucun emploi.", 0.3, 2.45), ("Toasty grille du pain!", 2.85, 4.1)]
    out = []
    for i, (txt, a, b) in enumerate(lines):
        ws = txt.split()
        d = (b - a) / len(ws)
        words = [{"i": k, "text": w, "start_s": round(a + d * k, 3), "end_s": round(a + d * (k + 1), 3)} for k, w in enumerate(ws)]
        out.append({"line_id": f"l00{i + 1}", "start_s": a, "end_s": b, "words": words})
    return out


def test_refine_uses_whisper_times_and_interpolates_unknown_words():
    segs = _segs()
    words0 = copy.deepcopy(segs)
    # « vraie » voix : débit irrégulier ; Whisper écrit « 28 » au lieu de « vingt-huit » et rate « aucun »
    asr = [("Kevin", 0.30, 0.52), ("a", 0.55, 0.60), ("28", 0.62, 1.10), ("ans,", 1.12, 1.40), ("emploi.", 1.95, 2.40),
           ("Toasty", 2.90, 3.30), ("grille", 3.32, 3.60), ("du", 3.62, 3.70), ("pain", 3.72, 4.05)]
    stats = whisper_align.refine(segs, asr)
    assert stats["matched"] == 8 and stats["total"] == 10  # « 28 » ≠ « vingt-huit » ; « aucun » non transcrit
    w = {x["text"]: x for s in segs for x in s["words"]}
    assert (w["Kevin"]["start_s"], w["ans,"]["end_s"], w["pain!"]["end_s"]) == (0.3, 1.4, 4.05)
    # mots non reconnus : interpolés entre les voisins reconnus, dans l'ordre
    assert 0.6 <= w["vingt-huit"]["start_s"] < w["ans,"]["start_s"]
    assert w["ans,"]["end_s"] <= w["aucun"]["start_s"] < w["emploi."]["start_s"]
    # texte, ordre et indices inchangés (le script fait foi)
    assert [[x["text"] for x in s["words"]] for s in segs] == [[x["text"] for x in s["words"]] for s in words0]
    assert 4.05 <= segs[1]["end_s"] <= 4.1


def test_refine_rejects_absurd_matches():
    segs = _segs()
    asr = [("Kevin", 9.0, 9.2)]   # même mot, mais 9 s plus loin : hors réplique, ignoré
    stats = whisper_align.refine(segs, asr)
    assert stats["matched"] == 0

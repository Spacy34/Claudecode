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
    assert stats["matched"] == 9 and stats["total"] == 10  # « 28 » reconnu comme « vingt-huit » ; « aucun » non transcrit
    w = {x["text"]: x for s in segs for x in s["words"]}
    assert (w["Kevin"]["start_s"], w["ans,"]["end_s"], w["pain!"]["end_s"]) == (0.3, 1.4, 4.05)
    assert (w["vingt-huit"]["start_s"], w["vingt-huit"]["end_s"]) == (0.62, 1.1)   # chiffres convertis en lettres
    # mot non reconnu : interpolé entre ses voisins reconnus, dans l'ordre
    assert w["ans,"]["end_s"] <= w["aucun"]["start_s"] < w["emploi."]["start_s"]
    # texte, ordre et indices inchangés (le script fait foi)
    assert [[x["text"] for x in s["words"]] for s in segs] == [[x["text"] for x in s["words"]] for s in words0]
    assert 4.05 <= segs[1]["end_s"] <= 4.1


def test_refine_rejects_absurd_matches():
    segs = _segs()
    asr = [("Kevin", 9.0, 9.2)]   # même mot, mais 9 s plus loin : hors réplique, ignoré
    stats = whisper_align.refine(segs, asr)
    assert stats["matched"] == 0


def test_french_numbers_and_spelling():
    from studio.whisper_align import fr_number, _spell
    assert fr_number(28) == "vingt-huit" and fr_number(71) == "soixante et onze" and fr_number(80) == "quatre-vingts"
    assert fr_number(91) == "quatre-vingt-onze" and fr_number(200) == "deux cents" and fr_number(250) == "deux cent cinquante"
    assert fr_number(3000000) == "trois millions" and fr_number(1000) == "mille" and fr_number(21) == "vingt et un"
    assert _spell("50") == ["cinquante"] and _spell("50€") == ["cinquante", "euros"] and _spell("3 000 000") == ["trois", "millions"]
    assert _spell("12,5%") == ["douze", "virgule", "cinq", "pour", "cent"] and _spell("Chloé") == ["Chloé"]


def test_full_voice_line_bounds_come_from_heard_words():
    """Voix complète : les répliques sont découpées à partir des mots entendus, même sans pause entre elles."""
    lines = ["Plus de messages, plus d'appels.", "Chloé commence à paniquer."]
    asr = [("Plus", 1.0, 1.2), ("de", 1.2, 1.3), ("messages,", 1.3, 1.8), ("plus", 1.95, 2.1), ("d'appels.", 2.1, 2.6),
           ("Chloé", 2.62, 2.95), ("commence", 2.95, 3.4), ("à", 3.4, 3.5), ("paniquer.", 3.5, 4.1)]
    words, stats = whisper_align.align_words(lines, asr, silences=[(0.0, 1.0), (1.8, 1.95), (4.1, 5.0)], span=(1.0, 4.1))
    assert stats["matched"] == 9
    assert (words[0][0][0], words[0][-1][1]) == (1.0, 2.6) and (words[1][0][0], words[1][-1][1]) == (2.62, 4.1)


def test_transcribe_feeds_whisper_a_decoded_array_not_a_path(tmp_path, monkeypatch):
    """Régression Windows : faster-whisper + PyAV ≥ 14 plantait (« metadata_errors ») en décodant lui-même le
    fichier ; le studio décode avec FFmpeg et passe un tableau 16 kHz."""
    import shutil
    import subprocess
    import sys
    import types
    import numpy as np
    import pytest
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg absent")
    wav = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=1.5", "-ar", "48000", str(wav)], check=True)
    seen = {}

    class W:
        def __init__(self, word, start, end):
            self.word, self.start, self.end = word, start, end

    class Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            seen["audio"], seen["kw"] = audio, kw
            return iter([types.SimpleNamespace(words=[W(" Bonjour", 0.1, 0.5)])]), None
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    words = whisper_align.transcribe_words(wav, "small", tmp_path, prompt="Bonjour.")
    assert isinstance(seen["audio"], np.ndarray) and seen["audio"].dtype == np.float32
    assert abs(len(seen["audio"]) / 16000 - 1.5) < 0.05           # 16 kHz, durée conservée (temps exacts)
    assert seen["kw"]["word_timestamps"] and seen["kw"]["language"] == "fr" and seen["kw"]["initial_prompt"] == "Bonjour."
    assert words == [("Bonjour", 0.1, 0.5)]

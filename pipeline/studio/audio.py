"""Étape `voice` : synthèse par réplique (avec cache), timing mot par mot, timeline audio = horloge de l'épisode.

L'alignement mot à mot par défaut est PROPORTIONNEL aux syllabes estimées de chaque mot à l'intérieur
d'une réplique dont les bornes sont exactes (silences de début/fin retirés). Précision typique : ±0,1 s
par mot, suffisante pour les sous-titres par groupes de mots et le lip-flap cartoon ; pas pour un
lip-sync phonétique. Un aligneur forcé peut remplacer `word_timings` sans changer le contrat.
"""
import re
import wave
from pathlib import Path

from . import sfx as sfxlib
from . import tts
from .contracts import CONTRACT_VERSION, provenance_deps
from .util import ROOT, now, read_json, run, sha256_file, sha256_json, write_json

VOWELS = re.compile(r"[aeiouyàâäéèêëîïôöùûüœæ]+", re.I)
PUNCT_PAUSE = {",": 0.6, ";": 0.8, ":": 0.8, ".": 1.0, "!": 1.0, "?": 1.0, "…": 1.4}


def syllables(word):
    w = re.sub(r"[^\wàâäéèêëîïôöùûüœæç'-]", "", word.lower())
    w = re.sub(r"e$|es$|ent$", "", w) or w   # e muet final (approximation)
    return max(1, len(VOWELS.findall(w)))


def is_emphasis(word, idx, explicit):
    """Mot fort : explicite (script) ou détecté (chiffre, exclamation, MAJUSCULES)."""
    core = re.sub(r"[^\w-]", "", word)
    return idx in explicit or bool(re.search(r"\d", word)) or word.endswith("!") or (len(core) > 2 and core.isupper())


def word_timings(words, start, end):
    weights = []
    for w in words:
        weights.append(syllables(w) + PUNCT_PAUSE.get(w[-1], 0.0) * 0.5)
    total = sum(weights)
    t = start
    out = []
    span = end - start
    for i, (w, k) in enumerate(zip(words, weights)):
        dt = span * k / total
        out.append({"i": i, "text": w, "start_s": round(t, 3), "end_s": round(t + dt * 0.92, 3)})
        t += dt
    return out


def _normalize(raw, out, sr):
    """-> mono 48 kHz s16, silences de début/fin retirés (bornes de réplique précises)."""
    trim = "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.02,areverse,silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.02,areverse"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", trim, "-ar", str(sr), "-ac", "1", "-sample_fmt", "s16", str(out)])


def _wav_dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / float(w.getframerate())


def build_voice(ep_dir, cfg, force=False):
    ep_dir = Path(ep_dir)
    script = read_json(ep_dir / "story_script.json")
    cast_p = ep_dir / "cast_bible.json"
    cast = {c["id"]: c for c in read_json(cast_p)["characters"]} if cast_p.exists() else {}
    sr = int(cfg["audio"]["sample_rate"])
    backend = tts.pick_backend(cfg, ep_dir)
    lines_dir = ep_dir / "audio" / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)
    t = float(cfg["audio"]["lead_in_s"])
    segments, voice_desc, synthesized, recorded = [], None, 0, []
    for line in script["lines"]:
        vcfg = cast.get(line["speaker"], {}).get("voice", {}) if line["speaker"] != "narrator" else {}
        rec = tts.recording_for(ep_dir, line["id"])   # voix enregistrée par l'utilisateur : prioritaire sur la synthèse
        if rec is not None:
            key = sha256_json({"recorded": sha256_file(rec), "v": 1})[:16]
        else:
            key = sha256_json({"text": line["text"], "delivery": line.get("delivery", {}), "voice": vcfg, "backend": backend,
                               "tts": {k: cfg["tts"][k] for k in ("espeak_voice", "espeak_speed", "piper_model")}})[:16]
        wav = lines_dir / f"{line['id']}_{key}.wav"
        if force or not wav.exists():
            if rec is not None:
                _normalize(rec, wav, sr)
                recorded.append(line["id"])
            else:
                raw = lines_dir / f"{line['id']}_{key}.raw.wav"
                voice_desc = tts.synth(backend, cfg, line["text"], raw, line, vcfg, ep_dir)
                _normalize(raw, wav, sr)
                raw.unlink(missing_ok=True)
                synthesized += 1
        elif rec is not None:
            recorded.append(line["id"])
        for old in lines_dir.glob(f"{line['id']}_*.wav"):
            if old != wav:
                old.unlink()
        dur = _wav_dur(wav)
        words = line["text"].split()
        seg = {"line_id": line["id"], "speaker": line["speaker"], "wav": str(wav.relative_to(ep_dir)), "text_sha256": sha256_json(line["text"]),
               "start_s": round(t, 3), "end_s": round(t + dur, 3), "words": word_timings(words, t, t + dur)}
        explicit = set(line.get("emphasis_words", []))
        for w in seg["words"]:
            if is_emphasis(w["text"], w["i"], explicit):
                w["emph"] = True
        segments.append(seg)
        pause = line.get("delivery", {}).get("pause_after_ms")
        if pause is None:
            pause = 350 if line["text"].rstrip()[-1:] in "?!…" else 220
        t += dur + pause / 1000.0
    duration = t + float(cfg["audio"]["tail_s"])
    # bruitages : ancrés sur les mots
    sfx_dir = ROOT / cfg["paths"]["assets_dir"] / "sfx"
    sfxlib.ensure_library(sfx_dir)
    cues = []
    for line, seg in zip(script["lines"], segments):
        for s in line.get("sfx", []):
            f = sfx_dir / f"{s['name']}.wav"
            if not f.exists():
                raise RuntimeError(f"bruitage inconnu '{s['name']}' (disponibles : {sorted(sfxlib.LIBRARY)})")
            st = seg["words"][s["word"]]["start_s"] if "word" in s else seg["start_s"]
            cues.append({"name": s["name"], "file": str(f.relative_to(ROOT)), "start_s": round(st, 3), "gain_db": s.get("gain_db", cfg["audio"]["sfx_gain_db"]), "source": "script"})
    # bruitages fournis par l'utilisateur (tableau de bord) : audio/user_sfx/sfx.json -> [{line, word?, file, gain_db?}]
    usr = ep_dir / "audio" / "user_sfx" / "sfx.json"
    if usr.exists():
        segs_by = {s_["line_id"]: s_ for s_ in segments}
        for u in read_json(usr):
            seg = segs_by.get(u["line"])
            f = ep_dir / "audio" / "user_sfx" / u["file"]
            if seg is None or not f.exists():
                continue
            st = seg["words"][min(u.get("word", 0), len(seg["words"]) - 1)]["start_s"]
            cues.append({"name": f"user:{u['file']}", "file": _rel_root(f), "start_s": round(st, 3), "gain_db": u.get("gain_db", cfg["audio"]["sfx_gain_db"] + 2), "source": "user"})
    custom = sorted(q for q in (ep_dir / "audio" / "music").glob("*") if q.suffix.lower() in tts.AUDIO_EXT) if (ep_dir / "audio" / "music").is_dir() else []
    if custom:
        music, music_lic = custom[0], "fournie par l'utilisateur (droits d'usage commercial à vérifier par l'utilisateur)"
    else:
        music, music_lic = sfxlib.music_loop(ROOT / cfg["paths"]["assets_dir"] / "music" / "goofy_bounce.wav"), "original (synthèse procédurale)"
    # piste narration complète (silences inclus) : la voix est l'horloge
    narr = ep_dir / "audio" / "narration.wav"
    _assemble(ep_dir, segments, duration, sr, narr)
    tl = {"contract": "audio_timeline", "contract_version": CONTRACT_VERSION, "episode_id": script["episode_id"], "status": "generated",
          "provenance": {"created_by": "studio voice", "created_at": now(), "tool": f"tts:{backend}", "depends_on": provenance_deps(ep_dir, ["story_script", "cast_bible"])},
          "sample_rate": sr, "duration_s": round(duration, 3), "narration_wav": str(narr.relative_to(ep_dir)),
          "tts": {"backend": backend, "voice": (voice_desc or {}).get("voice", "cache"), "license": (voice_desc or {}).get("license", "voir backend"),
                  "alignment": "proportional_syllables"},
          "segments": segments, "sfx": cues,
          "music": {"file": _rel_root(music), "gain_db": cfg["audio"]["music_gain_db"] + (4 if custom else 0), "license": music_lic}}
    if recorded:
        tl["tts"]["recorded_lines"] = recorded
    write_json(ep_dir / "audio_timeline.json", tl)
    return {"backend": backend, "synthesized_lines": synthesized, "recorded_lines": recorded, "duration_s": round(duration, 2)}


def _rel_root(p):
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)   # épisode hors du dépôt : chemin absolu (ROOT / absolu = absolu)


def _assemble(ep_dir, segments, duration, sr, out):
    import array
    total = int(duration * sr)
    buf = array.array("h", bytes(total * 2))
    for seg in segments:
        with wave.open(str(ep_dir / seg["wav"])) as w:
            data = array.array("h", w.readframes(w.getnframes()))
        st = int(seg["start_s"] * sr)
        n = min(len(data), total - st)
        buf[st:st + n] = data[:n]
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())

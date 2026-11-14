"""Voix complète fournie (ElevenLabs…) : découpage en répliques sur les pauses, puis tout se cale dessus."""
import array
import shutil
import subprocess
import wave

import pytest

from studio import align, audio
from studio import compile as comp
from studio.util import read_json

pytestmark = pytest.mark.skipif(shutil.which("espeak-ng") is None or shutil.which("ffmpeg") is None, reason="espeak-ng/ffmpeg absents")


def _voice(tmp_path, texts, pauses, sr=48000):
    buf, truth, t = array.array("h"), [], 0.0

    def sil(d):
        nonlocal t
        buf.extend(array.array("h", bytes(int(d * sr) * 2)))
        t += d
    sil(0.3)
    for i, (txt, p) in enumerate(zip(texts, pauses)):
        raw, n = tmp_path / f"{i}.wav", tmp_path / f"{i}n.wav"
        subprocess.run(["espeak-ng", "-v", "fr", "-w", str(raw), txt], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", "silenceremove=start_periods=1:start_threshold=-42dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-42dB,areverse", "-ar", str(sr), "-ac", "1", "-sample_fmt", "s16", str(n)], check=True)
        with wave.open(str(n)) as w:
            d = array.array("h", w.readframes(w.getnframes()))
        truth.append((t, t + len(d) / sr))
        buf.extend(d)
        t += len(d) / sr
        sil(p)
    out = tmp_path / "voix_complete.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())
    return out, truth


def test_full_voice_drives_the_whole_timeline(episode, cfg, tmp_path):
    lines = read_json(episode / "story_script.json")["lines"]
    src, truth = _voice(tmp_path, [l["text"] for l in lines], [0.6, 0.45, 0.8, 0.5, 0.7, 0.55, 0.65, 0.5, 0.4])
    d = episode / "audio" / "full_voice"
    d.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-b:a", "128k", str(d / "elevenlabs.mp3")], check=True)
    res = audio.build_voice(episode, cfg)
    tl = read_json(episode / "audio_timeline.json")
    assert tl["tts"]["alignment"] == "pauses_syllables" and "elevenlabs.mp3" in tl["tts"]["voice"]
    for seg, (a, b) in zip(tl["segments"], truth):
        assert abs(seg["start_s"] - a) < 0.1 and abs(seg["end_s"] - b) < 0.1, (seg["line_id"], seg["start_s"], seg["end_s"], a, b)
    rep = read_json(episode / "checks" / "voice_alignment.json")
    assert rep["virtual_cuts"] == 0 and len(rep["lines"]) == len(lines)
    assert tl["duration_s"] >= truth[-1][1]
    assert res["duration_s"] > 20
    man = comp.compile_episode(episode, cfg)   # les plans se calent sur la voix fournie
    assert man["shots"][-1]["end_frame"] == man["total_frames"]


def test_align_falls_back_when_no_pauses():
    bounds, rep = align.align(["un deux trois", "quatre cinq six sept"], [], 10.0)
    assert len(bounds) == 2 and bounds[0][0] == 0.0 and bounds[1][1] == 10.0
    assert rep["virtual_cuts"] >= 1

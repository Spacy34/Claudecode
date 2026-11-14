"""Aperçu de synchro : vidéo légère (fond sombre + voix + sous-titres réels + réplique en cours) pour juger
À L'OREILLE ET À L'ŒIL le calage d'une voix complète, en quelques secondes, avant toute production.

    studio sync-preview <voix.mp3> <script.txt>        (un fichier, une réplique par ligne)
    studio sync-preview <ep>                            (voix complète d'un épisode existant)
"""
from pathlib import Path

from . import script_import
from .audio import analyze_full_voice, full_voice_file, is_emphasis
from .subtitles import _esc, _ts, build_ass
from .util import read_json, run, write_json


def texts_from_file(script_file):
    raw = Path(script_file).read_text(encoding="utf-8")
    try:
        return [l["text"] for l in script_import.parse(raw)]
    except Exception:
        return [l.strip() for l in raw.splitlines() if l.strip()]


def build(audio_path, texts, cfg, out_mp4, work_dir, width=540, height=960):
    res = analyze_full_voice(audio_path, texts, cfg, work_dir)
    segs = []
    for li, (txt, (a, b)) in enumerate(zip(texts, res["bounds"])):
        ws = txt.split()
        if res["words"]:
            times = res["words"][li]
        else:
            from .audio import word_timings
            times = [(w["start_s"], w["end_s"]) for w in word_timings(ws, a, b)]
        words = [{"i": i, "text": w, "start_s": st, "end_s": en, **({"emph": True} if is_emphasis(w, i, set()) else {})}
                 for i, (w, (st, en)) in enumerate(zip(ws, times))]
        segs.append({"line_id": f"l{li + 1:03d}", "start_s": a, "end_s": b, "words": words})
    tl = {"duration_s": res["dur"], "segments": segs}
    out_mp4 = Path(out_mp4)
    ass = out_mp4.with_suffix(".ass")
    build_ass(tl, cfg, ass, 0.0, res["dur"], width, height)
    # réplique en cours (haut) + méthode de calage (bas)
    method = {"whisper": "Whisper (mots entendus)", "pauses_syllables": "pauses (sans Whisper)"}.get(res["method"], res["method"])
    top = int(height * 0.035)
    extra_style = (f"Style: TOP,Arial,{top},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,1,0,8,30,30,"
                   f"{int(height * 0.06)},1")
    lines = ass.read_text(encoding="utf-8").splitlines()
    i = lines.index("[Events]") - 1
    lines.insert(i, extra_style)
    for s in segs:
        flag = next((r.get("flag") for r in [res["report"]["lines"][int(s["line_id"][1:]) - 1]] if r.get("flag")), "")
        head = _esc(f"{s['line_id']}  ({s['start_s']:.2f}–{s['end_s']:.2f} s){'  ⚠ ' + flag if flag else ''}")
        body = _esc(" ".join(w["text"] for w in s["words"]))
        lines.append(f"Dialogue: 1,{_ts(s['start_s'])},{_ts(s['end_s'])},TOP,,0,0,0,,{{\\q0}}{head}\\N{body}")
    lines.append(f"Dialogue: 1,{_ts(0)},{_ts(res['dur'])},TOP,,0,0,0,,{{\\an2\\fs{int(top * 0.8)}\\c&H00A0A0A0&}}calage : {_esc(method)}")
    ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x15171C:s={width}x{height}:r=30:d={res['dur']:.3f}",
         "-i", str(Path(audio_path).resolve()), "-vf", f"ass='{ass.name}'", "-shortest", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(out_mp4.resolve())], cwd=str(ass.parent))
    rep = {"method": res["method"], "whisper": res["whisper"], "duration_s": round(res["dur"], 2),
           "lines": [{"line_id": s["line_id"], "text": t, **r} for s, t, r in zip(segs, texts, res["report"]["lines"])]}
    write_json(out_mp4.with_suffix(".json"), rep)
    return out_mp4, rep


def for_episode(ep_dir, cfg):
    ep_dir = Path(ep_dir)
    full = full_voice_file(ep_dir)
    if full is None:
        raise FileNotFoundError("cet épisode n'a pas de voix complète (Voix & sons → Fournir la voix complète)")
    sp = ep_dir / "story_script.json"
    if sp.exists():
        texts = [l["text"] for l in read_json(sp)["lines"]]
    else:
        lock = read_json(ep_dir / "episode_brief.json").get("script_lock") or {}
        texts = [l["text"] for l in lock.get("lines", [])]
    if not texts:
        raise ValueError("aucun texte de script pour cet épisode")
    return build(full, texts, cfg, ep_dir / "checks" / "sync_preview.mp4", ep_dir / "audio")

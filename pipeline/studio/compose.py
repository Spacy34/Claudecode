"""Montage FFmpeg : clips par plan (transitions), concaténation, mixage audio (ducking + loudnorm 2 passes),
sous-titres incrustés, export MP4 H.264/AAC 1080x1920 30 fps.

Les clips encodés sont mis en cache par contenu : changer un plan ne ré-encode que son clip
(et ceux de ses voisins si la transition qui les relie change).
"""
import json
import re
from pathlib import Path

from . import sfx as sfxlib
from .subtitles import build_ass
from .util import ROOT, cache_dir, run, sha256_json

ENC_VERSION = "clip-v2"


def encode_clip(cfg, rec, shot, profile, t_in, t_out, fps):
    w, h = profile["resolution"]
    step = int(profile.get("render_every_n_frames", 1))
    key = sha256_json({"r": rec["cache_key"], "n": shot["frames"], "in": t_in, "out": t_out, "res": [w, h], "step": step, "v": ENC_VERSION})
    out = cache_dir(cfg) / "clips" / f"{key}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    N = shot["frames"]
    T = N / fps
    vf = [f"fps={fps}", f"scale={w}:{h}:flags=lanczos", "tpad=stop_mode=clone:stop_duration=2", f"trim=end_frame={N}", "setpts=PTS-STARTPTS"]
    fd = min(0.25, T / 3)
    if t_in == "fade_black":
        vf.append(f"fade=t=in:st=0:d={fd:.3f}")
    elif t_in == "flash_white":
        vf.append(f"fade=t=in:st=0:d={min(0.12, fd):.3f}:color=white")
    if t_out == "fade_black":
        vf.append(f"fade=t=out:st={T - fd:.3f}:d={fd:.3f}")
    elif t_out == "flash_white":
        vf.append(f"fade=t=out:st={T - min(0.1, fd):.3f}:d={min(0.1, fd):.3f}:color=white")
    elif t_out == "whip":
        vf.append(f"boxblur=luma_radius=min(h\\,w)/12:luma_power=2:enable='gte(n\\,{max(0, N - 4)})'")
    if t_in == "whip":
        vf.append("boxblur=luma_radius=min(h\\,w)/14:luma_power=2:enable='lte(n\\,2)'")
    vf.append("format=yuv420p")
    # Liste ffconcat (portable : -pattern_type glob n'existe pas dans les builds FFmpeg Windows)
    fdir = Path(rec["frames_dir"])
    pngs = sorted(fdir.glob("f[0-9][0-9][0-9][0-9].png"))
    if not pngs:
        raise RuntimeError(f"aucune image rendue dans {fdir}")
    lst = out.with_suffix(".ffconcat")
    lines = ["ffconcat version 1.0"]
    for k, png in enumerate(pngs):
        nxt = int(pngs[k + 1].stem[1:]) if k + 1 < len(pngs) else N + 1
        lines += [f"file '{png.as_posix()}'", f"duration {max(1, nxt - int(png.stem[1:])) / fps:.6f}"]
    lines.append(f"file '{pngs[-1].as_posix()}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-vf", ",".join(vf), "-frames:v", str(N), "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-an", str(out)])
    lst.unlink(missing_ok=True)
    return out


def concat(clips, out):
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(c).as_posix()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    lst.unlink()
    return out


def sfx_cues(timeline, shots, cfg):
    cues = list(timeline["sfx"])
    sfx_dir = ROOT / cfg["paths"]["assets_dir"] / "sfx"
    for s in shots[:-1]:
        name = sfxlib.TRANSITION_SFX.get(s.get("transition_out", "cut"))
        if name:
            cues.append({"name": name, "file": str((sfx_dir / f"{name}.wav").relative_to(ROOT)), "start_s": max(0, s["end_s"] - (0.18 if name == "whoosh" else 0.0)),
                         "gain_db": cfg["audio"]["sfx_gain_db"] - 3, "source": "transition"})
    return cues


def mix_audio(ep_dir, timeline, shots, cfg, t0, t1, out):
    ep_dir = Path(ep_dir)
    dur = t1 - t0
    inputs = ["-i", str(ep_dir / timeline["narration_wav"])]
    music = timeline.get("music")
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(ROOT / music["file"])]
    cues = [c for c in sfx_cues(timeline, shots, cfg) if t0 - 0.05 <= c["start_s"] < t1]
    for c in cues:
        inputs += ["-i", str(ROOT / c["file"])]
    fl = [f"[0:a]atrim={t0:.3f}:{t1:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[nar][sc]"]
    mix_in = ["[nar]"]
    idx = 1
    if music:
        fl.append(f"[1:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,volume={music['gain_db']}dB[mus]")
        fl.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[duck]")
        mix_in.append("[duck]")
        idx = 2
    else:
        fl.append("[sc]anullsink")
    for k, c in enumerate(cues):
        ms = int(max(0.0, c["start_s"] - t0) * 1000)
        fl.append(f"[{idx + k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={c.get('gain_db', -8)}dB,adelay={ms}|{ms}[s{k}]")
        mix_in.append(f"[s{k}]")
    fl.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first,atrim=0:{dur:.3f}[pre]")
    graph = ";".join(fl)
    tmp = Path(out).with_suffix(".pre.wav")
    run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", graph, "-map", "[pre]", "-ar", "48000", str(tmp)])
    # loudnorm deux passes : niveau homogène entre épisodes (cible plateforme mobile)
    I, TP = cfg["audio"]["target_lufs"], cfg["audio"]["true_peak_db"]
    r = run(["ffmpeg", "-v", "info", "-i", str(tmp), "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if m:
        j = json.loads(m.group(0))
        af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
              f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    else:
        af = f"loudnorm=I={I}:TP={TP}:LRA=11"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af", af, "-ar", "48000", "-ac", "2", str(out)])
    tmp.unlink(missing_ok=True)
    return out, cues


def assemble(cfg, ep_dir, manifest, timeline, recs, profile, out_path, fps=30):
    """recs : enregistrements de rendu (même ordre que manifest['shots'] sélectionnés)."""
    ep_dir = Path(ep_dir)
    shots = [s for s in manifest["shots"] if s["id"] in {r["id"] for r in recs}]
    by_id = {r["id"]: r for r in recs}
    all_ids = [s["id"] for s in manifest["shots"]]
    clips = []
    for s in shots:
        i = all_ids.index(s["id"])
        prev = manifest["shots"][i - 1] if i > 0 else None
        t_in = prev.get("transition_out", "cut") if prev and prev["id"] in by_id else "cut"
        nxt_in = (i + 1 < len(all_ids)) and all_ids[i + 1] in by_id
        t_out = s.get("transition_out", "cut") if nxt_in else ("cut" if i + 1 < len(all_ids) else s.get("transition_out", "cut"))
        clips.append(encode_clip(cfg, by_id[s["id"]], s, profile, t_in, t_out, fps))
    work = Path(out_path).parent / ".work"
    work.mkdir(parents=True, exist_ok=True)
    stem = Path(out_path).stem
    video = concat(clips, work / f"{stem}_video.mp4")
    t0, t1 = shots[0]["start_s"], shots[-1]["end_s"]
    audio, cues = mix_audio(ep_dir, timeline, shots, cfg, t0, t1, work / f"{stem}_mix.wav")
    ass = Path(out_path).with_suffix(".ass")
    n_sub = build_ass(timeline, cfg, ass, t0, t1)
    up = profile.get("upscale_to_delivery", True)
    W, H = (1080, 1920) if up else tuple(profile["resolution"])
    fonts = ROOT / cfg["paths"]["assets_dir"] / "fonts"
    # ffmpeg lancé depuis le dossier du .ass : chemins relatifs, donc pas de « C: » à échapper sous Windows
    import os
    ass_f = f"ass='{ass.name}'"
    if fonts.is_dir():
        try:
            ass_f += f":fontsdir='{Path(os.path.relpath(fonts, ass.parent)).as_posix()}'"
        except ValueError:   # disque différent sous Windows
            pass
    # couche motion design (téléphone, textes, stickers…) SOUS les sous-titres, puis barre de progression
    from . import motion
    md = motion.load(ep_dir)
    overlay = motion.build_overlay(cfg, ep_dir, timeline, W, H, fps, t0, t1) if md else None
    prog = motion.progress_settings(md)
    inputs = ["-i", str(Path(video).resolve()), "-i", str(Path(audio).resolve())]
    graph = [f"[0:v]scale={W}:{H}:flags=lanczos[b0]"]
    cur = "b0"
    if overlay:
        inputs += ["-f", "concat", "-safe", "0", "-i", str(Path(overlay).resolve())]
        graph.append(f"[2:v]format=rgba,setpts=PTS-STARTPTS[ov];[{cur}][ov]overlay=0:0:eof_action=pass:format=auto[b1]")
        cur = "b1"
    if prog:
        ph = max(4, H // 160)
        col = prog["color"].lstrip("#")
        total = max(0.1, timeline["duration_s"])
        graph.append(f"color=c=0x{col}:s={W}x{ph}:r={fps}[pb];[{cur}][pb]overlay=x='-w+w*(t+{t0:.3f})/{total:.3f}':y={int(H * 0.012)}:shortest=1[b2]")
        cur = "b2"
    graph.append(f"[{cur}]{ass_f},format=yuv420p[v]")
    run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(graph), "-map", "[v]", "-map", "1:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18" if profile["name"] == "final" else "21", "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-ac", "2", "-t", f"{t1 - t0:.3f}", "-movflags", "+faststart", str(Path(out_path).resolve())], cwd=str(ass.parent))
    return {"output": str(out_path), "start_s": t0, "end_s": t1, "subtitle_events": n_sub, "sfx_cues": len(cues), "clips": [str(c) for c in clips],
            "expected_frames": sum(s["frames"] for s in shots), "resolution": [W, H], "motion_overlay": bool(overlay), "progress_bar": bool(prog)}

"""QA technique automatique d'un MP4 (ffprobe + filtres ffmpeg). Mesures objectives uniquement.

Ce module ne juge PAS la qualité visuelle : un rapport entièrement vert signifie « techniquement conforme »,
pas « réussi ». Le jugement visuel appartient au critique visuel (images) et à l'humain.
"""
import re
from pathlib import Path

from ..contracts import CONTRACT_VERSION
from ..util import ffprobe_json, now, run, sha256_file

SPEC_FINAL = {"width": 1080, "height": 1920, "fps": "30/1", "vcodec": "h264", "pix_fmt": "yuv420p", "acodec": "aac", "sample_rate": 48000, "channels": 2}


def _c(cid, cat, sev, ok, msg, method, warn=False, **ev):
    return {"id": cid, "category": cat, "severity": sev, "status": "pass" if ok else ("warn" if warn else "fail"), "message": msg, "method": method, "evidence": ev}


def check_video(path, expected_duration=None, expected_frames=None, spec=None, subs_path=None, allowed_black=None, cfg=None):
    spec = dict(SPEC_FINAL, **(spec or {}))
    path = Path(path)
    out = []
    pj = ffprobe_json(path)
    v = next((s for s in pj["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in pj["streams"] if s["codec_type"] == "audio"), None)
    dur = float(pj["format"]["duration"])
    out.append(_c("container_mp4", "technical", "blocker", "mp4" in pj["format"]["format_name"], f"conteneur {pj['format']['format_name']}", "ffprobe"))
    if v is None:
        out.append(_c("video_stream", "technical", "blocker", False, "aucune piste vidéo", "ffprobe"))
        return out, dur
    out.append(_c("resolution", "technical", "blocker", (v["width"], v["height"]) == (spec["width"], spec["height"]), f"{v['width']}x{v['height']} (attendu {spec['width']}x{spec['height']})", "ffprobe"))
    out.append(_c("video_codec", "technical", "blocker", v["codec_name"] == spec["vcodec"], f"codec {v['codec_name']} profil {v.get('profile')}", "ffprobe"))
    out.append(_c("pix_fmt", "technical", "major", v.get("pix_fmt") == spec["pix_fmt"], f"pix_fmt {v.get('pix_fmt')}", "ffprobe"))
    out.append(_c("framerate", "technical", "blocker", v["r_frame_rate"] == spec["fps"], f"fps {v['r_frame_rate']}", "ffprobe"))
    if a is None:
        out.append(_c("audio_stream", "audio", "blocker", False, "aucune piste audio", "ffprobe"))
    else:
        out.append(_c("audio_codec", "audio", "blocker", a["codec_name"] == spec["acodec"], f"audio {a['codec_name']} {a.get('sample_rate')} Hz {a.get('channels')} canaux", "ffprobe"))
        out.append(_c("audio_format", "audio", "major", int(a.get("sample_rate", 0)) == spec["sample_rate"] and a.get("channels") == spec["channels"], f"{a.get('sample_rate')} Hz / {a.get('channels')} canaux", "ffprobe"))
        vs, as_ = float(v.get("start_time", 0)), float(a.get("start_time", 0))
        vd, ad = float(v.get("duration", dur)), float(a.get("duration", dur))
        out.append(_c("av_start_sync", "sync", "blocker", abs(vs - as_) < 0.045, f"décalage de départ audio/vidéo {as_ - vs:+.3f}s", "ffprobe", video_start=vs, audio_start=as_))
        out.append(_c("av_duration_match", "sync", "major", abs(vd - ad) < 0.12, f"durées vidéo {vd:.2f}s / audio {ad:.2f}s", "ffprobe"))
    if expected_duration is not None:
        out.append(_c("duration", "technical", "major", abs(dur - expected_duration) < 0.2, f"durée {dur:.2f}s (attendu {expected_duration:.2f}s)", "ffprobe"))
    if expected_frames is not None:
        nb = int(v.get("nb_frames") or round(float(v.get("duration", dur)) * 30))
        out.append(_c("frame_count", "technical", "major", abs(nb - expected_frames) <= 2, f"{nb} images (attendu {expected_frames})", "ffprobe"))
    # images noires
    r = run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "blackdetect=d=0.25:pic_th=0.94:pix_th=0.08", "-an", "-f", "null", "-"], check=False)
    blacks = [(float(m.group(1)), float(m.group(2))) for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
    allowed_black = allowed_black or []
    bad = [b for b in blacks if not any(abs(b[0] - t) < 0.4 for t in allowed_black)]
    out.append(_c("black_frames", "technical", "blocker", not bad, f"segments noirs non prévus : {[(round(x, 2), round(y, 2)) for x, y in bad]}" if bad else "aucun segment noir non prévu",
                  "ffmpeg_filter", segments=bad))
    # images figées longues
    r = run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "freezedetect=n=-60dB:d=2.5", "-an", "-f", "null", "-"], check=False)
    frz = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
    out.append(_c("frozen_video", "technical", "major", not frz, f"image figée > 2,5 s à {frz}" if frz else "aucune image figée > 2,5 s", "ffmpeg_filter", warn=True, starts=frz))
    if a is not None:
        r = run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"], check=False)
        I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
        TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
        if I:
            li = float(I[-1])
            tgt = cfg["audio"]["target_lufs"] if cfg else -14.0
            out.append(_c("loudness", "audio", "major", abs(li - tgt) <= 1.5, f"loudness intégrée {li:.1f} LUFS (cible {tgt})", "ffmpeg_filter", lufs=li))
        if TP:
            tp = float(TP[-1])
            out.append(_c("true_peak", "audio", "major", tp <= -0.5, f"true peak {tp:.1f} dBTP", "ffmpeg_filter", true_peak=tp))
        r = run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "silencedetect=n=-45dB:d=1.6", "-vn", "-f", "null", "-"], check=False)
        sil = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
        out.append(_c("long_silence", "audio", "minor", not sil, f"silences > 1,6 s à {sil}" if sil else "pas de silence long", "ffmpeg_filter", warn=True))
    if subs_path:
        sp = Path(subs_path)
        ok = sp.exists()
        ends = []
        if ok:
            for l in sp.read_text(encoding="utf-8").splitlines():
                if l.startswith("Dialogue:"):
                    e = l.split(",")[2]
                    h, m, s = e.split(":")
                    ends.append(int(h) * 3600 + int(m) * 60 + float(s))
        out.append(_c("subtitles_present", "subtitles", "major", ok and bool(ends), f"{len(ends)} évènements de sous-titres", "python"))
        if ends:
            out.append(_c("subtitles_within_video", "subtitles", "minor", max(ends) <= dur + 0.05, f"dernier sous-titre à {max(ends):.2f}s / vidéo {dur:.2f}s", "python"))
    return out, dur


def report(target, checks, episode_id, kind):
    passed = sum(c["status"] == "pass" for c in checks)
    failed = sum(c["status"] == "fail" for c in checks)
    warns = sum(c["status"] == "warn" for c in checks)
    blocking = any(c["status"] == "fail" and c["severity"] in ("blocker", "major") for c in checks)
    return {"contract": "qa_report", "contract_version": CONTRACT_VERSION, "episode_id": episode_id, "status": "generated",
            "provenance": {"created_by": "studio qa", "created_at": now(), "tool": "ffprobe/ffmpeg"},
            "target": {"path": str(target), "sha256": sha256_file(target), "kind": kind},
            "checks": checks, "summary": {"passed": passed, "failed": failed, "warnings": warns, "skipped": 0, "blocking": blocking}}


def scene_checks_to_qa(recs):
    """Convertit les contrôles exécutés dans Blender (render_manifest) en entrées QA."""
    out = []
    for r in recs:
        rep = r.get("scene_report") or {}
        if r["status"] == "failed":
            out.append(_c(f"render_failed:{r['id']}", "scene", "blocker", False, f"{r['id']} : rendu en échec : {r.get('error', '')[:300]}", "blender_scene_check"))
            continue
        for c in rep.get("checks", []):
            out.append({"id": f"{r['id']}:{c['id']}", "category": "scene", "severity": c["severity"], "status": c["status"], "message": f"{r['id']} : {c['message']}",
                        "method": "blender_scene_check", "evidence": {"shot_id": r["id"], "frames": c.get("frames", [])}})
        if not rep.get("checks"):
            out.append(_c(f"{r['id']}:scene_ok", "scene", "info", True, f"{r['id']} : aucun défaut géométrique détecté", "blender_scene_check"))
    return out

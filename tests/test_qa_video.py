"""Tests I et G sans Blender : la QA vérifie réellement les spécifications MP4 et détecte des défauts injectés."""
import shutil
import subprocess

import pytest

from studio.qa import tech

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def _make(path, black=None, offset=None, w=1080, h=1920):
    vf = "format=yuv420p"
    if black:
        vf = f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,{black[0]},{black[1]})',format=yuv420p"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=4"]
    if offset:
        cmd += ["-itsoffset", str(offset)]
    cmd += ["-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=4", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-ar", "48000", "-t", "4", str(path)]
    subprocess.run(cmd, check=True)


def _status(checks, cid):
    return next(c for c in checks if c["id"] == cid)["status"]


def test_spec_compliant_video_passes(tmp_path):
    p = tmp_path / "ok.mp4"
    _make(p)
    checks, dur = tech.check_video(p, expected_duration=4.0)
    for cid in ("resolution", "video_codec", "framerate", "audio_codec", "av_start_sync", "black_frames", "duration"):
        assert _status(checks, cid) == "pass", cid


def test_wrong_resolution_detected(tmp_path):
    p = tmp_path / "small.mp4"
    _make(p, w=720, h=1280)
    checks, _ = tech.check_video(p)
    assert _status(checks, "resolution") == "fail"


def test_injected_black_segment_detected(tmp_path):
    p = tmp_path / "black.mp4"
    _make(p, black=(1.0, 2.0))
    checks, _ = tech.check_video(p)
    c = next(c for c in checks if c["id"] == "black_frames")
    assert c["status"] == "fail" and abs(c["evidence"]["segments"][0][0] - 1.0) < 0.1


def test_injected_audio_offset_detected(tmp_path):
    p = tmp_path / "offset.mp4"
    _make(p, offset=0.5)
    checks, _ = tech.check_video(p)
    assert _status(checks, "av_start_sync") == "fail"

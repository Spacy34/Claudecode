"""Sous-titres ASS « TikTok » : groupes de 2-4 mots, mot courant surligné, grande police lisible sur mobile."""
from pathlib import Path


def _ts(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def chunks(words, per, max_chars):
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x["text"] for x in cur)
        if len(cur) >= per or len(text) >= max_chars or w["text"][-1:] in ".,!?…;:":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build_ass(timeline, cfg, out_path, t_start=0.0, t_end=None, width=1080, height=1920):
    sc = cfg["subtitles"]
    size = int(height * float(sc["font_size_ratio"]))
    y = int(height * float(sc["vertical_position"]))
    upper = sc.get("uppercase", True)
    hl, base = sc["highlight_color"], sc["base_color"]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: TT,{sc['font_family']},{size},{base},{hl},&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,{max(4, size // 14)},{max(2, size // 30)},5,60,60,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    t_end = t_end if t_end is not None else timeline["duration_s"]
    events = 0
    all_chunks = []
    for seg in timeline["segments"]:
        for ch in chunks(seg["words"], int(sc["words_per_chunk"]), int(sc["max_chars_per_chunk"])):
            all_chunks.append(ch)
    for ci, ch in enumerate(all_chunks):
        c0 = ch[0]["start_s"]
        nxt = all_chunks[ci + 1][0]["start_s"] if ci + 1 < len(all_chunks) else ch[-1]["end_s"] + 0.4
        c1 = min(nxt, ch[-1]["end_s"] + 0.45)
        if c1 <= t_start or c0 >= t_end:
            continue
        for wi, w in enumerate(ch):
            w0 = w["start_s"] if wi > 0 else c0
            w1 = ch[wi + 1]["start_s"] if wi + 1 < len(ch) else c1
            a, b = max(w0, t_start) - t_start, min(w1, t_end) - t_start
            if b <= a:
                continue
            parts = []
            for k, x in enumerate(ch):
                txt = _esc(x["text"].upper() if upper else x["text"])
                if k == wi:
                    parts.append(f"{{\\c{hl}\\fscx112\\fscy112}}{txt}{{\\c{base}\\fscx100\\fscy100}}")
                else:
                    parts.append(txt)
            pop = "{\\fad(40,0)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},TT,,0,0,0,,{{\\pos({width // 2},{y})}}{pop}{' '.join(parts)}")
            events += 1
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return events

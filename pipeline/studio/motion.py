"""Motion design 2D par-dessus la 3D (couche « TikTok ») : écran de smartphone (conversation, notifications,
appel entrant, post, recherche), textes qui « pop », stickers, étiquettes de personnage, compteurs, flèche
entourée, barre de progression.

Tout est DÉTERMINISTE : `motion_design.json` (écrit par le motion-designer) décrit des éléments ancrés sur les
répliques / mots (jamais de timecode) ; ce module les dessine image par image avec Pillow (formes vectorielles
originales, aucune ressource externe) et produit une piste d'incrustation (PNG avec transparence + liste ffconcat)
que le montage superpose sous les sous-titres. Mise en cache par contenu.
"""
import hashlib
import math
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import ROOT, cache_dir, read_json, sha256_json

MOTION_VERSION = "motion-v1"
TYPES = ["phone", "text_pop", "sticker", "name_tag", "counter", "arrow"]
PHONE_SCREENS = ["chat", "notification", "call", "post", "search"]
TEXT_STYLES = ["impact", "label", "typewriter"]
STICKERS = ["heart", "broken_heart", "skull", "fire", "question", "exclamation", "money", "clock", "check", "cross",
            "star", "lightning", "laugh", "sweat"]
POSITIONS = ["top", "center", "left", "right", "top_left", "top_right"]
BASE_W, BASE_H = 1080, 1920
# centres des zones (repère 1080x1920) : hors zone des sous-titres (y≈0,68) et des boutons TikTok (droite, bas)
ZONES = {"top": (540, 430), "center": (540, 860), "left": (265, 720), "right": (805, 720), "top_left": (290, 420), "top_right": (790, 420)}
DEFAULT_SCALE = {"phone": 0.9}
DEFAULT_POS = {"phone": "right", "text_pop": "top", "sticker": "top_right", "name_tag": "top_left", "counter": "top", "arrow": "center"}
DEFAULT_DUR = {"phone": 3.5, "text_pop": 1.6, "sticker": 1.4, "name_tag": 2.2, "counter": 2.0, "arrow": 1.6}
T_IN, T_OUT = 0.22, 0.18
CLOCK = "21:42"


# ------------------------------------------------------------------ polices
_FONT_CACHE = {}


def _font_path(bold=True):
    cands = []
    fd = ROOT / "assets" / "fonts"
    if fd.is_dir():
        files = sorted(list(fd.glob("*.ttf")) + list(fd.glob("*.otf")))
        heavy = [f for f in files if re.search(r"(Black|ExtraBold|Bold|Heavy)", f.name, re.I)]
        cands += (heavy + files) if bold else ([f for f in files if f not in heavy] + files)
    if sys.platform.startswith("win"):
        wd = Path("C:/Windows/Fonts")
        cands += [wd / n for n in (("arialbd.ttf", "segoeuib.ttf", "arial.ttf") if bold else ("arial.ttf", "segoeui.ttf"))]
    else:
        try:
            r = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold" if bold else "DejaVu Sans"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                cands.append(Path(r.stdout.strip()))
        except (OSError, subprocess.SubprocessError):
            pass
        cands += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
                  Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf")]
    for c in cands:
        if c.exists():
            return str(c)
    return None


def font(size, bold=True):
    size = max(6, int(size))
    k = (size, bold)
    if k not in _FONT_CACHE:
        p = _font_path(bold)
        _FONT_CACHE[k] = ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
    return _FONT_CACHE[k]


def clean(text):
    """Retire les émojis/symboles que les polices ne savent pas dessiner (utiliser les stickers à la place)."""
    out = []
    for ch in str(text or ""):
        if ord(ch) > 0xFFFF or unicodedata.category(ch) == "So" or 0x2600 <= ord(ch) <= 0x27BF or 0xFE00 <= ord(ch) <= 0xFE0F:
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def wrap(text, f, max_w):
    words, lines, cur = clean(text).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def hexcol(h, a=255, default="#FF2D55"):
    h = (h or default).lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x):
    return 1 - (1 - x) ** 3


# ------------------------------------------------------------------ temps
def anchor_time(at, segs):
    seg = segs.get(at["line"])
    if seg is None:
        raise ValueError(f"réplique inconnue {at['line']}")
    if "word" in at:
        w = seg["words"][min(at["word"], len(seg["words"]) - 1)]
        t = w["end_s"] if at.get("edge") == "end" else w["start_s"]
    else:
        t = seg["end_s"] if at.get("edge") == "end" else seg["start_s"]
    return t + at.get("offset_s", 0.0)


def resolve(md, timeline):
    """-> liste d'éléments avec t0, t1 (et temps absolus des messages), triés, bornés à la durée."""
    segs = {s["line_id"]: s for s in timeline["segments"]}
    dur = timeline["duration_s"]
    out = []
    for el in md.get("elements", []):
        e = dict(el)
        t0 = anchor_time(el["at"], segs)
        msgs = []
        for i, m in enumerate(el.get("messages", [])):
            tm = anchor_time(m["at"], segs) if m.get("at") else t0 + 0.5 + 0.9 * i
            msgs.append({**m, "t": max(t0, tm)})
        e["_msgs"] = msgs
        if el.get("until"):
            t1 = anchor_time(el["until"], segs)
        else:
            t1 = t0 + el.get("duration_s", DEFAULT_DUR[el["type"]])
        if msgs:
            t1 = max(t1, msgs[-1]["t"] + 1.2)
        t1 = min(t1, dur)
        if t1 - t0 < 0.3:
            t1 = min(dur, t0 + 0.3)
        e["_t0"], e["_t1"] = t0, t1
        out.append(e)
    return sorted(out, key=lambda e: e["_t0"])


# ------------------------------------------------------------------ éléments graphiques
def _avatar(d, cx, cy, r, color, name):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=hexcol(color, default="#8E8E93"))
    ini = (clean(name)[:1] or "?").upper()
    f = font(r * 1.05)
    d.text((cx, cy), ini, font=f, fill=(255, 255, 255, 255), anchor="mm")


def _phone_frame(s):
    W, H = int(420 * s), int(820 * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(62 * s), fill=(28, 28, 30, 255))
    d.rounded_rectangle((int(3 * s), int(3 * s), W - int(4 * s), H - int(4 * s)), radius=int(60 * s), outline=(90, 90, 96, 255), width=max(1, int(3 * s)))
    inset = int(14 * s)
    screen = (inset, inset, W - inset, H - inset)
    return im, d, screen


def _status_bar(d, screen, s, dark_text=True):
    x0, y0, x1, _ = screen
    col = (0, 0, 0, 255) if dark_text else (255, 255, 255, 255)
    d.text((x0 + int(34 * s), y0 + int(26 * s)), CLOCK, font=font(22 * s), fill=col, anchor="lm")
    bx = x1 - int(64 * s)
    d.rounded_rectangle((bx, y0 + int(17 * s), bx + int(34 * s), y0 + int(35 * s)), radius=int(5 * s), outline=col, width=max(1, int(2 * s)))
    d.rectangle((bx + int(4 * s), y0 + int(21 * s), bx + int(24 * s), y0 + int(31 * s)), fill=col)
    cx = (x0 + x1) // 2
    d.rounded_rectangle((cx - int(56 * s), y0 + int(12 * s), cx + int(56 * s), y0 + int(42 * s)), radius=int(15 * s), fill=(0, 0, 0, 255))


def _screen_layer(im, screen, s, fill):
    x0, y0, x1, y1 = screen
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(screen, radius=int(48 * s), fill=255)
    if callable(fill):
        fill(layer)
    else:
        ImageDraw.Draw(layer).rectangle(screen, fill=fill)
    return layer, mask


def _gradient(layer, box, c_top, c_bot):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(layer)
    for y in range(y0, y1):
        k = (y - y0) / max(1, y1 - y0 - 1)
        d.line((x0, y, x1, y), fill=tuple(int(a + (b - a) * k) for a, b in zip(c_top, c_bot)))


def phone_sprite(el, t, s):
    im, d, screen = _phone_frame(s)
    x0, y0, x1, y1 = screen
    scr = el.get("screen", "chat")
    contact = clean(el.get("contact", "")) or "Inconnu"
    ccol = el.get("contact_color", "#5E5CE6")
    msgs = el["_msgs"]
    dark_status = True
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    if scr == "chat":
        ld.rectangle(screen, fill=(255, 255, 255, 255))
        hb = y0 + int(150 * s)
        # zone de saisie
        ld.rounded_rectangle((x0 + int(20 * s), y1 - int(72 * s), x1 - int(20 * s), y1 - int(24 * s)), radius=int(24 * s), outline=(200, 200, 205, 255), width=max(1, int(2 * s)))
        ld.text((x0 + int(44 * s), y1 - int(48 * s)), "Message", font=font(21 * s, False), fill=(170, 170, 175, 255), anchor="lm")
        area_top, area_bot = hb + int(16 * s), y1 - int(90 * s)
        f = font(27 * s, False)
        maxw = (x1 - x0) * 0.70
        bubbles = []
        for m in msgs:
            me = m.get("from", "them") == "me"
            if m["t"] <= t:
                bubbles.append(("msg", me, wrap(m["text"], f, maxw), clamp((t - m["t"]) / 0.18)))
            elif not me and m.get("typing", True) and m["t"] - 0.75 <= t:
                bubbles.append(("typing", False, None, 1.0))
                break
            else:
                break
        lh = int(33 * s)
        pad = int(14 * s)
        heights = [(len(b[2]) * lh + 2 * pad) if b[0] == "msg" else int(50 * s) for b in bubbles]
        total = sum(heights) + int(12 * s) * len(bubbles)
        y = area_top - max(0, total - (area_bot - area_top))
        for b, h in zip(bubbles, heights):
            kind, me, lines, p = b
            if kind == "typing":
                bx = x0 + int(20 * s)
                ld.rounded_rectangle((bx, y, bx + int(96 * s), y + h), radius=int(22 * s), fill=(233, 233, 235, 255))
                for k in range(3):
                    ph = math.sin(t * 9 - k * 0.9)
                    cy = y + h // 2 - int(5 * s * max(0, ph))
                    cx = bx + int((28 + 20 * k) * s)
                    r = int(7 * s)
                    ld.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(140, 140, 145, 255))
            else:
                tw = max(f.getlength(l) for l in lines) + 2 * pad
                yy = y + int((1 - ease_out(p)) * 24 * s)
                if me:
                    bx1 = x1 - int(20 * s)
                    box = (bx1 - tw, yy, bx1, yy + h)
                    fill, tc = (10, 132, 255, int(255 * p)), (255, 255, 255, int(255 * p))
                else:
                    bx0 = x0 + int(20 * s)
                    box = (bx0, yy, bx0 + tw, yy + h)
                    fill, tc = (233, 233, 235, int(255 * p)), (0, 0, 0, int(255 * p))
                if box[1] >= area_top - h:
                    ld.rounded_rectangle(box, radius=int(22 * s), fill=fill)
                    for k, l in enumerate(lines):
                        ld.text((box[0] + pad, yy + pad + k * lh), l, font=f, fill=tc)
            y += h + int(12 * s)
        # le haut de la conversation passe sous l'en-tête
        ld.rectangle((x0, y0, x1, hb), fill=(242, 242, 247, 255))
        ld.line((x0, hb, x1, hb), fill=(210, 210, 215, 255), width=max(1, int(2 * s)))
        ld.text((x0 + int(26 * s), y0 + int(100 * s)), "<", font=font(40 * s), fill=(10, 132, 255, 255), anchor="mm")
        _avatar(ld, x0 + int(90 * s), y0 + int(100 * s), int(30 * s), ccol, contact)
        ld.text((x0 + int(132 * s), y0 + int(88 * s)), contact[:16], font=font(28 * s), fill=(0, 0, 0, 255), anchor="lm")
        ld.text((x0 + int(132 * s), y0 + int(120 * s)), "en ligne", font=font(19 * s, False), fill=(52, 199, 89, 255), anchor="lm")
    elif scr == "notification":
        dark_status = False
        base = hexcol(ccol)
        _gradient(layer, screen, tuple(min(255, int(c * 0.9 + 40)) for c in base[:3]) + (255,), (18, 18, 40, 255))
        ld.text(((x0 + x1) // 2, y0 + int(150 * s)), CLOCK, font=font(92 * s), fill=(255, 255, 255, 255), anchor="mm")
        ld.text(((x0 + x1) // 2, y0 + int(212 * s)), "mardi 12 novembre", font=font(22 * s, False), fill=(235, 235, 245, 255), anchor="mm")
        items = list(msgs) or [{"text": el.get("text", ""), "t": el["_t0"] + 0.25}]
        shown = [m for m in items if m["t"] <= t]
        y = y0 + int(270 * s)
        fb, ft = font(25 * s), font(24 * s, False)
        app = clean(el.get("app", "Messages"))[:18]
        for k, m in enumerate(reversed(shown)):   # la plus récente en haut
            p = ease_out(clamp((t - m["t"]) / 0.22))
            lines = wrap(m["text"], ft, (x1 - x0) - int(80 * s))[:3]
            h = int((90 + 30 * len(lines)) * s)
            yy = y - int((1 - p) * 120 * s) if k == 0 else y
            ld.rounded_rectangle((x0 + int(16 * s), yy, x1 - int(16 * s), yy + h), radius=int(24 * s), fill=(250, 250, 252, int(235 * p)))
            ix = x0 + int(32 * s)
            ld.rounded_rectangle((ix, yy + int(14 * s), ix + int(34 * s), yy + int(48 * s)), radius=int(9 * s), fill=hexcol(ccol))
            ld.text((ix + int(46 * s), yy + int(31 * s)), f"{app.upper()}   maintenant", font=font(16 * s, False), fill=(110, 110, 115, int(255 * p)), anchor="lm")
            title = clean(m.get("title") or contact)
            ld.text((ix, yy + int(58 * s)), title[:24], font=fb, fill=(0, 0, 0, int(255 * p)))
            for j, l in enumerate(lines):
                ld.text((ix, yy + int((90 + 30 * j) * s)), l, font=ft, fill=(30, 30, 30, int(255 * p)))
            y += h + int(12 * s)
            if y > y1 - int(120 * s):
                break
    elif scr == "call":
        dark_status = False
        _gradient(layer, screen, (40, 52, 64, 255), (12, 16, 20, 255))
        cx = (x0 + x1) // 2
        ld.text((cx, y0 + int(120 * s)), "appel entrant...", font=font(22 * s, False), fill=(210, 210, 215, 255), anchor="mm")
        ld.text((cx, y0 + int(165 * s)), contact[:16], font=font(40 * s), fill=(255, 255, 255, 255), anchor="mm")
        cy = y0 + int(360 * s)
        for k in range(3):
            ph = ((t * 0.9) + k / 3.0) % 1.0
            r = int((95 + 90 * ph) * s)
            ld.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, int(110 * (1 - ph))), width=max(1, int(4 * s)))
        _avatar(ld, cx, cy, int(90 * s), ccol, contact)
        by = y1 - int(130 * s)
        pulse = 1 + 0.08 * math.sin(t * 8)
        for bx, colr, lab, sc_ in ((x0 + int(100 * s), (255, 59, 48, 255), "Refuser", 1.0), (x1 - int(100 * s), (52, 199, 89, 255), "Accepter", pulse)):
            r = int(46 * s * sc_)
            ld.ellipse((bx - r, by - r, bx + r, by + r), fill=colr)
            ld.rounded_rectangle((bx - int(24 * s), by - int(8 * s), bx + int(24 * s), by + int(8 * s)), radius=int(8 * s), fill=(255, 255, 255, 255))
            ld.text((bx, by + int(72 * s)), lab, font=font(19 * s, False), fill=(235, 235, 240, 255), anchor="mm")
    elif scr == "post":
        ld.rectangle(screen, fill=(255, 255, 255, 255))
        hy = y0 + int(84 * s)
        _avatar(ld, x0 + int(46 * s), hy, int(22 * s), ccol, contact)
        ld.text((x0 + int(80 * s), hy), clean(contact).lower().replace(" ", "_")[:18], font=font(21 * s), fill=(0, 0, 0, 255), anchor="lm")
        ld.text((x1 - int(30 * s), hy), "...", font=font(24 * s), fill=(0, 0, 0, 255), anchor="mm")
        iy0, iy1 = hy + int(36 * s), hy + int(36 * s) + (x1 - x0)
        base = hexcol(ccol)
        _gradient(layer, (x0, iy0, x1, iy1), base[:3] + (255,), tuple(int(c * 0.55) for c in base[:3]) + (255,))
        cap = el.get("text", "")
        if cap:
            fcap = font(38 * s)
            ls = wrap(cap, fcap, (x1 - x0) - int(60 * s))[:4]
            for j, l in enumerate(ls):
                ld.text(((x0 + x1) // 2, (iy0 + iy1) // 2 + int((j - (len(ls) - 1) / 2) * 46 * s)), l, font=fcap, fill=(255, 255, 255, 255),
                        anchor="mm", stroke_width=max(1, int(3 * s)), stroke_fill=(0, 0, 0, 160))
        ay = iy1 + int(36 * s)
        lf, lt_ = el.get("likes_from", 0), el.get("likes_to", el.get("likes_from", 0))
        k = ease_out(clamp((t - el["_t0"] - 0.3) / max(0.5, (el["_t1"] - el["_t0"]) * 0.6)))
        likes = int(round(lf + (lt_ - lf) * k))
        liked = lt_ > lf and k > 0.05
        _heart(ld, x0 + int(40 * s), ay, int(17 * s), (255, 48, 64, 255) if liked else None, (0, 0, 0, 255), s)
        ld.text((x0 + int(70 * s), ay), _fmt_num(likes) + " j'aime", font=font(21 * s), fill=(0, 0, 0, 255), anchor="lm")
        cy = ay + int(40 * s)
        fc, fcb = font(19 * s, False), font(19 * s)
        for m in msgs:
            if m["t"] > t or cy > y1 - int(40 * s):
                break
            who = clean(m.get("title") or ("moi" if m.get("from") == "me" else contact))[:14]
            ld.text((x0 + int(24 * s), cy), who, font=fcb, fill=(0, 0, 0, 255))
            wx = x0 + int(32 * s) + fcb.getlength(who)
            for j, l in enumerate(wrap(m["text"], fc, x1 - wx - int(20 * s))[:2]):
                ld.text((wx if j == 0 else x0 + int(24 * s), cy + j * int(26 * s)), l, font=fc, fill=(30, 30, 30, 255))
            cy += int(58 * s)
    elif scr == "search":
        ld.rectangle(screen, fill=(255, 255, 255, 255))
        cx = (x0 + x1) // 2
        ld.text((cx, y0 + int(150 * s)), clean(el.get("app", "Recherche"))[:16], font=font(44 * s), fill=hexcol(ccol), anchor="mm")
        by0 = y0 + int(210 * s)
        ld.rounded_rectangle((x0 + int(22 * s), by0, x1 - int(22 * s), by0 + int(58 * s)), radius=int(29 * s), fill=(241, 243, 244, 255))
        mx, my = x0 + int(52 * s), by0 + int(29 * s)
        ld.ellipse((mx - int(10 * s), my - int(12 * s), mx + int(8 * s), my + int(6 * s)), outline=(110, 110, 115, 255), width=max(1, int(3 * s)))
        ld.line((mx + int(5 * s), my + int(4 * s), mx + int(13 * s), my + int(12 * s)), fill=(110, 110, 115, 255), width=max(1, int(3 * s)))
        q = clean(el.get("query", el.get("text", "")))
        type_end = el["_t0"] + 0.25 + 0.045 * len(q)
        n = int(len(q) * clamp((t - el["_t0"] - 0.25) / max(0.1, type_end - el["_t0"] - 0.25)))
        fq = font(22 * s, False)
        shown = q[:n]
        while shown and fq.getlength(shown) > (x1 - x0) - int(110 * s):
            shown = shown[1:]
        ld.text((mx + int(26 * s), my), shown, font=fq, fill=(20, 20, 20, 255), anchor="lm")
        if int(t * 2.5) % 2 == 0 or t < type_end:
            cxr = mx + int(28 * s) + fq.getlength(shown)
            ld.line((cxr, my - int(13 * s), cxr, my + int(13 * s)), fill=(10, 132, 255, 255), width=max(1, int(2 * s)))
        ry = by0 + int(96 * s)
        results = [m["text"] for m in msgs] or ["", "", ""]
        fr = font(22 * s)
        for i, r_ in enumerate(results[:5]):
            tr = type_end + 0.25 + 0.3 * i
            if t < tr:
                break
            p = ease_out(clamp((t - tr) / 0.2))
            ld.rounded_rectangle((x0 + int(26 * s), ry, x0 + int(170 * s), ry + int(12 * s)), radius=int(6 * s), fill=(200, 200, 205, int(255 * p)))
            if r_:
                for j, l in enumerate(wrap(r_, fr, (x1 - x0) - int(60 * s))[:2]):
                    ld.text((x0 + int(26 * s), ry + int((22 + 28 * j) * s)), l, font=fr, fill=(26, 13, 171, int(255 * p)))
            else:
                ld.rounded_rectangle((x0 + int(26 * s), ry + int(26 * s), x1 - int(60 * s), ry + int(44 * s)), radius=int(8 * s), fill=(26, 13, 171, int(140 * p)))
            ld.rounded_rectangle((x0 + int(26 * s), ry + int(84 * s), x1 - int(40 * s), ry + int(96 * s)), radius=int(6 * s), fill=(225, 225, 230, int(255 * p)))
            ry += int(128 * s)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(screen, radius=int(48 * s), fill=255)
    clipped = Image.new("RGBA", im.size, (0, 0, 0, 0))
    clipped.paste(layer, (0, 0), Image.composite(layer.getchannel("A"), Image.new("L", im.size, 0), mask))
    im.alpha_composite(clipped)
    _status_bar(ImageDraw.Draw(im), screen, s, dark_status)
    return _with_shadow(im, s)


def _fmt_num(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " M"
    if n >= 10_000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " k"
    return f"{n:,}".replace(",", " ")


def _heart(d, cx, cy, r, fill, outline, s):
    pts = []
    for k in range(60):
        a = 2 * math.pi * k / 60
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * r / 16, cy + y * r / 16))
    if fill:
        d.polygon(pts, fill=fill)
    else:
        d.line(pts + [pts[0]], fill=outline, width=max(1, int(3 * s)), joint="curve")


def _with_shadow(im, s, off=10, blur=12, alpha=110):
    pad = int((blur * 2 + off) * s)
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: v * alpha // 255)
    sh.paste((0, 0, 0, 255), (pad + int(off * s), pad + int(off * s)), a)
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, blur * s)))
    out.alpha_composite(sh)
    out.alpha_composite(im, (pad, pad))
    return out


def _stickerize(icon, s, border=10):
    """Bord blanc épais + ombre portée : look « sticker »."""
    b = max(1, int(border * s))
    pad = b * 3
    big = Image.new("RGBA", (icon.width + 2 * pad, icon.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(icon, (pad, pad))
    a = big.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    k = 2 * (b // 2) + 1
    for _ in range(2):
        a = a.filter(ImageFilter.MaxFilter(min(k, 15)))
    border_l = Image.new("RGBA", big.size, (255, 255, 255, 0))
    border_l.putalpha(a)
    border_l.alpha_composite(big)
    return _with_shadow(border_l, s, off=6, blur=8, alpha=120)


def sticker_sprite(el, t, s):
    S = int(200 * s)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S // 2
    ic = el.get("icon", "heart")
    blk = (25, 25, 25, 255)
    lw = max(2, int(7 * s))
    if ic in ("heart", "broken_heart"):
        _heart(d, c, c + int(6 * s), int(80 * s), (255, 45, 85, 255), None, s)
        if ic == "broken_heart":
            zz = [(c + int(4 * s), int(30 * s)), (c - int(14 * s), int(70 * s)), (c + int(12 * s), int(100 * s)), (c - int(10 * s), int(135 * s)), (c + int(2 * s), S - int(28 * s))]
            d.line(zz, fill=(0, 0, 0, 0), width=max(2, int(12 * s)))
    elif ic == "skull":
        d.ellipse((int(30 * s), int(18 * s), S - int(30 * s), int(150 * s)), fill=(245, 245, 240, 255), outline=blk, width=lw)
        d.rounded_rectangle((int(62 * s), int(120 * s), S - int(62 * s), int(182 * s)), radius=int(14 * s), fill=(245, 245, 240, 255), outline=blk, width=lw)
        for ex in (c - int(34 * s), c + int(34 * s)):
            d.ellipse((ex - int(24 * s), int(70 * s), ex + int(24 * s), int(118 * s)), fill=blk)
        d.polygon([(c, int(118 * s)), (c - int(11 * s), int(138 * s)), (c + int(11 * s), int(138 * s))], fill=blk)
        for tx in range(-2, 3):
            d.line((c + tx * int(14 * s), int(150 * s), c + tx * int(14 * s), int(178 * s)), fill=blk, width=max(1, int(4 * s)))
    elif ic == "fire":
        for scale_, col in ((1.0, (255, 87, 34, 255)), (0.72, (255, 167, 38, 255)), (0.45, (255, 235, 59, 255))):
            r = int(62 * s * scale_)
            cy = int(S - 30 * s - r)
            d.ellipse((c - r, cy - r, c + r, cy + r), fill=col)
            d.polygon([(c - r * 0.95, cy - r * 0.2), (c + r * 0.95, cy - r * 0.2), (c + r * 0.15, cy - r * 2.3)], fill=col)
    elif ic in ("question", "exclamation"):
        col = (255, 214, 10, 255) if ic == "question" else (255, 45, 85, 255)
        d.text((c, c), "?" if ic == "question" else "!", font=font(170 * s), fill=col, anchor="mm", stroke_width=max(2, int(8 * s)), stroke_fill=blk)
    elif ic == "money":
        for k, rot in enumerate((-12, 8)):
            note = Image.new("RGBA", (int(170 * s), int(92 * s)), (0, 0, 0, 0))
            nd = ImageDraw.Draw(note)
            nd.rounded_rectangle((0, 0, note.width - 1, note.height - 1), radius=int(10 * s), fill=(76, 175, 80, 255), outline=(27, 94, 32, 255), width=max(2, int(5 * s)))
            nd.ellipse((note.width // 2 - int(28 * s), note.height // 2 - int(28 * s), note.width // 2 + int(28 * s), note.height // 2 + int(28 * s)), fill=(200, 230, 201, 255))
            nd.text((note.width // 2, note.height // 2), "€", font=font(44 * s), fill=(27, 94, 32, 255), anchor="mm")
            note = note.rotate(rot, expand=True, resample=Image.BICUBIC)
            im.alpha_composite(note, (int((10 + 14 * k) * s), int((40 + 30 * k) * s)))
    elif ic == "clock":
        r = int(80 * s)
        d.ellipse((c - r, c - r, c + r, c + r), fill=(255, 255, 255, 255), outline=blk, width=lw)
        for k in range(12):
            a = k * math.pi / 6
            d.line((c + 0.8 * r * math.sin(a), c - 0.8 * r * math.cos(a), c + 0.92 * r * math.sin(a), c - 0.92 * r * math.cos(a)), fill=blk, width=max(1, int(4 * s)))
        a1, a2 = t * 6.0, t * 0.5
        d.line((c, c, c + 0.75 * r * math.sin(a1), c - 0.75 * r * math.cos(a1)), fill=(255, 45, 85, 255), width=max(2, int(6 * s)))
        d.line((c, c, c + 0.5 * r * math.sin(a2), c - 0.5 * r * math.cos(a2)), fill=blk, width=max(2, int(9 * s)))
    elif ic in ("check", "cross"):
        r = int(80 * s)
        d.ellipse((c - r, c - r, c + r, c + r), fill=(52, 199, 89, 255) if ic == "check" else (255, 59, 48, 255))
        w = max(3, int(20 * s))
        if ic == "check":
            d.line([(c - int(40 * s), c), (c - int(10 * s), c + int(32 * s)), (c + int(44 * s), c - int(32 * s))], fill=(255, 255, 255, 255), width=w, joint="curve")
        else:
            k = int(36 * s)
            d.line((c - k, c - k, c + k, c + k), fill=(255, 255, 255, 255), width=w)
            d.line((c - k, c + k, c + k, c - k), fill=(255, 255, 255, 255), width=w)
    elif ic == "star":
        pts = []
        for k in range(10):
            r = (85 if k % 2 == 0 else 36) * s
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((c + r * math.cos(a), c + int(6 * s) + r * math.sin(a)))
        d.polygon(pts, fill=(255, 214, 10, 255), outline=blk)
    elif ic == "lightning":
        pts = [(0.58, 0.05), (0.22, 0.55), (0.48, 0.55), (0.36, 0.95), (0.80, 0.40), (0.54, 0.40), (0.70, 0.05)]
        d.polygon([(x * S, y * S) for x, y in pts], fill=(255, 214, 10, 255), outline=blk)
    elif ic in ("laugh", "sweat"):
        r = int(80 * s)
        d.ellipse((c - r, c - r, c + r, c + r), fill=(255, 204, 0, 255), outline=(200, 140, 0, 255), width=max(2, int(4 * s)))
        if ic == "laugh":
            for ex in (c - int(30 * s), c + int(30 * s)):
                d.arc((ex - int(18 * s), c - int(36 * s), ex + int(18 * s), c - int(6 * s)), 200, 340, fill=blk, width=max(2, int(6 * s)))
            d.chord((c - int(46 * s), c - int(2 * s), c + int(46 * s), c + int(56 * s)), 0, 180, fill=(120, 30, 30, 255))
            for sx in (-1, 1):
                tx = c + sx * int(70 * s)
                d.ellipse((tx - int(14 * s), c - int(14 * s), tx + int(14 * s), c + int(22 * s)), fill=(64, 156, 255, 255))
        else:
            for ex in (c - int(28 * s), c + int(28 * s)):
                d.ellipse((ex - int(9 * s), c - int(26 * s), ex + int(9 * s), c - int(4 * s)), fill=blk)
            d.arc((c - int(30 * s), c + int(18 * s), c + int(30 * s), c + int(48 * s)), 200, 340, fill=blk, width=max(2, int(6 * s)))
            dx, dy = c + int(58 * s), c - int(40 * s)
            d.ellipse((dx - int(16 * s), dy - int(4 * s), dx + int(16 * s), dy + int(30 * s)), fill=(64, 156, 255, 255))
            d.polygon([(dx - int(14 * s), dy + int(6 * s)), (dx + int(14 * s), dy + int(6 * s)), (dx, dy - int(22 * s))], fill=(64, 156, 255, 255))
    spr = _stickerize(im, s)
    return spr.rotate(math.sin(t * 7.0) * 7.0, resample=Image.BICUBIC, expand=True)


def text_sprite(el, t, s):
    style = el.get("style", "impact")
    txt = clean(el.get("text", ""))
    if style == "impact":
        txt = txt.upper()
        size = 100 * s
        f = font(size)
        while f.getlength(txt) > 940 * s and size > 40 * s:
            size *= 0.92
            f = font(size)
        lines = wrap(txt, f, 940 * s)[:3]
        lh = int(size * 1.08)
        W = int(max(f.getlength(l) for l in lines) + 60 * s)
        H = lh * len(lines) + int(50 * s)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for k, l in enumerate(lines):
            d.text((W // 2, int(25 * s) + lh * k + lh // 2), l, font=f, fill=hexcol(el.get("color"), default="#FFFFFF"), anchor="mm",
                   stroke_width=max(2, int(size * 0.1)), stroke_fill=(0, 0, 0, 255))
        im = _with_shadow(im, s, off=6, blur=6, alpha=140)
        return im.rotate(-3 + math.sin(t * 5) * 1.2, resample=Image.BICUBIC, expand=True)
    f = font(58 * s)
    if style == "typewriter":
        n = int(len(txt) * clamp((t - el["_t0"]) / max(0.3, min(1.0, 0.05 * len(txt)))))
        shown = txt[:n] + ("|" if int(t * 3) % 2 == 0 else " ")
    else:
        shown = txt
    lines = wrap(txt, f, 860 * s)[:3]
    W = int(max(f.getlength(l) for l in lines) + 70 * s)
    lh = int(70 * s)
    H = lh * len(lines) + int(36 * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(26 * s), fill=hexcol(el.get("color"), default="#FF2D55"))
    rem = shown
    for k, l in enumerate(lines):
        part = rem[:len(l)] if style == "typewriter" else l
        rem = rem[len(l):].lstrip() if style == "typewriter" else rem
        d.text((int(35 * s), int(18 * s) + lh * k + lh // 2), part, font=f, fill=(255, 255, 255, 255), anchor="lm")
    return _with_shadow(im, s, off=8, blur=10, alpha=120)


def name_tag_sprite(el, t, s):
    name, sub = clean(el.get("text", "")), clean(el.get("subtitle", ""))
    fn, fs = font(54 * s), font(30 * s, False)
    W = int(max(fn.getlength(name), fs.getlength(sub) if sub else 0) + 90 * s)
    W = min(W, int(900 * s))
    H = int((112 if sub else 84) * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(22 * s), fill=(255, 255, 255, 245))
    d.rounded_rectangle((0, 0, int(22 * s), H - 1), radius=int(10 * s), fill=hexcol(el.get("color")))
    d.text((int(44 * s), int(14 * s)), name, font=fn, fill=(20, 20, 24, 255))
    if sub:
        d.text((int(46 * s), int(72 * s)), sub, font=fs, fill=(95, 95, 105, 255))
    return _with_shadow(im, s, off=8, blur=10, alpha=110)


def counter_sprite(el, t, s):
    a, b = float(el.get("value_from", 0)), float(el["value_to"])
    dec = int(el.get("decimals", 0))
    span = min(1.2, max(0.4, (el["_t1"] - el["_t0"]) * 0.5))
    k = ease_out(clamp((t - el["_t0"] - 0.1) / span))
    v = a + (b - a) * k
    num = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    pre, suf = el.get("prefix", ""), el.get("suffix", "")
    txt = f"{clean(pre)}{' ' if pre.endswith(' ') else ''}{num}{' ' if suf.startswith(' ') else ''}{clean(suf)}"
    size = 120 * s
    f = font(size)
    widest = f"{clean(pre)}{b:,.{dec}f}{clean(suf)}  "
    while f.getlength(widest) > 940 * s and size > 40 * s:   # le nombre final doit tenir dans l'image
        size *= 0.92
        f = font(size)
    lab = clean(el.get("label", ""))
    fl = font(34 * s)
    W = int(max(f.getlength(widest), fl.getlength(lab) + 50 * s if lab else 0) + 80 * s)
    H = int(size * 1.25 + (70 * s if lab else 0))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 0
    if lab:
        lw_ = int(fl.getlength(lab) + 44 * s)
        d.rounded_rectangle(((W - lw_) // 2, 0, (W + lw_) // 2, int(56 * s)), radius=int(28 * s), fill=hexcol(el.get("color"), default="#111111"))
        d.text((W // 2, int(28 * s)), lab, font=fl, fill=(255, 255, 255, 255), anchor="mm")
        y = int(66 * s)
    bump = 1.0 + 0.12 * math.sin(math.pi * clamp((t - el["_t0"] - 0.1 - span) / 0.25))
    tf = font(size * bump)
    d.text((W // 2, y + int(size * 0.62)), txt, font=tf, fill=hexcol(el.get("number_color"), default="#FFE600"), anchor="mm",
           stroke_width=max(2, int(size * 0.09)), stroke_fill=(0, 0, 0, 255))
    return _with_shadow(im, s, off=6, blur=6, alpha=130)


def draw_arrow(canvas, el, t, s, W, H):
    tx, ty = el.get("target", [0.5, 0.45])
    px, py = tx * W, ty * H
    d = ImageDraw.Draw(canvas)
    p = ease_out(clamp((t - el["_t0"]) / 0.35))
    col = hexcol(el.get("color"), default="#FF2D2D")
    r = 105 * s
    lw = max(3, int(13 * s))
    d.arc((px - r, py - r * 0.85, px + r, py + r * 0.85), -100, -100 + 370 * p, fill=col, width=lw)
    # la flèche vient du côté le plus dégagé (vers le centre de l'image)
    sx = px + (-300 * s if px > W / 2 else 300 * s)
    sy = py - 260 * s if py > H * 0.35 else py + 260 * s
    q = ease_out(clamp((t - el["_t0"] - 0.15) / 0.3))
    ang = math.atan2(py - sy, px - sx)
    ex, ey = px - math.cos(ang) * (r + 18 * s), py - math.sin(ang) * (r + 18 * s)
    hx, hy = sx + (ex - sx) * q, sy + (ey - sy) * q
    if q > 0:
        d.line((sx, sy, hx, hy), fill=col, width=lw)
        hs = 42 * s
        for da in (2.6, -2.6):
            d.line((hx, hy, hx + hs * math.cos(ang + da), hy + hs * math.sin(ang + da)), fill=col, width=lw)
    lab = clean(el.get("label", ""))
    if lab and q > 0.5:
        f = font(52 * s)
        d.text((sx, sy + (-40 * s if sy < py else 40 * s)), lab.upper(), font=f, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=max(2, int(7 * s)), stroke_fill=(0, 0, 0, 255))


SPRITES = {"phone": phone_sprite, "text_pop": text_sprite, "sticker": sticker_sprite, "name_tag": name_tag_sprite, "counter": counter_sprite}


def render_canvas(elements, t, W, H, base=None):
    """Image RGBA (W,H) des éléments actifs à l'instant t (secondes, temps de la narration)."""
    s = W / BASE_W
    canvas = base.copy() if base is not None else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    active = False
    for el in elements:
        t0, t1 = el["_t0"], el["_t1"]
        if not (t0 <= t < t1):
            continue
        active = True
        sc = s * float(el.get("scale", DEFAULT_SCALE.get(el["type"], 1.0)))
        if el["type"] == "arrow":
            draw_arrow(canvas, el, t, sc, W, H)
            continue
        spr = SPRITES[el["type"]](el, t, sc)
        pin = clamp((t - t0) / T_IN)
        pout = clamp((t1 - t) / T_OUT)
        pos = el.get("position", DEFAULT_POS[el["type"]])
        cx, cy = ZONES[pos]
        cx, cy = cx * s, cy * s
        k, alpha, dx = 1.0, 1.0, 0.0
        if el["type"] in ("phone", "name_tag"):
            side = -1 if (pos.endswith("left") or (el["type"] == "phone" and pos == "center")) else 1
            dx = side * (1 - ease_out(pin)) * (W * 0.6)
        else:
            k = 0.35 + 0.65 * ease_out_back(pin)
        if pout < 1:
            k *= 0.85 + 0.15 * pout
            alpha = pout
        if k != 1.0:
            spr = spr.resize((max(1, int(spr.width * k)), max(1, int(spr.height * k))), Image.BILINEAR)
        if alpha < 1:
            spr.putalpha(spr.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        x = int(cx - spr.width / 2 + dx)
        y = int(cy - spr.height / 2)
        x = max(-spr.width, min(W, x))
        canvas.alpha_composite(spr, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    return canvas, active


# ------------------------------------------------------------------ piste d'incrustation
def load(ep_dir):
    p = Path(ep_dir) / "motion_design.json"
    return read_json(p) if p.exists() else None


def build_overlay(cfg, ep_dir, timeline, W, H, fps, t0, t1):
    """-> chemin d'une liste ffconcat (PNG transparents) couvrant [t0,t1], ou None s'il n'y a rien à incruster."""
    md = load(ep_dir)
    if not md or not md.get("elements"):
        return None
    els = [e for e in resolve(md, timeline) if e["_t1"] > t0 and e["_t0"] < t1]
    if not els:
        return None
    key = sha256_json({"v": MOTION_VERSION, "md": md, "segs": [(s["line_id"], s["start_s"], s["end_s"], [(w["start_s"], w["end_s"]) for w in s["words"]]) for s in timeline["segments"]],
                       "res": [W, H], "fps": fps, "t": [round(t0, 3), round(t1, 3)], "font": _font_path(True), "font2": _font_path(False)})
    d = cache_dir(cfg) / "motion" / key
    lst = d / "overlay.ffconcat"
    if lst.exists():
        return lst
    d.mkdir(parents=True, exist_ok=True)
    empty = d / "empty.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(empty)
    n = int(round((t1 - t0) * fps))
    entries = []   # [png, nb_images]
    last_hash, k = None, 0
    for i in range(n):
        t = t0 + i / fps
        if not any(e["_t0"] <= t < e["_t1"] for e in els):
            png, h = empty, "empty"
        else:
            cv, _ = render_canvas(els, t, W, H)
            h = hashlib.md5(cv.tobytes()).hexdigest()
            if h == last_hash:
                entries[-1][1] += 1
                continue
            png = d / f"o{k:05d}.png"
            k += 1
            cv.save(png, compress_level=1)
        if h == last_hash:
            entries[-1][1] += 1
        else:
            entries.append([png, 1])
            last_hash = h
    lines = ["ffconcat version 1.0"]
    for png, cnt in entries:
        lines += [f"file '{Path(png).as_posix()}'", f"duration {cnt / fps:.6f}"]
    lines.append(f"file '{Path(entries[-1][0]).as_posix()}'")
    tmp = lst.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(lst)
    return lst


def progress_settings(md):
    g = (md or {}).get("globals", {})
    if md is None or not g.get("progress_bar", True):
        return None
    return {"color": g.get("progress_color", "#FF2D55")}


# ------------------------------------------------------------------ aide au motion-designer
KEYWORDS = [
    (r"(t[ée]l[ée]phone|portable|smartphone|[ée]cran)", "phone", "chat", "objet téléphone : montrer l'écran"),
    (r"(message|texto|sms|[ée]crit|r[ée]pond|whatsapp|snap|dm|vu\b)", "phone", "chat", "échange de messages : conversation à l'écran"),
    (r"(notif)", "phone", "notification", "notification reçue"),
    (r"(appel|appelle|sonne|t[ée]l[ée]phoner|bip)", "phone", "call", "appel entrant"),
    (r"(insta|tiktok|post|story|like|abonn|followers|vues)", "phone", "post", "réseau social : post avec likes"),
    (r"(google|cherch|recherch|tap[ée])", "phone", "search", "recherche en ligne : barre de recherche tapée"),
    (r"(€|euros?$|balles$|argent|fric$|salaire|dette|prix$|loyer|cher|pay)", "counter", None, "argent : compteur ou sticker money"),
    (r"(\d+|millions?$|milliards?$|mille$)", "counter", None, "chiffre : compteur animé"),
    (r"(jours?|heures?|minutes?|semaines?|mois|tard|lendemain)$", "text_pop", None, "ellipse temporelle : carton texte"),
    (r"(amour|aime|coeur|cœur|crush|bisou|love|rendez-vous|date)", "sticker", "heart", "amour : sticker coeur"),
    (r"(rupture|largu|quitt|trahi|cocu|tromp)", "sticker", "broken_heart", "rupture : coeur brisé"),
    (r"(mort|mourir|cimeti|crev|g[eê]nance|malaise|honte)", "sticker", "skull", "malaise/mort de honte : sticker crâne"),
    (r"(pourquoi|comment)$", "sticker", "question", "question : point d'interrogation"),
    (r"(urgent|attention|danger|alerte|stop)", "sticker", "exclamation", "alerte : point d'exclamation"),
    (r"(mdr|lol|rigol|ptdr|rire)", "sticker", "laugh", "rire : sticker rieur"),
]


def suggest(script):
    """Repère dans le script les moments propices au motion design (indices, pas des décisions)."""
    out, seen_speakers = [], set()
    for line in script["lines"]:
        words = line["text"].split()
        low = [re.sub(r"[^\wàâäéèêëîïôöùûüç€]", "", w.lower()) for w in words]
        sp = line["speaker"]
        if sp != "narrator" and sp not in seen_speakers:
            seen_speakers.add(sp)
            out.append({"line": line["id"], "word": 0, "type": "name_tag", "reason": f"première apparition de {sp} : étiquette nom + trait de caractère"})
        for pat, typ, sub, why in KEYWORDS:
            for i, w in enumerate(low):
                if re.match(pat, w):
                    item = {"line": line["id"], "word": i, "type": typ, "reason": why, "mot": words[i]}
                    if sub:
                        item["screen" if typ == "phone" else "icon"] = sub
                    out.append(item)
                    break
    return out


def preview(ep_dir, timeline, out_png, W=540, H=960):
    """Planche de contrôle : chaque élément au milieu de sa fenêtre, sur un fond neutre avec les zones TikTok."""
    from .qa import frames as qframes
    md = load(ep_dir)
    els = resolve(md, timeline) if md else []
    out_png = Path(out_png)
    tmpd = out_png.parent / "motion_preview"
    tmpd.mkdir(parents=True, exist_ok=True)
    bg = Image.new("RGBA", (W, H), (70, 74, 82, 255))
    d = ImageDraw.Draw(bg)
    d.rectangle((0, int(H * 0.64), W, int(H * 0.74)), fill=(95, 80, 80, 255))            # sous-titres
    d.rectangle((int(W * 0.89), int(H * 0.50), W, int(H * 0.86)), fill=(60, 60, 64, 255))  # boutons TikTok
    d.rectangle((0, int(H * 0.86), W, H), fill=(55, 55, 60, 255))                           # légende TikTok
    d.ellipse((int(W * 0.38), int(H * 0.30), int(W * 0.62), int(H * 0.44)), outline=(200, 200, 200, 255), width=2)  # tête d'un sujet
    items = []
    for e in els:
        t = e["_t0"] + (e["_t1"] - e["_t0"]) * 0.6
        if e["_msgs"]:
            t = min(e["_t1"] - 0.05, e["_msgs"][-1]["t"] + 0.5)
        cv, _ = render_canvas([e], t, W, H, base=bg)
        p = tmpd / f"{e['id']}.png"
        cv.convert("RGB").save(p)
        items.append((p, f"{e['id']} {e['type']} {e['_t0']:.1f}-{e['_t1']:.1f}s"))
    if not items:
        return None
    return qframes.contact_sheet(items, out_png, cols=4, title="MOTION DESIGN — un instant par élément (gris = zones TikTok/sous-titres)")

"""Extraction de frames et planches contact horodatées pour l'inspection visuelle (agents multimodaux ou humain)."""
from pathlib import Path

from ..util import run

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:   # Pillow facultatif : planche sans légende via ffmpeg
    Image = None


def extract(video, times, out_dir, prefix="t"):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in times:
        p = out_dir / f"{prefix}{t:07.2f}s.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(p)])
        paths.append(p)
    return paths


def _font(size):
    for f in ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def contact_sheet(items, out_path, cols=4, thumb_w=270, title=None):
    """items : liste de (chemin_image, légende). Retourne le chemin de la planche."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if Image is None:
        lst = out_path.with_suffix(".txt")
        lst.write_text("".join(f"file '{p}'\n" for p, _ in items))
        rows = (len(items) + cols - 1) // cols
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"scale={thumb_w}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out_path)])
        return out_path
    thumbs = []
    for p, cap in items:
        im = Image.open(p).convert("RGB")
        h = int(im.height * thumb_w / im.width)
        thumbs.append((im.resize((thumb_w, h)), cap))
    th = max(t.height for t, _ in thumbs)
    cap_h = 64
    rows = (len(thumbs) + cols - 1) // cols
    head = 50 if title else 0
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * 8, head + rows * (th + cap_h + 8) + 8), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f, fs = _font(20), _font(15)
    if title:
        d.text((10, 12), title, fill=(255, 255, 255), font=_font(24))
    for i, (im, cap) in enumerate(thumbs):
        x = 8 + (i % cols) * (thumb_w + 8)
        y = head + 8 + (i // cols) * (th + cap_h + 8)
        sheet.paste(im, (x, y))
        lines = str(cap).split("\n")
        d.text((x + 4, y + th + 4), lines[0][:30], fill=(255, 220, 90), font=f)
        for k, l in enumerate(lines[1:3]):
            d.text((x + 4, y + th + 28 + k * 17), l[:36], fill=(220, 220, 220), font=fs)
    sheet.save(out_path)
    return out_path

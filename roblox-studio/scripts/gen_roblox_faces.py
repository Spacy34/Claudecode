"""Génère les décalcomanies de bouche (style « visage de jouet en blocs », dessins ORIGINAUX) :
assets/roblox/faces/mouth_<forme>.png, transparentes, 512x256. Relancer après modification ; les PNG sont versionnés
(le Python embarqué de Blender n'a pas Pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "roblox" / "faces"
INK = (24, 20, 22, 255)
INSIDE = (70, 18, 26, 255)
TONGUE = (226, 92, 108, 255)
TEETH = (250, 250, 250, 255)
W, H = 512, 256


def canvas():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def open_shape(d, box, teeth_top=False, tongue=False, teeth_bottom=False):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=min(x1 - x0, y1 - y0) // 2, fill=INSIDE, outline=INK, width=14)
    if teeth_top:
        d.rectangle((x0 + 22, y0 + 12, x1 - 22, y0 + 12 + (y1 - y0) // 4), fill=TEETH)
    if teeth_bottom:
        d.rectangle((x0 + 30, y1 - 12 - (y1 - y0) // 5, x1 - 30, y1 - 12), fill=TEETH)
    if tongue:
        cx = (x0 + x1) // 2
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(box, radius=min(x1 - x0, y1 - y0) // 2, fill=255)
        t = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(t).ellipse((cx - (x1 - x0) // 4, y1 - (y1 - y0) // 2, cx + (x1 - x0) // 4, y1 + 30), fill=TONGUE)
        d._image.paste(t, (0, 0), Image.composite(t.getchannel("A"), Image.new("L", (W, H), 0), m))
        d.rounded_rectangle(box, radius=min(x1 - x0, y1 - y0) // 2, outline=INK, width=14)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    shapes = {}
    im, d = canvas(); d.line((176, 128, 336, 128), fill=INK, width=18); shapes["line"] = im
    im, d = canvas(); d.arc((136, 20, 376, 190), 25, 155, fill=INK, width=20); shapes["smile"] = im
    im, d = canvas(); d.arc((156, 110, 356, 270), 205, 335, fill=INK, width=20); shapes["frown"] = im
    im, d = canvas(); d.arc((190, 40, 390, 170), 15, 110, fill=INK, width=20); d.line((180, 135, 250, 150), fill=INK, width=18); shapes["smirk"] = im
    im, d = canvas(); open_shape(d, (210, 70, 302, 200)); shapes["open_o"] = im
    im, d = canvas(); open_shape(d, (150, 50, 362, 220), teeth_top=True, tongue=True); shapes["open_wide"] = im
    im, d = canvas()
    d.chord((130, -30, 382, 200), 0, 180, fill=INSIDE, outline=INK, width=14)
    d.rectangle((160, 88, 352, 120), fill=TEETH)
    shapes["grin"] = im
    im, d = canvas(); open_shape(d, (176, 70, 336, 196), tongue=True); shapes["talk_a"] = im
    im, d = canvas(); open_shape(d, (196, 92, 316, 168)); shapes["talk_b"] = im
    im, d = canvas(); open_shape(d, (150, 96, 362, 162), teeth_top=True, teeth_bottom=True); shapes["v_E"] = im
    im, d = canvas(); open_shape(d, (226, 88, 286, 172)); shapes["v_U"] = im
    im, d = canvas(); d.rounded_rectangle((186, 116, 326, 142), radius=12, fill=INK); shapes["v_M"] = im
    im, d = canvas(); open_shape(d, (176, 100, 336, 160), teeth_top=True); shapes["v_F"] = im
    for k, im in shapes.items():
        im.save(OUT / f"mouth_{k}.png")
    return sorted(shapes)


if __name__ == "__main__":
    print(build())

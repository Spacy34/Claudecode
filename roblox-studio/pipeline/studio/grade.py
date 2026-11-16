"""Étalonnage par ambiance : ce qui fait passer de « démo 3D » à « vidéo soignée ».

Appliqué à l'encodage de chaque clip (FFmpeg, déterministe, mis en cache avec le clip) :
contraste et saturation, température (ombres / tons moyens / hautes lumières séparés), gamma, vignettage léger.
L'ambiance vient du `mood` du plan ; le storyboard peut forcer une intention (`grade` : conflict, romance, sad…).
Désactivable : config [grade] enabled = false ; intensité globale [grade] strength (0–1,5).
"""

# contraste, saturation, gamma, (r,g,b ombres), (r,g,b tons moyens), (r,g,b hautes lumières), vignettage (angle π/x, 0 = aucun)
GRADES = {
    "neutral":  (1.11, 1.14, 0.97, (0, 0, 0), (0, 0, 0), (0, 0, 0), 6.0),
    "warm":     (1.14, 1.20, 0.95, (0.02, 0.0, -0.04), (0.04, 0.01, -0.03), (0.03, 0.01, -0.02), 5.5),
    "cool":     (1.12, 1.10, 0.96, (-0.02, 0.0, 0.04), (-0.01, 0.0, 0.03), (-0.01, 0.0, 0.02), 6.0),
    "night":    (1.16, 1.06, 0.95, (-0.04, -0.01, 0.08), (-0.02, 0.0, 0.04), (0.0, 0.0, 0.02), 4.5),
    "conflict": (1.24, 0.94, 0.94, (-0.03, 0.0, 0.06), (0.01, 0.0, -0.01), (0.04, 0.01, -0.03), 4.0),
    "romance":  (1.05, 1.16, 1.01, (0.03, 0.0, 0.01), (0.04, 0.0, 0.01), (0.04, 0.01, 0.02), 5.0),
    "sad":      (1.04, 0.74, 0.98, (-0.02, 0.0, 0.05), (-0.02, 0.0, 0.03), (0.0, 0.0, 0.01), 4.5),
    "spooky":   (1.20, 0.88, 0.95, (-0.02, 0.04, 0.0), (-0.02, 0.03, -0.01), (0.0, 0.02, -0.02), 4.0),
    "sunset":   (1.12, 1.20, 0.98, (0.0, -0.02, 0.04), (0.05, 0.01, -0.03), (0.05, 0.02, -0.04), 5.0),
}
MOOD_GRADE = {"day_warm": "warm", "interior_warm": "warm", "day_cool": "cool", "office_flat": "cool", "night": "night",
              "dramatic": "conflict", "spooky": "spooky", "sunset": "sunset"}
NAMES = sorted(GRADES)


def grade_for(mood, override=None):
    if override and override != "auto" and override in GRADES:
        return override
    return MOOD_GRADE.get(mood or "", "neutral")


def filters(name, cfg=None):
    """-> liste de filtres FFmpeg (vide si l'étalonnage est désactivé)."""
    g = (cfg or {}).get("grade", {})
    if not g.get("enabled", True):
        return []
    k = max(0.0, min(1.5, float(g.get("strength", 1.0))))
    c, s, gm, sh, mid, hi, vig = GRADES.get(name, GRADES["neutral"])
    lerp = (lambda v, base=1.0: base + (v - base) * k)
    cb = ":".join(f"{p}{zone}={v * k:.3f}" for zone, rgb in (("s", sh), ("m", mid), ("h", hi)) for p, v in zip("rgb", rgb) if v)
    out = []
    if cb:
        out.append(f"colorbalance={cb}")
    out.append(f"eq=contrast={lerp(c):.3f}:saturation={lerp(s):.3f}:gamma={lerp(gm):.3f}")
    if vig and g.get("vignette", True):
        # angle plus petit = vignettage plus léger ; jamais de coins noirs (lisibilité TikTok)
        out.append(f"vignette=angle=PI/{vig / max(0.4, k):.2f}")
    return out

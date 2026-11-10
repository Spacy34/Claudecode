"""Mémoire de production : fichiers Markdown versionnés, une entrée = une section `## ` avec des tags.

Jamais injectée en bloc dans le contexte : les agents interrogent `studio memory search <mots>` et ne lisent
que les quelques entrées pertinentes (classement par nombre de termes/tags correspondants).
"""
import re
from pathlib import Path

from .util import ROOT, now

CATEGORIES = {"lessons": "Leçons créatives et techniques validées", "blender_errors": "Erreurs Blender/rendu et correctifs",
              "presets": "Réglages qui fonctionnent", "creative_decisions": "Décisions créatives durables (style, ton, personnages récurrents)",
              "recurring_issues": "Problèmes récurrents relevés par les critiques"}


def mem_dir(cfg):
    return ROOT / cfg["paths"]["memory_dir"]


def entries(cfg):
    out = []
    for p in sorted(mem_dir(cfg).glob("*.md")):
        text = p.read_text(encoding="utf-8")
        for block in re.split(r"(?m)^## ", text)[1:]:
            title, _, body = block.partition("\n")
            tags = re.findall(r"(?mi)^tags:\s*(.+)$", body)
            out.append({"file": p.name, "title": title.strip(), "body": body.strip(), "tags": [t.strip().lower() for t in (tags[0].split(",") if tags else [])]})
    return out


def search(cfg, terms, limit=5):
    terms = [t.lower() for t in terms]
    scored = []
    for e in entries(cfg):
        hay = (e["title"] + " " + e["body"]).lower()
        score = sum(3 for t in terms if t in e["tags"]) + sum(hay.count(t) for t in terms)
        if score:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit]]


def add(cfg, category, title, text, tags, episode=None):
    if category not in CATEGORIES:
        raise ValueError(f"catégorie inconnue {category} ({sorted(CATEGORIES)})")
    p = mem_dir(cfg) / f"{category}.md"
    if not p.exists():
        p.write_text(f"# {CATEGORIES[category]}\n\nUne entrée par section `## `. Ajouter via `studio memory add`.\n", encoding="utf-8")
    entry = f"\n## {title}\ntags: {', '.join(tags)}\ndate: {now()[:10]}" + (f"\nepisode: {episode}" if episode else "") + f"\n\n{text.strip()}\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(entry)
    return p

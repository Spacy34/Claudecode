"""Journal des refus : POURQUOI ça bloque, et COMBIEN ça coûte (au lieu de deviner).

Chaque refus (contrat invalide, pré-vérification, critique bloquant, contrôle des plans, rendu raté) est ajouté à
`checks/rejections.jsonl` (fichier GÉNÉRÉ, une ligne par motif). Les sessions Codex (`checks/codex_tokens.jsonl`,
écrit par le pilote) qui suivent un refus de la même étape sont comptées comme coût de correction.
`studio rejets <ep>` / `studio rejets --all` et l'onglet Vérifications du tableau de bord en font la synthèse.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .util import now

FILE = "rejections.jsonl"
MAX_TEXT = 300


def _path(ep_dir):
    d = Path(ep_dir) / "checks"
    d.mkdir(exist_ok=True)
    return d / FILE


def normalize(text):
    """Motif générique d'une raison (sans ids ni nombres) : sert à regrouper « la même cause »."""
    t = str(text)
    m = re.match(r"\s*\[(?:sh_\w+)\]\s*([a-z_]+)", t)
    if m:                                  # ligne de pré-vérification « [sh_003] char_never_visible:ch_x : … »
        return m.group(1)
    m = re.match(r"\s*([a-z][a-z_]+):[\w:]+\s", t)
    if m:                                  # identifiant de contrôle « prop_in_character:pr_x:ch_y … »
        return m.group(1)
    t = re.sub(r"\b(sh|ch|pr|l|set|r)_?\d+\w*\b", "<id>", t)
    t = re.sub(r"\b\d+([.,]\d+)?\b", "<n>", t)
    t = re.sub(r"[«\"'].*?[»\"']", "<…>", t)
    return re.sub(r"\s+", " ", t).strip()[:90]


def record(ep_dir, stage, source, reasons):
    """reasons : liste de dicts {category, text, owner?, id?}. Ne lève jamais (le journal ne doit rien bloquer)."""
    try:
        with open(_path(ep_dir), "a", encoding="utf-8") as h:
            for r in reasons or [{"category": source, "text": ""}]:
                txt = str(r.get("text", ""))[:MAX_TEXT]
                h.write(json.dumps({"at": now(), "stage": stage, "source": source, "category": r.get("category") or source,
                                    "key": r.get("key") or normalize(txt), "owner": r.get("owner"), "text": txt},
                                   ensure_ascii=False) + "\n")
    except OSError:
        pass


def from_error(error):
    """Erreur texte d'une étape -> motifs (une ligne par cause quand l'erreur en liste plusieurs)."""
    e = str(error)
    if e.startswith("pré-vérification : "):
        return "pré-vérification", [{"category": "pré-vérification", "text": x} for x in e[len("pré-vérification : "):].split(" | ") if x.strip()]
    if e.startswith("{"):
        try:
            errs = json.loads(e)
            return "contrat", [{"category": f"contrat:{k}", "text": x} for k, v in errs.items() for x in (v if isinstance(v, list) else [v])]
        except ValueError:
            pass
    if "bloquant" in e and e.startswith("verdicts"):
        return "critique", []          # détaillé par record_review (un motif par finding)
    m = re.match(r"tour \d+ : [^.]*\.\s*(.*)$", e, re.S)
    if m:                              # contrôle des plans / gate auto : « [director] sh_008:char_never_visible:ch_x : … | … »
        items = [x.strip() for x in m.group(1).split(" | ") if x.strip()]
        out = []
        for x in items:
            o = re.match(r"\[([\w-]+)\]\s*(?:sh_\w+:)?([a-z][a-z_]+)", x)
            out.append({"category": "contrôle des plans", "owner": o.group(1) if o else None, "key": o.group(2) if o else None, "text": x})
        return "contrôle des plans", out or [{"category": "contrôle des plans", "text": e}]
    return "étape", [{"category": "étape", "text": e}]


def record_review(ep_dir, stage, review, blockers):
    record(ep_dir, stage, "critique", [{"category": f"critique:{review.get('reviewer')}", "owner": f.get("fix_owner"),
                                        "key": f"{review.get('reviewer')}/{f.get('category')}",
                                        "text": f"{f.get('id')} {f.get('shot_id') or ''} {f.get('description', '')}"} for f in blockers])


def load(ep_dir):
    f = Path(ep_dir) / "checks" / FILE
    out = []
    if f.exists():
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    return out


def _sessions(ep_dir):
    f = Path(ep_dir) / "checks" / "codex_tokens.jsonl"
    out = []
    if f.exists():
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    return out


def summary(ep_dirs, top=12):
    """Synthèse sur un ou plusieurs épisodes : refus par étape / catégorie, motifs les plus fréquents, tokens."""
    rej, tok_total, tok_retry = [], 0, 0
    retry_by_stage = Counter()
    for ep in ep_dirs:
        rs = load(ep)
        for r in rs:
            r["episode"] = Path(ep).name
        rej += rs
        fails = defaultdict(list)          # étape -> horodatages des refus
        for r in rs:
            fails[r["stage"]].append(r["at"])
        for s in _sessions(ep):
            t = int(s.get("tokens") or 0)
            tok_total += t
            # session de CORRECTION : elle retravaille une étape déjà refusée avant elle
            ref = s.get("started") or s.get("at", "")
            hit = [st for st in s.get("stages", []) if any(a <= ref for a in fails.get(st, []))]
            if hit:
                tok_retry += t
                for st in hit:
                    retry_by_stage[st] += t // len(hit)
    events = Counter((r["stage"], r["at"][:16]) for r in rej)   # un refus = une soumission refusée (plusieurs motifs)
    by_stage = Counter(st for st, _ in events)
    by_cat = Counter(r["category"].split(":")[0] if r["category"].startswith("contrat") else r["category"] for r in rej)
    keys = Counter((r["category"], r["key"]) for r in rej)
    examples = {}
    for r in rej:
        examples.setdefault((r["category"], r["key"]), r["text"])
    n = sum(keys.values()) or 1
    return {"episodes": len(ep_dirs), "refus": sum(events.values()), "motifs": len(rej),
            "par_etape": dict(by_stage.most_common()), "par_categorie": dict(by_cat.most_common()),
            "top_motifs": [{"categorie": c, "motif": k, "fois": v, "part": round(100 * v / n), "exemple": examples[(c, k)][:200]}
                           for (c, k), v in keys.most_common(top)],
            "tokens_total": tok_total, "tokens_corrections": tok_retry,
            "tokens_corrections_par_etape": dict(retry_by_stage.most_common())}


def format_text(s):
    lines = [f"Refus : {s['refus']} soumissions refusées ({s['motifs']} motifs) sur {s['episodes']} épisode(s)."]
    if s["tokens_total"]:
        pct = round(100 * s["tokens_corrections"] / max(1, s["tokens_total"]))
        lines.append(f"Tokens Codex : {s['tokens_total']:,} dont {s['tokens_corrections']:,} en corrections ({pct} %).".replace(",", " "))
    if s["par_etape"]:
        lines.append("Par étape : " + ", ".join(f"{k} {v}" for k, v in s["par_etape"].items()))
    if s["tokens_corrections_par_etape"]:
        lines.append("Tokens de correction par étape : " + ", ".join(f"{k} {v:,}".replace(",", " ") for k, v in s["tokens_corrections_par_etape"].items()))
    if s["top_motifs"]:
        lines.append("Motifs les plus fréquents :")
        for m in s["top_motifs"]:
            lines.append(f"  {m['part']:>3} %  {m['fois']:>3}×  [{m['categorie']}] {m['motif']}  — ex. {m['exemple'][:110]}")
    else:
        lines.append("Aucun refus enregistré.")
    return "\n".join(lines)

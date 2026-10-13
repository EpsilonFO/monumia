"""CS2 : Jev, avec la règle de production, sur les pages de l'échantillon de contrôle du tri.

Commande, depuis backend/ :

    uv run python scripts/mesures/tri_titre_jev.py

Entrées, dans backend/data/reviews/logs/refonte/ :

- 2026-10-10-tri-titre-echantillon-1/pages/<id>.md et index.tsv : le texte des
  143 pages lisibles de l'échantillon de contrôle (97 écartées au tri sur titre,
  46 gardées), tel que la lecture de prospection l'aurait jugé ;
- 2026-10-10-tri-titre-echantillon-1/etiquettes.json : les verdicts à l'aveugle
  des juges Claude ;
- 2026-10-10-tri-titre-1/echantillon_controle.jsonl et leurres.jsonl : le
  verdict du tri.

Chaque page passe une fois par `prospection.arbitre.arbitrer` (questions
`QUESTIONS`, bandes 0,12 / 0,57 et règle de cohérence de production), un appel
Jev par page, sans repli sur un LLM. Plafond de dépense : 0,20 $ (arrêt avant
l'appel qui le dépasserait). Sortie dans 2026-10-10-tri-titre-jev-1/ :
reponses.jsonl (une ligne par page, probabilités, bande, coût facturé, modèle
servi) et resume.txt (bandes par groupe, croisées avec les étiquettes).
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from pipeline import llm  # noqa: E402
from pipeline.decision import ClientDecision, ErreurDecision  # noqa: E402
from prospection.arbitre import arbitrer  # noqa: E402

LOGS = SCRIPTS.parent / "data" / "reviews" / "logs" / "refonte"
ECH = LOGS / "2026-10-10-tri-titre-echantillon-1"
TIRAGE = LOGS / "2026-10-10-tri-titre-1"
SORTIE = LOGS / "2026-10-10-tri-titre-jev-1"
PLAFOND_USD = 0.20


def wilson(k: int, n: int, z: float = 1.96) -> str:
    if n == 0:
        return "0/0"
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    d = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{k}/{n} = {100 * p:.1f} % [{100 * max(0, c - d):.1f} ; {100 * min(1, c + d):.1f}]"


def main() -> int:
    llm.charger_env()
    index = dict(
        ligne.split("\t")
        for ligne in (ECH / "pages" / "index.tsv").read_text(encoding="utf-8").splitlines()[1:]
        if ligne
    )
    etiquettes = {
        e["id"]: e for e in json.loads((ECH / "etiquettes.json").read_text(encoding="utf-8"))
    }
    groupe: dict[str, str] = {}
    for nom, fichier in (
        ("ecartee_au_tri", "echantillon_controle.jsonl"),
        ("gardee_au_tri", "leurres.jsonl"),
    ):
        for ligne in (TIRAGE / fichier).read_text(encoding="utf-8").splitlines():
            if ligne:
                groupe[json.loads(ligne)["id_aveugle"]] = nom
    SORTIE.mkdir(parents=True, exist_ok=False)
    client = ClientDecision()
    depense = 0.0
    lignes = []
    with (SORTIE / "reponses.jsonl").open("w", encoding="utf-8") as sortie:
        for ident, url in sorted(index.items()):
            if depense + 0.002 > PLAFOND_USD:
                print(f"plafond atteint avant {ident} ({depense:.4f} $)")
                break
            texte = (ECH / "pages" / f"{ident}.md").read_text(encoding="utf-8")
            debut = time.monotonic()
            try:
                a = arbitrer(client, url, texte)
                ligne = {
                    "id": ident,
                    "groupe": groupe[ident],
                    "etiquette": etiquettes[ident]["verdict_final"],
                    "deposable": a.deposable,
                    "dispositif": a.dispositif,
                    "destinataire": a.destinataire,
                    "objet": a.objet,
                    "categorie_ecart": a.categorie_ecart,
                    "bande": a.bande,
                    "modele": a.modele,
                    "cout_usd": a.cout_usd,
                    "jetons_entree": a.jetons_entree,
                    "duree_s": round(time.monotonic() - debut, 3),
                }
                depense += a.cout_usd or 0.002
            except ErreurDecision as e:
                ligne = {"id": ident, "groupe": groupe[ident], "panne": str(e)}
            lignes.append(ligne)
            sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            sortie.flush()
    client.fermer()

    resume = [f"pages jugées : {len(lignes)} ; dépense facturée : {depense:.4f} $"]
    pannes = [x for x in lignes if "panne" in x]
    resume.append(f"pannes : {len(pannes)}")
    for nom in ("ecartee_au_tri", "gardee_au_tri"):
        g = [x for x in lignes if x["groupe"] == nom and "panne" not in x]
        bandes = Counter(x["bande"] for x in g)
        resume.append(f"== {nom} ({len(g)} pages) : bandes {dict(bandes)}")
        hors_basse = sum(x["bande"] != "ecartee" for x in g)
        resume.append(f"   hors bande basse : {wilson(hors_basse, len(g))}")
        croise = Counter((x["etiquette"], x["bande"]) for x in g)
        resume.append(f"   étiquette Claude x bande : {dict(sorted(croise.items()))}")
    (SORTIE / "resume.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))
    return 0


if __name__ == "__main__":
    sys.exit(main())

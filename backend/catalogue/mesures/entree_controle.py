"""Mesure d'I6, hors ligne : fidélité du portage de la règle d'entrée, et contrôle des pages sans contenu.

    uv run --no-sync python -m catalogue.mesures.entree_controle [<dossier du jeu E>]

1. **Fidélité.** Les deux exécutions de la règle de production sur le jeu E
   (`regle-1`, `regle-2`, 2026-10-10) ont gardé, page par page, les
   distributions de Jev et la lecture du LLM. On les rend au nouveau code
   (`catalogue.entree.juger`) par de faux clients, et on compare son issue
   (admise, écartée, doute, et la bande de Jev) à celle de la production. Le
   portage est fidèle si toutes concordent.
2. **`C-inexploitable`.** Sur les pages de E qui ont un texte, on compare ce que
   le contrôle arrête aux 33 pages que la relecture du 2026-10-10 a jugées
   sans contenu (`jeu_e.pages_sans_contenu`) : rappel, et pages jugeables
   arrêtées à tort, dont les pages à revoir (retenues ou indéterminées).

Aucun appel de modèle ni réseau. Écrit `<dossier>/entree-controle.json`.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline import decision as pd
from prospection import lecture

from catalogue import entree
from catalogue.journal import Vue
from catalogue.mesures import jeu_e
from catalogue.mesures.stats import wilson
from catalogue.registre import BACKEND, charger

DOSSIER = BACKEND / "data" / "reviews" / "logs" / "refonte" / "2026-10-10-jeu-e-1"


class FauxJev:
    def __init__(self, distributions: dict[str, Any], modele: str) -> None:
        self.d, self.modele = distributions, modele

    def decider(self, etat_jev: Any, questions: dict[str, Any]) -> pd.Decision:
        reponses = {
            nom: pd.Reponse(
                type=v["type"], choix=v["choix"], noul=v["noul"], probabilites=v["probabilites"]
            )
            for nom, v in self.d.items()
        }
        return pd.Decision(reponses, self.modele, "", 0, 0.0, 0.0, {})


class FauxLecteur:
    def __init__(self, lu: dict[str, Any], titre: str) -> None:
        self.lu, self.titre = lu, titre

    def try_complete_json(self, modele: Any, prompt: str, *, system: str) -> Any:
        fiche = lecture.LectureFiche.model_construct(
            destinataire=self.lu["destinataire"],
            objet=self.lu["objet"],
            categorie_ecart=self.lu.get("categorie_ecart"),
            famille=self.lu.get("famille") or "adjacente",
            titre=self.titre or "",
            note="",
            slug_propose="",
            urls_pdf=[],
            beneficiaires=None,
        )
        return type("Essai", (), {"data": fiche, "response": None})()


def attendue(r: dict[str, Any]) -> str:
    if r.get("promue"):
        return "admise"
    return "ecartee" if r.get("verdict") == "ecartee" else "doute"


def fidelite(dossier: Path, reg: Any) -> dict[str, Any]:
    telech = {t["id"]: t for t in jeu_e._lire_jsonl(dossier / "telechargements.jsonl")}
    echantillon = {e["id"]: e for e in jeu_e._lire_jsonl(dossier / "echantillon.jsonl")}
    sortie: dict[str, Any] = {}
    for execution in ("regle-1", "regle-2"):
        concordantes, ecarts = 0, []
        for r in jeu_e._lire_jsonl(dossier / execution / "reponses.jsonl"):
            if "jev_distributions" not in r or r.get("panne"):
                continue
            t = telech[r["id"]]
            page = entree.Page(
                url=t["url"],
                url_finale=t["url_finale"],
                texte="x " * 400,  # le contrôle des pages sans contenu se mesure à part
                documents=t["documents"],
                est_pdf=t["est_pdf"],
                territoire=echantillon[r["id"]].get("territoire", ""),
            )
            j = entree.juger(
                page,
                registre=reg,
                vue=Vue([]),
                jev=FauxJev(r["jev_distributions"], r["jev"]["modele"]),
                lecteur=FauxLecteur(r.get("llm") or {}, r.get("titre") or ""),
                modele_lecture="or-glm",
                consigner=lambda e: e,
            )
            if j.issue == attendue(r) and j.bande == r["bande"]:
                concordantes += 1
            else:
                ecarts.append(
                    {
                        "id": r["id"],
                        "nouveau": [j.issue, j.bande],
                        "production": [attendue(r), r["bande"]],
                    }
                )
        sortie[execution] = {"concordantes": concordantes, "ecarts": ecarts}
    return sortie


def controle(dossier: Path) -> dict[str, Any]:
    etiquettes = json.loads((dossier / "etiquettes.json").read_text(encoding="utf-8"))
    sans_contenu = jeu_e.pages_sans_contenu(dossier, etiquettes)
    labels = {e["id"]: jeu_e._etiquette(e) for e in etiquettes}
    arretees, vrais, faux_revoir, faux = [], 0, [], []
    telech = {t["id"]: t for t in jeu_e._lire_jsonl(dossier / "telechargements.jsonl")}
    vus: dict[tuple[str, str], str] = {}
    for p in sorted((dossier / "pages").glob("*.md")):
        motif = entree.inexploitable(
            p.read_text(encoding="utf-8", errors="replace"), telech[p.stem]["url_finale"], vus
        )
        if motif is None:
            continue
        arretees.append(p.stem)
        if p.stem in sans_contenu:
            vrais += 1
        else:
            faux.append(p.stem)
            if labels.get(p.stem) in ("retenue", "indeterminee"):
                faux_revoir.append(p.stem)
    jugeables = [p.stem for p in (dossier / "pages").glob("*.md") if p.stem not in sans_contenu]
    return {
        "pages": len(list((dossier / "pages").glob("*.md"))),
        "sans_contenu": len(sans_contenu),
        "arretees": len(arretees),
        "rappel": wilson(vrais, len(sans_contenu)).texte(),
        "jugeables_arretees": wilson(len(faux), len(jugeables)).texte(),
        "a_revoir_arretees": faux_revoir,
        "jugeables_arretees_ids": faux,
        "manquees": sorted(set(sans_contenu) - set(arretees)),
        "etiquettes_des_jugeables_arretees": Counter(labels.get(x) for x in faux),
    }


def main(argv: list[str] | None = None) -> int:
    dossier = Path((argv or sys.argv[1:] or [str(DOSSIER)])[0])
    resultat = {"fidelite": fidelite(dossier, charger()), "inexploitable": controle(dossier)}
    (dossier / "entree-controle.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    for execution, f in resultat["fidelite"].items():
        print(
            f"{execution} : {f['concordantes']} concordantes, {len(f['ecarts'])} écarts",
            f["ecarts"][:3],
        )
    print({k: v for k, v in resultat["inexploitable"].items() if k != "jugeables_arretees_ids"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

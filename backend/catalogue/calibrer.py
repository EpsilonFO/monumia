"""Recalibrer une décision fermée sur ses étalons (section 6 d'`architecture.md`).

    uv run python -m catalogue calibrer --decision V1-garde [--modele <nom>]

La commande rejoue le décideur sur le jeu étiqueté de la décision (les
probabilités déjà connues pour ce modèle sont reprises, les autres demandées),
choisit les seuils en validation croisée à deux plis répétée 20 fois pour le
budget du registre, et écrit un rapport
`data/reviews/<date>-calibration-<décision>-<modèle>.md` avec le bloc de
registre proposé. Elle n'écrit jamais `registre.yaml` : un seuil n'entre en
service que par le commit de Félix.

Une seule décision se recalibre à ce jour, la garde de veille (`V1-garde`).
Ses étalons sont les « inchangé » du LLM de veille au passage du 2026-10-04,
étiquetés par des agents Claude (`2026-10-04-etiquettes-veille-jev.md`) ; ils
vivent dans `data/catalogue/etalons/V1-garde.jsonl`, avec la probabilité de
chaque modèle de décision déjà mesuré.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veille_arbitre import QUESTIONS_MANDAT, empreinte_etat, etat_mandat

from catalogue.journal import empreinte
from catalogue.mesures.stats import fr, wilson
from catalogue.registre import BACKEND, Registre, charger

ETALONS = BACKEND / "data" / "catalogue" / "etalons"
REVIEWS = BACKEND / "data" / "reviews"
BANC_VEILLE = BACKEND / "data" / "reviews" / "logs" / "veille-jev"
JOUR_V1 = "2026-10-04"
REPETITIONS = 20


@dataclass(frozen=True)
class Etalon:
    cas: str
    etiquette: int  # 1 : le changement touche le mandat (un « inchangé » faux)
    provenance: str
    etat: dict[str, Any]
    p: dict[str, float]  # probabilité par modèle de décision servi


def effectif_minimal(budget: float) -> int:
    """Positifs sans erreur qu'il faut pour que la borne haute de Wilson tienne le budget."""
    n = 1
    while wilson(0, n).haut > budget:
        n += 1
    return n


# ------------------------------------------------------------------ V1


def construire_v1() -> list[Etalon]:
    """Les étalons de la garde, depuis le banc de veille du 2026-10-04 (lecture seule)."""
    from veille_benchmark_jev import lire_cas, lire_etiquettes

    etiquettes = lire_etiquettes(JOUR_V1)
    cache: dict[str, dict[str, Any]] = {}
    chemin = BANC_VEILLE / "jev.jsonl"
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            r = json.loads(ligne)
            cache[r["cle"]] = r
    etalons = []
    for c in lire_cas(JOUR_V1):
        lab = etiquettes.get(c.id)
        if c.verdict_llm != "inchange" or lab not in ("touche", "ne touche pas"):
            continue
        etat = etat_mandat(c.fiche, c.diff, c.resume_llm)
        r = cache.get(f"garde:{empreinte_etat(etat)}")
        p = {r["modele"]: float(r["p"])} if r else {}
        etalons.append(Etalon(c.id, int(lab == "touche"), "claude", etat, p))
    return etalons


def lire(decision: str) -> list[Etalon]:
    chemin = ETALONS / f"{decision}.jsonl"
    return [
        Etalon(**json.loads(ligne))
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]


def ecrire(decision: str, etalons: list[Etalon]) -> Path:
    ETALONS.mkdir(parents=True, exist_ok=True)
    chemin = ETALONS / f"{decision}.jsonl"
    lignes = [json.dumps(e.__dict__, ensure_ascii=False, sort_keys=True) for e in etalons]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def seuil_bas(points: list[tuple[float, int]], budget: float) -> float:
    """Le plus haut seuil sous lequel la part des positifs reste dans le budget.

    Sous ce seuil, la référence avance : un positif en dessous est un
    changement perdu. Le seuil est placé à mi-chemin entre deux notes
    observées, jamais sur une note.
    """
    positifs = sorted(p for p, y in points if y == 1)
    if not positifs:
        return 0.0
    tolere = math.floor(budget * len(positifs))
    # On peut laisser passer les `tolere` positifs les plus bas.
    if tolere >= len(positifs):
        return 1.0
    plafond = positifs[tolere]
    sous = [p for p, _ in points if p < plafond]
    return (max(sous) + plafond) / 2 if sous else plafond / 2


def valider(
    points: list[tuple[float, int]],
    budget: float,
    regle: Callable[[list[tuple[float, int]], float], float],
) -> dict[str, Any]:
    """Pertes et avances hors échantillon : deux plis, `REPETITIONS` fois, graine fixe."""
    hasard = random.Random(20261011)
    pertes = positifs = avances = negatifs = 0
    for _ in range(REPETITIONS):
        melange = points[:]
        hasard.shuffle(melange)
        moitie = len(melange) // 2
        for apprend, teste in (
            (melange[:moitie], melange[moitie:]),
            (melange[moitie:], melange[:moitie]),
        ):
            s = regle(apprend, budget)
            pertes += sum(1 for p, y in teste if y == 1 and p < s)
            positifs += sum(1 for _, y in teste if y == 1)
            avances += sum(1 for p, y in teste if y == 0 and p < s)
            negatifs += sum(1 for _, y in teste if y == 0)
    return {
        "pertes": pertes / positifs if positifs else float("nan"),
        "avances": avances / negatifs if negatifs else float("nan"),
    }


def calibrer_v1(
    reg: Registre, modele: str, appeler: Callable[[dict[str, Any]], float] | None
) -> str:
    """Rapport de calibration de la garde pour un modèle de décision servi."""
    chemin = ETALONS / "V1-garde.jsonl"
    existe = chemin.exists()
    etalons = lire("V1-garde") if existe else construire_v1()
    manquants = [e for e in etalons if modele not in e.p]
    if manquants:
        if appeler is None:
            raise SystemExit(
                f"{len(manquants)} étalon(s) sans probabilité pour {modele} : relancer avec le "
                "client (la commande appelle Jev pour eux)"
            )
        etalons = [
            Etalon(e.cas, e.etiquette, e.provenance, e.etat, {**e.p, modele: appeler(e.etat)})
            if modele not in e.p
            else e
            for e in etalons
        ]
    if manquants or not existe:
        ecrire("V1-garde", etalons)

    d = reg.decisions["V1-garde"]
    budget = reg.budgets.erreurs.changements_manques
    points = [(e.p[modele], e.etiquette) for e in etalons]
    n_pos = sum(y for _, y in points)
    besoin = effectif_minimal(budget)
    en_service = d.seuils["zone_prudente_bas"]
    perdus = sorted(p for p, y in points if y == 1 and p < en_service)
    propose = seuil_bas(points, budget)
    cv = valider(points, budget, seuil_bas)
    perte = wilson(len(perdus), n_pos)
    positifs = sorted(round(p, 3) for p, y in points if y == 1)
    lignes = [
        f"# Calibration de `V1-garde` pour `{modele}` ({dt.date.today().isoformat()})",
        "",
        "Écrit par `uv run python -m catalogue calibrer --decision V1-garde`. Aucun seuil n'est "
        "modifié : un seuil n'entre en service que par un commit de Félix.",
        "",
        "## Jeu",
        "",
        f"- {len(points)} « inchangé » du LLM de veille au passage du {JOUR_V1}, étiquetés par "
        f"des agents Claude ; {n_pos} cachent un changement du mandat (positifs).",
        f"- Questions `{empreinte(json.dumps(QUESTIONS_MANDAT, sort_keys=True, ensure_ascii=False))}` "
        f"(registre : `{d.empreintes.get('questions')}`).",
        f"- Notes des positifs : {' ; '.join(fr(p, 2) for p in positifs)}.",
        "",
        "## Seuils",
        "",
        f"- En service : bas de la zone prudente {fr(en_service, 2)}, escalade {fr(d.seuils['escalade'], 2)}.",
        f"- Sous le bas en service, positifs perdus dans l'échantillon : {perte.texte()}.",
        f"- Seuil bas proposé pour le budget de {fr(100 * budget, 0)} % de changements manqués : {fr(propose, 3)} "
        f"(dans l'échantillon) ; hors échantillon (deux plis, {REPETITIONS} répétitions) : "
        f"{fr(100 * cv['pertes'], 1)} % de positifs perdus, {fr(100 * cv['avances'], 1)} % des vrais « inchangé » qui "
        "font avancer la référence.",
        f"- Effectif minimal pour certifier ce budget sans erreur observée : {besoin} positifs ; "
        f"le jeu en a {n_pos}.",
        "",
        "## Décision",
        "",
    ]
    if n_pos < besoin:
        lignes.append(
            f"Effectif insuffisant ({n_pos} < {besoin}) : les seuils en service restent. Le "
            "seuil proposé n'est qu'indicatif ; le jeu grandit à chaque session d'étiquetage des "
            "cas de la zone prudente."
        )
    else:
        lignes += [
            "Bloc de registre proposé :",
            "",
            "```yaml",
            "  V1-garde:",
            f"    seuils: {{escalade: {d.seuils['escalade']}, zone_prudente_bas: {propose:.3f}}}",
            "```",
        ]
    return "\n".join(lignes) + "\n"


def commande(decision: str, modele: str | None) -> int:
    reg = charger()
    if decision != "V1-garde":
        print(f"{decision} : aucun jeu de calibration branché (seule V1-garde l'est).")
        return 2
    role = reg.modele("decision")
    nom_servi = modele or role.acceptes[0]

    def appeler(etat: dict[str, Any]) -> float:
        from catalogue.openrouter import Client

        client = Client()
        try:
            d = client.decider(modele or role.nom, etat, QUESTIONS_MANDAT, delai_s=role.delai_s)
        finally:
            client.fermer()
        return d.avis["touche"].proba("true")

    texte = calibrer_v1(reg, nom_servi, appeler)
    REVIEWS.mkdir(parents=True, exist_ok=True)
    chemin = (
        REVIEWS
        / f"{dt.date.today().isoformat()}-calibration-V1-garde-{nom_servi.replace('/', '_')}.md"
    )
    if chemin.exists():
        print(f"{chemin} existe déjà : rien écrit.")
        return 1
    chemin.write_text(texte, encoding="utf-8")
    print(f"rapport : {chemin}")
    return 0

"""Candidate pour la décision d'entrée : questions atomiques de Jev, état réduit (I0, M1).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.combinaison jev <dossier du jeu E>
    uv run python -m catalogue.mesures.combinaison evaluer <dossier du jeu E> <etiquettes.json>

`jev` (payant, plafond 0,30 $) pose à Jev, pour chaque page lisible du jeu E,
des questions étroites sur un état réduit : la tête de l'étape 3 du skill de
prospection (le test, sans la table des cas), lue dans le skill à chaque
lancement, puis l'URL, les documents liés et le texte de la page. Une question
`noul` par exclusion nommée de la liste fermée de l'étape 3, plus six questions
sur le dispositif, la qualité du demandeur, la réserve de métier, l'objet de la
dépense, les bénéficiaires mixtes, et la question `deposable` de production
reposée telle quelle pour mesurer ce que coûte la réduction de l'état. Une
réponse sans probabilité est une panne, jamais un « non ». Sortie dans un
sous-dossier neuf jev-reduit-<k>/ : reponses.jsonl.

`evaluer` combine par une régression logistique pondérée (`catalogue.logistique`)
les probabilités de Jev (état de production, lues dans regle-1/ ; état réduit,
lues dans jev-reduit-1/) et les jugements du LLM de lecture (regle-1/), en deux
modèles : P(page à revoir) pour écarter, P(page à retenir) pour admettre.
Validation croisée à deux plis répétée 20 fois : les seuils se choisissent sur
le pli d'apprentissage (pertes au plus 2 % des pages à revoir, admissions à tort
au plus 10 % des admissions), les mesures se font sur l'autre pli, et la règle
de production se mesure sur les mêmes pages. Sortie : combinaison.json et
combinaison.txt dans le dossier du jeu E.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from pipeline import llm
from pipeline.decision import ClientDecision, Decision, ErreurDecision, noul
from prospection.tri import SKILL_PROSPECTION

from catalogue.logistique import Modele, ajuster, auc
from catalogue.mesures.jeu_e import _lire_jsonl, _sous_dossier_neuf, pages_sans_contenu, verdict
from catalogue.mesures.stats import ponderee

PLAFOND_USD = 0.30
RESERVE_APPEL_USD = 0.002
REPETITIONS = 20
GRAINE = 20261012
BUDGET_PERTES = 0.02
BUDGET_ADMISSIONS = 0.10

# La liste fermée de « Ce qu'on écarte, et rien d'autre » (étape 3 du skill) et
# les écarts de la table des cas frontière, un cas par question. Les textes
# reprennent ceux du skill.
EXCLUSIONS = {
    "aide_personne": (
        "Une aide à la personne : formation, emploi, bourse, prime, mobilité, santé, logement "
        "des jeunes, ou une aide conditionnée au quotient familial ou aux ressources du ménage."
    ),
    "production_oeuvre": (
        "Une aide à la production d'une œuvre ou d'un contenu (film, écriture, édition, jeu "
        "vidéo), quand le lieu n'est ni l'objet ni la scène."
    ),
    "filiere_agricole": (
        "Une aide à la performance zootechnique ou à la filière agricole : UGB, MSA, "
        "installation, matériel, conversion, densité de plantation."
    ),
    "foret": (
        "Une aide à la forêt : sylviculture, boisement, reboisement, desserte, mécanisation, "
        "regroupement foncier, filière bois (le bois énergie qui chauffe un bâtiment n'en "
        "relève pas)."
    ),
    "prix_personne_ou_produit": (
        "Un prix récompensant une personne pour son parcours, son bénévolat ou son métier, ou "
        "un label portant sur un produit ou une entreprise."
    ),
    "portail": (
        "Un formulaire, un portail ou un guide-agrégat qui renvoie à d'autres fiches : ce "
        "n'est pas un dispositif."
    ),
    "reseau_public": (
        "Une infrastructure ou un service public de réseau sans bâtiment : rail, routes, pôles "
        "d'échanges, eau potable, assainissement, déchets, haut débit."
    ),
    "sport_enseignement_sante": (
        "Le sport de haut niveau, les lycées et l'enseignement, la recherche, l'export, la santé."
    ),
    "fusionne_remplace": (
        "Un dispositif fusionné ou remplacé par un autre, que la page désigne comme son successeur."
    ),
    "etat_europe": (
        "Un dispositif de l'État (DRAC), d'une fondation nationale ou de l'Europe, sauf quand "
        "la Région en est le guichet (LEADER, FEADER régionalisé)."
    ),
    "lecture_cinema_public": (
        "Une bibliothèque, une médiathèque, la lecture publique, une salle de cinéma ou une "
        "manifestation cinématographique, comme équipement public de diffusion et son programme."
    ),
    "promotion_tourisme": (
        "La promotion d'une destination, un office de tourisme, l'e-tourisme collectif, des "
        "itinéraires portés par un syndicat."
    ),
    "itineraire_sans_bati": (
        "Un réseau d'itinéraires, PDIPR, randonnée, véloroute : création, entretien, balisage "
        "ou signalétique de sentiers sans bâti."
    ),
    "entreprise_generale": (
        "Une aide à l'entreprise en général : prêt d'honneur, garantie, innovation, "
        "transmission, croissance de TPE, RSE, numérique d'entreprise, ESS en général."
    ),
    "logement_social": (
        "Le logement social (parc locatif social, bailleurs, organismes de logement), "
        "l'habitat inclusif, le logement d'un ménage sous condition de ressources."
    ),
    "fonctionnement_associatif": (
        "Le fonctionnement ou les activités d'une association en général, la formation des "
        "bénévoles, la pratique sportive ou musicale amateur."
    ),
    "organisateur_artiste": (
        "Une aide que la source RÉSERVE à une compagnie, un artiste ou un festival organisateur "
        "(licence d'entrepreneur de spectacles, conventionnement, label professionnel, équipe "
        "artistique constituée, budget de création)."
    ),
}

QUESTIONS: dict[str, Any] = {
    **{
        f"exclusion_{nom}": noul(
            "La page relève-t-elle de ce cas, que la doctrine écarte du catalogue ?",
            vrai=texte,
            faux="Non, la page ne relève pas de ce cas.",
        )
        for nom, texte in EXCLUSIONS.items()
    },
    "dispositif": noul(
        "La page décrit-elle UN dispositif qu'on peut demander (subvention, prêt, appel à "
        "projets, aide en nature, label ou prix ouvrant droit à une aide) ?",
        vrai="Oui : on peut déposer une demande au titre de ce dispositif.",
        faux=(
            "Non : portail, liste de dispositifs, guide-agrégat, actualité, page-programme, "
            "formulaire générique : rien à y demander."
        ),
    ),
    "qualite_proprietaire": noul(
        "La source permet-elle à celui qui POSSÈDE ou GÈRE un lieu de déposer, pris en cette "
        "qualité (particulier, commune ou EPCI propriétaire, association gestionnaire, SCI, "
        "société qui exploite le lieu) ?",
        vrai="Oui, un propriétaire ou un gestionnaire de lieu peut déposer en cette qualité.",
        faux="Non, la source vise d'autres demandeurs.",
    ),
    "reserve_metier": noul(
        "La source RÉSERVE-t-elle l'aide à un métier ou à une activité professionnelle (label "
        "professionnel, licence, affiliation MSA, inscription au RCS, équipe artistique) ?",
        vrai="Oui, il faut exercer ce métier ou cette activité pour déposer.",
        faux="Non, aucune condition de métier ne ferme la demande.",
    ),
    "objet_lieu": noul(
        "La dépense aidée porte-t-elle sur un bien (son bâti, son domaine, ses abords) ou sur ce "
        "qui s'y tient et que son propriétaire porte lui-même ?",
        vrai="Oui, la dépense porte sur le lieu ou sur une activité que le propriétaire y porte.",
        faux="Non, la dépense porte ailleurs, ou sans lieu.",
    ),
    "beneficiaires_mixtes": noul(
        "La source liste-t-elle des bénéficiaires qui couvrent à la fois des propriétaires ou "
        "gestionnaires de lieux et des organisateurs ou professionnels, ou ne dit-elle pas en "
        "quelle qualité on dépose ?",
        vrai="Oui, les deux sortes de demandeurs sont possibles, ou la qualité n'est pas dite.",
        faux="Non, la source dit clairement qui dépose et en quelle qualité.",
    ),
    "deposable": noul(
        "Un propriétaire de monument peut-il déposer cette demande tel qu'il est, pour son "
        "monument, sans changer de métier ni créer une structure pour l'occasion ?",
        vrai="Oui, il en est un destinataire légitime, en sa qualité de propriétaire ou gestionnaire.",
        faux=(
            "Non : il faudrait qu'il soit aussi agriculteur, entreprise, compagnie, artiste, "
            "ménage aidé, ou que la dépense porte hors de son lieu."
        ),
    ),
}


def criteres(skill_path: Path = SKILL_PROSPECTION) -> str:
    """La tête de l'étape 3 du skill, lue dans le skill : le test, sans la table des cas."""
    md = skill_path.read_text(encoding="utf-8")
    debut = md.index("## Étape 3")
    fin = md.index("### Deux jugements", debut)
    return md[debut:fin].strip()


def _probabilites(d: Decision) -> dict[str, float]:
    """La probabilité du vrai pour chaque question ; une réponse vide est une panne."""
    sortie: dict[str, float] = {}
    for nom, r in d.reponses.items():
        if r.noul is None:
            raise ErreurDecision(f"réponse sans probabilité pour {nom}")
        sortie[nom] = r.noul
    return sortie


# --------------------------------------------------------------------------
# jev
# --------------------------------------------------------------------------


def jev(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    sortie = _sous_dossier_neuf(dossier, "jev-reduit")
    llm.charger_env()
    client = ClientDecision()
    texte_criteres = criteres()
    depense = 0.0
    n = pannes = 0
    with (sortie / "reponses.jsonl").open("w", encoding="utf-8") as f:
        for t in _lire_jsonl(dossier / "telechargements.jsonl"):
            if not t["longueur"]:
                continue
            if depense + RESERVE_APPEL_USD > PLAFOND_USD:
                print(f"plafond atteint avant {t['id']} ({depense:.4f} $)")
                break
            page = (dossier / "pages" / f"{t['id']}.md").read_text(encoding="utf-8")
            etat = {
                "criteres": texte_criteres,
                "page": {"url": t["url_finale"], "documents": t["documents"], "texte": page},
            }
            ligne: dict[str, Any] = {"id": t["id"]}
            debut = time.monotonic()
            for essai in range(2):
                try:
                    d = client.decider(etat, QUESTIONS)
                    ligne.update(
                        probabilites=_probabilites(d),
                        modele=d.modele,
                        cout_usd=d.cout_usd,
                        jetons=d.jetons_entree,
                    )
                    ligne.pop("panne", None)
                    break
                except ErreurDecision as exc:
                    ligne["panne"] = f"essai {essai + 1} : {exc}"
                    time.sleep(5)
            ligne["duree_s"] = round(time.monotonic() - debut, 2)
            if "panne" in ligne:
                pannes += 1
            # Un coût inconnu ne compte jamais pour zéro.
            cout = ligne.get("cout_usd")
            depense += cout if isinstance(cout, int | float) else RESERVE_APPEL_USD
            n += 1
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            f.flush()
    client.fermer()
    print(f"{sortie} : {n} pages, {pannes} pannes, dépense comptée {depense:.4f} $")
    return 0


# --------------------------------------------------------------------------
# evaluer
# --------------------------------------------------------------------------


def _p(distributions: dict[str, Any], nom: str, option: str = "true") -> float:
    """Une probabilité lue dans les distributions de Jev enregistrées par `jeu_e regle`."""
    r = distributions[nom]
    if r.get("type") == "noul":
        if r.get("noul") is None:
            raise ValueError(f"{nom} sans probabilité")
        return float(r["noul"]) if option == "true" else 1.0 - float(r["noul"])
    return float((r.get("probabilites") or {}).get(option, 0.0))


def _variables(regle: dict[str, Any], reduit: dict[str, Any] | None) -> dict[str, list[float]]:
    """Les variables de chaque configuration candidate, pour une page."""
    prod = regle["jev_distributions"]
    v_prod = [
        _p(prod, "deposable"),
        _p(prod, "dispositif"),
        _p(prod, "destinataire", "proprietaire_gestionnaire"),
        _p(prod, "objet", "bien_ou_lieu") + _p(prod, "objet", "activite_dans_le_lieu"),
    ]
    lu = regle.get("llm")
    v_llm = [
        float(lu is None),
        float(bool(lu) and lu["destinataire"] == "proprietaire_gestionnaire"),
        float(bool(lu) and lu["destinataire"] == "indetermine"),
        float(bool(lu) and lu["objet"] in ("bien_ou_lieu", "activite_dans_le_lieu")),
        float(bool(lu) and lu["objet"] == "indetermine"),
    ]
    configurations = {"jev_production": v_prod, "jev_production_et_llm": v_prod + v_llm}
    if reduit is not None:
        p = reduit["probabilites"]
        exclusions = [p[f"exclusion_{nom}"] for nom in EXCLUSIONS]
        v_reduit = [
            p["dispositif"],
            max(exclusions),
            p["qualite_proprietaire"],
            p["reserve_metier"],
            p["objet_lieu"],
            p["beneficiaires_mixtes"],
            p["deposable"],
        ]
        configurations.update(
            jev_reduit=v_reduit,
            jev_reduit_et_llm=v_reduit + v_llm,
            jev_reduit_atomique_et_llm=exclusions + v_reduit[:1] + v_reduit[2:] + v_llm,
            tout=v_prod + v_reduit + v_llm,
        )
    return configurations


def _seuil_bas(scores: list[float], revoir: list[int], poids: list[float], budget: float) -> float:
    """Le plus haut seuil d'écart dont les pertes pondérées restent dans le budget."""
    total = sum(p for v, p in zip(revoir, poids, strict=True) if v)
    if total == 0:
        return 0.0
    meilleur = 0.0
    for s in sorted(set(scores)):
        pertes = sum(p for sc, v, p in zip(scores, revoir, poids, strict=True) if v and sc < s)
        if pertes / total > budget:
            break
        meilleur = s
    return meilleur


def _seuil_haut(
    scores: list[float], ecartee: list[int], poids: list[float], budget: float
) -> float:
    """Le plus bas seuil d'admission dont la part d'admissions à tort reste dans le budget."""
    meilleur = float("inf")
    for s in sorted(set(scores), reverse=True):
        admises = [(v, p) for sc, v, p in zip(scores, ecartee, poids, strict=True) if sc >= s]
        total = sum(p for _, p in admises)
        if total and sum(p for v, p in admises if v) / total <= budget:
            meilleur = s
    return meilleur


def _issues(
    m_revoir: Modele, m_retenir: Modele, b: float, h: float, x: list[list[float]]
) -> list[str]:
    sortie = []
    for v in x:
        if m_revoir.proba(v) < b:
            sortie.append("ecarter")
        elif m_retenir.proba(v) >= h:
            sortie.append("admettre")
        else:
            sortie.append("doute")
    return sortie


def _compter(issues: list[str], etiquettes: list[str], poids: list[float]) -> dict[str, float]:
    cles = ("pages", "a_revoir", "a_retenir", "pertes", "pertes_strictes", "admises")
    c = dict.fromkeys((*cles, "admises_a_tort", "doute"), 0.0)
    for i, e, p in zip(issues, etiquettes, poids, strict=True):
        revoir = e in ("retenue", "indeterminee")
        c["pages"] += p
        c["a_revoir"] += p * revoir
        c["a_retenir"] += p * (e == "retenue")
        c["pertes"] += p * (revoir and i == "ecarter")
        c["pertes_strictes"] += p * (e == "retenue" and i == "ecarter")
        c["admises"] += p * (i == "admettre")
        c["admises_a_tort"] += p * (i == "admettre" and e == "ecartee")
        c["doute"] += p * (i == "doute")
    return c


def _taux(c: dict[str, float]) -> dict[str, float]:
    def div(a: float, b: float) -> float:
        return a / b if b else 0.0

    return {
        "pertes": div(c["pertes"], c["a_revoir"]),
        "pertes_strictes": div(c["pertes_strictes"], c["a_retenir"]),
        "admises_a_tort": div(c["admises_a_tort"], c["admises"]),
        "part_doute": div(c["doute"], c["pages"]),
        "part_admise": div(c["admises"], c["pages"]),
    }


PLIS_INTERNES = 5


def _hors_pli(
    x: list[list[float]],
    y_revoir: list[int],
    y_retenir: list[int],
    poids: list[float],
    rng: random.Random,
) -> tuple[list[float], list[float]]:
    """Les deux probabilités de chaque page, prédites par un modèle qui ne l'a pas vue."""
    ordre = list(range(len(x)))
    rng.shuffle(ordre)
    parts = [ordre[j::PLIS_INTERNES] for j in range(PLIS_INTERNES)]
    p_revoir = [0.0] * len(x)
    p_retenir = [0.0] * len(x)
    for part in parts:
        dedans = set(part)
        appr = [k for k in ordre if k not in dedans]
        xa = [x[k] for k in appr]
        wa = [poids[k] for k in appr]
        m_revoir = ajuster(xa, [y_revoir[k] for k in appr], wa)
        m_retenir = ajuster(xa, [y_retenir[k] for k in appr], wa)
        for k in part:
            p_revoir[k] = m_revoir.proba(x[k])
            p_retenir[k] = m_retenir.proba(x[k])
    return p_revoir, p_retenir


def valider(
    ids: list[str],
    variables: dict[str, dict[str, list[float]]],
    etiquettes: dict[str, str],
    poids: dict[str, float],
    issues_reference: dict[str, str],
    configurations: list[str],
) -> dict[str, Any]:
    """Validation croisée à deux plis répétée, pour chaque configuration de variables.

    Sur chaque pli d'apprentissage : deux régressions (page à revoir, page à
    retenir), un seuil d'écart pour le budget de pertes, un seuil d'admission
    pour le budget d'admissions à tort. Sur l'autre pli : les issues, comptées
    avec leurs poids, et comparées à celles de la règle de référence sur les
    mêmes pages. Les mêmes plis servent à toutes les configurations.
    """
    rng = random.Random(GRAINE)
    plis_par_repetition = []
    for _ in range(REPETITIONS):
        melange = ids[:]
        rng.shuffle(melange)
        plis_par_repetition.append((melange[: len(melange) // 2], melange[len(melange) // 2 :]))

    sortie: dict[str, Any] = {}
    for nom in configurations:
        rng_interne = random.Random(GRAINE + 1)
        cumul: dict[str, float] = {}
        cumul_ref: dict[str, float] = {}
        discordances = {"candidate_perd_seule": 0.0, "reference_perd_seule": 0.0}
        par_repetition = []
        for plis in plis_par_repetition:
            c_rep: dict[str, float] = {}
            for k in (0, 1):
                appr, test = plis[k], plis[1 - k]
                xa = [variables[i][nom] for i in appr]
                wa = [poids[i] for i in appr]
                ya_revoir = [int(etiquettes[i] in ("retenue", "indeterminee")) for i in appr]
                ya_retenir = [int(etiquettes[i] == "retenue") for i in appr]
                m_revoir = ajuster(xa, ya_revoir, wa)
                m_retenir = ajuster(xa, ya_retenir, wa)
                # Les seuils se choisissent sur des prédictions hors pli, à
                # l'intérieur du pli d'apprentissage : réglés sur les prédictions
                # du modèle ajusté sur ces mêmes pages, ils surajustaient (pertes
                # de 0,6 % dans l'échantillon contre 8,6 % hors échantillon,
                # relecture adverse du 2026-10-10).
                p_revoir, p_retenir = _hors_pli(xa, ya_revoir, ya_retenir, wa, rng_interne)
                b = _seuil_bas(p_revoir, ya_revoir, wa, BUDGET_PERTES)
                h = _seuil_haut(
                    p_retenir,
                    [int(etiquettes[i] == "ecartee") for i in appr],
                    wa,
                    BUDGET_ADMISSIONS,
                )
                issues = _issues(m_revoir, m_retenir, b, h, [variables[i][nom] for i in test])
                lab_test = [etiquettes[i] for i in test]
                w_test = [poids[i] for i in test]
                for cle, v in _compter(issues, lab_test, w_test).items():
                    c_rep[cle] = c_rep.get(cle, 0.0) + v
                ref = [issues_reference[i] for i in test]
                for cle, v in _compter(ref, lab_test, w_test).items():
                    cumul_ref[cle] = cumul_ref.get(cle, 0.0) + v
                for iss, i in zip(issues, test, strict=True):
                    if etiquettes[i] == "ecartee":
                        continue
                    perd_c, perd_r = iss == "ecarter", issues_reference[i] == "ecarter"
                    if perd_c and not perd_r:
                        discordances["candidate_perd_seule"] += 1
                    elif perd_r and not perd_c:
                        discordances["reference_perd_seule"] += 1
            par_repetition.append(_taux(c_rep))
            for cle, v in c_rep.items():
                cumul[cle] = cumul.get(cle, 0.0) + v
        sortie[nom] = {
            "taux_cumules": _taux(cumul),
            "reference_sur_les_memes_plis": _taux(cumul_ref),
            "doute_min_max": [
                min(r["part_doute"] for r in par_repetition),
                max(r["part_doute"] for r in par_repetition),
            ],
            "pertes_min_max": [
                min(r["pertes"] for r in par_repetition),
                max(r["pertes"] for r in par_repetition),
            ],
            # Pages à revoir discordantes, en moyenne par répétition (chaque page
            # est testée une fois par répétition).
            "discordances_par_repetition": {k: v / REPETITIONS for k, v in discordances.items()},
        }
    return sortie


def lignes_configurations(configurations: dict[str, Any]) -> list[str]:
    lignes = []
    for nom, bloc in configurations.items():
        t = bloc["taux_cumules"]
        d = bloc["discordances_par_repetition"]
        lignes.append(
            f"{nom} : pertes {t['pertes']:.3f} (répétitions {bloc['pertes_min_max'][0]:.3f} à "
            f"{bloc['pertes_min_max'][1]:.3f}), strictes {t['pertes_strictes']:.3f}, admises à "
            f"tort {t['admises_a_tort']:.3f}, doute {t['part_doute']:.3f} (répétitions "
            f"{bloc['doute_min_max'][0]:.3f} à {bloc['doute_min_max'][1]:.3f}), admises "
            f"{t['part_admise']:.3f} ; pages à revoir perdues par la seule candidate "
            f"{d['candidate_perd_seule']:.1f}, par la seule référence {d['reference_perd_seule']:.1f}"
        )
    return lignes


def _issue_production(r: dict[str, Any]) -> str:
    if r.get("verdict") == "ecartee":
        return "ecarter"
    return "admettre" if r.get("promue") else "doute"


def evaluer(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    echantillon = {e["id"]: e for e in _lire_jsonl(dossier / "echantillon.jsonl")}
    etiquettes: dict[str, str] = {}
    brut = json.loads(Path(args.etiquettes).read_text(encoding="utf-8"))
    # Les pages sans contenu jugeable sortent des mesures (`jeu_e.pages_sans_contenu`).
    vides = {} if args.avec_pages_vides else pages_sans_contenu(dossier, brut)
    for e in brut:
        if e.get("final") and e["id"] not in vides:
            f = e["final"]
            etiquettes[e["id"]] = verdict(f["destinataire"], f["objet"], f.get("categorie_ecart"))
    regle = {r["id"]: r for r in _lire_jsonl(dossier / "regle-1" / "reponses.jsonl")}
    chemin_reduit = dossier / "jev-reduit-1" / "reponses.jsonl"
    reduit = {r["id"]: r for r in _lire_jsonl(chemin_reduit)} if chemin_reduit.exists() else None

    ids: list[str] = []
    variables: dict[str, dict[str, list[float]]] = {}
    exclues: dict[str, str] = {}
    for i in sorted(etiquettes):
        r = regle.get(i)
        if r is None or "panne" in r:
            exclues[i] = "règle de production en panne ou absente"
            continue
        rr = None if reduit is None else reduit.get(i)
        if reduit is not None and (rr is None or "panne" in rr):
            exclues[i] = "état réduit en panne ou absent"
            continue
        try:
            variables[i] = _variables(r, rr)
        except (KeyError, ValueError) as exc:
            exclues[i] = f"distribution incomplète : {exc}"
            continue
        ids.append(i)
    poids = {i: 1.0 / echantillon[i]["p_inclusion"] for i in ids}
    configurations = list(variables[ids[0]])
    lab = [etiquettes[i] for i in ids]
    w = [poids[i] for i in ids]

    resultat: dict[str, Any] = {"pages": len(ids), "exclues": exclues, "configurations": {}}
    issues_prod = {i: _issue_production(regle[i]) for i in ids}
    c_prod = _compter([issues_prod[i] for i in ids], lab, w)
    resultat["production"] = {"comptes": c_prod, "taux": _taux(c_prod)}
    resultat["production"]["pertes_intervalle"] = ponderee(
        [(issues_prod[i] == "ecarter", poids[i]) for i in ids if etiquettes[i] != "ecartee"]
    ).texte(pondere=True)
    resultat["production"]["doute_intervalle"] = ponderee(
        [(issues_prod[i] == "doute", poids[i]) for i in ids]
    ).texte(pondere=True)

    # Pouvoir de séparation des variables seules (U2 : l'état réduit vaut-il celui de production ?).
    y_revoir = [int(e in ("retenue", "indeterminee")) for e in lab]
    y_retenir = [int(e == "retenue") for e in lab]
    deposable_prod = [variables[i]["jev_production"][0] for i in ids]
    resultat["auc"] = {
        "deposable_production_revoir": auc(deposable_prod, y_revoir, w),
        "deposable_production_retenir": auc(deposable_prod, y_retenir, w),
    }
    if reduit is not None:
        deposable_reduit = [variables[i]["jev_reduit"][6] for i in ids]
        resultat["auc"]["deposable_reduit_revoir"] = auc(deposable_reduit, y_revoir, w)
        resultat["auc"]["deposable_reduit_retenir"] = auc(deposable_reduit, y_retenir, w)
        resultat["auc"]["sans_exclusion_revoir"] = auc(
            [1.0 - variables[i]["jev_reduit"][1] for i in ids], y_revoir, w
        )

    resultat["configurations"] = valider(
        ids, variables, etiquettes, poids, issues_prod, configurations
    )

    (dossier / "combinaison.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    lignes = [f"pages : {resultat['pages']} ; exclues : {len(exclues)}"]
    lignes += [f"AUC {k} : {v:.3f}" for k, v in resultat["auc"].items()]
    t = resultat["production"]["taux"]
    lignes.append(
        f"production : pertes {t['pertes']:.3f}, strictes {t['pertes_strictes']:.3f}, admises à "
        f"tort {t['admises_a_tort']:.3f}, doute {t['part_doute']:.3f}, admises {t['part_admise']:.3f}"
    )
    lignes.append(f"  pertes {resultat['production']['pertes_intervalle']}")
    lignes.append(f"  doute {resultat['production']['doute_intervalle']}")
    lignes += lignes_configurations(resultat["configurations"])
    (dossier / "combinaison.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("jev")
    p.add_argument("dossier")
    p.set_defaults(fonction=jev)
    p = sous.add_parser("evaluer")
    p.add_argument("dossier")
    p.add_argument("etiquettes")
    p.add_argument("--avec-pages-vides", action="store_true")
    p.set_defaults(fonction=evaluer)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""
Linter des données d'aides (data/aides/*.yaml + data/facts.yaml).

Vérifie :
  - validation Pydantic de chaque fichier (enums, structure, slug = nom de fichier)
  - les `fact` référencés existent dans l'ontologie
  - les `field` (kind: auto, applies_if) existent dans FIELD_REGISTRY
  - l'opérateur du prédicat est compatible avec le type du fait / du champ
  - pour les faits enum et les champs à référentiel : valeurs du prédicat valides
  - les `auto_source` de l'ontologie pointent vers un champ du registre
  - statistiques de couverture du typage (untyped restants) et dette de quotes
  - avec `--quotes`, que chaque citation se retrouve dans un snapshot archivé
  - ratchet des `manual_check` : aucune aide ne peut dépasser son compte de
    `manual_check` gate ni de `manual_check` sans notes enregistré dans
    data/manual_check_baseline.json — objectif zéro gate à terme

Deux modes, et la différence est importante :

  - GLOBAL (sans argument) : tout le catalogue, statistiques comprises. C'est
    le mode de la CI et du pre-commit. La dette historique (quotes introuvables
    des aides converties depuis les seeds) y est une INFORMATION : elle ne peut
    pas casser un build pour une faute que personne n'a commise aujourd'hui.
  - MONO-SLUG (`lint_aides_data.py <slug> …`) : seulement ces aides, sans
    statistique globale, et la dette y devient une ERREUR. C'est le mode d'une
    aide qu'on vient d'écrire — elle, on la veut irréprochable, et c'est ce
    contrat que l'agent d'ingestion doit satisfaire avant de rendre la main.

Run (exit 1 si erreur — branchable en CI / pre-commit) :
    cd backend && uv run python scripts/lint_aides_data.py
    cd backend && uv run python scripts/lint_aides_data.py <slug> --quotes
Après un batch de résorption relu, abaisser le plafond :
    uv run python scripts/lint_aides_data.py --update-baseline
"""

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ontologie_regles import (
    MAX_CAR_QUESTION_LINT,
    booleen_a_seuil,
    question_trop_longue,
)

from aides_schema import (
    AIDES_DIR,
    CATEGORIES_TERRITORIALES,
    FACTS_FILE,
    FACTS_PENDING_FILE,
    FAIT_PORTEUR,
    FIELD_REGISTRY,
    OPS_BY_FIELD_TYPE,
    OPTIONS_BOOLEEN_IMPLICITES,
    Aide,
    FactDef,
    Predicate,
    # Remontée dans aides_schema (second usager au runtime : /admin). Réimportée
    # ici parce que `veille_apply` et `veille_typage` l'importent DU LINT.
    check_fact_predicate,
    evaluate_predicate,
    # Remontée dans aides_schema pour le MOTEUR : un gate porteur explicite a
    # précédence sur la dérivation du marqueur, et le moteur ne peut pas
    # importer `scripts/`. Réimportée ici parce que `proposer_gate_porteur`
    # l'importe DU LINT.
    gate_porteur,
    load_aide,
    load_facts,
    load_pending_facts,
    predicate_leaves,
    sans_rien_a_verifier,
)
from eligibility_engine import _normalize_answer, deduire_faits_des_faits
from labels import DEPARTEMENT_LABELS, REGION_LABELS

# `help` NOMINATIF : marqueurs de financeur et de territoire. Un fait cité par
# plusieurs aides dont l'aide contextuelle nomme un seul financeur fait croire
# que la question ne concerne que celui-là — c'est le retour du testeur du
# 2026-09-16 sur `budget_projet_mediation` et `appellation_musee_de_france`,
# dont le `help` nommait un autre financeur que l'aide qui posait la question.
# Les libellés de territoire viennent du référentiel, pas d'une liste à tenir.
MOTIFS_NOMINATIFS = re.compile(
    "|".join(
        [
            r"\bR[ée]gion\b",
            r"\bD[ée]partement\b",
            r"\bConseil d[ée]partemental\b",
            r"\bFondation\b",
            r"\bAcad[ée]mie\b",
            r"\bInstitut de France\b",
            r"\bDRAC\b",
            r"\bGIP\b",
            r"\bFEDER\b",
            r"\bVMF\b",
            r"\bREMPART\b",
            r"\bDemeure Historique\b",
            *(re.escape(nom) for nom in {**REGION_LABELS, **DEPARTEMENT_LABELS}.values()),
        ]
    )
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_collect import load_baselines
from veille_text import find_quote_in_any, normalize

# Kinds dont la condition est opposable à une source : la quote y est attendue
# à terme (les conditions issues des seeds legacy n'en ont pas encore).
EVALUABLE_KINDS = ("auto", "user_fact", "discretionary", "manual_check")

# Ratchet de la dette `manual_check` : {slug: {"gates": n, "sans_notes": m}}.
# Un manual_check + gate rend l'aide indécidable (toujours « À confirmer »,
# sans question posée) : chaque compte ne peut que baisser, une aide nouvelle
# part de zéro. Le fichier ne se réécrit que via --update-baseline, après
# relecture (le diff git du baseline EST la revue de la dette).
BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "manual_check_baseline.json"

# (slug, id de condition, quote) — le triplet suffit à retrouver la ligne.
Citation = tuple[str, str, str]


def manual_check_counts(aides: list[Aide]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for aide in aides:
        mc = [c for c in aide.conditions if c.kind == "manual_check"]
        gates = sum(1 for c in mc if c.effect == "gate")
        sans_notes = sum(1 for c in mc if not (c.notes or "").strip())
        if gates or sans_notes:
            counts[aide.slug] = {"gates": gates, "sans_notes": sans_notes}
    return counts


def check_manual_check_ratchet(
    counts: dict[str, dict[str, int]], baseline_path: Path = BASELINE_FILE
) -> list[str]:
    if not baseline_path.exists():
        return [
            f"{baseline_path.name} absent — le générer : "
            "uv run python scripts/lint_aides_data.py --update-baseline"
        ]
    baseline: dict[str, dict[str, int]] = json.loads(baseline_path.read_text(encoding="utf-8"))
    errors = []
    for slug, cur in sorted(counts.items()):
        base = baseline.get(slug, {"gates": 0, "sans_notes": 0})
        if cur["gates"] > base["gates"]:
            errors.append(
                f"{slug}: {cur['gates']} manual_check gate (plafond {base['gates']}) — "
                "retyper via l'arbre de TYPING.md, pas de nouveau manual_check gate"
            )
        if cur["sans_notes"] > base["sans_notes"]:
            errors.append(
                f"{slug}: {cur['sans_notes']} manual_check sans notes "
                f"(plafond {base['sans_notes']}) — notes obligatoires (pourquoi irréductible)"
            )
    return errors


def check_field_predicate(where: str, field_path: str | None, predicate: Predicate) -> list[str]:
    errors: list[str] = []
    spec = FIELD_REGISTRY.get(field_path or "")
    if spec is None:
        errors.append(f"{where}: champ inconnu « {field_path} » (absent de FIELD_REGISTRY)")
        return errors
    allowed_ops = OPS_BY_FIELD_TYPE[spec["type"]]
    values = spec.get("values")
    for op, val in predicate_leaves(predicate.root):
        if op not in allowed_ops:
            errors.append(f"{where}: opérateur « {op} » invalide pour un champ {spec['type']}")
        if values is not None:
            vals = val if isinstance(val, list) else [val]
            bad = [v for v in vals if v not in values]
            if bad:
                errors.append(f"{where}: valeur(s) hors référentiel du champ : {bad}")
        if spec["type"] == "boolean" and not isinstance(val, bool):
            errors.append(f"{where}: un champ boolean se compare à true/false, reçu {val!r}")
    return errors


def check_aide(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    errors = []
    if aide.applies_if:
        errors.extend(
            check_fact_predicate(
                f"{aide.slug} (périmètre)",
                aide.applies_if.fact,
                aide.applies_if.predicate,
                facts,
            )
        )
    for cond in aide.conditions:
        where = f"{aide.slug} / {cond.id}"
        if cond.kind == "user_fact":
            assert cond.predicate is not None  # garanti par le schéma
            errors.extend(check_fact_predicate(where, cond.fact, cond.predicate, facts))
        elif cond.kind == "auto":
            assert cond.predicate is not None  # garanti par le schéma
            errors.extend(check_field_predicate(where, cond.field, cond.predicate))
        if cond.levier:
            fait = facts.get(cond.levier)
            if fait is None:
                errors.append(f"{where}: levier « {cond.levier} » absent de facts.yaml")
            elif fait.levier is None:
                errors.append(
                    f"{where}: le fait « {cond.levier} » ne porte pas de `levier`, "
                    "rien à afficher : en écrire un dans facts.yaml ou retirer la référence"
                )
        if cond.applies_if:
            w = f"{where} (applies_if)"
            if cond.applies_if.fact:
                errors.extend(
                    check_fact_predicate(w, cond.applies_if.fact, cond.applies_if.predicate, facts)
                )
            else:
                errors.extend(
                    check_field_predicate(w, cond.applies_if.field, cond.applies_if.predicate)
                )
    return errors


def check_hors_gate(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Aucun gate, aucun périmètre sur un fait marqué `hors_gate`.

    Miroir, côté pipeline, du test de corpus
    `test_corpus_autofinancement_ne_gate_plus_nulle_part` : l'agent d'ingestion
    voit le lint, jamais pytest.
    """
    conseil = "typer manual_check + info (TYPING, « manual_check + effect: info »)"
    erreurs: list[str] = []

    def _hors_gate(fact: str | None) -> bool:
        return bool(fact) and fact in facts and facts[fact].hors_gate

    if aide.applies_if and _hors_gate(aide.applies_if.fact):
        erreurs.append(
            f"{aide.slug} / applies_if: fait « {aide.applies_if.fact} » hors_gate — {conseil}"
        )
    for cond in aide.conditions:
        where = f"{aide.slug} / {cond.id}"
        if cond.effect == "gate" and _hors_gate(cond.fact):
            erreurs.append(
                f"{where}: gate sur le fait « {cond.fact} » marqué hors_gate — {conseil}"
            )
        if cond.applies_if and _hors_gate(cond.applies_if.fact):
            erreurs.append(
                f"{where}: applies_if sur le fait « {cond.applies_if.fact} » hors_gate — {conseil}"
            )
    return erreurs


def gates_sur_fait_a_levier(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Gates posés sur un fait porteur d'un `levier` (doctrine du 2026-09-23).

    Un fait qu'une démarche rend favorable n'est plus une question : il coûte une
    ligne au questionnaire de tous sans écarter personne. Sa place est un
    `manual_check` + `info` qui cite le levier (TYPING, « Critère ou démarche »).
    Erreur depuis que la repasse du 2026-09-23 a ramené le catalogue à zéro. Un
    levier `question_maintenue` garde la question par décision écrite.
    """
    return [
        f"{aide.slug} / {cond.id} → {cond.fact}"
        for cond in aide.conditions
        if cond.kind == "user_fact"
        and cond.effect == "gate"
        and cond.fact in facts
        and (levier := facts[cond.fact].levier) is not None
        and not levier.question_maintenue
    ]


def aides_sous_derivation_porteur(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Les conditions dont le marqueur du fait gaté FAIT le travail, sans gate explicite.

    C'était une ERREUR jusqu'au 2026-09-21 : l'aide devait traduire sa puce
    « Bénéficiaires » en gate `in` sur `statut_juridique_porteur`, faute de quoi
    le lint sortait rouge. La règle a produit l'inverse de son but — quand la
    source ne nomme pas ses bénéficiaires, le modèle INVENTAIT le gate pour
    satisfaire le lint, le vérificateur le contestait à chaque passage, et le
    modèle le maintenait « parce que le lint l'exige ». 580 aides sur 643 gatent
    le porteur, 60 conditions le disent dans leurs `notes`, 13 sont étiquetées
    « NON SOURCÉ », et 8 questions d'entreprise entraient dans le tronc d'un
    profil association.

    Le marqueur est désormais EXÉCUTABLE (`conditions_porteur_derivees`) : ces
    aides sont déjà fermées aux autres porteurs. Il ne reste qu'un relevé.
    """
    if gate_porteur(aide):
        return []
    lignes: list[str] = []
    for cond in aide.conditions:
        if cond.effect != "gate" or not cond.fact:
            continue
        marques = (facts[cond.fact].porteurs_concernes or []) if cond.fact in facts else []
        if not marques:
            continue
        lignes.append(f"{aide.slug} / {cond.id} → {cond.fact} {{{', '.join(marques)}}}")
    return lignes


def gate_plus_large_que_le_marqueur(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Un gate porteur EXPLICITE plus large que le marqueur d'un fait qu'elle gate.

    Avertissement, jamais une erreur — et c'est le point. 138 aides du corpus
    sont dans ce cas, dont 31 qui admettent `public_commune` sur un fait marqué
    `[societe, ei]` : la source les admet, et c'est le gate explicite qui a
    raison. Mais l'écart mérite d'être vu, parce qu'il signifie que la question
    du fait marqué sera posée à des porteurs pour qui elle n'a pas de sens.
    """
    porteur = facts.get(FAIT_PORTEUR)
    if porteur is None or not gate_porteur(aide):
        return []
    admis: set[str] | None = None
    for cond in aide.conditions:
        if cond.effect == "gate" and cond.fact == FAIT_PORTEUR:
            valeurs = {
                v
                for op, val in predicate_leaves(cond.predicate.root)
                for v in _valeurs_de_feuille(op, val)
            }
            admis = valeurs if admis is None else admis | valeurs
    if not admis:
        return []
    lignes: list[str] = []
    for cond in aide.conditions:
        if cond.effect != "gate" or not cond.fact or cond.fact == FAIT_PORTEUR:
            continue
        marques = (facts[cond.fact].porteurs_concernes or []) if cond.fact in facts else []
        if not marques:
            continue
        surplus = sorted(admis - set(marques))
        if surplus:
            lignes.append(
                f"{aide.slug} / {cond.id}: gate porteur admet {{{', '.join(surplus)}}} que "
                f"« {cond.fact} » ne concerne pas — sa question leur sera posée"
            )
    return lignes


def check_famille_faire_vivre(aide: Aide) -> list[str]:
    """Une aide « faire vivre le lieu » DOIT déclarer ses familles. Bloquant.

    `hors_famille` est fail-open PAR AIDE : sans `familles`, l'aide passe tous
    les cadrages et se présente à un projet de spectacles comme à un projet
    d'hébergement — avec ses questions. Mesuré le 2026-09-22 sur le profil qui a
    révélé le bug (Vosges, « faire vivre », tuile tourisme) : 106 aides
    candidates, 80 questions, 31 dans le tronc commun, contre 10 pour le même
    profil en Bourgogne-Franche-Comté. Dix-sept aides non taguées portaient
    l'essentiel de l'écart.

    La règle ne vaut QUE pour `valorisation_rayonnement` : le filtre des
    familles ne s'active jamais pour une aide de restauration seule
    (`hors_projet` l'a déjà écartée d'un projet d'animation, et un projet de
    travaux ne voit pas l'étape des familles). « Vide = fail-open » reste donc
    la doctrine ailleurs — cf. `data/TYPING.md` § `familles`.

    Une aide généraliste n'est pas une exception : elle déclare TOUTES les
    familles que sa page énumère. Ajouter une famille ne peut qu'élargir sa
    visibilité (`hors_famille` n'écarte que sur intersection vide) ; le risque
    est tout entier dans le tag trop étroit.
    """
    if "valorisation_rayonnement" in aide.raison and not aide.familles:
        return [
            f"{aide.slug}: `valorisation_rayonnement` sans `familles` — l'aide se présenterait "
            "à TOUS les projets « faire vivre le lieu », quel qu'en soit le thème "
            "(cf. data/TYPING.md, § `familles`)"
        ]
    return []


def check_portee_geographique(aide: Aide) -> list[str]:
    """Une aide départementale ou régionale doit dire sur quel territoire elle porte.

    Signalé par un test utilisateur du 2026-09-22 : un monument des Vosges se
    voyait proposer des aides de Meurthe-et-Moselle et des Hauts-de-Seine. Le
    ressort d'un conseil départemental EST son département ; l'omettre ne rend
    pas l'aide plus large, elle la rend fausse partout ailleurs.

    Ce n'est pas une condition au sens de la doctrine (elle ne se lit pas dans
    une puce du règlement) : c'est le périmètre du financeur, et c'est pour ça
    qu'il tient dans `hard_filters` et non dans `conditions`.
    """
    champ = CATEGORIES_TERRITORIALES.get(aide.categorie)
    if champ and not getattr(aide.hard_filters, champ):
        return [
            f"{aide.slug}: `categorie: {aide.categorie}` sans `hard_filters.{champ}` — "
            f"l'aide se proposera hors du ressort de {aide.organisme[:60]}"
        ]
    return []


def gates_refutes_sans_travaux(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Les gates d'une aide `valorisation_rayonnement` qu'un projet SANS travaux réfute.

    Une telle aide finance une action sans chantier (TYPING, § `raison`) : si
    « ce projet ne comporte pas de travaux » la ferme, le tag ou la condition est
    faux. Vide pour une aide sans ce tag.
    """
    if "valorisation_rayonnement" not in aide.raison:
        return []
    sans_travaux = deduire_faits_des_faits({"etat_travaux": "aucun"}, facts)
    return sorted(
        {
            f"{c.id} ({c.fact})"
            for c in aide.conditions
            if c.kind == "user_fact"
            and c.effect == "gate"
            and c.fact in sans_travaux
            and c.predicate is not None
            and evaluate_predicate(
                c.predicate.root,
                _normalize_answer(facts.get(c.fact), sans_travaux[c.fact]),
            )
            is False
        }
    )


def check_ecriture(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Erreurs propres à une aide qu'on ÉCRIT : outil `lint` de l'agent et `controler`.

    Chacune a été corrigée à la main sur le lot du 2026-09-18, et le lint global
    ne peut pas les rendre bloquantes sans rougir sur le stock existant (13
    calendriers contradictoires, 18 `raison` incohérentes au 2026-09-28). En
    mode écriture, l'agent les voit pendant sa boucle et peut les corriger ;
    `controler` refuse ensuite ce qui reste.
    """
    erreurs: list[str] = []
    for c in aide.conditions:
        if c.kind == "untyped":
            erreurs.append(
                f"{aide.slug} / {c.id} : condition `untyped` — le moteur ignore toute l'aide "
                "tant qu'une seule reste non typée. La typer (TYPING, arbre de décision)."
            )
    cal = aide.calendrier
    if cal is not None and cal.permanent and cal.date_limite is not None:
        erreurs.append(
            f"{aide.slug} : `calendrier.permanent: true` avec une `date_limite` "
            f"({cal.date_limite}) — les deux se contredisent. Une date limite dans la source "
            "→ `permanent: false`."
        )
    refutes = gates_refutes_sans_travaux(aide, facts)
    if refutes:
        erreurs.append(
            f"{aide.slug} : `raison: valorisation_rayonnement` mais un projet SANS travaux est "
            f"écarté par {', '.join(refutes)}. Soit l'aide finance des travaux (retirer le "
            "tag), soit la condition est trop large (TYPING, § `raison`)."
        )
    return erreurs


def page_sans_rien_a_trancher(aide: Aide) -> list[str]:
    """Avertissement : ni gate, ni modulateur, ni périmètre, ni critère structuré hors géographie.

    Forme typique d'une page-programme (stratégie, observatoire, page de liens)
    ingérée comme un dispositif : 18 retirées à la main le 2026-09-24. Pas une
    erreur, un prix ouvert à tous a légitimement cette forme.
    """
    hf = aide.hard_filters
    if (
        aide.applies_if is None
        and not any(c.effect in ("gate", "modulateur") for c in aide.conditions)
        and not (
            hf.protections
            or hf.proprietaires
            or hf.travaux
            or hf.etats_conservation
            or hf.commune_max_population
        )
    ):
        return [
            f"{aide.slug} : rien à trancher hors la géographie. Si la page ne présente aucun "
            "dispositif demandable (stratégie, observatoire, page de liens), "
            "`declarer_hors_perimetre` avec la catégorie `non_dispositif`."
        ]
    return []


def check_fail_open(aide: Aide) -> list[str]:
    """Aucun gate vérifiable ET aucun hard_filter : l'aide est éligible partout.

    Cf. `aides_schema.sans_rien_a_verifier`. AVERTISSEMENT et non erreur, parce
    que l'état est rare mais légitime : `vmf-prix-restauration` est un prix
    ouvert à tout propriétaire de patrimoine bâti, paysager ou mobilier, et son
    snapshot ne publie AUCUN critère discriminant. Y poser un gate reviendrait à
    l'inventer, ce que la doctrine interdit avant tout.

    Le cas qui a fait remonter le défaut — une aide des Hauts-de-Seine proposée
    à un monument des Vosges — est couvert en ERREUR par
    `check_portee_geographique` : ce qui manquait n'était pas un critère
    d'éligibilité, c'était le ressort du financeur.
    """
    if sans_rien_a_verifier(aide):
        return [
            f"{aide.slug}: aucune condition vérifiable et aucun hard_filter — "
            "le moteur n'a rien à opposer et l'annonce « potentiellement éligible » "
            "à tout le monde, partout"
        ]
    return []


_TIRETS_LONGS = ("—", "–")


def _textes_de_fiche(aide: Aide) -> list[str]:
    """Tout ce que la fiche fait lire, dans l'ordre de la page."""
    f = aide.fiche
    if f is None:
        return []
    textes: list[str | None] = [f.titre, f.financeur, f.chapeau]
    valeurs = [f.montant, *(getattr(f.essentiel, k) for k in type(f.essentiel).model_fields)]
    textes += [t for v in valeurs if v for t in (v.valeur, v.detail)]
    if f.en_bref:
        textes += [p.texte for p in f.en_bref.puces] + f.en_bref.detail
    textes += [t for c in f.conseils for t in (c.titre, c.texte)]
    textes += [t for e in f.etapes for t in (e.titre, e.texte)]
    textes += [t for p in f.points.values() for t in (p.titre, p.resume)]
    textes += list(f.pieces.values())
    return [t for t in textes if t]


def check_fiche(aide: Aide) -> list[str]:
    """Avertissements sur la fiche rédigée. Aucun n'est bloquant : une fiche en
    retard sur sa source reste plus lisible que le YAML brut, et la page ne
    s'appuie sur elle pour aucun verdict.

    - rédigée AVANT la dernière vérification de la source : la veille a pu
      changer une date, un taux ou une condition que la fiche résume encore ;
    - un point ou un conseil qui cite une condition que le YAML n'a plus, une
      condition sans point, une pièce renommée qui n'existe plus : la veille a
      touché aux conditions sans que la fiche suive ;
    - un tiret cadratin ou demi-cadratin : c'est le premier tic d'écriture
      automatique que la rédaction doit retirer (skill `ecriture-propre`).
    """
    f = aide.fiche
    if f is None:
        return []
    avertissements = []
    verifiee = aide.source.verified_at
    if f.redige_le and verifiee and verifiee > f.redige_le:
        avertissements.append(
            f"{aide.slug}: fiche rédigée le {f.redige_le}, source revérifiée le {verifiee}, "
            "à relire"
        )
    ids = {c.id for c in aide.conditions}
    orphelins = sorted(set(f.points) - ids)
    orphelins += [c.condition for c in f.conseils if c.condition and c.condition not in ids]
    if orphelins:
        avertissements.append(
            f"{aide.slug}: la fiche cite des conditions absentes {orphelins}, à relire"
        )
    manquants = [c.id for c in aide.conditions if c.id not in f.points]
    if manquants:
        avertissements.append(
            f"{aide.slug}: {len(manquants)} condition(s) sans point dans la fiche, à relire"
        )
    pieces = sorted(set(f.pieces) - {d.nom for d in aide.documents_requis})
    if pieces:
        avertissements.append(f"{aide.slug}: la fiche renomme des pièces absentes {pieces}")
    tirets = [t for t in _textes_de_fiche(aide) if any(c in t for c in _TIRETS_LONGS)]
    if tirets:
        avertissements.append(
            f"{aide.slug}: {len(tirets)} texte(s) de fiche avec un tiret long, "
            f"ex. « {_extrait(tirets[0], 60)} »"
        )
    return avertissements


def check_urls_partagees(aides: Sequence[Aide]) -> list[str]:
    """Deux aides du catalogue qui pointent la même page. Mode GLOBAL seulement.

    130 groupes d'URL partagées dans le lot du 2026-09-18, dont 51 ré-ingestions
    d'aides déjà au catalogue sous un slug suffixé `-2` : même URL, même
    territoire, la base ingérée le 17 et le double le 18. Le dédoublonnage de la
    collecte n'agissait qu'à l'étage 1, et `lecture.slug_final` résolvait la
    collision de slug par un suffixe numérique au lieu d'y voir un doublon.

    La clé est `cle_fiche` : elle ignore la pagination, qui a produit 22 paires
    à elle seule (`16-developpement-local`, `-2`, `-3`). Une ANCRE distincte est
    en revanche un vrai découpage — une page qui porte deux dispositifs sous
    deux ancres — et n'est pas signalée.

    **À n'activer qu'une fois le lot dédoublonné** (`scripts/dedoublonner_aides.py`) :
    rendue bloquante sur 130 groupes, elle interdirait tout travail sur le
    catalogue avant de l'avoir corrigé.
    """
    from prospection.collecte import cle_fiche

    groupes: dict[str, list[str]] = {}
    for aide in aides:
        url = aide.source.url_officielle
        if not url:
            continue
        ancre = url.split("#", 1)[1] if "#" in url else ""
        groupes.setdefault(f"{cle_fiche(url)}#{ancre}", []).append(aide.slug)
    return [
        f"{len(slugs)} aides partagent l'URL officielle « {cle} » : {', '.join(sorted(slugs))} "
        "— un dispositif, une fiche (scripts/dedoublonner_aides.py)"
        for cle, slugs in sorted(groupes.items())
        if len(slugs) > 1
    ]


def _valeurs_de_feuille(op: str, val: object) -> list[str]:
    """Les options d'un fait à choix citées par une feuille de prédicat.

    `neq` et `not_in` sont volontairement IGNORÉS : ils disent qui est exclu,
    pas qui est admis, et en déduire l'ensemble admis demanderait de connaître
    toutes les options — ce que ce relevé n'a pas à faire pour un
    avertissement.
    """
    if op in ("in", "contains_any", "contains_all") and isinstance(val, list):
        return [str(x) for x in val]
    if op == "eq" and isinstance(val, str):
        return [val]
    return []


def check_colonnes_non_nulles(aide: Aide) -> list[str]:
    """Champs que `aides_v3` refuse en NULL, et que le schéma laisse optionnels.

    `nom_court` est NOT NULL en base mais `str | None` dans `aides_schema` :
    l'exiger au chargement Pydantic obligerait chaque fixture de test à porter
    un champ sans rapport avec ce qu'elle teste. Le refus vit donc ici, là où le
    workflow l'attend — avant le commit, pas trois étapes plus loin quand
    `load_aides_yaml.py` remonte une violation de contrainte sur une fiche déjà
    relue et committée (vu le 2026-09-18 sur
    `normandie-cofinancement-projets-integres`).
    """
    if (aide.nom_court or "").strip():
        return []
    return [
        f"{aide.slug}: `nom_court` vide — NOT NULL dans aides_v3, le chargement "
        "échouerait. Un libellé court qui situe l'aide et son territoire."
    ]


# Marqueur de lien d'auteur — `[[fait]]`. Il n'a jamais été rendu : le front
# affiche `question` et `help` tels quels, crochets compris. Le lecteur d'un
# `help` est l'UTILISATEUR ; un renvoi vers une autre question s'écrit en
# français (« la question sur le statut juridique du porteur »). Les
# commentaires YAML, eux, restent libres : ils ne sortent jamais du fichier.
LIEN_AUTEUR = "[["


def check_facts(facts: dict[str, FactDef]) -> list[str]:
    erreurs = [
        f"facts.yaml / {key}: auto_source « {f.auto_source} » absent de FIELD_REGISTRY"
        for key, f in facts.items()
        if f.auto_source and f.auto_source not in FIELD_REGISTRY
    ]
    erreurs += [
        f"facts.yaml / {key}: `{champ}` contient un lien d'auteur `[[…]]`, rendu brut à "
        f"l'écran — le réécrire en français"
        for key, f in facts.items()
        for champ in ("question", "help")
        if LIEN_AUTEUR in (getattr(f, champ, None) or "")
    ]
    erreurs += [
        f"facts.yaml / {key} / option {o.id}: `{champ}` contient un lien d'auteur `[[…]]`"
        for key, f in facts.items()
        for o in f.options or []
        for champ in ("label", "description")
        if LIEN_AUTEUR in (getattr(o, champ, None) or "")
    ]
    erreurs.extend(check_pertinent_si(facts))
    erreurs.extend(check_porteurs_concernes(facts))
    erreurs.extend(check_pourquoi(facts))
    return erreurs


def check_pourquoi(facts: dict[str, FactDef]) -> list[str]:
    """Chaque clé de `pourquoi` nomme une réponse du fait, ou vaut « * ».

    Vérifié ici et non dans `FactDef` : l'administration peut retirer une
    réponse (`faits_surcharges`), et un modèle qui refuserait la clé orpheline
    ferait ignorer la surcharge entière. Le moteur, lui, ne sert que les clés
    des réponses encore offertes.
    """
    erreurs: list[str] = []
    for key, f in facts.items():
        if not f.pourquoi:
            continue
        if f.type == "boolean":
            ids = {o.id for o in f.options or OPTIONS_BOOLEEN_IMPLICITES}
        else:
            ids = {o.id for o in f.options or []}
        for cle, texte in f.pourquoi.items():
            if cle != "*" and cle not in ids:
                erreurs.append(
                    f"facts.yaml / {key}: `pourquoi.{cle}` ne nomme aucune réponse du fait "
                    f"(réponses : {', '.join(sorted(ids)) or 'aucune'}, ou « * »)"
                )
            if LIEN_AUTEUR in texte:
                erreurs.append(
                    f"facts.yaml / {key}: `pourquoi.{cle}` contient un lien d'auteur `[[…]]`"
                )
    return erreurs


# Vocabulaire qui trahit une question réservée à un porteur économique. Liste
# FERMÉE, appliquée à la clé ET à la question normalisées. Elle ne décide rien :
# elle ALERTE, sans jamais bloquer. Le marqueur reste une décision humaine —
# « ouvrez-vous votre atelier à la visite ? » parle d'entreprise sans être
# réservée à une entreprise, et un faux positif qu'on ne peut pas taire
# apprendrait à ne plus lire l'alerte.
MOTS_PORTEUR_ECONOMIQUE = re.compile(
    "|".join(
        [
            r"\bentreprises?\b",
            r"\bpme\b",
            r"\btpe\b",
            r"\beti\b",
            r"\bsalaries?\b",
            r"\beffectif\b",
            r"\bchiffre d'affaires\b",
            r"\bexploitant\b",
            r"\bexploitation agricole\b",
            r"\bagriculteur\b",
            r"\brepreneur\b",
            r"\bdirigeant\b",
            r"\bsociete\b",
            r"\bfonds propres\b",
            r"\bcotation\b",
            r"\bimmatricul",
            r"\bsiret\b",
            r"\bsiren\b",
        ]
    )
)


# L'entreprise dont parle la question est un TIERS — celle qui exécute les
# travaux, pas celle qui dépose le dossier. « Les travaux ont-ils été réalisés
# par des entreprises du bâtiment ? » concerne une commune autant qu'une SARL.
# C'est la famille de faux positifs la plus nombreuse, et la seule qui soit
# systématique : elle se reconnaît au fait que l'entreprise y est complément
# d'agent, jamais sujet.
MOTS_ENTREPRISE_TIERCE = re.compile(
    "|".join(
        [
            r"realise(?:e|s|es)? par",
            r"\bcertifie",
            r"\brge\b",
            r"\bpressenties?\b",
            r"recours a une entreprise",
            r"\bprestataires?\b",
        ]
    )
)


def faits_entreprise_sans_marqueur(facts: dict[str, FactDef]) -> list[str]:
    """Les faits dont le vocabulaire sent l'entreprise et qui ne se déclarent pas.

    C'est la DETTE que le marqueur laisse derrière lui : `porteurs_concernes`
    bloque une aide qui gate un fait marqué, mais rien ne fait naître un fait
    marqué. Un lot sur une région viticole ferait naître
    `chiffre_affaires_viticole` sans garde-fou, et ses aides reposeraient leurs
    questions d'entreprise aux communes — exactement le défaut du lot Grand Est,
    transposé aux faits.

    Volontairement NON bloquant, et c'est le cœur du réglage : la liste est une
    invitation à relire, pas un verdict. `creation_offre_visite_entreprise`
    parle d'entreprise et concerne pourtant un monument qui ouvre son atelier à
    la visite ; le refuser obligerait à marquer un fait à tort, ce qui est bien
    pire qu'un fait non marqué.
    """
    suspects: list[str] = []
    for key, f in sorted(facts.items()):
        # Un fait `hors_gate` ne peut être gaté par AUCUNE aide : le marqueur,
        # qui n'agit qu'à travers un gate, n'y changerait rien.
        if f.porteurs_concernes or f.hors_gate or key == FAIT_PORTEUR:
            continue
        texte = normalize(f"{key.replace('_', ' ')} {f.question}")
        if MOTS_PORTEUR_ECONOMIQUE.search(texte) and not MOTS_ENTREPRISE_TIERCE.search(texte):
            suspects.append(key)
    return suspects


def check_porteurs_concernes(facts: dict[str, FactDef]) -> list[str]:
    """Les catégories citées par le marqueur existent bien chez le porteur.

    Cette erreur est devenue CRITIQUE le 2026-09-21, avec la dérivation : le
    marqueur ne documente plus une contrainte de lint, il ÉLIMINE. Une option
    inventée n'est plus une gêne de relecture — `{in: [<option inconnue>]}` est
    faux pour tout le monde, et l'aide devient inaccessible à tous les porteurs
    sans qu'aucun test de corpus ne s'en aperçoive.

    Si `statut_juridique_porteur` lui-même manque à l'ontologie servie, on se
    TAIT : 207 aides gatent dessus, leur `check_aide` le dira déjà, et une
    ontologie partielle (un test, un script hors ligne) n'a pas à récolter une
    erreur par fait marqué.
    """
    porteur = facts.get(FAIT_PORTEUR)
    erreurs: list[str] = []
    for key, f in facts.items():
        if not f.porteurs_concernes:
            continue
        ou = f"facts.yaml / {key} (porteurs_concernes)"
        if key == FAIT_PORTEUR:
            erreurs.append(f"{ou}: le fait porteur ne se marque pas lui-même")
            continue
        if porteur is None:
            continue
        connues = {o.id for o in (porteur.options or [])}
        inconnues = [v for v in f.porteurs_concernes if v not in connues]
        if inconnues:
            erreurs.append(
                f"{ou}: option(s) inconnue(s) de « {FAIT_PORTEUR} » : {', '.join(inconnues)}"
            )
    return erreurs


def check_pertinent_si(facts: dict[str, FactDef]) -> list[str]:
    """La dépendance intrinsèque d'un fait : cible, prédicat, et pas de chaîne.

    Le prédicat est validé par `check_fact_predicate`, la MÊME fonction que les
    conditions d'aides et l'administration du catalogue : une clause qui
    citerait une option inexistante ne serait jamais vraie, et la question
    qu'elle gouverne ne serait plus jamais posée — un fait tu, pas une erreur.

    La chaîne est limitée à UN niveau parce que `build_questions` suppose une
    seule passerelle (`_depends_on` ne projette qu'un `showForOptionIds`) : une
    question branchée sur une question elle-même branchée resterait invisible.
    """
    erreurs: list[str] = []
    for key, f in facts.items():
        clause = f.pertinent_si
        if clause is None:
            continue
        ou = f"facts.yaml / {key} (pertinent_si)"
        if clause.fact == key:
            erreurs.append(f"{ou}: un fait ne peut pas dépendre de lui-même")
            continue
        cible = facts.get(clause.fact or "")
        if cible is None:
            erreurs.append(f"{ou}: fait cible inconnu « {clause.fact} »")
            continue
        erreurs.extend(check_fact_predicate(ou, clause.fact, clause.predicate, facts))
        if cible.pertinent_si is not None:
            erreurs.append(
                f"{ou}: la cible « {clause.fact} » porte elle-même un `pertinent_si` — "
                "chaîne limitée à un niveau (le questionnaire ne sait rendre qu'une "
                "passerelle)"
            )
    return erreurs


# ---------------------------------------------------------------------------
# Quotes : la citation est-elle dans un snapshot archivé ?
# ---------------------------------------------------------------------------


def check_quotes(
    aide: Aide, documents: list[tuple[str, str, str]], illisibles: Sequence[str] = ()
) -> tuple[list[Citation], list[Citation], list[Citation]]:
    """(absentes, dégradées, hors portée) pour une aide, contre ses snapshots.

    Même définition que `veille_quotes_audit` — un seul verdict de ce qu'est
    une citation justifiée, sinon l'audit et le lint diraient deux choses
    différentes de la même donnée.

    « Hors portée » recouvre les deux cas où l'absence n'accuse pas la
    citation : aucun snapshot exploitable pour l'aide, ou un règlement PDF
    scanné dont `pdftotext` ne tire rien. Les imputer à la dette reviendrait à
    reprocher à une ingestion l'illisibilité de sa source.
    """
    citees = [c for c in aide.conditions if c.quote]
    if not documents:
        return [], [], [(aide.slug, c.id, c.quote or "") for c in citees]

    absentes: list[Citation] = []
    degradees: list[Citation] = []
    hors_portee: list[Citation] = []
    for cond in citees:
        _nom, match = find_quote_in_any(cond.quote or "", documents)  # type: ignore[arg-type]
        if not match.found:
            (hors_portee if illisibles else absentes).append((aide.slug, cond.id, cond.quote or ""))
        elif match.status != "exacte" or match.reconstitution:
            degradees.append((aide.slug, cond.id, cond.quote or ""))
    return absentes, degradees, hors_portee


def _extrait(quote: str, taille: int = 90) -> str:
    plat = " ".join(quote.split())
    return plat if len(plat) <= taille else plat[:taille] + "…"


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


@dataclass
class RapportLint:
    """Ce que le lint a trouvé. `ok` seul décide du code de sortie."""

    erreurs: list[str] = field(default_factory=list)
    #: Ce qui mérite d'être vu sans bloquer le commit. Le lint DOIT avoir cette
    #: catégorie : une règle qui ne sait que bloquer se fait contourner, et
    #: c'est exactement ce qui est arrivé au gate porteur — le modèle inventait
    #: le gate pour satisfaire le lint plutôt que de lire sa source.
    avertissements: list[str] = field(default_factory=list)
    lignes: list[str] = field(default_factory=list)
    aides: list[Aide] = field(default_factory=list)
    quotes_absentes: list[Citation] = field(default_factory=list)
    quotes_degradees: list[Citation] = field(default_factory=list)
    quotes_hors_portee: list[Citation] = field(default_factory=list)

    #: Au-delà, les avertissements noient les erreurs qu'il faut lire.
    MAX_AVERTISSEMENTS_AFFICHES = 15

    @property
    def ok(self) -> bool:
        return not self.erreurs

    def texte(self) -> str:
        sortie = list(self.lignes)
        if self.avertissements:
            sortie.append(f"\n⚠ {len(self.avertissements)} avertissement(s) :")
            sortie.extend(
                f"  - {a}" for a in self.avertissements[: self.MAX_AVERTISSEMENTS_AFFICHES]
            )
            reste = len(self.avertissements) - self.MAX_AVERTISSEMENTS_AFFICHES
            if reste > 0:
                sortie.append(f"  … et {reste} autre(s)")
        if self.erreurs:
            sortie.append(f"\n✗ {len(self.erreurs)} erreur(s) :")
            sortie.extend(f"  - {e}" for e in self.erreurs)
        else:
            sortie.append("\n✓ lint OK")
        return "\n".join(sortie)


def lint(
    slugs: Sequence[str] = (),
    *,
    strict: bool = False,
    quotes: bool = False,
    ratchet: bool = True,
    aides_dir: Path = AIDES_DIR,
    facts_path: Path = FACTS_FILE,
    pending_path: Path = FACTS_PENDING_FILE,
    baseline_path: Path = BASELINE_FILE,
    reference_dirs: Sequence[Path] = (),
    faits_du_run: Sequence[str] = (),
    ecriture: bool = False,
) -> RapportLint:
    """Lint du catalogue entier, ou des seuls `slugs` donnés.

    Les caches de `load_facts` / `load_pending_facts` sont vidés en entrée :
    l'agent d'ingestion appelle ce lint DANS le même processus, entre deux
    écritures de `facts_pending.yaml` — un fait qu'il vient de proposer doit
    être vu, sinon il se ferait refuser sa propre proposition.

    `faits_du_run` sont les faits que l'ingestion en cours vient de proposer :
    un orphelin parmi eux est une ERREUR en mono-slug, là où celui du voisin
    reste un avertissement. La distinction est tout l'intérêt de la règle —
    l'agent peut retirer le sien, pas celui d'un autre.

    `ecriture` ajoute les contrôles d'une aide qu'on écrit (`check_ecriture`,
    `page_sans_rien_a_trancher`) : l'ingestion les active, le lint du stock non.
    """
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    rapport = RapportLint()

    try:
        approved = load_facts(facts_path)
        pending = load_pending_facts(pending_path)
    except Exception as e:
        rapport.erreurs.append(f"facts.yaml / facts_pending.yaml invalide : {e}")
        return rapport

    collisions = sorted(set(approved) & set(pending))
    if collisions:
        rapport.erreurs.append(f"facts_pending.yaml: clé(s) déjà dans facts.yaml : {collisions}")
    # Les conditions sont validées contre l'union approuvés + pending : un fait
    # proposé est utilisable immédiatement par le typage, mais reste signalé
    # (bloquant en --strict, pour la CI) tant qu'il n'a pas été approuvé.
    facts = {**approved, **pending}
    rapport.erreurs.extend(check_facts(facts))

    global_mode = not slugs
    chemins = (
        sorted(aides_dir.glob("*.yaml"))
        if global_mode
        else [aides_dir / f"{s}.yaml" for s in slugs]
    )
    # Groupés en UN avertissement plutôt qu'un par condition : 271 lignes sur le
    # corpus noieraient les deux qui portent (cf. `RapportLint.texte`).
    gates_larges: list[str] = []
    fail_open: list[str] = []
    gates_levier: list[str] = []
    for path in chemins:
        if not path.exists():
            rapport.erreurs.append(f"{path.name}: fichier absent de {aides_dir}")
            continue
        try:
            aide = load_aide(path)
        except Exception as e:
            rapport.erreurs.append(f"{path.name}: {e}")
            continue
        rapport.aides.append(aide)
        rapport.erreurs.extend(check_colonnes_non_nulles(aide))
        rapport.erreurs.extend(check_aide(aide, facts))
        rapport.erreurs.extend(check_hors_gate(aide, facts))
        rapport.erreurs.extend(check_portee_geographique(aide))
        rapport.erreurs.extend(check_famille_faire_vivre(aide))
        if ecriture:
            rapport.erreurs.extend(check_ecriture(aide, facts))
            rapport.avertissements.extend(page_sans_rien_a_trancher(aide))
        fail_open.extend(check_fail_open(aide))
        gates_levier.extend(gates_sur_fait_a_levier(aide, facts))
        gates_larges.extend(gate_plus_large_que_le_marqueur(aide, facts))
        rapport.avertissements.extend(check_fiche(aide))

    if fail_open:
        rapport.avertissements.append(
            f"{len(fail_open)} aide(s) sans rien à vérifier — ni gate, ni hard_filter, ni "
            "`applies_if` — donc annoncées « potentiellement éligibles » partout :\n"
            + "\n".join(f"      {li}" for li in fail_open[:6])
            + (f"\n      … et {len(fail_open) - 6} autre(s)" if len(fail_open) > 6 else "")
        )

    if gates_levier:
        rapport.erreurs.extend(
            f"{li} : gate sur un fait à levier. Une démarche faisable avant le dépôt ne "
            "se demande pas, elle s'annonce en `manual_check` + `info` avec `levier: <fait>` ; "
            "si la question doit rester, `question_maintenue: true` dans le levier "
            "(TYPING, « Critère ou démarche »)"
            for li in gates_levier
        )

    if gates_larges:
        rapport.avertissements.append(
            f"{len(gates_larges)} gate(s) porteur plus large(s) que le marqueur d'un fait "
            "gaté — la source a raison, mais la question du fait marqué sera posée à des "
            "porteurs pour qui elle n'a pas de sens :\n"
            + "\n".join(f"      {li}" for li in gates_larges[:6])
            + (f"\n      … et {len(gates_larges) - 6} autre(s)" if len(gates_larges) > 6 else "")
        )

    if global_mode:
        rapport.lignes.extend(_statistiques(rapport.aides, facts))
    else:
        rapport.lignes.append(f"aides   : {len(rapport.aides)} fichier(s) — {', '.join(slugs)}")
        for aide in rapport.aides:
            derivees = aides_sous_derivation_porteur(aide, facts)
            if derivees:
                rapport.lignes.append(
                    "gate porteur : le marqueur `porteurs_concernes` fait le travail sur "
                    f"{len(derivees)} condition(s) — n'en pose un que si la source NOMME ses "
                    "bénéficiaires. Un gate inventé pour satisfaire le lint est un faux "
                    "négatif que personne ne verra."
                )
                rapport.lignes.extend(f"   {li}" for li in derivees)
        kinds = Counter(c.kind for a in rapport.aides for c in a.conditions)
        if kinds:
            rapport.lignes.append(
                "conditions : "
                + ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items()))
                + f" ({sum(kinds.values())} au total)"
            )

    # L'usage se compte sur TOUT `aides_dir`, y compris en mono-slug : sinon
    # chaque lint d'une aide déclarerait orphelins les faits proposés par les
    # autres. En mode global, les aides sont déjà chargées — rien à rebalayer.
    usage_global = (
        set(compter_usage_faits(rapport.aides)) if global_mode else faits_references_dans(aides_dir)
    )
    rapport.lignes.extend(
        _bloc_pending(
            rapport.aides,
            pending,
            strict,
            rapport,
            usage_global=usage_global,
            global_mode=global_mode,
            faits_du_run=faits_du_run,
        )
    )
    if quotes:
        _bloc_quotes(rapport, global_mode)

    mc_counts = manual_check_counts(rapport.aides)
    n_gates = sum(c["gates"] for c in mc_counts.values())
    n_sans_notes = sum(c["sans_notes"] for c in mc_counts.values())
    n_aides_gates = sum(1 for c in mc_counts.values() if c["gates"])
    rapport.lignes.append(
        f"manual_check : {n_gates} gate(s) sur {n_aides_gates} aide(s) — objectif zéro ; "
        f"{n_sans_notes} sans notes (ratchet : {baseline_path.name})"
    )
    if ratchet:
        rapport.erreurs.extend(check_manual_check_ratchet(mc_counts, baseline_path))

    if global_mode:
        rapport.lignes.extend(_bloc_calendrier(rapport.aides))
        rapport.lignes.extend(_bloc_dettes_editoriales(rapport.aides, facts))
    return rapport


# Volontairement PERMISSIF : la forme repliée (`fact: x`) comme la forme en flux
# (`applies_if: {fact: x}`), et jusqu'à une mention en commentaire. Sur-détecter
# fait dire « encore référencé » d'un fait qui ne l'est plus — un orphelin
# annoncé à tort, lui, ferait retirer un fait dont une aide dépend.
_REF_FAIT_RE = re.compile(r"\b(?:fact|levier):\s*['\"]?([A-Za-z0-9_]+)")


def faits_references_dans(*aides_dirs: Path) -> set[str]:
    """Les clés de faits citées par le catalogue ENTIER, par balayage textuel.

    Plusieurs dossiers parce que le banc d'essai en a deux : celui du run
    (`--sortie`) et le vrai `data/aides/`. N'en balayer qu'un ferait passer pour
    orphelins les faits proposés par tout le reste du catalogue.

    Charger les 396 fichiers coûte 2,7 s, le balayage 0,08 s — et il faut bien
    balayer tout le catalogue même quand le lint ne porte que sur un slug,
    sinon un fait proposé par une autre aide paraîtrait orphelin. L'agent
    d'ingestion lance ce lint plusieurs fois par aide : la différence se paie à
    chaque tour.

    Les deux méthodes rendent exactement les mêmes 711 clés sur le catalogue
    réel (`TestOrphelins.test_le_balayage_textuel_est_fidele_au_parsing`).
    """
    return {
        cle
        for dossier in aides_dirs
        if dossier.is_dir()
        for chemin in dossier.glob("*.yaml")
        for cle in _REF_FAIT_RE.findall(chemin.read_text(encoding="utf-8", errors="replace"))
    }


def compter_usage_faits(aides: list[Aide]) -> Counter[str]:
    """Combien de conditions citent chaque fait — `fact`, `applies_if.fact`, périmètre.

    Un fait seulement ciblé par un `applies_if` est bien « utilisé » : il
    déclenche une question. Les faits de périmètre d'une aide comptent aussi,
    ce sont même les premiers du questionnaire.
    """
    usage = Counter(
        ref
        for a in aides
        for c in a.conditions
        for ref in [c.fact, c.levier, c.applies_if.fact if c.applies_if else None]
        if ref
    )
    usage.update(a.applies_if.fact for a in aides if a.applies_if and a.applies_if.fact)
    return usage


def _statistiques(aides: list[Aide], facts: dict[str, FactDef]) -> list[str]:
    """Le tableau de bord du catalogue — seulement en mode global.

    En mono-slug ces chiffres seraient trompeurs (« 2 faits utilisés sur 239 »)
    et noieraient les trois lignes qui comptent.
    """
    lignes: list[str] = []
    kinds = Counter(c.kind for a in aides for c in a.conditions)
    fact_usage = compter_usage_faits(aides)
    n_cond = sum(kinds.values())
    n_typed = n_cond - kinds.get("untyped", 0)

    lignes.append(f"aides   : {len(aides)} fichiers valides")
    lignes.append(f"faits   : {len(facts)} dans l'ontologie, {len(fact_usage)} utilisés")
    lignes.append(
        f"conditions : {n_cond} au total — typées {n_typed} ({n_typed * 100 // max(n_cond, 1)} %)"
    )
    for kind, n in kinds.most_common():
        lignes.append(f"  {kind:<14} {n}")
    if fact_usage:
        lignes.append("faits les plus référencés :")
        for fact_id, n in fact_usage.most_common(10):
            lignes.append(f"  {fact_id:<32} {n} condition(s)")
    unused = sorted(set(facts) - set(fact_usage))
    if unused:
        lignes.append(f"faits non référencés ({len(unused)}) : {', '.join(unused)}")

    # Dette de provenance : conditions opposables à une source mais sans quote.
    # Non bloquant pendant la transition (les conditions venues des seeds n'ont
    # pas de source) ; toute aide ré-ingérée depuis sa source doit être à zéro.
    evaluables = [c for a in aides for c in a.conditions if c.kind in EVALUABLE_KINDS]
    sans_quote = sum(1 for c in evaluables if not c.quote)
    if evaluables:
        lignes.append(
            f"quotes : {len(evaluables) - sans_quote}/{len(evaluables)} conditions "
            f"évaluables sourcées — dette : {sans_quote}"
        )

    # Dette du marqueur porteur : un fait neuf ne naît jamais marqué, et rien
    # ne le fait naître marqué. Non bloquant — la liste est une invitation à
    # relire, pas un verdict (cf. `faits_entreprise_sans_marqueur`).
    sans_marqueur = faits_entreprise_sans_marqueur(facts)
    marques = sum(1 for f in facts.values() if f.porteurs_concernes)
    lignes.append(
        f"porteurs_concernes : {marques} fait(s) marqué(s) — "
        f"{len(sans_marqueur)} à relire (vocabulaire d'entreprise, aucun marqueur)"
    )
    if sans_marqueur:
        lignes.append(f"  {', '.join(sans_marqueur)}")

    # Combien d'aides s'en remettent au MARQUEUR plutôt qu'à un gate explicite.
    # Le message est mono-slug pour l'agent d'ingestion (cf. `lint`) ; ici, le
    # compte suffit — et il dit ce que vaut la dérivation sur le corpus.
    sous_derivation = [a.slug for a in aides if aides_sous_derivation_porteur(a, facts)]
    if sous_derivation:
        lignes.append(
            f"gate porteur dérivé du marqueur : {len(sous_derivation)} aide(s) — "
            "le marqueur fait le travail, elles n'ont pas de gate explicite"
        )

    sans_raison = sum(1 for a in aides if not a.raison)
    if sans_raison:
        lignes.append(f"raison : {sans_raison} aide(s) sans finalité — valeur en base préservée")

    # Couverture du rattachement au référentiel de pièces : le mapping est
    # incrémental (scripts/map_pieces.py), ce chiffre suit sa progression.
    total_pieces = sum(len(a.documents_requis) for a in aides)
    rattachees = sum(1 for a in aides for d in a.documents_requis if d.piece_id is not None)
    if total_pieces:
        pct = round(100 * rattachees / total_pieces)
        lignes.append(f"pièces rattachées au référentiel : {rattachees}/{total_pieces} ({pct} %)")
    return lignes


def _bloc_pending(
    aides: list[Aide],
    pending: dict[str, FactDef],
    strict: bool,
    rapport: RapportLint,
    *,
    usage_global: set[str] | None = None,
    global_mode: bool = False,
    faits_du_run: Sequence[str] = (),
) -> list[str]:
    """Les faits en attente, et ceux que plus aucune aide ne référence.

    `usage_global` est compté sur TOUT le catalogue, jamais sur les seules
    aides lintées : en mono-slug, un fait proposé par une autre aide paraîtrait
    orphelin à chaque passage, et l'agent d'ingestion se verrait reprocher le
    fait du voisin à chacun de ses lints.

    `global_mode` ne sert qu'à taire l'alerte « vocabulaire d'entreprise sans
    marqueur » : en global, `_statistiques` la donne déjà pour tout le
    catalogue, et la répéter ici la ferait lire deux fois — donc plus du tout.
    """
    if not pending:
        return []
    refs = [
        f"{a.slug} / {c.id} → {ref}"
        for a in aides
        for c in a.conditions
        for ref in [c.fact, c.levier, c.applies_if.fact if c.applies_if else None]
        if ref in pending
    ]
    lignes = [
        f"⏳ faits en attente d'approbation ({len(pending)}) : {', '.join(sorted(pending))}",
        *(f"   {ref}" for ref in refs),
    ]
    # F3 — la forme des faits proposés. AVERTISSEMENTS et jamais erreurs : 25
    # booléens à seuil et 97 questions longues sont déjà dans le fichier, et
    # rendre le lint rouge dessus bloquerait tout travail sur le lot avant de
    # l'avoir corrigé. La porte d'entrée, elle, les REFUSE (`faits.proposer`).
    a_seuil = sorted(cle for cle, f in pending.items() if booleen_a_seuil(cle, f))
    if a_seuil:
        rapport.avertissements.append(
            f"{len(a_seuil)} booléen(s) proposé(s) enferment un seuil chiffré dans leur clé "
            "— le seuil appartient au prédicat, pas au fait (un integer + `gte`) : "
            + ", ".join(a_seuil[:8])
            + (" …" if len(a_seuil) > 8 else "")
        )
    longues = sorted(
        cle for cle, f in pending.items() if question_trop_longue(f, maximum=MAX_CAR_QUESTION_LINT)
    )
    if longues:
        rapport.avertissements.append(
            f"{len(longues)} question(s) proposée(s) dépassent {MAX_CAR_QUESTION_LINT} "
            "caractères — une question est une phrase, le détail va dans `help` : "
            + ", ".join(longues[:8])
            + (" …" if len(longues) > 8 else "")
        )
    if usage_global is not None:
        orphelins = sorted(set(pending) - usage_global)
        if orphelins:
            # Un fait proposé que plus rien ne cite est un BROUILLON : l'agent a
            # changé d'avis et n'avait, avant `retirer_fait`, aucun moyen de
            # l'effacer. Il ne pose aucune question à personne — il encombre la
            # relecture humaine, qui doit arbitrer 526 entrées.
            lignes.append(
                f"   ⚠ {len(orphelins)} proposé(s) qu'AUCUNE aide ne référence "
                f"(brouillons à retirer) : {', '.join(orphelins)}"
            )
            if strict:
                rapport.erreurs.append(
                    f"--strict : {len(orphelins)} fait(s) proposé(s) sans aucune référence "
                    f"dans le catalogue — retirer de facts_pending.yaml : {', '.join(orphelins)}"
                )
            # F4 — un orphelin que CE RUN vient de proposer est une erreur, même
            # sans `--strict` : l'agent l'a écrit il y a trois tours, il peut le
            # retirer d'un `retirer_fait`, et laisser le brouillon derrière lui
            # est précisément ce qui a produit les 37 orphelins du lot. Ceux du
            # voisin restent un avertissement (cf.
            # `test_mono_slug_ne_declare_pas_orphelin_le_fait_dune_autre_aide`).
            miens = sorted(set(orphelins) & set(faits_du_run))
            if miens and not global_mode:
                rapport.erreurs.append(
                    f"{len(miens)} fait(s) que TU viens de proposer ne sont référencés par "
                    f"aucune condition : {', '.join(miens)}. Soit une condition les cite "
                    "(`ecrire_aide`), soit `retirer_fait` les efface — un brouillon laissé "
                    "derrière soi encombre la relecture humaine sans poser de question à "
                    "personne."
                )
    # Les faits que les aides lintées CITENT et qui sentent l'entreprise sans se
    # déclarer. En mono-slug, c'est exactement le fait que l'agent vient de
    # proposer : l'alerte arrive donc pendant qu'il peut encore le corriger, et
    # pas six mois plus tard dans une dette globale que personne ne lit.
    cites = {f for a in aides for c in a.conditions for f in (c.fact,) if f in pending}
    a_relire = [f for f in faits_entreprise_sans_marqueur(pending) if f in cites]
    if a_relire and not global_mode:
        lignes.append(
            f"   ⚠ {len(a_relire)} fait(s) au vocabulaire d'entreprise sans "
            f"`porteurs_concernes` : {', '.join(a_relire)} — si la question n'a de sens "
            "que pour une entreprise ou une exploitation, le déclarer (le lint obligera "
            "alors les aides à gater aussi statut_juridique_porteur)"
        )
    if strict:
        rapport.erreurs.append(
            f"--strict : {len(pending)} fait(s) non approuvé(s) dans facts_pending.yaml "
            "— approuver (déplacer vers facts.yaml) avant merge"
        )
    return lignes


def _bloc_quotes(rapport: RapportLint, global_mode: bool) -> None:
    """Vérifie chaque citation contre les snapshots, et range le verdict.

    En mono-slug l'absence est une ERREUR : l'aide vient d'être écrite depuis
    sa source, une citation qu'on ne retrouve pas y a donc été inventée ou
    recopiée de travers, et c'est précisément ce que le contrat d'ingestion
    interdit. En global c'est une information — la dette héritée des seeds
    (~6 % du corpus) ne peut pas casser la CI.
    """
    sans_snapshot: list[str] = []
    pdf_illisibles: list[tuple[str, str]] = []
    for aide in rapport.aides:
        documents, illisibles, _provenance = load_baselines(aide.slug)
        absentes, degradees, hors_portee = check_quotes(aide, documents, illisibles)
        rapport.quotes_absentes.extend(absentes)
        rapport.quotes_degradees.extend(degradees)
        rapport.quotes_hors_portee.extend(hors_portee)
        if hors_portee and not documents:
            sans_snapshot.append(aide.slug)
        elif illisibles:
            pdf_illisibles.append((aide.slug, ", ".join(illisibles)))

    citees = sum(1 for a in rapport.aides for c in a.conditions if c.quote)
    n_abs = len(rapport.quotes_absentes)
    rapport.lignes.append(
        f"quotes vérifiées : {citees} citation(s) — {n_abs} introuvable(s), "
        f"{len(rapport.quotes_degradees)} retrouvée(s) après normalisation, "
        f"{len(rapport.quotes_hors_portee)} hors portée (aucun snapshot, ou PDF illisible)"
    )

    if global_mode:
        for slug, cond_id, quote in rapport.quotes_absentes[:20]:
            rapport.lignes.append(f"  introuvable : {slug} / {cond_id} — « {_extrait(quote)} »")
        if n_abs > 20:
            rapport.lignes.append(f"  … et {n_abs - 20} autre(s)")
        return

    for slug, cond_id, quote in rapport.quotes_absentes:
        rapport.erreurs.append(
            f"{slug} / {cond_id}: quote introuvable dans les snapshots de "
            f"data/sources/{slug}/ — « {_extrait(quote)} »"
        )
    # Une aide qu'on vient d'ingérer DOIT avoir archivé sa source : sans
    # snapshot, aucune de ses citations n'est opposable et la review humaine
    # n'a rien à relire.
    for slug in sans_snapshot:
        rapport.erreurs.append(
            f"{slug}: citations présentes mais aucun snapshot exploitable dans "
            f"data/sources/{slug}/ — snapshoter la source avant de citer"
        )
    for slug, illisibles in pdf_illisibles:
        rapport.lignes.append(f"  {slug}: citations non vérifiables — PDF illisible ({illisibles})")


def _bloc_calendrier(aides: list[Aide]) -> list[str]:
    """Dette de calendrier : sans `permanent` ni aucune date structurée, la
    disponibilité (« maintenant » / « bientôt ») est indéterminable et l'aide
    est réputée ouverte par défaut. Non bloquant, même en --strict : 22
    fichiers sont dans ce cas et l'information n'est pas toujours sourçable."""
    sans_calendrier = sorted(
        a.slug
        for a in aides
        if not a.calendrier.permanent
        and not a.calendrier.date_ouverture
        and not a.calendrier.date_limite
    )
    if not sans_calendrier:
        return []
    return [
        f"calendrier : {len(sans_calendrier)} aide(s) non permanentes sans date "
        f"d'ouverture ni date limite — disponibilité indéterminable, réputée ouverte :",
        *(f"  {slug}" for slug in sans_calendrier),
    ]


def _bloc_dettes_editoriales(aides: list[Aide], facts: dict[str, FactDef]) -> list[str]:
    """Trois dettes que seul le catalogue ENTIER rend lisibles — toutes non
    bloquantes : elles se résorbent par lots éditoriaux, pas à l'ingestion.

    La quatrième, les aides « faire vivre » sans famille, est passée en ERREUR
    le 2026-09-22 une fois le backfill fait (`check_famille_faire_vivre`)."""
    lignes: list[str] = []
    fact_usage = compter_usage_faits(aides)

    # `applies_if` de condition qui RÉPÈTE le `pertinent_si` de son fait : la
    # clause est déjà reportée par le moteur, la recopier est du bruit. Non
    # bloquant — c'est un guide pour la migration éditoriale, et une clause
    # propre reste toujours légitime (elle est plus spécifique).
    redondantes = sorted(
        f"{a.slug} / {c.id} ({c.fact})"
        for a in aides
        for c in a.conditions
        if c.fact
        and c.applies_if
        and (pertinent := (facts[c.fact].pertinent_si if c.fact in facts else None))
        and c.applies_if.fact == pertinent.fact
        and c.applies_if.predicate.root == pertinent.predicate.root
    )
    if redondantes:
        lignes.append(
            f"pertinent_si : {len(redondantes)} condition(s) dont l'`applies_if` répète la "
            f"dépendance déjà déclarée sur le fait — retirable :"
        )
        lignes.extend(f"  {ligne}" for ligne in redondantes)

    # COHÉRENCE entre `raison` et « aucun travaux » : une aide ne porte
    # `valorisation_rayonnement` que si elle finance une action SANS chantier
    # (cf. data/TYPING.md, § `raison`). Le moteur sait le vérifier — si un de
    # ses gates est réfuté par « ce projet ne comporte pas de travaux », elle ne
    # le fait pas. C'est le filtre strict posé sur la DONNÉE plutôt qu'au
    # runtime : un tag faux se voit ici au lieu de se payer en aides hors sujet
    # et en questions de chantier dans un projet d'animation.
    #
    # Non bloquant : neuf aides restent dans ce cas pour une dette de TYPAGE
    # (plancher de dépenses posé sur `budget_travaux_estime`, gate `acheves`
    # appliqué à un prix d'action), qui se corrige en rouvrant la source. Le
    # ratchet, lui, vit dans
    # `tests/test_eligibility_engine.py::TestProjetSansTravaux`.
    incoherentes = []
    for aide in aides:
        refutes = gates_refutes_sans_travaux(aide, facts)
        if refutes:
            incoherentes.append(f"{aide.slug} — {', '.join(refutes)}")
    if incoherentes:
        lignes.append(
            f"raison : {len(incoherentes)} aide(s) `valorisation_rayonnement` qu'un projet SANS "
            f"TRAVAUX ne peut pas obtenir (tag faux, ou condition trop large) :"
        )
        lignes.extend(f"  {ligne}" for ligne in sorted(incoherentes))

    # `help` NOMINATIF sur un fait PARTAGÉ : la question est posée pour plusieurs
    # aides, et son aide contextuelle n'en nomme qu'une — le lecteur croit que la
    # question ne concerne que ce financeur-là, ou ce territoire-là. Le contexte
    # par aide se donne au complément (`contexteAide`) et sur la fiche, pas dans
    # le `help`. Non bloquant : la réécriture est éditoriale et se fait par lots.
    # Un marqueur que la QUESTION nomme déjà est intrinsèque au fait (« avez-vous
    # obtenu une subvention de l'État (DRAC) ? ») : ce n'est pas le contexte
    # d'une aide parmi d'autres, et le signaler ne serait que du bruit.
    nominatifs = sorted(
        f"{key} ({fact_usage[key]} aides) : {', '.join(sorted(noms))}"
        for key, f in facts.items()
        if fact_usage.get(key, 0) >= 2
        and f.help
        and (
            noms := set(MOTIFS_NOMINATIFS.findall(f.help))
            - set(MOTIFS_NOMINATIFS.findall(f.question or ""))
        )
    )
    if nominatifs:
        lignes.append(
            f"help nominatif : {len(nominatifs)} fait(s) partagé(s) par au moins deux aides "
            f"dont le `help` nomme un financeur ou un territoire :"
        )
        lignes.extend(f"  {ligne}" for ligne in nominatifs)

    return lignes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint_aides_data.py",
        description="Lint des données d'aides. Sans slug : tout le catalogue.",
    )
    parser.add_argument("slugs", nargs="*", help="n'auditer que ces aides (mode strict sur elles)")
    parser.add_argument(
        "--strict", action="store_true", help="échoue si des faits attendent une approbation"
    )
    parser.add_argument(
        "--quotes",
        action="store_true",
        help="vérifie chaque citation contre les snapshots de data/sources/",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="réécrit le ratchet manual_check depuis l'état courant (à relire au diff)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.update_baseline and args.slugs:
        # Le baseline est un plafond GLOBAL : le réécrire depuis un
        # sous-ensemble effacerait la dette de toutes les aides non citées.
        print("✗ --update-baseline porte sur tout le catalogue : ne pas passer de slug")
        return 2

    # Chemins passés explicitement, et lus dans les globales du module au
    # moment de l'appel : les valeurs par défaut de `lint()` sont figées à la
    # définition de la fonction, donc invisibles à un `mock.patch.object` — ce
    # qui rendrait les tests inopérants sur `main()`.
    rapport = lint(
        args.slugs,
        strict=args.strict,
        quotes=args.quotes,
        ratchet=not args.update_baseline,
        aides_dir=AIDES_DIR,
        facts_path=FACTS_FILE,
        pending_path=FACTS_PENDING_FILE,
        baseline_path=BASELINE_FILE,
    )
    print(rapport.texte())

    if args.update_baseline:
        counts = manual_check_counts(rapport.aides)
        BASELINE_FILE.write_text(
            json.dumps(counts, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline réécrit : {BASELINE_FILE.name} ({len(counts)} aide(s)) — à relire au diff")
    return 0 if rapport.ok else 1


if __name__ == "__main__":
    sys.exit(main())

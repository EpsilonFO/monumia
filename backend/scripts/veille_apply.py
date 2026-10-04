"""
Étage C, seconde moitié : valider la sortie du modèle et l'appliquer au YAML.

Le modèle ne touche jamais un fichier. Il rend un objet JSON que CE module
valide, puis applique par ÉDITION CHIRURGICALE — remplacement de plages de
texte, jamais de réécriture globale.

Pourquoi pas un round-trip YAML : les 142 fiches sont écrites à la main, avec
des styles hétérogènes d'un fichier à l'autre (indentation de listes à 0 ou 2
espaces, block scalars `>-`, commentaires explicatifs, lignes vides de
respiration). Re-sérialiser un fichier entier normaliserait tout ça et noierait
la vraie modification dans des centaines de lignes de reformatage. Or le
`git diff` EST la revue humaine : le noyer, c'est supprimer le seul contrôle
qui empêche une hallucination d'entrer dans les données.

D'où le test canonique, dans `tests/test_veille_apply.py` : appliquer une
sortie VIDE à chacune des 142 fiches doit produire un diff git strictement
vide. Tant qu'il passe, l'éditeur ne touche que ce qu'on lui a demandé.

Chaîne de validation, dans cet ordre (l'ordre est la sûreté) :
  1. parse JSON (fences retirées)
  2. schéma Pydantic, `extra="forbid"`
  3. contrôles référentiels : slug, ids existants/inédits, prédicats
  4. grep normalisé de CHAQUE quote dans le contenu frais
  5. application par plages, en mémoire
  6. assertion de différence profonde : ancien dict + changements == nouveau
     dict, sinon rollback
Un échec en 1-4 est rattrapable par UN retour au modèle avec les erreurs ;
un échec en 6 ne l'est pas — c'est un bug d'éditeur, on escalade.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import Aide, Predicate, charger_yaml, load_facts, load_pending_facts

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_aides_data import (
    check_aide,
    check_ecriture,
    check_fact_predicate,
    check_field_predicate,
    check_hors_gate,
)
from veille_text import find_quote_in_any, is_cosmetic_change, normalize_line

# Largeur de repli des block scalars, alignée sur `line-length = 100` de ruff
# et sur ce que font les fiches existantes.
WRAP_WIDTH = 88

# Champs modifiables par section. C'est une LISTE BLANCHE : tout le reste est
# hors du mandat de la veille (`description`, `demarche`, `documents_requis`
# relèvent de `/ingest-aide`), et un champ inconnu est une erreur, pas un
# silence.
CHAMPS_CALENDRIER = frozenset({"permanent", "date_ouverture", "date_limite", "delai_instruction"})
CHAMPS_FINANCEMENT = frozenset(
    {"montant_min", "montant_max", "taux_min", "taux_max", "plancher", "base_ttc", "assiette"}
)
CHAMPS_CUMUL = frozenset({"plafond_public_pct", "cumulable", "exclusions"})
CHAMPS_PAR_SECTION = {
    "calendrier": CHAMPS_CALENDRIER,
    "financement": CHAMPS_FINANCEMENT,
    "cumul": CHAMPS_CUMUL,
}

# Origine par défaut du libellé de note d'une condition ajoutée. Paramétrée
# parce que `veille_audit.py` réutilise cet éditeur : une condition ajoutée par
# l'audit d'exhaustivité ne vient PAS d'un changement de source, et la note doit
# le dire — c'est elle qui, dans six mois, expliquera d'où sort la condition.
ORIGINE_DEFAUT = "veille"


def note_ajout(origine: str, aujourd_hui: str) -> str:
    """Libellé de traçabilité d'une condition ajoutée, à typer plus tard.

    Un seul endroit pour le produire : l'éditeur et le témoin de différence
    profonde DOIVENT écrire exactement la même chaîne, sinon le deep-diff casse
    et l'aide part en échec d'édition alors que tout est correct.
    """
    return f"ajoutée par {origine} du {aujourd_hui}, à typer"


# Champs modifiables sur une condition existante par la VEILLE. `kind`,
# `effect`, `fact` et `field` en sont ABSENTS volontairement : les changer,
# c'est re-typer la condition, ce qui ne relève pas d'une retouche de source.
CHAMPS_CONDITION = frozenset({"text", "quote", "notes", "predicate"})

# Liste blanche du TYPAGE (`veille_typage.py`), qui a précisément pour mandat de
# poser kind/effect/fact/field/predicate sur une condition `untyped`. Elle est
# passée explicitement à `appliquer` : la valeur par défaut reste celle de la
# veille, pour qu'aucun appelant existant ne gagne ce pouvoir par accident.
# `text` et `quote` en sont exclus — le typage ne touche jamais au fond, et
# reformuler le texte d'une condition reste interdit quel que soit l'outil.
CHAMPS_TYPAGE = frozenset({"kind", "effect", "fact", "field", "predicate", "notes"})

# Ordre des champs d'une condition dans les fiches écrites à la main. Sert à
# INSÉRER un champ absent à sa place plutôt qu'en fin d'item : le `git diff` est
# la revue, et un `effect` atterrissant après `notes` fait buter le relecteur
# sur la forme au lieu du fond. Un champ hors de cette liste va en fin d'item.
ORDRE_CHAMPS_CONDITION = (
    "id",
    "text",
    "kind",
    "effect",
    "fact",
    "field",
    "predicate",
    "applies_if",
    "derogation_possible",
    "levier",
    "quote",
    "notes",
)


# ---------------------------------------------------------------------------
# Schéma de sortie du modèle
# ---------------------------------------------------------------------------


class MajSection(BaseModel):
    """Mise à jour d'une section structurée (calendrier, financement, cumul)."""

    model_config = ConfigDict(extra="forbid")

    champs: dict[str, Any]
    # Citation du CONTENU FRAIS qui justifie la modification. Vérifiée par grep
    # normalisé : sans elle, rien ne distingue une lecture d'une invention.
    quote: str


class NouvelleCondition(BaseModel):
    """Condition ajoutée. Jamais typée par la veille — c'est le rôle de /typer-aides."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    text: str
    kind: Literal["untyped", "info"] = "untyped"
    quote: str
    notes: str | None = None


class ChangementCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["update", "add", "signaler_disparue"]
    id: str
    champs: dict[str, Any] | None = None
    condition: NouvelleCondition | None = None
    apres_id: str | None = None


class VeilleLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Facultatif : l'aide traitée est connue de l'appelant. Ce champ ne sert que
    # de contre-contrôle contre une confusion de fiche — l'exiger ferait échouer
    # gratuitement les fournisseurs qui ne savent pas contraindre un schéma.
    slug: str | None = None
    # Auto-déclaration : le modèle peut dire « ça me dépasse ». Rien n'est
    # appliqué, l'aide part en ré-ingestion complète. C'est une porte de
    # sortie volontairement facile à emprunter.
    changement_majeur: bool = False
    raison_changement_majeur: str | None = None
    resume: str = ""
    calendrier: MajSection | None = None
    financement: MajSection | None = None
    cumul: MajSection | None = None
    conditions: list[ChangementCondition] = []

    @property
    def est_vide(self) -> bool:
        return not (self.calendrier or self.financement or self.cumul or self.conditions)


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------

Issue = Literal[
    "json",
    "schema",
    "referentiel",
    "quote",
    "ancrage",
    "majeur",
    "structure",
    "edition",
    "deep_diff",
    "lint",
    "coherence",
]


@dataclass
class ApplyResult:
    slug: str
    ok: bool = False
    # Erreurs renvoyées au modèle lors de l'unique nouvelle tentative.
    erreurs: list[str] = field(default_factory=list)
    # Étape ayant échoué : décide si un retour au modèle a un sens.
    etape: Issue | None = None
    texte: str | None = None
    output: VeilleLLMOutput | None = None
    champs_touches: list[str] = field(default_factory=list)
    cosmetiques: int = 0

    @property
    def rattrapable(self) -> bool:
        """Un retour au modèle peut-il corriger ça ?

        Oui pour ce qu'il a lui-même produit (JSON, schéma, références,
        citations). Non pour un échec d'édition ou de différence profonde :
        c'est notre bug, pas le sien, et le relancer ne ferait que brûler des
        jetons avant d'escalader quand même.

        Non non plus pour `majeur` : un « ça me dépasse » auto-déclaré est une
        RÉPONSE, pas une erreur. Le redemander coûterait un appel pour, au
        mieux, la même réponse — au pire une contradiction.

        Non pour `ancrage` : le modèle a cité correctement une page qui n'a pas
        bougé sur ce point. Il n'a rien à corriger, c'est sa lecture de la tâche
        qui est en cause. Le relancer produirait la même proposition.

        Non pour `structure` : une condition apparue ou disparue est un constat,
        et il envoie l'aide en ré-ingestion.

        Oui pour `coherence` : la fiche obtenue est valide mais le lint la refuse
        (une `date_limite` posée sans lever `permanent: true`, par exemple), et
        c'est au modèle de compléter sa réponse.
        """
        return self.etape in ("json", "schema", "referentiel", "quote", "coherence")


# ---------------------------------------------------------------------------
# Étapes 1 et 2 : JSON puis schéma
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def parse_json_output[M: BaseModel](
    texte: str, modele: type[M]
) -> tuple[M | None, list[str], Issue | None]:
    """Étapes 1-2, génériques sur le modèle de sortie attendu.

    Générique depuis que `veille_audit.py` valide sa propre sortie : la
    tolérance aux fences et la mise en forme des erreurs de schéma doivent être
    IDENTIQUES d'un outil à l'autre, sinon un modèle acceptable pour la veille
    serait rejeté par l'audit pour une raison de forme.
    """
    brut = texte.strip()
    if m := _FENCE_RE.match(brut):
        brut = m.group(1)
    try:
        data = json.loads(brut)
    except json.JSONDecodeError as exc:
        # Un objet complet suivi de texte (« Extra data ») : certains modèles
        # ajoutent une phrase après le JSON malgré la consigne. L'objet est
        # entier et valide, on le prend ; tout autre défaut reste une erreur.
        # Mesuré au benchmark d'audit du 2026-09-01 : un cas sur cinq perdu
        # pour glm-5.3-flash à cause d'un commentaire final.
        try:
            data, _fin = json.JSONDecoder().raw_decode(brut)
        except json.JSONDecodeError:
            return None, [f"JSON invalide : {exc}"], "json"
    if not isinstance(data, dict):
        return None, [f"objet JSON attendu, reçu {type(data).__name__}"], "json"
    try:
        return modele.model_validate(data), [], None
    except ValidationError as exc:
        erreurs = [f"{'.'.join(str(p) for p in e['loc'])} : {e['msg']}" for e in exc.errors()[:12]]
        return None, erreurs, "schema"


def parse_output(texte: str, slug: str) -> tuple[VeilleLLMOutput | None, list[str], Issue | None]:
    """Étapes 1-2 pour la sortie de veille. `slug` reste pour la compatibilité."""
    return parse_json_output(texte, VeilleLLMOutput)


# ---------------------------------------------------------------------------
# Étape 3 : contrôles référentiels
# ---------------------------------------------------------------------------


def check_referentiel(
    out: VeilleLLMOutput,
    aide: Aide,
    champs_autorises: frozenset[str] = CHAMPS_CONDITION,
    facts_extra: dict[str, Any] | None = None,
) -> list[str]:
    """Le modèle parle-t-il bien de CETTE aide, et de conditions qui existent ?"""
    erreurs: list[str] = []
    if out.slug is not None and out.slug != aide.slug:
        erreurs.append(f"slug « {out.slug} » ≠ aide traitée « {aide.slug} »")

    existants = {c.id for c in aide.conditions}
    vus: set[str] = set()
    for chg in out.conditions:
        if chg.id in vus:
            erreurs.append(f"condition « {chg.id} » : visée deux fois")
        vus.add(chg.id)

        if chg.op == "add":
            if chg.condition is None:
                erreurs.append(f"condition « {chg.id} » : op=add exige `condition`")
                continue
            if chg.condition.id != chg.id:
                erreurs.append(f"condition « {chg.id} » : id différent dans `condition`")
            if chg.id in existants:
                erreurs.append(f"condition « {chg.id} » : id déjà utilisé, choisir un id inédit")
            if chg.apres_id and chg.apres_id not in existants:
                erreurs.append(f"condition « {chg.id} » : apres_id « {chg.apres_id} » inconnu")
        else:
            if chg.id not in existants:
                erreurs.append(f"condition « {chg.id} » : inconnue dans l'aide")
            if chg.op == "update":
                erreurs.extend(_check_update(chg, aide, champs_autorises, facts_extra))

    for nom, section in (
        ("calendrier", out.calendrier),
        ("financement", out.financement),
        ("cumul", out.cumul),
    ):
        if section is None:
            continue
        if not section.champs:
            erreurs.append(f"{nom} : `champs` vide — omettre la section plutôt que la vider")
        inconnus = sorted(set(section.champs) - CHAMPS_PAR_SECTION[nom])
        if inconnus:
            erreurs.append(
                f"{nom} : champ(s) hors périmètre {inconnus} — "
                f"autorisés : {sorted(CHAMPS_PAR_SECTION[nom])}"
            )
    return erreurs


def _check_update(
    chg: ChangementCondition,
    aide: Aide,
    champs_autorises: frozenset[str] = CHAMPS_CONDITION,
    facts_extra: dict[str, Any] | None = None,
) -> list[str]:
    erreurs: list[str] = []
    if not chg.champs:
        erreurs.append(f"condition « {chg.id} » : op=update exige `champs`")
        return erreurs
    hors = sorted(set(chg.champs) - champs_autorises)
    if hors:
        erreurs.append(
            f"condition « {chg.id} » : champ(s) {hors} non modifiables par la veille. "
            "Changer kind/effect/fact/field est un changement majeur : "
            "répondre changement_majeur=true."
        )
    if "predicate" in chg.champs:
        erreurs.extend(_check_predicate(chg, aide, facts_extra))
    return erreurs


def _check_predicate(
    chg: ChangementCondition, aide: Aide, facts_extra: dict[str, Any] | None = None
) -> list[str]:
    """Valide un prédicat avec les MÊMES contrôles que le linter du dépôt.

    Réutilisés tels quels plutôt que réécrits : un prédicat que la veille
    accepterait et que le lint refuse laisserait le dépôt cassé après coup.

    `facts_extra` porte les faits qui n'existent pas ENCORE sur disque : le
    typage (`veille_typage.py`) propose un fait et pose un prédicat dessus dans
    le même mouvement, et `facts_pending.yaml` n'est écrit qu'une fois l'édition
    validée — pour ne pas y laisser un fait orphelin si l'écriture échoue.
    """
    cond = next((c for c in aide.conditions if c.id == chg.id), None)
    if cond is None:
        return []
    assert chg.champs is not None
    try:
        predicate = Predicate.model_validate(chg.champs["predicate"])
    except ValidationError as exc:
        return [f"condition « {chg.id} » : prédicat invalide — {exc.errors()[0]['msg']}"]
    where = f"condition « {chg.id} »"
    # Le prédicat se valide contre le kind, le fait et le champ que la condition
    # AURA une fois le changement appliqué, pas contre ceux qu'elle a encore.
    # Sans ça, un re-typage `untyped` → `user_fact` posé dans le même update se
    # ferait refuser au motif que `untyped` n'admet pas de prédicat.
    champs = chg.champs
    kind = champs.get("kind", cond.kind)
    if kind == "user_fact":
        facts = {**load_facts(), **load_pending_facts(), **(facts_extra or {})}
        return check_fact_predicate(where, champs.get("fact", cond.fact), predicate, facts)
    if kind == "auto":
        return check_field_predicate(where, champs.get("field", cond.field), predicate)
    return [f"{where} : kind={kind} n'admet pas de prédicat"]


# ---------------------------------------------------------------------------
# Étape 4 : chaque citation existe-t-elle dans le contenu frais ?
# ---------------------------------------------------------------------------


def check_quotes(out: VeilleLLMOutput, documents: list[tuple[str, str, str]]) -> list[str]:
    """Grep normalisé de CHAQUE quote produite par le modèle.

    C'est le garde-fou central du dispositif : une citation introuvable dans le
    document qu'on vient de télécharger est une invention, quelle que soit sa
    vraisemblance. Le même `find_quote_in_any` sert ici et au triage — une
    citation acceptée à l'analyse ne peut pas être refusée ici pour une raison
    de tolérance différente.
    """
    erreurs: list[str] = []
    if not documents:
        return ["aucun contenu frais : impossible de vérifier les citations"]

    def verifier(quote: str, ou: str) -> None:
        if not quote.strip():
            erreurs.append(f"{ou} : citation vide")
            return
        _, match = find_quote_in_any(quote, documents)  # type: ignore[arg-type]
        if not match.found:
            extrait = " ".join(quote.split())[:90]
            erreurs.append(
                f"{ou} : citation introuvable dans la source fraîche "
                f"(préfixe commun {match.prefix_ratio:.0%}) — « {extrait} »"
            )

    for nom, section in (
        ("calendrier", out.calendrier),
        ("financement", out.financement),
        ("cumul", out.cumul),
    ):
        if section is not None:
            verifier(section.quote, nom)
    for chg in out.conditions:
        if chg.op == "add" and chg.condition is not None:
            verifier(chg.condition.quote, f"condition « {chg.id} »")
        elif chg.op == "update" and chg.champs and "quote" in chg.champs:
            verifier(str(chg.champs["quote"]), f"condition « {chg.id} »")
    return erreurs


# ---------------------------------------------------------------------------
# Étape 5 : la citation vient-elle de ce qui a CHANGÉ ?
# ---------------------------------------------------------------------------


def lignes_ajoutees(diff: str) -> str:
    """Contenu des seules lignes `+` d'un diff, concaténé.

    Sert de document au grep d'ancrage. Les lignes `-` sont exclues : une
    citation qui ne se trouve que dans le texte SUPPRIMÉ décrit l'ancien
    règlement, pas le nouveau.
    """
    return "\n".join(ligne[2:] for ligne in diff.splitlines() if ligne.startswith("+ "))


def _seulement_des_disparitions(out: VeilleLLMOutput) -> bool:
    """La sortie ne fait que signaler des conditions disparues de la source."""
    return (
        out.calendrier is None
        and out.financement is None
        and out.cumul is None
        and bool(out.conditions)
        and all(c.op == "signaler_disparue" for c in out.conditions)
    )


def check_ancrage(out: VeilleLLMOutput, diff: str) -> list[str]:
    """Chaque citation justifiant un changement doit venir de ce qui a CHANGÉ.

    `check_quotes` demande « cette citation est-elle dans la page ? ». La page
    ayant toujours dit ce qu'elle dit, une citation authentique n'y prouve rien :
    c'est ainsi qu'un faux changement de taux a franchi toute la chaîne sur
    `pdl-restauration-mh`, cité mot pour mot depuis une page dont le passage en
    question n'avait pas bougé d'une virgule.

    La question utile est « cette citation est-elle dans ce qui a changé ? ».
    Le grep porte donc sur les seules lignes ajoutées du diff.

    Le mandat de la veille étant la RETOUCHE de ce qui a bougé, une proposition
    non ancrée est hors mandat — même quand elle est juste. Si la fiche diverge
    de la source sans que la source ait changé, c'est une erreur d'ingestion à
    reprendre par `/ingest-aide`, pas une mise à jour.

    Faux négatifs assumés : diff tronqué par `MAX_CHARS_DIFF`, clause déplacée
    sans être modifiée, page régénérée sous un autre gabarit. L'appelant traite
    donc cet échec en ESCALADE et non en rejet sec — la proposition part à la
    relecture humaine au lieu d'être perdue.
    """
    ajoutees = lignes_ajoutees(diff)
    if not ajoutees.strip():
        # Aucune ligne ajoutée : rien n'a pu motiver une MODIFICATION. Le cas
        # se produit quand le triage a déclenché sur des suppressions seules,
        # ou sur des citations manquantes. Une sortie qui ne fait que signaler
        # des conditions disparues est précisément ce qu'un tel diff appelle :
        # la refuser ici envoyait en escalade le cas nominal de
        # `signaler_disparue`.
        if out.est_vide or _seulement_des_disparitions(out):
            return []
        return ["aucune ligne ajoutée dans le diff : aucun changement à retoucher"]

    documents: list[tuple[str, str, str]] = [("diff", ajoutees, "text")]
    erreurs: list[str] = []

    def ancrer(quote: str, ou: str) -> None:
        """Au moins une LIGNE substantielle de la citation doit être ajoutée.

        Pas la citation entière et contiguë : une citation qui couvre une zone
        de tableau ou de liste enjambe des lignes inchangées, et le diff ne
        garde que les lignes modifiées. Exiger la contiguïté rejetait alors un
        vrai changement — mesuré sur `56-valorisation-restauration-patrimoine`,
        dont trois lignes de la citation étaient bien des ajouts mais séparées
        par du contexte (préfixe commun 53 %).

        La question utile n'est pas « toute la citation est-elle neuve ? » mais
        « ce que tu cites contient-il du neuf ? ». Si AUCUNE de ses lignes n'a
        été ajoutée, la proposition ne décrit pas un changement.
        """
        if not quote.strip():
            return
        lignes = [ligne for ligne in quote.splitlines() if len(normalize_line(ligne)) >= 25]
        # Citation trop courte pour être découpée : contrôle global, la
        # contiguïté n'est alors pas une contrainte supplémentaire.
        candidates = lignes or [quote]
        for ligne in candidates:
            _, match = find_quote_in_any(ligne, documents)  # type: ignore[arg-type]
            if match.found:
                return
        extrait = " ".join(quote.split())[:90]
        erreurs.append(
            f"{ou} : aucune ligne de la citation ne figure dans les ajouts du "
            f"diff — la source n'a pas changé sur ce point « {extrait} »"
        )

    for nom, section in (
        ("calendrier", out.calendrier),
        ("financement", out.financement),
        ("cumul", out.cumul),
    ):
        if section is not None:
            ancrer(section.quote, nom)
    for chg in out.conditions:
        # `signaler_disparue` n'a par nature aucune citation à ancrer : ce qui
        # la justifie est une ABSENCE. Elle échappe donc à ce contrôle.
        if chg.op == "signaler_disparue":
            continue
        quote = (chg.champs or {}).get("quote") if chg.champs else None
        if chg.condition is not None:
            quote = chg.condition.quote
        if quote:
            ancrer(quote, f"condition « {chg.id} »")
    return erreurs


# ---------------------------------------------------------------------------
# Étape 5 : édition chirurgicale
# ---------------------------------------------------------------------------

_PLAIN_INTERDIT = re.compile(r"^[\s\-?:,\[\]{}#&*!|>'\"%@`]|: | #|[\n\t]|\s$")
_RESERVES = {
    "true", "false", "null", "yes", "no", "on", "off", "~", "",
}  # fmt: skip


def _plain_sur(valeur: str) -> bool:
    """La valeur peut-elle s'écrire sans guillemets ni block scalar ?"""
    if _PLAIN_INTERDIT.search(valeur) or valeur.lower() in _RESERVES:
        return False
    try:
        float(valeur)
    except ValueError:
        return True
    return False  # un nombre en clair changerait de type


def emit_field(cle: str, valeur: Any, indent: int) -> list[str]:
    """Rend `cle: valeur` dans le style du dépôt, en lignes sans saut final.

    Les chaînes longues passent en `>-` (replié) et celles à sauts de ligne
    significatifs en `|-`, comme les fiches écrites à la main.
    """
    pad = " " * indent
    if valeur is None:
        return [f"{pad}{cle}:"]
    if isinstance(valeur, bool):
        return [f"{pad}{cle}: {'true' if valeur else 'false'}"]
    if isinstance(valeur, (int, float)):
        return [f"{pad}{cle}: {valeur}"]
    if isinstance(valeur, list):
        if not valeur:
            return [f"{pad}{cle}: []"]
        lignes = [f"{pad}{cle}:"]
        for item in valeur:
            lignes.extend(emit_item(item, indent + 2))
        return lignes
    if isinstance(valeur, dict):
        lignes = [f"{pad}{cle}:"]
        for k, v in valeur.items():
            lignes.extend(emit_field(k, v, indent + 2))
        return lignes

    return _emit_chaine(cle, str(valeur), indent)


def _emit_chaine(cle: str, texte: str, indent: int) -> list[str]:
    """Rend une chaîne dans le style du dépôt, en VÉRIFIANT le rendu.

    Chaque style candidat est relu avant d'être retenu. Sans ce contrôle, un
    scalaire replié avale silencieusement les espaces multiples et finaux
    (« 5 000  € » deviendrait « 5 000 € ») : une citation altérée à l'écriture,
    donc une preuve fausse, et le lint ne verrait rien puisque le YAML reste
    valide. Le style le plus lisible qui round-trip exactement gagne ; les
    guillemets ne servent que de dernier recours.
    """
    pad = " " * indent
    candidats: list[list[str]] = []
    if "\n" not in texte:
        une_ligne = f"{pad}{cle}: {texte}"
        if len(une_ligne) <= WRAP_WIDTH and _plain_sur(texte):
            candidats.append([une_ligne])
        candidats.append([f"{pad}{cle}: >-", *_replier(texte, indent + 2)])
    else:
        candidats.append(
            [f"{pad}{cle}: |-", *[f"{pad}  {ligne}".rstrip() for ligne in texte.split("\n")]]
        )
    # Dernier recours : double quotes. Le sous-ensemble d'échappement de JSON
    # est valide en YAML double-quoted, donc `json.dumps` suffit et couvre tout.
    candidats.append([f"{pad}{cle}: {json.dumps(texte, ensure_ascii=False)}"])

    for candidat in candidats:
        if _relit_identique(candidat, cle, texte, indent):
            return candidat
    return candidats[-1]


def _relit_identique(lignes: list[str], cle: str, attendu: str, indent: int) -> bool:
    fragment = "\n".join(ligne[indent:] for ligne in lignes)
    try:
        recharge = charger_yaml(fragment)
    except yaml.YAMLError:
        return False
    return isinstance(recharge, dict) and recharge.get(cle) == attendu


def _replier(texte: str, indent: int) -> list[str]:
    """Replie un texte pour un block scalar `>-`.

    Aucune ligne produite ne commence par une espace supplémentaire : dans un
    scalaire replié, une ligne plus indentée que le bloc est conservée
    littéralement, ce qui injecterait un saut de ligne parasite.
    """
    pad = " " * indent
    lignes: list[str] = []
    courante = ""
    for mot in texte.split():
        essai = f"{courante} {mot}" if courante else mot
        if courante and len(pad) + len(essai) > WRAP_WIDTH:
            lignes.append(pad + courante)
            courante = mot
        else:
            courante = essai
    if courante:
        lignes.append(pad + courante)
    return lignes or [pad]


def emit_item(valeur: Any, indent: int) -> list[str]:
    """Rend un item de liste (`- ...`) au niveau d'indentation donné."""
    pad = " " * indent
    if isinstance(valeur, dict):
        lignes: list[str] = []
        for i, (k, v) in enumerate(valeur.items()):
            rendu = emit_field(k, v, indent + 2)
            # Le premier champ porte le tiret, à la place des deux espaces.
            lignes.append(f"{pad}- {rendu[0][indent + 2 :]}" if i == 0 else rendu[0])
            lignes.extend(rendu[1:])
        return lignes
    rendu = emit_field("_", valeur, indent)
    return [f"{pad}- {rendu[0][indent + 3 :]}", *rendu[1:]]


def _indent_de(ligne: str) -> int:
    return len(ligne) - len(ligne.lstrip())


def _neutre(ligne: str, indent: int) -> bool:
    """Ligne qui ne délimite rien : vide, ou commentaire au niveau du bloc.

    Un commentaire ne termine pas plus un bloc qu'une ligne vide — plusieurs
    fiches intercalent des titres de section (`# ── II.2 Candidature ──`) entre
    leurs conditions, et les prendre pour la fin du bloc rendait toutes les
    conditions suivantes introuvables. Comme une ligne vide, il ne l'étend pas
    non plus : un commentaire final appartient à ce qui suit, pas au champ.

    Le test d'indentation est ce qui protège les block scalars : une ligne
    commençant par « # » PLUS indentée que la clé est du texte, pas un
    commentaire.
    """
    nu = ligne.strip()
    return not nu or (nu.startswith("#") and _indent_de(ligne) <= indent)


def _span_champ(lignes: list[str], ligne_cle: int) -> tuple[int, int]:
    """Plage [début, fin) du champ commençant à `ligne_cle`, valeur comprise.

    Le champ court jusqu'à la première ligne non vide moins indentée que la clé
    — c'est ce qui délimite un block scalar sans avoir à le reparser. Les lignes
    vides finales restent dehors : elles séparent les blocs et font partie de la
    respiration du fichier.

    L'exception des tirets n'en est pas une : YAML autorise une séquence en bloc
    à la MÊME indentation que la clé qui la porte, et 26 des 142 fiches écrivent
    ainsi leurs conditions. Sans ce cas, le bloc `conditions:` de ces fiches
    s'arrêtait à sa première ligne — plus aucune condition n'y était localisable,
    donc aucune retouche possible, sur 18 % du parc. Trouvé au run pilote de
    l'étage C sur `fctva`.
    """
    indent = _indent_de(lignes[ligne_cle])
    fin = ligne_cle
    i = ligne_cle + 1
    while i < len(lignes):
        if not _neutre(lignes[i], indent):
            ind = _indent_de(lignes[i])
            if ind < indent or (ind == indent and not lignes[i].lstrip().startswith("- ")):
                break
            fin = i
        i += 1
    return ligne_cle, fin + 1


def _localiser(lignes: list[str], chemin: list[str]) -> int | None:
    """Numéro de ligne de la clé désignée par `chemin`, ou None.

    Recherche descendante et indentée plutôt que par ruamel : on ne cherche
    qu'une position, et une correspondance textuelle contrainte par
    l'indentation du parent est plus simple à auditer qu'un arbre de nœuds.
    """
    debut, fin = 0, len(lignes)
    ligne_trouvee = None
    for cle in chemin:
        motif = re.compile(rf"^(\s*){re.escape(cle)}:")
        # Le premier niveau est la racine du document, les suivants l'enfant
        # DIRECT du précédent. Chercher « à n'importe quelle profondeur » faisait
        # trouver `fiche.essentiel.calendrier` dans une fiche sans section
        # `calendrier:`, et y diriger l'édition.
        indent_attendu = 0 if ligne_trouvee is None else _indent_enfants(lignes, debut, fin)
        ligne_trouvee = None
        for i in range(debut, fin):
            m = motif.match(lignes[i])
            if m and len(m.group(1)) == indent_attendu:
                ligne_trouvee = i
                break
        if ligne_trouvee is None:
            return None
        debut, fin = _span_champ(lignes, ligne_trouvee)
        debut += 1
    return ligne_trouvee


def _indent_enfants(lignes: list[str], debut: int, fin: int) -> int:
    """Indentation des clés enfants d'un mapping, lue sur sa première ligne utile."""
    for i in range(debut, fin):
        if not _neutre(lignes[i], 10**6):
            return _indent_de(lignes[i])
    return -1


def _localiser_condition(lignes: list[str], cond_id: str) -> tuple[int, int] | None:
    """Plage [début, fin) de l'item de condition portant cet id."""
    debut_conditions = _localiser(lignes, ["conditions"])
    if debut_conditions is None:
        return None
    _, fin_bloc = _span_champ(lignes, debut_conditions)
    motif = re.compile(rf"^(\s*)-\s+id:\s*{re.escape(cond_id)}\s*$")
    for i in range(debut_conditions + 1, fin_bloc):
        if m := motif.match(lignes[i]):
            indent_item = len(m.group(1))
            fin = i
            j = i + 1
            while j < fin_bloc:
                if not _neutre(lignes[j], indent_item):
                    ind = _indent_de(lignes[j])
                    if ind < indent_item or (
                        ind == indent_item and lignes[j].lstrip().startswith("- ")
                    ):
                        break
                    fin = j
                j += 1
            return i, fin + 1
    return None


@dataclass
class _Edition:
    """Une substitution de plage, à appliquer de la fin vers le début."""

    debut: int
    fin: int
    remplacement: list[str]
    etiquette: str
    # Section créée : à point d'insertion égal, elle passe APRÈS les champs
    # ajoutés en fin de la section précédente, sinon ces champs atterriraient
    # sous la nouvelle clé.
    nouvelle_section: bool = False


def _editions_section(
    lignes: list[str], section: str, champs: dict[str, Any]
) -> tuple[list[_Edition], list[str]]:
    editions: list[_Edition] = []
    erreurs: list[str] = []
    ligne_section = _localiser(lignes, [section])
    if ligne_section is None:
        # Section absente : le schéma lui donne ses valeurs par défaut (29 % des
        # fiches n'écrivent pas `cumul`), et le prompt les montre au modèle
        # comme si elles étaient écrites. On crée la section à sa place.
        return [_edition_nouvelle_section(lignes, section, champs)], []
    if re.fullmatch(rf"{re.escape(section)}:\s*\{{\}}\s*", lignes[ligne_section]):
        # Section vide écrite en flow, comme `yaml.safe_dump` écrit un mapping
        # vide : on l'ouvre en bloc à la même place.
        nouvelle = _edition_nouvelle_section(lignes, section, champs)
        return [
            _Edition(ligne_section, ligne_section + 1, nouvelle.remplacement, nouvelle.etiquette)
        ], []
    indent_section = _indent_de(lignes[ligne_section])
    _, fin_section = _span_champ(lignes, ligne_section)

    for cle, valeur in champs.items():
        ligne_cle = _localiser(lignes, [section, cle])
        if ligne_cle is not None and ligne_cle < fin_section:
            debut, fin = _span_champ(lignes, ligne_cle)
            editions.append(
                _Edition(
                    debut,
                    fin,
                    emit_field(cle, valeur, _indent_de(lignes[ligne_cle])),
                    f"{section}.{cle}",
                )
            )
        else:
            # Champ absent : insertion en fin de section, à l'indentation de ses
            # voisins (ou +2 si la section est un mapping vide type `{}`).
            indent = indent_section + 2
            for i in range(ligne_section + 1, fin_section):
                if lignes[i].strip():
                    indent = _indent_de(lignes[i])
                    break
            if lignes[ligne_section].strip().endswith(("{}", "[]")):
                erreurs.append(
                    f"{section}.{cle} : section vide écrite en flow (`{{}}`) — "
                    "à ouvrir à la main avant application automatique"
                )
                continue
            editions.append(
                _Edition(
                    fin_section,
                    fin_section,
                    emit_field(cle, valeur, indent),
                    f"{section}.{cle} (ajout)",
                )
            )
    return editions, erreurs


# Ordre des sections au premier niveau des fiches (celui de `Aide`, et celui de
# 193 des 200 fiches qui écrivent `cumul`). Une section créée se range avant la
# première section présente qui la suit.
ORDRE_SECTIONS = (
    "source",
    "financement",
    "cumul",
    "calendrier",
    "hard_filters",
    "conditions",
    "demarche",
    "documents_requis",
    "tags",
    "fiche",
)


def _edition_nouvelle_section(lignes: list[str], section: str, champs: dict[str, Any]) -> _Edition:
    point = len(lignes)
    while point > 0 and not lignes[point - 1].strip():
        point -= 1
    for suivante in ORDRE_SECTIONS[ORDRE_SECTIONS.index(section) + 1 :]:
        if (ligne := _localiser(lignes, [suivante])) is not None:
            point = ligne
            break
    rendu = [f"{section}:"]
    for cle, valeur in champs.items():
        rendu.extend(emit_field(cle, valeur, 2))
    return _Edition(point, point, rendu, f"{section} (nouvelle section)", nouvelle_section=True)


def _editions_conditions(
    lignes: list[str],
    changements: list[ChangementCondition],
    aujourd_hui: str,
    origine: str = ORIGINE_DEFAUT,
) -> tuple[list[_Edition], list[str], int]:
    editions: list[_Edition] = []
    erreurs: list[str] = []
    cosmetiques = 0

    for chg in changements:
        if chg.op == "add":
            assert chg.condition is not None
            editions.append(_edition_ajout(lignes, chg, aujourd_hui, origine))
            continue

        span = _localiser_condition(lignes, chg.id)
        if span is None:
            erreurs.append(f"condition « {chg.id} » : item introuvable dans le fichier")
            continue
        debut_item, fin_item = span

        if chg.op == "signaler_disparue":
            # On ne supprime JAMAIS : une condition peut avoir disparu d'une
            # page sans disparaître du règlement. On annote, un humain tranche.
            note = f"non retrouvée dans la source du {aujourd_hui} : à confirmer ou supprimer"
            edition, err = _edition_note(lignes, debut_item, fin_item, chg.id, note)
            editions.append(edition) if edition else erreurs.append(err or "")
            continue

        assert chg.champs is not None
        for cle, valeur in chg.champs.items():
            ligne_cle = _localiser_dans(lignes, debut_item, fin_item, cle)
            if ligne_cle is None:
                indent = _indent_de(lignes[debut_item]) + 2
                point = _point_insertion(lignes, debut_item, fin_item, cle)
                editions.append(
                    _Edition(
                        point,
                        point,
                        emit_field(cle, valeur, indent),
                        f"{chg.id}.{cle} (ajout)",
                    )
                )
                continue
            debut, fin = _span_champ(lignes, ligne_cle)
            ancien = "\n".join(lignes[debut:fin])
            if isinstance(valeur, str) and is_cosmetic_change(_valeur_brute(ancien, cle), valeur):
                # Retouche purement typographique : jetée. La réécrire
                # polluerait le diff sans rien changer au fond.
                cosmetiques += 1
                continue
            editions.append(
                _Edition(
                    debut,
                    fin,
                    emit_field(cle, valeur, _indent_de(lignes[ligne_cle])),
                    f"{chg.id}.{cle}",
                )
            )
    return editions, erreurs, cosmetiques


def _point_insertion(lignes: list[str], debut: int, fin: int, cle: str) -> int:
    """Ligne où insérer un champ absent d'un item de condition.

    Juste avant le premier champ qui le suit dans l'ordre canonique, et à défaut
    en fin d'item. Un champ inconnu de l'ordre va en fin d'item — le
    comportement historique, conservé pour ne rien changer aux appelants.
    """
    if cle not in ORDRE_CHAMPS_CONDITION:
        return fin
    rang = ORDRE_CHAMPS_CONDITION.index(cle)
    point = fin
    for suivant in ORDRE_CHAMPS_CONDITION[rang + 1 :]:
        ligne = _localiser_dans(lignes, debut, fin, suivant)
        if ligne is not None:
            point = min(point, _span_champ(lignes, ligne)[0])
    return point


def _valeur_brute(bloc: str, cle: str) -> str:
    """Valeur d'un champ telle que YAML la lit, pour comparaison et réécriture.

    Lue par le parseur et non découpée à la main : depuis que les fiches sont
    sérialisées par `yaml.safe_dump`, des milliers de `text`/`notes` sont entre
    guillemets simples, apostrophes doublées (`d''administration`). Le texte
    brut, guillemets compris, faisait réécrire une note avec ses artefacts et
    jeter toute la réponse à la différence profonde (344 aides sur 584), et
    prenait une apostrophe retouchée pour un vrai changement.
    """
    try:
        valeur = charger_yaml(textwrap.dedent(bloc))
    except yaml.YAMLError:
        valeur = None
    if isinstance(valeur, dict) and cle in valeur and valeur[cle] is not None:
        return str(valeur[cle])
    lignes = bloc.split("\n")
    tete = lignes[0].split(":", 1)[1].strip() if ":" in lignes[0] else ""
    if tete in (">-", "|-", ">", "|", ">+", "|+"):
        return " ".join(ligne.strip() for ligne in lignes[1:])
    return " ".join([tete, *(ligne.strip() for ligne in lignes[1:])]).strip()


def _localiser_dans(lignes: list[str], debut: int, fin: int, cle: str) -> int | None:
    indent_item = _indent_de(lignes[debut]) + 2
    motif = re.compile(rf"^\s{{{indent_item}}}{re.escape(cle)}:")
    return next((i for i in range(debut, fin) if motif.match(lignes[i])), None)


def _edition_note(
    lignes: list[str], debut: int, fin: int, cond_id: str, note: str
) -> tuple[_Edition | None, str | None]:
    ligne_notes = _localiser_dans(lignes, debut, fin, "notes")
    indent = _indent_de(lignes[debut]) + 2
    if ligne_notes is None:
        return _Edition(fin, fin, emit_field("notes", note, indent), f"{cond_id}.notes"), None
    d, f = _span_champ(lignes, ligne_notes)
    existant = _valeur_brute("\n".join(lignes[d:f]), "notes")
    if note in existant:
        return None, None
    return _Edition(
        d, f, emit_field("notes", f"{existant} — {note}", indent), f"{cond_id}.notes"
    ), None


def _edition_ajout(
    lignes: list[str],
    chg: ChangementCondition,
    aujourd_hui: str,
    origine: str = ORIGINE_DEFAUT,
) -> _Edition:
    """Insère une condition, dans le style de liste local au fichier."""
    assert chg.condition is not None
    debut_conditions = _localiser(lignes, ["conditions"])
    assert debut_conditions is not None
    _, fin_bloc = _span_champ(lignes, debut_conditions)

    indent_item = 2
    for i in range(debut_conditions + 1, fin_bloc):
        if m := re.match(r"^(\s*)-\s+id:", lignes[i]):
            indent_item = len(m.group(1))
            break

    item: dict[str, Any] = {
        "id": chg.condition.id,
        "text": chg.condition.text,
        "kind": chg.condition.kind,
    }
    if chg.condition.kind == "info":
        item["effect"] = "info"
    item["quote"] = chg.condition.quote
    # Trace explicite : une condition ajoutée automatiquement n'est pas typée,
    # et le workflow /typer-aides doit pouvoir la retrouver.
    ajout = note_ajout(origine, aujourd_hui)
    item["notes"] = f"{chg.condition.notes} — {ajout}" if chg.condition.notes else ajout

    rendu = emit_item(item, indent_item)

    point = fin_bloc
    if chg.apres_id and (span := _localiser_condition(lignes, chg.apres_id)):
        point = span[1]
    # Une ligne vide entre items si le fichier en met entre les siens.
    if point > 0 and point < len(lignes) and not lignes[point - 1].strip():
        rendu = [*rendu, ""]
    elif _items_espaces(lignes, debut_conditions, fin_bloc):
        rendu = ["", *rendu]
    return _Edition(point, point, rendu, f"{chg.id} (nouvelle condition)")


def _items_espaces(lignes: list[str], debut: int, fin: int) -> bool:
    """Le fichier sépare-t-il ses conditions par une ligne vide ?"""
    vues = 0
    for i in range(debut + 1, fin):
        if re.match(r"^\s*-\s+id:", lignes[i]):
            vues += 1
            if vues > 1:
                return not lignes[i - 1].strip()
    return False


def appliquer_editions(texte: str, editions: list[_Edition]) -> str:
    """Applique les substitutions de la fin vers le début.

    L'ordre inverse est ce qui rend l'opération sûre sans recalculer d'offsets :
    une édition tardive ne décale jamais les lignes d'une édition plus haute.

    Le rang dans la clé de tri traite le cas de DEUX insertions au même point :
    à position égale, l'application inverse remettrait la seconde avant la
    première. Le modèle qui ajoute deux conditions d'un coup les verrait
    permutées — détecté par l'assertion de différence profonde lors du premier
    benchmark réel, sur une réponse en proposant deux.
    """
    lignes = texte.split("\n")
    ordonnees = sorted(
        enumerate(editions),
        key=lambda t: (t[1].debut, t[1].fin, t[1].nouvelle_section, t[0]),
        reverse=True,
    )
    for _rang, edition in ordonnees:
        lignes[edition.debut : edition.fin] = edition.remplacement
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Étape 6 : assertion de différence profonde
# ---------------------------------------------------------------------------


def attendu_apres(
    ancien: dict, out: VeilleLLMOutput, aujourd_hui: str, origine: str = ORIGINE_DEFAUT
) -> dict:
    """Ce que le dictionnaire DOIT devenir, calculé indépendamment de l'éditeur.

    Volontairement écrit sans regarder le texte : c'est le témoin. Si le
    fichier réécrit ne se recharge pas exactement sur ce dictionnaire, le
    splice a fait autre chose que ce qui était demandé — on annule tout.
    """
    attendu = json.loads(json.dumps(ancien, default=str))
    for nom, section in (
        ("calendrier", out.calendrier),
        ("financement", out.financement),
        ("cumul", out.cumul),
    ):
        if section is not None:
            attendu.setdefault(nom, {}).update(section.champs)

    # Pas de `setdefault` : une fiche sans `conditions:` doit le rester quand
    # la réponse ne touche qu'à une section.
    conditions = attendu.setdefault("conditions", []) if out.conditions else []
    par_id = {c["id"]: c for c in conditions}
    for chg in out.conditions:
        if chg.op == "update" and chg.champs:
            cible = par_id.get(chg.id)
            if cible is None:
                continue
            for cle, valeur in chg.champs.items():
                if isinstance(valeur, str) and is_cosmetic_change(cible.get(cle), valeur):
                    continue  # jetée par l'éditeur : le témoin doit faire pareil
                cible[cle] = valeur
        elif chg.op == "signaler_disparue":
            cible = par_id.get(chg.id)
            if cible is None:
                continue
            note = f"non retrouvée dans la source du {aujourd_hui} : à confirmer ou supprimer"
            ancienne = cible.get("notes")
            if ancienne and note in ancienne:
                continue
            cible["notes"] = f"{ancienne} — {note}" if ancienne else note
        elif chg.op == "add" and chg.condition is not None:
            item: dict[str, Any] = {
                "id": chg.condition.id,
                "text": chg.condition.text,
                "kind": chg.condition.kind,
            }
            if chg.condition.kind == "info":
                item["effect"] = "info"
            item["quote"] = chg.condition.quote
            ajout = note_ajout(origine, aujourd_hui)
            item["notes"] = f"{chg.condition.notes} — {ajout}" if chg.condition.notes else ajout
            index = len(conditions)
            if chg.apres_id:
                index = next(
                    (i + 1 for i, c in enumerate(conditions) if c["id"] == chg.apres_id),
                    len(conditions),
                )
            conditions.insert(index, item)
    return attendu


def _normaliser(valeur: Any) -> Any:
    """Aplatit dates et nombres pour comparer deux chargements YAML."""
    if isinstance(valeur, dict):
        return {k: _normaliser(v) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [_normaliser(v) for v in valeur]
    if isinstance(valeur, bool) or valeur is None:
        return valeur
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return str(valeur)


def deep_diff(attendu: dict, obtenu: dict) -> list[str]:
    """Chemins où les deux dictionnaires divergent. Vide = splice conforme."""
    ecarts: list[str] = []

    def marcher(a: Any, b: Any, chemin: str) -> None:
        if len(ecarts) > 10:
            return
        a, b = _normaliser(a), _normaliser(b)
        if isinstance(a, dict) and isinstance(b, dict):
            for cle in sorted(set(a) | set(b)):
                if cle not in a:
                    ecarts.append(f"{chemin}.{cle} : ajouté sans être demandé")
                elif cle not in b:
                    ecarts.append(f"{chemin}.{cle} : disparu")
                else:
                    marcher(a[cle], b[cle], f"{chemin}.{cle}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                ecarts.append(f"{chemin} : {len(a)} élément(s) attendu(s), {len(b)} obtenu(s)")
                return
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                marcher(x, y, f"{chemin}[{i}]")
        elif a != b:
            ecarts.append(f"{chemin} : attendu {a!r}, obtenu {b!r}")

    marcher(attendu, obtenu, "")
    return ecarts


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def appliquer(
    texte_modele: str,
    aide: Aide,
    chemin: Path,
    documents: list[tuple[str, str, str]],
    *,
    aujourd_hui: str,
    diff: str = "",
    origine: str = ORIGINE_DEFAUT,
    champs_condition: frozenset[str] = CHAMPS_CONDITION,
    facts_extra: dict[str, Any] | None = None,
    escalader_structure: bool = False,
    lint_complet: bool = False,
) -> ApplyResult:
    """Chaîne complète. Ne touche au disque que si TOUT passe.

    Retourne un `ApplyResult` dont `texte` porte le nouveau contenu du fichier ;
    l'écriture reste à l'appelant, ce qui rend `--dry-run` gratuit.

    `escalader_structure` (la veille) : une condition ajoutée ou disparue n'est
    pas écrite, elle arrête la chaîne à l'étape `structure`. Les critères de la
    source ont changé, et c'est une ré-ingestion qui les type et les vérifie ;
    une condition ajoutée en `untyped` retirait l'aide entière du moteur.
    L'audit garde l'ajout, qu'il fait suivre de son propre typage.

    `lint_complet` (la veille) : la fiche obtenue doit passer le lint d'écriture
    sans erreur NOUVELLE, pas seulement le schéma.
    """
    res = ApplyResult(slug=aide.slug)

    out, erreurs, etape = parse_output(texte_modele, aide.slug)
    if out is None:
        res.erreurs, res.etape = erreurs, etape
        return res
    res.output = out

    if out.changement_majeur:
        res.etape = "majeur"
        res.erreurs = [
            "changement majeur auto-déclaré : "
            + (out.raison_changement_majeur or "sans raison fournie")
        ]
        return res

    if erreurs := check_referentiel(out, aide, champs_condition, facts_extra):
        res.erreurs, res.etape = erreurs, "referentiel"
        return res
    if erreurs := check_quotes(out, documents):
        res.erreurs, res.etape = erreurs, "quote"
        return res
    # `diff` vide = appelant qui ne le fournit pas (benchmark en mode brut) :
    # on ne peut pas ancrer, et refuser par défaut casserait ces appelants.
    if diff and (erreurs := check_ancrage(out, diff)):
        res.erreurs, res.etape = erreurs, "ancrage"
        return res

    if escalader_structure and (structurels := _changements_structurels(out)):
        res.erreurs, res.etape = structurels, "structure"
        return res

    ancien_texte = chemin.read_text(encoding="utf-8")
    if out.est_vide:
        # Rien à faire, et surtout : ne pas réécrire le fichier.
        res.ok, res.texte = True, ancien_texte
        return res

    lignes = ancien_texte.split("\n")
    editions: list[_Edition] = []
    erreurs = []
    # Dans l'ordre des sections du fichier : deux sections créées au même point
    # s'y rangent dans cet ordre.
    for nom, section in (
        ("financement", out.financement),
        ("cumul", out.cumul),
        ("calendrier", out.calendrier),
    ):
        if section is not None:
            eds, errs = _editions_section(lignes, nom, section.champs)
            editions.extend(eds)
            erreurs.extend(errs)
    eds, errs, cosmetiques = _editions_conditions(lignes, out.conditions, aujourd_hui, origine)
    editions.extend(eds)
    erreurs.extend(errs)
    res.cosmetiques = cosmetiques
    if erreurs:
        res.erreurs, res.etape = erreurs, "edition"
        return res

    if not editions:
        res.ok, res.texte = True, ancien_texte
        return res

    if chevauchement := _chevauchements(editions):
        res.erreurs, res.etape = [chevauchement], "edition"
        return res

    nouveau = appliquer_editions(ancien_texte, editions)

    # Étape 6 : le filet. Un splice qui produit autre chose que le dictionnaire
    # attendu est annulé — mieux vaut une escalade qu'un YAML abîmé.
    try:
        obtenu = charger_yaml(nouveau)
    except yaml.YAMLError as exc:
        res.erreurs, res.etape = [f"YAML invalide après édition : {exc}"], "edition"
        return res
    ancien_dict = charger_yaml(ancien_texte)
    if ecarts := deep_diff(attendu_apres(ancien_dict, out, aujourd_hui, origine), obtenu):
        res.erreurs, res.etape = ecarts, "deep_diff"
        return res

    try:
        nouvelle_aide = Aide.model_validate(obtenu)
    except ValidationError as exc:
        res.erreurs, res.etape = (
            [f"{'.'.join(str(p) for p in e['loc'])} : {e['msg']}" for e in exc.errors()[:8]],
            "lint",
        )
        return res

    if lint_complet and (nouvelles := _erreurs_lint_nouvelles(aide, nouvelle_aide)):
        res.erreurs, res.etape = nouvelles, "coherence"
        return res

    res.ok = True
    res.texte = nouveau
    res.champs_touches = [e.etiquette for e in editions]
    return res


def _changements_structurels(out: VeilleLLMOutput) -> list[str]:
    """Conditions apparues ou disparues dans la réponse, en clair pour le rapport."""
    ajouts = [c.id for c in out.conditions if c.op == "add"]
    disparues = [c.id for c in out.conditions if c.op == "signaler_disparue"]
    motifs = []
    if ajouts:
        motifs.append(
            f"{len(ajouts)} condition(s) nouvelle(s) dans la source : {', '.join(ajouts)}"
        )
    if disparues:
        motifs.append(
            f"{len(disparues)} condition(s) disparue(s) de la source : {', '.join(disparues)}"
        )
    return motifs


def _erreurs_lint_nouvelles(avant: Aide, apres: Aide) -> list[str]:
    """Erreurs du lint d'écriture que la retouche a fait apparaître.

    Un écart, pas un absolu : une fiche du stock peut porter une dette que le
    lint global tolère, et la veille n'a pas à la solder pour retoucher un taux.
    """
    facts = {**load_facts(), **load_pending_facts()}

    def erreurs(a: Aide) -> set[str]:
        return {*check_aide(a, facts), *check_hors_gate(a, facts), *check_ecriture(a, facts)}

    return sorted(erreurs(apres) - erreurs(avant))


def _chevauchements(editions: list[_Edition]) -> str | None:
    """Deux éditions sur la même plage se corrompraient mutuellement."""
    triees = sorted(editions, key=lambda e: (e.debut, e.fin))
    for a, b in zip(triees, triees[1:], strict=False):
        if a.fin > b.debut and a.debut != a.fin and b.debut != b.fin:
            return f"éditions en conflit sur « {a.etiquette} » et « {b.etiquette} »"
    return None

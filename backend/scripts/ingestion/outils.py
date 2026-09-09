"""Les outils de l'agent d'ingestion — treize, tous bornés au slug en cours.

Pas de bash, pas de lecture de fichier arbitraire, pas d'écriture hors des
quatre chemins de l'atelier. Ce n'est pas de la méfiance envers le modèle :
c'est ce qui rend le pipeline exécutable sans surveillance, et ce qui fait
qu'un run raté ne peut abîmer que son propre slug.

**Les docstrings de ce module sont du prompt.** C'est ce que le modèle lit pour
décider quel outil appeler et avec quoi ; providall en dérive le schéma depuis
la signature. Une docstring vague ici coûte des tours et des dollars, pas une
note de lisibilité.

Deux outils portent l'essentiel de la qualité :
  - `ecrire_aide` valide le YAML ET audite les citations dans la foulée. Le
    modèle apprend qu'une quote est fausse au moment où il l'écrit, pas trois
    tours plus tard au lint — et l'audit lui rend la ligne du snapshot la plus
    proche, ce qui transforme « c'est faux » en « voilà le vrai texte ».
  - `explorer_url` est explicitement NON CITABLE : sa sortie n'est pas
    archivée, donc rien de ce qu'elle montre ne peut fonder une quote.
"""

# Pas de `from __future__ import annotations` ici, volontairement : providall
# dérive le schéma d'un outil en reconstruisant un modèle Pydantic depuis la
# SIGNATURE de la fonction, et des annotations différées ne se résolvent pas
# dans son espace de noms — `Annotated[str, Field(description=…)]` y arriverait
# sous forme de chaîne, et la description que lit le modèle serait perdue.

import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from lint_aides_data import lint as lancer_lint
from pipeline.llm import Compteur
from pipeline.verrou import ecrire_atomique
from pipeline.web import Fetcheur
from snapshot_source import write_docx_snapshot, write_md_snapshot, write_pdf_snapshot
from veille_collect import load_baselines, pdf_bytes_to_text, pdf_lisible, pdf_to_text
from veille_text import (
    find_quote_in_any,
    normalize,
    normalize_line,
    normalize_with_offsets,
    parse_front_matter,
)

from aides_schema import Aide, FactDef, load_aide

from . import faits as faits_mod
from .atelier import Atelier
from .boucle import Journal, JournalMuet
from .verification import RapportVerification, verifier

MAX_CAR_EXPLORATION = 20_000
MAX_LIGNES_LECTURE = 600
LIGNES_PAR_DEFAUT = 400
MIN_CAR_REVIEW = 800
# En dessous, une page HTML n'a pas de substance : c'est une SPA dont le corps
# est monté en JavaScript (mesuré sur aides.hautsdefrance.fr / plateforme Galis).
SEUIL_SPA = 500


@dataclass
class EtatOutils:
    """Ce que les outils ont produit — lu par la boucle et par les post-contrôles."""

    review_ecrite: bool = False
    aide_ecrite: bool = False
    dernier_lint_ok: bool = False
    verification: RapportVerification | None = None
    # Vrai dès que le YAML change après une vérification : le rapport en main
    # ne décrit alors plus le fichier sur le disque. Mesuré le 2026-09-07 sur
    # trois aides Grand Est — les fiches annonçaient « tous traités » quand
    # `ds-pro` relevait encore 9 bloquants sur les fichiers finaux.
    modifiee_depuis_verification: bool = False
    faits_proposes: list[str] = field(default_factory=list)
    appels: Counter[str] = field(default_factory=Counter)


# ---------------------------------------------------------------------------
# Aides internes
# ---------------------------------------------------------------------------


def _texte_snapshot(chemin: Path) -> str:
    """Contenu lisible d'un snapshot : markdown sans en-tête, ou texte du PDF."""
    if chemin.suffix.lower() == ".pdf":
        texte = pdf_to_text(chemin)
        if texte is None:
            raise ValueError(
                f"{chemin.name} : `pdftotext` indisponible ou en échec — "
                "ce PDF n'est pas lisible, cherche la même information sur la page HTML."
            )
        if not pdf_lisible(texte):
            raise ValueError(
                f"{chemin.name} : PDF scanné ({len(texte.strip())} caractères extraits) — "
                "son texte n'est pas exploitable, ne cite rien depuis lui."
            )
        return texte
    _meta, corps = parse_front_matter(chemin.read_text(encoding="utf-8", errors="replace"))
    return corps


def _provenance(chemin: Path) -> str:
    if chemin.suffix.lower() == ".pdf":
        sidecar = chemin.with_name(chemin.name + ".meta.yaml")
        if sidecar.is_file():
            meta = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
            return str(meta.get("url", "")) or "(provenance inconnue)"
        return "(provenance inconnue)"
    meta, _ = parse_front_matter(chemin.read_text(encoding="utf-8", errors="replace"))
    return meta.get("url", "(provenance inconnue)")


def _numeroter(lignes: list[str], depart: int) -> str:
    return "\n".join(f"{depart + i:>4}| {ligne}" for i, ligne in enumerate(lignes))


# Longueur minimale d'ancrage : en dessous, une « ressemblance » ne prouve rien
# et un extrait pris au hasard induirait le modèle en erreur.
ANCRE_MIN_CAR = 20
ANCRE_MIN_RATIO = 0.25
# Ce qu'on montre APRÈS le point de divergence, pour que le modèle voie la
# vraie fin de la phrase et pas seulement son début commun.
MARGE_EXTRAIT = 60


def _longueur_prefixe_present(aiguille: str, botte: str) -> int:
    """Longueur du plus long préfixe d'`aiguille` présent dans `botte`, par dichotomie.

    C'est le point exact où la citation cesse de correspondre à la source : à
    gauche le texte est commun, à droite il diverge. Dichotomie parce que la
    propriété est monotone (si un préfixe est présent, tous les plus courts le
    sont) et qu'un document de règlement fait couramment 60 000 caractères.
    """
    if not aiguille or aiguille[0] not in botte:
        return 0
    bas, haut = 1, len(aiguille)
    while bas < haut:
        milieu = (bas + haut + 1) // 2
        if aiguille[:milieu] in botte:
            bas = milieu
        else:
            haut = milieu - 1
    return bas


def passage_le_plus_proche(
    quote: str, documents: list[tuple[str, str, str]], *, marge: int = MARGE_EXTRAIT
) -> str | None:
    """Le passage de snapshot d'où la citation a dérivé, ou None si rien n'y ressemble.

    Sans lui, « quote introuvable » n'apprend rien au modèle : il ne sait pas
    s'il a inventé la phrase, changé un chiffre ou perdu une apostrophe. Avec
    lui, il voit le vrai texte et corrige en un tour.

    On ne compare pas ligne à ligne : `html2text` rend un paragraphe entier sur
    UNE ligne (`body_width=0`), et un score de similarité global y serait dilué
    par tout ce qui entoure la citation. On cherche donc le plus long PRÉFIXE
    de la quote encore présent dans le document, et on restitue le texte réel à
    partir de là — la table d'offsets de `normalize_with_offsets` ramenant la
    position normalisée vers le texte brut, accents et casse d'origine compris.
    """
    cible = normalize(quote)
    if len(cible) < ANCRE_MIN_CAR:
        return None
    seuil = max(ANCRE_MIN_CAR, int(ANCRE_MIN_RATIO * len(cible)))
    meilleur_ancrage, extrait = 0, ""
    for _nom, contenu, _kind in documents:
        hay_norm, offsets = normalize_with_offsets(contenu)
        ancrage = _longueur_prefixe_present(cible, hay_norm)
        if ancrage < seuil or ancrage <= meilleur_ancrage:
            continue
        depart = hay_norm.find(cible[:ancrage])
        fin = min(len(hay_norm), depart + len(cible) + marge)
        meilleur_ancrage = ancrage
        extrait = " ".join(contenu[offsets[depart] : offsets[fin - 1] + 1].split())
    return extrait or None


def _entete_review_defaut(atelier: Atelier) -> str:
    return (
        f"<!-- Fiche générée par scripts/ingerer.py pour {atelier.slug} "
        f"le {atelier.jour.isoformat()}. À relire avant commit. -->\n"
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def outils_pour(
    atelier: Atelier,
    *,
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    fetcheur: Fetcheur,
    client_verif: providall.Client | None = None,
    journal: Journal | None = None,
    compteur: Compteur | None = None,
    entete_review: Callable[[], str] | None = None,
) -> tuple[list[providall.Tool], EtatOutils]:
    """Les treize outils, fermés sur cet atelier. Renvoie aussi leur état partagé."""
    etat = EtatOutils()
    journal = journal or JournalMuet()

    def compter(nom: str) -> None:
        etat.appels[nom] += 1

    # ----------------------------------------------------------- exploration

    def explorer_url(
        url: Annotated[str, Field(description="URL complète, http(s)")],
    ) -> str:
        """Ouvre une page pour la REPÉRER, sans l'archiver. Sa sortie n'est JAMAIS citable.

        Sert à vérifier qu'une URL existe, à suivre un lien vers un règlement, à
        voir de quoi parle une page avant de décider de la snapshoter. Le texte
        rendu est tronqué et n'est enregistré nulle part : toute `quote` prise
        ici sera déclarée introuvable par le lint. Pour citer, il faut
        `snapshotter` puis `lire_snapshot`.
        """
        compter("explorer_url")
        page = fetcheur.get(url)
        if not page.ok:
            return f"ERREUR : {url} → {page.erreur or f'HTTP {page.status}'}"
        if page.est_pdf:
            return (
                f"{url} est un PDF ({len(page.contenu)} octets). `explorer_url` ne le lit pas : "
                "utilise `snapshotter` pour l'archiver, puis `lire_snapshot`."
            )
        md = page.markdown()
        if len(md.strip()) < SEUIL_SPA:
            return (
                f"{page.url_finale} répond {page.status} mais ne rend que "
                f"{len(md.strip())} caractères : c'est une page dont le contenu est monté "
                "en JavaScript (SPA). Cherche la source citable ailleurs (règlement PDF, "
                "page statique) et signale-le dans la review."
            )
        entete = f"[NON CITABLE — repérage seulement] {page.url_finale}\n\n"
        return entete + md[:MAX_CAR_EXPLORATION]

    # ------------------------------------------------------------- snapshots

    def snapshotter(
        url: Annotated[str, Field(description="URL de la page ou du PDF à archiver")],
        label: Annotated[
            str,
            Field(
                description="Étiquette courte en minuscules (reglement, faq, formulaire…), "
                "obligatoire si plusieurs sources sont archivées le même jour"
            ),
        ] = "",
    ) -> str:
        """Télécharge une source et l'archive dans le dossier de l'aide.

        C'est l'ARCHIVE qui fait foi : toute citation doit s'y retrouver mot pour
        mot. Une page HTML est convertie en markdown, un PDF est copié tel quel,
        un .docx est converti en texte (les règlements d'intervention régionaux
        sont souvent des .docx : archive-les, ils portent les critères fins).
        Archiver deux fois la même page le même jour ne crée pas de doublon.
        Après l'appel, lis le snapshot avec `lire_snapshot` — jamais la page live.
        """
        compter("snapshotter")
        page = fetcheur.get(url)
        if not page.ok:
            return f"ERREUR : impossible d'archiver {url} → {page.erreur or f'HTTP {page.status}'}"
        etiquette = (label or "").strip().lower() or None
        try:
            if page.est_pdf:
                chemin = write_pdf_snapshot(
                    atelier.slug,
                    page.contenu,
                    url=page.url_finale,
                    label=etiquette,
                    jour=atelier.jour,
                )
                texte = pdf_bytes_to_text(page.contenu)
                if not pdf_lisible(texte):
                    return (
                        f"Archivé : {atelier.relatif(chemin)} — mais ATTENTION, ce PDF ne "
                        f"s'extrait pas ({len((texte or '').strip())} caractères) : c'est un "
                        "scan. Tu ne pourras rien en citer ; cherche la même information sur "
                        "une page HTML et signale-le dans la review."
                    )
                lignes = len(texte.splitlines()) if texte else 0
                return (
                    f"Archivé : {atelier.relatif(chemin)} (PDF, {lignes} lignes de texte). "
                    f"Lis-le avec `lire_snapshot('{chemin.name}')`."
                )
            if page.est_docx:
                # Les règlements d'intervention régionaux sont souvent en .docx,
                # et c'est là que vivent les critères fins : sans conversion,
                # l'archive était le ZIP brut et rien n'en était citable.
                chemin, texte = write_docx_snapshot(
                    atelier.slug,
                    page.contenu,
                    url=page.url_finale,
                    label=etiquette,
                    jour=atelier.jour,
                )
                if not texte.strip():
                    return (
                        f"Archivé : {atelier.relatif(chemin)} — mais ce .docx ne "
                        "s'extrait pas (document vide ou protégé). Tu ne pourras rien "
                        "en citer ; cherche la même information ailleurs et "
                        "signale-le dans la review."
                    )
                return (
                    f"Archivé : {atelier.relatif(chemin)} (.docx converti, "
                    f"{len(texte.splitlines())} lignes). "
                    f"Lis-le avec `lire_snapshot('{chemin.name}')`."
                )
            chemin = write_md_snapshot(
                atelier.slug, page.url_finale, page.texte, label=etiquette, jour=atelier.jour
            )
        except SystemExit as exc:  # `snapshot_source` refuse un label invalide ainsi
            return f"ERREUR : {exc}"
        corps = _texte_snapshot(chemin)
        if len(corps.strip()) < SEUIL_SPA:
            return (
                f"Archivé : {atelier.relatif(chemin)} — mais la page ne contient que "
                f"{len(corps.strip())} caractères (SPA ou page vide). Cherche la source "
                "citable ailleurs et signale-le dans la review."
            )
        return (
            f"Archivé : {atelier.relatif(chemin)} ({len(corps.splitlines())} lignes). "
            f"Lis-le avec `lire_snapshot('{chemin.name}')`."
        )

    def lister_snapshots() -> str:
        """Les sources déjà archivées pour cette aide : nom, type, URL d'origine, taille."""
        compter("lister_snapshots")
        chemins = atelier.snapshots()
        if not chemins:
            return "Aucun snapshot pour cette aide. Commence par `snapshotter` sa source."
        lignes = [f"{len(chemins)} snapshot(s) dans {atelier.relatif(atelier.dossier_sources)} :"]
        for chemin in chemins:
            taille = chemin.stat().st_size
            lignes.append(
                f"  {chemin.name}  ({chemin.suffix.lstrip('.')}, {taille // 1024} Ko)  "
                f"← {_provenance(chemin)}"
            )
        return "\n".join(lignes)

    def lire_snapshot(
        chemin: Annotated[str, Field(description="Nom du fichier de snapshot (ex. 2026-09-06.md)")],
        offset: Annotated[int, Field(description="Première ligne à lire (0 = début)")] = 0,
        limit: Annotated[int, Field(description=f"Nombre de lignes, max {MAX_LIGNES_LECTURE}")] = (
            LIGNES_PAR_DEFAUT
        ),
    ) -> str:
        """Lit une tranche d'un snapshot archivé, lignes numérotées.

        C'est LA source des citations : une `quote` doit être copiée depuis ce
        que cet outil affiche, caractère pour caractère (les numéros de ligne et
        la barre verticale ne font pas partie du texte). L'en-tête de
        métadonnées d'un `.md` est retiré automatiquement. Un PDF est converti
        en texte. Lis par tranches utiles plutôt que le document entier.
        """
        compter("lire_snapshot")
        try:
            fichier = atelier.resoudre_snapshot(chemin)
            texte = _texte_snapshot(fichier)
        except (ValueError, FileNotFoundError) as exc:
            return f"ERREUR : {exc}"
        lignes = texte.splitlines()
        depart = max(0, offset)
        combien = max(1, min(limit, MAX_LIGNES_LECTURE))
        tranche = lignes[depart : depart + combien]
        if not tranche:
            return f"{fichier.name} : {len(lignes)} lignes au total, rien à l'offset {depart}."
        reste = len(lignes) - (depart + len(tranche))
        suite = (
            f"\n\n[… {reste} lignes de plus — relire avec offset={depart + len(tranche)}]"
            if reste > 0
            else ""
        )
        return (
            f"{fichier.name} — lignes {depart}-{depart + len(tranche) - 1} sur {len(lignes)}\n\n"
            + _numeroter(tranche, depart)
            + suite
        )

    def chercher_dans_snapshot(
        motif: Annotated[
            str, Field(description="Mots à retrouver (recherche insensible aux accents)")
        ],
        chemin: Annotated[
            str, Field(description="Limiter à un snapshot précis ; vide = tous")
        ] = "",
    ) -> str:
        """Retrouve les lignes d'un snapshot qui contiennent des mots donnés.

        Le moyen le moins cher de localiser un passage dans un règlement de
        400 lignes : cherche « plafond », « bénéficiaires » ou « 80 % », lis le
        numéro de ligne rendu, puis ouvre la tranche avec `lire_snapshot`.
        """
        compter("chercher_dans_snapshot")
        tokens = [t for t in normalize(motif).split() if t]
        if not tokens:
            return "ERREUR : aucun mot-clé fourni."
        try:
            cibles = [atelier.resoudre_snapshot(chemin)] if chemin.strip() else atelier.snapshots()
        except (ValueError, FileNotFoundError) as exc:
            return f"ERREUR : {exc}"
        if not cibles:
            return "Aucun snapshot à fouiller. Commence par `snapshotter`."
        blocs: list[str] = []
        total = 0
        for fichier in cibles:
            try:
                texte = _texte_snapshot(fichier)
            except ValueError:
                continue
            # Numérotation sur `splitlines()` et non sur `normalize_lines()`, qui
            # écarte les lignes vides : les numéros rendus ici doivent être ceux
            # que `lire_snapshot` affichera, sinon l'offset promis est faux.
            trouvees = [
                (i, brute.rstrip())
                for i, brute in enumerate(texte.splitlines())
                if all(t in normalize_line(brute) for t in tokens)
            ]
            total += len(trouvees)
            if trouvees:
                blocs.append(
                    f"{fichier.name} — {len(trouvees)} ligne(s) :\n"
                    + "\n".join(f"{i:>4}| {ligne}" for i, ligne in trouvees[:40])
                    + ("\n  […]" if len(trouvees) > 40 else "")
                )
        if not total:
            return f"Aucune ligne ne contient « {motif} »."
        return "\n\n".join(blocs)

    # ----------------------------------------------------------------- faits

    def chercher_faits(
        mots: Annotated[str, Field(description="Mots-clés, en français (ex. « label jardin »)")],
        scope: Annotated[
            str, Field(description="Filtrer sur monument, projet ou proprietaire ; vide = tous")
        ] = "",
    ) -> str:
        """Cherche un fait existant dans l'ontologie avant d'en proposer un nouveau.

        Un fait réutilisé, c'est une question de moins dans le questionnaire de
        tous les propriétaires. Cherche large : le seuil d'un règlement se porte
        par le prédicat, pas par le fait — « surface_jardin_m2 » sert aussi bien
        à un seuil de 500 m² qu'à un seuil de 2 000 m².
        """
        compter("chercher_faits")
        return faits_mod.rechercher(facts, pending, mots, scope=(scope or None))

    def detail_fait(
        fact_id: Annotated[str, Field(description="Identifiant exact du fait")],
    ) -> str:
        """Définition complète d'un fait : type, scope, question, options, aide, levier."""
        compter("detail_fait")
        return faits_mod.detail(facts, pending, fact_id)

    def proposer_fait(
        fact_id: Annotated[
            str, Field(description="Identifiant en snake_case minuscule, ex. jardin_remarquable")
        ],
        definition_yaml: Annotated[
            str,
            Field(
                description="Définition YAML du fait (type, scope, question, options, help, levier)"
            ),
        ],
        justification: Annotated[
            str,
            Field(
                description="Pourquoi aucun fait existant ne convient : cite ceux que tu as "
                "écartés et ce qui les disqualifie (80 caractères minimum)"
            ),
        ],
    ) -> str:
        """Propose un fait NOUVEAU dans facts_pending.yaml. Dernier recours.

        À n'appeler qu'après avoir cherché et lu les faits proches. Le fait est
        utilisable immédiatement dans une condition `kind: user_fact`, mais
        reste « en attente » : c'est un humain qui l'approuvera en le déplaçant
        vers facts.yaml. Mentionne-le dans la fiche de review.
        """
        compter("proposer_fait")
        message = faits_mod.proposer(atelier, facts, fact_id, definition_yaml, justification)
        if not message.startswith("ERREUR"):
            etat.faits_proposes.append(fact_id)
            pending[fact_id] = FactDef.model_validate(yaml.safe_load(definition_yaml))
            journal.evenement(f"fait proposé : {fact_id}")
        return message

    # ------------------------------------------------------------------ aide

    def ecrire_aide(
        yaml_texte: Annotated[str, Field(description="Contenu COMPLET du fichier YAML de l'aide")],
    ) -> str:
        """Écrit le fichier de l'aide, le valide, et audite tes citations.

        Envoie toujours le fichier ENTIER : chaque appel remplace le précédent.
        Le YAML est validé contre le schéma avant d'être écrit — un fichier
        invalide n'écrase rien, tu reçois l'erreur et tu recommences. En cas de
        succès, l'outil vérifie chaque `quote` contre les snapshots archivés et
        te rend, pour chaque citation introuvable, la ligne du snapshot qui s'en
        approche le plus. Appelle-le autant de fois que nécessaire.
        """
        compter("ecrire_aide")
        try:
            brut = yaml.safe_load(yaml_texte)
        except yaml.YAMLError as exc:
            return f"ERREUR : YAML invalide, rien n'a été écrit — {exc}"
        if not isinstance(brut, dict):
            return "ERREUR : le contenu doit être un objet YAML (slug, nom, organisme…)."
        if brut.get("slug") != atelier.slug:
            return (
                f"ERREUR : le slug du fichier est « {brut.get('slug')} » alors que tu ingères "
                f"« {atelier.slug} ». Corrige le champ `slug` — tu ne peux écrire aucune "
                "autre aide."
            )
        try:
            aide = Aide.model_validate(brut)
        except Exception as exc:
            return f"ERREUR : le fichier ne respecte pas le schéma, rien n'a été écrit — {exc}"

        atelier.yaml_path.parent.mkdir(parents=True, exist_ok=True)
        ecrire_atomique(
            atelier.yaml_path,
            yaml.safe_dump(brut, allow_unicode=True, sort_keys=False, width=100),
        )
        etat.aide_ecrite = True
        etat.modifiee_depuis_verification = etat.verification is not None
        return "\n".join(
            [
                f"Écrit : {atelier.relatif(atelier.yaml_path)} "
                f"({len(aide.conditions)} condition(s)).",
                *_audit_citations(aide),
                *_controle_source(aide),
            ]
        )

    def _audit_citations(aide: Aide) -> list[str]:
        documents, illisibles, _ = load_baselines(atelier.slug)
        citees = [c for c in aide.conditions if c.quote]
        if not citees:
            return ["Aucune citation dans ce fichier — toute condition opposable en attend une."]
        if not documents:
            return [
                "ATTENTION : aucun snapshot exploitable, tes citations ne sont vérifiables "
                "par personne. Snapshote la source avant d'aller plus loin."
            ]
        absentes: list[tuple[str, str]] = []
        degradees = 0
        for cond in citees:
            _nom, match = find_quote_in_any(cond.quote or "", documents)  # type: ignore[arg-type]
            if not match.found:
                absentes.append((cond.id, cond.quote or ""))
            elif match.status != "exacte" or match.reconstitution:
                degradees += 1
        lignes = [
            f"Citations : {len(citees) - len(absentes)}/{len(citees)} retrouvées dans les "
            f"snapshots ({degradees} après normalisation typographique)."
        ]
        if illisibles:
            lignes.append(f"  (PDF non extractibles, hors contrôle : {', '.join(illisibles)})")
        for cond_id, quote in absentes:
            lignes.append(f"  ✗ {cond_id} — INTROUVABLE : « {' '.join(quote.split())[:120]} »")
            proche = passage_le_plus_proche(quote, documents)
            if proche:
                lignes.append(f"      texte le plus proche dans le snapshot : « {proche[:200]} »")
        if absentes:
            lignes.append(
                "  Corrige ces citations en les recopiant depuis `lire_snapshot`, ou retire "
                "la condition si la source ne la porte pas."
            )
        return lignes

    def _controle_source(aide: Aide) -> list[str]:
        lignes: list[str] = []
        if not aide.source.snapshot:
            lignes.append(
                "  ⚠ `source.snapshot` est vide : renseigne le chemin du snapshot principal "
                f"(ex. {atelier.relatif(atelier.dossier_sources)}/<fichier>)."
            )
        else:
            try:
                atelier.resoudre_snapshot(aide.source.snapshot)
            except (ValueError, FileNotFoundError):
                lignes.append(
                    f"  ⚠ `source.snapshot` pointe vers « {aide.source.snapshot} », "
                    "qui n'existe pas. `lister_snapshots` donne les chemins réels."
                )
        if aide.source.verified_at != atelier.jour:
            lignes.append(
                f"  ⚠ `source.verified_at` doit valoir {atelier.jour.isoformat()} "
                f"(date de cette vérification), pas {aide.source.verified_at}."
            )
        return lignes

    def lire_aide() -> str:
        """Relit le fichier YAML tel qu'il est écrit sur le disque."""
        compter("lire_aide")
        if not atelier.yaml_path.exists():
            return "Le fichier n'existe pas encore : c'est une aide nouvelle, à toi de l'écrire."
        return atelier.yaml_path.read_text(encoding="utf-8")

    def lint() -> str:
        """Lance le linter sur cette aide, citations comprises. Il doit sortir vert.

        Contrôle le schéma, l'existence des faits et des champs référencés, la
        compatibilité des opérateurs, le plafond de `manual_check` + `gate`
        (zéro pour une aide nouvelle), et retrouve chaque citation dans les
        snapshots. Corrige tout ce qu'il signale avant de passer à la suite.
        """
        compter("lint")
        if not atelier.yaml_path.exists():
            return "ERREUR : rien à linter, le fichier n'a pas encore été écrit."
        rapport = lancer_lint(
            [atelier.slug],
            quotes=True,
            aides_dir=atelier.aides_dir,
            facts_path=atelier.facts_path,
            pending_path=atelier.pending_path,
        )
        etat.dernier_lint_ok = rapport.ok
        return rapport.texte()

    def verification_adversariale() -> str:
        """Fait relire ton extraction par un second modèle chargé de la RÉFUTER.

        À appeler UNE fois, après un `lint` vert. Le vérificateur n'a pas vu ton
        raisonnement : il ne lit que la source archivée et le fichier produit.
        Corrige les problèmes bloquants puis relance `lint`. Si tu es en
        désaccord, garde ta version, re-cite la source, et consigne l'arbitrage
        dans la fiche de review.
        """
        compter("verification_adversariale")
        if client_verif is None:
            return "Vérification indisponible dans ce run (aucun modèle de vérification)."
        if not atelier.yaml_path.exists():
            return "ERREUR : écris d'abord le fichier avec `ecrire_aide`."
        try:
            aide = load_aide(atelier.yaml_path)
        except Exception as exc:
            return f"ERREUR : le fichier écrit n'est pas chargeable — {exc}"
        rapport, rendu = verifier(atelier, client_verif, aide=aide, compteur=compteur)
        etat.verification = rapport
        etat.modifiee_depuis_verification = False
        journal.evenement(
            f"vérification : {len(rapport.problemes)} problème(s), "
            f"{len(rapport.bloquants)} bloquant(s)"
        )
        return rendu

    def ecrire_review(
        markdown: Annotated[
            str, Field(description="Fiche de review complète, en markdown, sections `## `")
        ],
    ) -> str:
        """Écrit la fiche de review humaine. C'est la DERNIÈRE étape.

        Suis le format de l'étape 5 du skill : tableau des conditions, diff avec
        la version précédente, faits ou chemins nouveaux proposés, points
        d'arbitrage, résultat de la vérification adversariale. C'est ce
        document que l'humain lira pour décider de committer ou non — dis-y ce
        dont tu n'es pas sûr. Après cet appel, réponds sans appeler d'outil.
        """
        compter("ecrire_review")
        texte = markdown.strip()
        if len(texte) < MIN_CAR_REVIEW:
            return (
                f"ERREUR : fiche trop courte ({len(texte)} caractères, {MIN_CAR_REVIEW} minimum). "
                "Elle doit permettre à un humain de valider sans rouvrir la source : conditions, "
                "arbitrages, ce qui reste incertain."
            )
        if "## " not in texte:
            return (
                "ERREUR : la fiche doit être structurée en sections markdown (`## `) — "
                "cf. le format de l'étape 5 du skill."
            )
        if client_verif is not None and etat.verification is None:
            return (
                "ERREUR : un modèle de vérification est configuré et tu n'as jamais appelé "
                "`verification_adversariale`. L'étape 4 du skill n'est pas facultative : "
                "lance-la sur le fichier écrit, puis réécris la fiche avec son verdict."
            )
        if etat.modifiee_depuis_verification:
            return (
                "ERREUR : tu as modifié l'aide depuis la dernière "
                "`verification_adversariale`. Le rapport que tu as en main ne décrit plus "
                "le fichier sur le disque, et la fiche ne peut donc pas affirmer que les "
                "problèmes sont traités. Relance `verification_adversariale`, puis réécris "
                "la fiche avec son verdict réel."
            )
        entete = entete_review() if entete_review else _entete_review_defaut(atelier)
        atelier.review_path.parent.mkdir(parents=True, exist_ok=True)
        ecrire_atomique(atelier.review_path, entete.rstrip() + "\n\n" + texte + "\n")
        etat.review_ecrite = True
        return (
            f"Fiche écrite : {atelier.relatif(atelier.review_path)}. "
            "L'ingestion est terminée — réponds maintenant sans appeler d'outil."
        )

    outils = [
        providall.tool(f)
        for f in (
            explorer_url,
            snapshotter,
            lister_snapshots,
            lire_snapshot,
            chercher_dans_snapshot,
            chercher_faits,
            detail_fait,
            proposer_fait,
            ecrire_aide,
            lire_aide,
            lint,
            verification_adversariale,
            ecrire_review,
        )
    ]
    return outils, etat


__all__ = [
    "ANCRE_MIN_CAR",
    "LIGNES_PAR_DEFAUT",
    "MAX_CAR_EXPLORATION",
    "MAX_LIGNES_LECTURE",
    "MIN_CAR_REVIEW",
    "SEUIL_SPA",
    "EtatOutils",
    "passage_le_plus_proche",
    "outils_pour",
]

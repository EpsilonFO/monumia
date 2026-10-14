"""
Étage B de la veille : trier les aides d'après ce que l'étage A a rapporté.

Zéro LLM, zéro réseau, zéro écriture — que des décisions déterministes prises
sur des comparaisons de texte. C'est ce qui rend le triage rejouable et
testable : l'étage C (coûteux) ne voit que les aides que CET étage a retenues.

Deux garde-fous décident de la qualité du signal, et ils sont plus importants
que les seuils eux-mêmes :

1. Une quote ne « régresse » que si elle était retrouvée dans la BASELINE et ne
   l'est plus dans le contenu FRAIS. Compter les quotes simplement introuvables
   enverrait 56 aides au modèle dès le premier passage — ce sont 99 quotes de
   dette préexistante (mesurée par `veille_quotes_audit.py`), pas des
   changements de source. Cette dette est rapportée à part, jamais escaladée.

2. Une régression n'est retenue que si le document qui justifiait la quote a
   réellement été re-téléchargé. 802 quotes du dépôt sont justifiées par un PDF
   souvent sans URL connue : sans ce garde-fou, elles paraîtraient toutes avoir
   disparu au premier passage.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import Aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_collect import AideCollect, FetchResult, MonitoredUrl, cle_url
from veille_text import (
    NormalizedDiff,
    QuoteMatch,
    find_quote_in_any,
    is_noise_line,
    normalize_line,
    normalize_lines,
    normalized_diff,
)

Statut = Literal[
    "OK",
    "MAJ_LLM",
    "ESCALADE_INGESTION",
    "ERREUR_HTTP",
    "SANS_BASELINE",
    "DATE_PERIMEE_SOURCE_INCHANGEE",
]

# Ordre d'affichage du récapitulatif : ce qui demande une action d'abord.
STATUTS = (
    "ESCALADE_INGESTION",
    "MAJ_LLM",
    "DATE_PERIMEE_SOURCE_INCHANGEE",
    "ERREUR_HTTP",
    "SANS_BASELINE",
    "OK",
)

# ---------------------------------------------------------------------------
# Seuils de triage — à réajuster après le premier passage réel, d'après les
# faux positifs observés. Ils sont ici, nommés et groupés, pour qu'un
# ajustement soit une modification d'une ligne et non une chasse dans le code.
# ---------------------------------------------------------------------------

# Sous ce volume de texte utile (hors menus et bandeaux), la page rapportée
# n'est pas le règlement : redirection vers un portail, mur anti-bot, page
# vidée. Rien d'exploitable pour une mise à jour chirurgicale.
MIN_CONTENU_UTILE = 500

# Au-delà de cette part de lignes changées, la page a été refondue : la
# retoucher champ par champ n'a plus de sens, il faut la ré-ingérer.
RATIO_DIFF_ESCALADE = 0.50

# Régressions de quotes massives : le règlement a changé de structure.
# La condition est double (part ET nombre absolu) pour qu'une aide à trois
# quotes ne bascule pas sur une seule disparition.
REGRESSIONS_RATIO_ESCALADE = 0.40
REGRESSIONS_MIN_ESCALADE = 3

# Part d'échecs réseau au-delà de laquelle le RUN est présumé en cause, pas les
# sources : une coupure de connexion ferait sinon escalader tout le parc d'un
# coup. Au-dessus, toute panne redevient réessayable.
SEUIL_PANNE_GENERALISEE = 0.30

# Nombre d'URL DISTINCTES sur lesquelles une même ligne doit changer pour être
# tenue pour du gabarit de site. Deux suffisent : une modification de règlement
# est propre à sa page, alors qu'un carrousel bouge sur tout le portail. Voir
# `lignes_de_chrome` pour la mesure qui a fixé ce seuil.
CHROME_MIN_URLS = 2

# Une ligne de RÈGLEMENT n'est jamais du chrome, même partagée : les aides sœurs
# d'un même guide ont des pages distinctes au texte commun, et leur échéance
# change d'un bloc. Mesuré au 2026-10-04 : « déposés… avant le 16 novembre
# 2026 » (deux aides cvl-pact, classées « source inchangée »), la date limite de
# six aides des Vosges, un plafond savoyard, tous effacés. Est réputée de
# règlement une ligne qui porte une date ou un montant ET un mot de règlement ;
# l'un sans l'autre laissait passer « Mis à jour le… », « Corrèze 100% Fibre »
# et les carrousels d'actualités datés. Motifs écrits sur la forme normalisée
# (`normalize_line` : minuscules, sans accents).
_MOIS = r"(janv|fevr|mars|avr|mai|juin|juil|aout|sept|oct|nov|dec)[a-z]*\.?"
_DATE_RE = re.compile(rf"\b\d{{1,2}}(er)?\s+{_MOIS}\s+20\d\d\b|\b\d{{1,2}}/\d{{1,2}}/20\d\d\b")
_MONTANT_RE = re.compile(r"\d[\d .]*\s*(€|euros?\b|%)")
_MOT_REGLEMENT_RE = re.compile(
    r"(depot|deposer|deposes|avant le|date limite|cloture|jusqu|candidature|appel a projet|"
    r"plafond|taux|montant|subvention|eligib|depense|dossier)"
)
_GABARIT_DATE_RE = re.compile(r"(mis a jour|mise a jour|publie le|modifie le|©|\(c\))")


def ligne_de_reglement(norm: str) -> bool:
    """Ligne normalisée qui porte une échéance ou un montant de règlement."""
    return bool(
        (_DATE_RE.search(norm) or _MONTANT_RE.search(norm))
        and _MOT_REGLEMENT_RE.search(norm)
        and not _GABARIT_DATE_RE.search(norm)
    )


# Une page qui répond 200 mais ne rend presque plus rien, alors que sa baseline
# était un vrai règlement, n'a pas été vidée par son financeur : elle est rendue
# en JavaScript, ou un pare-feu applicatif sert une coquille. Mesuré : neuf
# aides Auvergne-Rhône-Alpes renvoient 980 octets de HTML pour zéro caractère
# utile. Ré-ingérer ne servirait à rien — l'agent se heurterait au même mur —,
# c'est un problème de COLLECTE, donc réessayable (voir `--proxy jina`).
RATIO_CONTENU_EFFONDRE = 0.20


@dataclass
class QuoteVerdict:
    """Sort d'une citation entre sa baseline et le contenu fraîchement récupéré."""

    cond_id: str
    quote: str
    baseline: QuoteMatch
    fresh: QuoteMatch
    baseline_doc: str | None = None
    # Le document qui justifiait la quote a-t-il été re-téléchargé ? Sinon on ne
    # peut RIEN conclure de son absence dans le contenu frais.
    recontrolable: bool = False

    @property
    def regression(self) -> bool:
        return self.recontrolable and self.baseline.found and not self.fresh.found

    @property
    def dette(self) -> bool:
        """Introuvable dès la baseline : dette préexistante, pas un changement."""
        return not self.baseline.found


@dataclass
class UrlVerdict:
    murl: MonitoredUrl
    result: FetchResult | None = None
    diff: NormalizedDiff | None = None
    # sha du contenu frais identique à celui de l'en-tête du snapshot.
    sha_identique: bool = False
    # Binaire (PDF scanné, .docx, tableur) dont le sha a changé sans qu'aucun
    # texte ne permette de dire QUOI : c'est un changement avéré, mais
    # inexploitable par l'étage C. Il escalade vers un humain.
    binaire_modifie: bool = False

    @property
    def a_change(self) -> bool:
        if self.sha_identique:
            return False
        if self.binaire_modifie:
            return True
        return self.diff is not None and not self.diff.is_empty


@dataclass
class AideAnalysis:
    slug: str
    statut: Statut = "OK"
    raisons: list[str] = field(default_factory=list)
    urls: list[UrlVerdict] = field(default_factory=list)
    quotes: list[QuoteVerdict] = field(default_factory=list)
    date_limite_perimee: date | None = None
    pdf_illisibles: list[str] = field(default_factory=list)
    contenu_utile: int | None = None
    contenu_utile_baseline: int | None = None
    # Escalade par la seule règle 6 (pourcentage de lignes changées). Refonte du
    # site ou nouveau règlement, le code ne sait pas les distinguer : c'est la
    # seule escalade que la veille soumet à Jev (`veille_arbitre`), entre
    # l'étage B et l'étage C. Page morte, binaire illisible, contenu effondré et
    # régressions massives de citations restent décidés ici.
    refonte: bool = False
    # Refonte que Jev a jugée sans changement de règlement : rétrogradée en
    # MAJ_LLM, jamais classée inchangée. Le filtre de Jev ne s'y applique pas.
    retrogradee: bool = False

    @property
    def regressions(self) -> list[QuoteVerdict]:
        return [q for q in self.quotes if q.regression]

    @property
    def dette_quotes(self) -> list[QuoteVerdict]:
        return [q for q in self.quotes if q.dette]

    @property
    def non_recontrolables(self) -> list[QuoteVerdict]:
        return [q for q in self.quotes if q.baseline.found and not q.recontrolable]

    @property
    def couverture_quotes(self) -> tuple[int, int]:
        """(citations recontrôlées ce run, citations au total).

        Le chiffre qui manquait au RÉCAP. Un `OK` adossé à 0 citation contrôlée
        ne dit RIEN du règlement : il ne prouve que l'immobilité des pages qui
        ont pu être re-téléchargées. Cas typique, et fréquent : toutes les
        conditions sont justifiées par un règlement PDF dépourvu de sidecar de
        provenance, donc hors du périmètre de surveillance, tandis que la page
        d'atterrissage HTML — elle, surveillée — n'a pas bougé.
        """
        return sum(1 for q in self.quotes if q.recontrolable), len(self.quotes)

    @property
    def a_change(self) -> bool:
        return any(u.a_change for u in self.urls)

    @property
    def erreurs(self) -> list[UrlVerdict]:
        return [u for u in self.urls if u.result is not None and not u.result.ok]

    @property
    def liens_morts(self) -> list[UrlVerdict]:
        """Formulaire ou page secondaire qui n'existe plus (404, 410, redirection sans issue).

        Hors de `_decider` : seule la page officielle décide du statut, et un
        formulaire mort ne doit pas empêcher la retouche d'une page qui a
        changé. Sans ce relevé, un règlement PDF passé en 404 laissait l'aide en
        `OK` (ses citations devenaient seulement « non recontrôlables »), et le
        code HTTP de `formulaire_url` n'était lu nulle part.
        """
        return [
            u
            for u in self.urls
            if u.murl.role != "officielle" and u.result is not None and u.result.morte
        ]


def contenu_utile(markdown: str) -> int:
    """Volume de texte hors chrome de page : menus et bandeaux ne comptent pas.

    Sans ce filtre, une page anti-bot pleine de navigation passerait le seuil
    de contenu minimal alors qu'elle ne contient aucun règlement.
    """
    return sum(len(norm) for norm, raw in normalize_lines(markdown) if not is_noise_line(raw))


def _panne_generalisee(collects: dict[str, AideCollect]) -> bool:
    """Le run lui-même est-il en cause plutôt que les sources ?"""
    resultats = [r for col in collects.values() for r in col.fetched.values()]
    if not resultats:
        return False
    pannes = sum(1 for r in resultats if r.error is not None)
    return pannes / len(resultats) > SEUIL_PANNE_GENERALISEE


def _quote_verdicts(
    aide: Aide, collect: AideCollect, urls_rafraichies: set[str]
) -> list[QuoteVerdict]:
    """Compare le sort de chaque quote entre baseline et contenu frais."""
    fresh_docs = collect.fresh_docs()
    if not fresh_docs:
        return []
    # Quel document archivé correspond à quelle URL re-téléchargée : c'est ce
    # qui rend une absence interprétable (garde-fou n°2 du module).
    #
    # La provenance lue dans les snapshots prime sur la correspondance par nom
    # de fichier. `MonitoredUrl.baseline_path` ne désigne que le snapshot le
    # PLUS RÉCENT de chaque URL, alors que `find_quote_in_any` balaye tout le
    # dossier : dès qu'une aide gardait deux snapshots de la même page, la quote
    # était rattachée à l'ancien, absent de cette table, et l'aide sortait en
    # « 0/n citation contrôlée » — un faux négatif, sur la page même qu'on
    # venait de re-télécharger.
    doc_recontrolable = {
        m.baseline_path.name: cle_url(m.url) in urls_rafraichies
        for m in collect.urls
        if m.baseline_path is not None
    }

    def recontrolable(nom: str | None) -> bool:
        if not nom:
            return False
        if url := collect.baseline_urls.get(nom):
            return cle_url(url) in urls_rafraichies
        # Sans provenance — les PDF antérieurs au sidecar — on ne sait pas quelle
        # page ce document archive : le nom de fichier est tout ce qui reste.
        return doc_recontrolable.get(nom, False)

    verdicts = []
    for cond in aide.conditions:
        if not cond.quote:
            continue
        base_doc, base_match = find_quote_in_any(cond.quote, collect.baseline_docs)  # type: ignore[arg-type]
        _, fresh_match = find_quote_in_any(cond.quote, fresh_docs)  # type: ignore[arg-type]
        verdicts.append(
            QuoteVerdict(
                cond_id=cond.id,
                quote=cond.quote,
                baseline=base_match,
                fresh=fresh_match,
                baseline_doc=base_doc,
                recontrolable=recontrolable(base_doc),
            )
        )
    return verdicts


def analyze(
    aide: Aide,
    collect: AideCollect,
    *,
    today: date | None = None,
    panne_generalisee: bool = False,
    chrome: frozenset[str] = frozenset(),
) -> AideAnalysis:
    """Trie une aide. Aucune écriture, aucun appel réseau, aucun LLM."""
    today = today or date.today()
    an = AideAnalysis(slug=aide.slug, pdf_illisibles=list(collect.pdf_illisibles))

    urls_rafraichies: set[str] = set()
    for murl in collect.urls:
        result = collect.fetched.get(murl.url)
        verdict = UrlVerdict(murl=murl, result=result)
        if result and result.ok and murl.role != "formulaire":
            # « Rafraîchie » doit vouloir dire EXACTEMENT « a fourni un document
            # fouillable », au sens de `AideCollect.fresh_docs()` — c'est
            # `FetchResult.texte` qui en décide, pour une page comme pour un
            # PDF. Un .docx ou un scan répond 200 sans rien donner à lire : le
            # compter ferait passer pour disparues toutes les citations qu'il
            # justifiait.
            texte = result.texte
            if texte is not None:
                # Sous les deux formes : la provenance d'un snapshot est l'URL où
                # le téléchargement avait ABOUTI, redirections suivies.
                urls_rafraichies.add(cle_url(murl.url))
                if result.url_finale:
                    urls_rafraichies.add(cle_url(result.url_finale))
            if murl.baseline_sha and result.sha256 == murl.baseline_sha:
                # Chemin rapide : pas un octet de différence, rien à calculer.
                verdict.sha_identique = True
            # Le contenu d'un proxy ne passe pas par la même chaîne de conversion
            # que la baseline : le differ produirait du bruit pur.
            elif texte is not None and murl.baseline_body is not None and not result.via_proxy:
                verdict.diff = normalized_diff(murl.baseline_body, texte, extra_noise=chrome)
            elif (
                murl.baseline_empreinte_texte
                and result.empreinte_texte == murl.baseline_empreinte_texte
            ):
                # PDF trop court pour servir de baseline, mais dont le texte est
                # identique : généré à la volée, ses octets changent à chaque
                # requête (meuse.fr/…/pdf). Rien n'a bougé.
                verdict.sha_identique = True
            elif result.is_binary and murl.baseline_sha:
                # Le sha a bougé et aucun texte comparable n'existe d'un côté ou
                # de l'autre (.docx, PDF scanné, pdftotext absent). Avant ce cas,
                # un règlement PDF remplacé n'était tout simplement pas vu : le
                # sha n'était comparé que pour les pages en markdown.
                verdict.binaire_modifie = True
        an.urls.append(verdict)

    an.quotes = _quote_verdicts(aide, collect, urls_rafraichies)

    if aide.calendrier.date_limite and aide.calendrier.date_limite < today:
        an.date_limite_perimee = aide.calendrier.date_limite

    principale = next((u for u in an.urls if u.murl.role == "officielle"), None)
    if principale and principale.result and principale.result.ok and principale.result.texte:
        an.contenu_utile = contenu_utile(principale.result.texte)
        if principale.murl.baseline_body is not None:
            an.contenu_utile_baseline = contenu_utile(principale.murl.baseline_body)

    _decider(an, principale, panne_generalisee=panne_generalisee)
    return an


def _decider(an: AideAnalysis, principale: UrlVerdict | None, *, panne_generalisee: bool) -> None:
    """Applique les règles de triage, des plus graves aux plus bénignes.

    L'ordre est significatif : une page morte prime sur tout le reste, et une
    erreur transitoire empêche de conclure quoi que ce soit d'autre.
    """
    res = principale.result if principale else None

    # 1. Page principale morte : décision éditoriale du financeur, pas une panne.
    if res is not None and res.morte:
        an.statut = "ESCALADE_INGESTION"
        an.raisons.append(f"page officielle morte (HTTP {res.status})")
        return

    # 2. Panne transitoire : on ne peut RIEN conclure, jamais d'escalade.
    if res is not None and not res.ok:
        an.statut = "ERREUR_HTTP"
        motif = res.error or f"HTTP {res.status}"
        if panne_generalisee and res.error:
            motif += " — panne réseau généralisée sur ce run, source non mise en cause"
        an.raisons.append(f"page officielle injoignable : {motif}")
        return

    # 3. Rien à quoi comparer : ni baseline exploitable, ni URL surveillable.
    if not any(u.murl.has_baseline for u in an.urls):
        an.statut = "SANS_BASELINE"
        if not an.urls:
            an.raisons.append("aucune URL surveillable (source.url_officielle absente)")
        else:
            an.raisons.append("aucun snapshot archivé auquel comparer les pages")
        if an.pdf_illisibles:
            an.raisons.append(f"PDF illisible : {', '.join(an.pdf_illisibles)}")
        return

    # 4. Page servie mais vide de substance. La baseline tranche la cause : si
    # elle avait du contenu, la page n'a pas été vidée, elle n'a pas été RENDUE.
    if an.contenu_utile is not None and an.contenu_utile < MIN_CONTENU_UTILE:
        base = an.contenu_utile_baseline
        if base and an.contenu_utile < RATIO_CONTENU_EFFONDRE * base:
            an.statut = "ERREUR_HTTP"
            an.raisons.append(
                f"page servie mais vide de substance ({an.contenu_utile} caractères utiles "
                f"contre {base} dans la baseline) — rendu JavaScript ou pare-feu applicatif ; "
                "réessayer avec --proxy jina"
            )
        else:
            an.statut = "ESCALADE_INGESTION"
            an.raisons.append(
                f"contenu utile réduit à {an.contenu_utile} caractères "
                f"(seuil {MIN_CONTENU_UTILE}) — page probablement vidée"
            )
        return

    # 5. Document binaire modifié sans texte comparable : le changement est
    # certain, son contenu inconnu. Aucun modèle ne peut retoucher une fiche
    # d'après un fichier qu'il ne lit pas ; un humain doit ouvrir le document.
    if binaires := [u for u in an.urls if u.binaire_modifie]:
        an.statut = "ESCALADE_INGESTION"
        for u in binaires:
            an.raisons.append(
                f"document binaire modifié (sha différent) sans texte comparable : {u.murl.url}"
            )
        return

    # 6. Refonte : la retouche champ par champ n'a plus de sens.
    gros_diff = [u for u in an.urls if u.diff and u.diff.ratio > RATIO_DIFF_ESCALADE]
    if gros_diff:
        an.statut = "ESCALADE_INGESTION"
        an.refonte = True
        for u in gros_diff:
            assert u.diff is not None
            an.raisons.append(f"refonte de {u.murl.url} ({u.diff.ratio:.0%} des lignes changées)")
        return

    # 7. Régressions massives de citations : le règlement a changé de structure.
    controlables = [q for q in an.quotes if q.recontrolable and q.baseline.found]
    regressions = an.regressions
    if (
        len(regressions) >= REGRESSIONS_MIN_ESCALADE
        and controlables
        and len(regressions) / len(controlables) > REGRESSIONS_RATIO_ESCALADE
    ):
        an.statut = "ESCALADE_INGESTION"
        an.raisons.append(
            f"{len(regressions)}/{len(controlables)} citations recontrôlables ont disparu "
            f"de la source (seuil {REGRESSIONS_RATIO_ESCALADE:.0%})"
        )
        return

    # 8. Changement circonscrit : c'est le cas nominal de l'étage C.
    if an.a_change:
        for u in an.urls:
            if u.a_change and u.diff is not None:
                an.raisons.append(
                    f"{u.murl.url} a changé ({u.diff.added} ligne(s) ajoutée(s), "
                    f"{u.diff.removed} retirée(s))"
                )
    if regressions:
        an.raisons.append(
            f"{len(regressions)} citation(s) introuvable(s) dans la source fraîche : "
            + ", ".join(q.cond_id for q in regressions)
        )
    if an.date_limite_perimee and an.a_change:
        an.raisons.append(f"date limite dépassée ({an.date_limite_perimee}) et page modifiée")
    if an.a_change or regressions:
        an.statut = "MAJ_LLM"
        return

    # 9. Échéance passée alors que la source n'a pas bougé : typiquement une
    # annonce sans année (« du 1er septembre au 31 octobre »). Aucun modèle ne
    # peut trancher ça, seul un humain le peut.
    if an.date_limite_perimee:
        an.statut = "DATE_PERIMEE_SOURCE_INCHANGEE"
        an.raisons.append(f"date limite dépassée ({an.date_limite_perimee}) mais source inchangée")
        return

    an.statut = "OK"


def lignes_de_chrome(collects: dict[str, AideCollect]) -> frozenset[str]:
    """Lignes qui changent à l'identique sur plusieurs pages DISTINCTES.

    Le gabarit d'un portail régional change pour tout le site à la fois :
    carrousel d'actualités, crédits photo, bandeau RGPD, listes de rubriques,
    pied de page. Mesuré au premier passage réel : 68 % des lignes diffées
    apparaissaient sur au moins deux pages différentes, et aucune n'était
    rattrapée par le filtre de bruit à motifs — c'est ce qui classait 79 aides
    sur 142 « à mettre à jour » alors que leur règlement n'avait pas bougé.

    Aucune liste de motifs ne tient face à ça : « Mon été, ma Région : que faire
    cet été ? » est de la prose parfaitement formée. Seule la RÉCURRENCE la
    distingue du règlement, qui lui est propre à sa page.

    Le décompte porte sur les URL distinctes, jamais sur les aides : cinq aides
    partageant un même règlement ne doivent pas faire passer sa vraie
    modification pour du gabarit. Et une ligne de règlement (échéance, montant,
    cf. `ligne_de_reglement`) n'est jamais retenue, même vue sur plusieurs pages.
    """
    par_ligne: dict[str, set[str]] = defaultdict(set)
    for col in collects.values():
        for murl in col.urls:
            res = col.fetched.get(murl.url)
            if not (res and res.ok and res.texte and murl.baseline_body is not None):
                continue
            brut = normalized_diff(murl.baseline_body, res.texte)
            for ligne in brut.text.splitlines():
                if ligne[:2] in ("+ ", "- ") and (norm := normalize_line(ligne[2:])):
                    par_ligne[norm].add(murl.url)
    return frozenset(
        ligne
        for ligne, urls in par_ligne.items()
        if len(urls) >= CHROME_MIN_URLS and not ligne_de_reglement(ligne)
    )


def hotes_affames(collects: dict[str, AideCollect]) -> dict[str, int]:
    """Hôtes dont ce run voit trop peu d'URL pour reconnaître leur gabarit.

    `lignes_de_chrome` ne distingue le gabarit du contenu qu'à sa RÉCURRENCE
    sur au moins `CHROME_MIN_URLS` URL distinctes. Un run étroit — une seule
    aide, le cas courant quand on teste — ne lui donne rien à comparer : le
    menu du site passe alors pour du règlement et classe l'aide `MAJ_LLM`.

    Mesuré sur `pdl-restauration-mh` : `MAJ_LLM` lancée seule, `OK` lancée avec
    ses sept aides sœurs de paysdelaloire.fr. C'est un défaut de PÉRIMÈTRE du
    run, pas de la fiche ni du modèle — et il est invisible sans cet
    avertissement, puisque le verdict a l'air normal.

    Retourne {hôte: nombre d'URL diffables vues}, pour les hôtes sous le seuil.
    """
    par_hote: dict[str, set[str]] = defaultdict(set)
    for col in collects.values():
        for murl in col.urls:
            res = col.fetched.get(murl.url)
            if res and res.ok and res.texte and murl.baseline_body is not None:
                par_hote[murl.host].add(murl.url)
    return {h: len(urls) for h, urls in par_hote.items() if len(urls) < CHROME_MIN_URLS}


def analyze_all(
    aides: dict[str, Aide], collects: dict[str, AideCollect], *, today: date | None = None
) -> dict[str, AideAnalysis]:
    """Trie tout le parc. Deux passes : le chrome de site se détecte globalement.

    La première passe diffe tout pour repérer ce qui bouge partout à la fois ;
    la seconde retire ce gabarit et décide. Une aide analysée seule n'a pas
    cette information — c'est pourquoi le triage passe toujours par ici.
    """
    panne = _panne_generalisee(collects)
    chrome = lignes_de_chrome(collects)
    return {
        slug: analyze(aides[slug], col, today=today, panne_generalisee=panne, chrome=chrome)
        for slug, col in collects.items()
    }


def resume_diff(an: AideAnalysis, *, max_lignes: int = 40) -> str:
    """Diff lisible de toutes les URL changées, pour le rapport."""
    blocs = []
    for u in an.urls:
        if u.a_change and u.diff:
            texte = "\n".join(u.diff.text.splitlines()[:max_lignes])
            blocs.append(f"{u.murl.url}\n{texte}")
    return "\n\n".join(blocs)


__all__ = [
    "AideAnalysis",
    "QuoteVerdict",
    "STATUTS",
    "Statut",
    "UrlVerdict",
    "analyze",
    "analyze_all",
    "contenu_utile",
    "resume_diff",
]

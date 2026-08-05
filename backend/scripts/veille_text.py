"""
Primitives texte de la veille des aides : normalisation, matching de quotes, diff.

Zéro I/O, zéro réseau, zéro LLM — donc testable en isolation. Les trois étages
de la veille (collecte, analyse, mise à jour) partagent CES fonctions, et c'est
la condition de leur cohérence : une quote jugée « retrouvée » à l'analyse doit
l'être à l'identique lors de la validation de la sortie du modèle, sinon le
pipeline escalade ou applique sur des critères qui divergent d'un étage à
l'autre.

`normalize()` ne sert QU'AU matching et au diff. On n'écrit JAMAIS de texte
normalisé dans un YAML ou un snapshot : la sortie est désaccentuée, en
minuscules et sans sauts de ligne — elle détruirait les citations, qui doivent
rester verbatim.

Pourquoi une normalisation aussi agressive : les quotes des YAML ont été
copiées depuis des rendus HTML (apostrophes courbes, insécables, tirets
cadratins) alors que la même source relue en PDF passe par `pdftotext`, qui
rend une typographie différente. Sans désaccentuation ni repli de casse, une
quote authentique est déclarée « absente » et déclenche une escalade à tort.

Chaque assouplissement ici a été CALIBRÉ sur les 2 019 quotes du dépôt, avec
`scripts/veille_quotes_audit.py`, et aucun n'a été ajouté sans une classe de
divergence mesurée derrière lui :

  espace typographique avant ponctuation      1re cause de fausses absences
  élision « ... » / « [...] » de la saisie    31 quotes
  ponctuation de clôture ajoutée à la saisie  16 quotes
  liens markdown enrobés par html2text        7 quotes
  zone privée Unicode issue de pdftotext      cases à cocher des formulaires

Résultat : 94 % des quotes vérifiables retrouvées (86 % avant calibrage), et un
résidu de 99 quotes réparti sur 56 aides (6 au maximum sur une même aide) — la
dispersion est la signature d'une dette réelle, pas d'un bug systématique. Tout
nouvel assouplissement doit passer par la même mesure : le rôle de ce module est
d'absorber les divergences de RENDU, jamais les divergences de FOND.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

# Caractères dont la substitution ne peut pas être déléguée à NFKC (ils n'ont
# pas de décomposition de compatibilité) mais qui varient d'un rendu à l'autre.
_CHAR_MAP: dict[str, str] = {
    # Apostrophes : « l’édifice » (HTML) vs « l'édifice » (PDF, saisie manuelle).
    "’": "'",  # ’ apostrophe typographique
    "‘": "'",  # ‘
    "‛": "'",  # ‛
    "′": "'",  # ′ prime
    "´": "'",  # ´ accent aigu isolé
    # Guillemets : les français « » et les anglais “ ” désignent la même citation.
    "“": '"',  # “
    "”": '"',  # ”
    "„": '"',  # „
    "«": '"',  # «
    "»": '"',  # »
    "″": '"',  # ″
    # Tirets : un cadratin dans le règlement, un demi-cadratin dans la quote.
    "‐": "-",  # ‐
    "‑": "-",  # ‑ tiret insécable
    "‒": "-",  # ‒
    "–": "-",  # –
    "—": "-",  # —
    "―": "-",  # ―
    "−": "-",  # − signe moins
    "…": "...",  # … ellipse
    # Espaces exotiques → espace ordinaire (l'insécable avant « : » et « % »
    # est systématique dans les CMS français, absente des PDF).
    " ": " ",  # insécable
    " ": " ",  # chiffre
    " ": " ",  # ponctuation
    " ": " ",  # fine
    " ": " ",  # ultrafine
    " ": " ",  # fine insécable
    " ": " ",  # demi-cadratin
    " ": " ",  # cadratin
    " ": " ",
    " ": " ",
    " ": " ",
    "　": " ",  # idéographique
    " ": " ",  # séparateur de ligne
    " ": " ",  # séparateur de paragraphe
    # Trait d'union conditionnel : `pdftotext` en produit aux césures, il ne
    # doit pas couper un mot. Les autres invisibles (espaces sans largeur, BOM,
    # gluon de mots) relèvent des catégories Unicode filtrées dans `_fold_char`.
    "­": "",
    # Ligatures que NFKC ne décompose pas (contrairement à ﬁ / ﬂ) : « œuvre »
    # devient « oeuvre » dans certaines extractions PDF.
    "œ": "oe",  # œ
    "Œ": "oe",  # Œ
    "æ": "ae",  # æ
    "Æ": "ae",  # Æ
}


@lru_cache(maxsize=8192)
def _fold_char(ch: str) -> str:
    """Normalise UN caractère. Caché : l'alphabet est petit, les documents non.

    Le repli caractère par caractère donne le même résultat que sur la chaîne
    entière parce qu'on désaccentue : que « é » arrive précomposé (U+00E9) ou
    décomposé (« e » + U+0301), les deux finissent sur « e ». C'est ce qui
    permet de tenir une table d'offsets fiable vers le texte d'origine.
    """
    if (rep := _CHAR_MAP.get(ch)) is not None:
        return rep
    rep = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", ch))
    # `Mn` : accents (désaccentuation). `Cf` : caractères de formatage
    # (espaces sans largeur, BOM, marques bidi) semés par les CMS. `Co` : zone
    # privée — `pdftotext` y projette les glyphes des polices de symboles, d'où
    # les U+F020 qui polluent les cases à cocher des formulaires PDF.
    rep = "".join(c for c in rep if unicodedata.category(c) not in ("Mn", "Cf", "Co"))
    return rep.casefold()


# Ponctuation dont l'espace adjacent est purement typographique en français :
# l'espace fine avant « : ; ! ? % » est la règle dans les CMS, absente des PDF
# et de la plupart des saisies manuelles ; `pdftotext` en insère par ailleurs
# devant les virgules et les parenthèses fermantes. Effondrer cet espace ne
# peut pas rapprocher deux contenus distincts — « 50 % » et « 50% » disent la
# même chose, « 50 % » et « 80 % » restent différents.
_TIGHTEN_BEFORE = frozenset(",;:!?%).")
_TIGHTEN_AFTER = frozenset("(")


def normalize_with_offsets(s: str) -> tuple[str, list[int]]:
    """Normalise `s` et retourne la table d'offsets vers la chaîne d'origine.

    `offsets[i]` est l'index, dans `s`, du caractère qui a produit le caractère
    normalisé `i`. Sert à ramener une correspondance trouvée sur le texte
    normalisé vers le texte réel — pour citer la source dans le rapport, jamais
    pour écrire le texte normalisé lui-même.

    Tous les blancs (y compris les sauts de ligne) sont effondrés en un espace
    simple, et la chaîne est rognée aux deux bouts : une quote issue d'un block
    scalar YAML replié doit matcher le même texte réparti sur plusieurs lignes
    dans le snapshot.
    """
    out: list[str] = []
    offsets: list[int] = []
    pending_space = False
    for i, ch in enumerate(s):
        for c in _fold_char(ch):
            if c.isspace():
                pending_space = True
                continue
            if pending_space:
                pending_space = False
                tighten = c in _TIGHTEN_BEFORE or (out and out[-1] in _TIGHTEN_AFTER)
                # `out` vide ⇒ blancs de tête : on les jette (rognage à gauche).
                if out and not tighten:
                    out.append(" ")
                    offsets.append(i)
            out.append(c)
            offsets.append(i)
    # `pending_space` jamais vidé en fin de boucle ⇒ rognage à droite gratuit.
    return "".join(out), offsets


def normalize(s: str) -> str:
    """Forme canonique pour comparaison. Voir `normalize_with_offsets`.

    Implémentée par-dessus la version à offsets pour qu'il n'existe qu'UN seul
    chemin de code : deux implémentations parallèles finiraient par diverger, et
    une divergence ici fait mentir tout le triage.
    """
    return normalize_with_offsets(s)[0]


def normalize_lines(text: str) -> list[tuple[str, str]]:
    """Découpe en lignes et retourne les paires (normalisée, brute) non vides.

    Le diff s'aligne sur la forme normalisée (insensible au bruit
    typographique) mais s'affiche en texte brut : un rapport ou un prompt
    rempli de texte désaccentué en minuscules serait illisible et induirait le
    modèle en erreur sur la casse réelle de la source.
    """
    pairs = []
    for raw in text.splitlines():
        norm = normalize(raw)
        if norm:
            pairs.append((norm, raw.strip()))
    return pairs


# ---------------------------------------------------------------------------
# En-tête de snapshot
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)


def parse_front_matter(md: str) -> tuple[dict[str, str], str]:
    """Sépare l'en-tête de métadonnées d'un snapshot `.md` de son corps.

    L'en-tête est écrit par `snapshot_source.py` (url, fetched_at, sha256).
    Volontairement parsé à la main plutôt qu'en YAML : les valeurs sont des
    scalaires plats, et une URL contenant « : » ne doit pas faire échouer la
    lecture de la provenance de tout un snapshot.
    """
    m = _FRONT_MATTER_RE.match(md)
    if not m:
        return {}, md
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            meta[key.strip()] = value.strip()
    return meta, md[m.end() :]


def strip_front_matter(md: str) -> str:
    return parse_front_matter(md)[1]


_MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\((?:[^()\s]|\([^()]*\))*\)")


def flatten_markdown_links(md: str) -> str:
    """Réduit `[libellé](url)` à `libellé`.

    `html2text` enrobe toute ancre du corps de texte, y compris au milieu d'une
    phrase : « déposer sur la plateforme [mesdemarches.fr](https://…) » casse
    une quote pourtant authentique, saisie depuis le rendu visuel de la page où
    l'URL n'apparaît pas. On défait donc une transformation connue de notre
    propre outil de snapshot — le libellé est conservé caractère pour caractère,
    rien n'est deviné.
    """
    return _MD_LINK_RE.sub(r"\1", md)


# ---------------------------------------------------------------------------
# Filtre de bruit
# ---------------------------------------------------------------------------

# Un lien markdown seul sur sa ligne (`[Nos projets](https://…)`, éventuellement
# précédé d'une puce html2text). C'est la forme de tous les menus de navigation.
_LINK_ONLY_RE = re.compile(r"^(?:[*+-]\s+)?\[(?P<label>[^\]]*)\]\([^)]*\)$")

# Marqueurs de chrome de page. Liste VOLONTAIREMENT courte : chaque entrée est
# un risque de masquer du contenu réel, et le seul coût d'un oubli est un faux
# positif de diff, que le triage absorbe. Le rapport compte les lignes filtrées
# pour rendre ce filtre auditable au lieu de le laisser silencieux.
_NOISE_MARKERS = (
    "cookie",
    "politique de confidentialite",
    "mentions legales",
    "plan du site",
    "partager sur",
    "aller au contenu",
    "mot de passe oublie",
    "se connecter",
    "mon compte",
    "newsletter",
)

# Séparateurs html2text (`* * *`), lignes de puces vides, images seules.
_DECORATION_RE = re.compile(r"^(?:[*_\-\s]+|!\[[^\]]*\]\([^)]*\))$")

_MAX_NOISE_LABEL = 60


def is_noise_line(line: str) -> bool:
    """Vrai si la ligne relève du chrome de page et non du contenu.

    Garde-fou sur les liens : un lien porteur d'un chiffre (« Règlement 2026 »,
    « Dossier — 15 novembre ») ou au label long n'est PAS du bruit. Une échéance
    annoncée uniquement dans un libellé de lien doit continuer de déclencher le
    triage — c'est exactement le changement qu'on cherche à détecter.
    """
    norm = normalize(line)
    if not norm:
        return True
    if _DECORATION_RE.match(line.strip()):
        return True
    if any(marker in norm for marker in _NOISE_MARKERS):
        return True
    if m := _LINK_ONLY_RE.match(line.strip()):
        label = m.group("label").strip()
        return len(label) <= _MAX_NOISE_LABEL and not any(c.isdigit() for c in label)
    return False


# ---------------------------------------------------------------------------
# Matching de quotes
# ---------------------------------------------------------------------------

QuoteStatus = Literal["exacte", "degradee", "baseline_pdf", "absente"]


@dataclass(frozen=True)
class QuoteMatch:
    """Résultat de la recherche d'une quote dans un document.

    `start`/`end` indexent le texte BRUT du document (pas sa forme normalisée),
    pour pouvoir en extraire le passage réel — sa typographie d'origine
    comprise — dans un rapport ou un prompt.
    """

    status: QuoteStatus
    start: int | None = None
    end: int | None = None
    # Renseigné quand la correspondance a demandé de retoucher la quote (voir
    # `find_quote`) : `elision` ou `ponctuation_finale`. La preuve est alors plus
    # faible qu'une citation contiguë, donc jamais `exacte`, et le rapport les
    # compte à part pour que l'assouplissement reste visible et auditable.
    reconstitution: Literal["elision", "ponctuation_finale"] | None = None
    # Nombre de caractères normalisés de la quote retrouvés depuis son début.
    # Égal à la longueur de la quote normalisée quand le statut n'est pas
    # `absente` ; sinon c'est le point de divergence, qui distingue une vraie
    # disparition (0) d'un décalage de typographie ou de troncature (> 0).
    prefix_len: int = 0
    quote_len: int = 0

    @property
    def found(self) -> bool:
        return self.status != "absente"

    @property
    def prefix_ratio(self) -> float:
        return self.prefix_len / self.quote_len if self.quote_len else 0.0

    def excerpt(self, haystack: str) -> str | None:
        if self.start is None or self.end is None:
            return None
        return haystack[self.start : self.end]


def _matching_prefix_len(needle: str, haystack: str) -> int:
    """Longueur du plus long préfixe de `needle` présent dans `haystack`.

    Recherche dichotomique : si un préfixe de longueur k est présent, tout
    préfixe plus court l'est aussi, donc la propriété est monotone. O(log n)
    recherches de sous-chaîne au lieu de n.
    """
    if not needle or needle[0] not in haystack:
        return 0
    lo, hi = 1, len(needle)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if needle[:mid] in haystack:
            lo = mid
        else:
            hi = mid - 1
    return lo


# Marqueurs d'élision dans les quotes du dépôt : les fiches sautent un passage
# non pertinent avec « … » (« ce partenariat. ... le bénéficiaire ») ou avec
# « [...] » (« les festivals hors région ; [...] les stages »). C'est une
# convention de saisie, pas un caractère de la source : la chercher
# littéralement fait échouer une citation authentique.
_ELISION_RE = re.compile(r"\[\.\.\.\]|\.\.\.")
# Une élision saute une incise ou une phrase, pas la moitié d'un règlement :
# au-delà, les fragments matchent probablement des passages sans rapport.
_ELISION_WINDOW_FACTOR = 4
_ELISION_WINDOW_MIN = 400
# Le plus long fragment doit rester une preuve à lui seul. Sinon une quote
# réduite à des miettes (« : », « ). ») matcherait n'importe quel document.
_ELISION_MIN_ANCHOR = 12


def _find_elided(quote_norm: str, hay_norm: str) -> tuple[int, int] | None:
    """Cherche les fragments d'une quote élidée, dans l'ordre et sans chevauchement.

    Retourne le span normalisé couvert (début du 1er fragment, fin du dernier)
    ou None. Recherche gloutonne : la première occurrence de chaque fragment
    après la fin du précédent. Suffisant ici — les fragments sont longs et
    l'ancrage du premier lève l'ambiguïté.
    """
    fragments = [f for frag in _ELISION_RE.split(quote_norm) if (f := frag.strip())]
    if not fragments or max(len(f) for f in fragments) < _ELISION_MIN_ANCHOR:
        return None
    total = sum(len(f) for f in fragments)
    if total == len(quote_norm):
        return None  # aucune élision : rien à reconstituer

    start: int | None = None
    pos = 0
    for frag in fragments:
        idx = hay_norm.find(frag, pos)
        if idx == -1:
            return None
        if start is None:
            start = idx
        pos = idx + len(frag)
    assert start is not None
    if pos - start > max(_ELISION_WINDOW_MIN, _ELISION_WINDOW_FACTOR * total):
        return None
    return start, pos


# Ponctuation de clôture ajoutée à la saisie : citer une longue phrase en la
# coupant se termine par un point que la source n'a pas à cet endroit (« … du
# 17 juin 2014. » alors qu'elle continue par « déclarant certaines aides… »).
# `pdftotext` produit le même effet en collant les appels de note (« par année
# civile1. »). Mesuré : c'est la première cause de quotes authentiques encore
# déclarées absentes après normalisation.
_TRAILING_PUNCT = ".,;:)'\" "
# La retouche ne doit jamais amputer la substance de la citation : la preuve
# reste les ~200 caractères qui précèdent, pas le point retiré.
_TRAILING_MIN_KEPT = 20
_TRAILING_MIN_RATIO = 0.9


def _strip_trailing_punct(quote_norm: str) -> str | None:
    """Quote sans sa ponctuation de clôture, ou None si la retouche est abusive."""
    tronquee = quote_norm.rstrip(_TRAILING_PUNCT)
    if tronquee == quote_norm:
        return None
    if len(tronquee) < _TRAILING_MIN_KEPT or len(tronquee) < _TRAILING_MIN_RATIO * len(quote_norm):
        return None
    return tronquee


def find_quote(
    quote: str,
    haystack: str,
    *,
    source_kind: Literal["text", "pdf"] = "text",
) -> QuoteMatch:
    """Cherche `quote` dans `haystack`, d'abord verbatim puis après normalisation.

    Statuts :
      - `exacte`       : retrouvée caractère pour caractère (source inchangée)
      - `degradee`     : retrouvée seulement après normalisation (la source a
                         changé de typographie, pas de fond — aucune action)
      - `baseline_pdf` : retrouvée dans un PDF. Distingué parce qu'un PDF n'est
                         pas re-téléchargeable en texte comparable : la quote
                         est justifiée, mais on ne peut pas surveiller la page.
      - `absente`      : à confirmer par un humain ou par le modèle

    `source_kind="pdf"` n'assouplit pas la recherche : il ne fait que qualifier
    la provenance d'une correspondance trouvée.
    """
    quote_norm = normalize(quote)
    if not quote_norm:
        return QuoteMatch(status="absente")

    def result(
        start_end: tuple[int, int],
        *,
        exact: bool = False,
        reconstitution: Literal["elision", "ponctuation_finale"] | None = None,
    ) -> QuoteMatch:
        if source_kind == "pdf":
            status: QuoteStatus = "baseline_pdf"
        else:
            status = "exacte" if exact else "degradee"
        return QuoteMatch(
            status=status,
            start=start_end[0],
            end=start_end[1],
            reconstitution=reconstitution,
            prefix_len=len(quote_norm),
            quote_len=len(quote_norm),
        )

    if quote and quote in haystack:
        start = haystack.index(quote)
        return result((start, start + len(quote)), exact=True)

    hay_norm, offsets = normalize_with_offsets(haystack)

    def to_raw_span(span: tuple[int, int]) -> tuple[int, int]:
        # `offsets[j]` donne le caractère d'origine ayant produit le normalisé
        # `j` ; la borne de fin est exclusive côté normalisé, on prend donc le
        # dernier caractère couvert, + 1 pour une tranche brute inclusive.
        start_norm, end_norm = span
        return offsets[start_norm], offsets[end_norm - 1] + 1

    # Retrouvée après normalisation seule : la source n'a bougé que sur la
    # typographie, il n'y a rien à faire.
    if (idx := hay_norm.find(quote_norm)) != -1:
        return result(to_raw_span((idx, idx + len(quote_norm))))

    if (span := _find_elided(quote_norm, hay_norm)) is not None:
        return result(to_raw_span(span), reconstitution="elision")

    tronquee = _strip_trailing_punct(quote_norm)
    if tronquee is not None and (idx := hay_norm.find(tronquee)) != -1:
        return result(to_raw_span((idx, idx + len(tronquee))), reconstitution="ponctuation_finale")

    return QuoteMatch(
        status="absente",
        prefix_len=_matching_prefix_len(quote_norm, hay_norm),
        quote_len=len(quote_norm),
    )


def find_quote_in_any(
    quote: str,
    documents: list[tuple[str, str, Literal["text", "pdf"]]],
) -> tuple[str | None, QuoteMatch]:
    """Cherche la quote dans plusieurs documents, garde la meilleure preuve.

    `documents` : liste de (nom, contenu, type). Une aide a souvent plusieurs
    snapshots (page + règlement PDF + formulaire) et une quote n'est justifiée
    que par l'un d'eux ; c'est donc le MEILLEUR statut qui compte, pas celui du
    premier document essayé. Retourne (nom du document, correspondance) — nom à
    None si la quote est introuvable partout.
    """
    order: dict[QuoteStatus, int] = {"exacte": 3, "degradee": 2, "baseline_pdf": 1, "absente": 0}

    def score(m: QuoteMatch) -> tuple[int, int, int]:
        # Une citation intacte primant une citation reconstituée, et à défaut de
        # correspondance, le plus long préfixe commun — c'est lui qui rend le
        # diagnostic d'une quote absente exploitable.
        return (order[m.status], 0 if m.reconstitution else 1, m.prefix_len)

    best_name: str | None = None
    best = QuoteMatch(status="absente", quote_len=len(normalize(quote)))
    for name, content, kind in documents:
        match = find_quote(quote, content, source_kind=kind)
        if score(match) > score(best):
            best, best_name = match, name if match.found else None
            if best.status == "exacte":
                break
    return best_name, best


# ---------------------------------------------------------------------------
# Diff normalisé
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedDiff:
    """Écart de fond entre deux versions d'un document.

    `ratio` est la part de lignes touchées (ajoutées + supprimées) sur la plus
    longue des deux versions : c'est lui qui décide de l'escalade vers une
    ré-ingestion complète, une page refondue n'étant pas rattrapable par des
    retouches de champs.
    """

    ratio: float
    text: str
    added: int
    removed: int
    noise_filtered: int
    truncated: bool = False

    @property
    def changed(self) -> int:
        return self.added + self.removed

    @property
    def is_empty(self) -> bool:
        return self.changed == 0


def normalized_diff(old: str, new: str, *, max_lines: int = 400) -> NormalizedDiff:
    """Diff de fond entre deux documents, insensible au bruit.

    Deux couches de désensibilisation, indispensables sur 142 aides : la
    normalisation (un CMS qui change ses apostrophes ferait sinon clignoter
    toutes les pages) et le filtre de bruit (menus, bandeaux cookies, liens de
    partage — présents sur chaque page et régénérés à chaque requête).

    `max_lines` borne le texte du diff seul, pas le calcul : le ratio reste
    juste même quand l'affichage est tronqué, sinon un plafond d'affichage
    ferait dériver une décision d'escalade.
    """
    noise = 0
    keep: list[list[tuple[str, str]]] = [[], []]
    for slot, text in ((0, old), (1, new)):
        for norm, raw in normalize_lines(text):
            if is_noise_line(raw):
                noise += 1
            else:
                keep[slot].append((norm, raw))
    old_pairs, new_pairs = keep

    matcher = difflib.SequenceMatcher(
        a=[n for n, _ in old_pairs], b=[n for n, _ in new_pairs], autojunk=False
    )
    added = removed = 0
    lines: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed += i2 - i1
        added += j2 - j1
        lines.extend(f"- {old_pairs[i][1]}" for i in range(i1, i2))
        lines.extend(f"+ {new_pairs[j][1]}" for j in range(j1, j2))

    truncated = len(lines) > max_lines
    if truncated:
        omitted = len(lines) - max_lines
        lines = [*lines[:max_lines], f"... ({omitted} ligne(s) de diff omise(s))"]

    denominator = max(len(old_pairs), len(new_pairs), 1)
    return NormalizedDiff(
        ratio=(added + removed) / denominator,
        text="\n".join(lines),
        added=added,
        removed=removed,
        noise_filtered=noise,
        truncated=truncated,
    )


def is_cosmetic_change(before: str | None, after: str | None) -> bool:
    """Vrai si passer de `before` à `after` ne change rien au fond.

    Sert de dernier filet à l'étage C : une op purement typographique proposée
    par le modèle est comptée « cosmétique » et jetée. Réécrire une apostrophe
    droite en courbe dans un YAML soigné à la main polluerait le `git diff`,
    qui EST la revue humaine.
    """
    return normalize(before or "") == normalize(after or "")

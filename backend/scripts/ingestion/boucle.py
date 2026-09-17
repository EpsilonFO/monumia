"""La boucle d'agent : appeler, exécuter, élaguer, s'arrêter à temps.

`providall.tool_loop` fait tourner un agent en vingt lignes, et ne suffit pas
ici. Il manque les quatre choses qui font la différence entre une démo et un
run de 130 aides :

  - **un budget**, en dollars quand le tarif est connu, en jetons d'entrée
    sinon. Avec avertissement à 100 % (le modèle a encore le temps d'écrire sa
    review) puis arrêt dur à 125 % ;
  - **une troncature** des sorties d'outil : un PDF de règlement fait 300 Ko, et
    `tool_loop` le recopierait intégralement dans la conversation ;
  - **un élagage** : au-delà du seuil, les vieilles lectures de snapshot sont
    remplacées par un talon « relis-le si besoin ». Sans ça, le contexte croît
    de 22 k à 90 k jetons sur 60 tours et chaque tour repaye tout ;
  - **des relances** : un modèle qui s'arrête sans avoir écrit sa review n'a pas
    fini, et le lui dire suffit presque toujours.

Ce que la boucle ne fait pas : juger. Aucun contrôle de qualité ici — ils sont
tous dans `worker.py`, après coup, et déterministes.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.llm import Compteur
from providall import Message, Response, ToolCall, Usage
from providall.errors import EmptyResponseError, ProvidallError
from providall.tools import Tool, as_tools

Arret = Literal["termine", "sans_review", "budget", "max_tours", "erreur_modele", "boucle"]

# Une sortie d'outil plus courte que ça ne vaut pas la peine d'être élaguée :
# le talon qui la remplacerait coûterait presque autant.
TAILLE_MIN_ELAGAGE = 2_000

# Outils dont la sortie n'est JAMAIS élaguée : c'est l'état courant du travail
# (le YAML écrit, le verdict du lint, les reproches du vérificateur), pas une
# lecture qu'on peut refaire. L'effacer ferait retravailler le modèle à l'aveugle.
OUTILS_INELAGUABLES = frozenset({"ecrire_aide", "lint", "verification_adversariale"})

TALON = (
    "[sortie élaguée pour tenir dans le contexte — relis-la avec `lire_snapshot` "
    "si tu en as encore besoin]"
)


@dataclass
class Limites:
    """Les bornes d'un run. Toutes réglables en ligne de commande."""

    max_tours: int = 120
    budget_usd: float = 1.5
    # Plafond de repli quand le tarif du modèle est inconnu : sans lui, un
    # modèle hors registre tournerait sans aucune limite de coût.
    budget_tokens_entree: int = 6_000_000
    max_car_sortie: int = 40_000
    garder_sorties: int = 8
    seuil_elagage_tokens: int = 110_000
    max_relances: int = 2
    # Au-delà de ce multiple du budget, on coupe sans négocier.
    facteur_arret_dur: float = 1.25
    # Un modèle à raisonnement peut brûler tout son budget de sortie à réfléchir
    # et ne rien rendre (`EmptyResponseError`, budget de sortie épuisé). Élaguer
    # n'y change rien ; on rejoue le tour avec deux fois plus de jetons de
    # sortie, une fois, sans dépasser ce plafond. Vu le 2026-09-09 sur or-glm à
    # 32 000 jetons, alors qu'OpenRouter en accepte 131 072 pour ce modèle.
    plafond_sortie_sauvetage: int = 128_000
    # Une erreur TRANSITOIRE du fournisseur (`retryable`), après les relances
    # internes de providall : on attend un peu et on rejoue le tour, une fois.
    # Le 2026-09-09, un `finish_reason='error'` répété a tué une aide au tour 5.
    pause_relance_s: float = 2.0
    # Détection de boucle. Le 2026-09-09, une aide a passé 95 tours à relire les
    # mêmes lignes sans jamais écrire : 12 centimes grâce au cache, donc le
    # budget en dollars n'a rien vu, et seuls les 120 tours l'ont arrêtée, deux
    # heures plus tard. Deux signaux : le même appel d'outil répété à
    # l'identique d'un tour sur l'autre, et l'absence prolongée d'appel qui
    # fasse avancer l'ingestion (snapshot, fait, écriture, lint, vérification).
    # Un rappel à l'ordre au premier seuil, l'arrêt au second.
    appels_identiques_avertir: int = 3
    appels_identiques_max: int = 6
    tours_sans_progres_avertir: int = 40
    tours_sans_progres_max: int = 60


@dataclass
class Resultat:
    arret: Arret
    tours: int
    usage: Usage
    cout_usd: float
    cout_inconnu: bool
    messages: list[Message] = field(default_factory=list)
    motif: str = ""

    @property
    def ok(self) -> bool:
        return self.arret == "termine"


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


class Journal:
    """Trace complète d'un run, dans `data/reviews/logs/ingest-<slug>.log`.

    Ce fichier est la seule chose qui permette de comprendre APRÈS COUP pourquoi
    une ingestion a coûté trois fois le prix ou raté une condition : quels
    outils, avec quels arguments, dans quel ordre, et ce que le modèle a
    répondu. Il est ignoré par git — c'est une trace d'exécution, pas une donnée.

    Le YAML écrit par `ecrire_aide` y va EN ENTIER, contrairement aux autres
    arguments : c'est le produit du travail, et le tronquer rendrait le journal
    inutile pour reconstituer ce qui a été proposé à chaque tentative.
    """

    MAX_CAR_SORTIE = 3_000
    MAX_CAR_ARGS = 3_000

    def __init__(self, chemin: Path, *, entete: str = "") -> None:
        self.chemin = chemin
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self._fichier = chemin.open("a", encoding="utf-8")
        if entete:
            self._ecrire(f"\n{'=' * 78}\n{entete}\n{'=' * 78}")

    def _ecrire(self, texte: str) -> None:
        self._fichier.write(texte.rstrip() + "\n")
        self._fichier.flush()

    def tour(self, n: int, reponse: Response, *, cout_cumule: float) -> None:
        u = reponse.usage
        self._ecrire(
            f"\n--- tour {n} — entrée {u.input_tokens} (+{u.cache_read_tokens} cache) / "
            f"sortie {u.output_tokens} — cumul ${cout_cumule:.4f} — "
            f"{reponse.finish_reason or '?'}"
        )
        if reponse.reasoning:
            self._ecrire(f"[raisonnement] {reponse.reasoning.strip()}")
        if reponse.text.strip():
            self._ecrire(f"[texte] {reponse.text.strip()}")

    def appel(self, appel: ToolCall, sortie: str) -> None:
        args = appel.arguments or "{}"
        if appel.name != "ecrire_aide" and len(args) > self.MAX_CAR_ARGS:
            args = args[: self.MAX_CAR_ARGS] + f"… (+{len(args) - self.MAX_CAR_ARGS} car.)"
        self._ecrire(f"[appel] {appel.name}({args})")
        rendu = (
            sortie
            if len(sortie) <= self.MAX_CAR_SORTIE
            else (sortie[: self.MAX_CAR_SORTIE] + f"… (+{len(sortie) - self.MAX_CAR_SORTIE} car.)")
        )
        self._ecrire(f"[sortie] {rendu}")

    def evenement(self, texte: str) -> None:
        self._ecrire(f"[*] {texte}")

    def close(self) -> None:
        self._fichier.close()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class JournalMuet(Journal):
    """Journal qui n'écrit nulle part — pour les tests et les `--dry-run`."""

    def __init__(self) -> None:  # noqa: D107 - pas de fichier à ouvrir
        self.chemin = Path("/dev/null")
        self.evenements: list[str] = []

    def _ecrire(self, texte: str) -> None:
        self.evenements.append(texte)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Exécution des outils
# ---------------------------------------------------------------------------


def executer_appel(table: dict[str, Tool], appel: ToolCall) -> str:
    """Exécute un outil et rend TOUJOURS du texte, erreur comprise.

    Copie assumée des huit lignes de `providall.tools._executer` : renvoyer
    l'erreur au modèle plutôt que la lever est la bonne décision (il se corrige
    souvent), mais la fonction est privée et son comportement fait partie du
    contrat de cette boucle.
    """
    outil = table.get(appel.name)
    if outil is None:
        return f"ERREUR : outil inconnu « {appel.name} ». Disponibles : {', '.join(sorted(table))}"
    try:
        resultat = outil.run(appel.parsed())
    except Exception as exc:  # noqa: BLE001 — l'erreur est une donnée pour le modèle
        return f"ERREUR : {type(exc).__name__}: {exc}"
    if isinstance(resultat, str):
        return resultat
    try:
        return json.dumps(resultat, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(resultat)


def tronquer(sortie: str, maximum: int) -> str:
    if len(sortie) <= maximum:
        return sortie
    reste = len(sortie) - maximum
    return sortie[:maximum] + (
        f"\n\n[… sortie tronquée à {maximum} caractères, {reste} de plus non affichés. "
        "Relis la suite par tranches (offset/limit) si tu en as besoin.]"
    )


# ---------------------------------------------------------------------------
# Élagage
# ---------------------------------------------------------------------------


def elaguer(conversation: list[Message], garder: int) -> int:
    """Remplace les vieilles sorties d'outil volumineuses par un talon.

    Ne touche JAMAIS aux messages de l'assistant : chez Anthropic, un bloc
    `tool_use` détaché de son `thinking` signé est refusé, et plus généralement
    récrire le raisonnement du modèle lui fait perdre le fil. Ne touche pas non
    plus aux `garder` dernières sorties — ce sont celles sur lesquelles il
    travaille.

    Renvoie le nombre de caractères récupérés.
    """
    indices = [
        i
        for i, m in enumerate(conversation)
        if m.role == "tool"
        and (m.name or "") not in OUTILS_INELAGUABLES
        and isinstance(m.content, str)
        and len(m.content) > TAILLE_MIN_ELAGAGE
    ]
    gagne = 0
    for i in indices[: max(0, len(indices) - garder)]:
        message = conversation[i]
        assert isinstance(message.content, str)
        gagne += len(message.content) - len(TALON)
        conversation[i] = Message(
            role="tool",
            tool_call_id=message.tool_call_id,
            name=message.name,
            content=TALON,
        )
    return gagne


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@dataclass
class Budget:
    """Combien il reste, et dans quelle unité.

    Deux unités parce que le tarif d'un modèle n'est pas toujours au registre
    providall : plutôt qu'un budget silencieusement infini, on plafonne alors
    les jetons d'entrée cumulés — grossier, mais borné.
    """

    limites: Limites
    cout: float = 0.0
    tokens_in: int = 0
    inconnu: bool = False

    def ajouter(self, reponse: Response) -> None:
        u = reponse.usage
        self.tokens_in += u.input_tokens + u.cache_read_tokens + u.cache_write_tokens
        if reponse.cost_usd is None:
            self.inconnu = True
        else:
            self.cout += reponse.cost_usd

    @property
    def part(self) -> float:
        """Fraction du budget consommée (1.0 = plafond atteint)."""
        if self.inconnu or self.limites.budget_usd <= 0:
            return self.tokens_in / max(self.limites.budget_tokens_entree, 1)
        return self.cout / self.limites.budget_usd

    @property
    def unite(self) -> str:
        return "jetons d'entrée" if self.inconnu else "dollars"

    def resume(self) -> str:
        if self.inconnu:
            return f"{self.tokens_in} / {self.limites.budget_tokens_entree} jetons d'entrée"
        return f"${self.cout:.4f} / ${self.limites.budget_usd:.2f}"


AVERTISSEMENT_BUDGET = (
    "BUDGET ÉPUISÉ ({resume}). Arrête l'extraction MAINTENANT. Dans cet ordre, et "
    "sans rien explorer de plus : (1) `lint`, (2) `ecrire_review` en décrivant "
    "l'état atteint ET ce qui manque encore. Puis réponds sans appeler d'outil."
)


# ---------------------------------------------------------------------------
# Boucle
# ---------------------------------------------------------------------------


def executer(
    client: providall.Client,
    system: str,
    prompt: str,
    outils: Sequence[Any],
    *,
    limites: Limites | None = None,
    journal: Journal | None = None,
    compteur: Compteur | None = None,
    review_ecrite: Callable[[], bool] = lambda: True,
) -> Resultat:
    """Fait tourner l'agent jusqu'à ce qu'il ait fini, ou qu'on l'arrête."""
    limites = limites or Limites()
    journal = journal or JournalMuet()
    table_outils = as_tools(outils)
    definitions = [o.definition for o in table_outils]
    table = {o.name: o for o in table_outils}

    conversation: list[Message] = [
        Message(role="system", content=system),
        Message(role="user", content=prompt),
    ]
    budget = Budget(limites)
    usage_cumule = Usage()
    relances = 0
    averti = False
    sauvetages = 0
    max_tokens_force: int | None = None
    relance_transitoire_faite = False
    signature_precedente = ""
    repetitions = 0
    dernier_tour_progres = 0
    avertis: set[str] = set()
    depart = time.monotonic()

    for tour in range(1, limites.max_tours + 1):
        try:
            reponse = client.complete(conversation, tools=definitions, max_tokens=max_tokens_force)
        except ProvidallError as exc:
            journal.evenement(f"appel en échec : {type(exc).__name__}: {exc}")
            if _sortie_epuisee(exc) and max_tokens_force is None:
                courant = _max_tokens_courant(client, exc)
                max_tokens_force = min(courant * 2, limites.plafond_sortie_sauvetage)
                if max_tokens_force > courant:
                    journal.evenement(
                        f"sauvetage : budget de sortie épuisé à {courant} jetons (raisonnement), "
                        f"même tour rejoué avec {max_tokens_force} — conservé pour la suite du run"
                    )
                    continue
            if getattr(exc, "retryable", False) and not relance_transitoire_faite:
                relance_transitoire_faite = True
                journal.evenement(
                    f"erreur transitoire, même tour rejoué dans {limites.pause_relance_s:g} s"
                )
                time.sleep(limites.pause_relance_s)
                continue
            # Une seule tentative de sauvetage : si le contexte a débordé,
            # l'élagage peut suffire à faire repasser l'appel. Au-delà, on
            # rend la main — providall a déjà fait ses propres relances.
            if sauvetages or not _sauvetage(conversation, limites, journal):
                return Resultat(
                    arret="erreur_modele",
                    tours=tour - 1,
                    usage=usage_cumule,
                    cout_usd=budget.cout,
                    cout_inconnu=budget.inconnu,
                    messages=conversation,
                    motif=f"{type(exc).__name__}: {exc}",
                )
            sauvetages += 1
            continue

        usage_cumule = usage_cumule + reponse.usage
        budget.ajouter(reponse)
        if compteur is not None:
            compteur.ajouter(reponse, "ingestion")
        journal.tour(tour, reponse, cout_cumule=budget.cout)
        if reponse.message:
            # Rejoué TEL QUEL : chez Anthropic le bloc `thinking` signé qui
            # précède un `tool_use` fait partie du message, et le reconstruire
            # ferait refuser le tour suivant.
            conversation.append(reponse.message)

        if not reponse.tool_calls:
            if review_ecrite():
                journal.evenement(
                    f"terminé en {tour} tour(s), {budget.resume()}, "
                    f"durée {time.monotonic() - depart:.0f} s"
                )
                return Resultat(
                    arret="termine",
                    tours=tour,
                    usage=usage_cumule,
                    cout_usd=budget.cout,
                    cout_inconnu=budget.inconnu,
                    messages=conversation,
                )
            if relances >= limites.max_relances:
                journal.evenement(
                    f"arrêt : aucune review après relances, durée {time.monotonic() - depart:.0f} s"
                )
                return Resultat(
                    arret="sans_review",
                    tours=tour,
                    usage=usage_cumule,
                    cout_usd=budget.cout,
                    cout_inconnu=budget.inconnu,
                    messages=conversation,
                    motif="l'agent a rendu la main sans appeler ecrire_review",
                )
            relances += 1
            journal.evenement(f"relance {relances}/{limites.max_relances} : review manquante")
            conversation.append(
                Message(
                    role="user",
                    content=(
                        "Tu n'as pas appelé `ecrire_review`, l'ingestion n'est donc pas "
                        "terminée. Vérifie que `lint` est vert, puis écris la fiche de "
                        "review (étape 5 du skill) avec `ecrire_review`."
                    ),
                )
            )
            continue

        for appel in reponse.tool_calls:
            sortie = tronquer(executer_appel(table, appel), limites.max_car_sortie)
            journal.appel(appel, sortie)
            conversation.append(
                Message(role="tool", tool_call_id=appel.id, name=appel.name, content=sortie)
            )

        # --- détection de boucle
        signature = _signature_tour(reponse.tool_calls)
        repetitions = repetitions + 1 if signature == signature_precedente else 1
        signature_precedente = signature
        if any(a.name in OUTILS_PROGRES for a in reponse.tool_calls):
            dernier_tour_progres = tour
        sans_progres = tour - dernier_tour_progres
        motif_boucle = None
        if repetitions >= limites.appels_identiques_max:
            motif_boucle = f"le même appel d'outil rejoué {repetitions} tours de suite"
        elif sans_progres >= limites.tours_sans_progres_max:
            motif_boucle = (
                f"{sans_progres} tours sans snapshot, fait, écriture, lint ni vérification"
            )
        if motif_boucle:
            journal.evenement(
                f"arrêt : boucle — {motif_boucle}, durée {time.monotonic() - depart:.0f} s"
            )
            return Resultat(
                arret="boucle",
                tours=tour,
                usage=usage_cumule,
                cout_usd=budget.cout,
                cout_inconnu=budget.inconnu,
                messages=conversation,
                motif=motif_boucle,
            )
        rappel = None
        if repetitions == limites.appels_identiques_avertir and "identiques" not in avertis:
            avertis.add("identiques")
            rappel = (
                f"Tu viens de faire {repetitions} fois de suite exactement le même appel "
                "d'outil, avec le même résultat. Il ne rendra rien de plus. Avec ce que tu "
                "as déjà lu, écris le fichier (`ecrire_aide`), lance `lint`, puis la "
                "vérification et la fiche. Si une information manque vraiment, dis-le "
                "dans la fiche plutôt que de la chercher encore."
            )
        elif sans_progres == limites.tours_sans_progres_avertir and "progres" not in avertis:
            avertis.add("progres")
            rappel = (
                f"Cela fait {sans_progres} tours que tu lis et cherches sans rien produire. "
                "Écris maintenant le fichier avec ce que tu as (`ecrire_aide`), puis `lint`, "
                "`verification_adversariale` et `ecrire_review`. Ce qui reste incertain se "
                "consigne dans la fiche."
            )
        if rappel:
            journal.evenement(f"rappel à l'ordre : {rappel[:60]}…")
            conversation.append(Message(role="user", content=rappel))

        contexte = (
            reponse.usage.input_tokens
            + reponse.usage.cache_read_tokens
            + reponse.usage.cache_write_tokens
        )
        if contexte > limites.seuil_elagage_tokens:
            gagne = elaguer(conversation, limites.garder_sorties)
            if gagne:
                journal.evenement(f"élagage : {gagne} caractères retirés ({contexte} jetons)")

        if budget.part >= limites.facteur_arret_dur:
            journal.evenement(
                f"arrêt dur : budget dépassé ({budget.resume()}), "
                f"durée {time.monotonic() - depart:.0f} s"
            )
            return Resultat(
                arret="budget",
                tours=tour,
                usage=usage_cumule,
                cout_usd=budget.cout,
                cout_inconnu=budget.inconnu,
                messages=conversation,
                motif=f"budget dépassé ({budget.resume()})",
            )
        if budget.part >= 1.0 and not averti:
            averti = True
            journal.evenement(f"avertissement de budget ({budget.resume()})")
            conversation.append(
                Message(role="user", content=AVERTISSEMENT_BUDGET.format(resume=budget.resume()))
            )

    journal.evenement(
        f"arrêt : {limites.max_tours} tours atteints, durée {time.monotonic() - depart:.0f} s"
    )
    return Resultat(
        arret="max_tours",
        tours=limites.max_tours,
        usage=usage_cumule,
        cout_usd=budget.cout,
        cout_inconnu=budget.inconnu,
        messages=conversation,
        motif=f"{limites.max_tours} tours sans conclusion",
    )


OUTILS_PROGRES: frozenset[str] = frozenset(
    {
        "snapshotter",
        "proposer_fait",
        "ecrire_aide",
        "lint",
        "verification_adversariale",
        "ecrire_review",
    }
)


def _signature_tour(appels: Sequence[ToolCall]) -> str:
    """Empreinte des appels d'un tour, pour reconnaître un tour rejoué à l'identique."""
    return "|".join(
        f"{a.name}:{json.dumps(getattr(a, 'arguments', None), sort_keys=True, ensure_ascii=False)}"
        for a in appels
    )


def _sortie_epuisee(exc: ProvidallError) -> bool:
    """Vrai si le modèle a rendu un vide parce que son budget de SORTIE était épuisé."""
    return isinstance(exc, EmptyResponseError) and (
        exc.finish_reason == "length" or "budget de sortie" in str(exc)
    )


def _max_tokens_courant(client: providall.Client, exc: ProvidallError, defaut: int = 32_000) -> int:
    """Le budget de sortie qui vient d'être épuisé : celui du client, sinon celui
    que providall a écrit dans le message (« (32000 jetons) »), sinon `defaut`."""
    if client.max_tokens:
        return int(client.max_tokens)
    trouve = re.search(r"\((\d[\d\s\u202f]*) jetons\)", str(exc))
    if trouve:
        return int(re.sub(r"\D", "", trouve.group(1)))
    return defaut


def _sauvetage(conversation: list[Message], limites: Limites, journal: Journal) -> bool:
    """Élague en cas d'erreur, dans l'espoir que le contexte était simplement trop long.

    Tenté UNE seule fois par run (le compteur est dans la boucle), et seulement
    si l'élagage a réellement retiré quelque chose : réessayer en boucle sur une
    erreur d'authentification ferait tourner le run jusqu'au plafond de tours.
    """
    gagne = elaguer(conversation, limites.garder_sorties // 2)
    if not gagne:
        return False
    journal.evenement(f"sauvetage après erreur : {gagne} caractères élagués, nouvel essai")
    return True


__all__ = [
    "AVERTISSEMENT_BUDGET",
    "OUTILS_INELAGUABLES",
    "OUTILS_PROGRES",
    "TALON",
    "Arret",
    "Budget",
    "Journal",
    "JournalMuet",
    "Limites",
    "Resultat",
    "elaguer",
    "executer",
    "executer_appel",
    "tronquer",
]

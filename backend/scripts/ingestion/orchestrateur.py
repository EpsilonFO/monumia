"""Ingestion d'un lot d'aides : parallélisme, budget global, reprise.

Trois choses seulement, mais aucune n'est facultative à l'échelle de 1 400
aides :

  - **le jeton `en_cours`** : un slug est réservé par une transition atomique
    sous verrou avant d'être soumis. Deux orchestrateurs lancés en parallèle (ou
    un relancé sans avoir vu que le premier tournait encore) ne peuvent pas
    ingérer la même aide deux fois ;
  - **la soumission progressive** : on ne remplit la file que tant que le budget
    restant peut payer une aide de plus. Soumettre tout d'un coup ferait
    dépasser le plafond de la valeur de `parallele` aides ;
  - **la reprise** : un Ctrl-C rend leur statut `valide` aux aides en vol, et
    `--reprendre` fait de même pour les `en_cours` orphelines d'un run tué net.
    Sans ça, un plantage laisse des slugs bloqués que plus rien ne reprend.

Les ressources partagées entre workers sont exactement quatre, et chacune a sa
protection : `facts_pending.yaml` (verrou de fichier), `file-attente.yaml`
(verrou de fichier), `data/sources/<slug>/` (disjoints par construction) et le
cache `pdftotext` (idempotent, clé par sha256). Le `Fetcheur` ajoute son verrou
par hôte.
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.etat import (
    FILE_ATTENTE,
    MOTIF_SANS_YAML,
    Tache,
    charger,
    echecs_a_relire,
    mettre_a_jour,
    transition,
)
from pipeline.llm import Compteur

from .ontologie import RapportOntologie
from .ontologie import rendre as rendre_ontologie
from .worker import ConfigIngestion, ContextePartage, ResultatIngestion, ingerer_aide

PARALLELE_DEFAUT = 3
BUDGET_TOTAL_DEFAUT = 50.0


class Disjoncteur:
    """Coupe le run quand la panne est celle du FOURNISSEUR, pas celle d'une aide.

    Le 2026-09-18, le run a continué à lancer des aides pendant deux heures
    alors qu'OpenRouter renvoyait `Connection error` puis « credits épuisés » :
    351 tâches consommées à zéro dollar et à zéro octet, et la reprise
    n'existait pas. Aucun signal n'existait pour distinguer « cette aide-là est
    difficile » de « le fournisseur est à terre ».

    Deux salves, et l'asymétrie est volontaire : une première salve de quatre
    échecs transitoires d'affilée arrête tout pendant une minute, puis remet le
    compteur à zéro — une coupure de réseau d'une minute ne doit pas tuer un run
    de six heures. Une SECONDE salve après la pause n'est plus un accident, et
    le run s'arrête proprement, toutes les aides en vol et restantes rendues à
    `valide`.

    Un échec FATAL (clé invalide, modèle inconnu) coupe immédiatement, sans
    pause ni seuil : il n'y a rien à attendre.
    """

    def __init__(self, *, seuil: int = 4, pause_s: float = 60.0, dormir=None) -> None:
        self.seuil = seuil
        self.pause_s = pause_s
        self._dormir = dormir or time.sleep
        self.consecutifs = 0
        self.salves = 0
        self.motif = ""

    def succes(self) -> None:
        """Un verdict qui n'est pas une panne du fournisseur : le compteur repart."""
        self.consecutifs = 0

    def panne(self, resultat: ResultatIngestion) -> bool:
        """Enregistre un verdict. Rend True quand le run doit s'arrêter."""
        if resultat.echec_fatal:
            self.motif = (
                f"erreur fatale sur {resultat.slug} ({resultat.motif_echec}) — "
                "clé d'API ou configuration : rejouer n'y changerait rien."
            )
            return True
        if not resultat.echec_transitoire:
            self.succes()
            return False
        self.consecutifs += 1
        if self.consecutifs < self.seuil:
            return False
        self.salves += 1
        self.consecutifs = 0
        if self.salves == 1:
            print(
                f"\n⚠ {self.seuil} pannes de fournisseur d'affilée — pause de "
                f"{self.pause_s:.0f} s avant de reprendre. Les aides concernées sont "
                "rendues à `valide` et repartiront."
            )
            self._dormir(self.pause_s)
            return False
        self.motif = (
            f"réseau ou crédits : {self.seuil} pannes d'affilée pour la deuxième fois, "
            "après une pause. Vérifier le solde OpenRouter "
            "(https://openrouter.ai/credits) et la connectivité, puis relancer avec "
            "`ingerer.py --file-attente` — les aides non traitées sont en `valide`."
        )
        return True


def reprendre(etat_path: Path = FILE_ATTENTE) -> list[str]:
    """Rend `valide` aux aides restées `en_cours` d'un run interrompu.

    À n'appeler que si l'on sait qu'aucun autre orchestrateur ne tourne : le
    statut `en_cours` est précisément ce qui l'empêche de reprendre une aide
    déjà prise ailleurs.
    """
    liberes = []
    for slug, tache in charger(etat_path).items():
        if tache.statut == "en_cours" and transition(
            etat_path, slug, "valide", depuis=("en_cours",)
        ):
            liberes.append(slug)
    return liberes


def relancer_echecs(
    etat_path: Path = FILE_ATTENTE,
    *,
    territoires: Sequence[str] | None = None,
    seulement_sans_yaml: bool = False,
) -> list[str]:
    """Rend `valide` aux aides en `echec`, pour les rejouer — après un correctif du
    harnais, typiquement. Filtrable par territoire.

    `seulement_sans_yaml` ne relance que les tâches dont l'agent n'a rien écrit :
    c'est la forme qu'a prise la panne du 2026-09-18, et elle épargne les vrais
    refus, dont le YAML `.echec` est sur disque et attend une relecture.

    Le `<slug>.yaml.echec` est laissé en place : il contient le YAML que le
    modèle avait produit, ce qu'il y a de plus utile pour comprendre l'échec, et
    il vit hors du glob `*.yaml`. La relance écrira son propre `<slug>.yaml` à
    côté ; c'est à la relecture de trancher lequel garder.

    Les échecs de panne qui n'ont jamais passé le test du destinataire
    (`echecs_a_relire`) sont laissés de côté : `prospecter.py relire` les
    requalifie d'abord, sans quoi ils seraient ingérés sans aucun filtre.
    """
    relances = []
    etat = charger(etat_path)
    sans_lecture = set(echecs_a_relire(etat))
    for slug, tache in etat.items():
        if tache.statut != "echec" or slug in sans_lecture:
            continue
        if territoires and tache.territoire not in territoires:
            continue
        if seulement_sans_yaml:
            motif = (tache.ingestion.motif_echec if tache.ingestion else None) or ""
            if MOTIF_SANS_YAML not in motif:
                continue
        if transition(etat_path, slug, "valide", depuis=("echec",)):
            relances.append(slug)
    return relances


def executer(
    slugs: Sequence[str],
    config: ConfigIngestion,
    *,
    parallele: int = PARALLELE_DEFAUT,
    budget_total: float = BUDGET_TOTAL_DEFAUT,
    etat_path: Path = FILE_ATTENTE,
    compteur: Compteur | None = None,
    ingerer=ingerer_aide,
    disjoncteur: Disjoncteur | None = None,
) -> list[ResultatIngestion]:
    """Ingère les slugs donnés, dans la limite du budget. Renvoie leurs verdicts.

    `ingerer` est injectable pour les tests : c'est le seul point du module qui
    parle à un modèle, tout le reste est de l'ordonnancement.

    `disjoncteur` arrête le run quand la panne est celle du fournisseur : sans
    lui, un run continue à lancer des aides pendant deux heures sur un réseau
    mort ou un solde à zéro, et les consomme toutes à zéro dollar.
    """
    disjoncteur = disjoncteur if disjoncteur is not None else Disjoncteur()
    etat = charger(etat_path)
    manquants = [s for s in slugs if s not in etat]
    if manquants:
        raise KeyError(f"slug(s) absent(s) de la file d'attente : {', '.join(manquants)}")

    compteur = compteur or Compteur()
    contexte = ContextePartage.construire(config.atelier(slugs[0] if slugs else "reference"))
    arret = threading.Event()
    resultats: list[ResultatIngestion] = []
    differes: list[tuple[Tache, ResultatIngestion]] = []
    restants = list(slugs)
    en_vol: dict[Future[ResultatIngestion], str] = {}

    with _interception_sigint(arret), ThreadPoolExecutor(max_workers=parallele) as pool:
        while (restants or en_vol) and not arret.is_set():
            while restants and len(en_vol) < parallele and not arret.is_set():
                if _budget_epuise(compteur, config, budget_total):
                    print(
                        f"budget total atteint ({compteur.cout_usd:.2f} $ sur {budget_total:.2f}) — "
                        f"{len(restants)} aide(s) non lancée(s) : {', '.join(restants)}"
                    )
                    restants.clear()
                    break
                slug = restants.pop(0)
                if not transition(etat_path, slug, "en_cours", depuis=("valide",)):
                    print(f"  {slug} : déjà pris ou statut incompatible — ignoré")
                    continue
                print(f"  → {slug}")
                en_vol[
                    pool.submit(
                        ingerer, slug, etat[slug], config, contexte=contexte, compteur=compteur
                    )
                ] = slug
            if not en_vol:
                break
            termines, _ = wait(list(en_vol), return_when=FIRST_COMPLETED)
            for future in termines:
                slug = en_vol.pop(future)
                resultat = future.result()
                resultats.append(resultat)
                _consigner_ou_differer(etat_path, etat[slug], resultat, differes)
                print(
                    f"  ← {slug} : {'ok' if resultat.ok else 'ÉCHEC — ' + (resultat.motif_echec or '')}"
                )
                if disjoncteur.panne(resultat):
                    print(f"\n⛔ run arrêté — {disjoncteur.motif}")
                    arret.set()

        if arret.is_set():
            print("\ninterruption demandée — attente des aides en vol…")
            for future in list(en_vol):
                slug = en_vol[future]
                try:
                    resultat = future.result()
                except Exception:  # noqa: BLE001 — l'aide sera simplement relibérée
                    resultat = None
                if resultat is not None:
                    resultats.append(resultat)
                    _consigner_ou_differer(etat_path, etat[slug], resultat, differes)
                else:
                    transition(etat_path, slug, "valide", depuis=("en_cours",))
            for slug in restants:
                transition(etat_path, slug, "valide", depuis=("en_cours",))

    if differes:
        _reconsigner(etat_path, differes)
    return resultats


def _budget_epuise(compteur: Compteur, config: ConfigIngestion, budget_total: float) -> bool:
    """Vrai s'il ne reste pas de quoi payer une aide de plus.

    On raisonne sur ce qu'une aide peut coûter AU PIRE (`budget_aide`), pas sur
    ce qu'elle coûte en moyenne : un plafond qu'on ne franchit qu'« en général »
    n'est pas un plafond.
    """
    if compteur.cout_inconnu:
        # Sans tarif, le budget en dollars ne veut rien dire : c'est le budget
        # en jetons, par aide, qui borne la dépense.
        return False
    return compteur.cout_usd + config.limites.budget_usd > budget_total


#: Combien de fois une même aide peut mourir d'une panne transitoire avant
#: qu'on cesse de la rejouer. Trois, parce qu'une aide qui ne passe pas au bout
#: de trois coupures n'a probablement pas de problème de réseau.
MAX_TENTATIVES_TRANSITOIRES = 3


def _statut_final(tache: Tache, resultat: ResultatIngestion, tentatives: int) -> str:
    """`ingere`, `valide` (à rejouer) ou `echec` (à relire).

    Le statut `valide` pour un échec n'est pas une facilité : c'est la
    différence entre 351 tâches perdues et 351 tâches qui repartent au passage
    suivant. Une panne réseau ou un solde à zéro ne dit RIEN de l'aide, et la
    ranger en `echec` la met dans le même sac que les trois lints rouges et les
    deux `max_tours` qui, eux, demandent une décision humaine.

    Le plafond de tentatives garde le filet honnête : une aide qui échoue trois
    fois de suite « transitoirement » cache autre chose, et doit se voir.
    """
    # Un écart motivé par la SOURCE, pas un échec : la tâche est classée et ne
    # revient pas au balayage suivant. Testé avant `ok` parce que l'arrêt est
    # normal — `controler` ne rend aucun échec dans ce cas.
    if resultat.hors_perimetre is not None:
        return "ignore"
    if resultat.ok:
        return "ingere"
    if resultat.echec_transitoire and tentatives < MAX_TENTATIVES_TRANSITOIRES:
        return "valide"
    return "echec"


def _consigner(etat_path: Path, tache: Tache, resultat: ResultatIngestion) -> None:
    tentatives = (tache.ingestion.tentatives if tache.ingestion else 0) + 1
    mettre_a_jour(
        etat_path,
        resultat.slug,
        statut=_statut_final(tache, resultat, tentatives),
        a_relire=resultat.a_relire or tache.a_relire,
        **(
            {
                "categorie_ecart": resultat.hors_perimetre[0],
                "motif_ignore": f"hors périmètre à l'ingestion : {resultat.hors_perimetre[1]}",
            }
            if resultat.hors_perimetre
            else {}
        ),
        ingestion={
            "debut": resultat.debut,
            "fin": resultat.fin,
            "modele": resultat.modele,
            "modele_verif": resultat.modele_verif,
            "tours": resultat.tours,
            "cout_usd": None if resultat.cout_inconnu else round(resultat.cout_usd, 4),
            "review": resultat.review,
            "motif_echec": resultat.motif_echec,
            "tentatives": tentatives,
        },
    )


def _consigner_ou_differer(
    etat_path: Path,
    tache: Tache,
    resultat: ResultatIngestion,
    differes: list[tuple[Tache, ResultatIngestion]],
) -> None:
    """Consigne le verdict ; si la file d'attente s'y refuse, le garde pour la fin.

    Le 2026-09-13, un `git commit` lancé dans un autre terminal a fait repasser
    `file-attente.yaml` par sa version HEAD le temps des hooks de pre-commit
    (qui met de côté les modifications non indexées). `mettre_a_jour` a levé
    `KeyError` sur un slug que HEAD ne connaissait pas, la boucle principale est
    morte, et huit aides pourtant terminées sont restées `en_cours`. Le verdict
    d'une aide est ce qui a coûté le plus cher du run : on ne le perd pas parce
    que le fichier d'état était indisponible cinq secondes.
    """
    try:
        _consigner(etat_path, tache, resultat)
    except Exception as exc:  # noqa: BLE001 — la file est un fichier partagé, tout peut arriver
        differes.append((tache, resultat))
        print(
            f"  ⚠ {resultat.slug} : verdict non consigné ({type(exc).__name__}: {exc}) "
            "— nouvelle tentative en fin de run"
        )


def _reconsigner(etat_path: Path, differes: list[tuple[Tache, ResultatIngestion]]) -> None:
    """Retente les consignations différées ; dit clairement ce qui reste à faire à la main."""
    restes: list[str] = []
    for tache, resultat in differes:
        try:
            _consigner(etat_path, tache, resultat)
            print(f"  ✓ {resultat.slug} : verdict consigné au second essai")
        except Exception as exc:  # noqa: BLE001
            restes.append(
                f"{resultat.slug} ({'ok' if resultat.ok else 'échec'} ; {type(exc).__name__}: {exc})"
            )
    if restes:
        print(
            f"\n⚠ {len(restes)} verdict(s) impossibles à consigner — leurs fichiers (YAML, review, "
            "journal) sont bien sur disque, mais leur statut reste `en_cours` dans la file "
            "d'attente. Ne PAS relancer avec --reprendre (ce serait les ré-ingérer) : corriger "
            "le statut à la main d'après data/reviews/logs/ingest-<slug>.log."
        )
        for r in restes:
            print(f"  - {r}")


class _interception_sigint:
    """Transforme un Ctrl-C en demande d'arrêt propre, une seule fois.

    Un second Ctrl-C rétablit le comportement par défaut : si l'arrêt propre
    lui-même se coince, l'utilisateur doit pouvoir tuer le processus.
    """

    def __init__(self, drapeau: threading.Event) -> None:
        self.drapeau = drapeau
        self.precedent = None

    def __enter__(self) -> _interception_sigint:
        if threading.current_thread() is threading.main_thread():
            self.precedent = signal.signal(signal.SIGINT, self._gerer)
        return self

    def _gerer(self, *_args: object) -> None:
        self.drapeau.set()
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def __exit__(self, *_exc: object) -> None:
        if self.precedent is not None:
            signal.signal(signal.SIGINT, self.precedent)


def bilan(
    resultats: Sequence[ResultatIngestion],
    compteur: Compteur | None = None,
    *,
    sortie: Path | None = None,
    ontologie: RapportOntologie | None = None,
) -> str:
    """Le tableau de fin de run, et les commandes à lancer ensuite.

    `ontologie` est le rapport d'audit de fin de run, imprimé sous la section
    des faits proposés : un seul `print` en fin de run, donc un seul endroit à
    lire. Son coût N'EST PAS couvert par `--budget-total`, qui n'arbitre
    qu'avant le lancement d'une aide — le bilan le dit plutôt que de le taire.

    `cout_questions` d'une aide est la seule grandeur du bilan qu'on ne peut pas
    lire dans sa fiche : une question n'entre au tronc commun que si une AUTRE
    aide la partage déjà. Elle est mesurée par le worker, juste après les
    post-contrôles et avant toute mise en échec.

    `sortie` (le `--sortie` du banc d'essai) change TOUT ce qui suit le
    tableau : rien de ce qu'un run redirigé produit n'a vocation à être
    committé ni chargé en base, et le fait proposé n'est pas allé dans
    `data/facts_pending.yaml` mais dans la copie du banc. Le dire faux invitait
    à committer des fichiers qui ne sont pas là, et à chercher un fait dans un
    fichier qui ne l'a pas.
    """
    if not resultats:
        return "Aucune aide ingérée."
    largeur = max(len(r.slug) for r in resultats)
    lignes = [
        "",
        f"{'aide'.ljust(largeur)}  état    tours  coût      arrêt          motif",
        "-" * (largeur + 60),
    ]
    for r in sorted(resultats, key=lambda r: (r.ok, r.slug)):
        cout = "  ?    " if r.cout_inconnu else f"${r.cout_usd:6.3f}"
        lignes.append(
            f"{r.slug.ljust(largeur)}  {'ok  ' if r.ok else 'ÉCHEC'}  "
            f"{r.tours:>5}  {cout}  {r.arret:<13}  {(r.motif_echec or '')[:70]}"
        )
    ok = [r for r in resultats if r.ok]
    faits = sorted({f for r in resultats for f in r.faits_proposes})
    bloquants = sum(r.bloquants for r in resultats)
    lignes += [
        "",
        f"{len(ok)}/{len(resultats)} aide(s) ingérée(s). "
        + (compteur.resume() if compteur else ""),
        (
            f"{bloquants} problème(s) bloquant(s) que le vérificateur maintient sur les fichiers "
            "FINAUX — l'agent les a vus et a gardé sa version : ce sont des arbitrages, à relire "
            "dans la section « À trancher » des fiches."
            if bloquants
            else "0 problème bloquant sur les fichiers finaux."
        ),
    ]
    couteuses = [r for r in resultats if r.cout_questions]
    if couteuses:
        lignes += [
            "",
            "Coût en questions — ce que chaque aide ajoute au TRONC COMMUN, donc au "
            "questionnaire de tous les propriétaires du profil nommé (détail dans la review) :",
            *(f"  {r.slug} : {r.cout_questions}" for r in sorted(couteuses, key=lambda r: r.slug)),
        ]
    if faits:
        ou = f"{sortie}/facts_pending.yaml" if sortie else "data/facts_pending.yaml"
        suite = (
            " — copie du banc d'essai, le vrai `data/facts_pending.yaml` n'a pas bougé."
            if sortie
            else " — à approuver à la main (déplacer vers facts.yaml)."
        )
        lignes.append(f"{len(faits)} fait(s) proposé(s) dans {ou} : {', '.join(faits)}{suite}")
    if ontologie is not None:
        lignes.append(rendre_ontologie(ontologie))

    if not ok:
        return "\n".join(lignes)
    if sortie:
        lignes += [
            "",
            f"BANC D'ESSAI — rien n'a été écrit dans data/. Tout est sous {sortie} :",
            f"  aides {sortie}/aides/   reviews {sortie}/reviews/   journaux {sortie}/reviews/logs/",
            "",
            "  uv run python scripts/comparer_aides.py tableau "
            + " ".join(r.slug for r in ok)
            + f" --sortie {sortie}",
        ]
    else:
        lignes += [
            "",
            "À FAIRE À LA MAIN (le pipeline ne commite ni ne charge jamais) :",
            "  1. relire les fiches data/reviews/<date>-ingest-<slug>.md",
            "  2. cd backend && uv run python scripts/lint_aides_data.py",
            "  3. git add -p backend/data && git commit",
            "  4. cd backend && uv run python scripts/load_aides_yaml.py",
        ]
    return "\n".join(lignes)


__all__ = [
    "BUDGET_TOTAL_DEFAUT",
    "PARALLELE_DEFAUT",
    "relancer_echecs",
    "bilan",
    "executer",
    "reprendre",
]

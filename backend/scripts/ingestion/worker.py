"""Ingestion d'UNE aide, de bout en bout, avec ses post-contrôles.

La boucle d'agent ne juge rien : c'est ici que l'on décide si une ingestion est
acceptable, et la décision est entièrement DÉTERMINISTE. Aucun modèle n'a son
mot à dire sur la qualité de son propre travail — six contrôles, tous
vérifiables à la main :

  1. le YAML se charge et son slug est le bon ;
  2. `lint --quotes` sort vert (schéma, faits, opérateurs, ratchet, citations) ;
  3. la fiche de review existe et n'est pas un moignon ;
  4. au moins un snapshot est archivé, `source.snapshot` pointe dessus, et
     `verified_at` porte la date du jour ;
  5. l'agent s'est arrêté de lui-même (ni budget, ni plafond de tours) ;
  6. le vérificateur adversarial a été lancé.

Un échec ne détruit rien : le YAML est renommé `<slug>.yaml.echec` — hors du
glob `*.yaml`, donc invisible au lint, au moteur et au loader — tandis que les
snapshots, la review et le journal restent en place pour la relecture. C'est la
règle qui empêche le pire scénario : un fichier plausible mais faux qui entre
au catalogue parce que personne n'a regardé.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lint_aides_data import lint as lancer_lint
from pipeline.etat import Tache
from pipeline.llm import Compteur, client_pour
from pipeline.web import Fetcheur

from aides_schema import AIDES_DIR, FactDef, load_aide, load_facts, load_pending_facts
from labels import FAMILLES_LABELS

from .atelier import Atelier, atelier_redirige, atelier_standard
from .boucle import Journal, JournalMuet, Limites, Resultat, classe_erreur, executer
from .contexte import choisir_aide_reference, prompt_initial, prompt_systeme
from .faits import MAX_FAITS_PAR_AIDE
from .outils import MIN_CAR_REVIEW, EtatOutils, outils_pour


@dataclass
class ConfigIngestion:
    """Ce qui ne dépend pas du slug : modèles, bornes, dossier de sortie."""

    modele: str | None = None
    modele_verif: str | None = None
    limites: Limites = field(default_factory=Limites)
    sortie: Path | None = None
    jour: date = field(default_factory=date.today)
    # Journaliser sur disque. Faux en test, et pour un `--dry-run`.
    journaliser: bool = True
    # Fabrique du client HTTP. Injectable pour que les tests de bout en bout
    # tournent sans réseau : c'est le seul endroit du worker qui sorte de la
    # machine en dehors des appels au modèle.
    fetcheur: Callable[[], Fetcheur] = Fetcheur
    # Où chercher l'aide de RÉFÉRENCE servie en exemple de format. Toujours le
    # vrai catalogue, y compris au banc d'essai : un dossier de sortie est vide
    # au premier run, et le modèle y perdrait le gabarit dont il dispose en
    # production — le banc mesurerait alors une situation qui n'existe pas.
    reference_dir: Path = AIDES_DIR

    def atelier(self, slug: str) -> Atelier:
        if self.sortie is not None:
            return atelier_redirige(slug, self.sortie, jour=self.jour)
        return atelier_standard(slug, jour=self.jour)


@dataclass
class ContextePartage:
    """Le prompt système et l'ontologie, construits UNE fois pour tout le run.

    Le prompt système pèse ~23 000 jetons et ne dépend pas du slug : le
    reconstruire par aide coûterait le même temps CPU et, surtout, ferait
    varier le préfixe d'un appel à l'autre, ce qui casserait le cache de
    préfixe du fournisseur — le poste de dépense numéro un du pipeline.

    `pending` est PARTAGÉ et mutable : quand un worker propose un fait, les
    autres le voient via `chercher_faits` et évitent d'en proposer un quasi
    doublon. La cohérence du fichier, elle, ne dépend pas de ce dictionnaire —
    `faits.proposer` relit toujours le disque sous verrou.
    """

    systeme: str
    facts: dict[str, FactDef]
    pending: dict[str, FactDef]
    #: Les faits proposés AVANT le run. Ce qui s'y ajoute ensuite est le fait
    #: d'un worker de ce run, et c'est précisément ce que les autres doivent
    #: voir : l'index du prompt système est figé au démarrage, donc deux workers
    #: proposaient le même fait à la même minute sans jamais se croiser.
    pending_initial: frozenset[str] = frozenset()

    @classmethod
    def construire(cls, atelier: Atelier) -> ContextePartage:
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        facts = dict(load_facts(atelier.facts_path))
        pending = dict(load_pending_facts(atelier.pending_path))
        return cls(
            systeme=prompt_systeme(facts, pending),
            facts=facts,
            pending=pending,
            pending_initial=frozenset(pending),
        )

    def faits_du_run(self) -> tuple[str, ...]:
        """Les faits nés PENDANT ce run, à rappeler dans le message initial.

        Dans le message initial et non dans le système : celui-ci pèse
        ~23 000 jetons et sa stabilité fait tenir le cache de préfixe du
        fournisseur, le premier poste de dépense du pipeline. Une liste qui
        change à chaque aide l'invaliderait à chaque appel.
        """
        return tuple(sorted(set(self.pending) - self.pending_initial))


@dataclass
class ResultatIngestion:
    """Le verdict sur une aide, tel qu'il ira dans la file d'attente."""

    slug: str
    ok: bool
    arret: str
    tours: int
    cout_usd: float
    cout_inconnu: bool
    modele: str
    modele_verif: str
    debut: str
    fin: str
    motif_echec: str | None = None
    review: str | None = None
    faits_proposes: list[str] = field(default_factory=list)
    bloquants: int = 0
    controles_rates: list[str] = field(default_factory=list)
    #: « +N question(s) de tronc (profil) », vide si l'aide n'en fait entrer aucune.
    cout_questions: str = ""
    #: Une panne du fournisseur, qui n'a rien écrit et n'a rien coûté : la
    #: tâche redevient `valide` et repartira au prochain passage. C'est le
    #: 2026-09-18 qui l'impose — 351 tâches passées `echec` définitif pour une
    #: coupure réseau et un solde OpenRouter à zéro.
    echec_transitoire: bool = False
    #: Une clé invalide, un modèle inconnu : rejouer n'y changerait rien, et le
    #: run entier doit s'arrêter plutôt que de brûler 900 tâches sur la même
    #: erreur (55 `AuthError` dans les journaux du 2026-09-18).
    echec_fatal: bool = False
    #: Posé par `ecrire_review` quand la fiche a été écrite au plafond de
    #: vérifications, bloquants non re-vérifiés : c'est la liste de relecture.
    a_relire: bool = False
    #: (catégorie, motif) quand l'agent a écarté l'aide après lecture de sa
    #: source. La tâche passe `ignore` et ne revient plus.
    hors_perimetre: tuple[str, str] | None = None
    #: Ce que l'agent a fait des signaux de l'espace (`EtatOutils.mesures_espace`) :
    #: alertes de fait réutilisées ou maintenues, écarts de typage levés au lint.
    espace: dict[str, int] = field(default_factory=dict)
    #: Où le temps est passé, en secondes : `modele` (appels du modèle
    #: d'extraction), `outil <nom>` (dont `lint` et `verification_adversariale`).
    durees: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Coût en questions
# ---------------------------------------------------------------------------

#: Au-delà, l'aide fait entrer assez de questions dans le tronc d'un profil pour
#: que la fiche le dise en toutes lettres. Trois, parce qu'une aide légitime en
#: apporte une ou deux en réutilisant des faits existants — c'est ce qu'on lui
#: demande — et que la série de 2026-09 montre le décrochage à partir de trois.
SEUIL_ALERTE_QUESTIONS = 3


class CoutQuestions(NamedTuple):
    """Le bloc à appender à la review, et la ligne à mettre au bilan de run."""

    bloc: str
    resume: str


def cout_en_questions(atelier: Atelier) -> CoutQuestions:
    """Ce que l'aide coûte au questionnaire de TOUS les propriétaires.

    Invisible depuis la fiche de l'aide : une question n'entre au tronc commun
    que si une AUTRE aide la partage déjà. La relecture humaine ne peut donc pas
    la deviner, et c'est exactement le genre de coût qui s'accumule sans que
    personne ne le voie — 90 aides économiques du lot Grand Est ont ainsi ajouté
    dix questions au parcours d'une commune des Vosges.

    Le diagnostic coûte ~2 ms : mesurer les neuf profils deux fois est gratuit
    devant une ingestion. Ne fait JAMAIS échouer un run — toute exception rend
    une ligne « mesure indisponible », comme l'audit d'ontologie.
    """
    try:
        from profils_questionnaire import delta_tronc

        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        facts = {
            **load_facts(atelier.facts_path),
            **load_pending_facts(atelier.pending_path),
        }
        apres = {
            chemin.stem: load_aide(chemin) for chemin in sorted(atelier.aides_dir.glob("*.yaml"))
        }
        if atelier.slug not in apres:
            return CoutQuestions("", "")
        avant = {slug: aide for slug, aide in apres.items() if slug != atelier.slug}
        delta = delta_tronc(avant, apres, facts)
    except Exception as exc:  # noqa: BLE001 — une mesure ratée ne casse pas une ingestion
        return CoutQuestions(
            f"\n## Coût en questions (mesuré)\n\nmesure indisponible : {exc}\n",
            "coût en questions non mesuré",
        )

    lignes = [
        "",
        "## Coût en questions (mesuré)",
        "",
        "Questions du TRONC COMMUN (partagées par au moins deux aides) avant et après",
        "cette aide, par profil de référence. Une question qui entre ici est posée à",
        "tous les propriétaires de ce profil, pas seulement aux candidats de l'aide.",
        "",
        "| profil | tronc avant | après | questions entrantes |",
        "|---|---:|---:|---|",
    ]
    pire_nom, pire_n = "", 0
    for nom, (avant_n, apres_n, entrantes) in delta.items():
        if len(entrantes) > pire_n:
            pire_nom, pire_n = nom, len(entrantes)
        lignes.append(
            f"| {nom} | {avant_n} | {apres_n} | {', '.join(f'`{q}`' for q in entrantes) or '—'} |"
        )
    lignes.append("")
    if pire_n >= SEUIL_ALERTE_QUESTIONS:
        lignes += [
            f"⚠ **{pire_n} questions entrent dans le tronc du profil « {pire_nom} ».** Vérifier "
            "que l'aide porte bien son cadrage : `applies_if` de périmètre, "
            "`hard_filters.travaux`, `familles`, et le gate `statut_juridique_porteur` si elle "
            "vise un porteur particulier. Sans cadrage, ses questions sont posées à tout le "
            "monde.",
            "",
        ]
    resume = f"+{pire_n} question(s) de tronc ({pire_nom})" if pire_n else ""
    return CoutQuestions("\n".join(lignes), resume)


# ---------------------------------------------------------------------------
# Post-contrôles
# ---------------------------------------------------------------------------


def controler(atelier: Atelier, resultat: Resultat, etat: EtatOutils) -> list[str]:
    """La liste (vide si tout va bien) de ce qui interdit d'accepter l'ingestion.

    Un `declarer_hors_perimetre` n'en fait PAS partie : l'agent a lu la source,
    constaté qu'elle s'adresse à un tiers, écrit sa fiche et n'a produit aucun
    YAML. Le traiter comme « aucun fichier écrit » rangerait en `echec` une aide
    correctement écartée, et le balayage suivant la re-proposerait.
    """
    echecs: list[str] = []

    if etat.hors_perimetre is not None:
        if atelier.yaml_path.exists():
            return [
                "hors périmètre déclaré MAIS un YAML a été écrit — les deux se "
                "contredisent ; retirer le fichier ou retirer la déclaration"
            ]
        return []

    if not atelier.yaml_path.exists():
        return ["aucun fichier YAML écrit"]
    try:
        load_aide(atelier.yaml_path)
    except Exception as exc:
        return [f"YAML non chargeable : {exc}"]

    rapport = lancer_lint(
        [atelier.slug],
        quotes=True,
        aides_dir=atelier.aides_dir,
        facts_path=atelier.facts_path,
        pending_path=atelier.pending_path,
        faits_du_run=tuple(etat.faits_proposes),
        ecriture=True,
    )
    if not rapport.ok:
        echecs.append("lint rouge : " + " ; ".join(rapport.erreurs[:5]))

    if not atelier.review_path.exists():
        echecs.append("aucune fiche de review")
    elif len(atelier.review_path.read_text(encoding="utf-8").strip()) < MIN_CAR_REVIEW:
        echecs.append("fiche de review trop courte")

    if not atelier.snapshots():
        echecs.append("aucune source archivée")

    if resultat.arret != "termine":
        echecs.append(f"agent arrêté sur « {resultat.arret} » : {resultat.motif or 'sans motif'}")

    if etat.verification is None:
        echecs.append("vérification adversariale jamais lancée")

    # F1 — deux contrôles de SORTIE, tous deux mesurés sur le lot du 2026-09-18.
    #
    # Le plafond de faits est déjà opposé à l'écriture (`faits.proposer`) ; ce
    # second contrôle attrape le cas où l'agent a proposé sous le plafond puis
    # contourné, et surtout il rend le plafond visible dans le motif d'échec.
    if len(etat.faits_proposes) > MAX_FAITS_PAR_AIDE:
        echecs.append(
            f"{len(etat.faits_proposes)} faits neufs proposés ({MAX_FAITS_PAR_AIDE} au "
            f"maximum) : {', '.join(etat.faits_proposes)}"
        )

    # `familles` vide sur 114 aides du lot : elles sont visibles pour TOUT
    # projet, parce que le filtrage par famille est fail-open. La liste fermée
    # est assez large (13 valeurs, dont `adjacente`) pour qu'un vide soit une
    # omission et non un cas légitime.
    try:
        aide = load_aide(atelier.yaml_path)
    except Exception:  # noqa: BLE001 — déjà signalé plus haut
        aide = None
    if aide is not None and not aide.familles:
        echecs.append(
            "`familles` vide — fail-open : l'aide serait proposée pour tout projet. "
            f"Au moins une famille parmi {', '.join(sorted(FAMILLES_LABELS))}"
        )

    return echecs


def _mettre_en_echec(atelier: Atelier, motif: str) -> None:
    """Sort le YAML du catalogue sans l'effacer.

    Renommer plutôt que supprimer : le fichier est ce qu'il y a de plus utile
    pour comprendre ce que le modèle a compris de travers, et il se remet en
    place d'un `mv` si la relecture humaine le juge finalement bon.
    """
    if not atelier.yaml_path.exists():
        return
    cible = atelier.yaml_echec_path
    cible.write_text(
        f"# ÉCHEC D'INGESTION ({atelier.jour.isoformat()}) : {motif}\n"
        "# Fichier volontairement hors du glob *.yaml — ni le lint, ni le moteur,\n"
        "# ni le loader ne le voient. Le renommer en .yaml après relecture.\n"
        + atelier.yaml_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    atelier.yaml_path.unlink()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def ingerer_aide(
    slug: str,
    tache: Tache,
    config: ConfigIngestion,
    *,
    contexte: ContextePartage,
    compteur: Compteur | None = None,
) -> ResultatIngestion:
    """Ingère une aide et rend son verdict. Ne lève jamais : un plantage est un échec."""
    debut = datetime.now(UTC).isoformat(timespec="seconds")
    atelier = config.atelier(slug)
    atelier.preparer()
    compteur_local = Compteur()
    durees: dict[str, float] = {}
    modele = config.modele or "(défaut LLM_MODEL_INGESTION)"
    modele_verif = config.modele_verif or "(défaut LLM_MODEL_VERIFICATION)"

    journal: Journal = (
        Journal(
            atelier.log_path,
            entete=f"{slug} — {debut} — ingestion {modele} / vérification {modele_verif}",
        )
        if config.journaliser
        else JournalMuet()
    )

    try:
        client = client_pour("ingestion", config.modele)
        client_verif = client_pour("verification", config.modele_verif)
        fetcheur = config.fetcheur()

        def entete_review() -> str:
            cout = (
                "coût inconnu" if compteur_local.cout_inconnu else f"${compteur_local.cout_usd:.4f}"
            )
            return (
                f"<!-- Généré par scripts/ingerer.py le {atelier.jour.isoformat()} — "
                f"extraction {modele}, vérification {modele_verif}, "
                f"{compteur_local.appels} appel(s), {cout}. "
                f"Snapshots : {', '.join(p.name for p in atelier.snapshots()) or 'aucun'}. "
                "À RELIRE avant commit : ni le commit ni le chargement en base ne sont "
                "faits par le pipeline. -->"
            )

        outils, etat = outils_pour(
            atelier,
            facts=contexte.facts,
            pending=contexte.pending,
            fetcheur=fetcheur,
            client_verif=client_verif,
            journal=journal,
            compteur=compteur_local,
            entete_review=entete_review,
        )
        reference = choisir_aide_reference(slug, config.reference_dir)
        existante = (
            atelier.yaml_path.read_text(encoding="utf-8") if atelier.yaml_path.exists() else None
        )
        prompt = prompt_initial(
            slug=slug,
            url=tache.url,
            atelier=atelier,
            urls_pdf=tuple(tache.urls_pdf),
            territoire=tache.territoire,
            famille=tache.famille,
            beneficiaires=tache.beneficiaires,
            note=tache.note,
            departements=tuple(tache.departements),
            doublon_probable=tache.doublon_probable,
            source_unique_vulgarisation=tache.source_unique_vulgarisation,
            faits_du_run=contexte.faits_du_run(),
            existante=existante,
            aide_reference=reference[1] if reference else None,
        )
        resultat = executer(
            client,
            contexte.systeme,
            prompt,
            outils,
            limites=config.limites,
            journal=journal,
            compteur=compteur_local,
            review_ecrite=lambda: etat.review_ecrite,
            durees=durees,
        )
        fetcheur.close()

        echecs = controler(atelier, resultat, etat)
        # AVANT `_mettre_en_echec` : celui-ci renomme le YAML en `.yaml.echec`,
        # hors du glob que la mesure balaye. Après, on mesurerait le catalogue
        # sans l'aide qu'on vient d'ingérer.
        cout = cout_en_questions(atelier) if atelier.review_path.exists() else CoutQuestions("", "")
        if cout.bloc:
            with atelier.review_path.open("a", encoding="utf-8") as fichier:
                fichier.write(cout.bloc)
        # Calculés AVANT `_mettre_en_echec`, qui renomme le YAML : le critère
        # porte sur « aucun fichier n'a été écrit », et après le renommage la
        # distinction serait perdue.
        aide_ecrite = atelier.yaml_path.exists()
        transitoire = (
            resultat.arret == "erreur_modele"
            and resultat.classe_erreur == "transitoire"
            and not aide_ecrite
        )
        fatal = resultat.classe_erreur == "fatal"
        if echecs:
            _mettre_en_echec(atelier, " ; ".join(echecs))
            journal.evenement("ÉCHEC : " + " ; ".join(echecs))
        else:
            journal.evenement(
                f"OK — {resultat.tours} tour(s), {compteur_local.resume()}. "
                "Relire la review, puis committer et charger à la main."
            )

        bloquants = len(etat.verification.bloquants) if etat.verification else 0
        return ResultatIngestion(
            slug=slug,
            ok=not echecs,
            arret=resultat.arret,
            tours=resultat.tours,
            cout_usd=compteur_local.cout_usd,
            cout_inconnu=compteur_local.cout_inconnu,
            modele=modele,
            modele_verif=modele_verif,
            debut=debut,
            fin=datetime.now(UTC).isoformat(timespec="seconds"),
            motif_echec=" ; ".join(echecs) or None,
            review=atelier.relatif(atelier.review_path) if atelier.review_path.exists() else None,
            faits_proposes=list(etat.faits_proposes),
            bloquants=bloquants,
            controles_rates=echecs,
            cout_questions=cout.resume,
            echec_transitoire=transitoire,
            echec_fatal=fatal,
            a_relire=etat.a_relire,
            espace=etat.mesures_espace(
                atelier.yaml_path.read_text(encoding="utf-8")
                if atelier.yaml_path.exists()
                else None
            ),
            durees={k: round(v, 1) for k, v in durees.items()},
            hors_perimetre=(
                (etat.hors_perimetre.categorie, etat.hors_perimetre.motif)
                if etat.hors_perimetre
                else None
            ),
        )
    except Exception as exc:  # noqa: BLE001 — un worker ne fait jamais tomber le run
        journal.evenement("EXCEPTION : " + traceback.format_exc())
        # Une panne réseau peut aussi frapper HORS de la boucle d'agent — au
        # chargement du contexte, au snapshot d'une source. Le verdict est le
        # même : la tâche n'a rien écrit, elle repartira.
        classe = classe_erreur(exc)
        aide_ecrite = atelier.yaml_path.exists()
        _mettre_en_echec(atelier, f"exception : {exc}")
        return ResultatIngestion(
            slug=slug,
            ok=False,
            arret="erreur_modele",
            tours=0,
            cout_usd=compteur_local.cout_usd,
            cout_inconnu=compteur_local.cout_inconnu,
            modele=modele,
            modele_verif=modele_verif,
            debut=debut,
            fin=datetime.now(UTC).isoformat(timespec="seconds"),
            motif_echec=f"{type(exc).__name__}: {exc}",
            echec_transitoire=classe == "transitoire" and not aide_ecrite,
            echec_fatal=classe == "fatal",
        )
    finally:
        if compteur is not None:
            compteur.fusionner(compteur_local, f"aide:{slug}")
        journal.close()


__all__ = [
    "ConfigIngestion",
    "ContextePartage",
    "ResultatIngestion",
    "controler",
    "ingerer_aide",
]

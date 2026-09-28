"""
Ingestion d'aides par un agent LLM — le skill `/ingest-aide`, payé à l'API.

Deux modes :

    # une aide, tout de suite (escalade de veille, banc d'essai, test)
    uv run python scripts/ingerer.py --slug hdf-jardins-en-scene \\
        --url https://guide-aides.hautsdefrance.fr/dispositif748

    # le lot validé de la file d'attente (sortie de la prospection)
    uv run python scripts/ingerer.py --file-attente --territoire hauts-de-france \\
        --parallele 2 --budget-total 5

Ce que la commande NE FAIT JAMAIS, quel que soit son verdict : `git add`, un
commit, `load_aides_yaml.py`. Elle écrit des fichiers dans le working tree et
imprime, à la fin, les commandes qui restent à lancer à la main.

Réglage des modèles, par rôle, dans `backend/.env` :

    LLM_MODEL_INGESTION=glm-flash
    LLM_MODEL_VERIFICATION=ds-pro

`--model` et `--model-verif` l'emportent sur l'environnement. Si le tarif du
modèle est absent du registre providall, `cost_usd` vaut None : passer
`--tarif <entrée>,<sortie>` (en $/M jetons) pour que le budget en dollars
fonctionne, sinon le budget bascule automatiquement sur les jetons d'entrée.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion import ontologie, orchestrateur
from ingestion.boucle import Limites
from ingestion.contexte import apercu, estimer_jetons
from ingestion.worker import ConfigIngestion, ContextePartage, ingerer_aide
from pipeline.etat import FILE_ATTENTE, Tache, charger, echecs_a_relire, selectionner
from pipeline.llm import (
    Compteur,
    charger_env,
    client_pour,
    enregistrer_tarif,
    parse_tarif,
    resolution_pour,
)

from aides_schema import AIDES_DIR, load_aide, load_facts, load_pending_facts


def construire_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ingerer.py",
        description="Ingère une aide (ou un lot) depuis ses sources officielles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_argument_group("mode")
    mode.add_argument("--slug", action="append", default=[], help="slug à ingérer")
    mode.add_argument("--url", action="append", default=[], help="source principale (mode --slug)")
    mode.add_argument("--pdf", action="append", default=[], help="document à snapshoter en plus")
    mode.add_argument(
        "--file-attente",
        action="store_true",
        help="ingérer les aides `valide` de data/prospection/file-attente.yaml",
    )
    mode.add_argument("--territoire", action="append", default=[], help="filtrer la file d'attente")
    mode.add_argument(
        "--reprendre",
        action="store_true",
        help="relibérer les aides restées `en_cours` d'un run interrompu",
    )
    mode.add_argument(
        "--relancer-echecs",
        action="store_true",
        help="remettre en `valide` les aides en `echec` (du territoire donné, sinon toutes) "
        "pour les rejouer dans ce run",
    )

    p.add_argument(
        "--seulement-sans-yaml",
        action="store_true",
        help="avec --relancer-echecs : ne relancer que les échecs « aucun fichier YAML "
        "écrit » (une panne du fournisseur), et épargner les vrais refus dont le "
        "`.yaml.echec` attend une relecture",
    )

    reglages = p.add_argument_group("réglages")
    reglages.add_argument(
        "--parallele",
        type=int,
        default=orchestrateur.PARALLELE_DEFAUT,
        help=f"aides ingérées en même temps (défaut : {orchestrateur.PARALLELE_DEFAUT})",
    )
    reglages.add_argument(
        "--budget-aide",
        type=float,
        default=Limites.budget_usd,
        help=f"plafond en $ par aide, arrêt dur à ×{Limites.facteur_arret_dur} "
        f"(défaut : {Limites.budget_usd:.2f})",
    )
    reglages.add_argument(
        "--budget-total",
        type=float,
        default=orchestrateur.BUDGET_TOTAL_DEFAUT,
        help=f"plafond en $ pour tout le run (défaut : {orchestrateur.BUDGET_TOTAL_DEFAUT:.0f})",
    )
    reglages.add_argument(
        "--max-tours",
        type=int,
        default=Limites.max_tours,
        help=f"tours d'agent par aide (défaut : {Limites.max_tours})",
    )
    reglages.add_argument("--model", help="modèle d'extraction (défaut : LLM_MODEL_INGESTION)")
    reglages.add_argument(
        "--model-verif", help="modèle de vérification (défaut : LLM_MODEL_VERIFICATION)"
    )
    reglages.add_argument(
        "--model-audit",
        help="modèle de l'audit d'ontologie de fin de run (défaut : LLM_MODEL_AUDIT)",
    )
    reglages.add_argument(
        "--tarif", help="tarif $/M jetons du modèle d'extraction, « entrée,sortie »"
    )
    reglages.add_argument(
        "--sortie", type=Path, help="écrire dans ce dossier au lieu de data/ (banc d'essai)"
    )
    reglages.add_argument(
        "--sans-audit",
        action="store_true",
        help="sauter l'audit d'ontologie de fin de run (un appel, hors --budget-total)",
    )
    reglages.add_argument("--etat", type=Path, default=FILE_ATTENTE, help=argparse.SUPPRESS)
    reglages.add_argument(
        "--dry-run",
        action="store_true",
        help="afficher le prompt système, sa taille et les aides retenues, sans rien appeler",
    )
    return p


def _url_du_yaml(slug: str) -> str | None:
    """`source.url_officielle` d'une aide déjà au catalogue, ou None.

    C'est ce qui rend `ingerer.py --slug <slug>` suffisant pour une
    RÉ-EXTRACTION : le skill dit « sinon `source.url_officielle` du YAML
    existant », et c'est exactement le cas de l'escalade de veille, qui connaît
    des slugs mais pas leurs URL.
    """
    chemin = AIDES_DIR / f"{slug}.yaml"
    if not chemin.exists():
        return None
    try:
        return load_aide(chemin).source.url_officielle
    except Exception:
        return None


def _taches_directes(args: argparse.Namespace) -> dict[str, Tache]:
    """Les tâches du mode `--slug/--url`, construites sans passer par la file.

    Volontairement hors file d'attente : ce mode sert aux escalades de veille et
    au banc d'essai, où enregistrer un statut n'aurait aucun sens et polluerait
    un fichier versionné.
    """
    if args.url and len(args.url) not in (1, len(args.slug)):
        raise SystemExit(
            "--url : en donner une seule (partagée) ou autant que de --slug, "
            f"reçu {len(args.url)} url(s) pour {len(args.slug)} slug(s)"
        )
    if args.url:
        urls: list[str | None] = list(args.url * len(args.slug) if len(args.url) == 1 else args.url)
    else:
        urls = [_url_du_yaml(slug) for slug in args.slug]

    taches: dict[str, Tache] = {}
    for slug, url in zip(args.slug, urls, strict=True):
        if not url:
            raise SystemExit(
                f"« {slug} » : aucune URL. Passer --url, ou ingérer une aide déjà au "
                "catalogue (son `source.url_officielle` sert alors de source)."
            )
        taches[slug] = Tache(
            titre=slug,
            url=url,
            urls_pdf=list(args.pdf),
            territoire="(hors file)",
            statut="valide",
            ajoute_le=date.today(),
        )
    return taches


def main(argv: list[str] | None = None) -> int:
    args = construire_parser().parse_args(argv)
    charger_env()

    if args.tarif:
        if not args.model:
            raise SystemExit("--tarif exige --model (le tarif s'applique à un modèle nommé)")
        entree, sortie = parse_tarif(args.tarif)
        spec = enregistrer_tarif(args.model, entree, sortie)
        print(f"tarif posé : {spec.alias} = {entree} / {sortie} $ par million de jetons")

    if args.reprendre:
        liberes = orchestrateur.reprendre(args.etat)
        print(
            f"reprise : {len(liberes)} aide(s) relibérée(s){': ' + ', '.join(liberes) if liberes else ''}"
        )

    if args.relancer_echecs:
        relances = orchestrateur.relancer_echecs(
            args.etat,
            territoires=args.territoire or None,
            seulement_sans_yaml=args.seulement_sans_yaml,
        )
        cadre = " (sans YAML écrit seulement)" if args.seulement_sans_yaml else ""
        print(
            f"relance des échecs{cadre} : {len(relances)} aide(s) remise(s) en `valide`"
            f"{': ' + ', '.join(relances) if relances else ''}"
        )
        a_relire = echecs_a_relire(charger(args.etat))
        if a_relire:
            print(
                f"  {len(a_relire)} échec(s) de panne laissé(s) de côté : lus avant le test "
                "du destinataire, ils repassent d'abord par "
                "`prospecter.py relire` (ou `balayage.py --rattraper-echecs`)."
            )

    config = ConfigIngestion(
        modele=args.model,
        modele_verif=args.model_verif,
        limites=Limites(
            max_tours=args.max_tours,
            budget_usd=args.budget_aide,
        ),
        sortie=args.sortie,
        jour=date.today(),
        journaliser=not args.dry_run,
    )

    if args.file_attente:
        etat = charger(args.etat)
        slugs = selectionner(etat, territoires=args.territoire or None, slugs=args.slug or None)
        taches = {s: etat[s] for s in slugs}
    elif args.slug:
        taches = _taches_directes(args)
        slugs = list(taches)
    else:
        construire_parser().print_help()
        return 2

    if not slugs:
        print("Aucune aide à ingérer (file d'attente vide, ou aucune au statut `valide`).")
        print("Valider des candidates : uv run python scripts/prospecter.py valider <territoire>")
        return 0

    _banniere(args, config, slugs, taches)
    if args.dry_run:
        return 0

    compteur = Compteur()
    disjoncteur = orchestrateur.Disjoncteur()
    if args.file_attente:
        resultats = orchestrateur.executer(
            slugs,
            config,
            parallele=args.parallele,
            budget_total=args.budget_total,
            etat_path=args.etat,
            compteur=compteur,
            disjoncteur=disjoncteur,
        )
    else:
        contexte = ContextePartage.construire(config.atelier(slugs[0]))
        resultats = [
            ingerer_aide(slug, taches[slug], config, contexte=contexte, compteur=compteur)
            for slug in slugs
        ]

    print(
        orchestrateur.bilan(
            resultats,
            compteur,
            sortie=args.sortie,
            ontologie=_auditer_ontologie(args, config, slugs[0], compteur),
        )
    )
    if disjoncteur.motif:
        # Code 3 et non 1 : `balayage.py` et l'utilisateur doivent distinguer
        # « des aides ont échoué » (on relit les fiches) de « le fournisseur
        # est à terre » (on vérifie le solde, puis on relance le même run).
        print(f"\n⛔ {disjoncteur.motif}")
        return 3
    return 0 if all(r.ok for r in resultats) else 1


def _auditer_ontologie(
    args: argparse.Namespace,
    config: ConfigIngestion,
    slug: str,
    compteur: Compteur,
) -> ontologie.RapportOntologie | None:
    """L'audit de fin de run, ou None s'il est désactivé.

    Appelé depuis `main()` et non depuis `orchestrateur.executer` : le mode
    direct `--slug` ne passe pas par `executer`, et l'audit doit couvrir les
    deux. L'ontologie est RELUE depuis le disque plutôt que reprise du
    `ContextePartage` — les faits proposés par le run viennent d'y être écrits,
    et c'est eux qu'il s'agit d'auditer.

    L'atelier est celui du run : au banc d'essai, `pending_path` est la copie
    sous `--sortie` et non `data/facts_pending.yaml`.

    Rien de ce qui se passe ici ne peut faire échouer le run. L'audit arrive
    APRÈS l'ingestion — les YAML sont écrits, les fiches de review aussi — et il
    ne modifie aucun fichier : perdre une ingestion de 130 aides parce que
    `LLM_MODEL_AUDIT` désigne un alias inconnu serait absurde. `auditer` ne lève
    déjà jamais ; ce `try` couvre ce qui l'entoure (résolution du modèle,
    lecture de l'ontologie).
    """
    try:
        atelier = config.atelier(slug)
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        facts = load_facts(atelier.facts_path)
        pending = load_pending_facts(atelier.pending_path)
        if not pending:
            return None
        client = None if args.sans_audit else client_pour("audit", args.model_audit)
        return ontologie.auditer(atelier, facts, pending, client, compteur=compteur)
    except Exception as exc:  # noqa: BLE001 — un audit raté ne casse pas un run réussi
        return ontologie.RapportOntologie(degrade=f"audit d'ontologie impossible : {exc}")


def _banniere(
    args: argparse.Namespace,
    config: ConfigIngestion,
    slugs: list[str],
    taches: dict[str, Tache],
) -> None:
    ingestion = resolution_pour("ingestion", args.model)
    verification = resolution_pour("verification", args.model_verif)
    print(f"extraction   : {ingestion.spec.alias} ({ingestion.source})")
    print(f"vérification : {verification.spec.alias} ({verification.source})")
    if not ingestion.spec.price_known:
        plafond = f"{config.limites.budget_tokens_entree:,}".replace(",", " ")
        print(
            "  ⚠ tarif inconnu pour ce modèle : le budget par aide sera compté en jetons "
            f"d'entrée ({plafond} max). Poser --tarif entrée,sortie pour un budget en dollars."
        )
    print(
        f"budget       : ${config.limites.budget_usd:.2f} par aide, "
        f"${args.budget_total:.2f} au total, {config.limites.max_tours} tours max"
    )
    if config.sortie:
        print(f"sortie       : {config.sortie} (banc d'essai — data/ n'est pas touché)")
    print(f"\n{len(slugs)} aide(s) :")
    for slug in slugs:
        t = taches[slug]
        print(f"  {slug:<44} {t.priorite:<8} {apercu(t.url, 70)}")

    if args.dry_run:
        contexte = ContextePartage.construire(config.atelier(slugs[0]))
        print(
            f"\nprompt système : {len(contexte.systeme)} caractères, "
            f"≈ {estimer_jetons(contexte.systeme)} jetons\n"
        )
        print(contexte.systeme)


if __name__ == "__main__":
    sys.exit(main())

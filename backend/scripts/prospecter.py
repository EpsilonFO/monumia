"""
Prospection des guides d'aides territoriaux — le skill `/prospecter-aides-region`,
payé à l'API.

    # TOUT d'un coup : collecte, tri, lecture, puis un agent d'ingestion par aide
    uv run python scripts/prospecter.py normandie --auto --parallele 5

    # balayer un territoire, écrire la fiche, poser les candidates en `a_valider`
    uv run python scripts/prospecter.py hauts-de-france
    uv run python scripts/prospecter.py --regions          # les 13 régions
    uv run python scripts/prospecter.py --departements     # ceux qui ont un guide

    # le point de contrôle humain
    uv run python scripts/prospecter.py etat hauts-de-france
    uv run python scripts/prospecter.py valider hauts-de-france --tout
    uv run python scripts/prospecter.py ignorer hauts-de-france hdf-truc hdf-machin

    # puis l'ingestion prend le relais
    uv run python scripts/ingerer.py --file-attente --territoire hauts-de-france

    # départements sans point d'entrée : proposer une URL de guide à coller
    uv run python scripts/prospecter.py deviner-sites 44 49 85

    # repasser par la lecture les échecs de panne lus avant le test du destinataire
    uv run python scripts/prospecter.py relire --dry-run

    # confronter une liste d'URL externe à ce qu'on a (et dire pourquoi ça manque)
    uv run python scripts/prospecter.py comparer grand-est /tmp/urls-du-collegue.txt

Trois étages : `collecte` (aucun modèle, sauf sur un site inconnu), `tri` (par
lots de 25, sur le titre seul), `lecture` (les retenues et les douteuses sont
ouvertes et qualifiées). Les intermédiaires sont écrits en `.jsonl` sous
`data/prospection/<territoire>/` et `--rejouer` repart de là sans réseau.

Ce que la commande ne fait JAMAIS : écrire dans `data/aides/`, committer,
charger en base. Elle produit une fiche de review et une file d'attente.
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion import orchestrateur
from ingestion.boucle import Limites
from pipeline.decision import ClientDecision, ErreurDecision
from pipeline.etat import (
    FILE_ATTENTE,
    PROSPECTION_DIR,
    charger,
    mettre_a_jour,
    motif_non_promotion,
    promouvables,
)
from pipeline.etat import fusionner as fusionner_etat
from pipeline.llm import Compteur, charger_env, client_pour, resolution_pour
from pipeline.web import Fetcheur
from prospection import collecte as collecte_mod
from prospection import fiche as fiche_mod
from prospection import lecture as lecture_mod
from prospection import requalification
from prospection import tri as tri_mod
from prospection.annuaire import sites_departementaux
from prospection.territoires import (
    TERRITOIRES_FILE,
    Territoire,
    charger_territoires,
    selectionner,
)

from aides_schema import load_all_aides

REVIEWS_DIR = Path(__file__).resolve().parent.parent / "data" / "reviews"


# ---------------------------------------------------------------------------
# Balayage
# ---------------------------------------------------------------------------


def dossier_travail(cle: str) -> Path:
    return PROSPECTION_DIR / cle


def _court(url: str, n: int = 64) -> str:
    return url if len(url) <= n else url[: n - 1] + "…"


def _progression_tri(i: int, n: int, tries: list[tri_mod.TriCandidat]) -> None:
    retenus = sum(1 for t in tries if t.decision == "retenir")
    douteux = sum(1 for t in tries if t.decision == "douteux")
    requalifies = sum(1 for t in tries if t.motif.startswith(tri_mod.MOTIF_SANS_TITRE))
    dont = f" dont {requalifies} requalifiée(s)" if requalifies else ""
    print(
        f"    [2/3] lot {i}/{n} : {retenus} retenue(s), {douteux} douteuse(s){dont}",
        flush=True,
    )


def arbitre_pour(args: argparse.Namespace) -> ClientDecision | None:
    """Jev pour la lecture (`prospection/arbitre.py`), sauf `--sans-jev` ou sans clé.

    Une clé absente n'arrête pas le balayage : la lecture retombe sur le LLM
    seul, comme avant Jev, et le dit.
    """
    if getattr(args, "sans_jev", False):
        return None
    try:
        return ClientDecision()
    except ErreurDecision as exc:
        print(f"    Jev indisponible ({exc}) : lecture par le LLM seul", flush=True)
        return None


def _verdict(le: lecture_mod.Lecture) -> str:
    if le.erreur:
        return "ERREUR "
    verdict = "retenue" if le.retenue else "à trancher" if le.indeterminee else "écartée"
    if le.arbitrage is not None:
        suite = {"retenue": ", corrigée", "renvoyee": ", renvoyée"}.get(le.correction or "", "")
        sans_llm = ", sans lecture" if le.arbitrage.bande == "ecartee" else ""
        verdict += f" ({le.arbitrage.resume()}{sans_llm}{suite})"
    return verdict


def prospecter(
    cle: str,
    territoire: Territoire,
    args: argparse.Namespace,
    compteur: Compteur,
) -> str | None:
    """Balaye un territoire de bout en bout. Renvoie le chemin de la fiche écrite."""
    jour = date.today()
    travail = dossier_travail(cle)
    travail.mkdir(parents=True, exist_ok=True)
    corpus = load_all_aides()
    from prospection.territoires import aides_existantes

    existantes = aides_existantes(cle, territoire, corpus)
    print(f"\n=== {territoire.nom} ({cle}) — {territoire.strategie.type}, {territoire.statut}")
    print(f"    {len(existantes)} aide(s) déjà au catalogue")

    fetcheur = Fetcheur(entetes=territoire.entetes)
    try:
        # --- étage 1 : collecte
        chemin_candidats = travail / "candidats.jsonl"
        if args.rejouer and chemin_candidats.exists():
            candidats = collecte_mod.Collecte.lire(chemin_candidats)
            collecte = collecte_mod.Collecte(
                candidats=candidats, notes=["rejoué depuis candidats.jsonl"]
            )
            print(f"    [1/3] rejoué : {len(candidats)} candidat(s)")
        else:
            collecte = collecte_mod.collecter(
                territoire,
                fetcheur,
                corpus,
                # La file compte autant que le corpus : une URL déjà `ignore`
                # reviendrait sinon sous un slug suffixé, à chaque passage.
                file=charger(args.etat),
                client_decouverte=client_pour("decouverte", args.model_decouverte),
                compteur=compteur,
            )
            collecte.ecrire(chemin_candidats)
            print(f"    [1/3] {len(collecte.candidats)} candidat(s) à trier")
        if args.etape == 1:
            return None
        if not collecte.candidats:
            print("    rien à trier — voir les notes techniques de la fiche")

        # --- étage 2 : tri
        chemin_tri = travail / "tri.jsonl"
        if args.rejouer and chemin_tri.exists():
            tries = [
                tri_mod.TriCandidat.model_validate_json(li)
                for li in chemin_tri.read_text(encoding="utf-8").splitlines()
                if li.strip()
            ]
        else:
            tries = tri_mod.trier(
                collecte.candidats,
                territoire,
                existantes,
                client_pour("tri", args.model_tri),
                compteur=compteur,
                progression=_progression_tri,
            )
            chemin_tri.write_text(
                "".join(t.model_dump_json() + "\n" for t in tries), encoding="utf-8"
            )
        retenus = sum(1 for t in tries if t.decision == "retenir")
        douteux = sum(1 for t in tries if t.decision == "douteux")
        print(
            f"    [2/3] {retenus} retenue(s), {douteux} douteuse(s), "
            f"{len(tries) - retenus - douteux} écartée(s)"
        )
        if args.etape == 2:
            return None

        # --- étage 3 : lecture
        a_ouvrir = set(tri_mod.a_lire(tries))
        client_lecture = client_pour("lecture", args.model_lecture)
        arbitre = arbitre_pour(args)
        a_lire = [c for c in collecte.candidats if c.url in a_ouvrir]
        print(f"    [3/3] {len(a_lire)} page(s) à lire, une par une", flush=True)
        lectures: list[lecture_mod.Lecture] = []
        debut = time.monotonic()
        try:
            for i, c in enumerate(a_lire, 1):
                le = lecture_mod.lire(
                    c, territoire, fetcheur, client_lecture, compteur=compteur, arbitre=arbitre
                )
                lectures.append(le)
                print(
                    f"    [3/3] {i:>3}/{len(a_lire)} {_verdict(le)}  {_court(c.url)}"
                    f"  ({time.monotonic() - debut:.0f} s)",
                    flush=True,
                )
        finally:
            if arbitre is not None:
                arbitre.fermer()
        (travail / "lectures.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "url": le.candidat.url,
                        "erreur": le.erreur,
                        "fiche": le.fiche.model_dump() if le.fiche else None,
                        "arbitrage": le.arbitrage.en_dict() if le.arbitrage else None,
                        "correction": le.correction,
                    },
                    ensure_ascii=False,
                )
                + "\n"
                for le in lectures
            ),
            encoding="utf-8",
        )
        gardees = [le for le in lectures if le.retenue]
        print(f"    [3/3] {len(gardees)} fiche(s) retenue(s) sur {len(lectures)} lue(s)")
    finally:
        fetcheur.close()

    # --- fiche et file d'attente
    occupes = set(corpus) | set(charger(args.etat))
    slugs = fiche_mod.attribuer_slugs(territoire, lectures, occupes)
    chemin_fiche = REVIEWS_DIR / f"{jour.isoformat()}-prospection-{cle}.md"
    relatif = str(chemin_fiche.relative_to(REVIEWS_DIR.parent.parent))
    chemin_fiche.parent.mkdir(parents=True, exist_ok=True)
    chemin_fiche.write_text(
        fiche_mod.rendre_fiche(
            cle,
            territoire,
            lectures,
            tries,
            collecte,
            existantes,
            slugs,
            jour=jour,
            cout=compteur.resume(),
        ),
        encoding="utf-8",
    )
    nouvelles = fiche_mod.taches(cle, territoire, lectures, slugs, relatif, jour=jour)
    ajoutes = fusionner_etat(args.etat, nouvelles)
    print(f"    fiche : {relatif}")
    print(f"    file d'attente : {len(ajoutes)} nouvelle(s) candidate(s) en `a_valider`")
    return relatif


# ---------------------------------------------------------------------------
# Sous-commandes
# ---------------------------------------------------------------------------


def cmd_etat(args: argparse.Namespace) -> int:
    etat = charger(args.etat)
    if args.territoire:
        etat = {s: t for s, t in etat.items() if t.territoire == args.territoire}
    if not etat:
        print("File d'attente vide.")
        return 0
    largeur = max(len(s) for s in etat)
    par_statut: dict[str, int] = {}
    for slug, tache in sorted(etat.items()):
        par_statut[tache.statut] = par_statut.get(tache.statut, 0) + 1
        print(f"{slug.ljust(largeur)}  {tache.statut:<10} {tache.territoire:<26} {tache.url}")
    print("\n" + ", ".join(f"{n} {s}" for s, n in sorted(par_statut.items())))
    return 0


# Statuts sur lesquels une transition manuelle a le droit de porter. `--tout`
# ne touche QUE `a_valider` : reprendre en bloc ce qu'on vient d'écarter n'a
# aucun sens. Nommer un slug est en revanche un geste délibéré, et doit pouvoir
# revenir sur un `ignorer` — sinon la seule issue est d'éditer le YAML à la
# main, ce qui s'est présenté dès le premier territoire (2026-09-09).
DEPUIS_NOMME: tuple[str, ...] = ("a_valider", "ignore", "valide")
DEPUIS_TOUT: tuple[str, ...] = ("a_valider",)


def _lister_restantes(etat: dict, territoire: str) -> int:
    """`valider <territoire>` sans slug : ce qui attend, et pourquoi.

    C'est le point de contrôle humain rendu praticable. Une liste de 140 slugs
    sans motif ne se relit pas ; avec le motif en face, l'arbitrage se fait à
    l'œil.
    """
    restantes = {
        slug: motif_non_promotion(t)
        for slug, t in sorted(etat.items())
        if t.territoire == territoire and t.statut == "a_valider"
    }
    if not restantes:
        print(f"Aucune candidate `a_valider` pour {territoire}.")
        return 0
    pretes = [s for s, m in restantes.items() if m is None]
    largeur = max(len(s) for s in restantes)
    print(f"{len(restantes)} candidate(s) `a_valider` pour {territoire} :\n")
    for slug, motif in restantes.items():
        tache = etat[slug]
        marque = "✓" if motif is None else " "
        print(
            f"{marque} {slug.ljust(largeur)}  {(tache.famille or '—'):<32} "
            f"{tache.destinataire:<26} {tache.objet:<22} {tache.titre[:60]}"
        )
        if motif is not None:
            print(f"  {' ' * largeur}  → {motif}")
        if tache.note:
            print(f"  {' ' * largeur}    « {tache.note[:140]} »")
        print(f"  {' ' * largeur}    {tache.url}")
    print(
        f"\n{len(pretes)} passerai(en)t le test du destinataire (✓), "
        f"{len(restantes) - len(pretes)} demande(nt) un arbitrage."
    )
    print(
        f"\n  prospecter.py valider {territoire} --tout        "
        "(les ✓ seulement)\n"
        f"  prospecter.py valider {territoire} <slug> [<slug>…]  "
        "(un arbitrage nommé, quel que soit son motif)"
    )
    return 0


def _transitionner(args: argparse.Namespace, vers: str) -> int:
    etat = charger(args.etat)
    if vers == "valide" and not args.slugs and not args.tout:
        return _lister_restantes(etat, args.territoire)
    depuis = DEPUIS_TOUT if args.tout else DEPUIS_NOMME
    if args.tout and vers == "valide" and not getattr(args, "sans_filtre", False):
        # `--tout` applique désormais le test du destinataire : c'est ce qui a
        # manqué au balayage du 2026-09-18, où 140 candidates `adjacente` et 5
        # `hors_perimetre` sont passées en `valide` avec les autres. Nommer un
        # slug reste un geste délibéré et n'est jamais filtré.
        candidats = [s for s, t in etat.items() if t.territoire == args.territoire]
        cibles = promouvables(etat, candidats)
        ecartes = [s for s in candidats if s not in cibles and etat[s].statut == "a_valider"]
        if ecartes:
            print(
                f"  {len(ecartes)} candidate(s) laissée(s) en `a_valider` par le test du "
                f"destinataire — `prospecter.py valider {args.territoire}` les liste."
            )
        for slug in cibles:
            mettre_a_jour(args.etat, slug, statut=vers)
            print(f"  {slug} → {vers}")
        print(f"{len(cibles)} aide(s) passée(s) en `{vers}`.")
        if cibles:
            print(
                "\nIngérer : uv run python scripts/ingerer.py --file-attente "
                f"--territoire {args.territoire}"
            )
        return 0
    cibles = [
        slug
        for slug, t in etat.items()
        if t.territoire == args.territoire
        and t.statut in depuis
        and t.statut != vers
        and (args.tout or slug in args.slugs)
    ]
    inconnus = [s for s in args.slugs if s not in etat]
    for slug in inconnus:
        print(f"  slug inconnu, ignoré : {slug}")
    figes = [
        s
        for s in args.slugs
        if s in etat and etat[s].statut not in depuis and etat[s].statut != vers
    ]
    for slug in figes:
        print(
            f"  {slug} : statut `{etat[slug].statut}` — inchangé "
            "(une aide en cours d'ingestion, ingérée ou en échec ne se rebascule pas ici ; "
            "cf. `ingerer.py --reprendre` / `--relancer-echecs`)"
        )
    for slug in cibles:
        mettre_a_jour(args.etat, slug, statut=vers)
        print(f"  {slug} → {vers}")
    print(f"{len(cibles)} aide(s) passée(s) en `{vers}`.")
    if vers == "valide" and cibles:
        print(
            "\nIngérer : uv run python scripts/ingerer.py --file-attente "
            f"--territoire {args.territoire}"
        )
    return 0


def cmd_comparer(args: argparse.Namespace) -> int:
    """Confronte une liste d'URL externe au corpus, à la file et à la dernière fiche.

    Utile tant que deux pipelines coexistent : la question n'est pas « qui a le
    plus d'URL » mais « pourquoi celle-là nous manque » — écartée au tri,
    écartée à la lecture, ou jamais collectée.
    """
    from prospection import comparer as comparer_mod

    territoires = charger_territoires(args.territoires)
    territoire = territoires.get(args.territoire)
    if territoire is None:
        print(f"territoire inconnu de {args.territoires} : {args.territoire}")
        return 2
    if not args.fichier.exists():
        print(f"fichier introuvable : {args.fichier}")
        return 2
    resultat = comparer_mod.comparer(
        args.territoire,
        territoire,
        comparer_mod.lire_urls(args.fichier),
        load_all_aides(),
        charger(args.etat),
        fiche=comparer_mod.derniere_fiche(args.territoire, REVIEWS_DIR),
    )
    print(comparer_mod.rendre(resultat, args.territoire))
    return 0


class SiteOfficiel(BaseModel):
    """Ce qu'on demande au modèle quand l'annuaire de l'État ne sait pas."""

    url_racine: str
    url_guide_aides: str
    confiance: str = "faible"


def cmd_deviner_sites(args: argparse.Namespace) -> int:
    """Propose une URL de guide pour des départements sans point d'entrée.

    L'annuaire de l'administration passe EN PREMIER : c'est une source
    déterministe, gratuite, tenue à jour par les administrations elles-mêmes.
    Le modèle n'intervient qu'en repli, et sa proposition est toujours vérifiée
    par une vraie requête.

    N'ÉCRIT PAS `territoires.yaml` dans tous les cas : imprime un bloc à coller
    après contrôle. Une URL de guide fausse fait tourner un balayage entier
    dans le vide et remplit une fiche de bruit — c'est le genre de décision qui
    passe par un humain.
    """
    territoires = charger_territoires(args.territoires)
    fetcheur = Fetcheur()
    compteur = Compteur()
    blocs: list[str] = []
    client = None
    try:
        annuaire = sites_departementaux(fetcheur)
        print(f"annuaire de l'État : {len(annuaire)} conseil(s) départemental(aux) référencé(s)\n")
        for cle in args.departements:
            territoire = territoires.get(cle)
            if territoire is None:
                print(f"  {cle} : inconnu de territoires.yaml")
                continue
            officiel = annuaire.get(cle)
            if officiel is not None:
                url, provenance = officiel.url, "annuaire de l'administration"
            else:
                if client is None:
                    client = client_pour("decouverte", args.model_decouverte)
                essai = client.try_complete_json(
                    SiteOfficiel,
                    f"Quel est le site officiel du conseil départemental « {territoire.nom} » "
                    f"(code {cle}, France), et l'URL de sa rubrique « aides et subventions » ? "
                    "Ne réponds que si tu es sûr de l'existence de ces URL.",
                )
                compteur.ajouter(essai.response, "decouverte")
                if essai.data is None:
                    print(f"  {cle} {territoire.nom:<28} aucune proposition")
                    continue
                url = essai.data.url_guide_aides
                provenance = f"modèle, confiance {essai.data.confiance}"
            page = fetcheur.get(url)
            verdict = "200" if page.ok else f"{page.erreur or page.status}"
            print(f"  {cle} {territoire.nom:<28} {url}  [{verdict}] ({provenance})")
            if not page.ok:
                continue
            blocs.append(
                f"'{cle}':\n"
                f"  statut: decouverte\n"
                f"  guides: [{page.url_finale}]\n"
                f"  notes: URL relevée le {date.today().isoformat()} via {provenance}, "
                "répond 200 — rubrique des aides et recette à préciser après un premier "
                "balayage.\n"
            )
    finally:
        fetcheur.close()
    if compteur.appels:
        print(f"\n{compteur.resume()}")
    if blocs:
        print(
            f"\n--- à fusionner À LA MAIN dans {args.territoires} "
            "(après avoir OUVERT chaque URL) ---\n"
        )
        print("\n".join(blocs))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _options_communes(p: argparse.ArgumentParser) -> None:
    """Les deux chemins que toutes les sous-commandes doivent pouvoir détourner."""
    p.add_argument("--etat", type=Path, default=FILE_ATTENTE, help=argparse.SUPPRESS)
    p.add_argument("--territoires-file", dest="territoires", type=Path, default=TERRITOIRES_FILE)


def construire_parser() -> argparse.ArgumentParser:
    """Le parseur du BALAYAGE. Les sous-commandes ont chacune le leur.

    Un `nargs="*"` positionnel et des sous-commandes ne cohabitent pas dans
    argparse : il assigne gloutonnement les positionnels avant de chercher un
    verbe, et `prospecter.py deviner-sites 44 49` finissait en « invalid
    choice ». D'où un aiguillage explicite dans `main()`, sur le premier mot.
    """
    p = argparse.ArgumentParser(
        prog="prospecter.py",
        description="Balaye les guides d'aides territoriaux et propose des candidates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("territoires_cles", nargs="*", help="clés de territoires.yaml")
    p.add_argument("--regions", action="store_true", help="toutes les régions")
    p.add_argument("--departements", action="store_true", help="tous les départements")
    p.add_argument(
        "--forcer",
        action="store_true",
        help="inclure les territoires `sans_point_entree` (ne produira rien)",
    )
    p.add_argument("--etape", type=int, choices=(1, 2, 3), help="s'arrêter après cet étage")
    p.add_argument("--rejouer", action="store_true", help="repartir des .jsonl, sans réseau")
    p.add_argument(
        "--auto",
        action="store_true",
        help="enchaîner : valider les retenues et les ingérer, sans point de contrôle humain",
    )
    p.add_argument("--model-tri")
    p.add_argument("--model-lecture")
    p.add_argument("--model-decouverte")
    p.add_argument(
        "--sans-jev",
        action="store_true",
        help="lecture par le LLM seul, sans l'arbitrage de Jev (prospection/arbitre.py)",
    )

    ing = p.add_argument_group(
        "ingestion (avec --auto)",
        "Mêmes réglages que ingerer.py. Sans --auto, ils sont sans effet.",
    )
    ing.add_argument(
        "--parallele",
        type=int,
        default=orchestrateur.PARALLELE_DEFAUT,
        help=f"aides ingérées en même temps (défaut : {orchestrateur.PARALLELE_DEFAUT})",
    )
    ing.add_argument(
        "--budget-aide",
        type=float,
        default=Limites.budget_usd,
        help=f"plafond en $ par aide (défaut : {Limites.budget_usd:.2f})",
    )
    ing.add_argument(
        "--budget-total",
        type=float,
        default=orchestrateur.BUDGET_TOTAL_DEFAUT,
        help=f"plafond en $ pour toute l'ingestion (défaut : {orchestrateur.BUDGET_TOTAL_DEFAUT:.0f})",
    )
    ing.add_argument(
        "--max-tours",
        type=int,
        default=Limites.max_tours,
        help=f"tours d'agent par aide (défaut : {Limites.max_tours})",
    )
    ing.add_argument("--model-ingestion", help="modèle d'extraction (défaut : LLM_MODEL_INGESTION)")
    ing.add_argument(
        "--model-verif", help="modèle de vérification (défaut : LLM_MODEL_VERIFICATION)"
    )
    _options_communes(p)
    return p


def _parseur_etat() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py etat")
    p.add_argument("territoire", nargs="?")
    _options_communes(p)
    return p


def _parseur_transition(verbe: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"prospecter.py {verbe}")
    p.add_argument("territoire")
    p.add_argument("slugs", nargs="*")
    p.add_argument(
        "--tout",
        action="store_true",
        help="toutes les candidates `a_valider` (jamais celles déjà ignorées : "
        "pour revenir sur un `ignorer`, nommer le slug)",
    )
    if verbe == "valider":
        p.add_argument(
            "--sans-filtre",
            action="store_true",
            help="avec --tout : promouvoir SANS appliquer le test du destinataire "
            "(ancien comportement, pour une file relue à la main)",
        )
    _options_communes(p)
    return p


def _parseur_comparer() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py comparer")
    p.add_argument("territoire")
    p.add_argument("fichier", type=Path, help="liste d'URL externe, une par ligne")
    _options_communes(p)
    return p


def cmd_requalifier(args: argparse.Namespace) -> int:
    """Applique le test du destinataire à des aides DÉJÀ ingérées. Écrit une FICHE.

    Ne renomme rien : c'est l'utilisateur qui valide la liste, et les
    renommages viennent après. 643 aides sont entrées dans la nuit du
    2026-09-18 sans qu'aucun humain ne s'interpose entre le tri et l'écriture
    des YAML — refaire la même chose à l'envers n'aurait aucun sens.
    """
    from prospection import requalification as requal

    if args.appliquer:
        ecarts = requal.parser_ecarts(args.appliquer.read_text(encoding="utf-8"))
        if not ecarts:
            print(f"Aucun slug à écarter dans {args.appliquer}.")
            return 0
        rapport_a = requal.appliquer(ecarts, etat_path=args.etat, ecrire=True)
        print(rapport_a.texte())
        if not rapport_a.ok:
            print("\nRien n'a été écrit.")
            return 1
        print("\nLes écartées sont en `.yaml.echec` — rien n'est supprimé, le")
        print("renommage inverse suffit à en rappeler une.")
        print("Faits proposés devenus orphelins :")
        print("  uv run python scripts/retyper_faits.py --retirer-orphelins --dry-run")
        print("Puis, à la main (cf. « Interdits absolus » de CLAUDE.md) :")
        print("  uv run python scripts/lint_aides_data.py")
        print("  git add -A && git commit")
        print("  uv run python scripts/load_aides_yaml.py")
        return 0

    aides = load_all_aides()
    if args.catalogue:
        vises = dict(aides)
        nom = "catalogue"
    elif args.lot:
        slugs = requal.slugs_du_fichier(args.lot)
        inconnus = [s for s in slugs if s not in aides]
        for slug in inconnus:
            print(f"  slug inconnu du catalogue, ignoré : {slug}")
        vises = {s: aides[s] for s in slugs if s in aides}
        nom = args.lot.stem
    else:
        etat = charger(args.etat)
        slugs = [s for s, t in etat.items() if t.territoire in args.territoire and s in aides]
        vises = {s: aides[s] for s in slugs}
        nom = "-".join(args.territoire)
    if not vises:
        print("Aucune aide à requalifier.")
        return 0

    compteur = Compteur()
    # Rôle `lecture` : la requalification EST la lecture, appliquée au YAML
    # d'une aide déjà ingérée plutôt qu'à sa page. Même consigne, même
    # jugement, donc même modèle — lui donner un rôle à part obligerait à
    # régler une septième variable d'environnement pour rien.
    client = client_pour("lecture", args.model_requalification)
    # `univers` = tout le catalogue : un slug court ne doit pas hériter de la
    # fiche d'un slug plus long qui le contient (cf. `reviews_de`).
    reviews = requal.reviews_de(list(vises), REVIEWS_DIR, univers=list(aides))
    print(f"{len(vises)} aide(s) à relire, {len(reviews)} fiche(s) de review trouvée(s)")
    print(f"modèle : {client.model}, {args.parallele} en parallèle\n")

    def progression(i: int, total: int, verdict) -> None:
        if i % 25 == 0 or i == total:
            print(f"  [{i}/{total}] {compteur.resume()}", flush=True)

    rapport = requal.requalifier(
        vises,
        client,
        reviews=reviews,
        compteur=compteur,
        progression=progression,
        parallele=args.parallele,
    )
    rapport.cout = compteur.resume()

    jour = date.today()
    cible = args.sortie or (REVIEWS_DIR / f"{jour.isoformat()}-tri-{nom}.md")
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(requal.rendre_fiche(rapport, nom=nom, jour=jour), encoding="utf-8")
    for sort, libelle in (
        ("retenir", "retenues"),
        ("ecarter", "à écarter"),
        ("indetermine", "à trancher"),
        ("erreur", "non jugées"),
    ):
        print(f"  {len(rapport.par_sort(sort)):4d} {libelle}")
    print(f"\nFiche écrite : {cible}")
    print("RIEN n'a été renommé. Relire et corriger le bloc « Slugs à écarter »")
    print("(retirer une ligne = garder l'aide), puis :")
    print(f"  uv run python scripts/prospecter.py requalifier --appliquer {cible}")
    return 0


def _parseur_requalifier() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py requalifier")
    cible = p.add_mutually_exclusive_group(required=True)
    cible.add_argument(
        "--appliquer",
        type=Path,
        metavar="FICHE",
        help="appliquer une fiche relue : renomme les écartées en `.yaml.echec`",
    )
    cible.add_argument("--lot", type=Path, help="fichier de slugs, un par ligne")
    cible.add_argument("--territoire", action="append", default=[], help="tout un territoire")
    cible.add_argument("--catalogue", action="store_true", help="TOUT le catalogue")
    p.add_argument("--sortie", type=Path, help="chemin de la fiche produite")
    p.add_argument(
        "--model-requalification",
        help="modèle à utiliser (défaut : LLM_MODEL_LECTURE, le même qu'à la lecture)",
    )
    p.add_argument(
        "--parallele",
        type=int,
        default=requalification.PARALLELE_DEFAUT,
        help=f"aides jugées en même temps (défaut : {requalification.PARALLELE_DEFAUT})",
    )
    _options_communes(p)
    return p


def _parseur_deviner() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py deviner-sites")
    p.add_argument("departements", nargs="+", help="codes INSEE (44, 2A, 971…)")
    p.add_argument("--model-decouverte")
    _options_communes(p)
    return p


def cmd_relire(args: argparse.Namespace) -> int:
    """Repasse par la lecture les échecs de panne qui n'ont jamais vu le test.

    Les 351 tâches perdues le 2026-09-18 ont été lues avant que la lecture ne
    rende `destinataire` et `objet` : relancées telles quelles, elles seraient
    ingérées sans filtre. Une lecture coûte un appel (≈ 0,004 $) là où une
    ingestion en coûte vingt ; sur le lot suivant, 29 % seulement des aides
    écrites ont survécu au tri.

    Rien n'est ingéré ici : les retenues passent en `a_valider`, les écartées
    en `ignore` avec leur motif. `balayage.py --rattraper-echecs` enchaîne la
    promotion et l'ingestion.
    """
    from concurrent.futures import ThreadPoolExecutor

    from pipeline.etat import echecs_a_relire, ecrire
    from pipeline.verrou import verrou_fichier

    etat = charger(args.etat)
    slugs = [
        s
        for s in echecs_a_relire(etat)
        if not args.territoire or etat[s].territoire in args.territoire
    ]
    if not slugs:
        print("Aucun échec à relire.")
        return 0
    territoires = charger_territoires(args.territoires)
    print(f"{len(slugs)} échec(s) de panne à relire, {args.parallele} en parallèle")
    if args.dry_run:
        for slug in slugs:
            print(f"  {slug:<60} {etat[slug].territoire}")
        return 0

    compteur = Compteur()
    client = client_pour("lecture", args.model_lecture)
    arbitre = arbitre_pour(args)

    def relire_une(slug: str) -> tuple[str, lecture_mod.Lecture | None, str | None]:
        tache = etat[slug]
        territoire = territoires.get(tache.territoire)
        if territoire is None:
            return slug, None, f"territoire inconnu : {tache.territoire}"
        candidat = collecte_mod.Candidat(
            url=tache.url, titre=tache.titre, documents=tuple(tache.urls_pdf)
        )
        fetcheur = Fetcheur(entetes=territoire.entetes)
        try:
            return (
                slug,
                lecture_mod.lire(
                    candidat, territoire, fetcheur, client, compteur=compteur, arbitre=arbitre
                ),
                None,
            )
        finally:
            fetcheur.close()

    try:
        with ThreadPoolExecutor(max_workers=args.parallele) as pool:
            resultats = list(pool.map(relire_une, slugs))
    finally:
        if arbitre is not None:
            arbitre.fermer()

    sorts: dict[str, list[str]] = {"a_valider": [], "ignore": [], "erreur": []}
    with verrou_fichier(args.etat):
        courant = charger(args.etat)
        for slug, lecture, erreur in resultats:
            tache = courant.get(slug)
            maj = fiche_mod.requalifier(tache, lecture) if tache and lecture else None
            # La tâche a pu bouger pendant la lecture : on ne touche qu'un échec.
            if maj is None or tache is None or tache.statut != "echec":
                sorts["erreur"].append(f"{slug} : {erreur or (lecture.erreur if lecture else '?')}")
                continue
            courant[slug] = maj
            sorts[maj.statut].append(slug)
        ecrire(args.etat, courant)

    promus = promouvables(charger(args.etat), sorts["a_valider"])
    print(f"  {len(sorts['a_valider']):4d} en `a_valider`, dont {len(promus)} promouvable(s)")
    print(f"  {len(sorts['ignore']):4d} écartée(s) par le test du destinataire (`ignore`)")
    print(f"  {len(sorts['erreur']):4d} non relue(s), restées en `echec`")
    for ligne in sorts["erreur"][:10]:
        print(f"         {ligne[:130]}")
    print(f"\n{compteur.resume()}")
    return 0


def _parseur_relire() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py relire")
    p.add_argument("--territoire", action="append", default=[], help="borner à un territoire")
    p.add_argument("--model-lecture")
    p.add_argument("--parallele", type=int, default=8, help="lectures simultanées (défaut : 8)")
    p.add_argument("--dry-run", action="store_true", help="lister, ne rien lire")
    p.add_argument("--sans-jev", action="store_true", help="lecture par le LLM seul")
    _options_communes(p)
    return p


SOUS_COMMANDES = {
    "etat": (_parseur_etat, cmd_etat),
    "valider": (lambda: _parseur_transition("valider"), lambda a: _transitionner(a, "valide")),
    "ignorer": (lambda: _parseur_transition("ignorer"), lambda a: _transitionner(a, "ignore")),
    "comparer": (_parseur_comparer, cmd_comparer),
    "requalifier": (_parseur_requalifier, cmd_requalifier),
    "deviner-sites": (_parseur_deviner, cmd_deviner_sites),
    "relire": (_parseur_relire, cmd_relire),
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    charger_env()

    # Pendant la refonte, une seule chaîne écrit chaque opération (registre du catalogue).
    from catalogue.registre import refus_ancienne

    if refus := refus_ancienne("prospection"):
        print(f"ERREUR : {refus}", file=sys.stderr)
        return 1

    if argv and argv[0] in SOUS_COMMANDES:
        fabrique, fonction = SOUS_COMMANDES[argv[0]]
        args = fabrique().parse_args(argv[1:])
        if not hasattr(args, "model_decouverte"):
            args.model_decouverte = None
        return fonction(args)

    parser = construire_parser()
    args = parser.parse_args(argv)

    territoires = charger_territoires(args.territoires)
    cles = selectionner(
        territoires,
        args.territoires_cles,
        regions=args.regions,
        departements=args.departements,
        forcer=args.forcer,
    )
    if not cles:
        parser.print_help()
        print(
            f"\n{len(territoires)} territoire(s) dans {args.territoires}. "
            "Sans point d'entrée connu, un territoire est ignoré (--forcer pour passer outre)."
        )
        return 2

    compteur = Compteur()
    fiches = []
    for cle in cles:
        fiche = prospecter(cle, territoires[cle], args, compteur)
        if fiche:
            fiches.append((cle, fiche))

    print(f"\n{len(fiches)} fiche(s) écrite(s). {compteur.resume()}")
    if not fiches:
        return 0
    if args.auto:
        return _enchainer(args, [cle for cle, _ in fiches])
    print("\nÀ FAIRE :")
    print("  1. relire les fiches ci-dessus (colonnes vides = information absente de la page)")
    for cle, _ in fiches:
        print(f"  2. uv run python scripts/prospecter.py valider {cle} --tout")
        print(f"  3. uv run python scripts/ingerer.py --file-attente --territoire {cle}")
    return 0


def _enchainer(args: argparse.Namespace, cles: list[str]) -> int:
    """`--auto` : valider les retenues et lancer l'ingestion sans attendre.

    Le point de contrôle humain est SAUTÉ, pas supprimé — les fiches sont
    écrites et les reviews d'ingestion restent à relire avant tout commit.

    Les réglages d'ingestion viennent de la ligne de commande, comme pour
    `ingerer.py` : sans eux, un balayage de région entier tournait à 3 en
    parallèle sans qu'on puisse rien y faire.
    """
    from ingestion.worker import ConfigIngestion

    etat = charger(args.etat)
    candidats = [slug for slug, t in etat.items() if t.territoire in cles]
    a_valider = promouvables(etat, candidats)
    laissees = [s for s in candidats if s not in a_valider and etat[s].statut == "a_valider"]
    for slug in a_valider:
        mettre_a_jour(args.etat, slug, statut="valide")
    print(f"\n--auto : {len(a_valider)} candidate(s) validée(s) sans relecture")
    if laissees:
        print(
            f"         {len(laissees)} laissée(s) en `a_valider` par le test du "
            "destinataire ou faute de famille — elles ne sont pas perdues, "
            "`prospecter.py valider <territoire>` les liste."
        )
    if not a_valider:
        return 0
    config = ConfigIngestion(
        modele=args.model_ingestion,
        modele_verif=args.model_verif,
        limites=Limites(max_tours=args.max_tours, budget_usd=args.budget_aide),
        jour=date.today(),
    )
    ingestion = resolution_pour("ingestion", args.model_ingestion)
    verification = resolution_pour("verification", args.model_verif)
    print(f"extraction   : {ingestion.spec.alias} ({ingestion.source})")
    print(f"vérification : {verification.spec.alias} ({verification.source})")
    print(
        f"budget       : ${args.budget_aide:.2f} par aide, ${args.budget_total:.2f} au total, "
        f"{args.max_tours} tours max, {args.parallele} en parallèle\n"
    )
    resultats = orchestrateur.executer(
        a_valider,
        config,
        parallele=args.parallele,
        budget_total=args.budget_total,
        etat_path=args.etat,
        compteur=Compteur(),
    )
    print(orchestrateur.bilan(resultats))
    return 0 if all(r.ok for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())

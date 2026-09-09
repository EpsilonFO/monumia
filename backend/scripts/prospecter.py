"""
Prospection des guides d'aides territoriaux — le skill `/prospecter-aides-region`,
payé à l'API.

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

from pipeline.etat import FILE_ATTENTE, PROSPECTION_DIR, charger, mettre_a_jour
from pipeline.etat import fusionner as fusionner_etat
from pipeline.llm import Compteur, charger_env, client_pour
from pipeline.web import Fetcheur
from prospection import collecte as collecte_mod
from prospection import fiche as fiche_mod
from prospection import lecture as lecture_mod
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
    print(f"    [2/3] lot {i}/{n} : {retenus} retenue(s), {douteux} douteuse(s)", flush=True)


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
        a_lire = [c for c in collecte.candidats if c.url in a_ouvrir]
        print(f"    [3/3] {len(a_lire)} page(s) à lire, une par une", flush=True)
        lectures: list[lecture_mod.Lecture] = []
        debut = time.monotonic()
        for i, c in enumerate(a_lire, 1):
            le = lecture_mod.lire(c, territoire, fetcheur, client_lecture, compteur=compteur)
            lectures.append(le)
            verdict = "retenue" if le.retenue else ("ERREUR " if le.erreur else "écartée")
            print(
                f"    [3/3] {i:>3}/{len(a_lire)} {verdict}  {_court(c.url)}"
                f"  ({time.monotonic() - debut:.0f} s)",
                flush=True,
            )
        (travail / "lectures.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "url": le.candidat.url,
                        "erreur": le.erreur,
                        "fiche": le.fiche.model_dump() if le.fiche else None,
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


def _transitionner(args: argparse.Namespace, vers: str) -> int:
    etat = charger(args.etat)
    depuis = DEPUIS_TOUT if args.tout else DEPUIS_NOMME
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
    p.add_argument("--auto", action="store_true", help="valider et ingérer dans la foulée")
    p.add_argument("--model-tri")
    p.add_argument("--model-lecture")
    p.add_argument("--model-decouverte")
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
    _options_communes(p)
    return p


def _parseur_deviner() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospecter.py deviner-sites")
    p.add_argument("departements", nargs="+", help="codes INSEE (44, 2A, 971…)")
    p.add_argument("--model-decouverte")
    _options_communes(p)
    return p


SOUS_COMMANDES = {
    "etat": (_parseur_etat, cmd_etat),
    "valider": (lambda: _parseur_transition("valider"), lambda a: _transitionner(a, "valide")),
    "ignorer": (lambda: _parseur_transition("ignorer"), lambda a: _transitionner(a, "ignore")),
    "deviner-sites": (_parseur_deviner, cmd_deviner_sites),
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    charger_env()

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
    """
    from ingestion import orchestrateur
    from ingestion.worker import ConfigIngestion

    etat = charger(args.etat)
    a_valider = [
        slug for slug, t in etat.items() if t.territoire in cles and t.statut == "a_valider"
    ]
    for slug in a_valider:
        mettre_a_jour(args.etat, slug, statut="valide")
    print(f"--auto : {len(a_valider)} candidate(s) validée(s) sans relecture")
    if not a_valider:
        return 0
    resultats = orchestrateur.executer(
        a_valider, ConfigIngestion(), etat_path=args.etat, compteur=Compteur()
    )
    print(orchestrateur.bilan(resultats))
    return 0 if all(r.ok for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())

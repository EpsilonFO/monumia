"""Un dispositif, une fiche : groupe le catalogue par URL et propose un survivant.

    uv run python scripts/dedoublonner_aides.py --dry-run
    uv run python scripts/dedoublonner_aides.py --appliquer data/doublons/2026-09-21-doublons-url.yaml

130 groupes d'URL partagées après le balayage du 2026-09-18, de trois origines
distinctes et qui se corrigent toutes ici :

  - **51 ré-ingestions** d'aides déjà au catalogue, sous un slug suffixé `-2` :
    même URL, même territoire, la base ingérée le 17 et le double le 18.
    `collecte.dedoublonner` n'agit qu'à l'étage 1, et `lecture.slug_final`
    résout une collision de slug par un suffixe numérique au lieu d'y voir un
    doublon ;
  - **22 paires nouvelles** : pages de pagination Typo3
    (`?tx_news_pi1[currentPage]=1&cHash=…`), documents `.doc` ou `.zip` pris
    pour des fiches ;
  - **17 dispositifs de la Collectivité européenne d'Alsace** ingérés sous
    `67-*` ET sous `68-*`, parce que `territoires.yaml` donnait le même guide
    aux deux clés.

Ce que le script fait : il PROPOSE. Le `--dry-run` écrit une table YAML que
l'humain relit et corrige, et `--appliquer` exécute cette table-là — jamais ce
que le script aurait décidé tout seul entre-temps. C'est le même contrat que
`fusionner_faits.py`, et pour la même raison : le survivant se choisit sur des
critères formels que rien ne garantit être les bons.

Ce qu'il ne fait JAMAIS :

  - supprimer un fichier. L'écarté est renommé `<slug>.yaml.echec` — hors du
    glob `*.yaml`, donc invisible au lint, au moteur et au loader — et il se
    remet en place d'un `mv` ;
  - toucher à `data/sources/`. Les snapshots sont la preuve des citations, et
    ils servent encore si l'écart se révèle une erreur ;
  - retirer l'aide d'`aides_v3`. C'est `scripts/purge_archived_aides.py --apply`
    après le `load`, et c'est une action de l'utilisateur.

Le cas de la Collectivité européenne d'Alsace est traité à part : le survivant y
est le `67-*`, et il doit porter `hard_filters.departements: ['67', '68']` —
sans quoi l'écart du `68-*` ferait perdre le Haut-Rhin. Le script le propose,
il ne l'écrit pas.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.etat import FILE_ATTENTE, charger, mettre_a_jour
from prospection.collecte import cle_fiche

from aides_schema import AIDES_DIR, DATA_DIR, Aide, charger_yaml, load_all_aides

#: PAS `data/fusions/`, qui tient les tables de fusion de FAITS et dont un test
#: vérifie que chaque fichier porte une clé `fusions` : deux schémas dans un
#: même dossier, et le contrôle de l'un tombe sur les tables de l'autre.
DOUBLONS_DIR = DATA_DIR / "doublons"


@dataclass(frozen=True)
class Groupe:
    """Des aides qui pointent la même page. `survivant` est une PROPOSITION."""

    cle: str
    survivant: str
    ecartes: tuple[str, ...]
    motif: str = ""

    @property
    def taille(self) -> int:
        return 1 + len(self.ecartes)


@dataclass
class Rapport:
    erreurs: list[str] = field(default_factory=list)
    groupes: list[Groupe] = field(default_factory=list)
    renommes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    @property
    def ecartes(self) -> int:
        return sum(len(g.ecartes) for g in self.groupes)

    def texte(self) -> str:
        lignes = [f"{len(self.groupes)} groupe(s), {self.ecartes} aide(s) à écarter"]
        for g in self.groupes[:20]:
            lignes.append(f"  {g.survivant}  ←  {', '.join(g.ecartes)}")
            if g.motif:
                lignes.append(f"      {g.motif}")
        if len(self.groupes) > 20:
            lignes.append(f"  … et {len(self.groupes) - 20} autre(s)")
        if self.renommes:
            lignes.append(f"{len(self.renommes)} fichier(s) renommé(s) en .yaml.echec")
        for e in self.erreurs:
            lignes.append(f"  ERREUR : {e}")
        return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Choix du survivant
# ---------------------------------------------------------------------------


#: Ce qui fait qu'une fiche est la bonne, du plus décisif au moins décisif. Une
#: clé lexicographique et non un score : un score pondéré se règle à l'infini et
#: ne se relit pas, alors qu'une liste ordonnée se discute critère par critère.
def _rang(slug: str, aide: Aide) -> tuple:
    """Plus petit = meilleur survivant.

    L'ordre n'est pas arbitraire. Une aide qui déclare son PÉRIMÈTRE ou ses
    DÉPARTEMENTS a été mieux ingérée que sa jumelle : ce sont les deux champs
    que le pipeline rate le plus souvent. Vient ensuite la richesse (familles,
    nombre de conditions), puis la forme du slug — un suffixe `-2` est la trace
    d'une collision, jamais un choix éditorial.
    """
    suffixe_numerique = slug.rsplit("-", 1)[-1].isdigit()
    return (
        aide.applies_if is None,
        not aide.hard_filters.departements,
        not aide.familles,
        -len(aide.conditions),
        suffixe_numerique,
        len(slug),
        slug,
    )


#: Le cas de la Collectivité européenne d'Alsace : un site unique pour deux
#: départements, 17 dispositifs entrés deux fois.
_PREFIXES_CEA = ("67-", "68-")


def _motif_cea(slugs: list[str]) -> str:
    """Le mot à dire quand un groupe mélange du `67-` et du `68-`."""
    if not ({s[:3] for s in slugs} >= set(_PREFIXES_CEA)):
        return ""
    return (
        "Collectivité européenne d'Alsace : un site unique pour les deux départements. "
        "Le survivant DOIT porter `hard_filters.departements: ['67', '68']`, sinon "
        "l'écart du 68 fait perdre le Haut-Rhin."
    )


def grouper(aides: dict[str, Aide]) -> list[Groupe]:
    """Les groupes d'aides qui partagent une URL de fiche, survivant proposé.

    Le groupement se fait sur `cle_fiche` — la même que la collecte et que
    `pipeline.etat.doublons_par_url`, sans quoi une paire écartée ici
    reviendrait par là. Une ANCRE distincte n'est PAS un doublon : une page
    peut porter deux dispositifs sous deux ancres, et c'est un vrai découpage.
    """
    par_cle: dict[str, list[str]] = {}
    for slug, aide in aides.items():
        url = aide.source.url_officielle
        if not url:
            continue
        ancre = url.split("#", 1)[1] if "#" in url else ""
        par_cle.setdefault(f"{cle_fiche(url)}#{ancre}", []).append(slug)

    groupes: list[Groupe] = []
    for cle, slugs in sorted(par_cle.items()):
        if len(slugs) < 2:
            continue
        classes = sorted(slugs, key=lambda s: _rang(s, aides[s]))
        cea = _motif_cea(slugs)
        # Sur un groupe CeA, le 67 porte la recette (cf. territoires.yaml).
        survivant = (
            next((s for s in classes if s.startswith("67-")), classes[0]) if cea else classes[0]
        )
        groupes.append(
            Groupe(
                cle=cle.rstrip("#"),
                survivant=survivant,
                ecartes=tuple(s for s in classes if s != survivant),
                motif=cea,
            )
        )
    return groupes


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def rendre_table(groupes: list[Groupe], *, jour: date) -> str:
    """La table à relire, au format que `--appliquer` relit.

    Elle est faite pour être ÉDITÉE : changer un `survivant`, retirer un groupe
    dont on juge qu'il porte bien deux dispositifs, ajouter un motif. C'est le
    point de contrôle humain, et il n'y en a pas d'autre.
    """
    entete = [
        f"# Doublons d'URL du catalogue — {jour.isoformat()}",
        "#",
        "# Relire, corriger, puis :",
        "#   uv run python scripts/dedoublonner_aides.py --appliquer <ce fichier>",
        "#",
        "# `survivant` : la fiche qu'on garde. Les autres sont renommées",
        "# `<slug>.yaml.echec` — hors du glob `*.yaml`, donc invisibles au lint, au",
        "# moteur et au loader — et leur tâche passe `ignore` dans la file d'attente.",
        "# Rien n'est supprimé, ni les fichiers, ni les snapshots.",
        "#",
        "# Retirer un groupe de cette liste = décider que la page porte bien deux",
        "# dispositifs distincts. C'est une décision légitime, et elle se prend ici.",
        "",
    ]
    corps = yaml.safe_dump(
        {
            "doublons": [
                {
                    "url": g.cle,
                    "survivant": g.survivant,
                    "ecarter": list(g.ecartes),
                    **({"motif": g.motif} if g.motif else {}),
                }
                for g in groupes
            ]
        },
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    return "\n".join(entete) + corps


def charger_table(chemin: Path) -> tuple[list[Groupe], list[str]]:
    """Relit une table corrigée à la main."""
    try:
        brut = charger_yaml(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], [f"table illisible : {exc}"]
    if not isinstance(brut, dict) or not isinstance(brut.get("doublons"), list):
        return [], ["la table doit être un objet avec une liste `doublons`"]
    groupes, erreurs = [], []
    for i, ligne in enumerate(brut["doublons"], 1):
        if not isinstance(ligne, dict) or not ligne.get("survivant"):
            erreurs.append(f"groupe n° {i} : `survivant` manquant")
            continue
        ecarter = ligne.get("ecarter") or []
        if not isinstance(ecarter, list) or not ecarter:
            erreurs.append(f"groupe n° {i} : `ecarter` vide — rien à faire, retirer le groupe")
            continue
        if ligne["survivant"] in ecarter:
            erreurs.append(f"groupe n° {i} : le survivant est aussi dans `ecarter`")
            continue
        groupes.append(
            Groupe(
                cle=str(ligne.get("url") or ""),
                survivant=str(ligne["survivant"]),
                ecartes=tuple(str(s) for s in ecarter),
                motif=str(ligne.get("motif") or ""),
            )
        )
    return groupes, erreurs


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def appliquer(
    groupes: list[Groupe],
    *,
    aides_dir: Path = AIDES_DIR,
    etat_path: Path = FILE_ATTENTE,
    ecrire: bool = False,
) -> Rapport:
    """Renomme les écartées en `.yaml.echec` et passe leur tâche `ignore`.

    Vérifie TOUT avant d'écrire quoi que ce soit : un renommage à moitié
    appliqué laisserait un catalogue dont on ne sait plus quelle moitié a été
    traitée.
    """
    rapport = Rapport(groupes=groupes)
    vus: set[str] = set()
    for g in groupes:
        if not (aides_dir / f"{g.survivant}.yaml").exists():
            rapport.erreurs.append(f"survivant introuvable : {g.survivant}.yaml")
        for slug in g.ecartes:
            if slug in vus:
                rapport.erreurs.append(f"« {slug} » écarté par deux groupes")
            vus.add(slug)
            if not (aides_dir / f"{slug}.yaml").exists():
                rapport.erreurs.append(f"aide introuvable : {slug}.yaml — déjà écartée ?")
    # Un survivant qu'un AUTRE groupe écarte : l'ordre d'application déciderait
    # du résultat, et personne ne saurait lequel a gagné.
    for g in groupes:
        if g.survivant in vus:
            rapport.erreurs.append(
                f"« {g.survivant} » est survivant d'un groupe et écarté par un autre — "
                "scinder la table, sinon l'ordre d'application décide."
            )
    if not rapport.ok:
        return rapport
    if not ecrire:
        return rapport

    etat = charger(etat_path) if etat_path.exists() else {}
    for g in groupes:
        for slug in g.ecartes:
            source = aides_dir / f"{slug}.yaml"
            source.rename(aides_dir / f"{slug}.yaml.echec")
            rapport.renommes.append(slug)
            if slug not in etat:
                continue
            try:
                mettre_a_jour(
                    etat_path,
                    slug,
                    statut="ignore",
                    doublon_de=g.survivant,
                    motif_ignore=f"doublon d'URL de {g.survivant}",
                )
            except Exception as exc:  # noqa: BLE001 — la file est un fichier partagé
                rapport.erreurs.append(f"{slug} : statut non consigné ({exc})")
    return rapport


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dedoublonner_aides.py",
        description="Groupe le catalogue par URL de fiche et propose un survivant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--dry-run", action="store_true", help="écrire la table à relire (défaut)")
    ap.add_argument("--appliquer", type=Path, help="appliquer une table relue")
    ap.add_argument("--sortie", type=Path, help="chemin de la table produite")
    args = ap.parse_args(argv)

    if args.appliquer:
        groupes, erreurs = charger_table(args.appliquer)
        if erreurs:
            for e in erreurs:
                print(f"ERREUR : {e}")
            return 2
        rapport = appliquer(groupes, ecrire=True)
        print(rapport.texte())
        if not rapport.ok:
            print("\nRien n'a été écrit.")
            return 1
        print("\nLes fichiers écartés sont en `.yaml.echec` — rien n'est supprimé.")
        print("Faits proposés devenus orphelins :")
        print("  uv run python scripts/retyper_faits.py --retirer-orphelins --dry-run")
        print("Puis, à la main (cf. « Interdits absolus » de CLAUDE.md) :")
        print("  git add -A && git commit")
        print("  uv run python scripts/load_aides_yaml.py")
        print("  uv run python scripts/purge_archived_aides.py --apply")
        return 0

    jour = date.today()
    groupes = grouper(load_all_aides())
    print(Rapport(groupes=groupes).texte())
    cible = args.sortie or (DOUBLONS_DIR / f"{jour.isoformat()}-doublons-url.yaml")
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(rendre_table(groupes, jour=jour), encoding="utf-8")
    print(f"\nTable écrite : {cible.relative_to(DATA_DIR.parent)}")
    print("La relire et la corriger AVANT :")
    print(f"  uv run python scripts/dedoublonner_aides.py --appliquer {cible}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Dédoublonnage du catalogue par URL de fiche (scripts/dedoublonner_aides.py).

130 groupes d'URL partagées après le balayage du 2026-09-18. Ce que ces tests
fixent :

  - le groupement est celui de la COLLECTE (`cle_fiche`) : une paire écartée ici
    ne doit pas revenir par `pipeline.etat.doublons_par_url` ;
  - le survivant se choisit sur des critères ORDONNÉS et relisibles, le
    périmètre et les départements d'abord — ce sont les deux champs que le
    pipeline rate le plus souvent ;
  - rien n'est supprimé : l'écarté est renommé `.yaml.echec`, et ses snapshots
    restent en place ;
  - la table est le point de contrôle humain, et `--appliquer` exécute la table
    RELUE, pas ce que le script aurait décidé entre-temps.

Run from backend/:  uv run pytest tests/test_dedoublonner_aides.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dedoublonner_aides import (  # noqa: E402
    Groupe,
    appliquer,
    charger_table,
    grouper,
    rendre_table,
)
from pipeline.etat import Tache, charger, ecrire  # noqa: E402

from aides_schema import Aide  # noqa: E402

JOUR = date(2026, 9, 21)


def aide(slug: str, url: str, **kw) -> Aide:
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": slug,
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "description": "d",
            "source": {"url_officielle": url},
            **kw,
        }
    )


class TestGroupement(unittest.TestCase):
    def test_deux_aides_une_page(self):
        groupes = grouper(
            {
                "aide": aide("aide", "https://x.fr/a"),
                "aide-2": aide("aide-2", "https://x.fr/a"),
            }
        )
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0].ecartes, ("aide-2",))

    def test_le_suffixe_numerique_perd(self):
        """`-2` est la trace d'une collision de slug, jamais un choix éditorial."""
        groupes = grouper(
            {
                "cvl-bovins-lait-2": aide("cvl-bovins-lait-2", "https://x.fr/a"),
                "cvl-bovins-lait": aide("cvl-bovins-lait", "https://x.fr/a"),
            }
        )
        self.assertEqual(groupes[0].survivant, "cvl-bovins-lait")

    def test_le_perimetre_prime_sur_tout_le_reste(self):
        """Une aide qui déclare son `applies_if` a été mieux ingérée que sa jumelle."""
        riche = aide(
            "b-longue",
            "https://x.fr/a",
            applies_if={"fact": "statut_juridique_porteur", "predicate": {"in": ["societe"]}},
        )
        groupes = grouper({"a": aide("a", "https://x.fr/a"), "b-longue": riche})
        self.assertEqual(groupes[0].survivant, "b-longue")

    def test_les_departements_priment_sur_la_richesse(self):
        avec = aide("b", "https://x.fr/a", hard_filters={"departements": ["67", "68"]})
        sans = aide(
            "a",
            "https://x.fr/a",
            familles=["restauration_bati"],
            conditions=[
                {"id": "c1", "text": "x", "kind": "info", "effect": "info"},
                {"id": "c2", "text": "y", "kind": "info", "effect": "info"},
            ],
        )
        groupes = grouper({"a": sans, "b": avec})
        self.assertEqual(groupes[0].survivant, "b")

    def test_la_pagination_ne_sauve_pas_le_doublon(self):
        """22 paires du lot : trois pages d'une même liste Typo3."""
        base = "https://x.fr/d?tx_news_pi1[news]=42"
        groupes = grouper(
            {
                "a": aide("a", base),
                "a-2": aide("a-2", f"{base}&tx_news_pi1[currentPage]=2&cHash=x"),
                "a-3": aide("a-3", f"{base}&tx_news_pi1[currentPage]=3&cHash=y"),
            }
        )
        self.assertEqual(len(groupes), 1)
        self.assertEqual(sorted(groupes[0].ecartes), ["a-2", "a-3"])

    def test_deux_ancres_sont_deux_dispositifs(self):
        """Une page peut porter deux dispositifs : c'est un vrai découpage."""
        self.assertEqual(
            grouper({"a": aide("a", "https://x.fr/p#toit"), "b": aide("b", "https://x.fr/p#mur")}),
            [],
        )

    def test_une_aide_sans_url_est_ignoree(self):
        sans_url = Aide.model_validate(
            {
                "slug": "x",
                "nom": "x",
                "organisme": "Org",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
            }
        )
        self.assertEqual(grouper({"x": sans_url, "y": aide("y", "https://x.fr/a")}), [])


class TestCeA(unittest.TestCase):
    """17 dispositifs de la Collectivité européenne d'Alsace entrés deux fois."""

    def _groupes(self):
        return grouper(
            {
                "67-fonds": aide("67-fonds", "https://alsace.eu/f"),
                "68-fonds": aide("68-fonds", "https://alsace.eu/f"),
            }
        )

    def test_le_67_survit(self):
        """C'est lui qui porte la recette dans territoires.yaml."""
        self.assertEqual(self._groupes()[0].survivant, "67-fonds")

    def test_le_motif_avertit_sur_les_departements(self):
        """Sans `departements: ['67','68']`, l'écart du 68 perd le Haut-Rhin."""
        motif = self._groupes()[0].motif
        self.assertIn("Collectivité européenne d'Alsace", motif)
        self.assertIn("hard_filters.departements", motif)

    def test_le_67_survit_meme_moins_riche(self):
        groupes = grouper(
            {
                "67-fonds": aide("67-fonds", "https://alsace.eu/f"),
                "68-fonds": aide(
                    "68-fonds",
                    "https://alsace.eu/f",
                    familles=["restauration_bati"],
                    conditions=[{"id": "c", "text": "x", "kind": "info", "effect": "info"}],
                ),
            }
        )
        self.assertEqual(groupes[0].survivant, "67-fonds")

    def test_deux_aides_du_meme_departement_ne_declenchent_pas_le_motif(self):
        groupes = grouper(
            {
                "67-a": aide("67-a", "https://alsace.eu/f"),
                "67-b": aide("67-b", "https://alsace.eu/f"),
            }
        )
        self.assertEqual(groupes[0].motif, "")


class TestTable(unittest.TestCase):
    def test_aller_retour(self):
        groupes = [Groupe(cle="x.fr/a", survivant="a", ecartes=("a-2",), motif="m")]
        relus, erreurs = charger_table(self._ecrire(rendre_table(groupes, jour=JOUR)))
        self.assertEqual(erreurs, [])
        self.assertEqual(relus, groupes)

    def test_la_table_dit_comment_lappliquer(self):
        texte = rendre_table([], jour=JOUR)
        self.assertIn("--appliquer", texte)
        self.assertIn("Rien n'est supprimé", texte)

    def test_un_groupe_sans_ecarter_est_refuse(self):
        _g, erreurs = charger_table(self._ecrire("doublons:\n  - survivant: a\n    ecarter: []\n"))
        self.assertEqual(len(erreurs), 1, erreurs)

    def test_un_survivant_dans_ecarter_est_refuse(self):
        _g, erreurs = charger_table(self._ecrire("doublons:\n  - survivant: a\n    ecarter: [a]\n"))
        self.assertEqual(len(erreurs), 1, erreurs)

    def _ecrire(self, contenu: str) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        chemin = Path(self._tmp.name) / "t.yaml"
        chemin.write_text(contenu, encoding="utf-8")
        return chemin


class TestApplication(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.aides_dir = self.racine / "aides"
        self.aides_dir.mkdir()
        self.etat = self.racine / "file-attente.yaml"
        for slug in ("aide", "aide-2"):
            (self.aides_dir / f"{slug}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "slug": slug,
                        "nom": slug,
                        "organisme": "Org",
                        "categorie": "region",
                        "type": "subvention",
                        "description": "d",
                    },
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
        ecrire(
            self.etat,
            {
                slug: Tache(titre=slug, url="https://x.fr/a", territoire="ex", statut="ingere")
                for slug in ("aide", "aide-2")
            },
        )

    def appliquer(self, groupes, *, ecrire_=True):
        return appliquer(groupes, aides_dir=self.aides_dir, etat_path=self.etat, ecrire=ecrire_)

    GROUPE = [Groupe(cle="x.fr/a", survivant="aide", ecartes=("aide-2",))]

    def test_lecarte_est_renomme_pas_supprime(self):
        rapport = self.appliquer(self.GROUPE)
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertFalse((self.aides_dir / "aide-2.yaml").exists())
        self.assertTrue((self.aides_dir / "aide-2.yaml.echec").exists())
        self.assertTrue((self.aides_dir / "aide.yaml").exists())

    def test_la_tache_passe_ignore_avec_son_doublon_de(self):
        self.appliquer(self.GROUPE)
        tache = charger(self.etat)["aide-2"]
        self.assertEqual(tache.statut, "ignore")
        self.assertEqual(tache.doublon_de, "aide")
        self.assertIn("doublon", tache.motif_ignore or "")

    def test_dry_run_necrit_rien(self):
        rapport = self.appliquer(self.GROUPE, ecrire_=False)
        self.assertTrue(rapport.ok)
        self.assertTrue((self.aides_dir / "aide-2.yaml").exists())
        self.assertEqual(charger(self.etat)["aide-2"].statut, "ingere")

    def test_un_survivant_introuvable_bloque_tout(self):
        rapport = self.appliquer([Groupe(cle="x", survivant="jamais-vu", ecartes=("aide-2",))])
        self.assertFalse(rapport.ok)
        self.assertTrue((self.aides_dir / "aide-2.yaml").exists())

    def test_un_ecarte_deja_traite_bloque_tout(self):
        rapport = self.appliquer([Groupe(cle="x", survivant="aide", ecartes=("jamais-vu",))])
        self.assertFalse(rapport.ok)
        self.assertIn("déjà écartée", rapport.erreurs[0])

    def test_un_survivant_ecarte_ailleurs_est_refuse(self):
        """L'ordre d'application déciderait du résultat, et personne ne le saurait."""
        rapport = self.appliquer(
            [
                Groupe(cle="x", survivant="aide", ecartes=("aide-2",)),
                Groupe(cle="y", survivant="aide-2", ecartes=("aide",)),
            ]
        )
        self.assertFalse(rapport.ok)
        self.assertTrue(any("scinder la table" in e for e in rapport.erreurs))

    def test_une_aide_absente_de_la_file_est_quand_meme_renommee(self):
        """Le catalogue et la file ne sont pas toujours d'accord — le fichier prime."""
        ecrire(self.etat, {})
        rapport = self.appliquer(self.GROUPE)
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertTrue((self.aides_dir / "aide-2.yaml.echec").exists())


if __name__ == "__main__":
    unittest.main()

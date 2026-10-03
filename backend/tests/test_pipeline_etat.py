"""Tests de la file d'attente (scripts/pipeline/etat.py).

Ce qui est vérifié ici, c'est qu'aucune décision humaine ne peut être effacée
par une machine : une prospection rejouée ne remet pas en `a_valider` une aide
déjà ingérée, et deux orchestrateurs ne peuvent pas prendre le même slug.

Run from backend/:  uv run pytest tests/test_pipeline_etat.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.etat import (  # noqa: E402
    Ingestion,
    Tache,
    charger,
    doublons_par_url,
    ecrire,
    fusionner,
    mettre_a_jour,
    motif_non_promotion,
    promouvables,
    selectionner,
    transition,
)


def tache(**kw) -> Tache:
    base = {
        "titre": "Aide d'exemple",
        "url": "https://example.org/aide",
        "territoire": "hauts-de-france",
        "ajoute_le": date(2026, 9, 6),
    }
    return Tache.model_validate({**base, **kw})


class TestRoundTrip(unittest.TestCase):
    def test_ecriture_relecture_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            depart = {
                "hdf-b": tache(famille="restauration_bati"),
                "hdf-a": tache(
                    urls_pdf=["https://example.org/reglement.pdf"],
                    statut="ingere",
                    ingestion=Ingestion(tours=54, cout_usd=0.31, tentatives=1),
                ),
            }
            ecrire(chemin, depart)
            relu = charger(chemin)
            self.assertEqual(relu, depart)
            premier = chemin.read_text(encoding="utf-8")
            ecrire(chemin, relu)
            self.assertEqual(chemin.read_text(encoding="utf-8"), premier)

    def test_slugs_tries_et_champs_vides_omis(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"zz": tache(), "aa": tache()})
            texte = chemin.read_text(encoding="utf-8")
            self.assertLess(texte.index("aa:"), texte.index("zz:"))
            self.assertNotIn("famille:", texte)
            self.assertNotIn("ingestion:", texte)

    def test_motif_echec_nul_reste_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"aa": tache(ingestion=Ingestion(tours=3))})
            self.assertIn("motif_echec: null", chemin.read_text(encoding="utf-8"))

    def test_les_faux_et_les_listes_vides_sont_omis(self):
        """Sinon les dix champs de 2026-09 écrivent trois lignes mortes × 1 234 entrées."""
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"aa": tache()})
            texte = chemin.read_text(encoding="utf-8")
            for absent in (
                "a_relire:",
                "source_unique_vulgarisation:",
                "departements:",
                "urls_pdf:",
            ):
                self.assertNotIn(absent, texte)
            # Mais la valeur PORTÉE s'écrit, sinon on perdrait l'information.
            ecrire(chemin, {"aa": tache(a_relire=True, departements=["67", "68"])})
            texte = chemin.read_text(encoding="utf-8")
            self.assertIn("a_relire: true", texte)
            self.assertIn("- '67'", texte)

    def test_un_yaml_anterieur_aux_nouveaux_champs_se_charge(self):
        """Les 1 234 entrées écrites avant 2026-09-21 n'ont aucun de ces champs."""
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            chemin.write_text(
                "aa:\n  titre: Ancienne\n  url: https://x/a\n  territoire: ex\n  statut: ingere\n",
                encoding="utf-8",
            )
            relu = charger(chemin)["aa"]
            self.assertEqual(relu.destinataire, "indetermine")
            self.assertEqual(relu.objet, "indetermine")
            self.assertEqual(relu.departements, [])
            self.assertFalse(relu.a_relire)
            self.assertIsNone(relu.note)


class TestTestDuDestinataire(unittest.TestCase):
    """Ce qui a le droit de passer de `a_valider` à `valide`."""

    def test_seul_le_bon_couple_est_retenu(self):
        self.assertTrue(
            tache(destinataire="proprietaire_gestionnaire", objet="bien_ou_lieu").retenue
        )
        self.assertTrue(
            tache(destinataire="proprietaire_gestionnaire", objet="activite_dans_le_lieu").retenue
        )
        self.assertFalse(tache(destinataire="proprietaire_gestionnaire", objet="hors_lieu").retenue)
        self.assertFalse(tache(destinataire="activite_tiers", objet="bien_ou_lieu").retenue)

    def test_le_defaut_nest_pas_retenu(self):
        """Un modèle qui oublie les champs ne doit pas faire entrer l'aide."""
        self.assertFalse(tache().retenue)


class TestPromouvables(unittest.TestCase):
    def setUp(self):
        self.file = {
            "ok": tache(
                destinataire="proprietaire_gestionnaire",
                objet="bien_ou_lieu",
                famille="restauration_bati",
            ),
            "adjacente": tache(
                destinataire="proprietaire_gestionnaire",
                objet="bien_ou_lieu",
                famille="adjacente",
            ),
            "indeterminee": tache(famille="tourisme_hebergement"),
            "hors-perimetre": tache(
                destinataire="activite_tiers",
                objet="hors_lieu",
                categorie_ecart="metier_agricole",
                famille="eau_nature_domaine",
            ),
            "deja-ingeree": tache(
                statut="ingere",
                destinataire="proprietaire_gestionnaire",
                objet="bien_ou_lieu",
                famille="restauration_bati",
            ),
        }

    def test_ne_promeut_que_les_retenues_et_rangees(self):
        """643 aides sont entrées sans qu'aucune règle ne s'interpose."""
        self.assertEqual(promouvables(self.file, self.file), ["ok"])

    def test_une_adjacente_nest_pas_rangee(self):
        """`adjacente` est le DÉFAUT du tri : promouvoir dessus, c'est promouvoir
        parce que personne n'a tranché. 140 aides du lot étaient dans ce cas."""
        motif = motif_non_promotion(self.file["adjacente"])
        self.assertIn("adjacente", motif or "")

    def test_une_indeterminee_reste_a_valider(self):
        motif = motif_non_promotion(self.file["indeterminee"])
        self.assertIn("indéterminé", motif or "")

    def test_le_motif_dune_ecartee_nomme_sa_categorie(self):
        motif = motif_non_promotion(self.file["hors-perimetre"])
        self.assertIn("metier_agricole", motif or "")

    def test_tout_rend_lancien_comportement(self):
        """Une file relue et corrigée à la main : l'utilisateur assume le bloc."""
        promus = promouvables(self.file, self.file, tout=True)
        self.assertEqual(promus, ["adjacente", "hors-perimetre", "indeterminee", "ok"])

    def test_un_slug_inconnu_est_ignore(self):
        self.assertEqual(promouvables(self.file, ["ok", "jamais-vu"]), ["ok"])


class TestDoublons(unittest.TestCase):
    """A5 — le second filet, sur la file ENTIÈRE, juste avant la promotion."""

    @staticmethod
    def cle(url: str) -> str:
        """Groupement de test : la page, sans ses paramètres."""
        return url.split("?")[0]

    def test_un_ingere_survit_toujours(self):
        """51 aides du catalogue sont revenues en `-2` : c'est la base qui reste."""
        file = {
            "aide": tache(url="https://x/a", statut="ingere"),
            "aide-2": tache(url="https://x/a?page=2", statut="a_valider"),
        }
        self.assertEqual(doublons_par_url(file, cle=self.cle), {"aide-2": "aide"})

    def test_a_statut_egal_la_plus_ancienne_survit(self):
        file = {
            "b": tache(url="https://x/a", ajoute_le=date(2026, 9, 1)),
            "a": tache(url="https://x/a", ajoute_le=date(2026, 9, 18)),
        }
        self.assertEqual(doublons_par_url(file, cle=self.cle), {"a": "b"})

    def test_a_date_egale_lordre_alphabetique_tranche(self):
        """Un départage stable : deux runs doivent écarter le même slug."""
        file = {"b": tache(url="https://x/a"), "a": tache(url="https://x/a")}
        self.assertEqual(doublons_par_url(file, cle=self.cle), {"b": "a"})

    def test_des_urls_distinctes_ne_sont_pas_des_doublons(self):
        file = {"a": tache(url="https://x/a"), "b": tache(url="https://x/b")}
        self.assertEqual(doublons_par_url(file, cle=self.cle), {})

    def test_le_groupement_par_defaut_est_celui_de_la_collecte(self):
        """Les deux doivent grouper pareil, sinon une paire écartée ici revient par là."""
        file = {
            "aide": tache(url="https://x.fr/detail?tx_news_pi1[news]=42", statut="ingere"),
            "aide-2": tache(
                url="https://x.fr/detail?tx_news_pi1[news]=42&tx_news_pi1[currentPage]=2"
            ),
        }
        self.assertEqual(doublons_par_url(file), {"aide-2": "aide"})


class TestFusion(unittest.TestCase):
    def test_ajoute_les_inconnus_et_les_renvoie(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            self.assertEqual(fusionner(chemin, {"hdf-a": tache()}), ["hdf-a"])
            self.assertEqual(fusionner(chemin, {"hdf-a": tache(), "hdf-b": tache()}), ["hdf-b"])

    def test_preserve_un_slug_deja_ingere(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(
                chemin,
                {"hdf-a": tache(statut="ingere", ingestion=Ingestion(tours=54, tentatives=1))},
            )
            self.assertEqual(fusionner(chemin, {"hdf-a": tache(statut="a_valider")}), [])
            relu = charger(chemin)["hdf-a"]
            self.assertEqual(relu.statut, "ingere")
            assert relu.ingestion is not None
            self.assertEqual(relu.ingestion.tours, 54)

    def test_preserve_un_slug_ignore_a_la_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="ignore")})
            fusionner(chemin, {"hdf-a": tache()})
            self.assertEqual(charger(chemin)["hdf-a"].statut, "ignore")

    def test_complete_les_pdf_sans_doublon(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="valide", urls_pdf=["https://e.org/1.pdf"])})
            fusionner(
                chemin,
                {"hdf-a": tache(urls_pdf=["https://e.org/1.pdf", "https://e.org/2.pdf"])},
            )
            relu = charger(chemin)["hdf-a"]
            self.assertEqual(relu.urls_pdf, ["https://e.org/1.pdf", "https://e.org/2.pdf"])
            self.assertEqual(relu.statut, "valide")


class TestTransition(unittest.TestCase):
    def test_prise_de_jeton_puis_refus(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="valide")})
            self.assertTrue(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))
            # Le second orchestrateur trouve le slug déjà pris.
            self.assertFalse(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))

    def test_refuse_de_reprendre_une_aide_ingeree(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="ingere")})
            self.assertFalse(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))
            self.assertEqual(charger(chemin)["hdf-a"].statut, "ingere")

    def test_slug_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {})
            self.assertFalse(transition(chemin, "inconnu", "en_cours", depuis=("valide",)))


class TestMiseAJour(unittest.TestCase):
    def test_fusionne_le_bloc_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(ingestion=Ingestion(tentatives=1, modele="glm-flash"))})
            mettre_a_jour(chemin, "hdf-a", statut="echec", ingestion={"motif_echec": "lint rouge"})
            relu = charger(chemin)["hdf-a"]
            assert relu.ingestion is not None
            self.assertEqual(relu.statut, "echec")
            self.assertEqual(relu.ingestion.motif_echec, "lint rouge")
            # Ce que la tentative précédente avait consigné survit.
            self.assertEqual(relu.ingestion.tentatives, 1)
            self.assertEqual(relu.ingestion.modele, "glm-flash")

    def test_slug_absent_leve(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {})
            with self.assertRaises(KeyError):
                mettre_a_jour(chemin, "inconnu", statut="echec")


class TestSelection(unittest.TestCase):
    def test_filtre_et_trie_par_priorite(self):
        etat = {
            "b-normale": tache(statut="valide"),
            "a-basse": tache(statut="valide", priorite="basse"),
            "c-haute": tache(statut="valide", priorite="haute"),
            "d-attente": tache(statut="a_valider", priorite="haute"),
            "e-ailleurs": tache(statut="valide", territoire="normandie"),
        }
        self.assertEqual(
            selectionner(etat, territoires=["hauts-de-france"]),
            ["c-haute", "b-normale", "a-basse"],
        )
        self.assertEqual(selectionner(etat, statuts=("a_valider",)), ["d-attente"])
        self.assertEqual(selectionner(etat, slugs=["a-basse", "d-attente"]), ["a-basse"])


class TestChargementAbsent(unittest.TestCase):
    def test_fichier_absent_donne_file_vide(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(charger(Path(tmp) / "rien.yaml"), {})


if __name__ == "__main__":
    unittest.main()

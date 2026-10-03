"""Fonctions pures de scripts/map_pieces.py (l'appel LLM n'est pas testé)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from map_pieces import inserer_piece_ids, normaliser


class NormalisationTests(unittest.TestCase):
    def test_casse_et_espaces(self) -> None:
        self.assertEqual(normaliser("  Relevé d'Identité Bancaire  "), "releve d'identite bancaire")

    def test_accents_supprimes(self) -> None:
        self.assertEqual(normaliser("Procès-verbal"), "proces-verbal")

    def test_espaces_internes_reduits(self) -> None:
        self.assertEqual(normaliser("RIB   (IBAN)"), "rib (iban)")

    def test_ponctuation_finale_retiree(self) -> None:
        self.assertEqual(normaliser("Titre de propriété."), "titre de propriete")


class InsertionTests(unittest.TestCase):
    YAML = (
        "nom: Aide test\n"
        "documents_requis:\n"
        "  - nom: Relevé d'identité bancaire\n"
        "  - nom: Copie de la convention\n"
        "    obligatoire: false\n"
        "    note: En cas de délégation.\n"
        "  - nom: Pièce sans correspondance\n"
        "\n"
        "tags: []\n"
    )

    def test_insere_apres_le_nom(self) -> None:
        texte, n, non_traites = inserer_piece_ids(self.YAML, {"releve d'identite bancaire": "rib"})
        self.assertEqual(n, 1)
        self.assertEqual(non_traites, [])
        self.assertIn("  - nom: Relevé d'identité bancaire\n    piece_id: rib\n", texte)

    def test_conserve_les_autres_cles(self) -> None:
        texte, _, non_traites = inserer_piece_ids(
            self.YAML, {"copie de la convention": "statuts_structure"}
        )
        self.assertEqual(non_traites, [])
        self.assertIn("    piece_id: statuts_structure\n    obligatoire: false\n", texte)

    def test_libelle_absent_du_mapping_ignore(self) -> None:
        texte, n, non_traites = inserer_piece_ids(self.YAML, {})
        self.assertEqual(n, 0)
        self.assertEqual(non_traites, [])
        self.assertEqual(texte, self.YAML)

    def test_idempotent(self) -> None:
        mapping = {"releve d'identite bancaire": "rib"}
        une_fois, _, non_traites1 = inserer_piece_ids(self.YAML, mapping)
        deux_fois, n, non_traites2 = inserer_piece_ids(une_fois, mapping)
        self.assertEqual(n, 0)
        self.assertEqual(non_traites1, [])
        self.assertEqual(non_traites2, [])
        self.assertEqual(une_fois, deux_fois)

    def test_hors_bloc_documents_requis_ignore(self) -> None:
        yaml_texte = "conditions:\n  - nom: Relevé d'identité bancaire\n"
        texte, n, non_traites = inserer_piece_ids(yaml_texte, {"releve d'identite bancaire": "rib"})
        self.assertEqual(n, 0)
        self.assertEqual(non_traites, [])
        self.assertEqual(texte, yaml_texte)


class BlockScalarTests(unittest.TestCase):
    """Tests pour les block scalars (>-, |, etc.) qui s'étendent sur plusieurs lignes."""

    def test_block_scalar_simple(self) -> None:
        """Un item avec block scalar >- sur plusieurs lignes, rattaché correctement."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >-\n"
            "      Description du projet et budget dedie et tous autres\n"
            "      elements venant etayer la demande\n"
            "tags: []\n"
        )
        mapping = {
            "description du projet et budget dedie et tous autres elements venant etayer la demande": "description_projet"
        }
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        self.assertEqual(n, 1)
        self.assertEqual(non_traites, [])
        self.assertIn("    piece_id: description_projet\n", texte)

    def test_block_scalar_idempotent(self) -> None:
        """Un block scalar avec piece_id ne reçoit pas de doublon."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >-\n"
            "      Description du projet et budget dedie\n"
            "    piece_id: description_projet\n"
            "tags: []\n"
        )
        mapping = {"description du projet et budget dedie": "description_projet"}
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        self.assertEqual(n, 0)
        self.assertEqual(non_traites, [])
        # Vérifier qu'il n'y a qu'un seul piece_id
        self.assertEqual(texte.count("piece_id: description_projet"), 1)

    def test_block_scalar_avec_proprietes_suivantes(self) -> None:
        """Un block scalar suivi d'autres propriétés — piece_id atterrit au bon endroit."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >-\n"
            "      Piece justifiant du soutien du lieu de diffusion pour la\n"
            "      creation du spectacle\n"
            "    obligatoire: false\n"
            "    note: Pour les spectacles uniquement.\n"
            "tags: []\n"
        )
        mapping = {
            "piece justifiant du soutien du lieu de diffusion pour la creation du spectacle": "soutien_diffusion"
        }
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        self.assertEqual(n, 1)
        self.assertEqual(non_traites, [])
        # Vérifier que piece_id est inséré après le bloc et avant obligatoire
        self.assertIn(
            "    piece_id: soutien_diffusion\n    obligatoire: false\n",
            texte,
        )

    def test_block_scalar_absent_du_mapping(self) -> None:
        """Un block scalar absent du mapping reste inchangé."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >-\n"
            "      Description unique qui n'existe nulle part ailleurs\n"
            "tags: []\n"
        )
        texte, n, non_traites = inserer_piece_ids(yaml, {})
        self.assertEqual(n, 0)
        self.assertEqual(non_traites, [])
        self.assertEqual(texte, yaml)

    def test_block_scalar_avec_ligne_vide_avant_cle_suivante(self) -> None:
        """Block scalar dernier item de documents_requis, suivi d'une ligne vide et d'une clé de premier niveau.

        Reproduit la forme réelle trouvée dans 8 fiches (ex: 29-projets-culturels-diffusion.yaml).
        Le piece_id doit être inséré après la dernière ligne de contenu, avant la ligne vide.
        """
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >-\n"
            "      Autres partenaires publics engages subvention soutien technique ou\n"
            "      humain\n"
            "\n"
            "tags: []\n"
        )
        mapping = {
            "autres partenaires publics engages subvention soutien technique ou humain": "partenaires_publics"
        }
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        self.assertEqual(n, 1)
        self.assertEqual(non_traites, [])
        # piece_id doit être avant la ligne vide
        self.assertIn(
            "      humain\n    piece_id: partenaires_publics\n\n",
            texte,
        )


class UnreadableLabelTests(unittest.TestCase):
    """Tests pour les libellés illisibles (indicateurs non reconnus, valeurs vides)."""

    def test_block_scalar_indicateur_non_reconnu(self) -> None:
        """Un item avec bloc scalar indicateur non standard (>2-, |+, etc.) est illisible."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: >2-\n"
            "      Première ligne de contenu\n"
            "      Deuxième ligne de contenu\n"
            "tags: []\n"
        )
        mapping = {"premiere ligne de contenu deuxieme ligne de contenu": "some_id"}
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        # L'indicateur >2- n'est pas reconnu : le libellé brut vaut '>2-', qui est illisible
        self.assertEqual(n, 0)  # Pas de piece_id inséré
        self.assertGreater(len(non_traites), 0)  # Au moins une entrée
        self.assertEqual(texte, yaml)  # Texte inchangé

    def test_nom_sans_valeur(self) -> None:
        """Un item avec `- nom:` sans valeur suivante est illisible."""
        yaml = "nom: Aide test\ndocuments_requis:\n  - nom:\n  - nom: Relevé bancaire\n\ntags: []\n"
        mapping = {"releve bancaire": "rib"}
        texte, n, non_traites = inserer_piece_ids(yaml, mapping)
        # Le premier item a une valeur vide après strip()
        self.assertEqual(n, 1)  # Le deuxième item doit être traité
        self.assertGreater(len(non_traites), 0)  # Au moins le premier item non lisible
        # Le deuxième item DOIT avoir son piece_id
        self.assertIn("  - nom: Relevé bancaire\n    piece_id: rib\n", texte)

    def test_libelle_ordinaire_absent_du_mapping_nominal(self) -> None:
        """Un libellé ordinaire absent du mapping n'est PAS un non-traité — c'est nominal."""
        yaml = (
            "nom: Aide test\n"
            "documents_requis:\n"
            "  - nom: Pièce sans correspondance nulle part\n"
            "tags: []\n"
        )
        texte, n, non_traites = inserer_piece_ids(yaml, {})
        self.assertEqual(n, 0)  # Pas d'insertion
        self.assertEqual(non_traites, [])  # VIDE — ce n'est pas un non-traité
        self.assertEqual(texte, yaml)  # Inchangé


class ListeNonIndenteeTests(unittest.TestCase):
    """Les deux styles d'indentation de liste YAML coexistent dans le corpus.

    Fixtures reprises de `data/aides/detr-dsil-haute-loire.yaml` et
    `data/aides/cd43-cap43-communes.yaml`, qui écrivent leurs items au niveau
    de la clé. Ne traiter que la forme indentée avait laissé 51 pièces de côté,
    silencieusement.
    """

    def test_item_au_niveau_de_la_cle(self) -> None:
        yaml = (
            "documents_requis:\n"
            "- nom: Devis descriptif détaillé\n"
            "- nom: Échéancier de réalisation\n"
            "\n"
            "tags: []\n"
        )
        texte, n, non_traites = inserer_piece_ids(
            yaml, {"devis descriptif detaille": "devis_travaux"}
        )
        self.assertEqual(n, 1)
        self.assertEqual(non_traites, [])
        self.assertIn("- nom: Devis descriptif détaillé\n  piece_id: devis_travaux\n", texte)

    def test_proprietes_voisines_preservees(self) -> None:
        yaml = (
            "documents_requis:\n"
            "- nom: Formulaire unique de demande de subvention\n"
            "  url: https://exemple.fr/formulaire\n"
            "- nom: Autre pièce\n"
            "  obligatoire: false\n"
            "tags: []\n"
        )
        mapping = {"formulaire unique de demande de subvention": "formulaire_demande"}
        texte, n, _ = inserer_piece_ids(yaml, mapping)
        self.assertEqual(n, 1)
        self.assertIn(
            "  piece_id: formulaire_demande\n  url: https://exemple.fr/formulaire\n", texte
        )
        self.assertIn("  obligatoire: false\n", texte)

    def test_block_scalar_non_indente(self) -> None:
        yaml = (
            "documents_requis:\n"
            "- nom: >-\n"
            "    Délibération du conseil municipal approuvant les travaux et\n"
            "    sollicitant la subvention\n"
            "- nom: Autre\n"
            "tags: []\n"
        )
        cle = (
            "deliberation du conseil municipal approuvant les travaux et sollicitant la subvention"
        )
        texte, n, _ = inserer_piece_ids(yaml, {cle: "deliberation_conseil"})
        self.assertEqual(n, 1)
        self.assertIn("    sollicitant la subvention\n  piece_id: deliberation_conseil\n", texte)

    def test_idempotent_non_indente(self) -> None:
        yaml = "documents_requis:\n- nom: Titre de propriété\ntags: []\n"
        mapping = {"titre de propriete": "titre_propriete"}
        une_fois, n1, _ = inserer_piece_ids(yaml, mapping)
        deux_fois, n2, _ = inserer_piece_ids(une_fois, mapping)
        self.assertEqual((n1, n2), (1, 0))
        self.assertEqual(une_fois, deux_fois)


if __name__ == "__main__":
    unittest.main()

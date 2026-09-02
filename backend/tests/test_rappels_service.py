"""Tests de la sélection des rappels d'aides (logique pure) et de leur rendu."""

import unittest
from datetime import date

from services.email_service import (
    BlocProjet,
    date_fr,
    jours_fr,
    montant_fr,
    render_echeances_email,
    render_ouvertures_email,
)
from services.rappels_service import (
    PALIERS_DEFAUT,
    echeances_a_rappeler,
    normaliser_paliers,
    ouvertures_franchies,
    palier_courant,
)

TODAY = date(2026, 9, 1)


def _match(
    *,
    aide_id: str = "aide-test",
    nom: str = "Aide test",
    statut: str = "eligible",
    disponibilite: str = "maintenant",
    date_limite: str | None = None,
    date_ouverture: str | None = None,
    permanent: bool = False,
    montant_max: int | None = 50_000,
) -> dict:
    """Un AideMatchResult camélisé, réduit à ce que les rappels lisent."""
    return {
        "statut": statut,
        "disponibilite": disponibilite,
        "aide": {
            "id": aide_id,
            "nom": nom,
            "dateLimite": date_limite,
            "dateOuverture": date_ouverture,
            "permanent": permanent,
            "montantMax": montant_max,
        },
    }


def _diagnostic(*, eligibles=(), potentiels=(), atteignables=(), non_eligibles=()) -> dict:
    return {
        "aidesEligibles": list(eligibles),
        "aidesPotentiellementEligibles": list(potentiels),
        "aidesAtteignables": list(atteignables),
        "aidesNonEligibles": list(non_eligibles),
    }


class NormaliserPaliersTests(unittest.TestCase):
    def test_defaut_si_absent_ou_illisible(self) -> None:
        for brut in (None, "30", {}, [], ["trente"], [999], [-1]):
            self.assertEqual(normaliser_paliers(brut), PALIERS_DEFAUT)

    def test_trie_du_plus_lointain_au_plus_proche_sans_doublon(self) -> None:
        self.assertEqual(normaliser_paliers([7, 30, 7, 60]), (60, 30, 7))

    def test_ecarte_les_booleens(self) -> None:
        # `True` est un `int` en Python : sans garde, il deviendrait « 1 jour ».
        self.assertEqual(normaliser_paliers([True, 30]), (30,))


class PalierCourantTests(unittest.TestCase):
    PALIERS = (30, 7)

    def test_le_jour_pile_declenche_le_palier(self) -> None:
        self.assertEqual(palier_courant(30, self.PALIERS), 30)
        self.assertEqual(palier_courant(7, self.PALIERS), 7)

    def test_entre_deux_paliers_le_plus_lointain_reste_courant(self) -> None:
        # Le journal des envois empêche le doublon : ce jour-là, le palier 30
        # a déjà été rappelé, rien ne repart.
        self.assertEqual(palier_courant(20, self.PALIERS), 30)

    def test_rattrapage_dun_jour_manque(self) -> None:
        # Le job n'a pas tourné à J-7 : à J-6, le palier 7 est toujours courant.
        self.assertEqual(palier_courant(6, self.PALIERS), 7)

    def test_trop_loin_ou_deja_passe(self) -> None:
        self.assertIsNone(palier_courant(90, self.PALIERS))
        self.assertIsNone(palier_courant(-1, self.PALIERS))


class EcheancesTests(unittest.TestCase):
    def test_les_trois_seaux_a_portee_sont_couverts(self) -> None:
        diag = _diagnostic(
            eligibles=[_match(aide_id="a", date_limite="2026-10-01")],
            potentiels=[_match(aide_id="b", statut="potentiel", date_limite="2026-10-01")],
            atteignables=[_match(aide_id="c", statut="atteignable", date_limite="2026-10-01")],
        )
        ids = {r.aide_id for r in echeances_a_rappeler(diag, TODAY, (30,))}
        self.assertEqual(ids, {"a", "b", "c"})

    def test_les_non_eligibles_sont_ignorees(self) -> None:
        diag = _diagnostic(
            non_eligibles=[_match(statut="non_eligible", date_limite="2026-10-01")],
        )
        self.assertEqual(echeances_a_rappeler(diag, TODAY, (30,)), [])

    def test_une_aide_pas_encore_ouverte_ne_presse_pas(self) -> None:
        diag = _diagnostic(
            eligibles=[
                _match(
                    disponibilite="bientot", date_ouverture="2026-12-01", date_limite="2026-10-01"
                )
            ]
        )
        self.assertEqual(echeances_a_rappeler(diag, TODAY, (30,)), [])

    def test_les_dispositifs_permanents_nont_pas_decheance(self) -> None:
        diag = _diagnostic(eligibles=[_match(permanent=True, date_limite="2026-10-01")])
        self.assertEqual(echeances_a_rappeler(diag, TODAY, (30,)), [])

    def test_sans_date_limite_rien_a_rappeler(self) -> None:
        self.assertEqual(echeances_a_rappeler(_diagnostic(eligibles=[_match()]), TODAY, (30,)), [])

    def test_porte_le_palier_et_les_jours_restants(self) -> None:
        diag = _diagnostic(eligibles=[_match(date_limite="2026-09-21")])
        (rappel,) = echeances_a_rappeler(diag, TODAY, (30, 7))
        self.assertEqual(rappel.jours_restants, 20)
        self.assertEqual(rappel.palier_jours, 30)
        self.assertEqual(rappel.date_limite, date(2026, 9, 21))

    def test_tri_par_urgence(self) -> None:
        diag = _diagnostic(
            eligibles=[
                _match(aide_id="loin", date_limite="2026-09-25"),
                _match(aide_id="proche", date_limite="2026-09-03"),
            ]
        )
        self.assertEqual(
            [r.aide_id for r in echeances_a_rappeler(diag, TODAY, (30,))], ["proche", "loin"]
        )


class OuverturesTests(unittest.TestCase):
    def test_ouverture_du_jour(self) -> None:
        diag = _diagnostic(eligibles=[_match(date_ouverture="2026-09-01")])
        (ouverture,) = ouvertures_franchies(diag, TODAY)
        self.assertEqual(ouverture.date_ouverture, date(2026, 9, 1))
        self.assertEqual(ouverture.statut, "eligible")

    def test_rattrapage_dans_la_fenetre(self) -> None:
        diag = _diagnostic(eligibles=[_match(date_ouverture="2026-08-28")])
        self.assertEqual(len(ouvertures_franchies(diag, TODAY)), 1)

    def test_hors_fenetre_lhistorique_ne_se_reveille_pas(self) -> None:
        diag = _diagnostic(eligibles=[_match(date_ouverture="2024-01-01")])
        self.assertEqual(ouvertures_franchies(diag, TODAY), [])

    def test_ouverture_a_venir_nannonce_rien(self) -> None:
        diag = _diagnostic(eligibles=[_match(disponibilite="bientot", date_ouverture="2026-12-01")])
        self.assertEqual(ouvertures_franchies(diag, TODAY), [])

    def test_guichet_ouvert_mais_session_close_reste_muet(self) -> None:
        # Ouverture franchie, date limite dépassée : l'aide est retombée en
        # « Disponibles bientôt », il n'y a rien à déposer.
        diag = _diagnostic(
            eligibles=[
                _match(
                    disponibilite="bientot",
                    date_ouverture="2026-08-30",
                    date_limite="2026-08-31",
                )
            ]
        )
        self.assertEqual(ouvertures_franchies(diag, TODAY), [])


class FormatsTests(unittest.TestCase):
    def test_date_en_francais_sans_dependre_de_la_locale(self) -> None:
        self.assertEqual(date_fr(date(2027, 3, 12)), "12 mars 2027")
        self.assertEqual(date_fr(date(2026, 8, 1)), "1 août 2026")

    def test_montant(self) -> None:
        self.assertEqual(montant_fr(120000), "120 000 €")
        self.assertIsNone(montant_fr(None))

    def test_jours(self) -> None:
        self.assertEqual(jours_fr(0), "aujourd'hui")
        self.assertEqual(jours_fr(1), "demain")
        self.assertEqual(jours_fr(30), "dans 30 jours")


class RenderTests(unittest.TestCase):
    def _bloc_echeances(self) -> BlocProjet:
        diag = _diagnostic(eligibles=[_match(nom="DRAC Toiture", date_limite="2026-09-21")])
        return BlocProjet(
            projet_titre="Réfection de la toiture",
            monument_nom="Église Saint-Pierre",
            projet_url="https://app.monumia.fr/app/projets/p1",
            echeances=tuple(echeances_a_rappeler(diag, TODAY, (30,))),
        )

    def _bloc_ouvertures(self) -> BlocProjet:
        diag = _diagnostic(
            atteignables=[
                _match(
                    nom="Fondation du Patrimoine",
                    statut="atteignable",
                    date_ouverture="2026-09-01",
                    date_limite="2026-11-30",
                )
            ]
        )
        return BlocProjet(
            projet_titre="Réfection de la toiture",
            monument_nom="Église Saint-Pierre",
            projet_url="https://app.monumia.fr/app/projets/p1",
            ouvertures=tuple(ouvertures_franchies(diag, TODAY)),
        )

    def test_echeances_nomme_le_chantier_laide_et_la_date(self) -> None:
        html = render_echeances_email(
            prenom="Marie",
            blocs=[self._bloc_echeances()],
            reglages_url="https://app.monumia.fr/app/profil",
        )
        self.assertIn("Bonjour Marie,", html)
        self.assertIn("Église Saint-Pierre", html)
        self.assertIn("Réfection de la toiture", html)
        self.assertIn("DRAC Toiture", html)
        self.assertIn("21 septembre 2026", html)
        self.assertIn("https://app.monumia.fr/app/projets/p1/aides/aide-test", html)

    def test_ouvertures_annonce_le_seau_darrivee(self) -> None:
        html = render_ouvertures_email(
            prenom="",
            blocs=[self._bloc_ouvertures()],
            reglages_url="https://app.monumia.fr/app/profil",
        )
        self.assertIn("Bonjour,", html)
        self.assertIn("À débloquer", html)
        self.assertIn("1 septembre 2026", html)
        self.assertIn("30 novembre 2026", html)

    def test_lien_de_reglage_present_dans_les_deux(self) -> None:
        for html in (
            render_echeances_email(
                prenom="Marie",
                blocs=[self._bloc_echeances()],
                reglages_url="https://app.monumia.fr/app/profil",
            ),
            render_ouvertures_email(
                prenom="Marie",
                blocs=[self._bloc_ouvertures()],
                reglages_url="https://app.monumia.fr/app/profil",
            ),
        ):
            self.assertIn("https://app.monumia.fr/app/profil", html)


if __name__ == "__main__":
    unittest.main()

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
    Disponibilite,
    EtatAide,
    comparer_catalogue,
    disponibilites_recentes,
    disponibles_pour_le_projet,
    echeances_a_rappeler,
    normaliser_paliers,
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


def _dispo(aide_id: str = "aide-test", nature: str = "ouverture", depuis: date = TODAY):
    return {aide_id: Disponibilite(aide_id=aide_id, nature=nature, depuis=depuis)}  # type: ignore[arg-type]


class InstantaneTests(unittest.TestCase):
    """L'état du catalogue, comparé d'un matin à l'autre."""

    HIER = date(2026, 8, 31)

    def _etat(self, ouverte: bool, entree_le=date(2026, 1, 1), ouverte_depuis=None) -> EtatAide:
        return EtatAide(ouverte=ouverte, entree_le=entree_le, ouverte_depuis=ouverte_depuis)

    def test_premier_passage_nannonce_rien(self) -> None:
        # Sans cette règle, le premier matin présenterait tout le catalogue
        # comme neuf.
        etat = comparer_catalogue({}, {"a": True, "b": False}, TODAY)
        self.assertEqual(set(etat), {"a", "b"})
        self.assertIsNone(etat["a"].ouverte_depuis)
        self.assertEqual(disponibilites_recentes(etat, TODAY), {})

    def test_nouvelle_aide_ouverte(self) -> None:
        etat = comparer_catalogue({"a": self._etat(True)}, {"a": True, "neuve": True}, TODAY)
        dispos = disponibilites_recentes(etat, TODAY)
        self.assertEqual(list(dispos), ["neuve"])
        self.assertEqual(dispos["neuve"].nature, "nouvelle")
        self.assertEqual(dispos["neuve"].depuis, TODAY)

    def test_nouvelle_aide_fermee_sannonce_a_son_ouverture(self) -> None:
        # Arrivée en « Disponibles bientôt » : rien à l'entrée...
        etat = comparer_catalogue({"a": self._etat(True)}, {"a": True, "neuve": False}, self.HIER)
        self.assertEqual(disponibilites_recentes(etat, self.HIER), {})
        # ... puis une annonce le jour où le guichet ouvre.
        etat = comparer_catalogue(etat, {"a": True, "neuve": True}, TODAY)
        dispos = disponibilites_recentes(etat, TODAY)
        self.assertEqual(dispos["neuve"].nature, "ouverture")

    def test_reouverture(self) -> None:
        # Fermée hier (session passée), rouverte aujourd'hui (la veille a posé
        # une nouvelle date limite) : peu importe qu'il n'y ait pas de
        # `date_ouverture`, la bascule suffit.
        etat = comparer_catalogue({"a": self._etat(False)}, {"a": True}, TODAY)
        dispos = disponibilites_recentes(etat, TODAY)
        self.assertEqual(dispos["a"], Disponibilite("a", "ouverture", TODAY))

    def test_rattrapage_dans_la_fenetre_puis_silence(self) -> None:
        etat = {"a": self._etat(True, ouverte_depuis=date(2026, 8, 28))}
        self.assertIn("a", disponibilites_recentes(etat, TODAY))
        self.assertEqual(disponibilites_recentes(etat, date(2026, 9, 30)), {})

    def test_fermeture_efface_la_date_douverture(self) -> None:
        etat = comparer_catalogue(
            {"a": self._etat(True, ouverte_depuis=self.HIER)}, {"a": False}, TODAY
        )
        self.assertEqual(etat["a"], self._etat(False))
        self.assertEqual(disponibilites_recentes(etat, TODAY), {})

    def test_aide_absente_garde_sa_ligne(self) -> None:
        # Retirée du catalogue servi : sa ligne reste, pour qu'un retour ne
        # passe pas pour une nouveauté.
        avant = {"a": self._etat(True), "retiree": self._etat(True)}
        etat = comparer_catalogue(avant, {"a": True}, TODAY)
        self.assertEqual(etat["retiree"], avant["retiree"])
        etat = comparer_catalogue(etat, {"a": True, "retiree": True}, date(2026, 9, 2))
        self.assertEqual(disponibilites_recentes(etat, date(2026, 9, 2)), {})


class DisponiblesPourLeProjetTests(unittest.TestCase):
    def test_aide_a_portee(self) -> None:
        diag = _diagnostic(potentiels=[_match(statut="potentiel", date_limite="2026-11-30")])
        (o,) = disponibles_pour_le_projet(diag, _dispo(nature="nouvelle"))
        self.assertEqual(o.nature, "nouvelle")
        self.assertEqual(o.statut, "potentiel")
        self.assertEqual(o.date_limite, date(2026, 11, 30))

    def test_les_trois_seaux_du_haut(self) -> None:
        diag = _diagnostic(
            eligibles=[_match(aide_id="e")],
            potentiels=[_match(aide_id="p", statut="potentiel")],
            atteignables=[_match(aide_id="t", statut="atteignable")],
        )
        dispos = {**_dispo("e"), **_dispo("p"), **_dispo("t")}
        self.assertEqual(
            sorted(o.aide_id for o in disponibles_pour_le_projet(diag, dispos)), ["e", "p", "t"]
        )

    def test_aide_ecartee_par_le_projet_ne_sannonce_pas(self) -> None:
        # Non éligible : un critère automatique ou une réponse déjà donnée
        # l'écarte. Pas d'email.
        diag = _diagnostic(non_eligibles=[_match(statut="non_eligible")])
        self.assertEqual(disponibles_pour_le_projet(diag, _dispo()), [])

    def test_aide_hors_disponibilites_ne_sannonce_pas(self) -> None:
        diag = _diagnostic(eligibles=[_match(aide_id="ancienne")])
        self.assertEqual(disponibles_pour_le_projet(diag, _dispo("autre")), [])

    def test_encore_fermee_pour_le_projet(self) -> None:
        diag = _diagnostic(eligibles=[_match(disponibilite="bientot")])
        self.assertEqual(disponibles_pour_le_projet(diag, _dispo()), [])

    def test_les_nouveautes_dabord(self) -> None:
        diag = _diagnostic(eligibles=[_match(aide_id="r", nom="A"), _match(aide_id="n", nom="B")])
        dispos = {**_dispo("r"), **_dispo("n", nature="nouvelle")}
        self.assertEqual([o.aide_id for o in disponibles_pour_le_projet(diag, dispos)], ["n", "r"])


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

    def _bloc_ouvertures(self, nature: str = "ouverture") -> BlocProjet:
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
            ouvertures=tuple(disponibles_pour_le_projet(diag, _dispo(nature=nature))),
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
        self.assertIn("Le dépôt vient d&#x27;ouvrir", html)
        self.assertIn("https://app.monumia.fr/app/projets/p1/aides/aide-test", html)

    def test_nouvelle_aide_se_dit_nouvelle(self) -> None:
        html = render_ouvertures_email(
            prenom="Marie",
            blocs=[self._bloc_ouvertures(nature="nouvelle")],
            reglages_url="https://app.monumia.fr/app/profil",
        )
        self.assertIn("Une nouvelle aide pour vos projets", html)
        self.assertIn("Nouvelle aide au catalogue", html)
        self.assertIn("https://app.monumia.fr/app/projets/p1/aides/aide-test", html)

    def test_les_saisies_utilisateur_sont_echappees(self) -> None:
        bloc = BlocProjet(
            projet_titre="<script>x</script>",
            monument_nom="Tour & Remparts",
            projet_url="https://app.monumia.fr/app/projets/p1",
            ouvertures=self._bloc_ouvertures().ouvertures,
        )
        html = render_ouvertures_email(
            prenom="Marie", blocs=[bloc], reglages_url="https://app.monumia.fr/app/profil"
        )
        self.assertNotIn("<script>", html)
        self.assertIn("Tour &amp; Remparts", html)

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

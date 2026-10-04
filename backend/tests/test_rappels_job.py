"""Tests de l'orchestration du job de rappels (scripts/rappels_aides.py).

La sélection des aides est testée à part (test_rappels_service). Ici on vérifie
ce que le job décide AUTOUR d'elle : le respect des préférences, l'offre du
compte, et le dédoublonnage — les trois endroits où une erreur envoie un email
de trop, ou un email à un compte qui n'a pas souscrit au service. Et, sur le
vrai moteur, à qui une aide nouvelle s'annonce.
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rappels_aides  # noqa: E402

from aides_schema import Aide, FactDef, load_facts, load_pending_facts  # noqa: E402
from services.rappels_service import Disponibilite  # noqa: E402

TODAY = date(2026, 9, 1)
APP_URL = "https://app.monumia.fr"

MONUMENT = {"id": "m1", "nom": "Église Saint-Pierre", "code_insee": "35238", "my_role": "owner"}
PROJET = {"id": "p1", "monument_id": "m1", "titre": "Réfection de la toiture", "questionnaire": {}}

# Une aide à J-30 (palier par défaut), devenue disponible ce matin.
DIAGNOSTIC = {
    "aidesEligibles": [
        {
            "statut": "eligible",
            "disponibilite": "maintenant",
            "aide": {
                "id": "drac-toiture",
                "nom": "DRAC Toiture",
                "dateLimite": "2026-10-01",
                "dateOuverture": "2026-09-01",
                "permanent": False,
                "montantMax": 50_000,
            },
        }
    ],
    "aidesPotentiellementEligibles": [],
    "aidesAtteignables": [],
    "aidesNonEligibles": [],
}


DISPOS = {"drac-toiture": Disponibilite("drac-toiture", "ouverture", TODAY)}


class CollecterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.droit = True
        self.deja: set[tuple] = set()

        patches = [
            patch.object(
                rappels_aides, "projets_de", return_value=([PROJET], {"m1": MONUMENT}, {})
            ),
            patch.object(rappels_aides, "rappels_deja_envoyes", side_effect=lambda *_: self.deja),
            patch.object(rappels_aides, "deterministic_diagnostic_for", return_value=DIAGNOSTIC),
            patch.object(
                rappels_aides, "compte_a_droit_aux_rappels", side_effect=lambda *_: self.droit
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _collecter(self, dispos=DISPOS, **prefs):
        user = {
            "id": "u1",
            "email": "marie@example.fr",
            "prenom": "Marie",
            "notification_preferences": prefs,
        }
        return rappels_aides.collecter(None, user, TODAY, APP_URL, dispos)

    def test_les_deux_familles_par_defaut(self) -> None:
        # Préférences vides = tout activé : un compte créé avant la migration
        # ne doit pas se retrouver privé de rappels.
        (bloc,), cles = self._collecter()
        self.assertEqual(len(bloc.echeances), 1)
        self.assertEqual(len(bloc.ouvertures), 1)
        self.assertEqual(len(cles), 2)
        self.assertEqual(bloc.projet_url, f"{APP_URL}/app/projets/p1")
        self.assertEqual(bloc.monument_nom, "Église Saint-Pierre")
        self.assertEqual(bloc.projet_id, "p1")

    def test_rien_de_disponible_ce_matin(self) -> None:
        (bloc,), _ = self._collecter(dispos={})
        self.assertEqual(len(bloc.echeances), 1)
        self.assertEqual(bloc.ouvertures, ())

    def test_nouvelle_aide_journalisee_comme_nouvelle(self) -> None:
        (bloc,), cles = self._collecter(
            dispos={"drac-toiture": Disponibilite("drac-toiture", "nouvelle", TODAY)}
        )
        self.assertEqual(bloc.ouvertures[0].nature, "nouvelle")
        self.assertIn(("p1", "drac-toiture", "nouvelle", None, "2026-09-01"), cles)

    def test_echeances_coupees(self) -> None:
        (bloc,), cles = self._collecter(rappelsEcheances=False)
        self.assertEqual(bloc.echeances, ())
        self.assertEqual(len(bloc.ouvertures), 1)
        self.assertEqual([c[2] for c in cles], ["ouverture"])

    def test_ouvertures_coupees(self) -> None:
        (bloc,), _ = self._collecter(rappelsOuvertures=False)
        self.assertEqual(len(bloc.echeances), 1)
        self.assertEqual(bloc.ouvertures, ())

    def test_tout_coupe_ne_lance_aucun_diagnostic(self) -> None:
        with patch.object(rappels_aides, "projets_de") as projets:
            resultat = self._collecter(rappelsEcheances=False, rappelsOuvertures=False)
        self.assertEqual(resultat, ([], []))
        projets.assert_not_called()

    def test_paliers_personnalises(self) -> None:
        # L'aide est à 30 jours : avec un seul palier à 7 jours, pas d'échéance.
        (bloc,), _ = self._collecter(rappelDelaisJours=[7])
        self.assertEqual(bloc.echeances, ())

    def test_offre_gratuite_ne_recoit_rien(self) -> None:
        # Les rappels sont vendus avec Veille et Multi-monuments. Sur l'offre
        # gratuite, on sort avant même de charger les chantiers : pas un
        # diagnostic n'est rejoué pour un compte qui ne recevra rien.
        self.droit = False
        with patch.object(rappels_aides, "projets_de") as projets:
            self.assertEqual(self._collecter(), ([], []))
        projets.assert_not_called()

    def test_loffre_ne_dispense_pas_des_preferences(self) -> None:
        # Avoir droit au service ne force pas l'envoi : le compte qui a tout
        # coupé reste silencieux, offre ou pas.
        self.droit = True
        self.assertEqual(self._collecter(rappelsEcheances=False, rappelsOuvertures=False), ([], []))

    def test_rappel_deja_envoye_ne_repart_pas(self) -> None:
        self.deja = {
            ("p1", "drac-toiture", "echeance", 30, "2026-10-01"),
            ("p1", "drac-toiture", "ouverture", None, "2026-09-01"),
        }
        self.assertEqual(self._collecter(), ([], []))

    def test_les_cles_journalisees_decrivent_ce_qui_est_parti(self) -> None:
        _, cles = self._collecter()
        self.assertIn(("p1", "drac-toiture", "echeance", 30, "2026-10-01"), cles)
        self.assertIn(("p1", "drac-toiture", "ouverture", None, "2026-09-01"), cles)

    def test_un_seul_envoi_puis_plus_rien_les_jours_suivants(self) -> None:
        # J-30 : le rappel part. Puis le job tourne chaque matin jusqu'à
        # l'échéance : à J-29, J-28… l'aide relève toujours du palier 30 et de
        # la même date limite, donc de la même clé, déjà journalisée. Même
        # chose pour l'annonce d'ouverture, rejouable 7 jours.
        _, cles = self._collecter()
        self.deja = set(cles)
        for decalage in range(1, 31):
            jour = date.fromordinal(TODAY.toordinal() + decalage)
            user = {"id": "u1", "email": "m@example.fr", "notification_preferences": {}}
            self.assertEqual(
                rappels_aides.collecter(None, user, jour, APP_URL, DISPOS),
                ([], []),
                f"un rappel repart le {jour}",
            )

    def test_apres_amorcage_un_rappel_neuf_part(self) -> None:
        # L'amorçage a journalisé l'aide de p1. Le lendemain, un projet p2
        # (nouveau compte, ou nouveau chantier) découvre la même aide à J-32 :
        # rien ce jour-là, puis le rappel part à J-30, car sa clé est neuve.
        self.deja = {("p1", "drac-toiture", "echeance", 30, "2026-10-01")}
        projet2 = {**PROJET, "id": "p2"}
        user = {"id": "u1", "email": "m@example.fr", "notification_preferences": {}}
        with patch.object(
            rappels_aides, "projets_de", return_value=([PROJET, projet2], {"m1": MONUMENT}, {})
        ):
            self.assertEqual(
                rappels_aides.collecter(None, user, date(2026, 8, 30), APP_URL, {}), ([], [])
            )
            (bloc,), cles = rappels_aides.collecter(None, user, date(2026, 9, 1), APP_URL, {})
        self.assertEqual(bloc.projet_id, "p2")
        self.assertEqual(cles, [("p2", "drac-toiture", "echeance", 30, "2026-10-01")])

    def test_un_nouveau_palier_repart_une_fois(self) -> None:
        # Avec 30 ET 7 jours : le rappel de J-30 ne bloque pas celui de J-7,
        # qui a sa propre clé.
        self.deja = {("p1", "drac-toiture", "echeance", 30, "2026-10-01")}
        user = {
            "id": "u1",
            "email": "m@example.fr",
            "notification_preferences": {"rappelDelaisJours": [30, 7]},
        }
        (bloc,), cles = rappels_aides.collecter(None, user, date(2026, 9, 24), APP_URL, {})
        self.assertEqual([e.palier_jours for e in bloc.echeances], [7])
        self.assertEqual(cles, [("p1", "drac-toiture", "echeance", 7, "2026-10-01")])


class TraiterTests(unittest.TestCase):
    """Le dry-run n'écrit ni n'envoie, et le journal ne s'écrit qu'après l'envoi."""

    def setUp(self) -> None:
        self.user = {"id": "u1", "email": "marie@example.fr", "prenom": "Marie"}
        bloc = rappels_aides.BlocProjet(
            projet_titre="Toiture",
            monument_nom="Église",
            projet_url=f"{APP_URL}/app/projets/p1",
            echeances=tuple(
                rappels_aides.echeances_a_rappeler(DIAGNOSTIC, TODAY, (30,)),
            ),
        )
        patches = [
            patch.object(
                rappels_aides,
                "collecter",
                return_value=([bloc], [("p1", "drac-toiture", "echeance", 30, "2026-10-01")]),
            ),
            patch.object(rappels_aides, "send_rappel_email"),
            patch.object(rappels_aides, "journaliser"),
            patch.object(rappels_aides, "notifier_in_app"),
        ]
        self.mocks = {}
        for p in patches:
            self.mocks[p.attribute] = p.start()
            self.addCleanup(p.stop)

    def test_dry_run_nenvoie_rien(self) -> None:
        n_e, n_o = rappels_aides.traiter(
            None, self.user, TODAY, APP_URL, dry_run=True, disponibilites={}
        )
        self.assertEqual((n_e, n_o), (1, 0))
        self.mocks["send_rappel_email"].assert_not_called()
        self.mocks["journaliser"].assert_not_called()

    def test_envoi_puis_journalisation(self) -> None:
        rappels_aides.traiter(None, self.user, TODAY, APP_URL, dry_run=False, disponibilites={})
        self.mocks["send_rappel_email"].assert_called_once()
        self.mocks["notifier_in_app"].assert_called_once()
        self.mocks["journaliser"].assert_called_once()

    def test_un_seul_email_pour_tout_le_compte(self) -> None:
        # Deux chantiers, des échéances et des aides devenues disponibles :
        # tout part dans UN email, dont l'objet dit les deux.
        echeances = rappels_aides.echeances_a_rappeler(DIAGNOSTIC, TODAY, (30,))
        ouvertures = rappels_aides.disponibles_pour_le_projet(DIAGNOSTIC, DISPOS)
        blocs = [
            rappels_aides.BlocProjet(
                projet_titre="Toiture",
                monument_nom="Église",
                projet_url=f"{APP_URL}/app/projets/p1",
                echeances=tuple(echeances),
                ouvertures=tuple(ouvertures),
            ),
            rappels_aides.BlocProjet(
                projet_titre="Clocher",
                monument_nom="Église",
                projet_url=f"{APP_URL}/app/projets/p2",
                ouvertures=tuple(ouvertures),
            ),
        ]
        self.mocks["collecter"].return_value = (blocs, [])
        n_e, n_o = rappels_aides.traiter(
            None, self.user, TODAY, APP_URL, dry_run=False, disponibilites={}
        )
        self.assertEqual((n_e, n_o), (1, 2))
        self.mocks["send_rappel_email"].assert_called_once()
        envoi = self.mocks["send_rappel_email"].call_args.kwargs
        self.assertEqual(envoi["subject"], "Du nouveau sur les aides de vos projets")
        self.assertIn("Toiture", envoi["html"])
        self.assertIn("Clocher", envoi["html"])

    def test_amorcer_journalise_sans_envoyer(self) -> None:
        # Mise en service : les rappels dus aujourd'hui sont tenus pour
        # envoyés. Aucun email, aucune notification, mais le journal est
        # écrit, donc ils ne partiront pas demain non plus.
        n_e, n_o = rappels_aides.traiter(
            None, self.user, TODAY, APP_URL, dry_run=False, disponibilites={}, amorcer=True
        )
        self.assertEqual((n_e, n_o), (1, 0))
        self.mocks["send_rappel_email"].assert_not_called()
        self.mocks["notifier_in_app"].assert_not_called()
        self.mocks["journaliser"].assert_called_once_with(
            None, "u1", [("p1", "drac-toiture", "echeance", 30, "2026-10-01")]
        )

    def test_un_echec_denvoi_laisse_le_rappel_repartir_demain(self) -> None:
        self.mocks["send_rappel_email"].side_effect = RuntimeError("Resend HS")
        with self.assertRaises(RuntimeError):
            rappels_aides.traiter(None, self.user, TODAY, APP_URL, dry_run=False, disponibilites={})
        self.mocks["journaliser"].assert_not_called()

    def test_compte_sans_email(self) -> None:
        n_e, n_o = rappels_aides.traiter(
            None,
            {"id": "u1", "email": "", "prenom": ""},
            TODAY,
            APP_URL,
            dry_run=False,
            disponibilites={},
        )
        self.assertEqual((n_e, n_o), (0, 0))
        self.mocks["send_rappel_email"].assert_not_called()
        self.mocks["journaliser"].assert_not_called()


# ---------------------------------------------------------------------------
# Sur le vrai moteur : à qui une aide nouvelle s'annonce
# ---------------------------------------------------------------------------

SLUG_YONNE = "fx-yonne-prives"
FAIT_NEWSLETTER = "fx_newsletter_mensuelle"


def _aide_yonne() -> Aide:
    """Une aide du département de l'Yonne, réservée aux propriétaires privés,
    pour des travaux pas encore commencés, et qui exige un engagement que seule
    elle demande (le fait propre à une aide toute neuve)."""
    return Aide.model_validate(
        {
            "slug": SLUG_YONNE,
            "nom": "Aide de l'Yonne aux monuments privés",
            "organisme": "Département de l'Yonne",
            "categorie": "departement",
            "type": "subvention",
            "description": "d",
            "conditions": [
                {
                    "id": "dep",
                    "text": "Monument situé dans l'Yonne",
                    "kind": "auto",
                    "effect": "gate",
                    "field": "monument.departement_num",
                    "predicate": {"eq": "89"},
                },
                {
                    "id": "prive",
                    "text": "Propriétaire privé",
                    "kind": "auto",
                    "effect": "gate",
                    "field": "monument.proprietaire",
                    "predicate": {"in": ["prive_personne_physique"]},
                },
                {
                    "id": "travaux",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "etat_travaux",
                    "predicate": {"eq": "non_commences"},
                },
                {
                    "id": "newsletter",
                    "text": "S'engager à publier une lettre d'information mensuelle",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": FAIT_NEWSLETTER,
                    "predicate": {"eq": True},
                },
            ],
        }
    )


class AnnonceNouvelleAideTests(unittest.TestCase):
    """Une aide nouvelle s'annonce à tout projet dont elle passe les critères
    automatiques, sauf si une réponse déjà donnée l'écarte. Ce qui n'a jamais
    été demandé (le fait propre à l'aide) ne retient pas l'annonce."""

    def setUp(self) -> None:
        facts = {
            **load_facts(),
            **load_pending_facts(),
            FAIT_NEWSLETTER: FactDef.model_validate(
                {
                    "type": "boolean",
                    "scope": "projet",
                    "question": "Publierez-vous une lettre d'information mensuelle ?",
                }
            ),
        }
        self.monument = {
            "id": "m1",
            "nom": "Maison forte de Test",
            "code_insee": "89024",
            "departement_num": "89",
            "region": "bourgogne-franche-comte",
            "protection": "inscrit",
            "proprietaire": ["prive_personne_physique"],
            "my_role": "owner",
        }
        self.projet = {"id": "p1", "monument_id": "m1", "titre": "Toiture", "questionnaire": {}}
        patches = [
            patch("routers.aides.load_all_aides", return_value={SLUG_YONNE: _aide_yonne()}),
            patch("routers.aides.load_facts", return_value=facts),
            patch("routers.aides.load_pending_facts", return_value={}),
            patch.object(
                rappels_aides,
                "projets_de",
                side_effect=lambda *_: ([self.projet], {"m1": self.monument}, {}),
            ),
            patch.object(rappels_aides, "rappels_deja_envoyes", return_value=set()),
            patch.object(rappels_aides, "compte_a_droit_aux_rappels", return_value=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _annoncees(self) -> list[str]:
        user = {"id": "u1", "email": "a@example.fr", "notification_preferences": {}}
        dispos = {SLUG_YONNE: Disponibilite(SLUG_YONNE, "nouvelle", TODAY)}
        blocs, _ = rappels_aides.collecter(None, user, TODAY, APP_URL, dispos)
        return [o.aide_id for b in blocs for o in b.ouvertures]

    def test_prive_dans_lyonne_sans_reponse(self) -> None:
        self.assertEqual(self._annoncees(), [SLUG_YONNE])

    def test_travaux_non_commences_declares(self) -> None:
        self.projet["questionnaire"] = {"etat_travaux": "non_commences"}
        self.assertEqual(self._annoncees(), [SLUG_YONNE])

    def test_travaux_acheves_ecartent_laide(self) -> None:
        self.projet["questionnaire"] = {"etat_travaux": "acheves"}
        self.assertEqual(self._annoncees(), [])

    def test_hors_de_lyonne(self) -> None:
        self.monument["departement_num"] = "21"
        self.assertEqual(self._annoncees(), [])

    def test_commune_proprietaire(self) -> None:
        self.monument["proprietaire"] = ["commune"]
        self.assertEqual(self._annoncees(), [])

    def test_un_des_proprietaires_suffit(self) -> None:
        self.monument["proprietaire"] = ["commune", "prive_personne_physique"]
        self.assertEqual(self._annoncees(), [SLUG_YONNE])


if __name__ == "__main__":
    unittest.main()

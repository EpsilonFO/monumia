"""L'avis envoyé à l'équipe quand un compte est créé.

Ce qui est figé ici :

  * les quatre chemins d'inscription mettent l'avis en file, une seule fois ;
  * une réinscription d'adresse non confirmée et une double soumission OAuth
    (ligne déjà là, ou course perdue) n'en envoient pas un second ;
  * sans `NOTIF_INSCRIPTION_TO`, rien ne part ; une panne de Resend ne remonte
    pas ;
  * tout ce qui vient du formulaire est échappé dans le HTML.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks, Response

from routers.auth import (
    RegisterCollaboratorOauthRequest,
    RegisterCollaboratorRequest,
    RegisterOauthRequest,
    RegisterRequest,
    register,
    register_collaborator,
    register_collaborator_oauth,
    register_oauth,
)
from services.email_service import (
    Inscription,
    render_inscription_email,
    send_inscription_email,
    sujet_inscription,
)
from tests.test_offre_a_la_creation import AUTH_USER, _anon, _base, _FakeSupabase


def _inscriptions(taches: BackgroundTasks) -> list[Inscription]:
    """Les avis mis en file par la route (les tâches ne tournent qu'après la
    réponse, donc rien n'est envoyé pendant le test)."""
    return [t.args[0] for t in taches.tasks if t.func is send_inscription_email]


INSCRIPTION = Inscription(
    email="marie@exemple.fr",
    prenom="Marie",
    nom="Dupont",
    telephone="06 12 34 56 78",
    metier=None,
    connexion="mot de passe",
)


class AvisSurLesQuatreInscriptionsTest(unittest.TestCase):
    def test_inscription_par_mot_de_passe(self):
        taches = BackgroundTasks()
        register(
            body=RegisterRequest(
                email="marie@exemple.fr",
                password="motdepasse1",
                prenom="Marie",
                nom="Dupont",
                telephone="06 12 34 56 78",
            ),
            response=Response(),
            background_tasks=taches,
            anon=_anon(),
            supabase=_base(),
        )
        (avis,) = _inscriptions(taches)
        self.assertEqual(avis, INSCRIPTION)

    def test_inscription_collaborateur(self):
        taches = BackgroundTasks()
        register_collaborator(
            body=RegisterCollaboratorRequest(
                email="marie@exemple.fr",
                password="motdepasse1",
                prenom="Marie",
                nom="Dupont",
                metier="architecte",
            ),
            response=Response(),
            background_tasks=taches,
            anon=_anon(),
            supabase=_base(),
        )
        (avis,) = _inscriptions(taches)
        self.assertEqual(avis.metier, "architecte")
        self.assertEqual(avis.connexion, "mot de passe")

    def test_inscription_oauth(self):
        taches = BackgroundTasks()
        register_oauth(
            RegisterOauthRequest(prenom="Marie", nom="Dupont"),
            background_tasks=taches,
            auth_user=AUTH_USER,
            supabase=_FakeSupabase({"users": []}),
        )
        (avis,) = _inscriptions(taches)
        # L'adresse vient du jeton, pas du formulaire.
        self.assertEqual(avis.email, "marie@exemple.fr")
        self.assertEqual(avis.connexion, "Google")

    def test_inscription_collaborateur_oauth(self):
        taches = BackgroundTasks()
        register_collaborator_oauth(
            RegisterCollaboratorOauthRequest(prenom="Marie", nom="Dupont", metier="architecte"),
            background_tasks=taches,
            auth_user=AUTH_USER,
            supabase=_FakeSupabase({"users": []}),
        )
        (avis,) = _inscriptions(taches)
        self.assertEqual(avis.metier, "architecte")
        self.assertEqual(avis.connexion, "Google")


class PasDeDoubleAvisTest(unittest.TestCase):
    def test_reinscription_d_une_adresse_non_confirmee(self):
        # Le profil existe déjà : Supabase a seulement relancé l'email.
        taches = BackgroundTasks()
        register(
            body=RegisterRequest(
                email="marie@exemple.fr", password="motdepasse1", prenom="Marie", nom="Dupont"
            ),
            response=Response(),
            background_tasks=taches,
            anon=_anon(),
            supabase=_FakeSupabase({"users": [{"id": "user-1", "email": "marie@exemple.fr"}]}),
        )
        self.assertEqual(_inscriptions(taches), [])

    def test_profil_oauth_deja_cree(self):
        taches = BackgroundTasks()
        register_oauth(
            RegisterOauthRequest(prenom="Marie", nom="Dupont"),
            background_tasks=taches,
            auth_user=AUTH_USER,
            supabase=_FakeSupabase({"users": [{"id": "user-1", "email": "marie@exemple.fr"}]}),
        )
        self.assertEqual(_inscriptions(taches), [])

    def test_course_oauth_perdue(self):
        # L'autre soumission a inséré la ligne entre la lecture et l'insert.
        supabase = MagicMock()
        users = supabase.table.return_value
        users.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            None
        )
        users.insert.return_value.execute.side_effect = Exception("duplicate key")
        taches = BackgroundTasks()
        register_oauth(
            RegisterOauthRequest(prenom="Marie", nom="Dupont"),
            background_tasks=taches,
            auth_user=AUTH_USER,
            supabase=supabase,
        )
        self.assertEqual(_inscriptions(taches), [])


class EnvoiTest(unittest.TestCase):
    def test_sans_destinataire_rien_ne_part(self):
        with (
            patch.dict(os.environ, {"NOTIF_INSCRIPTION_TO": "", "RESEND_API_KEY": "re_x"}),
            patch("resend.Emails.send") as envoi,
        ):
            send_inscription_email(INSCRIPTION)
        envoi.assert_not_called()

    def test_envoi_a_l_equipe_avec_reponse_a_l_inscrit(self):
        env = {
            "NOTIF_INSCRIPTION_TO": "contact@monumia.fr",
            "RESEND_API_KEY": "re_x",
            "FRONTEND_URL": "https://app.monumia.fr",
        }
        with patch.dict(os.environ, env), patch("resend.Emails.send") as envoi:
            send_inscription_email(INSCRIPTION)
        (message,) = envoi.call_args.args
        self.assertEqual(message["to"], ["contact@monumia.fr"])
        self.assertEqual(message["reply_to"], "marie@exemple.fr")
        self.assertEqual(message["subject"], "Nouvelle inscription sur Monumia : Marie Dupont")

    def test_une_panne_de_resend_ne_remonte_pas(self):
        env = {"NOTIF_INSCRIPTION_TO": "contact@monumia.fr", "RESEND_API_KEY": "re_x"}
        with (
            patch.dict(os.environ, env),
            patch("resend.Emails.send", side_effect=RuntimeError("503")),
            self.assertLogs("services.email_service", level="ERROR"),
        ):
            send_inscription_email(INSCRIPTION)


class RenduTest(unittest.TestCase):
    def test_hors_production_l_objet_le_dit(self):
        self.assertEqual(
            sujet_inscription(INSCRIPTION, "beta.monumia.fr"),
            "[beta.monumia.fr] Nouvelle inscription sur Monumia : Marie Dupont",
        )

    def test_collaborateur(self):
        collab = Inscription(**{**INSCRIPTION.__dict__, "metier": "architecte"})
        self.assertEqual(
            sujet_inscription(collab, None), "Nouveau collaborateur sur Monumia : Marie Dupont"
        )
        self.assertIn("collaborateur invité (architecte)", self._html(collab))

    def test_le_formulaire_est_echappe(self):
        piege = Inscription(**{**INSCRIPTION.__dict__, "nom": "<script>x</script>"})
        html = self._html(piege)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_adresse_non_confirmee_signalee_pour_un_mot_de_passe(self):
        self.assertIn("pas encore confirmée", self._html(INSCRIPTION))
        google = Inscription(**{**INSCRIPTION.__dict__, "connexion": "Google"})
        self.assertNotIn("pas encore confirmée", self._html(google))

    def _html(self, inscription: Inscription) -> str:
        return render_inscription_email(
            inscription=inscription, admin_url="https://app.monumia.fr/admin"
        )


if __name__ == "__main__":
    unittest.main()

"""L'offre offerte à la création d'un compte.

Depuis le 2026-09-07, tout compte NEUF reçoit Multi-monuments d'office : une
ligne d'abonnement `active` sans contrepartie Stripe, posée par la route
d'inscription. Ce qui est figé ici :

  * les quatre chemins d'inscription l'octroient (mot de passe, collaborateur,
    et leurs deux miroirs OAuth) — en oublier un donnerait deux catégories de
    comptes selon la façon de s'inscrire ;
  * la ligne écrite rend bien l'offre Multi-monuments quand `offre_du_compte`
    la relit, sans faire croire à un client Stripe (« Gérer mon abonnement »
    mènerait à un 404) ;
  * un échec d'écriture ne fait pas échouer la création du compte.
"""

import unittest
from types import SimpleNamespace
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
from services import offres
from services import stripe_billing as billing


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Chaînage fluent minimal : les lectures répondent des lignes, les
    écritures sont journalisées dans `writes`."""

    def __init__(self, table, rows, writes, erreur=None):
        self._table = table
        self._rows = rows
        self._writes = writes
        self._erreur = erreur
        self._op = "select"
        self._payload = None
        self._single = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload, *a, **k):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, *a, **k):
        self._op, self._payload = "upsert", payload
        return self

    def execute(self):
        if self._op != "select":
            self._writes.append((self._table, self._op, self._payload))
            if self._erreur is not None:
                raise self._erreur
            # La ligne insérée doit être relue ensuite : `_get_profile` lit le
            # profil juste après l'avoir créé.
            self._rows.append(self._payload)
            return _Resp([self._payload])
        if self._single:
            return _Resp(self._rows[0] if self._rows else None)
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, tables=None, erreurs=None):
        self.tables = tables or {}
        self.erreurs = erreurs or {}
        self.writes: list = []

    def table(self, name):
        rows = self.tables.setdefault(name, [])
        return _Query(name, rows, self.writes, self.erreurs.get(name))

    def abonnements_ecrits(self) -> list[dict]:
        return [payload for table, _, payload in self.writes if table == "subscriptions"]


AUTH_USER = SimpleNamespace(id="user-1", email="marie@exemple.fr", user_metadata={})


def _anon(user_id: str = "user-1"):
    """Client anon dont `sign_up` réussit, comme après une vraie inscription."""
    anon = MagicMock()
    anon.auth.sign_up.return_value = SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        session=SimpleNamespace(access_token="jwt", refresh_token="refresh"),
    )
    return anon


def _base(**tables) -> _FakeSupabase:
    """Base d'une inscription : `users` est VIDE.

    C'est l'état réel avant un `insert` de profil, et `register` en dépend
    désormais — il vérifie qu'aucun profil n'existe (réinscription d'une
    adresse jamais confirmée). Le faux client ajoute la ligne écrite à ses
    lignes lisibles, donc `_get_profile` la relit juste après.
    """
    return _FakeSupabase({"users": [], **tables})


class OctroiSurLesQuatreInscriptionsTest(unittest.TestCase):
    def test_inscription_par_mot_de_passe(self):
        supabase = _base()
        register(
            body=RegisterRequest(
                email="marie@exemple.fr", password="motdepasse1", prenom="Marie", nom="Dupont"
            ),
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_anon(),
            supabase=supabase,
        )
        (abonnement,) = supabase.abonnements_ecrits()
        self.assertEqual(abonnement["plan"], offres.PLAN_MULTI_MONUMENTS)
        self.assertEqual(abonnement["status"], "active")
        self.assertEqual(abonnement["user_id"], "user-1")

    def test_inscription_collaborateur(self):
        supabase = _base()
        register_collaborator(
            body=RegisterCollaboratorRequest(
                email="marie@exemple.fr",
                password="motdepasse1",
                prenom="Marie",
                nom="Dupont",
                metier="architecte",
            ),
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_anon(),
            supabase=supabase,
        )
        (abonnement,) = supabase.abonnements_ecrits()
        self.assertEqual(abonnement["plan"], offres.PLAN_MULTI_MONUMENTS)

    def test_inscription_oauth(self):
        # Compte auth existant (Google) mais aucun profil : la route le crée.
        supabase = _FakeSupabase({"users": []})
        register_oauth(
            RegisterOauthRequest(prenom="Marie", nom="Dupont"),
            background_tasks=BackgroundTasks(),
            auth_user=AUTH_USER,
            supabase=supabase,
        )
        (abonnement,) = supabase.abonnements_ecrits()
        self.assertEqual(abonnement["plan"], offres.PLAN_MULTI_MONUMENTS)

    def test_inscription_collaborateur_oauth(self):
        supabase = _FakeSupabase({"users": []})
        register_collaborator_oauth(
            RegisterCollaboratorOauthRequest(prenom="Marie", nom="Dupont", metier="architecte"),
            background_tasks=BackgroundTasks(),
            auth_user=AUTH_USER,
            supabase=supabase,
        )
        (abonnement,) = supabase.abonnements_ecrits()
        self.assertEqual(abonnement["plan"], offres.PLAN_MULTI_MONUMENTS)


class FormeDeLaLigneOctroyeeTest(unittest.TestCase):
    def test_ni_client_ni_prix_ni_echeance(self):
        supabase = _FakeSupabase()
        billing.octroyer_offre_initiale(supabase, "user-1")
        (abonnement,) = supabase.abonnements_ecrits()
        # Pas de Customer Stripe : `access.portail` reste faux, donc le front
        # ne propose pas un portail de facturation qui répondrait 404.
        self.assertEqual(abonnement["stripe_customer_id"], "")
        self.assertIsNone(abonnement["stripe_price_id"])
        self.assertIsNone(abonnement["current_period_end"])
        self.assertFalse(abonnement["cancel_at_period_end"])

    def test_cle_derivee_du_compte_donc_idempotente(self):
        supabase = _FakeSupabase()
        billing.octroyer_offre_initiale(supabase, "user-1")
        billing.octroyer_offre_initiale(supabase, "user-1")
        premier, second = supabase.abonnements_ecrits()
        self.assertEqual(premier["stripe_subscription_id"], second["stripe_subscription_id"])
        # Aucun id Stripe ne commence par ce préfixe : un webhook ne peut pas
        # écraser la ligne, ni la ligne masquer un abonnement payé.
        self.assertTrue(premier["stripe_subscription_id"].startswith(billing.PREFIXE_OCTROI))
        self.assertNotIn("sub_", premier["stripe_subscription_id"])

    def test_le_compte_lit_bien_multi_monuments(self):
        """La ligne écrite doit se relire en droits, pas seulement en base."""
        supabase = _FakeSupabase()
        billing.octroyer_offre_initiale(supabase, "user-1")
        (abonnement,) = supabase.abonnements_ecrits()

        relecture = _FakeSupabase({"subscriptions": [abonnement]})
        offre = billing.offre_du_compte(relecture, "user-1")
        self.assertEqual(offre, offres.MULTI_MONUMENTS)
        self.assertIsNone(offre.monuments_max)
        self.assertIsNone(offre.projets_max)
        self.assertTrue(offre.dashboard)
        self.assertTrue(offre.equipe)
        self.assertTrue(offre.echeancier)
        self.assertTrue(offre.rappels_email)
        self.assertTrue(offre.aides_bientot)
        self.assertTrue(billing.peut_recevoir_rappels(relecture, "user-1"))


class RobustesseTest(unittest.TestCase):
    def test_un_echec_d_octroi_ne_casse_pas_l_inscription(self):
        """Le compte doit exister même si l'octroi échoue : l'offre gratuite
        reste un état utilisable, un 500 à l'inscription non."""
        supabase = _FakeSupabase(
            {"users": []}, erreurs={"subscriptions": Exception("base indisponible")}
        )
        resultat = register(
            body=RegisterRequest(
                email="marie@exemple.fr", password="motdepasse1", prenom="Marie", nom="Dupont"
            ),
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_anon(),
            supabase=supabase,
        )
        self.assertEqual(resultat["user"]["prenom"], "Marie")

    def test_octroi_refermable(self):
        """Remettre `PLAN_A_LA_CREATION` à None coupe l'octroi sans autre
        changement — et sans toucher aux comptes déjà ouverts."""
        supabase = _FakeSupabase()
        with patch.object(billing, "PLAN_A_LA_CREATION", None):
            billing.octroyer_offre_initiale(supabase, "user-1")
        self.assertEqual(supabase.abonnements_ecrits(), [])


if __name__ == "__main__":
    unittest.main()

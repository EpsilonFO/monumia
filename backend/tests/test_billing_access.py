"""Tests des offres, de leurs garde-fous et du webhook Stripe.

Trois familles de risques sont couvertes ici, parce qu'elles coûtent de l'argent
ou de la confiance :

  • un droit accordé à tort (service payant offert) ou refusé à tort (client qui
    paye et se voit bloqué) ;
  • un plafond contournable — la seule frontière qui tienne est côté serveur,
    masquer un bouton ne protège rien ;
  • un webhook qui encaisse sans ouvrir l'offre — signature acceptée à tort,
    offre non identifiée, ou événement rejoué qui saute le traitement.

Les fakes miment supabase-py comme dans test_refresh_cookie.py : chaînage
fluide, `execute()` qui rend une réponse préparée. Celui-ci applique VRAIMENT
`eq` et `in_` : dès qu'un test distingue le propriétaire qui paye du
collaborateur qui regarde, ignorer les filtres rendrait le test faux plutôt que
simplement approximatif.
"""

import base64
import hashlib
import hmac
import json
import time
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from db import get_supabase
from main import app
from routers import aides as aides_router
from routers import billing as billing_router
from services import offres, quotas
from services import stripe_billing as billing

WEBHOOK_SECRET = "whsec_test_secret"


def _fake_jwt(sub: str = "user-1") -> str:
    def b64(payload: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    header = b64({"alg": "ES256", "kid": "test-key", "typ": "JWT"})
    return f"{header}.{b64({'sub': sub, 'aud': 'authenticated'})}.c2ln"


# ---------------------------------------------------------------------------
# Base factice
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Requête fluide qui filtre pour de vrai et note les écritures."""

    def __init__(self, table: str, rows: list, writes: list, insert_error: Exception | None):
        self._table = table
        self._rows = rows
        self._writes = writes
        self._insert_error = insert_error
        self._single = False
        self._limit: int | None = None
        self._op = "select"
        self._payload = None

    # --- lecture ---
    def select(self, *a, **k):
        return self

    def eq(self, column, value):
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        allowed = set(values)
        self._rows = [r for r in self._rows if r.get(column) in allowed]
        return self

    def is_(self, column, _value):
        self._rows = [r for r in self._rows if r.get(column) is None]
        return self

    def order(self, column, desc: bool = False):
        self._rows = sorted(self._rows, key=lambda r: str(r.get(column) or ""), reverse=desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    # --- écriture ---
    def insert(self, payload, *a, **k):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, *a, **k):
        self._op, self._payload = "upsert", payload
        return self

    def update(self, payload, *a, **k):
        self._op, self._payload = "update", payload
        return self

    def delete(self, *a, **k):
        self._op = "delete"
        return self

    def execute(self):
        if self._op != "select":
            self._writes.append((self._table, self._op, self._payload))
            if self._op == "insert" and self._insert_error is not None:
                raise self._insert_error
            return _Resp([self._payload] if self._payload else [])
        rows = self._rows if self._limit is None else self._rows[: self._limit]
        if self._single:
            return _Resp(rows[0] if rows else None)
        return _Resp(list(rows))


class _FakeSupabase:
    """Base factice pilotée par un dict {table: lignes}."""

    def __init__(self, tables: dict, insert_errors: dict | None = None):
        self.tables = tables
        self.insert_errors = insert_errors or {}
        self.writes: list = []

    def table(self, name):
        return _Query(
            name, list(self.tables.get(name, [])), self.writes, self.insert_errors.get(name)
        )


def _abonnement(user_id: str, plan: str | None, **overrides) -> dict:
    row = {
        "user_id": user_id,
        "stripe_subscription_id": f"sub_{user_id}_{plan}",
        "stripe_customer_id": "cus_1",
        "stripe_price_id": None,
        "plan": plan,
        "status": "active",
        "created_at": "2026-09-01T00:00:00+00:00",
        "current_period_end": "2026-10-01T00:00:00+00:00",
        "cancel_at_period_end": False,
    }
    row.update(overrides)
    return row


def _tables(**overrides) -> dict:
    """Un monument `mon-1` appartenant à `owner`, un projet, rien de payé."""
    tables: dict = {
        "users": [{"id": "owner"}, {"id": "collab"}],
        "subscriptions": [],
        "monuments": [{"id": "mon-1", "user_id": "owner"}],
        "projets": [{"id": "prj-1", "monument_id": "mon-1"}],
        "project_members": [{"monument_id": "mon-1", "user_id": "collab", "role": "co_owner"}],
        "stripe_events": [],
    }
    tables.update(overrides)
    return tables


# ---------------------------------------------------------------------------
# La table des offres — pure, sans base
# ---------------------------------------------------------------------------


class TableDesOffresTest(unittest.TestCase):
    """Fige ce que chaque offre ouvre. Le miroir de ces assertions vit dans
    frontend/src/lib/__tests__/offres.test.ts : les deux tables doivent dire la
    même chose, sinon le front montre un bouton que le serveur refuse."""

    def test_gratuit(self):
        o = offres.offre_pour(())
        self.assertEqual(o.monuments_max, 1)
        self.assertEqual(o.projets_max, 2)
        self.assertFalse(o.dashboard)
        self.assertFalse(o.equipe)
        self.assertFalse(o.suppression_monument)
        self.assertFalse(o.suppression_projet)
        self.assertFalse(o.aides_bientot)
        self.assertFalse(o.echeancier)
        self.assertFalse(o.rappels_email)

    def test_veille_ouvre_le_calendrier_l_equipe_et_les_projets(self):
        o = offres.offre_pour({offres.PLAN_VEILLE})
        self.assertIsNone(o.projets_max)
        self.assertTrue(o.equipe)
        self.assertTrue(o.suppression_projet)
        self.assertTrue(o.aides_bientot)
        self.assertTrue(o.echeancier)
        self.assertTrue(o.rappels_email)
        # Ce que Veille ne donne PAS : un second monument, et le tableau de bord.
        self.assertEqual(o.monuments_max, 1)
        self.assertFalse(o.suppression_monument)
        self.assertFalse(o.dashboard)

    def test_multi_monuments_contient_veille(self):
        o = offres.offre_pour({offres.PLAN_MULTI_MONUMENTS})
        self.assertIsNone(o.monuments_max)
        self.assertIsNone(o.projets_max)
        self.assertTrue(o.dashboard)
        self.assertTrue(o.equipe)
        self.assertTrue(o.suppression_monument)
        self.assertTrue(o.suppression_projet)
        self.assertTrue(o.aides_bientot)
        self.assertTrue(o.echeancier)
        self.assertTrue(o.rappels_email)

    def test_cumul_ne_retire_rien(self):
        """Le temps d'une montée en gamme, les deux abonnements coexistent."""
        cumul = offres.offre_pour({offres.PLAN_VEILLE, offres.PLAN_MULTI_MONUMENTS})
        self.assertEqual(cumul, offres.offre_pour({offres.PLAN_MULTI_MONUMENTS}))
        self.assertEqual(cumul.nom, "Multi-monuments")

    def test_plan_inconnu_n_ouvre_rien(self):
        """Un abonnement antérieur aux trois offres (plan NULL) ne donne aucun
        droit : c'était la décision de couper l'accès legacy."""
        self.assertEqual(offres.offre_pour({"abonnement"}), offres.GRATUIT)
        self.assertEqual(offres.offre_pour(None), offres.GRATUIT)

    def test_plan_seul_accepte_comme_ensemble(self):
        self.assertEqual(offres.offre_pour(offres.PLAN_VEILLE), offres.VEILLE)


# ---------------------------------------------------------------------------
# Les offres détenues par un compte
# ---------------------------------------------------------------------------


class PlansDetenusTest(unittest.TestCase):
    def test_compte_neuf_est_au_gratuit(self):
        db = _FakeSupabase(_tables())
        self.assertEqual(billing.active_plans(db, "owner"), set())
        self.assertEqual(billing.offre_du_compte(db, "owner"), offres.GRATUIT)

    def test_abonnement_actif_donne_son_offre(self):
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        self.assertEqual(billing.active_plans(db, "owner"), {"veille"})
        self.assertTrue(billing.offre_du_compte(db, "owner").echeancier)

    def test_impaye_conserve_l_offre_le_temps_des_relances(self):
        db = _FakeSupabase(
            _tables(subscriptions=[_abonnement("owner", "veille", status="past_due")])
        )
        self.assertEqual(billing.active_plans(db, "owner"), {"veille"})

    def test_resilie_ferme_l_offre(self):
        db = _FakeSupabase(
            _tables(subscriptions=[_abonnement("owner", "veille", status="canceled")])
        )
        self.assertEqual(billing.active_plans(db, "owner"), set())

    def test_plan_null_retombe_sur_le_prix(self):
        """Abonnement créé sans nos métadonnées : le prix identifie l'offre."""
        billing.os.environ["STRIPE_PRICE_VEILLE"] = "price_veille"
        try:
            db = _FakeSupabase(
                _tables(subscriptions=[_abonnement("owner", None, stripe_price_id="price_veille")])
            )
            self.assertEqual(billing.active_plans(db, "owner"), {"veille"})
        finally:
            billing.os.environ.pop("STRIPE_PRICE_VEILLE", None)

    def test_plan_null_sans_prix_connu_n_ouvre_rien(self):
        db = _FakeSupabase(
            _tables(subscriptions=[_abonnement("owner", None, stripe_price_id="price_legacy")])
        )
        self.assertEqual(billing.active_plans(db, "owner"), set())
        self.assertEqual(billing.offre_du_compte(db, "owner"), offres.GRATUIT)

    def test_l_abonnement_d_autrui_ne_fuite_pas(self):
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "multi_monuments")]))
        self.assertEqual(billing.active_plans(db, "collab"), set())

    def test_snapshot_porte_l_offre_resolue(self):
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "multi_monuments")]))
        snapshot = billing.access_snapshot(db, "owner")
        self.assertEqual(snapshot["plans"], ["multi_monuments"])
        self.assertEqual(snapshot["offre"]["nom"], "Multi-monuments")
        self.assertIsNone(snapshot["offre"]["monumentsMax"])
        self.assertTrue(snapshot["offre"]["dashboard"])
        self.assertEqual(snapshot["subscription"]["plan"], "multi_monuments")
        self.assertEqual(snapshot["subscription"]["status"], "active")

    def test_snapshot_d_un_compte_gratuit(self):
        db = _FakeSupabase(_tables())
        snapshot = billing.access_snapshot(db, "owner")
        self.assertEqual(snapshot["plans"], [])
        self.assertEqual(snapshot["offre"]["nom"], "Gratuit")
        self.assertIsNone(snapshot["subscription"])

    def test_le_portail_suit_le_client_stripe_et_non_l_abonnement(self):
        """Une offre sur mesure ouverte en base donne des droits sans passer par
        Stripe : proposer « Gérer mon abonnement » mènerait alors à un 404."""
        a_la_main = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "multi_monuments")]))
        self.assertFalse(
            a_la_main.tables and billing.access_snapshot(a_la_main, "owner")["portail"]
        )

        par_stripe = _FakeSupabase(
            _tables(
                users=[{"id": "owner", "stripe_customer_id": "cus_1"}, {"id": "collab"}],
                subscriptions=[_abonnement("owner", "veille")],
            )
        )
        self.assertTrue(billing.access_snapshot(par_stripe, "owner")["portail"])

    def test_abonnement_legacy_ne_passe_pas_pour_un_abonnement_affiche(self):
        """`plan` NULL : ni droit, ni ligne « vous êtes abonné » à l'écran."""
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", None)]))
        snapshot = billing.access_snapshot(db, "owner")
        self.assertEqual(snapshot["plans"], [])
        self.assertIsNone(snapshot["subscription"])

    def test_plans_par_compte_lit_plusieurs_comptes_d_un_coup(self):
        db = _FakeSupabase(
            _tables(
                subscriptions=[
                    _abonnement("owner", "multi_monuments"),
                    _abonnement("collab", "veille"),
                    _abonnement("tiers", "veille", status="canceled"),
                ]
            )
        )
        par_compte = billing.plans_par_compte(db, ["owner", "collab", "tiers"])
        self.assertEqual(par_compte, {"owner": {"multi_monuments"}, "collab": {"veille"}})

    def test_rappels_email_suit_l_offre(self):
        """Point de branchement du job de rappels : sans offre, aucun email."""
        gratuit = _FakeSupabase(_tables())
        self.assertFalse(billing.peut_recevoir_rappels(gratuit, "owner"))

        abonne = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        self.assertTrue(billing.peut_recevoir_rappels(abonne, "owner"))


# ---------------------------------------------------------------------------
# L'offre qui gouverne un bien
# ---------------------------------------------------------------------------


class OffreDuMonumentTest(unittest.TestCase):
    """C'est le BIEN qui est couvert, pas le spectateur — et réciproquement, on
    ne retire pas à un abonné un droit qu'il paye parce qu'il travaille sur le
    monument de quelqu'un d'autre. D'où l'union des deux offres."""

    def test_l_offre_du_proprietaire_profite_a_son_equipe(self):
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        offre = quotas.offre_du_monument(db, "mon-1", "collab")
        self.assertTrue(offre.echeancier)
        self.assertTrue(offre.aides_bientot)

    def test_l_offre_du_collaborateur_ne_profite_pas_au_compte_du_proprietaire(self):
        """Le bien est couvert, pas le compte : le propriétaire au gratuit reste
        plafonné à un monument."""
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("collab", "multi_monuments")]))
        self.assertEqual(billing.offre_du_compte(db, "owner"), offres.GRATUIT)
        # Mais sur CE monument, le collaborateur garde ce qu'il paye.
        self.assertTrue(quotas.offre_du_monument(db, "mon-1", "collab").suppression_monument)

    def test_propriete_introuvable_retombe_sur_le_gratuit(self):
        db = _FakeSupabase(_tables(monuments=[]))
        self.assertEqual(quotas.offre_du_monument(db, "mon-1", "collab"), offres.GRATUIT)

    def test_batch_rend_une_offre_par_monument(self):
        db = _FakeSupabase(
            _tables(
                monuments=[
                    {"id": "mon-1", "user_id": "owner"},
                    {"id": "mon-2", "user_id": "tiers"},
                ],
                subscriptions=[_abonnement("owner", "veille")],
            )
        )
        par_monument = quotas.offres_des_monuments(db, ["mon-1", "mon-2"], "collab")
        self.assertTrue(par_monument["mon-1"].echeancier)
        self.assertFalse(par_monument["mon-2"].echeancier)


# ---------------------------------------------------------------------------
# Plafonds et suppressions
# ---------------------------------------------------------------------------


class QuotasTest(unittest.TestCase):
    def _refus(self, fn, *args) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            fn(*args)
        # 402 et non 403 : la demande est légitime, il manque une offre. Le
        # frontend s'en sert pour mener à la page Tarifs.
        self.assertEqual(ctx.exception.status_code, 402)
        return ctx.exception

    def test_gratuit_s_arrete_a_un_monument(self):
        db = _FakeSupabase(_tables())
        exc = self._refus(quotas.verifier_creation_monument, db, "owner")
        self.assertIn("Multi-monuments", str(exc.detail))

    def test_premier_monument_autorise(self):
        db = _FakeSupabase(_tables(monuments=[]))
        quotas.verifier_creation_monument(db, "owner")

    def test_multi_monuments_ne_plafonne_pas(self):
        db = _FakeSupabase(
            _tables(
                monuments=[{"id": f"mon-{i}", "user_id": "owner"} for i in range(12)],
                subscriptions=[_abonnement("owner", "multi_monuments")],
            )
        )
        quotas.verifier_creation_monument(db, "owner")

    def test_un_monument_partage_ne_consomme_pas_le_quota(self):
        """`monuments.user_id` et non l'appartenance : le bien d'autrui ne compte
        pas contre le compte qui n'y est qu'invité."""
        db = _FakeSupabase(_tables())
        quotas.verifier_creation_monument(db, "collab")

    def test_gratuit_s_arrete_a_deux_projets(self):
        db = _FakeSupabase(
            _tables(
                projets=[
                    {"id": "prj-1", "monument_id": "mon-1"},
                    {"id": "prj-2", "monument_id": "mon-1"},
                ]
            )
        )
        exc = self._refus(quotas.verifier_creation_projet, db, "mon-1", "owner")
        self.assertIn("Veille", str(exc.detail))

    def test_deuxieme_projet_autorise_au_gratuit(self):
        db = _FakeSupabase(_tables())
        quotas.verifier_creation_projet(db, "mon-1", "owner")

    def test_veille_ne_plafonne_pas_les_projets(self):
        db = _FakeSupabase(
            _tables(
                projets=[{"id": f"prj-{i}", "monument_id": "mon-1"} for i in range(9)],
                subscriptions=[_abonnement("owner", "veille")],
            )
        )
        quotas.verifier_creation_projet(db, "mon-1", "owner")

    def test_l_abonnement_du_proprietaire_debloque_l_equipe(self):
        """Sinon le client paierait un service que son architecte ne peut rendre."""
        db = _FakeSupabase(
            _tables(
                projets=[{"id": f"prj-{i}", "monument_id": "mon-1"} for i in range(5)],
                subscriptions=[_abonnement("owner", "veille")],
            )
        )
        quotas.verifier_creation_projet(db, "mon-1", "collab")

    def test_suppression_monument_reservee_a_multi_monuments(self):
        gratuit = _FakeSupabase(_tables())
        self._refus(quotas.verifier_suppression_monument, gratuit, "mon-1", "owner")

        veille = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        self._refus(quotas.verifier_suppression_monument, veille, "mon-1", "owner")

        multi = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "multi_monuments")]))
        quotas.verifier_suppression_monument(multi, "mon-1", "owner")

    def test_suppression_projet_reservee_aux_offres_payantes(self):
        gratuit = _FakeSupabase(_tables())
        self._refus(quotas.verifier_suppression_projet, gratuit, "mon-1", "owner")

        veille = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        quotas.verifier_suppression_projet(veille, "mon-1", "owner")

    def test_invitation_reservee_aux_offres_payantes(self):
        gratuit = _FakeSupabase(_tables())
        exc = self._refus(quotas.verifier_invitation, gratuit, "mon-1", "owner")
        self.assertIn("Veille", str(exc.detail))

        veille = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        quotas.verifier_invitation(veille, "mon-1", "owner")

    def test_l_offre_du_proprietaire_laisse_son_equipe_inviter(self):
        """Un architecte co_owner au gratuit invite le couvreur sur le chantier
        d'un client abonné : c'est le client qui paye le service."""
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "veille")]))
        quotas.verifier_invitation(db, "mon-1", "collab")


# ---------------------------------------------------------------------------
# Ce qui s'achète en ligne, et ce qui se négocie
# ---------------------------------------------------------------------------


class CanalDAchatTest(unittest.TestCase):
    """Les deux offres payantes sont des offres de plein droit, mais aucune
    n'est un produit en libre-service : elles se négocient. Le tunnel d'achat
    doit donc les refuser, sans pour autant leur retirer leurs droits."""

    def _checkout(self, plan: str) -> HTTPException:
        db = _FakeSupabase(_tables())
        with self.assertRaises(HTTPException) as ctx:
            billing_router.create_checkout(
                body=billing_router.CheckoutRequest(plan=plan),
                request=None,  # type: ignore[arg-type]
                user_id="owner",
                supabase=db,  # type: ignore[arg-type]
            )
        return ctx.exception

    def test_aucune_offre_ne_se_vend_en_ligne(self):
        self.assertEqual(offres.PLANS_VENDABLES, ())
        for plan in offres.PLANS:
            self.assertIn(plan, offres.PLANS)

    def test_le_checkout_renvoie_vers_le_contact(self):
        for plan in offres.PLANS:
            with self.subTest(plan=plan):
                exc = self._checkout(plan)
                # 409 et non 400 : la demande est compréhensible, c'est le canal
                # qui n'est pas le bon.
                self.assertEqual(exc.status_code, 409)
                self.assertIn("contact@monumia.fr", str(exc.detail))

    def test_une_offre_inventee_reste_un_400(self):
        """Le 409 dit « pas par ce canal », le 400 dit « cette offre n'existe
        pas » : les confondre masquerait une faute de frappe côté client."""
        self.assertEqual(self._checkout("offre-pirate").status_code, 400)

    def test_les_droits_restent_entiers(self):
        """Ne pas être vendable n'est pas être dégradé : une ligne ouverte à la
        main donne bien l'offre complète."""
        db = _FakeSupabase(_tables(subscriptions=[_abonnement("owner", "multi_monuments")]))
        offre = billing.offre_du_compte(db, "owner")
        self.assertTrue(offre.dashboard)
        self.assertIsNone(offre.monuments_max)

    def test_aucun_prix_public_a_afficher(self):
        """Rien à lire dans Stripe pour l'affichage : la page Tarifs montre
        « Sur demande » sans attendre de montant."""
        self.assertEqual(billing.public_plans(), [])
        self.assertFalse(billing.is_configured())


# ---------------------------------------------------------------------------
# Redaction serveur des aides à venir
# ---------------------------------------------------------------------------


class RedactionTest(unittest.TestCase):
    def _aide(self) -> dict:
        return {
            "id": "aide-1",
            "nom": "Subvention DRAC pour monuments classés",
            "nomCourt": "DRAC — MH classés",
            "organisme": "DRAC Normandie",
            "description": "Aide de l'État aux travaux de restauration.",
            "urlOfficielle": "https://exemple.gouv.fr",
            "montantMax": 40000,
            "tauxMax": 40,
            "dateLimite": "2026-12-31",
            "categorie": "etat_drac",
        }

    def _diagnostic(self) -> dict:
        """Une aide ouverte et une aide à venir dans chaque seau à portée, plus
        une non éligible à venir — celle qui ne doit PAS être masquée."""
        return {
            "aidesEligibles": [
                {"aide": self._aide(), "disponibilite": "maintenant"},
                {"aide": self._aide(), "disponibilite": "bientot"},
            ],
            "aidesPotentiellementEligibles": [
                {"aide": self._aide(), "disponibilite": "bientot"},
            ],
            "aidesAtteignables": [
                {"aide": self._aide(), "disponibilite": "bientot"},
            ],
            "aidesNonEligibles": [
                {"aide": self._aide(), "disponibilite": "bientot"},
            ],
        }

    def test_l_identite_du_financeur_part_le_montant_reste(self):
        redacted = aides_router.redact_locked_aide(self._aide())

        # Ce qu'on vend : impossible de savoir à qui s'adresser.
        self.assertEqual(redacted["nom"], aides_router.LOCKED_AIDE_LABEL)
        self.assertEqual(redacted["nomCourt"], aides_router.LOCKED_AIDE_LABEL)
        self.assertIsNone(redacted["organisme"])
        self.assertIsNone(redacted["urlOfficielle"])
        self.assertNotIn("DRAC", json.dumps(redacted, ensure_ascii=False))

        # L'argumentaire de vente, lui, reste entier.
        self.assertEqual(redacted["montantMax"], 40000)
        self.assertEqual(redacted["tauxMax"], 40)
        self.assertEqual(redacted["dateLimite"], "2026-12-31")
        self.assertEqual(redacted["categorie"], "etat_drac")
        self.assertEqual(redacted["id"], "aide-1")
        self.assertTrue(redacted["locked"])

    def test_gratuit_masque_les_aides_a_venir_et_elles_seules(self):
        out = aides_router.redact_bientot_hors_offre(self._diagnostic(), offres.GRATUIT)

        # Ouverte aujourd'hui : le détail des aides est gratuit.
        self.assertEqual(out["aidesEligibles"][0]["aide"]["organisme"], "DRAC Normandie")
        # À venir : masquée dans les trois seaux à portée.
        for bucket in aides_router._BUCKETS_A_PORTEE:
            a_venir = [m for m in out[bucket] if m["disponibilite"] == "bientot"]
            for match in a_venir:
                self.assertEqual(match["aide"]["nom"], aides_router.LOCKED_AIDE_LABEL)
                self.assertIsNone(match["aide"]["organisme"])
        # Non éligible : rien à vendre, et le front l'affiche dans sa propre
        # section quelle que soit sa fenêtre — la masquer n'aurait aucun sens.
        self.assertEqual(out["aidesNonEligibles"][0]["aide"]["organisme"], "DRAC Normandie")

    def test_veille_rend_le_diagnostic_intact(self):
        out = aides_router.redact_bientot_hors_offre(self._diagnostic(), offres.VEILLE)
        for bucket in aides_router._BUCKETS_A_PORTEE:
            for match in out[bucket]:
                self.assertEqual(match["aide"]["organisme"], "DRAC Normandie")

    def test_disponibilite_absente_vaut_ouverte(self):
        """Fail-open sur la donnée manquante : on ne masque jamais une aide
        faute d'information, comme le moteur ne l'écarte jamais."""
        result = {"aidesEligibles": [{"aide": self._aide()}]}
        out = aides_router.redact_bientot_hors_offre(result, offres.GRATUIT)
        self.assertEqual(out["aidesEligibles"][0]["aide"]["organisme"], "DRAC Normandie")


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """En-tête Stripe-Signature authentique (HMAC-SHA256 de « t.payload »)."""
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def _subscription_event(
    event_id: str = "evt_1",
    plan: str | None = "veille",
    price: str = "price_veille",
    event_type: str = "customer.subscription.created",
) -> dict:
    # `"object": "event"` fait partie de l'enveloppe réelle de Stripe, et
    # `construct_event` le lit pour écarter les notifications « thin » v2 : un
    # fixture qui l'omet ne teste pas le même chemin que la production.
    metadata: dict = {"user_id": "user-1"}
    if plan is not None:
        metadata["plan"] = plan
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "active",
                "cancel_at_period_end": True,
                "metadata": metadata,
                "items": {"data": [{"price": {"id": price}, "current_period_end": 1790000000}]},
            }
        },
    }


class WebhookTest(unittest.TestCase):
    def setUp(self):
        self.db = _FakeSupabase(_tables(users=[{"id": "user-1"}]))
        app.dependency_overrides[get_supabase] = lambda: self.db
        self.client = TestClient(app)
        self._old_env = {
            k: billing.os.environ.get(k) for k in ("STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_VEILLE")
        }
        billing.os.environ["STRIPE_WEBHOOK_SECRET"] = WEBHOOK_SECRET
        billing.os.environ["STRIPE_PRICE_VEILLE"] = "price_veille"

    def tearDown(self):
        app.dependency_overrides.clear()
        for key, value in self._old_env.items():
            if value is None:
                billing.os.environ.pop(key, None)
            else:
                billing.os.environ[key] = value

    def _post(self, event: dict, signature: str | None = None):
        payload = json.dumps(event).encode()
        return self.client.post(
            "/billing/webhook",
            content=payload,
            headers={"stripe-signature": signature or _sign(payload)},
        )

    def _subscriptions_ecrites(self) -> list[dict]:
        return [w[2] for w in self.db.writes if w[0] == "subscriptions"]

    def test_signature_absente_refusee(self):
        payload = json.dumps(_subscription_event()).encode()
        res = self.client.post("/billing/webhook", content=payload)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_signature_forgee_refusee(self):
        """Un corps signé avec une autre clé ne doit rien ouvrir."""
        payload = json.dumps(_subscription_event()).encode()
        res = self.client.post(
            "/billing/webhook",
            content=payload,
            headers={"stripe-signature": _sign(payload, "whsec_mauvaise_cle")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_corps_altere_apres_signature_refuse(self):
        """La signature porte sur le corps : le modifier l'invalide."""
        original = json.dumps(_subscription_event(plan="veille")).encode()
        signature = _sign(original)
        falsifie = original.replace(b'"veille"', b'"multi_monuments"')
        res = self.client.post(
            "/billing/webhook", content=falsifie, headers={"stripe-signature": signature}
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.db.writes, [])

    def test_abonnement_reflete_dans_la_base_avec_son_offre(self):
        self.assertEqual(self._post(_subscription_event()).status_code, 200)

        rows = self._subscriptions_ecrites()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["user_id"], "user-1")
        self.assertEqual(row["plan"], "veille")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["stripe_price_id"], "price_veille")
        self.assertTrue(row["cancel_at_period_end"])
        # `current_period_end` a migré de l'abonnement vers ses lignes : la
        # lecture doit suivre, sinon la date de fin est perdue.
        self.assertTrue(row["current_period_end"].startswith("2026-"))

    def test_offre_deduite_du_prix_quand_les_metadonnees_manquent(self):
        """Abonnement créé à la main dans le dashboard Stripe."""
        self.assertEqual(self._post(_subscription_event(plan=None)).status_code, 200)
        self.assertEqual(self._subscriptions_ecrites()[0]["plan"], "veille")

    def test_offre_non_identifiable_ecrite_a_null(self):
        """Un plan inventé ne doit pas passer pour un droit : la ligne est
        écrite sans offre, donc sans aucun droit."""
        event = _subscription_event(plan="offre-pirate", price="price_inconnu")
        self.assertEqual(self._post(event).status_code, 200)
        self.assertIsNone(self._subscriptions_ecrites()[0]["plan"])

    def test_checkout_session_n_ecrit_plus_rien(self):
        """Les deux offres sont des abonnements : plus de déblocage à l'unité."""
        event = {
            "id": "evt_cs",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "mode": "payment",
                    "payment_status": "paid",
                    "metadata": {"user_id": "user-1", "monument_id": "mon-1"},
                }
            },
        }
        self.assertEqual(self._post(event).status_code, 200)
        self.assertEqual(self._subscriptions_ecrites(), [])

    def test_evenement_rejoue_traite_une_seule_fois(self):
        """Stripe livre « au moins une fois » : le second passage ne fait rien."""
        self.assertEqual(self._post(_subscription_event()).status_code, 200)

        # Le journal rejette désormais cet id (violation d'unicité Postgres).
        self.db.insert_errors["stripe_events"] = Exception(
            'duplicate key value violates unique constraint "stripe_events_pkey"'
        )
        res = self._post(_subscription_event())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["duplicate"])
        self.assertEqual(len(self._subscriptions_ecrites()), 1)

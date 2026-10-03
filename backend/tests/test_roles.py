"""Les rôles de compte : l'union socle + base, le cache, et le sens du repli
quand la lecture échoue.

Les routes sont testées ailleurs (`test_admin_routes`). Ici on vise ce qu'elles
ne traversent pas : une base injoignable (migration pas encore appliquée), un
identifiant de socle sans compte, une ligne au rôle inventé, et le cache
module-level — dont la durée de vie décide du délai entre un rôle donné dans
Supabase Studio et sa prise d'effet.
"""

import os
import unittest
from unittest.mock import patch

from services import roles


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table: str, store: "_FakeSupabase"):
        self._table = table
        self._store = store
        self._rows = list(store.rows.get(table, []))

    def select(self, *_a, **_k):
        if self._table in self._store.tables_en_panne:
            raise RuntimeError("relation « comptes_roles » inexistante")
        return self

    def eq(self, colonne, valeur):
        self._rows = [r for r in self._rows if r.get(colonne) == valeur]
        return self

    def in_(self, colonne, valeurs):
        permises = set(valeurs)
        self._rows = [r for r in self._rows if r.get(colonne) in permises]
        return self

    def order(self, colonne, desc: bool = False):
        self._rows = sorted(self._rows, key=lambda r: str(r.get(colonne) or ""), reverse=desc)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        self._store.lectures += 1
        return _Resp(self._rows)


class _FakeSupabase:
    def __init__(self, rows: dict | None = None, en_panne: tuple[str, ...] = ()):
        self.rows = rows or {}
        self.tables_en_panne = set(en_panne)
        self.lectures = 0

    def table(self, name):
        return _Query(name, self)


UTILISATEURS = [
    {"id": "u1", "email": "fondateur@monumia.fr", "prenom": "Félix", "nom": "O."},
    {"id": "u2", "email": "associe@monumia.fr", "prenom": "Associé", "nom": "M."},
]

ADMIN = roles.ROLE_ADMIN
BETA = roles.ROLE_BETA_TESTEUR


def _role(user_id: str, role: str, **extra) -> dict:
    return {"user_id": user_id, "role": role, **extra}


class RolesTest(unittest.TestCase):
    def setUp(self):
        roles.invalider()
        self.env = patch.dict(os.environ, {"ADMIN_USER_IDS": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        roles.invalider()

    def _par_id(self, db, appelant: str = "u1") -> dict:
        """La liste servie à `/admin`, indexée par compte."""
        return {
            ligne["userId"]: ligne
            for ligne in roles.lister_utilisateurs(db, appelant)["utilisateurs"]
        }

    def test_environnement_non_configure_n_a_aucun_administrateur(self):
        """Jamais tous : un `.env` vide et une table vide ferment la porte."""
        db = _FakeSupabase({"users": UTILISATEURS})
        self.assertFalse(roles.est_admin(db, "u1"))
        self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset())

    def test_union_du_socle_et_de_la_base(self):
        db = _FakeSupabase({"users": UTILISATEURS, roles.TABLE: [_role("u2", ADMIN)]})
        with patch.dict(os.environ, {"ADMIN_USER_IDS": " u1 , "}):
            self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset({"u1", "u2"}))
            self.assertTrue(roles.est_admin(db, "u1"))
            self.assertTrue(roles.est_admin(db, "u2"))
            self.assertFalse(roles.est_admin(db, "u3"))

    def test_beta_testeur_n_est_pas_administrateur(self):
        """Tout l'intérêt d'avoir deux rôles : l'offre sans le catalogue."""
        db = _FakeSupabase({"users": UTILISATEURS, roles.TABLE: [_role("u2", BETA)]})
        self.assertFalse(roles.est_admin(db, "u2"))
        self.assertTrue(roles.a_le_role(db, "u2", BETA))
        self.assertIn("u2", roles.comptes_avec_offre(db))

    def test_le_socle_ne_porte_que_l_administration(self):
        """Un bêta-testeur se nomme depuis la page : il n'a rien à amorcer."""
        db = _FakeSupabase({"users": UTILISATEURS})
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"}):
            self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset({"u1"}))
            self.assertEqual(roles.comptes_du_role(db, BETA), frozenset())

    def test_comptes_avec_offre_reunit_les_deux_roles(self):
        db = _FakeSupabase({roles.TABLE: [_role("u2", BETA), _role("u3", ADMIN)]})
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"}):
            self.assertEqual(roles.comptes_avec_offre(db), frozenset({"u1", "u2", "u3"}))

    def test_role_inconnu_en_base_n_ouvre_rien(self):
        """La contrainte SQL l'interdit, mais une valeur écrite à la main dans
        Supabase Studio ne doit pas ouvrir de droit par accident."""
        db = _FakeSupabase({"users": UTILISATEURS, roles.TABLE: [_role("u2", "super_admin")]})
        self.assertFalse(roles.est_admin(db, "u2"))
        self.assertEqual(roles.comptes_avec_offre(db), frozenset())
        u2 = self._par_id(db)["u2"]
        self.assertFalse(any(etat["actif"] for etat in u2["roles"].values()))

    def test_identifiant_vide_n_a_aucun_role(self):
        db = _FakeSupabase({roles.TABLE: [_role("u1", ADMIN)]})
        self.assertFalse(roles.est_admin(db, ""))

    def test_base_injoignable_ferme_la_porte(self):
        """Le repli va dans le sens qui REFUSE : on ne donne pas la main à
        quelqu'un parce qu'une requête a échoué. Seul le socle subsiste."""
        db = _FakeSupabase({roles.TABLE: [_role("u2", ADMIN)]}, en_panne=(roles.TABLE,))
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"}):
            self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset({"u1"}))
            self.assertFalse(roles.est_admin(db, "u2"))

    def test_la_liste_porte_les_comptes_sans_role(self):
        """La page donne un rôle en cliquant sur une ligne : un compte sans
        aucun rôle doit donc y figurer, avec ses deux bascules éteintes."""
        db = _FakeSupabase({"users": UTILISATEURS})
        par_id = self._par_id(db)
        self.assertEqual(set(par_id), {"u1", "u2"})
        self.assertEqual(par_id["u2"]["email"], "associe@monumia.fr")
        self.assertFalse(any(etat["actif"] for etat in par_id["u2"]["roles"].values()))
        self.assertTrue(all(etat["modifiable"] for etat in par_id["u2"]["roles"].values()))

    def test_socle_sans_compte_reste_visible(self):
        """UUID recopié de travers, ou compte supprimé : le cacher laisserait un
        administrateur invisible."""
        db = _FakeSupabase({"users": []})
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "fantome"}):
            (ligne,) = roles.lister_utilisateurs(db, "u1")["utilisateurs"]
        self.assertEqual(ligne["userId"], "fantome")
        self.assertTrue(ligne["compteIntrouvable"])
        self.assertIsNone(ligne["email"])
        self.assertTrue(ligne["roles"][ADMIN]["actif"])
        self.assertFalse(ligne["roles"][ADMIN]["modifiable"])

    def test_administration_du_socle_n_est_pas_modifiable(self):
        """Le socle l'emporte : supprimer sa ligne le laisserait administrateur,
        et la liste aurait promis un geste sans effet."""
        db = _FakeSupabase({"users": UTILISATEURS, roles.TABLE: [_role("u1", ADMIN)]})
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"}):
            etat = self._par_id(db, appelant="u2")["u1"]["roles"][ADMIN]
        self.assertEqual(etat["source"], "socle")
        self.assertFalse(etat["modifiable"])
        self.assertIn("ADMIN_USER_IDS", etat["raison"])

    def test_on_ne_peut_pas_retirer_sa_propre_administration(self):
        db = _FakeSupabase({"users": UTILISATEURS, roles.TABLE: [_role("u1", ADMIN)]})
        moi = self._par_id(db, appelant="u1")["u1"]["roles"]
        self.assertFalse(moi[ADMIN]["modifiable"])
        # Mais un AUTRE administrateur peut, lui, la lui retirer.
        self.assertTrue(self._par_id(db, appelant="u2")["u1"]["roles"][ADMIN]["modifiable"])

    def test_un_compte_peut_cumuler_les_deux_roles(self):
        db = _FakeSupabase(
            {"users": UTILISATEURS, roles.TABLE: [_role("u2", BETA), _role("u2", ADMIN)]}
        )
        etats = self._par_id(db)["u2"]["roles"]
        self.assertTrue(etats[ADMIN]["actif"])
        self.assertTrue(etats[BETA]["actif"])

    def test_un_porteur_de_role_hors_du_plafond_reste_visible(self):
        """Un droit attribué ne doit jamais devenir invisible faute de place —
        sans quoi il serait impossible de le retirer depuis la page."""
        recents = [
            {"id": f"u{i}", "email": f"u{i}@monumia.fr", "created_at": f"2026-09-{i:02d}"}
            for i in range(1, roles.LIMITE_UTILISATEURS + 2)
        ]
        vieux = {"id": "ancien", "email": "ancien@monumia.fr", "created_at": "2020-01-01"}
        db = _FakeSupabase({"users": [vieux, *recents], roles.TABLE: [_role("ancien", BETA)]})
        corps = roles.lister_utilisateurs(db, "u1")
        self.assertTrue(corps["tronquee"])
        par_id = {ligne["userId"]: ligne for ligne in corps["utilisateurs"]}
        self.assertIn("ancien", par_id)
        self.assertTrue(par_id["ancien"]["roles"][BETA]["actif"])

    def test_la_liste_est_mise_en_cache_mais_pas_le_socle(self):
        """Le socle est relu à chaque appel : le mettre en cache avec la base
        ferait mentir un `.env` rechargé (et les tests qui le remplacent)."""
        db = _FakeSupabase({roles.TABLE: [_role("u2", ADMIN)]})
        roles.comptes_du_role(db, ADMIN)
        lectures = db.lectures
        roles.comptes_du_role(db, ADMIN)
        self.assertEqual(db.lectures, lectures, "la base devrait être lue une seule fois")
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"}):
            self.assertIn("u1", roles.comptes_du_role(db, ADMIN))

    def test_invalider_force_la_relecture(self):
        db = _FakeSupabase({roles.TABLE: []})
        self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset())
        db.rows[roles.TABLE] = [_role("u2", ADMIN)]
        self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset(), "cache encore valide")
        roles.invalider()
        self.assertEqual(roles.comptes_du_role(db, ADMIN), frozenset({"u2"}))

    def test_attribuer_a_un_compte_inconnu(self):
        db = _FakeSupabase({"users": UTILISATEURS})
        with self.assertRaises(LookupError):
            roles.ajouter_role(db, "jamais-inscrit", ADMIN, "u1")

    def test_attribuer_un_role_inconnu(self):
        db = _FakeSupabase({"users": UTILISATEURS})
        with self.assertRaises(ValueError):
            roles.ajouter_role(db, "u2", "super_admin", "u1")

    def test_libelle_pour_chaque_role(self):
        """Un rôle ajouté sans son libellé s'afficherait vide côté serveur."""
        self.assertEqual(set(roles.LIBELLES), set(roles.ROLES))


if __name__ == "__main__":
    unittest.main()

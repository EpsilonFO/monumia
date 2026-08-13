"""Endpoint de reprise des pièces et détachement d'un document."""

import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from db import get_current_user_id, get_supabase
from main import app
from routers.dossiers import UpdateChecklistItemRequest, update_checklist_item


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store, table):
        self._store = store
        self._table = table
        self._update = None
        self._insert = None

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update = values
        return self

    def insert(self, values, *a, **k):
        self._insert = values
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._insert is not None:
            self._store.inserts.setdefault(self._table, []).append(self._insert)
            return _Resp([self._insert])
        if self._update is not None:
            self._store.updates.setdefault(self._table, []).append(self._update)
            return _Resp([self._store.rows.get(self._table)])
        return _Resp(self._store.rows.get(self._table))


class _FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.updates: dict[str, list] = {}
        self.inserts: dict[str, list] = {}

    def table(self, name):
        return _Query(self, name)


_DOSSIER = {
    "id": "d1",
    "monument_id": "p1",
    "user_id": "u1",
    "checklist": [
        {
            "id": "i1",
            "label": "RIB",
            "description": "",
            "obligatoire": True,
            "categorie": "document",
            "ordre": 1,
            "statut": "manquant",
            "pieceId": "rib",
        }
    ],
}


class ReprendrePiecesTests(unittest.TestCase):
    def test_endpoint_applique_la_reprise(self) -> None:
        from routers.dossiers import reprendre_pieces

        supabase = _FakeSupabase({"dossiers": _DOSSIER})

        reprise = [{**_DOSSIER["checklist"][0], "statut": "repris", "documentId": "doc1"}]
        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers.apply_reuse", return_value=(reprise, 1)) as faux,
        ):
            reprendre_pieces("d1", user_id="u1", supabase=supabase)

        faux.assert_called_once()
        ecrit = supabase.updates["dossiers"][0]
        self.assertEqual(ecrit["checklist"][0]["statut"], "repris")
        # Un item « repris » ne compte pas dans la progression.
        self.assertEqual(ecrit["progression_pourcentage"], 0)


class ResolutionPieceIdsTests(unittest.TestCase):
    """Les dossiers créés avant le rattachement du corpus n'ont aucun `pieceId`
    dans leur JSONB : sans re-résolution depuis l'aide, l'endpoint serait un
    no-op définitif sur exactement les dossiers qu'il vise."""

    _AIDE = {
        "documents_requis": [
            {"nom": "RIB", "piece_id": "rib"},
            {"nom": "Pièce propre à cette aide"},
        ]
    }

    def _dossier(self) -> dict:
        return {
            "id": "d1",
            "monument_id": "p1",
            "aide_id": "drac-restauration",
            "checklist": [
                {"id": "i1", "label": "RIB", "ordre": 1, "statut": "manquant", "obligatoire": True},
                {
                    "id": "i2",
                    "label": "Pièce propre à cette aide",
                    "ordre": 2,
                    "statut": "manquant",
                    "obligatoire": True,
                },
            ],
        }

    def _appeler(self, supabase, retour_reprise=(None, 0)):
        from routers.dossiers import reprendre_pieces

        vues: dict = {}

        def _capture(_sb, checklist, *_a, **_k):
            vues["checklist"] = checklist
            return (retour_reprise[0] or checklist), retour_reprise[1]

        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers.apply_reuse", side_effect=_capture),
        ):
            reprendre_pieces("d1", user_id="u1", supabase=supabase)
        return vues["checklist"]

    def test_le_piece_id_est_reresolu_par_libelle_exact(self) -> None:
        supabase = _FakeSupabase({"dossiers": self._dossier(), "aides_v3": self._AIDE})

        checklist = self._appeler(supabase)

        self.assertEqual(checklist[0]["pieceId"], "rib")
        # Une pièce sans rattachement dans l'aide en reste dépourvue : on ne
        # devine jamais un piece_id, on recopie celui du corpus.
        self.assertIsNone(checklist[1].get("pieceId"))

    def test_les_piece_ids_reresolus_sont_persistes_meme_sans_reprise(self) -> None:
        supabase = _FakeSupabase({"dossiers": self._dossier(), "aides_v3": self._AIDE})

        self._appeler(supabase)

        ecrit = supabase.updates["dossiers"][0]
        self.assertEqual(ecrit["checklist"][0]["pieceId"], "rib")
        self.assertEqual(ecrit["progression_pourcentage"], 0)

    def test_aide_introuvable_ne_fait_pas_echouer_la_reprise(self) -> None:
        supabase = _FakeSupabase({"dossiers": self._dossier(), "aides_v3": None})

        checklist = self._appeler(supabase)

        self.assertIsNone(checklist[0].get("pieceId"))
        self.assertNotIn("dossiers", supabase.updates)

    def test_un_piece_id_deja_present_n_est_pas_ecrase(self) -> None:
        dossier = self._dossier()
        dossier["checklist"][0]["pieceId"] = "titre_propriete"
        supabase = _FakeSupabase({"dossiers": dossier, "aides_v3": self._AIDE})

        checklist = self._appeler(supabase)

        self.assertEqual(checklist[0]["pieceId"], "titre_propriete")


class _RecordingQuery:
    """Note le champ sur lequel porte le filtre, pour vérifier slug vs UUID."""

    def __init__(self, journal):
        self._journal = journal

    def select(self, *a, **k):
        return self

    def eq(self, field, value, *a, **k):
        self._journal.append((field, value))
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return _Resp({"documents_requis": []})


class _RecordingSupabase:
    def __init__(self):
        self.journal: list[tuple[str, str]] = []

    def table(self, name):
        return _RecordingQuery(self.journal)


class FetchAideTests(unittest.TestCase):
    """`dossiers.aide_id` stocke un slug OU un UUID (cf. create_dossier)."""

    def test_un_slug_filtre_sur_slug(self) -> None:
        from routers.dossiers import _fetch_aide

        supabase = _RecordingSupabase()
        _fetch_aide(supabase, "drac-restauration")
        self.assertEqual(supabase.journal, [("slug", "drac-restauration")])

    def test_un_uuid_filtre_sur_id(self) -> None:
        from routers.dossiers import _fetch_aide

        supabase = _RecordingSupabase()
        identifiant = str(uuid.uuid4())
        _fetch_aide(supabase, identifiant)
        self.assertEqual(supabase.journal, [("id", identifiant)])

    def test_aide_id_vide_ne_declenche_aucune_requete(self) -> None:
        from routers.dossiers import _fetch_aide

        supabase = _RecordingSupabase()
        self.assertIsNone(_fetch_aide(supabase, None))
        self.assertEqual(supabase.journal, [])


class CreationRobusteTests(unittest.TestCase):
    """La reprise est un confort greffé sur la création de dossier, qui marchait
    avant elle : son échec ne doit pas se transformer en 500."""

    def _supabase(self) -> _FakeSupabase:
        return _FakeSupabase(
            {
                "monuments": {"id": "p1", "nom": "Chapelle"},
                "aides_v3": {"id": "a1", "nom": "Aide", "documents_requis": [{"nom": "RIB"}]},
                "users": {"id": "u1", "nom": "Dupont"},
                "dossiers": {"id": "d1"},
            }
        )

    def test_un_apply_reuse_qui_leve_n_empeche_pas_la_creation(self) -> None:
        from routers.dossiers import CreateDossierRequest, create_dossier

        supabase = self._supabase()
        body = CreateDossierRequest(monument_id="p1", aide_id="a1", travaux_prevus=[])

        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers._enrich_monument", side_effect=lambda _sb, m: m),
            patch("routers.dossiers.apply_reuse", side_effect=RuntimeError("PostgREST HS")),
        ):
            cree = create_dossier(body, user_id="u1", supabase=supabase)

        # Le dossier est bien inséré, avec sa checklist d'origine : aucune pièce
        # reprise, exactement le comportement d'avant le lot.
        self.assertEqual(cree["user_id"], "u1")
        self.assertEqual(cree["checklist"][0]["label"], "RIB")
        self.assertEqual(cree["checklist"][0]["statut"], "manquant")
        self.assertNotIn("documentId", cree["checklist"][0])
        self.assertEqual(len(supabase.inserts["dossiers"]), 1)


class DetachementSchemaTests(unittest.TestCase):
    def test_detacher_absent_par_defaut(self) -> None:
        body = UpdateChecklistItemRequest(statut="fourni", document_id="doc1")
        self.assertFalse(body.detacher)

    def test_fourni_et_detacher_est_rejete(self) -> None:
        with self.assertRaises(ValidationError):
            UpdateChecklistItemRequest(statut="fourni", detacher=True)

    def test_statut_hors_vocabulaire_est_rejete(self) -> None:
        with self.assertRaises(ValidationError):
            UpdateChecklistItemRequest(statut="valide")


class ValidationHttpTests(unittest.TestCase):
    """`fourni` + `detacher` était le seul chemin, atteignable depuis un client,
    par lequel un dossier pouvait se déclarer complet sans document : la pièce
    comptait dans la progression sans rien derrière. Le refus doit intervenir
    avant le handler, donc en 422."""

    def setUp(self) -> None:
        app.dependency_overrides[get_current_user_id] = lambda: "u1"
        app.dependency_overrides[get_supabase] = lambda: _FakeSupabase({"dossiers": _DOSSIER})
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_fourni_et_detacher_renvoie_422(self) -> None:
        reponse = self.client.patch(
            "/dossiers/d1/checklist/i1", json={"statut": "fourni", "detacher": True}
        )
        self.assertEqual(reponse.status_code, 422)

    def test_statut_inconnu_renvoie_422(self) -> None:
        reponse = self.client.patch("/dossiers/d1/checklist/i1", json={"statut": "valide"})
        self.assertEqual(reponse.status_code, 422)


# ---------------------------------------------------------------------------
# Faux client supabase pour `update_checklist_item` : contrairement au faux
# client ci-dessus (une seule ligne fixe par table), celui-ci adresse les
# lignes par id (documents, dossiers) ou par monument (project_members), pour
# pouvoir distinguer le document déjà attaché du document qu'on tente de
# rattacher, et simuler un appelant membre d'un projet mais pas d'un autre.
# ---------------------------------------------------------------------------


class _Table:
    def __init__(self, db, name):
        self._db = db
        self._name = name
        self._filters: dict[str, str] = {}
        self._update_values = None

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update_values = values
        return self

    def eq(self, field, value, *a, **k):
        self._filters[field] = value
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._update_values is not None:
            self._db.updates.setdefault(self._name, []).append(
                {"id": self._filters.get("id"), "values": self._update_values}
            )
            return _Resp(None)
        return _Resp(self._db.lookup(self._name, self._filters))


class _Db:
    """dossier : une seule ligne. documents : par id. project_members : par
    monument (une seule ligne « le rôle de l'appelant sur ce monument »)."""

    def __init__(self, *, dossier, documents=None, roles=None):
        self.dossier = dossier
        self.documents = documents or {}
        self.roles = roles or {}
        self.updates: dict[str, list] = {}

    def table(self, name):
        return _Table(self, name)

    def lookup(self, table, filters):
        if table == "dossiers":
            return self.dossier if filters.get("id") == self.dossier["id"] else None
        if table == "documents":
            return self.documents.get(filters.get("id"))
        if table == "project_members":
            role = self.roles.get(filters.get("monument_id"))
            return {"role": role} if role else None
        return None  # "monuments" (repli de get_project_role) : jamais utilisé ici


def _dossier(item: dict) -> dict:
    return {"id": "d1", "monument_id": "mon-1", "checklist": [item]}


class DetachementTests(unittest.TestCase):
    def test_detacher_vide_le_document_et_purge_les_marqueurs(self) -> None:
        item = {
            "id": "i1",
            "statut": "repris",
            "documentId": "docA",
            "origine": "repris",
            "perime": False,
            "pieceId": "rib",
        }
        db = _Db(
            dossier=_dossier(item),
            documents={"docA": {"user_id": "u1"}},  # l'appelant est l'auteur
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertIsNone(ecrit["documentId"])
        self.assertNotIn("origine", ecrit)
        self.assertNotIn("perime", ecrit)
        self.assertNotIn("documents", db.updates)  # pas de réécriture de piece_id
        # Le refus est MÉMORISÉ : sans cela, la reprise automatique reproposerait
        # le même fichier à la visite suivante, à l'infini.
        self.assertEqual(ecrit["refuses"], ["docA"])

    def test_detacher_deux_fois_ne_duplique_pas_le_refus(self) -> None:
        item = {
            "id": "i1",
            "statut": "repris",
            "documentId": "docA",
            "origine": "repris",
            "pieceId": "rib",
            "refuses": ["docA"],
        }
        db = _Db(
            dossier=_dossier(item),
            documents={"docA": {"user_id": "u1"}},
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["refuses"], ["docA"])

    def test_rattacher_a_la_main_annule_le_refus(self) -> None:
        """Choisir soi-même un fichier autrefois refusé est un changement d'avis
        explicite : le refus saute, la reprise peut de nouveau le proposer."""
        item = {
            "id": "i1",
            "statut": "manquant",
            "documentId": None,
            "pieceId": "rib",
            "refuses": ["docA", "docB"],
        }
        db = _Db(
            dossier=_dossier(item),
            documents={
                "docA": {
                    "user_id": "u1",
                    "visibility": "team",
                    "allowed_user_ids": [],
                    "monument_ids": ["mon-1"],
                }
            },
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="fourni", document_id="docA")

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["documentId"], "docA")
        self.assertEqual(ecrit["refuses"], ["docB"])


class ConfirmationRepriseTests(unittest.TestCase):
    """Confirmer une pièce reprise n'est pas un remplacement : la garde
    auteur/chef-de-projet ne doit pas s'appliquer, sinon le bouton de
    confirmation échouerait dès que le document a été repris chez un tiers."""

    def _item(self) -> dict:
        return {
            "id": "i1",
            "statut": "repris",
            "documentId": "docA",
            "origine": "repris",
            "perime": False,
            "pieceId": "rib",
        }

    def test_membre_non_auteur_peut_confirmer(self) -> None:
        db = _Db(
            dossier=_dossier(self._item()),
            documents={"docA": {"user_id": "u2"}},  # document d'un tiers
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="fourni")  # ni document_id, ni detacher

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["statut"], "fourni")
        self.assertEqual(ecrit["documentId"], "docA")  # document conservé
        self.assertNotIn("origine", ecrit)
        self.assertNotIn("perime", ecrit)

    def test_membre_non_auteur_ne_peut_toujours_pas_rejeter(self) -> None:
        # Le rejet retire bien le document : la garde s'applique, contrairement
        # à la confirmation.
        db = _Db(
            dossier=_dossier(self._item()),
            documents={"docA": {"user_id": "u2"}},
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)

        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)
        self.assertEqual(ctx.exception.status_code, 403)


class EstampillageTests(unittest.TestCase):
    def test_rattacher_un_document_visible_estampille_piece_id(self) -> None:
        item = {"id": "i1", "statut": "manquant", "pieceId": "rib"}
        db = _Db(
            dossier=_dossier(item),
            documents={
                "docNew": {
                    "user_id": "u2",
                    "visibility": "team",
                    "allowed_user_ids": [],
                    "monument_ids": ["mon-1"],
                }
            },
            roles={"mon-1": "member"},
        )
        body = UpdateChecklistItemRequest(statut="fourni", document_id="docNew")

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        estampille = db.updates["documents"][0]
        self.assertEqual(estampille["id"], "docNew")
        self.assertEqual(estampille["values"], {"piece_id": "rib"})

    def test_pas_destampillage_sans_pieceid(self) -> None:
        item = {"id": "i1", "statut": "manquant"}  # pas de pieceId
        db = _Db(dossier=_dossier(item), documents={}, roles={"mon-1": "member"})
        body = UpdateChecklistItemRequest(statut="fourni", document_id="doc-libre")

        update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        self.assertNotIn("documents", db.updates)
        ecrit = db.updates["dossiers"][0]["values"]["checklist"][0]
        self.assertEqual(ecrit["documentId"], "doc-libre")

    def test_document_non_visible_est_refuse(self) -> None:
        # Document d'un tiers, dans un projet dont l'appelant n'est pas membre :
        # sans le contrôle, il serait pourtant estampillé (stock empoisonné).
        item = {"id": "i1", "statut": "manquant", "pieceId": "rib"}
        db = _Db(
            dossier=_dossier(item),
            documents={
                "docForeign": {
                    "user_id": "u2",
                    "visibility": "custom",
                    "allowed_user_ids": [],
                    "monument_ids": ["autre-mon"],
                }
            },
            roles={"mon-1": "member"},  # rien sur "autre-mon"
        )
        body = UpdateChecklistItemRequest(statut="fourni", document_id="docForeign")

        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("d1", "i1", body, user_id="u1", supabase=db)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertNotIn("documents", db.updates)
        self.assertNotIn("dossiers", db.updates)


class EstampillageDesPiecesFourniesTests(unittest.TestCase):
    """Une pièce rattachée AVANT le rattachement du corpus n'a pas de `piece_id`.

    Elle reste donc invisible du stock de reprise, et l'utilisateur ne voit
    jamais servir un document qu'il a pourtant déjà fourni. « Reprendre mes
    pièces » doit donc aussi enregistrer dans le stock les pièces déjà fournies
    du dossier, une fois leurs `pieceId` re-résolus.
    """

    def _db(self, *, piece_id_item="rib", piece_id_doc=None, uploader="u1"):
        return _FakeSupabase(
            {
                "dossiers": {
                    "id": "d1",
                    "monument_id": "p1",
                    "user_id": "u1",
                    "aide_id": "aide-slug",
                    "checklist": [
                        {
                            "id": "i1",
                            "label": "RIB",
                            "description": "",
                            "obligatoire": True,
                            "categorie": "document",
                            "ordre": 1,
                            "statut": "fourni",
                            "documentId": "doc1",
                            "pieceId": piece_id_item,
                        }
                    ],
                },
                "documents": {
                    "id": "doc1",
                    "user_id": uploader,
                    "visibility": "team",
                    "allowed_user_ids": [],
                    "monument_ids": ["p1"],
                    "piece_id": piece_id_doc,
                },
                "aides_v3": {"slug": "aide-slug", "documents_requis": []},
                "project_members": [],
                "monuments": [],
            }
        )

    def _appeler(self, db):
        from routers.dossiers import reprendre_pieces

        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers.apply_reuse", side_effect=lambda s, c, m, u: (c, 0)),
        ):
            reprendre_pieces("d1", user_id="u1", supabase=db)
        return db.updates.get("documents", [])

    def test_piece_fournie_est_estampillee(self) -> None:
        db = self._db()
        self.assertEqual(self._appeler(db), [{"piece_id": "rib"}])

    def test_document_deja_estampille_non_reecrit(self) -> None:
        db = self._db(piece_id_doc="rib")
        self.assertEqual(self._appeler(db), [])

    def test_item_sans_piece_id_non_estampille(self) -> None:
        db = self._db(piece_id_item=None)
        self.assertEqual(self._appeler(db), [])

    def test_document_invisible_non_estampille(self) -> None:
        """La visibilité garde l'estampillage comme elle garde le rattachement."""
        db = self._db(uploader="u2")
        with patch("routers.dossiers._document_visible", return_value=False):
            self.assertEqual(self._appeler(db), [])


if __name__ == "__main__":
    unittest.main()

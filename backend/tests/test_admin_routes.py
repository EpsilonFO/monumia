"""Les routes d'administration du catalogue : qui y entre, et ce qu'elles
refusent.

Le garde est posé sur le ROUTER (`dependencies=[Depends(require_admin)]`) : le
premier test le vérifie route par route, parce qu'une route ajoutée plus tard
sans garde serait une porte ouverte sur le catalogue de production. Les trois
routes qui ATTRIBUENT les rôles sont derrière le même garde, et le test les
traite comme les autres — c'est là qu'une porte ouverte coûterait le plus cher.

Les deux caches module-level (surcouche du catalogue, rôles de compte) sont
invalidés en setUp ET en tearDown : ils sont partagés entre les tests, qui
n'utilisent pas le même faux client.
"""

import os
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch

from fastapi.testclient import TestClient

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from main import app
from services import catalogue_admin as ca
from services import roles

SLUG = sorted(load_all_aides())[0]
FACT_ENUM = next(k for k, f in sorted(load_facts().items()) if f.type == "enum")
FACT_BOOL = next(k for k, f in sorted(load_facts().items()) if f.type == "boolean")
FACT_NUM = next(k for k, f in sorted(load_facts().items()) if f.type in ("integer", "number"))


def _condition_modifiable() -> tuple[str, str, str, list[str]]:
    """Une condition réelle du corpus dans le mandat : (slug, id, fait, options).

    Prise sur le CORPUS et non fabriquée : les routes lisent le catalogue
    effectif, pas une fixture.
    """
    facts = {**load_facts(), **load_pending_facts()}
    for slug, aide in sorted(load_all_aides().items()):
        for condition in aide.conditions:
            if ca.condition_modifiable(condition, facts):
                fait = facts[condition.fact or ""]
                return (
                    slug,
                    condition.id,
                    condition.fact or "",
                    [o.id for o in fait.options or []],
                )
    raise AssertionError("aucune condition modifiable dans le corpus")


COND_SLUG, COND_ID, COND_FACT, COND_OPTIONS = _condition_modifiable()


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    """Faux PostgREST. Les filtres s'ACCUMULENT et ne s'appliquent qu'à
    `execute()`.

    Ce n'est pas un détail de confort : avec une clé primaire composite,
    `delete().eq("aide_slug", s).eq("condition_id", c)` appliqué au PREMIER
    `.eq()` effacerait toutes les conditions de l'aide. Le vrai client combine
    bien les deux ; un faux client qui applique au premier filtre mentirait, et
    il mentirait EN NOTRE FAVEUR — le test passerait sur une suppression de
    masse.
    """

    def __init__(self, store: "_FakeSupabase", table: str) -> None:
        self._store = store
        self._table = table
        self._suppression = False
        self._filtres: list[tuple[str, object]] = []
        self._in: list[tuple[str, set]] = []
        self._ordre: tuple[str, bool] | None = None
        self._limite: int | None = None

    def select(self, *_a, **_k) -> "_Query":
        return self

    def upsert(self, values, *_a, **_k) -> "_Query":
        self._store.upserts.setdefault(self._table, []).append(values)
        self._store.rows[self._table] = [
            r for r in self._store.rows.get(self._table, []) if not _meme_cle(r, values)
        ] + [values]
        return self

    def delete(self, *_a, **_k) -> "_Query":
        self._suppression = True
        return self

    def eq(self, colonne, valeur) -> "_Query":
        self._filtres.append((colonne, valeur))
        return self

    def in_(self, colonne, valeurs) -> "_Query":
        self._in.append((colonne, set(valeurs)))
        return self

    def order(self, colonne, desc: bool = False) -> "_Query":
        self._ordre = (colonne, desc)
        return self

    def limit(self, n) -> "_Query":
        self._limite = n
        return self

    def execute(self) -> _Resp:
        lignes = list(self._store.rows.get(self._table, []))
        if self._suppression:
            self._store.suppressions.setdefault(self._table, []).append(list(self._filtres))
            self._store.rows[self._table] = [
                r
                for r in lignes
                if not all(r.get(colonne) == valeur for colonne, valeur in self._filtres)
            ]
            return _Resp([])
        for colonne, valeur in self._filtres:
            lignes = [r for r in lignes if r.get(colonne) == valeur]
        for colonne, valeurs in self._in:
            lignes = [r for r in lignes if r.get(colonne) in valeurs]
        if self._ordre is not None:
            colonne, desc = self._ordre
            lignes = sorted(lignes, key=lambda r: str(r.get(colonne) or ""), reverse=desc)
        if self._limite is not None:
            lignes = lignes[: self._limite]
        return _Resp(lignes)


#: Clés primaires des tables écrites par /admin, la composite comprise.
CLES = (("slug",), ("fact_key",), ("aide_slug", "condition_id"), ("user_id", "role"))


def _meme_cle(gauche: dict, droite: dict) -> bool:
    for cle in CLES:
        if all(colonne in droite for colonne in cle):
            return all(gauche.get(colonne) == droite[colonne] for colonne in cle)
    return False


class _FakeSupabase:
    def __init__(self, **rows) -> None:
        self.rows: dict[str, list] = {k: list(v) for k, v in rows.items()}
        self.upserts: dict[str, list] = {}
        self.suppressions: dict[str, list] = {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)


#: Un prédicat que la condition choisie accepte : ses propres options.
PREDICAT_OK = {"operateur": "in", "valeurs": COND_OPTIONS}

#: Un compte ordinaire, présent en base : celui à qui les tests donnent et
#: reprennent un rôle. Jamais "u1", l'appelant — se retirer l'administration à
#: soi-même est refusé.
AUTRE_ID = "u2"
AUTRE_EMAIL = "associe@monumia.fr"

#: (méthode, chemin, corps) — les quinze routes du router.
ROUTES = (
    ("get", "/admin/aides", None),
    ("get", "/admin/statistiques", None),
    ("put", f"/admin/aides/{SLUG}/retrait", {"motif": "obsolète"}),
    ("delete", f"/admin/aides/{SLUG}/retrait", None),
    ("get", "/admin/faits", None),
    ("post", f"/admin/faits/{FACT_ENUM}/simuler", {"options": []}),
    ("put", f"/admin/faits/{FACT_ENUM}", {"question": "Reformulée ?"}),
    ("delete", f"/admin/faits/{FACT_ENUM}", None),
    ("get", "/admin/conditions", None),
    ("post", f"/admin/conditions/{COND_SLUG}/{COND_ID}/simuler", PREDICAT_OK),
    ("put", f"/admin/conditions/{COND_SLUG}/{COND_ID}", PREDICAT_OK),
    ("delete", f"/admin/conditions/{COND_SLUG}/{COND_ID}", None),
    ("get", "/admin/utilisateurs", None),
    ("put", f"/admin/roles/beta_testeur/{AUTRE_ID}", {"motif": "lot 2"}),
    ("delete", f"/admin/roles/beta_testeur/{AUTRE_ID}", None),
)


class _BaseAdmin(unittest.TestCase):
    def setUp(self) -> None:
        ca.invalider()
        roles.invalider()
        self.supabase = _FakeSupabase(
            users=[
                {"id": "u1", "email": "fondateur@monumia.fr", "prenom": "Félix", "nom": "O."},
                {"id": AUTRE_ID, "email": AUTRE_EMAIL, "prenom": "Associé", "nom": "M."},
            ]
        )
        app.dependency_overrides[get_current_user_id] = lambda: "u1"
        app.dependency_overrides[get_supabase] = lambda: self.supabase
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        ca.invalider()
        roles.invalider()

    def appeler(self, methode: str, chemin: str, corps=None):
        appel = getattr(self.client, methode)
        return appel(chemin, json=corps) if corps is not None else appel(chemin)


class GardeTests(_BaseAdmin):
    def test_sans_allowlist_toutes_les_routes_refusent(self) -> None:
        with patch.dict(os.environ, {"ADMIN_USER_IDS": ""}):
            for methode, chemin, corps in ROUTES:
                with self.subTest(route=f"{methode.upper()} {chemin}"):
                    self.assertEqual(self.appeler(methode, chemin, corps).status_code, 403)

    def test_compte_hors_allowlist_refuse(self) -> None:
        with patch.dict(os.environ, {"ADMIN_USER_IDS": "quelquun-dautre"}):
            self.assertEqual(self.appeler("get", "/admin/aides").status_code, 403)

    def test_compte_du_socle_accepte(self) -> None:
        with patch.dict(os.environ, {"ADMIN_USER_IDS": " autre , u1 "}):
            for methode, chemin, corps in ROUTES:
                with self.subTest(route=f"{methode.upper()} {chemin}"):
                    self.assertEqual(self.appeler(methode, chemin, corps).status_code, 200)

    def test_compte_nomme_en_base_accepte_sans_variable(self) -> None:
        """Tout l'objet du chantier : la table suffit, le `.env` peut être vide."""
        self.supabase.rows[roles.TABLE] = [{"user_id": "u1", "role": "admin"}]
        roles.invalider()
        with patch.dict(os.environ, {"ADMIN_USER_IDS": ""}):
            for methode, chemin, corps in ROUTES:
                with self.subTest(route=f"{methode.upper()} {chemin}"):
                    self.assertEqual(self.appeler(methode, chemin, corps).status_code, 200)


class AidesTests(_BaseAdmin):
    def setUp(self) -> None:
        super().setUp()
        self.env = patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        super().tearDown()

    def test_liste_porte_les_retirees(self) -> None:
        self.supabase.rows[ca.TABLE_RETIREES] = [{"slug": SLUG, "motif": "doublon"}]
        lignes = self.appeler("get", "/admin/aides").json()
        ligne = next(item for item in lignes if item["slug"] == SLUG)
        self.assertTrue(ligne["retiree"])
        self.assertEqual(ligne["motif"], "doublon")
        self.assertEqual(len(lignes), len(load_all_aides()))

    def test_retrait_dun_slug_inconnu_est_404(self) -> None:
        reponse = self.appeler("put", "/admin/aides/slug-qui-nexiste-pas/retrait", {})
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.supabase.upserts, {})

    def test_retrait_ecrit_et_invalide_le_cache(self) -> None:
        with patch.object(ca, "invalider", wraps=ca.invalider) as espion:
            reponse = self.appeler("put", f"/admin/aides/{SLUG}/retrait", {"motif": "  fausse  "})
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["retiree"])
        self.assertEqual(self.supabase.upserts[ca.TABLE_RETIREES][0]["motif"], "fausse")
        self.assertEqual(self.supabase.upserts[ca.TABLE_RETIREES][0]["retiree_par"], "u1")
        espion.assert_called()

    def test_motif_vide_vaut_absence_de_motif(self) -> None:
        self.appeler("put", f"/admin/aides/{SLUG}/retrait", {"motif": "   "})
        self.assertIsNone(self.supabase.upserts[ca.TABLE_RETIREES][0]["motif"])

    def test_republication_supprime_la_ligne(self) -> None:
        self.supabase.rows[ca.TABLE_RETIREES] = [{"slug": SLUG, "motif": "doublon"}]
        reponse = self.appeler("delete", f"/admin/aides/{SLUG}/retrait")
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.json()["retiree"])
        self.assertEqual(self.supabase.suppressions[ca.TABLE_RETIREES], [[("slug", SLUG)]])

    def test_republication_dune_aide_absente_du_corpus_aboutit(self) -> None:
        """Aide archivée depuis son retrait : sa ligne doit pouvoir partir."""
        self.supabase.rows[ca.TABLE_RETIREES] = [{"slug": "aide-archivee"}]
        reponse = self.appeler("delete", "/admin/aides/aide-archivee/retrait")
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.json()["retiree"])

    def test_corps_hors_schema_refuse(self) -> None:
        reponse = self.appeler("put", f"/admin/aides/{SLUG}/retrait", {"actif": False})
        self.assertEqual(reponse.status_code, 422)


class FaitsTests(_BaseAdmin):
    def setUp(self) -> None:
        super().setUp()
        self.env = patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        super().tearDown()

    def _options(self) -> list[dict]:
        return [
            {"id": o.id, "label": o.label, "unknown": o.unknown}
            for o in load_facts()[FACT_ENUM].options or []
        ]

    def test_liste_porte_original_surcharge_et_impact(self) -> None:
        self.supabase.rows[ca.TABLE_SURCHARGES] = [
            {"fact_key": FACT_ENUM, "question": "Reformulée ?"}
        ]
        entree = next(
            f for f in self.appeler("get", "/admin/faits").json() if f["key"] == FACT_ENUM
        )
        self.assertEqual(entree["original"]["question"], load_facts()[FACT_ENUM].question)
        self.assertEqual(entree["surcharge"]["question"], "Reformulée ?")
        self.assertIn("parOption", entree["impactParOption"])

    def test_fait_inconnu_est_404(self) -> None:
        for methode, chemin, corps in (
            ("post", "/admin/faits/fait_inconnu/simuler", {"options": []}),
            ("put", "/admin/faits/fait_inconnu", {"question": "q ?"}),
            ("delete", "/admin/faits/fait_inconnu", None),
        ):
            with self.subTest(route=chemin):
                self.assertEqual(self.appeler(methode, chemin, corps).status_code, 404)

    def test_simuler_necrit_rien(self) -> None:
        reponse = self.appeler(
            "post", f"/admin/faits/{FACT_ENUM}/simuler", {"options": self._options()}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.supabase.upserts, {})
        self.assertEqual(len(reponse.json()["parOption"]), len(self._options()))

    def test_options_sur_un_fait_numerique_refusees(self) -> None:
        """Les tranches viennent des seuils des aides, pas du YAML."""
        reponse = self.appeler(
            "put", f"/admin/faits/{FACT_NUM}", {"options": [{"id": "a", "label": "A"}]}
        )
        self.assertEqual(reponse.status_code, 422)
        self.assertEqual(self.supabase.upserts, {})

    def test_options_sur_un_booleen_acceptees_et_la_valeur_part_dans_lupsert(self) -> None:
        """Le contrat que pyright ne tient pas : `_options()` doit PROPAGER
        `valeur` (il n'analyse pas `routers/`, un oubli passerait le type-check
        et partirait silencieusement à `None`)."""
        reponse = self.appeler(
            "put",
            f"/admin/faits/{FACT_BOOL}",
            {
                "options": [
                    {"id": "oui", "label": "Oui", "valeur": True},
                    {"id": "non", "label": "Non", "valeur": False},
                    {"id": "les_deux", "label": "Les deux", "valeur": None},
                ]
            },
        )
        self.assertEqual(reponse.status_code, 200)
        ecrit = self.supabase.upserts[ca.TABLE_SURCHARGES][0]["options"]
        self.assertEqual(
            [(o["id"], o["valeur"]) for o in ecrit],
            [("oui", True), ("non", False), ("les_deux", None)],
        )

    def test_booleen_sans_le_couple_refuse(self) -> None:
        """R1 : le serveur refuse par un 422 ce que le panneau interdit déjà."""
        reponse = self.appeler(
            "put",
            f"/admin/faits/{FACT_BOOL}",
            {"options": [{"id": "oui", "label": "Oui", "valeur": True}]},
        )
        self.assertEqual(reponse.status_code, 422)
        self.assertIn("non", reponse.json()["detail"])
        self.assertEqual(self.supabase.upserts, {})

    def test_valeur_sur_un_enum_refusee(self) -> None:
        """R2 : sur un fait à choix, l'identifiant EST la valeur."""
        options = [{**o, "valeur": True} for o in self._options()]
        reponse = self.appeler("put", f"/admin/faits/{FACT_ENUM}", {"options": options})
        self.assertEqual(reponse.status_code, 422)
        self.assertEqual(self.supabase.upserts, {})

    def test_simuler_sur_un_booleen_evalue_a_la_valeur_declaree(self) -> None:
        reponse = self.appeler(
            "post",
            f"/admin/faits/{FACT_BOOL}/simuler",
            {
                "options": [
                    {"id": "oui", "label": "Oui", "valeur": True},
                    {"id": "non", "label": "Non", "valeur": False},
                    {"id": "les_deux", "label": "Les deux", "valeur": None},
                ]
            },
        )
        self.assertEqual(reponse.status_code, 200)
        lignes = {item["id"]: item for item in reponse.json()["parOption"]}
        self.assertEqual(lignes["oui"]["valeur"], True)
        # Une réponse qui ne tranche pas n'écarte rien, par construction.
        self.assertEqual(lignes["les_deux"]["ecarte"], [])

    def test_id_doption_hors_format_refuse(self) -> None:
        reponse = self.appeler(
            "put", f"/admin/faits/{FACT_ENUM}", {"options": [{"id": "Oui !", "label": "Oui"}]}
        )
        self.assertEqual(reponse.status_code, 422)

    def test_surcharge_ecrit_et_invalide_le_cache(self) -> None:
        with patch.object(ca, "invalider", wraps=ca.invalider) as espion:
            reponse = self.appeler("put", f"/admin/faits/{FACT_ENUM}", {"question": "Reformulée ?"})
        self.assertEqual(reponse.status_code, 200)
        ecrit = self.supabase.upserts[ca.TABLE_SURCHARGES][0]
        self.assertEqual(ecrit["question"], "Reformulée ?")
        self.assertEqual(ecrit["modifie_par"], "u1")
        self.assertEqual(reponse.json()["surcharge"]["question"], "Reformulée ?")
        espion.assert_called()

    def test_brouillon_identique_a_loriginal_supprime_la_ligne(self) -> None:
        original = load_facts()[FACT_ENUM]
        self.supabase.rows[ca.TABLE_SURCHARGES] = [
            {"fact_key": FACT_ENUM, "question": "Reformulée ?"}
        ]
        reponse = self.appeler(
            "put",
            f"/admin/faits/{FACT_ENUM}",
            {"question": original.question, "options": self._options()},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.json()["surcharge"])
        self.assertEqual(
            self.supabase.suppressions[ca.TABLE_SURCHARGES], [[("fact_key", FACT_ENUM)]]
        )
        self.assertNotIn(ca.TABLE_SURCHARGES, self.supabase.upserts)

    def test_retablir_supprime_la_ligne(self) -> None:
        self.supabase.rows[ca.TABLE_SURCHARGES] = [
            {"fact_key": FACT_ENUM, "question": "Reformulée ?"}
        ]
        reponse = self.appeler("delete", f"/admin/faits/{FACT_ENUM}")
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.json()["surcharge"])
        self.assertEqual(
            self.supabase.suppressions[ca.TABLE_SURCHARGES], [[("fact_key", FACT_ENUM)]]
        )


if __name__ == "__main__":
    unittest.main()


class ConditionsTests(_BaseAdmin):
    """Les quatre routes de prédicats."""

    def setUp(self) -> None:
        super().setUp()
        self.env = patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        super().tearDown()

    def test_inventaire_porte_la_condition_et_ses_reponses(self) -> None:
        corps = self.appeler("get", "/admin/conditions").json()
        entree = next(
            c
            for c in corps["conditions"]
            if c["aideSlug"] == COND_SLUG and c["conditionId"] == COND_ID
        )
        self.assertEqual(entree["factKey"], COND_FACT)
        self.assertEqual([r["id"] for r in entree["reponses"]], COND_OPTIONS)
        self.assertIn(entree["operateur"], ("eq", "neq", "in", "not_in", "none_in"))
        self.assertIsNone(entree["surcharge"])

    def test_aide_inconnue_est_404(self) -> None:
        reponse = self.appeler(
            "put", f"/admin/conditions/aide-qui-nexiste-pas/{COND_ID}", PREDICAT_OK
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("Aide inconnue", reponse.json()["detail"])

    def test_condition_inconnue_est_404(self) -> None:
        reponse = self.appeler(
            "put", f"/admin/conditions/{COND_SLUG}/condition-absente", PREDICAT_OK
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("Condition inconnue", reponse.json()["detail"])

    def test_condition_hors_mandat_est_404(self) -> None:
        """Trois causes, trois messages distincts."""
        facts = {**load_facts(), **load_pending_facts()}
        hors = next(
            (aide.slug, c.id)
            for aide in load_all_aides().values()
            for c in aide.conditions
            if not ca.condition_modifiable(c, facts)
        )
        reponse = self.appeler("put", f"/admin/conditions/{hors[0]}/{hors[1]}", PREDICAT_OK)
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("ne se modifie pas ici", reponse.json()["detail"])

    def test_valeur_hors_options_est_422_au_message_du_lint(self) -> None:
        reponse = self.appeler(
            "put",
            f"/admin/conditions/{COND_SLUG}/{COND_ID}",
            {"operateur": "eq", "valeurs": ["reponse-qui-nexiste-pas"]},
        )
        self.assertEqual(reponse.status_code, 422)
        self.assertIn("hors options du fait", reponse.json()["detail"])
        self.assertEqual(self.supabase.upserts, {})

    def test_liste_de_valeurs_vide_refusee_par_le_type(self) -> None:
        """Inexprimable dans le corps : c'est le TYPE qui tient la contrainte,
        pas la bonne volonté du composant."""
        reponse = self.appeler(
            "put", f"/admin/conditions/{COND_SLUG}/{COND_ID}", {"operateur": "in", "valeurs": []}
        )
        self.assertEqual(reponse.status_code, 422)

    def test_combinateur_inexprimable_dans_le_corps(self) -> None:
        reponse = self.appeler(
            "put",
            f"/admin/conditions/{COND_SLUG}/{COND_ID}",
            {"operateur": "any_of", "valeurs": COND_OPTIONS},
        )
        self.assertEqual(reponse.status_code, 422)

    def test_simuler_necrit_rien(self) -> None:
        reponse = self.appeler(
            "post", f"/admin/conditions/{COND_SLUG}/{COND_ID}/simuler", PREDICAT_OK
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.supabase.upserts, {})
        corps = reponse.json()
        self.assertEqual({r["id"] for r in corps["parReponse"]}, set(COND_OPTIONS))
        self.assertIn("avertissements", corps)

    def test_surcharge_ecrit_les_trois_temoins_et_invalide_le_cache(self) -> None:
        with patch.object(ca, "invalider", wraps=ca.invalider) as espion:
            reponse = self.appeler(
                "put",
                f"/admin/conditions/{COND_SLUG}/{COND_ID}",
                {**PREDICAT_OK, "motif": " élargi "},
            )
        self.assertEqual(reponse.status_code, 200)
        ecrit = self.supabase.upserts[ca.TABLE_PREDICATS][0]
        condition = next(c for c in load_all_aides()[COND_SLUG].conditions if c.id == COND_ID)
        self.assertEqual(ecrit["condition_text"], condition.text)
        self.assertEqual(ecrit["fact_key"], COND_FACT)
        self.assertEqual(ecrit["predicate_origine"], dict(condition.predicate.root))
        self.assertEqual(ecrit["motif"], "élargi")
        self.assertEqual(ecrit["modifie_par"], "u1")
        espion.assert_called()

    def test_predicat_identique_au_yaml_supprime_la_ligne(self) -> None:
        """Une ligne qui recopie le YAML figerait la version d'avant."""
        condition = next(c for c in load_all_aides()[COND_SLUG].conditions if c.id == COND_ID)
        operateur, valeurs = ca.operateur_et_valeurs(condition.predicate.root)
        reponse = self.appeler(
            "put",
            f"/admin/conditions/{COND_SLUG}/{COND_ID}",
            {"operateur": operateur, "valeurs": valeurs},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.supabase.upserts, {})
        self.assertEqual(
            self.supabase.suppressions[ca.TABLE_PREDICATS],
            [[("aide_slug", COND_SLUG), ("condition_id", COND_ID)]],
        )

    def test_suppression_ne_vise_que_la_condition_visee(self) -> None:
        """Clé primaire COMPOSITE : les deux filtres doivent s'appliquer
        ensemble, sinon c'est toute l'aide qui part."""
        self.supabase.rows[ca.TABLE_PREDICATS] = [
            {"aide_slug": COND_SLUG, "condition_id": COND_ID},
            {"aide_slug": COND_SLUG, "condition_id": "une-autre-condition"},
        ]
        self.appeler("delete", f"/admin/conditions/{COND_SLUG}/{COND_ID}")
        restantes = self.supabase.rows[ca.TABLE_PREDICATS]
        self.assertEqual([r["condition_id"] for r in restantes], ["une-autre-condition"])

    def test_retablir_ne_renvoie_jamais_404(self) -> None:
        """Une ligne orpheline doit pouvoir partir."""
        reponse = self.appeler("delete", "/admin/conditions/aide-archivee/condition-partie")
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["absenteDuMandat"])

    def test_surcharge_orpheline_remontee_dans_linventaire(self) -> None:
        """Sinon elle resterait invisible ET insupprimable."""
        self.supabase.rows[ca.TABLE_PREDICATS] = [
            {
                "aide_slug": "aide-archivee",
                "condition_id": "c1",
                "predicate": {"eq": "a"},
                "condition_text": "t",
                "fact_key": "f",
                "predicate_origine": {"eq": "b"},
            }
        ]
        corps = self.appeler("get", "/admin/conditions").json()
        self.assertEqual(
            [(o["aideSlug"], o["conditionId"]) for o in corps["orphelines"]],
            [("aide-archivee", "c1")],
        )
        self.assertEqual(corps["orphelines"][0]["surcharge"]["etat"], "aide_absente")

    def test_surcharge_servie_puis_relue(self) -> None:
        """Bout en bout : écrire, puis relire l'inventaire et retrouver l'état."""
        self.appeler("put", f"/admin/conditions/{COND_SLUG}/{COND_ID}", PREDICAT_OK)
        corps = self.appeler("get", "/admin/conditions").json()
        entree = next(
            c
            for c in corps["conditions"]
            if c["aideSlug"] == COND_SLUG and c["conditionId"] == COND_ID
        )
        self.assertIsNotNone(entree["surcharge"])
        self.assertTrue(entree["surcharge"]["appliquee"])
        self.assertEqual(sorted(entree["valeurs"]), sorted(COND_OPTIONS))

    def test_surcharge_perimee_nest_pas_appliquee(self) -> None:
        condition = next(c for c in load_all_aides()[COND_SLUG].conditions if c.id == COND_ID)
        self.supabase.rows[ca.TABLE_PREDICATS] = [
            {
                "aide_slug": COND_SLUG,
                "condition_id": COND_ID,
                "predicate": ca.predicat_depuis("in", COND_OPTIONS),
                "condition_text": "un texte qui n’est plus celui de la condition",
                "fact_key": COND_FACT,
                "predicate_origine": dict(condition.predicate.root),
            }
        ]
        corps = self.appeler("get", "/admin/conditions").json()
        entree = next(
            c
            for c in corps["conditions"]
            if c["aideSlug"] == COND_SLUG and c["conditionId"] == COND_ID
        )
        self.assertEqual(entree["surcharge"]["etat"], "perimee_texte")
        self.assertFalse(entree["surcharge"]["appliquee"])
        # Le prédicat servi reste celui du YAML.
        self.assertEqual(
            ca.predicat_depuis(entree["operateur"], entree["valeurs"]),
            ca.canoniser_predicat(condition.predicate.root),
        )


class RolesTests(_BaseAdmin):
    """Les trois routes qui listent les comptes et basculent leurs rôles.

    L'enjeu n'est pas le CRUD mais quatre invariants : la page ne doit jamais
    pouvoir se fermer sur elle-même, elle ne doit jamais promettre un geste qui
    n'aura pas lieu (retirer un compte que le `.env` rouvre aussitôt), un
    bêta-testeur ne doit JAMAIS entrer ici, et ce que la liste annonce
    modifiable doit être exactement ce que le serveur accepte.
    """

    def setUp(self) -> None:
        super().setUp()
        self.env = patch.dict(os.environ, {"ADMIN_USER_IDS": "u1"})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        super().tearDown()

    def utilisateurs(self) -> dict[str, dict]:
        corps = self.appeler("get", "/admin/utilisateurs").json()
        return {ligne["userId"]: ligne for ligne in corps["utilisateurs"]}

    def test_les_roles_du_type_sont_ceux_du_service_et_de_la_base(self) -> None:
        """Le `Literal` de la route, `roles.ROLES` et la contrainte SQL doivent
        dire la même chose : un rôle ajouté à l'un et pas aux autres passerait la
        validation et échouerait à l'insertion."""
        from routers.admin import RoleAttribuable

        self.assertEqual(set(get_args(RoleAttribuable)), set(roles.ROLES))
        migration = (
            Path(__file__).resolve().parents[2]
            / "supabase/migrations/20260916064516_roles_de_compte.sql"
        ).read_text()
        for role in roles.ROLES:
            self.assertIn(f"'{role}'", migration)

    def test_la_liste_porte_tous_les_comptes_et_leurs_bascules(self) -> None:
        """On clique sur une ligne existante plutôt que de taper un email : la
        liste doit donc porter les comptes SANS rôle, eux aussi."""
        self.supabase.rows[roles.TABLE] = [
            {
                "user_id": AUTRE_ID,
                "role": "beta_testeur",
                "motif": "lot 2",
                "ajoute_par": "u1",
                "created_at": "2026-09-16T00:00:00+00:00",
            }
        ]
        par_id = self.utilisateurs()
        self.assertEqual(set(par_id), {"u1", AUTRE_ID})

        associe = par_id[AUTRE_ID]
        self.assertEqual(associe["email"], AUTRE_EMAIL)
        self.assertEqual(associe["prenom"], "Associé")
        beta = associe["roles"]["beta_testeur"]
        self.assertTrue(beta["actif"])
        self.assertEqual(beta["source"], "base")
        self.assertTrue(beta["modifiable"])
        self.assertEqual(beta["motif"], "lot 2")
        # Qui a attribué, par son email : un UUID ne dit rien six mois plus tard.
        self.assertEqual(beta["ajoutePar"], "fondateur@monumia.fr")
        # Et l'autre bascule est simplement éteinte, pas absente.
        self.assertFalse(associe["roles"]["admin"]["actif"])
        self.assertIsNone(associe["roles"]["admin"]["source"])
        self.assertTrue(associe["roles"]["admin"]["modifiable"])

    def test_la_liste_dit_ce_que_le_serveur_accepte(self) -> None:
        """L'invariant qui tient l'écran : une bascule annoncée modifiable
        aboutit, une bascule bloquée part en 409. Un bouton qui échoue est un
        bouton qui n'aurait pas dû s'afficher."""
        self.supabase.rows[roles.TABLE] = [
            {"user_id": "u1", "role": "beta_testeur"},
            {"user_id": AUTRE_ID, "role": "admin"},
            {"user_id": AUTRE_ID, "role": "beta_testeur"},
        ]
        roles.invalider()
        for user_id, ligne in self.utilisateurs().items():
            for role, etat in ligne["roles"].items():
                if not etat["actif"]:
                    continue
                with self.subTest(compte=user_id, role=role):
                    attendu = 200 if etat["modifiable"] else 409
                    reponse = self.appeler("delete", f"/admin/roles/{role}/{user_id}")
                    self.assertEqual(reponse.status_code, attendu)
                    if attendu == 409:
                        self.assertTrue(etat["raison"])

    def test_basculer_admin_donne_la_main(self) -> None:
        ligne = self.appeler("put", f"/admin/roles/admin/{AUTRE_ID}").json()
        self.assertEqual(ligne["userId"], AUTRE_ID)
        self.assertTrue(ligne["roles"]["admin"]["actif"])
        self.assertTrue(roles.est_admin(self.supabase, AUTRE_ID))
        ecrit = self.supabase.upserts[roles.TABLE][-1]
        self.assertEqual(ecrit["user_id"], AUTRE_ID)
        self.assertEqual(ecrit["role"], "admin")
        self.assertEqual(ecrit["ajoute_par"], "u1")

    def test_beta_testeur_n_ouvre_pas_la_page(self) -> None:
        """Le point du chantier : l'offre sans le catalogue. Un bêta-testeur est
        dans la table, et chaque route d'administration lui répond 403."""
        self.appeler("put", f"/admin/roles/beta_testeur/{AUTRE_ID}")
        self.assertFalse(roles.est_admin(self.supabase, AUTRE_ID))

        app.dependency_overrides[get_current_user_id] = lambda: AUTRE_ID
        with patch.dict(os.environ, {"ADMIN_USER_IDS": ""}):
            for methode, chemin, corps in ROUTES:
                with self.subTest(route=f"{methode.upper()} {chemin}"):
                    self.assertEqual(self.appeler(methode, chemin, corps).status_code, 403)

    def test_les_deux_roles_se_cumulent_et_se_retirent_separement(self) -> None:
        self.appeler("put", f"/admin/roles/admin/{AUTRE_ID}")
        ligne = self.appeler("put", f"/admin/roles/beta_testeur/{AUTRE_ID}").json()
        self.assertEqual(
            {role for role, etat in ligne["roles"].items() if etat["actif"]},
            {"admin", "beta_testeur"},
        )
        ligne = self.appeler("delete", f"/admin/roles/beta_testeur/{AUTRE_ID}").json()
        self.assertEqual(
            {role for role, etat in ligne["roles"].items() if etat["actif"]}, {"admin"}
        )
        self.assertTrue(roles.est_admin(self.supabase, AUTRE_ID))

    def test_role_inconnu_est_refuse_par_le_type(self) -> None:
        reponse = self.appeler("put", f"/admin/roles/super_admin/{AUTRE_ID}")
        self.assertEqual(reponse.status_code, 422)
        self.assertEqual(self.supabase.upserts.get(roles.TABLE), None)

    def test_attribution_est_idempotente(self) -> None:
        """Ce qu'exige une bascule : un double-clic, ou deux onglets ouverts, ne
        doivent pas produire deux lignes ni une erreur."""
        self.appeler("put", f"/admin/roles/admin/{AUTRE_ID}")
        self.appeler("put", f"/admin/roles/admin/{AUTRE_ID}")
        self.assertEqual(len(self.supabase.rows[roles.TABLE]), 1)
        self.assertTrue(self.utilisateurs()[AUTRE_ID]["roles"]["admin"]["actif"])

    def test_identifiant_inconnu_est_404(self) -> None:
        """La clé étrangère le refuserait, mais par une erreur qui sortirait en
        500 : mieux vaut un 404 qui dit ce qui s'est passé."""
        reponse = self.appeler("put", "/admin/roles/admin/jamais-inscrit")
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.supabase.upserts.get(roles.TABLE), None)

    def test_retrait_reprend_la_main(self) -> None:
        self.appeler("put", f"/admin/roles/admin/{AUTRE_ID}")
        ligne = self.appeler("delete", f"/admin/roles/admin/{AUTRE_ID}").json()
        self.assertFalse(ligne["roles"]["admin"]["actif"])
        self.assertFalse(roles.est_admin(self.supabase, AUTRE_ID))

    def test_se_retirer_l_administration_est_refuse(self) -> None:
        """Le seul geste de cette page qui pourrait la fermer pour de bon."""
        self.supabase.rows[roles.TABLE] = [{"user_id": "u1", "role": "admin"}]
        roles.invalider()
        reponse = self.appeler("delete", "/admin/roles/admin/u1")
        self.assertEqual(reponse.status_code, 409)
        self.assertTrue(roles.est_admin(self.supabase, "u1"))

    def test_se_retirer_son_propre_role_de_beta_testeur_est_permis(self) -> None:
        """Le refus porte sur l'ADMINISTRATION, pas sur l'appartenance à soi :
        retirer son bêta-test ne ferme aucune porte."""
        self.supabase.rows[roles.TABLE] = [{"user_id": "u1", "role": "beta_testeur"}]
        roles.invalider()
        self.assertTrue(self.utilisateurs()["u1"]["roles"]["beta_testeur"]["modifiable"])
        self.assertEqual(self.appeler("delete", "/admin/roles/beta_testeur/u1").status_code, 200)

    def test_retirer_l_administration_a_un_compte_du_socle_est_refuse(self) -> None:
        """La suppression réussirait, le `.env` le rouvrirait, et la page
        mentirait."""
        with patch.dict(os.environ, {"ADMIN_USER_IDS": f"u1,{AUTRE_ID}"}):
            etat = self.utilisateurs()[AUTRE_ID]["roles"]["admin"]
            self.assertEqual(etat["source"], "socle")
            self.assertFalse(etat["modifiable"])
            reponse = self.appeler("delete", f"/admin/roles/admin/{AUTRE_ID}")
        self.assertEqual(reponse.status_code, 409)
        self.assertIn("ADMIN_USER_IDS", reponse.json()["detail"])

    def test_le_socle_ne_protege_que_l_administration(self) -> None:
        """Il ne porte que le rôle `admin` : le bêta-test d'un compte du socle
        reste retirable depuis la page."""
        self.supabase.rows[roles.TABLE] = [{"user_id": AUTRE_ID, "role": "beta_testeur"}]
        roles.invalider()
        with patch.dict(os.environ, {"ADMIN_USER_IDS": f"u1,{AUTRE_ID}"}):
            reponse = self.appeler("delete", f"/admin/roles/beta_testeur/{AUTRE_ID}")
        self.assertEqual(reponse.status_code, 200)

    def test_retirer_un_role_non_porte_ne_se_plaint_pas(self) -> None:
        """Idempotent, comme la republication d'une aide : une ligne orpheline
        doit pouvoir partir."""
        self.assertEqual(self.appeler("delete", f"/admin/roles/admin/{AUTRE_ID}").status_code, 200)

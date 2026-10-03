"""Tests de l'application des mises à jour de veille (scripts/veille_apply.py).

Le test qui compte est `TestSortieVideDiffVide` : appliquer une sortie vide aux
142 fiches doit rendre des fichiers strictement identiques, octet pour octet.
Les YAML sont écrits à la main et le `git diff` EST la revue humaine — un
éditeur qui reformate noie la vraie modification et supprime le seul contrôle
qui empêche une hallucination d'entrer dans les données.

Le reste vérifie que la chaîne de validation refuse ce qu'elle doit refuser :
citations inventées, re-typage déguisé, champs hors périmètre, et surtout tout
splice qui produirait autre chose que ce qui était demandé.

Run from backend/:  uv run pytest tests/test_veille_apply.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from veille_apply import (  # noqa: E402
    VeilleLLMOutput,
    _localiser_condition,
    appliquer,
    attendu_apres,
    check_quotes,
    check_referentiel,
    deep_diff,
    emit_field,
    parse_output,
)

from aides_schema import AIDES_DIR, Aide, charger_yaml, load_aide  # noqa: E402

AUJOURD_HUI = "2026-08-06"

FICHE = """slug: aide-test
nom: Aide de test
organisme: Organisme de test
categorie: region
type: subvention
raison:
  - restauration_travaux
description: >-
  Une aide de test pour la restauration du patrimoine rural, dotée d'une
  description suffisamment longue pour occuper un block scalar replié.

source:
  url_officielle: https://ex.fr/aide
  verified_at: 2026-07-01

financement:
  taux_max: 30.0

cumul:
  cumulable: true

calendrier:
  permanent: false
  date_limite: 2026-05-30

conditions:
  - id: edifice-anterieur-1800
    text: L'édifice doit être antérieur à 1800.
    kind: user_fact
    effect: gate
    fact: annee_construction
    predicate:
      lt: 1800
    quote: antérieurs à 1800,

  - id: montant-moyen
    text: Les dossiers sélectionnés reçoivent 5 000 € en moyenne.
    kind: info
    effect: info
    quote: une aide de 5 000 € en moyenne.
    notes: >-
      Montant moyen indicatif, pas un plafond — d'où l'absence de montant_max
      structuré dans la fiche.

tags:
  - test
"""

SOURCE_FRAICHE = """# Aide à la restauration

Les édifices antérieurs à 1800, non classés, sont éligibles.
Les dossiers sélectionnés reçoivent une aide de 8 000 € en moyenne.
Le taux d'intervention est porté à 40 % du montant des travaux.
Le dépôt est ouvert jusqu'au 30 novembre 2026.
Un architecte du patrimoine est désormais requis pour les édifices classés.
"""

DOCS = [("frais.md", SOURCE_FRAICHE, "text")]


def ecrire_fiche(contenu: str = FICHE) -> tuple[Path, Aide, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name) / "aide-test.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin, load_aide(chemin), tmp


def sortie(**kwargs) -> str:
    import json

    return json.dumps({"slug": "aide-test", "resume": "", **kwargs}, ensure_ascii=False)


class TestSortieVideDiffVide(unittest.TestCase):
    """Le test canonique du module.

    Une sortie vide ne doit RIEN changer — pas un espace, pas un repli de ligne
    — sur aucune des 142 fiches du dépôt, quels que soient leurs styles.
    """

    def test_142_fiches_inchangees_octet_pour_octet(self):
        chemins = sorted(AIDES_DIR.glob("*.yaml"))
        self.assertGreater(len(chemins), 100, "le dépôt doit contenir les fiches réelles")
        modifiees = []
        for chemin in chemins:
            aide = load_aide(chemin)
            avant = chemin.read_text(encoding="utf-8")
            res = appliquer(sortie(slug=aide.slug), aide, chemin, DOCS, aujourd_hui=AUJOURD_HUI)
            self.assertTrue(res.ok, f"{aide.slug} : {res.erreurs}")
            if res.texte != avant:
                modifiees.append(aide.slug)
        self.assertEqual(modifiees, [], f"fiches modifiées par une sortie vide : {modifiees}")

    def test_aucune_ecriture_disque(self):
        # `appliquer` ne doit jamais écrire : c'est ce qui rend --dry-run gratuit.
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            avant = chemin.read_text(encoding="utf-8")
            appliquer(
                sortie(
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": "taux d'intervention est porté à 40 %",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertEqual(chemin.read_text(encoding="utf-8"), avant)


class TestLocalisationConditions(unittest.TestCase):
    """Second test canonique : toute condition du dépôt doit être localisable.

    Le test de sortie vide ne l'exerce pas — sans édition, aucun repérage. Il a
    donc laissé passer, jusqu'au run pilote, que les 26 fiches écrivant leurs
    conditions au même niveau que la clé `conditions:` étaient intouchables :
    le bloc s'arrêtait à sa première ligne, aucune condition n'y était trouvée.
    """

    def test_toutes_les_conditions_du_depot_sont_reperables(self):
        chemins = sorted(AIDES_DIR.glob("*.yaml"))
        self.assertGreater(len(chemins), 100, "le dépôt doit contenir les fiches réelles")
        introuvables, mal_delimitees = [], []
        for chemin in chemins:
            lignes = chemin.read_text(encoding="utf-8").split("\n")
            attendues = {
                c["id"]: c for c in (charger_yaml("\n".join(lignes)).get("conditions") or [])
            }
            for cond_id, attendue in attendues.items():
                span = _localiser_condition(lignes, cond_id)
                if span is None:
                    introuvables.append(f"{chemin.stem}/{cond_id}")
                    continue
                bloc = lignes[span[0] : span[1]]
                marge = len(bloc[0]) - len(bloc[0].lstrip())
                relu = charger_yaml("\n".join(ligne[marge:] for ligne in bloc))
                # La plage doit couvrir l'item ENTIER et rien d'autre : un span
                # trop court tronquerait la condition à la réécriture, un span
                # trop long avalerait la suivante.
                if relu != [attendue]:
                    mal_delimitees.append(f"{chemin.stem}/{cond_id}")
        self.assertEqual(introuvables, [], f"conditions introuvables : {introuvables[:10]}")
        self.assertEqual(mal_delimitees, [], f"plages fautives : {mal_delimitees[:10]}")


class TestApplicationReelle(unittest.TestCase):
    def test_condition_modifiee_dans_une_fiche_a_liste_plate(self):
        # Style YAML où les items sont au même niveau que `conditions:` — 26
        # fiches du dépôt, dont `fctva`, sur laquelle le run pilote a buté.
        plate = FICHE.replace("\n  - id:", "\n- id:").replace("\n    ", "\n  ")
        chemin, aide, tmp = ecrire_fiche(plate)
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {
                            "op": "update",
                            "id": "montant-moyen",
                            "champs": {"quote": "une aide de 8 000 € en moyenne."},
                        }
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            assert res.texte is not None
            self.assertIn("quote: une aide de 8 000 € en moyenne.", res.texte)
            # Les autres champs de l'item survivent intacts.
            self.assertIn("  kind: info", res.texte)
            self.assertIn("\ntags:", res.texte)

    def test_montant_modifie_dans_une_condition(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {
                            "op": "update",
                            "id": "montant-moyen",
                            "champs": {"quote": "une aide de 8 000 € en moyenne."},
                        }
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            assert res.texte is not None
            self.assertIn("une aide de 8 000 € en moyenne.", res.texte)
            self.assertNotIn("une aide de 5 000 € en moyenne.", res.texte)
            # Le reste du fichier est intact, y compris les block scalars voisins.
            self.assertIn("Montant moyen indicatif, pas un plafond", res.texte)
            self.assertIn("  - id: edifice-anterieur-1800", res.texte)

    def test_date_limite_et_taux(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    calendrier={
                        "champs": {"date_limite": "2026-11-30"},
                        "quote": "ouvert jusqu'au 30 novembre 2026",
                    },
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": "taux d'intervention est porté à 40 %",
                    },
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            recharge = charger_yaml(res.texte)
            self.assertEqual(str(recharge["calendrier"]["date_limite"]), "2026-11-30")
            self.assertEqual(recharge["financement"]["taux_max"], 40.0)
            # `permanent: false` n'était pas visé : il ne bouge pas.
            self.assertIs(recharge["calendrier"]["permanent"], False)

    def test_champ_absent_est_ajoute_a_la_section(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    financement={
                        "champs": {"montant_max": 8000.0},
                        "quote": "une aide de 8 000 € en moyenne.",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            recharge = charger_yaml(res.texte)
            self.assertEqual(recharge["financement"]["montant_max"], 8000.0)
            self.assertEqual(recharge["financement"]["taux_max"], 30.0)

    def test_condition_ajoutee_est_untyped_et_tracee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {
                            "op": "add",
                            "id": "architecte-requis",
                            "apres_id": "edifice-anterieur-1800",
                            "condition": {
                                "id": "architecte-requis",
                                "text": "Un architecte du patrimoine est requis pour les édifices classés.",
                                "quote": "Un architecte du patrimoine est désormais requis",
                            },
                        }
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            recharge = charger_yaml(res.texte)
            ids = [c["id"] for c in recharge["conditions"]]
            self.assertEqual(ids, ["edifice-anterieur-1800", "architecte-requis", "montant-moyen"])
            ajoutee = recharge["conditions"][1]
            # Jamais typée par la veille : /typer-aides doit pouvoir la retrouver.
            self.assertEqual(ajoutee["kind"], "untyped")
            self.assertIn("ajoutée par veille du 2026-08-06, à typer", ajoutee["notes"])

    def test_deux_conditions_ajoutees_gardent_leur_ordre(self):
        # Deux insertions au même point : l'application se fait de la fin vers
        # le début, et sans rang dans la clé de tri elles ressortaient
        # permutées. Détecté par l'assertion de différence profonde au premier
        # benchmark réel, sur une réponse qui en proposait deux.
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {
                            "op": "add",
                            "id": "premiere-ajoutee",
                            "condition": {
                                "id": "premiere-ajoutee",
                                "text": "Un architecte du patrimoine est requis.",
                                "quote": "Un architecte du patrimoine est désormais requis",
                            },
                        },
                        {
                            "op": "add",
                            "id": "seconde-ajoutee",
                            "condition": {
                                "id": "seconde-ajoutee",
                                "text": "Le dépôt est ouvert jusqu'au 30 novembre 2026.",
                                "quote": "Le dépôt est ouvert jusqu'au 30 novembre 2026.",
                            },
                        },
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            ids = [c["id"] for c in charger_yaml(res.texte)["conditions"]]
            self.assertEqual(ids[-2:], ["premiere-ajoutee", "seconde-ajoutee"])

    def test_condition_disparue_est_annotee_jamais_supprimee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(conditions=[{"op": "signaler_disparue", "id": "montant-moyen"}]),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            recharge = charger_yaml(res.texte)
            cond = next(c for c in recharge["conditions"] if c["id"] == "montant-moyen")
            self.assertIn("non retrouvée dans la source du 2026-08-06", cond["notes"])
            # La note d'origine survit, et la condition aussi.
            self.assertIn("Montant moyen indicatif", cond["notes"])
            self.assertEqual(len(recharge["conditions"]), 2)

    def test_retouche_cosmetique_ignoree(self):
        # Apostrophe courbe au lieu de droite : le fond est identique, réécrire
        # polluerait le diff pour rien.
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            avant = chemin.read_text(encoding="utf-8")
            res = appliquer(
                sortie(
                    conditions=[
                        {
                            "op": "update",
                            "id": "edifice-anterieur-1800",
                            "champs": {"quote": "antérieurs à 1800,"},
                        }
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)
            self.assertEqual(res.texte, avant)
            self.assertEqual(res.cosmetiques, 1)


class TestRefusValidation(unittest.TestCase):
    def test_citation_inventee_refusee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    financement={
                        "champs": {"taux_max": 80.0},
                        "quote": "le taux est porté à 80 % pour les monuments classés",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "quote")
            self.assertTrue(res.rattrapable)

    def test_retypage_deguise_refuse(self):
        # Changer `kind` est un changement majeur, pas une retouche.
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {"op": "update", "id": "montant-moyen", "champs": {"kind": "user_fact"}}
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "referentiel")
            self.assertTrue(any("changement majeur" in e for e in res.erreurs))

    def test_champ_hors_perimetre_refuse(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(calendrier={"champs": {"description": "x"}, "quote": "antérieurs à 1800"}),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "referentiel")

    def test_condition_inconnue_refusee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[
                        {"op": "update", "id": "condition-fantome", "champs": {"text": "x"}}
                    ]
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "referentiel")

    def test_changement_majeur_autodeclare_escalade(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    changement_majeur=True, raison_changement_majeur="page entièrement refondue"
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertFalse(res.ok)
            self.assertIn("page entièrement refondue", res.erreurs[0])
            # Une escalade est une RÉPONSE : la rejouer coûterait un appel pour
            # rien, au mieux la même réponse, au pire une contradiction.
            self.assertEqual(res.etape, "majeur")
            self.assertFalse(res.rattrapable)

    def test_json_invalide_et_fences(self):
        out, erreurs, etape = parse_output("pas du json", "aide-test")
        self.assertIsNone(out)
        self.assertEqual(etape, "json")
        # Les fences markdown sont retirées : les modèles en produisent souvent.
        out, _, _ = parse_output('```json\n{"slug": "aide-test"}\n```', "aide-test")
        self.assertIsNotNone(out)
        self.assertEqual(out.slug, "aide-test")

    def test_champ_inconnu_du_schema_refuse(self):
        out, erreurs, etape = parse_output('{"slug": "aide-test", "montant": 1000}', "aide-test")
        self.assertIsNone(out)
        self.assertEqual(etape, "schema")

    def test_slug_d_une_autre_aide_refuse(self):
        _, aide, tmp = ecrire_fiche()
        with tmp:
            out = VeilleLLMOutput.model_validate({"slug": "une-autre-aide"})
            self.assertTrue(any("slug" in e for e in check_referentiel(out, aide)))

    def test_sans_contenu_frais_aucune_citation_ne_passe(self):
        out = VeilleLLMOutput.model_validate(
            {"slug": "aide-test", "cumul": {"champs": {"cumulable": False}, "quote": "x"}}
        )
        self.assertTrue(check_quotes(out, []))


class TestDeepDiff(unittest.TestCase):
    """Le filet de sécurité : un splice non conforme doit être détecté."""

    def test_temoin_et_fichier_concordent(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            out = VeilleLLMOutput.model_validate(
                {
                    "slug": "aide-test",
                    "financement": {
                        "champs": {"taux_max": 40.0},
                        "quote": "taux d'intervention est porté à 40 %",
                    },
                }
            )
            res = appliquer(out.model_dump_json(), aide, chemin, DOCS, aujourd_hui=AUJOURD_HUI)
            self.assertTrue(res.ok, res.erreurs)
            attendu = attendu_apres(charger_yaml(chemin.read_text()), out, AUJOURD_HUI)
            self.assertEqual(deep_diff(attendu, charger_yaml(res.texte)), [])

    def test_ecart_detecte(self):
        self.assertTrue(deep_diff({"a": 1}, {"a": 2}))
        self.assertTrue(deep_diff({"a": [1, 2]}, {"a": [1]}))
        self.assertTrue(deep_diff({"a": 1}, {"a": 1, "b": 2}))
        self.assertEqual(
            deep_diff({"a": 1, "b": [1, {"c": "x"}]}, {"a": 1, "b": [1, {"c": "x"}]}), []
        )

    def test_date_et_nombre_compares_apres_normalisation(self):
        # PyYAML rend une date en `datetime.date` et 30.0 en float : la
        # comparaison ne doit pas échouer là-dessus.
        import datetime

        self.assertEqual(deep_diff({"d": "2026-05-30"}, {"d": datetime.date(2026, 5, 30)}), [])
        self.assertEqual(deep_diff({"n": 30}, {"n": 30.0}), [])


class TestEmitField(unittest.TestCase):
    def test_scalaire_court_en_ligne(self):
        self.assertEqual(emit_field("kind", "info", 4), ["    kind: info"])

    def test_booleen_et_nombre(self):
        self.assertEqual(emit_field("permanent", False, 2), ["  permanent: false"])
        self.assertEqual(emit_field("taux_max", 40.0, 2), ["  taux_max: 40.0"])

    def test_texte_long_replie(self):
        texte = "Les travaux doivent concerner le gros œuvre : " * 4
        lignes = emit_field("text", texte.strip(), 4)
        self.assertEqual(lignes[0], "    text: >-")
        self.assertTrue(all(ligne.startswith("      ") for ligne in lignes[1:]))
        # Aucune ligne sur-indentée : dans un `>-`, elle serait prise au pied
        # de la lettre et injecterait un saut de ligne.
        self.assertTrue(all(not ligne[6:7].isspace() for ligne in lignes[1:]))
        self.assertEqual(charger_yaml("\n".join(lignes).strip())["text"], texte.strip())

    def test_sauts_de_ligne_significatifs_en_litteral(self):
        lignes = emit_field("quote", "Première ligne.\n\nSeconde ligne.", 4)
        self.assertEqual(lignes[0], "    quote: |-")
        self.assertEqual(
            charger_yaml("\n".join(lignes).strip())["quote"],
            "Première ligne.\n\nSeconde ligne.",
        )

    def test_valeurs_piegeuses_ne_partent_pas_en_clair(self):
        # « oui: non » serait un mapping ; « true » un booléen ; « 40 » un entier.
        for valeur in ("oui: non", "true", "40", "- tiret", "#commentaire", "a  "):
            rendu = "\n".join(emit_field("quote", valeur, 0))
            self.assertEqual(charger_yaml(rendu)["quote"], valeur, f"valeur : {valeur!r}")

    def test_liste(self):
        lignes = emit_field("exclusions", ["maprimerenov", "DETR"], 2)
        self.assertEqual(
            charger_yaml("\n".join(lignes).strip())["exclusions"], ["maprimerenov", "DETR"]
        )


class TestAncrageDansLeDiff(unittest.TestCase):
    """Une citation authentique ne prouve rien si la page n'a pas bougé dessus.

    Cas réel qui a motivé l'étape : sur `pdl-restauration-mh`, deux modèles de
    fournisseurs différents ont proposé de réécrire le taux en citant mot pour
    mot une page qui disait la même chose depuis toujours. `check_quotes`
    laissait passer — la citation EST dans la page. Le diff, lui, ne contenait
    que des libellés de menu.
    """

    # Le diff ne parle QUE du dépôt : toute proposition sur le taux est donc
    # non ancrée, même parfaitement citée depuis la source fraîche.
    DIFF = (
        "  Les édifices antérieurs à 1800, non classés, sont éligibles.\n"
        "- Le dépôt est ouvert jusqu'au 15 novembre 2026.\n"
        "+ Le dépôt est ouvert jusqu'au 30 novembre 2026.\n"
    )

    def test_citation_hors_diff_escalade(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": "Le taux d'intervention est porté à 40 % du montant des travaux.",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff=self.DIFF,
            )
            # La citation passe `check_quotes` (elle est dans SOURCE_FRAICHE)
            # et bute sur l'ancrage.
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "ancrage")
            # Ne pas relancer le modèle : il n'a rien à corriger.
            self.assertFalse(res.rattrapable)

    def test_citation_dans_le_diff_acceptee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    calendrier={
                        "champs": {"date_limite": "2026-11-30"},
                        "quote": "Le dépôt est ouvert jusqu'au 30 novembre 2026.",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff=self.DIFF,
            )
            self.assertTrue(res.ok, res.erreurs)

    def test_citation_seulement_supprimee_refusee_des_l_etape_quote(self):
        """Une citation issue des lignes `-` décrit l'ANCIEN règlement.

        Elle est refusée dès `check_quotes` et n'atteint pas l'ancrage : un
        texte supprimé de la page n'est, par définition, plus dans le contenu
        frais. L'ancrage ne sert donc que pour les citations qui SONT dans la
        page fraîche — c'est précisément le trou qu'il vient boucher.
        """
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    calendrier={
                        "champs": {"date_limite": "2026-11-15"},
                        "quote": "Le dépôt est ouvert jusqu'au 15 novembre 2026.",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff=self.DIFF,
            )
            self.assertFalse(res.ok)
            self.assertEqual(res.etape, "quote")

    def test_sortie_vide_sans_lignes_ajoutees_reste_valide(self):
        """Le cas nominal : rien à retoucher, et un diff sans ajout."""
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(conditions=[]),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff="- une ligne retirée seulement\n",
            )
            self.assertTrue(res.ok, res.erreurs)

    def test_signaler_disparue_echappe_a_l_ancrage(self):
        """Ce qui la motive est une absence, pas une citation."""
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(conditions=[{"op": "signaler_disparue", "id": "edifice-anterieur-1800"}]),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff=self.DIFF,
            )
            # `assertTrue(res.ok)` et non `assertNotEqual(etape, "ancrage")` : la
            # première version de ce test visait un id de condition inexistant,
            # butait au référentiel, et passait sans rien prouver de l'ancrage.
            self.assertTrue(res.ok, res.erreurs)

    def test_citation_multiligne_entrecoupee_de_contexte_acceptee(self):
        """Une citation de tableau enjambe des lignes inchangées.

        Régression mesurée sur `56-valorisation-restauration-patrimoine` : trois
        lignes de la citation étaient bien des ajouts, mais séparées par du
        contexte. Exiger la citation contiguë dans les seuls ajouts rejetait un
        vrai changement de barème (préfixe commun 53 %).
        """
        diff = (
            "  Les édifices antérieurs à 1800, non classés, sont éligibles.\n"
            "+ Le taux d'intervention est porté à 40 % du montant des travaux.\n"
            "  ligne de contexte inchangée au milieu du tableau\n"
            "+ Le dépôt est ouvert jusqu'au 30 novembre 2026.\n"
        )
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": (
                            "Le taux d'intervention est porté à 40 % du montant des travaux.\n"
                            "ligne de contexte inchangée au milieu du tableau\n"
                            "Le dépôt est ouvert jusqu'au 30 novembre 2026."
                        ),
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff=diff,
            )
            self.assertNotEqual(res.etape, "ancrage")

    def test_sans_diff_le_controle_est_inactif(self):
        """Appelant qui ne fournit pas de diff (benchmark brut) : pas de blocage."""
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": "Le taux d'intervention est porté à 40 % du montant des travaux.",
                    }
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
            )
            self.assertTrue(res.ok, res.erreurs)


if __name__ == "__main__":
    unittest.main()


class TestDisparitionSurSuppressionSeule(unittest.TestCase):
    """Un diff fait uniquement de lignes retirées appelle `signaler_disparue`.

    C'est le cas nominal de cette op, et l'ancrage la refusait (« aucune ligne
    ajoutée ») : la condition partait en escalade au lieu d'être annotée.
    """

    def test_signaler_disparue_acceptee_sans_ligne_ajoutee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(conditions=[{"op": "signaler_disparue", "id": "edifice-anterieur-1800"}]),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff="- Les édifices antérieurs à 1800, non classés, sont éligibles.\n",
            )
            self.assertTrue(res.ok, res.erreurs)
            self.assertIn("non retrouvée dans la source", res.texte or "")

    def test_une_retouche_sans_ligne_ajoutee_reste_refusee(self):
        chemin, aide, tmp = ecrire_fiche()
        with tmp:
            res = appliquer(
                sortie(
                    conditions=[{"op": "signaler_disparue", "id": "edifice-anterieur-1800"}],
                    financement={
                        "champs": {"taux_max": 40.0},
                        "quote": "Le taux d'intervention est porté à 40 % du montant des travaux.",
                    },
                ),
                aide,
                chemin,
                DOCS,
                aujourd_hui=AUJOURD_HUI,
                diff="- une ligne retirée seulement\n",
            )
            self.assertEqual(res.etape, "ancrage")


class TestJsonSuiviDeTexte(unittest.TestCase):
    """Un objet JSON complet suivi d'un commentaire est lu ; un JSON cassé reste refusé."""

    def test_texte_apres_l_objet_tolere(self):
        from veille_apply import VeilleLLMOutput, parse_json_output

        out, erreurs, etape = parse_json_output(
            '{"slug": "aide-test", "conditions": []}\nVoilà, rien à signaler.', VeilleLLMOutput
        )
        self.assertIsNotNone(out)
        self.assertEqual((erreurs, etape), ([], None))

    def test_objet_tronque_toujours_refuse(self):
        from veille_apply import VeilleLLMOutput, parse_json_output

        out, _, etape = parse_json_output('{"slug": "aide-test", "conditions": [', VeilleLLMOutput)
        self.assertIsNone(out)
        self.assertEqual(etape, "json")

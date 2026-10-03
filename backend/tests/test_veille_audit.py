"""Tests de l'audit d'exhaustivité des fiches (scripts/veille_audit.py).

Ce qui est vérifié ici n'est pas la qualité du modèle — le pilote de l'étape 8
s'en charge — mais la conduite autour de lui : qui est (ré)audité et qui est
sauté, ce que la validation refuse, et surtout ce qu'on N'écrit PAS. Le modèle
est donc remplacé par une réponse fixée, et aucun test ne touche au réseau.

Deux tests font office de filet canonique :
  - `TestSortieConformeDiffVide` : un relevé ne contenant que des `conforme`
    appliqué aux 141 fiches du dépôt ne doit modifier aucun octet.
  - `TestSelection` : une aide dont ni la fiche ni les sources n'ont bougé doit
    être sautée sans appel réseau ni modèle — c'est ce qui rend le régime de
    croisière quasi gratuit.

Run from backend/:  uv run pytest tests/test_veille_audit.py
"""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_audit  # noqa: E402
from veille_audit import (  # noqa: E402
    MAX_AJOUTS_CONDITIONS,
    AuditLLMOutput,
    AuditResult,
    Corpus,
    DocAudit,
    auditer,
    check_doublons,
    check_quotes_audit,
    check_referentiel_audit,
    construire_corpus,
    date_dernier_audit,
    raison_audit,
    selectionner,
    sha_fiche,
    sha_sources,
    sortie_ajouts,
    update_manifest_audit,
    valider,
)
from veille_collect import AideCollect, FetchResult, MonitoredUrl  # noqa: E402
from veille_llm import LLMCall, ModelSpec  # noqa: E402

from aides_schema import AIDES_DIR, Aide, load_aide  # noqa: E402

AUJOURD_HUI = date(2026, 8, 22)

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
  date_limite: 2026-11-30

conditions:
  - id: edifice-anterieur-1800
    text: L'édifice doit être antérieur à 1800.
    kind: user_fact
    effect: gate
    fact: annee_construction
    predicate:
      lt: 1800
    quote: Les édifices antérieurs à 1800 sont éligibles.

tags:
  - test
"""

SOURCE = """# Aide à la restauration

Les édifices antérieurs à 1800 sont éligibles.
Le propriétaire doit s'engager à ouvrir l'édifice au public quinze jours par an.
Les travaux ne doivent pas avoir commencé à la date du dépôt du dossier.
Le dossier comprend un devis détaillé et une note de présentation.
"""

REGLEMENT_PDF = """RÈGLEMENT DE L'AIDE

Article 3 — Le maître d'ouvrage doit confier la maîtrise d'œuvre à un
architecte du patrimoine inscrit à l'ordre.
"""


def corpus_test(*, avec_pdf: bool = False, manquants: list[str] | None = None) -> Corpus:
    docs = [
        DocAudit(
            nom="https://ex.fr/aide",
            contenu=SOURCE,
            kind="text",
            provenance="frais",
            sha256="sha-frais",
            url="https://ex.fr/aide",
        )
    ]
    if avec_pdf:
        docs.append(
            DocAudit(
                nom="2026-07-01-reglement.pdf",
                contenu=REGLEMENT_PDF,
                kind="pdf",
                provenance="baseline",
                sha256="sha-pdf",
            )
        )
    return Corpus(docs=docs, manquants=list(manquants or []))


def ecrire_fiche(contenu: str = FICHE) -> tuple[Path, Aide, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name) / "aide-test.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin, load_aide(chemin), tmp


def sortie(**kwargs) -> str:
    return json.dumps({"slug": "aide-test", "resume": "relevé", **kwargs}, ensure_ascii=False)


def critere(**kwargs) -> dict:
    return {"quote": "Les édifices antérieurs à 1800 sont éligibles.", **kwargs}


# ---------------------------------------------------------------------------
# Étape 1 — sélection
# ---------------------------------------------------------------------------


class TestSelection(unittest.TestCase):
    """Une aide inchangée doit être sautée : c'est toute l'économie du dispositif."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        racine = Path(self.tmp.name)
        (racine / "aides").mkdir()
        (racine / "sources" / "aide-test").mkdir(parents=True)
        self.chemin = racine / "aides" / "aide-test.yaml"
        self.chemin.write_text(FICHE, encoding="utf-8")
        self.snapshot = racine / "sources" / "aide-test" / "2026-07-01.md"
        self.snapshot.write_text(SOURCE, encoding="utf-8")
        self.aide = load_aide(self.chemin)

        for module, nom, valeur in (
            (veille_audit, "AIDES_DIR", racine / "aides"),
            (veille_audit, "SOURCES_DIR", racine / "sources"),
        ):
            patcheur = mock.patch.object(module, nom, valeur)
            patcheur.start()
            self.addCleanup(patcheur.stop)

    def _manifeste_a_jour(self) -> dict:
        return {
            "aide-test": {
                "checked_at": "2026-08-06",
                "status": "ok",
                "audit": {
                    "date": "2026-08-20",
                    "sha_fiche": sha_fiche(self.chemin),
                    "sha_sources": sha_sources("aide-test"),
                    "portee": "complet",
                },
            }
        }

    def test_jamais_auditee_est_candidate(self):
        self.assertEqual(raison_audit(self.aide, {}), "jamais auditée")

    def test_shas_identiques_est_sautee(self):
        self.assertIsNone(raison_audit(self.aide, self._manifeste_a_jour()))

    def test_fiche_modifiee_est_candidate(self):
        manifest = self._manifeste_a_jour()
        self.chemin.write_text(FICHE + "\n# retouche à la main\n", encoding="utf-8")
        self.assertEqual(
            raison_audit(self.aide, manifest), "fiche modifiée depuis le dernier audit"
        )

    def test_snapshot_modifie_est_candidate(self):
        manifest = self._manifeste_a_jour()
        self.snapshot.write_text(SOURCE + "\nUne clause nouvelle.\n", encoding="utf-8")
        self.assertEqual(
            raison_audit(self.aide, manifest), "sources ré-archivées depuis le dernier audit"
        )

    def test_nouveau_snapshot_est_candidate(self):
        # L'ARRIVÉE d'un document compte autant que sa modification : c'est le
        # cas d'une source qui a bougé et vient d'être ré-archivée.
        manifest = self._manifeste_a_jour()
        (self.snapshot.parent / "2026-08-22-reglement.md").write_text("neuf", encoding="utf-8")
        self.assertEqual(
            raison_audit(self.aide, manifest), "sources ré-archivées depuis le dernier audit"
        )

    def test_force_court_circuite_la_regle(self):
        self.assertEqual(raison_audit(self.aide, self._manifeste_a_jour(), force=True), "--force")

    def test_ordre_des_plus_anciennement_auditees(self):
        aides = {"aide-test": self.aide}
        manifest = self._manifeste_a_jour()
        manifest["aide-test"]["audit"]["sha_fiche"] = "périmé"
        candidates = selectionner(aides, manifest)
        self.assertEqual([a.slug for a, _ in candidates], ["aide-test"])
        self.assertEqual(date_dernier_audit("aide-test", manifest), date(2026, 8, 20))
        self.assertEqual(date_dernier_audit("inconnue", manifest), date.min)

    def test_limit_tronque_apres_tri(self):
        self.assertEqual(selectionner({"aide-test": self.aide}, {}, limit=0), [])


class TestManifeste(unittest.TestCase):
    def test_fusion_sans_perte_des_cles_de_veille(self):
        manifest = {
            "aide-test": {"checked_at": "2026-08-06", "status": "ok", "urls": [{"url": "x"}]},
            "autre-aide": {"checked_at": "2026-08-01", "audit": {"date": "2026-01-01"}},
        }
        res = AuditResult(slug="aide-test", etat="a_jour", sha_fiche="f", sha_sources="s")
        fusion = update_manifest_audit(manifest, {"aide-test": res}, AUJOURD_HUI)

        self.assertEqual(fusion["aide-test"]["checked_at"], "2026-08-06")
        self.assertEqual(fusion["aide-test"]["status"], "ok")
        self.assertEqual(fusion["aide-test"]["urls"], [{"url": "x"}])
        self.assertEqual(fusion["aide-test"]["audit"]["sha_fiche"], "f")
        # Une aide hors du run garde son entrée d'audit intacte.
        self.assertEqual(fusion["autre-aide"]["audit"], {"date": "2026-01-01"})

    def test_echec_et_inauditable_ne_laissent_aucune_trace(self):
        # Sinon l'aide serait réputée auditée et sautée aux passages suivants,
        # alors qu'on ne sait toujours rien d'elle.
        resultats = {
            "a": AuditResult(slug="a", etat="echec"),
            "b": AuditResult(slug="b", etat="inauditable"),
            "c": AuditResult(slug="c", etat="escalade"),
        }
        fusion = update_manifest_audit({}, resultats, AUJOURD_HUI)
        self.assertNotIn("a", fusion)
        self.assertNotIn("b", fusion)
        # L'escalade, elle, est un verdict acquis : le rejouer coûterait un
        # appel pour la même réponse.
        self.assertIn("audit", fusion["c"])


class TestVeillePreserveLAudit(unittest.TestCase):
    """La veille reconstruit son entrée de zéro : elle doit reporter `audit`."""

    def test_un_run_de_veille_n_efface_pas_l_audit(self):
        from veille_aides import update_manifest
        from veille_analyze import AideAnalysis

        manifest = {"aide-test": {"audit": {"date": "2026-08-20", "portee": "complet"}}}
        fusion = update_manifest(
            manifest,
            {"aide-test": AideAnalysis(slug="aide-test", statut="OK")},
            {},
            AUJOURD_HUI,
        )
        self.assertEqual(fusion["aide-test"]["audit"]["date"], "2026-08-20")
        self.assertEqual(fusion["aide-test"]["checked_at"], AUJOURD_HUI.isoformat())


# ---------------------------------------------------------------------------
# Étape 2 — corpus
# ---------------------------------------------------------------------------


class TestCorpus(unittest.TestCase):
    def setUp(self):
        self.aide = load_aide_depuis(FICHE)

    def test_baseline_remplacee_par_le_frais_n_est_pas_soumise_deux_fois(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        (racine / "aide-test").mkdir(parents=True)
        snap = racine / "aide-test" / "2026-07-01-page.md"
        snap.write_text(
            "---\nurl: https://ex.fr/aide\nsha256: vieux\n---\nancienne page\n", encoding="utf-8"
        )
        with mock.patch.object(veille_audit, "SOURCES_DIR", racine):
            col = AideCollect(
                slug="aide-test",
                urls=[
                    MonitoredUrl(url="https://ex.fr/aide", role="officielle", baseline_path=snap)
                ],
                fetched={
                    "https://ex.fr/aide": FetchResult(
                        url="https://ex.fr/aide", status=200, body_md=SOURCE, sha256="frais"
                    )
                },
                baseline_docs=[("2026-07-01-page.md", "ancienne page", "text")],
            )
            corpus = construire_corpus(self.aide, col)
        self.assertEqual([d.provenance for d in corpus.docs], ["frais"])
        self.assertEqual(corpus.portee, "complet")

    def test_page_en_erreur_compensee_par_sa_baseline(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        (racine / "aide-test").mkdir(parents=True)
        snap = racine / "aide-test" / "2026-07-01-page.md"
        snap.write_text("---\nurl: https://ex.fr/aide\nsha256: archive\n---\n" + SOURCE, "utf-8")
        with mock.patch.object(veille_audit, "SOURCES_DIR", racine):
            col = AideCollect(
                slug="aide-test",
                urls=[
                    MonitoredUrl(url="https://ex.fr/aide", role="officielle", baseline_path=snap)
                ],
                fetched={"https://ex.fr/aide": FetchResult(url="https://ex.fr/aide", status=503)},
                baseline_docs=[("2026-07-01-page.md", SOURCE, "text")],
            )
            corpus = construire_corpus(self.aide, col)
        # C'est exactement le cas que la lecture des baselines couvre : la page
        # est morte aujourd'hui, l'archive suffit à juger l'exhaustivité.
        self.assertEqual([d.provenance for d in corpus.docs], ["baseline"])
        self.assertEqual(corpus.docs[0].sha256, "archive")
        self.assertEqual(corpus.portee, "complet")

    def test_pdf_illisible_degrade_la_portee(self):
        col = AideCollect(
            slug="aide-test",
            urls=[],
            baseline_docs=[("2026-07-01-page.md", SOURCE, "text")],
            pdf_illisibles=["2026-07-01-reglement.pdf (0 car. extraits)"],
        )
        with mock.patch.object(veille_audit, "SOURCES_DIR", Path("/inexistant")):
            corpus = construire_corpus(self.aide, col)
        self.assertEqual(corpus.portee, "partiel")
        self.assertTrue(any("PDF illisible" in m for m in corpus.manquants))

    def test_corpus_vide(self):
        col = AideCollect(slug="aide-test", urls=[])
        with mock.patch.object(veille_audit, "SOURCES_DIR", Path("/inexistant")):
            corpus = construire_corpus(self.aide, col)
        self.assertTrue(corpus.vide)
        self.assertEqual(corpus.portee, "partiel")

    def test_entree_manifeste_distingue_frais_et_baseline(self):
        corpus = corpus_test(avec_pdf=True)
        entrees = [d.entree_manifeste() for d in corpus.docs]
        self.assertEqual(entrees[0]["url"], "https://ex.fr/aide")
        self.assertEqual(entrees[0]["etat"], "frais")
        self.assertEqual(entrees[1]["nom"], "2026-07-01-reglement.pdf")
        self.assertEqual(entrees[1]["etat"], "baseline")


def load_aide_depuis(contenu: str) -> Aide:
    chemin, aide, tmp = ecrire_fiche(contenu)
    tmp.cleanup()
    return aide


# ---------------------------------------------------------------------------
# Étapes 3-4 — parse, schéma, référentiel, citations, doublons
# ---------------------------------------------------------------------------


class TestParseEtSchema(unittest.TestCase):
    def test_json_entoure_de_fences(self):
        aide = load_aide_depuis(FICHE)
        # Un critère `conforme` et non `criteres=[]` : un relevé vide est
        # désormais refusé pour lui-même, ce test ne vise que les fences.
        brut = (
            "```json\n"
            + sortie(criteres=[critere(verdict="conforme", cond_id="edifice-anterieur-1800")])
            + "\n```"
        )
        out, erreurs, etape, _ = valider(brut, aide, corpus_test())
        self.assertIsNotNone(out)
        self.assertEqual((erreurs, etape), ([], None))

    def test_cle_inconnue_rejetee(self):
        aide = load_aide_depuis(FICHE)
        out, erreurs, etape, _ = valider(sortie(criteres=[], inattendu=1), aide, corpus_test())
        self.assertIsNone(out)
        self.assertEqual(etape, "schema")
        self.assertTrue(any("inattendu" in e for e in erreurs))

    def test_json_invalide(self):
        aide = load_aide_depuis(FICHE)
        out, _erreurs, etape, _ = valider("pas du json", aide, corpus_test())
        self.assertIsNone(out)
        self.assertEqual(etape, "json")


class TestReferentiel(unittest.TestCase):
    def setUp(self):
        self.aide = load_aide_depuis(FICHE)

    def _erreurs(self, criteres: list[dict], slug: str | None = "aide-test") -> list[str]:
        out = AuditLLMOutput.model_validate({"slug": slug, "criteres": criteres})
        return check_referentiel_audit(out, self.aide)

    def test_slug_etranger_rejete(self):
        erreurs = self._erreurs([], slug="une-autre-aide")
        self.assertTrue(any("≠ aide auditée" in e for e in erreurs))

    def test_cond_id_inconnu_rejete(self):
        erreurs = self._erreurs([critere(cond_id="fantome", verdict="conforme")])
        self.assertTrue(any("cond_id « fantome » inconnu" in e for e in erreurs))

    def test_absent_sans_text_rejete(self):
        erreurs = self._erreurs([critere(verdict="absent", id="ouverture-public")])
        self.assertTrue(any("exige un `id` inédit ET un `text`" in e for e in erreurs))

    def test_absent_sur_id_deja_pris_rejete(self):
        erreurs = self._erreurs(
            [critere(verdict="absent", id="edifice-anterieur-1800", text="doublon")]
        )
        self.assertTrue(any("déjà utilisé" in e for e in erreurs))

    def test_absent_en_double_rejete(self):
        erreurs = self._erreurs(
            [
                critere(verdict="absent", id="ouverture-public", text="a"),
                critere(verdict="absent", id="ouverture-public", text="b"),
            ]
        )
        self.assertTrue(any("proposé deux fois" in e for e in erreurs))

    def test_absent_avec_cond_id_est_contradictoire(self):
        erreurs = self._erreurs(
            [
                critere(
                    verdict="absent",
                    id="ouverture-public",
                    text="a",
                    cond_id="edifice-anterieur-1800",
                )
            ]
        )
        self.assertTrue(any("contradictoire" in e for e in erreurs))

    def test_divergent_sans_commentaire_rejete(self):
        erreurs = self._erreurs([critere(verdict="divergent", cond_id="edifice-anterieur-1800")])
        self.assertTrue(any("exige un `commentaire`" in e for e in erreurs))

    def test_divergent_sans_cond_id_rejete(self):
        erreurs = self._erreurs([critere(verdict="divergent", commentaire="ça diverge")])
        self.assertTrue(any("exige le `cond_id`" in e for e in erreurs))

    def test_conforme_sans_cond_id_rejete(self):
        erreurs = self._erreurs([critere(verdict="conforme")])
        self.assertTrue(any("`conforme` exige le `cond_id`" in e for e in erreurs))

    def test_releve_valide_ne_produit_aucune_erreur(self):
        self.assertEqual(
            self._erreurs([critere(verdict="conforme", cond_id="edifice-anterieur-1800")]), []
        )


class TestCitations(unittest.TestCase):
    def setUp(self):
        self.aide = load_aide_depuis(FICHE)

    def test_citation_inventee_rejette_la_reponse(self):
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    {
                        "quote": "Le monument doit être classé au patrimoine mondial.",
                        "verdict": "absent",
                        "id": "unesco",
                        "text": "Inventée.",
                    }
                ]
            }
        )
        erreurs, ecartes = check_quotes_audit(out, corpus_test().documents())
        self.assertTrue(any("introuvable" in e for e in erreurs))
        self.assertEqual(ecartes, [], "un `absent` mal cité rejette, il n'est pas écarté")

    def test_citation_d_un_pdf_de_baseline_est_acceptee(self):
        # Le point 2 des décisions de conception : les ~800 quotes justifiées
        # par des PDF non re-téléchargeables entrent dans le périmètre.
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    {
                        "quote": "confier la maîtrise d'œuvre à un architecte du patrimoine",
                        "verdict": "absent",
                        "id": "architecte-patrimoine",
                        "text": "La maîtrise d'œuvre revient à un architecte du patrimoine.",
                    }
                ]
            }
        )
        self.assertEqual(check_quotes_audit(out, corpus_test(avec_pdf=True).documents()), ([], []))

    def test_citation_d_un_conforme_fautive_ecarte_le_critere_sans_tout_rejeter(self):
        # Le critère est jeté de toute façon : détruire l'audit entier pour lui
        # serait disproportionné. Mesuré au pilote du 2026-08-24, où UNE ligne
        # de tableau mal aplatie a emporté 21 critères dont 4 exploitables.
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    {
                        "quote": "Une phrase qui n'est nulle part dans la source.",
                        "verdict": "conforme",
                        "cond_id": "edifice-anterieur-1800",
                    }
                ]
            }
        )
        erreurs, ecartes = check_quotes_audit(out, corpus_test().documents())
        self.assertEqual(erreurs, [], "un `conforme` mal cité ne doit rien rejeter")
        self.assertEqual(ecartes, [0])

    def test_corpus_vide_refuse_toute_citation(self):
        out = AuditLLMOutput.model_validate({"criteres": [{"quote": "x", "verdict": "absent"}]})
        self.assertTrue(check_quotes_audit(out, [])[0])


class TestToleranceConformes(unittest.TestCase):
    """L'assouplissement ne doit pas devenir une porte ouverte."""

    def setUp(self):
        self.aide = load_aide_depuis(FICHE)

    def _releve(self, n_bons: int, n_mauvais: int) -> str:
        bons = [
            {
                "quote": "Les édifices antérieurs à 1800 sont éligibles.",
                "verdict": "conforme",
                "cond_id": "edifice-anterieur-1800",
            }
        ] * n_bons
        mauvais = [
            {
                "quote": f"Citation inventée numéro {i} qui n'est nulle part dans le corpus.",
                "verdict": "conforme",
                "cond_id": "edifice-anterieur-1800",
            }
            for i in range(n_mauvais)
        ]
        return sortie(criteres=bons + mauvais)

    def test_quelques_citations_fautives_sont_ecartees_sans_rejet(self):
        out, erreurs, etape, ecartes = valider(self._releve(8, 2), self.aide, corpus_test())
        self.assertEqual((erreurs, etape), ([], None))
        self.assertEqual(ecartes, 2)
        assert out is not None
        # Les fautifs sont RETIRÉS de la sortie, pas seulement comptés.
        self.assertEqual(len(out.criteres), 8)

    def test_un_releve_majoritairement_infonde_est_rejete(self):
        _out, erreurs, etape, ecartes = valider(self._releve(2, 6), self.aide, corpus_test())
        self.assertEqual(etape, "quote")
        self.assertEqual(ecartes, 6)
        self.assertTrue(any("relevé non fiable" in e for e in erreurs))

    def test_le_retrait_ne_decale_pas_les_criteres_conserves(self):
        # Retrait par index décroissant : l'inverse supprimerait les mauvais
        # éléments et emporterait des bons avec eux.
        criteres = [
            {"quote": "introuvable A", "verdict": "conforme", "cond_id": "edifice-anterieur-1800"},
            {
                "quote": "ouvrir l'édifice au public quinze jours par an",
                "verdict": "conforme",
                "cond_id": "edifice-anterieur-1800",
            },
            {"quote": "introuvable B", "verdict": "conforme", "cond_id": "edifice-anterieur-1800"},
            {
                "quote": "Les travaux ne doivent pas avoir commencé",
                "verdict": "conforme",
                "cond_id": "edifice-anterieur-1800",
            },
        ]
        out, erreurs, _etape, ecartes = valider(sortie(criteres=criteres), self.aide, corpus_test())
        self.assertEqual((erreurs, ecartes), ([], 2))
        assert out is not None
        self.assertEqual(
            [c.quote for c in out.criteres],
            [
                "ouvrir l'édifice au public quinze jours par an",
                "Les travaux ne doivent pas avoir commencé",
            ],
        )


class TestAntiDoublon(unittest.TestCase):
    def setUp(self):
        self.aide = load_aide_depuis(FICHE)

    def test_absent_citant_une_condition_existante_est_rejete(self):
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    {
                        "quote": "Les édifices antérieurs à 1800 sont éligibles.",
                        "verdict": "absent",
                        "id": "anciennete-edifice",
                        "text": "L'édifice doit dater d'avant 1800.",
                    }
                ]
            }
        )
        erreurs = check_doublons(out, self.aide)
        self.assertTrue(any("rattachement manqué" in e for e in erreurs))
        self.assertTrue(any("edifice-anterieur-1800" in e for e in erreurs))

    def test_absent_sur_une_citation_inedite_passe(self):
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    {
                        "quote": "ouvrir l'édifice au public quinze jours par an",
                        "verdict": "absent",
                        "id": "ouverture-public",
                        "text": "L'édifice est ouvert au public quinze jours par an.",
                    }
                ]
            }
        )
        self.assertEqual(check_doublons(out, self.aide), [])

    def test_citation_courte_ne_declenche_pas_l_inclusion(self):
        # Une citation de dix caractères est « contenue » dans à peu près
        # n'importe quelle autre : l'inclusion n'y prouverait rien.
        out = AuditLLMOutput.model_validate(
            {"criteres": [{"quote": "à 1800", "verdict": "absent", "id": "x", "text": "t"}]}
        )
        self.assertEqual(check_doublons(out, self.aide), [])


# ---------------------------------------------------------------------------
# Étape 5 — application
# ---------------------------------------------------------------------------


SPEC = ModelSpec(
    alias="faux",
    provider="openai_compat",
    model_id="faux",
    env_key="FAUX_KEY",
    prix_in=0.0,
    prix_out=0.0,
)


class TestApplication(unittest.TestCase):
    """Ce qui est écrit, et surtout ce qui ne l'est pas."""

    def _auditer(self, reponse: str, *, dry_run: bool = False, fiche: str = FICHE):
        chemin, aide, tmp = ecrire_fiche(fiche)
        appels: list[str] = []

        def faux_call(spec, system, user, **kwargs):
            appels.append(user)
            return LLMCall(text=reponse, model="faux", cost_usd=0.0)

        with mock.patch.object(veille_audit, "call", faux_call):
            res = auditer(
                aide,
                AideCollect(slug=aide.slug),
                SPEC,
                aujourd_hui=AUJOURD_HUI,
                dry_run=dry_run,
                chemin=chemin,
                corpus=corpus_test(avec_pdf=True),
            )
        return res, chemin, tmp, appels

    def test_deux_absents_deviennent_deux_conditions_untyped(self):
        reponse = sortie(
            criteres=[
                critere(verdict="conforme", cond_id="edifice-anterieur-1800"),
                {
                    "quote": "ouvrir l'édifice au public quinze jours par an",
                    "verdict": "absent",
                    "id": "ouverture-public",
                    "text": "L'édifice est ouvert au public quinze jours par an.",
                },
                {
                    "quote": "Les travaux ne doivent pas avoir commencé",
                    "verdict": "absent",
                    "id": "travaux-non-commences",
                    "text": "Les travaux ne doivent pas avoir commencé au dépôt.",
                },
            ]
        )
        res, chemin, tmp, _ = self._auditer(reponse)
        with tmp:
            self.assertEqual(res.etat, "ajouts", res.erreurs)
            self.assertEqual(res.ajouts, ["ouverture-public", "travaux-non-commences"])
            texte = chemin.read_text(encoding="utf-8")
            self.assertIn("id: ouverture-public", texte)
            self.assertIn("kind: untyped", texte)
            # La note doit dire d'où sort la condition, et l'origine est bien
            # « audit » : elle ne vient PAS d'un changement de règlement.
            self.assertIn(f"ajoutée par audit du {AUJOURD_HUI.isoformat()}, à typer", texte)
            self.assertNotIn("ajoutée par veille", texte)
            # Le fichier reste une fiche valide, et le reste est intact.
            Aide.model_validate(__import__("yaml").safe_load(texte))
            self.assertIn("id: edifice-anterieur-1800", texte)
            self.assertEqual(res.criteres_releves, 3)

    def test_dry_run_n_ecrit_rien(self):
        reponse = sortie(
            criteres=[
                {
                    "quote": "ouvrir l'édifice au public quinze jours par an",
                    "verdict": "absent",
                    "id": "ouverture-public",
                    "text": "L'édifice est ouvert au public quinze jours par an.",
                }
            ]
        )
        res, chemin, tmp, _ = self._auditer(reponse, dry_run=True)
        with tmp:
            self.assertEqual(res.etat, "ajouts")
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_quatre_absents_escaladent_sans_toucher_au_fichier(self):
        criteres = [
            {
                "quote": q,
                "verdict": "absent",
                "id": f"critere-{i}",
                "text": f"Condition {i}.",
            }
            for i, q in enumerate(
                [
                    "ouvrir l'édifice au public quinze jours par an",
                    "Les travaux ne doivent pas avoir commencé",
                    "un devis détaillé et une note de présentation",
                    "confier la maîtrise d'œuvre à un architecte du patrimoine",
                ]
            )
        ]
        res, chemin, tmp, _ = self._auditer(sortie(criteres=criteres))
        with tmp:
            self.assertEqual(res.etat, "escalade")
            self.assertIn(f"seuil {MAX_AJOUTS_CONDITIONS}", res.raison)
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_fiche_incomplete_escalade(self):
        reponse = sortie(
            fiche_incomplete=True,
            raison_fiche_incomplete="la page décrit un dispositif différent",
            criteres=[],
        )
        res, chemin, tmp, _ = self._auditer(reponse)
        with tmp:
            self.assertEqual(res.etat, "escalade")
            self.assertIn("dispositif différent", res.raison)
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_fiche_incomplete_ne_fait_pas_fuiter_de_divergences_non_verifiees(self):
        # Une réponse `fiche_incomplete` court-circuite la validation : ses
        # critères n'ont PAS vu le contrôle des citations. Les verser au
        # rapport y ferait entrer des divergences invérifiées.
        reponse = sortie(
            fiche_incomplete=True,
            raison_fiche_incomplete="dispositif différent",
            criteres=[
                {
                    "quote": "Une citation que le corpus ne contient nulle part.",
                    "verdict": "divergent",
                    "cond_id": "edifice-anterieur-1800",
                    "commentaire": "invérifié",
                }
            ],
        )
        res, chemin, tmp, _ = self._auditer(reponse)
        with tmp:
            self.assertEqual(res.etat, "escalade")
            self.assertEqual(res.divergences, [])
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_divergence_ne_touche_jamais_le_yaml(self):
        reponse = sortie(
            criteres=[
                {
                    "quote": "Les édifices antérieurs à 1800 sont éligibles.",
                    "verdict": "divergent",
                    "cond_id": "edifice-anterieur-1800",
                    "commentaire": "la fiche dit « avant 1800 », la source « antérieurs à 1800 »",
                }
            ]
        )
        res, chemin, tmp, _ = self._auditer(reponse)
        with tmp:
            self.assertEqual(res.etat, "divergences")
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)
            self.assertEqual(len(res.divergences), 1)
            cond_id, texte_fiche, quote, commentaire = res.divergences[0]
            self.assertEqual(cond_id, "edifice-anterieur-1800")
            self.assertEqual(texte_fiche, "L'édifice doit être antérieur à 1800.")
            self.assertIn("antérieurs à 1800", commentaire)

    def test_releve_tout_conforme_laisse_la_fiche_a_jour(self):
        reponse = sortie(criteres=[critere(verdict="conforme", cond_id="edifice-anterieur-1800")])
        res, chemin, tmp, _ = self._auditer(reponse)
        with tmp:
            self.assertEqual(res.etat, "a_jour")
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_une_seule_relance_puis_echec(self):
        mauvaise = sortie(criteres=[critere(verdict="conforme", cond_id="fantome")])
        res, chemin, tmp, appels = self._auditer(mauvaise)
        with tmp:
            self.assertEqual(res.etat, "echec")
            self.assertEqual(res.etape_echec, "referentiel")
            self.assertEqual(len(appels), 2, "une seule nouvelle tentative")
            self.assertIn("REJETÉE", appels[1])
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)
            # La réponse rejetée est conservée : sans elle, rien n'est rejouable.
            self.assertIn("fantome", res.reponse_rejetee)

    def test_un_echec_conserve_le_compte_de_criteres_releves(self):
        # « 0 crit. » sur un échec masquait qu'un relevé de vingt et un critères
        # avait bien eu lieu — or c'est ce compte qui permet de juger l'échec.
        mauvaise = sortie(
            criteres=[
                critere(verdict="conforme", cond_id="edifice-anterieur-1800"),
                {
                    "quote": "Une citation absente du corpus.",
                    "verdict": "absent",
                    "id": "inventee",
                    "text": "Inventée.",
                },
            ]
        )
        res, chemin, tmp, _ = self._auditer(mauvaise)
        with tmp:
            self.assertEqual(res.etat, "echec")
            self.assertEqual(res.etape_echec, "quote")
            self.assertEqual(res.criteres_releves, 2)
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHE)

    def test_corpus_vide_est_inauditable_sans_appel(self):
        chemin, aide, tmp = ecrire_fiche()
        appels: list[str] = []

        def faux_call(*a, **k):
            appels.append("appel")
            return LLMCall(text="{}", model="faux")

        with tmp, mock.patch.object(veille_audit, "call", faux_call):
            res = auditer(
                aide,
                AideCollect(slug=aide.slug),
                SPEC,
                aujourd_hui=AUJOURD_HUI,
                chemin=chemin,
                corpus=Corpus(),
            )
            self.assertEqual(res.etat, "inauditable")
            self.assertEqual(appels, [])
            self.assertFalse(res.trace_manifeste)

    def test_portee_partielle_remonte_dans_le_resultat(self):
        chemin, aide, tmp = ecrire_fiche()
        reponse = sortie(criteres=[critere(verdict="conforme", cond_id="edifice-anterieur-1800")])
        with (
            tmp,
            mock.patch.object(
                veille_audit, "call", lambda *a, **k: LLMCall(text=reponse, model="faux")
            ),
        ):
            res = auditer(
                aide,
                AideCollect(slug=aide.slug),
                SPEC,
                aujourd_hui=AUJOURD_HUI,
                chemin=chemin,
                corpus=corpus_test(manquants=["PDF illisible : reglement.pdf"]),
            )
        self.assertEqual(res.portee, "partiel")
        self.assertEqual(res.manquants, ["PDF illisible : reglement.pdf"])


class TestSortieAjouts(unittest.TestCase):
    def test_seuls_les_absents_sont_traduits(self):
        aide = load_aide_depuis(FICHE)
        out = AuditLLMOutput.model_validate(
            {
                "criteres": [
                    critere(verdict="conforme", cond_id="edifice-anterieur-1800"),
                    {
                        "quote": "ouvrir l'édifice au public",
                        "verdict": "absent",
                        "id": "ouverture-public",
                        "text": "Ouverture au public.",
                        "kind": "info",
                    },
                    {
                        "quote": "Les édifices antérieurs à 1800 sont éligibles.",
                        "verdict": "divergent",
                        "cond_id": "edifice-anterieur-1800",
                        "commentaire": "diverge",
                    },
                ]
            }
        )
        sortie_veille = sortie_ajouts(out, aide)
        self.assertEqual(len(sortie_veille.conditions), 1)
        chg = sortie_veille.conditions[0]
        self.assertEqual(chg.op, "add")
        assert chg.condition is not None
        self.assertEqual(chg.condition.id, "ouverture-public")
        self.assertEqual(chg.condition.kind, "info")


# ---------------------------------------------------------------------------
# Test canonique — un relevé sans manque ne doit rien changer
# ---------------------------------------------------------------------------


class TestSortieConformeDiffVide(unittest.TestCase):
    """Décliné du test canonique de la veille.

    Une sortie ne contenant que des `conforme` ne doit RIEN changer — pas un
    espace, pas un repli de ligne — sur aucune fiche du dépôt. Le `git diff` EST
    la revue humaine : un éditeur qui reformate noie la vraie modification et
    supprime le seul contrôle qui empêche une hallucination d'entrer dans les
    données.
    """

    def test_toutes_les_fiches_du_depot_restent_intactes(self):
        chemins = sorted(AIDES_DIR.glob("*.yaml"))
        self.assertGreater(len(chemins), 100, "le dépôt doit contenir les fiches réelles")
        modifiees, etats = [], []
        for chemin in chemins:
            aide = load_aide(chemin)
            avant = chemin.read_text(encoding="utf-8")
            reponse = json.dumps(
                {
                    "slug": aide.slug,
                    "resume": "fiche conforme à sa source",
                    "criteres": [
                        {
                            "quote": "Les édifices antérieurs à 1800 sont éligibles.",
                            "verdict": "conforme",
                            "cond_id": aide.conditions[0].id,
                        }
                    ]
                    if aide.conditions
                    else [],
                },
                ensure_ascii=False,
            )
            with mock.patch.object(
                veille_audit, "call", lambda *a, _r=reponse, **k: LLMCall(text=_r, model="faux")
            ):
                res = auditer(
                    aide,
                    AideCollect(slug=aide.slug),
                    SPEC,
                    aujourd_hui=AUJOURD_HUI,
                    chemin=chemin,
                    corpus=corpus_test(),
                )
            if res.etat != "a_jour":
                etats.append(f"{aide.slug}: {res.etat} — {res.raison}")
            if chemin.read_text(encoding="utf-8") != avant:
                modifiees.append(aide.slug)
        self.assertEqual(modifiees, [], f"fiches modifiées par un relevé conforme : {modifiees}")
        self.assertEqual(etats, [], f"états inattendus : {etats[:5]}")


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


class TestRapport(unittest.TestCase):
    def _resultats(self) -> dict[str, AuditResult]:
        return {
            "avec-ajouts": AuditResult(
                slug="avec-ajouts",
                etat="ajouts",
                ajouts=["ouverture-public"],
                resume="il manquait l'ouverture au public",
            ),
            "divergente": AuditResult(
                slug="divergente",
                etat="divergences",
                divergences=[("taux", "30 %", "40 % du montant", "le taux a changé")],
            ),
            "escaladee": AuditResult(
                slug="escaladee", etat="escalade", raison="8 conditions manquantes"
            ),
            "partielle": AuditResult(
                slug="partielle",
                etat="a_jour",
                portee="partiel",
                manquants=["PDF illisible : reglement.pdf"],
            ),
            "cassee": AuditResult(
                slug="cassee", etat="echec", etape_echec="quote", raison="citation introuvable"
            ),
        }

    def test_le_rapport_couvre_les_cinq_sections(self):
        aides = {s: None for s in self._resultats()}
        rapport = veille_audit.build_report(
            self._resultats(),
            [],
            total=len(aides),
            today=AUJOURD_HUI,
            duree_s=60.0,
            mode="complet",
        )
        for attendu in (
            "## Conditions ajoutées",
            "## Divergences à arbitrer",
            "## Escalades",
            "## Portées partielles",
            "## Échecs de validation",
            "git diff -- data/aides",
            "ingerer.py --slug escaladee",
            "le taux a changé",
        ):
            self.assertIn(attendu, rapport, attendu)

    def test_le_releve_dit_combien_de_criteres_ont_ete_lus(self):
        # C'est la seule mesure qui dise si un « rien à signaler » vaut quelque
        # chose : sans elle, un survol à 2 critères se lit comme un audit.
        res = AuditResult(slug="a", etat="a_jour", criteres_releves=17, portee="complet")
        rapport = veille_audit.build_report(
            {"a": res}, [], total=1, today=AUJOURD_HUI, duree_s=1.0, mode="complet"
        )
        self.assertIn("## Relevé", rapport)
        self.assertIn("| a | `a_jour` | 17 | — | complet |", rapport)

    def test_le_releve_signale_les_citations_ecartees(self):
        res = AuditResult(
            slug="a", etat="a_jour", criteres_releves=17, conformes_ecartes=2, portee="complet"
        )
        rapport = veille_audit.build_report(
            {"a": res}, [], total=1, today=AUJOURD_HUI, duree_s=1.0, mode="complet"
        )
        self.assertIn("| a | `a_jour` | 17 | 2 | complet |", rapport)
        self.assertIn("Citations écartées", rapport)

    def test_le_prompt_porte_le_perimetre_de_la_fiche(self):
        # Sans la `description`, le modèle rapporte comme « manquants » les
        # critères des volets que la fiche ne traite pas — mesuré au pilote du
        # 2026-08-24 sur `29-projets-culturels-diffusion`.
        aide = load_aide_depuis(FICHE)
        prompt = veille_audit.build_prompt_audit(aide, corpus_test(), aujourd_hui=AUJOURD_HUI)
        self.assertIn(aide.description[:60], prompt)
        self.assertIn("délimite CE QUE COUVRE la fiche", prompt)

    def test_le_prompt_porte_les_pieces_deja_exigees(self):
        # Une exigence rangée dans `documents_requis` est couverte : sans la
        # voir, le modèle la redéclare condition manquante — mesuré sur
        # `77-association-patrimoine` (Contrat d'Engagement Républicain).
        fiche = FICHE.replace(
            "\ntags:\n",
            "\ndocuments_requis:\n  - nom: Attestation de souscription au Contrat d'Engagement Républicain\n\ntags:\n",
        )
        aide = load_aide_depuis(fiche)
        prompt = veille_audit.build_prompt_audit(aide, corpus_test(), aujourd_hui=AUJOURD_HUI)
        self.assertIn("Contrat d'Engagement Républicain", prompt)
        self.assertIn("ne la propose pas comme condition manquante", prompt.replace("\n", " "))

    def test_le_system_cadre_la_granularite(self):
        # Une condition qui résume une liste couvre chacune de ses puces : c'est
        # le principal pourvoyeur de faux « absent ».
        self.assertIn("RÈGLE DE GRANULARITÉ", veille_audit.SYSTEM_AUDIT)
        self.assertIn("RÉSUME une liste couvre CHACUN", veille_audit.SYSTEM_AUDIT)

    def test_dry_run_annonce_qu_il_n_a_rien_ecrit(self):
        rapport = veille_audit.build_report(
            self._resultats(), [], total=5, today=AUJOURD_HUI, duree_s=1.0, mode="dry-run"
        )
        self.assertIn("À blanc", rapport)
        self.assertIn("manifeste n'a PAS été mis à jour", rapport)

    def test_un_pipe_du_modele_ne_casse_pas_le_tableau(self):
        res = AuditResult(slug="a", etat="ajouts", ajouts=["x"], resume="a | b\nc")
        rapport = veille_audit.build_report(
            {"a": res}, [], total=1, today=AUJOURD_HUI, duree_s=1.0, mode="complet"
        )
        # La section « Relevé » émet aussi une ligne « | a | » : on vise celle du
        # tableau des ajouts, la seule qui porte du texte libre du modèle.
        ajouts = rapport.split("## Conditions ajoutées", 1)[1]
        ligne = next(ligne for ligne in ajouts.splitlines() if ligne.startswith("| a |"))
        # Le `|` du modèle est échappé, pas supprimé : il reste lisible sans
        # ouvrir une sixième colonne, et le saut de ligne est aplati.
        self.assertIn(r"a \| b c", ligne)
        self.assertEqual(ligne.replace(r"\|", "").count("|"), 5, ligne)


if __name__ == "__main__":
    unittest.main()


class TestCorpusUneVersionParUrl(unittest.TestCase):
    """Deux snapshots d'une même page ne doivent jamais être soumis ensemble."""

    URL = "https://ex.fr/aide"

    def _col(self, *, frais: bool) -> AideCollect:
        recent = Path("/inexistant/aide-test/2026-08-24-page.md")
        fetched = {}
        if frais:
            fetched[self.URL] = FetchResult(url=self.URL, status=200, body_md=SOURCE, sha256="f")
        return AideCollect(
            slug="aide-test",
            urls=[MonitoredUrl(url=self.URL, role="officielle", baseline_path=recent)],
            fetched=fetched,
            baseline_docs=[
                ("2026-07-01-page.md", "ancienne version", "text"),
                ("2026-08-24-page.md", SOURCE, "text"),
                ("2026-07-01-reglement.pdf", REGLEMENT_PDF, "pdf"),
            ],
            baseline_urls={
                "2026-07-01-page.md": self.URL,
                "2026-08-24-page.md": self.URL,
            },
        )

    def test_sans_frais_seul_le_snapshot_le_plus_recent_est_soumis(self):
        aide = load_aide_depuis(FICHE)
        with mock.patch.object(veille_audit, "SOURCES_DIR", Path("/inexistant")):
            corpus = construire_corpus(aide, self._col(frais=False))
        self.assertEqual(
            [d.nom for d in corpus.docs], ["2026-08-24-page.md", "2026-07-01-reglement.pdf"]
        )

    def test_avec_frais_toutes_les_versions_archivees_de_la_page_sont_ecartees(self):
        # Régression vécue sur 35-faat : le frais ET le snapshot du 29 juillet de
        # la même URL partaient au modèle ensemble.
        aide = load_aide_depuis(FICHE)
        with mock.patch.object(veille_audit, "SOURCES_DIR", Path("/inexistant")):
            corpus = construire_corpus(aide, self._col(frais=True))
        self.assertEqual([d.nom for d in corpus.docs], [self.URL, "2026-07-01-reglement.pdf"])
        self.assertEqual(corpus.docs[0].provenance, "frais")


class TestTypageRafraichitLEmpreinte(unittest.TestCase):
    """Après `--typer`, l'empreinte inscrite au manifeste est celle de la fiche typée.

    Sinon chaque aide typée ressort « fiche modifiée » au run suivant et repaie
    un audit pour un changement qu'on a fait nous-mêmes.
    """

    def test_sha_fiche_recalcule_apres_typage(self):
        import argparse

        from veille_typage import TypageResult

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        chemin = racine / "aide-test.yaml"
        chemin.write_text(FICHE, encoding="utf-8")
        res = AuditResult(slug="aide-test", etat="ajouts", sha_fiche=sha_fiche(chemin))

        def faux_typer_toutes(aides, spec, **kwargs):
            chemin.write_text(FICHE + "\n# typée\n", encoding="utf-8")
            return {"aide-test": TypageResult(slug="aide-test", etat="type")}

        args = argparse.Namespace(
            typer=True, report_only=False, dry_run=False, model="ds-flash", max_llm=20
        )
        with (
            mock.patch.object(veille_audit, "AIDES_DIR", racine),
            mock.patch.object(veille_audit, "typer_toutes", faux_typer_toutes),
        ):
            veille_audit._typer_ajouts(args, {"aide-test": res}, AUJOURD_HUI, lambda *_: None)
        self.assertEqual(res.sha_fiche, sha_fiche(chemin))


class TestReleveVide(unittest.TestCase):
    """Un relevé vide face à une fiche citée dans le corpus est un survol, pas un « à jour »."""

    def test_releve_vide_rejete_et_rattrapable(self):
        aide = load_aide_depuis(FICHE)
        out, erreurs, etape, _ = valider(sortie(criteres=[]), aide, corpus_test())
        self.assertIsNotNone(out)
        self.assertEqual(etape, "referentiel")
        self.assertTrue(any("relevé vide" in e for e in erreurs))

    def test_releve_vide_tolere_si_rien_de_la_fiche_n_est_dans_le_corpus(self):
        # Rien ne prouve que la lecture était possible : on ne peut pas exiger
        # un `conforme` sur une citation que le corpus ne contient pas.
        aide = load_aide_depuis(FICHE)
        etranger = Corpus(
            docs=[
                DocAudit(
                    nom="x", contenu="Un tout autre texte.", kind="text", provenance="baseline"
                )
            ]
        )
        out, erreurs, etape, _ = valider(sortie(criteres=[]), aide, etranger)
        self.assertEqual((erreurs, etape), ([], None))

    def test_un_releve_non_vide_passe(self):
        aide = load_aide_depuis(FICHE)
        out, erreurs, _, _ = valider(
            sortie(criteres=[critere(verdict="conforme", cond_id="edifice-anterieur-1800")]),
            aide,
            corpus_test(),
        )
        self.assertEqual(erreurs, [])

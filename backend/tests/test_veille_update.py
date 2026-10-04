"""Tests de l'orchestration de l'étage C (scripts/veille_update.py et le CLI).

Ce qui est vérifié ici n'est pas la qualité du modèle — le benchmark s'en
charge — mais la conduite autour de lui : combien de fois on le rappelle, ce
qu'on écrit, et surtout ce qu'on N'écrit PAS. Le modèle est donc remplacé par
une réponse fixée : le test doit rester vrai quel que soit le fournisseur, et
ne jamais toucher le réseau.

Run from backend/:  uv run pytest tests/test_veille_update.py
"""

import argparse
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import snapshot_source  # noqa: E402
import veille_apply  # noqa: E402
import veille_update  # noqa: E402
from veille_aides import build_report, run_stage_c, update_manifest  # noqa: E402
from veille_analyze import AideAnalysis, UrlVerdict  # noqa: E402
from veille_collect import AideCollect, FetchResult, MonitoredUrl  # noqa: E402
from veille_llm import (  # noqa: E402
    FOURNISSEURS,
    MODELE_DEFAUT,
    REGISTRE,
    LLMCall,
    ModelSpec,
    resoudre_modele,
)
from veille_text import normalized_diff  # noqa: E402
from veille_update import MajResult, mettre_a_jour, prompt_correction  # noqa: E402

from aides_schema import Aide, load_aide  # noqa: E402

AUJOURD_HUI = date(2026, 8, 7)
URL = "https://ex.fr/aide"

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
  - id: montant-moyen
    text: Les dossiers sélectionnés reçoivent 5 000 € en moyenne.
    kind: info
    effect: info
    quote: une aide de 5 000 € en moyenne.

tags:
  - test
"""

BASELINE = """# Aide à la restauration

Les dossiers sélectionnés reçoivent une aide de 5 000 € en moyenne.
Le taux d'intervention est de 30 % du montant des travaux.
"""

FRAIS = """# Aide à la restauration

Les dossiers sélectionnés reçoivent une aide de 5 000 € en moyenne.
Le taux d'intervention est porté à 40 % du montant des travaux.
"""

SPEC = ModelSpec(
    alias="faux",
    provider="openai_compat",
    model_id="faux-1",
    env_key="PATH",  # toujours présente : `cle_presente` doit être vraie
    prix_in=0.0,
    prix_out=0.0,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def fiche_temporaire(contenu: str = FICHE) -> tuple[Path, Aide, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name) / "aide-test.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin, load_aide(chemin), tmp


def contexte(frais: str = FRAIS) -> tuple[AideAnalysis, AideCollect]:
    """Une aide dont la page officielle a bougé entre baseline et contenu frais."""
    murl = MonitoredUrl(url=URL, role="officielle", baseline_sha="0" * 64, baseline_body=BASELINE)
    result = FetchResult(url=URL, status=200, raw_text=frais, body_md=frais, sha256="1" * 64)
    collect = AideCollect(slug="aide-test", urls=[murl], fetched={URL: result})
    an = AideAnalysis(
        slug="aide-test",
        statut="MAJ_LLM",
        urls=[UrlVerdict(murl=murl, result=result, diff=normalized_diff(BASELINE, frais))],
    )
    return an, collect


def reponse(**kwargs) -> str:
    return json.dumps({"slug": "aide-test", "resume": "", **kwargs}, ensure_ascii=False)


MAJ_TAUX = reponse(
    resume="taux porté à 40 %",
    financement={
        "champs": {"taux_max": 40.0},
        "quote": "Le taux d'intervention est porté à 40 %",
    },
)


class FauxModele:
    """Rend les réponses fournies, dans l'ordre, et compte les appels."""

    def __init__(self, *reponses: str | LLMCall) -> None:
        self.reponses = list(reponses)
        self.prompts: list[str] = []

    def __call__(self, spec, system, user, **kwargs) -> LLMCall:
        self.prompts.append(user)
        r = self.reponses[min(len(self.prompts) - 1, len(self.reponses) - 1)]
        return r if isinstance(r, LLMCall) else LLMCall(text=r, cost_usd=0.001, latency_s=1.0)


class BaseEtageC(unittest.TestCase):
    """Étage C complet, modèle et dossier de sources mis en bac à sable.

    `SOURCES_DIR` DOIT être détourné : une mise à jour réussie ré-archive ses
    pages, et sans ça un simple `pytest` déposait `data/sources/aide-test/`
    dans le dépôt.
    """

    def lancer(self, *reponses, dry_run=False, frais=FRAIS, contenu=FICHE):
        chemin, aide, tmp = fiche_temporaire(contenu)
        an, collect = contexte(frais)
        faux = FauxModele(*reponses)
        reel_call, reel_dir = veille_update.call, snapshot_source.SOURCES_DIR
        sources = tempfile.TemporaryDirectory()
        veille_update.call = faux
        snapshot_source.SOURCES_DIR = Path(sources.name)
        try:
            with tmp, sources:
                res = mettre_a_jour(
                    aide,
                    an,
                    collect,
                    SPEC,
                    aujourd_hui=AUJOURD_HUI,
                    dry_run=dry_run,
                    chemin=chemin,
                )
                return res, chemin.read_text(encoding="utf-8"), faux
        finally:
            veille_update.call, snapshot_source.SOURCES_DIR = reel_call, reel_dir


# ---------------------------------------------------------------------------
# Écriture, ou non
# ---------------------------------------------------------------------------


class TestEcriture(BaseEtageC):
    def test_reponse_vide_ne_touche_pas_le_fichier(self):
        res, apres, faux = self.lancer(reponse(conditions=[]))
        self.assertEqual(res.etat, "inchange")
        self.assertEqual(apres, FICHE)
        self.assertEqual(len(faux.prompts), 1)

    def test_mise_a_jour_ecrite_sur_disque(self):
        res, apres, _ = self.lancer(MAJ_TAUX)
        self.assertEqual(res.etat, "applique", res.erreurs)
        self.assertEqual(res.champs, ["financement.taux_max"])
        # La preuve part avec la modification : page ré-archivée dans le même geste.
        self.assertEqual(res.snapshots, [f"{AUJOURD_HUI.isoformat()}.md"])
        self.assertIn("taux_max: 40.0", apres)
        self.assertNotIn("taux_max: 30.0", apres)
        # Le reste du fichier ne bouge pas : c'est ce qui garde le diff lisible.
        self.assertIn("  - id: montant-moyen", apres)

    def test_dry_run_calcule_mais_n_ecrit_rien(self):
        res, apres, _ = self.lancer(MAJ_TAUX, dry_run=True)
        self.assertEqual(res.etat, "applique", res.erreurs)
        self.assertEqual(res.champs, ["financement.taux_max"])
        self.assertEqual(apres, FICHE, "--dry-run doit laisser le fichier intact")
        self.assertEqual(res.snapshots, [], "aucun snapshot ne doit être ré-archivé à blanc")

    def test_sans_contenu_frais_le_modele_n_est_pas_appele(self):
        chemin, aide, tmp = fiche_temporaire()
        an, _ = contexte()
        faux = FauxModele(MAJ_TAUX)
        reel = veille_update.call
        veille_update.call = faux
        try:
            with tmp:
                res = mettre_a_jour(
                    aide,
                    an,
                    AideCollect(slug="aide-test"),  # rien de téléchargé
                    SPEC,
                    aujourd_hui=AUJOURD_HUI,
                    chemin=chemin,
                )
        finally:
            veille_update.call = reel
        self.assertEqual(res.etat, "echec")
        self.assertEqual(res.etape_echec, "collecte")
        self.assertEqual(faux.prompts, [], "aucun jeton ne doit être brûlé sans document")


# ---------------------------------------------------------------------------
# La nouvelle tentative
# ---------------------------------------------------------------------------


class TestNouvelleTentative(BaseEtageC):
    def test_citation_inventee_rejouee_une_fois_puis_acceptee(self):
        invente = reponse(
            financement={"champs": {"taux_max": 40.0}, "quote": "le taux est de 40 % depuis 2019"}
        )
        res, apres, faux = self.lancer(invente, MAJ_TAUX)
        self.assertEqual(len(faux.prompts), 2)
        self.assertEqual(res.tentatives, 2)
        self.assertEqual(res.etat, "applique", res.erreurs)
        self.assertIn("taux_max: 40.0", apres)
        # Le second prompt porte le motif du rejet, pas seulement le premier.
        self.assertIn("REJETÉE", faux.prompts[1])
        self.assertIn("citation introuvable", faux.prompts[1])

    def test_deux_echecs_rattrapables_s_arretent_a_deux_appels(self):
        invente = reponse(
            financement={"champs": {"taux_max": 40.0}, "quote": "un taux jamais écrit nulle part"}
        )
        res, apres, faux = self.lancer(invente, invente)
        self.assertEqual(len(faux.prompts), 2, "une seule nouvelle tentative, pas une boucle")
        self.assertEqual(res.etat, "echec")
        self.assertEqual(res.etape_echec, "quote")
        self.assertEqual(apres, FICHE)
        # La réponse fautive est conservée : un rejet dont on ignore la cause
        # exacte n'est pas rejouable.
        self.assertIn("un taux jamais écrit nulle part", res.reponse_rejetee)

    def test_echec_non_rattrapable_n_est_pas_rejoue(self):
        # Un champ hors périmètre est une erreur de référentiel… donc rattrapable.
        # Un re-typage déguisé aussi. Ce qui ne l'est PAS : un JSON syntaxiquement
        # valide dont l'édition échoue — notre bug, pas celui du modèle. Les cas
        # réels (section absente, section en flow) sont désormais gérés par
        # l'éditeur : l'échec est donc simulé à la sortie de `appliquer`.
        def edition_ratee(texte, aide, *args, **kwargs):
            res = veille_apply.ApplyResult(slug=aide.slug, etape="edition")
            res.erreurs = ["édition impossible"]
            return res

        with patch.object(veille_update, "appliquer", edition_ratee):
            res, _, faux = self.lancer(
                reponse(
                    cumul={
                        "champs": {"cumulable": False},
                        "quote": "Le taux d'intervention est porté",
                    }
                ),
                MAJ_TAUX,
            )
        self.assertEqual(res.etape_echec, "edition")
        self.assertEqual(len(faux.prompts), 1, "notre bug d'édition ne se corrige pas au modèle")

    def test_reponse_vide_relancee_une_fois_a_l_identique(self):
        vide = LLMCall(error="contenu vide — finish_reason='stop'", reponse_vide=True)
        res, apres, faux = self.lancer(vide, MAJ_TAUX)
        self.assertEqual(len(faux.prompts), 2)
        # Relance à l'identique : rien à corriger, le modèle n'a rien dit.
        self.assertEqual(faux.prompts[0], faux.prompts[1])
        self.assertEqual(res.etat, "applique", res.erreurs)
        self.assertIn("taux_max: 40.0", apres)

    def test_reponse_vide_deux_fois_abandonne(self):
        vide = LLMCall(error="contenu vide", reponse_vide=True)
        res, _, faux = self.lancer(vide, vide)
        self.assertEqual(len(faux.prompts), 2, "une seule relance, pas une boucle")
        self.assertEqual(res.etape_echec, "appel")

    def test_erreur_d_api_n_est_pas_relancee(self):
        # Un 429 échouerait pareil : le relancer coûterait un aller-retour par
        # aide sans rien rattraper.
        res, _, faux = self.lancer(LLMCall(error="429 rate limit"), MAJ_TAUX)
        self.assertEqual(len(faux.prompts), 1)
        self.assertEqual(res.etape_echec, "appel")

    def test_appel_en_echec_remonte_tel_quel(self):
        res, apres, faux = self.lancer(LLMCall(error="429 rate limit"))
        self.assertEqual(res.etat, "echec")
        self.assertEqual(res.etape_echec, "appel")
        self.assertIn("429", res.raison)
        self.assertEqual(apres, FICHE)
        self.assertEqual(len(faux.prompts), 1)


class TestConditionsNouvellesOuDisparues(BaseEtageC):
    """Décision du 2026-10-04 : la veille n'écrit ni n'annote aucune condition.

    Une condition apparue ou disparue est ce que la veille existe pour voir, et
    elle part en ré-ingestion dès la première : ajoutée en `untyped`, elle
    retirait l'aide entière du moteur.
    """

    def _ajouts(self, n: int) -> str:
        return reponse(
            conditions=[
                {
                    "op": "add",
                    "id": f"nouvelle-condition-{i}",
                    "condition": {
                        "id": f"nouvelle-condition-{i}",
                        "text": f"Condition nouvelle numéro {i}.",
                        "kind": "untyped",
                        "quote": "Le taux d'intervention est porté à 40 %",
                    },
                }
                for i in range(n)
            ]
        )

    def test_un_seul_ajout_escalade_sans_rien_ecrire(self):
        res, apres, faux = self.lancer(self._ajouts(1))
        self.assertEqual(res.etat, "escalade", res.erreurs)
        self.assertIn("1 condition(s) nouvelle(s)", res.raison)
        self.assertIn("nouvelle-condition-0", res.raison)
        self.assertIn("ré-ingestion", res.raison)
        self.assertEqual(apres, FICHE)
        self.assertEqual(len(faux.prompts), 1, "un constat ne se renégocie pas avec le modèle")

    def test_condition_disparue_escalade_sans_annoter(self):
        res, apres, _ = self.lancer(
            reponse(conditions=[{"op": "signaler_disparue", "id": "montant-moyen"}])
        )
        self.assertEqual(res.etat, "escalade", res.erreurs)
        self.assertIn("disparue(s)", res.raison)
        self.assertEqual(apres, FICHE)

    def test_ajout_et_retouche_ensemble_rien_n_est_ecrit(self):
        # La retouche de taux qui accompagne l'ajout n'est pas appliquée seule :
        # la ré-ingestion reprendra l'aide entière.
        sortie = json.loads(self._ajouts(1))
        sortie["financement"] = json.loads(MAJ_TAUX)["financement"]
        res, apres, _ = self.lancer(json.dumps(sortie))
        self.assertEqual(res.etat, "escalade", res.erreurs)
        self.assertEqual(apres, FICHE)


class TestChangementMajeur(BaseEtageC):
    def test_auto_declaration_escalade_sans_rien_ecrire(self):
        res, apres, faux = self.lancer(
            reponse(changement_majeur=True, raison_changement_majeur="le dispositif a été fusionné")
        )
        self.assertEqual(res.etat, "escalade")
        self.assertIn("fusionné", res.raison)
        self.assertEqual(apres, FICHE)
        self.assertEqual(len(faux.prompts), 1, "une escalade n'est pas une erreur à corriger")


# ---------------------------------------------------------------------------
# Ré-archivage de la preuve
# ---------------------------------------------------------------------------


class TestRafraichirSnapshots(unittest.TestCase):
    def _avec_sources(self, an, collect):
        tmp = tempfile.TemporaryDirectory()
        reel = snapshot_source.SOURCES_DIR
        snapshot_source.SOURCES_DIR = Path(tmp.name)
        try:
            with tmp:
                noms = veille_update.rafraichir_snapshots(an, collect, jour=AUJOURD_HUI)
                return noms, sorted(p.name for p in (Path(tmp.name) / an.slug).glob("*"))
        finally:
            snapshot_source.SOURCES_DIR = reel

    def test_page_changee_rearchivee(self):
        an, collect = contexte()
        noms, fichiers = self._avec_sources(an, collect)
        self.assertEqual(noms, [f"{AUJOURD_HUI.isoformat()}.md"])
        self.assertEqual(fichiers, noms)

    def test_page_inchangee_non_rearchivee(self):
        # Sans ça, `data/sources/` gagnerait un snapshot par page et par passage.
        an, collect = contexte(frais=BASELINE)
        noms, _ = self._avec_sources(an, collect)
        self.assertEqual(noms, [])

    def test_contenu_de_proxy_jamais_archive(self):
        an, collect = contexte()
        collect.fetched[URL].via_proxy = True
        noms, _ = self._avec_sources(an, collect)
        self.assertEqual(noms, [], "un texte de proxy ferait diverger tous les diffs suivants")


class TestPromptCorrection(unittest.TestCase):
    def test_porte_le_prompt_initial_et_les_motifs(self):
        p = prompt_correction(
            "PROMPT INITIAL", '{"a": 1}', ["citation introuvable", "champ inconnu"]
        )
        self.assertIn("PROMPT INITIAL", p)
        self.assertIn("citation introuvable", p)
        self.assertIn("champ inconnu", p)
        self.assertIn('{"a": 1}', p)


# ---------------------------------------------------------------------------
# Câblage CLI
# ---------------------------------------------------------------------------


class MuetJournal:
    """Même interface que `Journal`, sans polluer la sortie des tests."""

    def __call__(self, message: str = "") -> None:
        pass


def analyses_factices(*statuts: str) -> dict[str, AideAnalysis]:
    return {
        f"aide-{i}": AideAnalysis(slug=f"aide-{i}", statut=s)  # type: ignore[arg-type]
        for i, s in enumerate(statuts)
    }


class TestRunStageC(unittest.TestCase):
    def setUp(self):
        self.appels: list[str] = []
        self.reel = veille_update.mettre_a_jour

        def faux(aide, an, collect, spec, **kwargs):
            self.appels.append(an.slug)
            return MajResult(slug=an.slug, etat="applique", modele=spec.alias)

        import veille_aides

        self.module = veille_aides
        veille_aides.mettre_a_jour = faux
        # L'étage C se saute lui-même quand la clé du modèle manque. Sans ce
        # forçage, ces tests passaient sur la machine du dev (où `backend/.env`
        # est chargé) et échouaient en CI, où aucune clé n'existe : c'est le
        # contenu de l'environnement, pas le câblage, qui décidait du résultat.
        # `patch.dict` restaure l'environnement entier au teardown, y compris
        # une clé retirée à l'intérieur d'un test.
        env = patch.dict(os.environ, {"DEEPSEEK_API_KEY": "cle-de-test"})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self.module.mettre_a_jour = self.reel

    def _args(self, **kwargs) -> argparse.Namespace:
        base = {
            "report_only": False,
            "offline": False,
            "dry_run": False,
            "max_llm": 20,
            "model": "ds-flash",
        }
        return argparse.Namespace(**{**base, **kwargs})

    def _lancer(self, args, analyses):
        aides = dict.fromkeys(analyses)  # l'ordre des clés = l'ordre d'ancienneté
        collects = dict.fromkeys(analyses)
        return run_stage_c(args, aides, analyses, collects, AUJOURD_HUI, MuetJournal())

    def test_report_only_n_appelle_jamais_le_modele(self):
        majs = self._lancer(self._args(report_only=True), analyses_factices("MAJ_LLM", "MAJ_LLM"))
        self.assertEqual(majs, {})
        self.assertEqual(self.appels, [])

    def test_offline_n_appelle_jamais_le_modele(self):
        majs = self._lancer(self._args(offline=True), analyses_factices("MAJ_LLM"))
        self.assertEqual(majs, {})
        self.assertEqual(self.appels, [])

    def test_seules_les_maj_llm_sont_soumises(self):
        analyses = analyses_factices("OK", "MAJ_LLM", "ESCALADE_INGESTION", "MAJ_LLM")
        self._lancer(self._args(), analyses)
        self.assertEqual(self.appels, ["aide-1", "aide-3"])

    def test_max_llm_plafonne_dans_l_ordre_d_anciennete(self):
        analyses = analyses_factices(*(["MAJ_LLM"] * 5))
        majs = self._lancer(self._args(max_llm=2), analyses)
        self.assertEqual(self.appels, ["aide-0", "aide-1"])
        self.assertEqual(sorted(majs), ["aide-0", "aide-1"])

    def test_escalade_bascule_le_statut(self):
        def faux(aide, an, collect, spec, **kwargs):
            return MajResult(slug=an.slug, etat="escalade", raison="dispositif fusionné")

        self.module.mettre_a_jour = faux
        analyses = analyses_factices("MAJ_LLM")
        self._lancer(self._args(), analyses)
        self.assertEqual(analyses["aide-0"].statut, "ESCALADE_INGESTION")
        self.assertIn("dispositif fusionné", analyses["aide-0"].raisons)

    def test_changement_deja_refuse_n_est_pas_resoumis(self):
        from veille_aides import empreinte_changement

        analyses = analyses_factices("MAJ_LLM", "MAJ_LLM", "MAJ_LLM")
        manifest = {
            "aide-0": {
                "maj_refusee": {
                    "date": "2026-08-01",
                    "etat": "escalade",
                    "empreinte": empreinte_changement(analyses["aide-0"]),
                    "raison": "1 condition(s) nouvelle(s)",
                }
            },
            # Empreinte différente : la source a encore bougé, on resoumet.
            "aide-1": {"maj_refusee": {"etat": "echec", "empreinte": "perimee"}},
        }
        aides = dict.fromkeys(analyses)
        run_stage_c(
            self._args(max_llm=2),
            aides,
            analyses,
            dict.fromkeys(analyses),
            AUJOURD_HUI,
            MuetJournal(),
            manifest=manifest,
        )
        # aide-0 ne prend pas de place sous le plafond : aide-1 et aide-2 passent.
        self.assertEqual(self.appels, ["aide-1", "aide-2"])
        self.assertEqual(analyses["aide-0"].statut, "ESCALADE_INGESTION")

    def test_cle_absente_saute_l_etage_sans_echouer(self):
        spec = self.module.resoudre_modele("gpt-luna")
        os.environ.pop(spec.env_key, None)
        self.assertFalse(ModelSpec.cle_presente.fget(spec))  # type: ignore[attr-defined]
        analyses = analyses_factices("MAJ_LLM")
        majs = self._lancer(self._args(model="gpt-luna"), analyses)
        self.assertEqual(majs, {})
        self.assertEqual(self.appels, [])
        # L'aide reste candidate : une clé manquante diffère le passage, elle ne
        # le solde pas.
        self.assertEqual(analyses["aide-0"].statut, "MAJ_LLM")


class TestManifesteEtRapport(unittest.TestCase):
    def test_maj_enregistree_puis_conservee_au_run_suivant(self):
        analyses = analyses_factices("MAJ_LLM")
        maj = MajResult(
            slug="aide-0", etat="applique", modele="ds-flash", champs=["financement.taux_max"]
        )
        m1 = update_manifest({}, analyses, {"aide-0": maj}, AUJOURD_HUI)
        self.assertEqual(m1["aide-0"]["maj"]["champs"], ["financement.taux_max"])
        # Passage suivant sans mise à jour : la trace ne doit pas disparaître.
        m2 = update_manifest(m1, analyses_factices("OK"), {}, date(2026, 9, 1))
        self.assertEqual(m2["aide-0"]["maj"]["date"], AUJOURD_HUI.isoformat())
        self.assertEqual(m2["aide-0"]["checked_at"], "2026-09-01")

    def test_rapport_dit_ce_qui_a_ete_ecrit(self):
        analyses = analyses_factices("MAJ_LLM")
        majs = {
            "aide-0": MajResult(
                slug="aide-0",
                etat="applique",
                modele="ds-flash",
                resume="taux porté à 40 %",
                champs=["financement.taux_max"],
                snapshots=["2026-08-07.md"],
            )
        }
        complet = build_report(analyses, AUJOURD_HUI, 60.0, majs=majs, mode="complet")
        self.assertIn("ÉCRITE", complet)
        self.assertIn("financement.taux_max", complet)
        self.assertIn("2026-08-07.md", complet)

        blanc = build_report(analyses, AUJOURD_HUI, 60.0, majs=majs, mode="dry-run")
        self.assertIn("aucun fichier n'a été écrit", blanc)
        self.assertIn("À blanc", blanc)

    def test_rapport_report_only_ne_promet_aucune_ecriture(self):
        texte = build_report(analyses_factices("MAJ_LLM"), AUJOURD_HUI, 60.0)
        self.assertIn("aucun YAML d'aide n'a été modifié", texte)
        self.assertNotIn("## Étage C", texte)


class TestResolutionModele(unittest.TestCase):
    """Le point unique de réglage du modèle, et la porte de sortie hors registre.

    Le pipeline change de modèle plus souvent qu'il ne change de code : ces
    tests gardent l'invariant qui rend ça possible — un alias suffit, et un
    modèle sorti hier s'essaie sans écrire une ligne de Python.
    """

    def test_le_defaut_est_resolvable(self):
        # Sans ça, tout étage LLM planterait au premier appel avec le défaut du
        # dépôt (ou un VEILLE_MODEL mal saisi).
        spec = resoudre_modele(MODELE_DEFAUT)
        self.assertEqual(spec.alias, MODELE_DEFAUT)

    def test_tous_les_alias_du_registre_se_resolvent(self):
        for alias, attendu in REGISTRE.items():
            self.assertIs(resoudre_modele(alias), attendu)

    def test_chaque_fournisseur_a_au_moins_un_modele(self):
        couverts = {s.fournisseur for s in REGISTRE.values()}
        self.assertEqual(couverts, set(FOURNISSEURS))

    def test_modele_hors_registre_herite_du_fournisseur(self):
        spec = resoudre_modele("glm:glm-9-turbo")
        f = FOURNISSEURS["glm"]
        self.assertEqual(spec.model_id, "glm-9-turbo")
        self.assertEqual(spec.env_key, f.env_key)
        self.assertEqual(spec.base_url, f.base_url)
        self.assertEqual(spec.provider, f.protocole)
        # Un identifiant recopié à la main n'est jamais réputé vérifié, et son
        # tarif est inconnu : mieux vaut aucun coût rapporté qu'un coût faux.
        self.assertFalse(spec.id_verifie)
        self.assertFalse(spec.tarif_connu)

    def test_fournisseur_ou_modele_inconnu_est_une_erreur_parlante(self):
        for nom in ("openia:gpt-5", "modele-invente", "glm:"):
            with self.assertRaises(KeyError):
                resoudre_modele(nom)


if __name__ == "__main__":
    unittest.main()


class TestRafraichirSnapshotsPdf(TestRafraichirSnapshots):
    """Un règlement PDF modifié est ré-archivé avec sa provenance ; un .docx non."""

    PDF_URL = "https://ex.fr/reglement.pdf"

    def _contexte_binaire(self, contenu: bytes) -> tuple[AideAnalysis, AideCollect]:
        murl = MonitoredUrl(
            url=self.PDF_URL,
            role="snapshot",
            label="reglement",
            baseline_sha="0" * 64,
            is_binary=True,
        )
        result = FetchResult(
            url=self.PDF_URL, status=200, sha256="1" * 64, is_binary=True, content=contenu
        )
        collect = AideCollect(slug="aide-test", urls=[murl], fetched={self.PDF_URL: result})
        an = AideAnalysis(
            slug="aide-test",
            statut="ESCALADE_INGESTION",
            urls=[UrlVerdict(murl=murl, result=result, binaire_modifie=True)],
        )
        return an, collect

    def test_pdf_modifie_rearchive_avec_sidecar(self):
        an, collect = self._contexte_binaire(b"%PDF-1.4 nouveau reglement")
        noms, fichiers = self._avec_sources(an, collect)
        attendu = f"{AUJOURD_HUI.isoformat()}-reglement.pdf"
        self.assertEqual(noms, [attendu])
        self.assertEqual(fichiers, [attendu, attendu + ".meta.yaml"])

    def test_docx_modifie_non_rearchive(self):
        an, collect = self._contexte_binaire(b"PK\x03\x04 docx")
        noms, _ = self._avec_sources(an, collect)
        self.assertEqual(noms, [])


class TestRearchivageSansRetouche(BaseEtageC):
    """Une page lue par le modèle devient la baseline, même sans retouche.

    Sinon l'aide dont la page a bougé hors mandat repasse au modèle à chaque
    run, pour la même réponse, indéfiniment.
    """

    def test_inchange_rearchive_la_page(self):
        res, apres, _ = self.lancer(reponse(conditions=[]))
        self.assertEqual(res.etat, "inchange")
        self.assertEqual(apres, FICHE)
        self.assertEqual(res.snapshots, [f"{AUJOURD_HUI.isoformat()}.md"])

    def test_inchange_a_blanc_n_archive_rien(self):
        res, _, _ = self.lancer(reponse(conditions=[]), dry_run=True)
        self.assertEqual(res.etat, "inchange")
        self.assertEqual(res.snapshots, [])


class TestManifesteErreurHttp(unittest.TestCase):
    def test_erreur_http_garde_la_date_du_dernier_vrai_controle(self):
        # Sinon l'aide injoignable recule en fin de file d'ancienneté, donc
        # hors d'un `--limit` au passage suivant : l'inverse de « à retenter ».
        avant = {"aide-0": {"checked_at": "2026-07-01", "status": "ok"}}
        m = update_manifest(avant, analyses_factices("ERREUR_HTTP"), {}, AUJOURD_HUI)
        self.assertEqual(m["aide-0"]["checked_at"], "2026-07-01")
        self.assertEqual(m["aide-0"]["status"], "erreur_http")

    def test_erreur_http_sur_une_aide_jamais_vue_reste_sans_date(self):
        m = update_manifest({}, analyses_factices("ERREUR_HTTP"), {}, AUJOURD_HUI)
        self.assertNotIn("checked_at", m["aide-0"])

    def test_erreur_http_se_range_a_sa_derniere_tentative(self):
        # Sinon les sources en panne durable restent seules en tête de file, et
        # un `--limit` ne revisite plus qu'elles.
        from veille_aides import anciennete

        avant = {"aide-0": {"checked_at": "2026-07-01", "status": "ok"}}
        m = update_manifest(avant, analyses_factices("ERREUR_HTTP"), {}, AUJOURD_HUI)
        self.assertEqual(m["aide-0"]["tente_le"], AUJOURD_HUI.isoformat())
        aide = Aide.model_validate(
            {
                "slug": "aide-0",
                "nom": "n",
                "organisme": "o",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
            }
        )
        self.assertEqual(anciennete(aide, m), AUJOURD_HUI)

    def test_maj_llm_laissee_de_cote_garde_sa_date(self):
        # Plafond `--max-llm` atteint : l'aide n'a pas été traitée, elle doit
        # repasser en tête au run suivant.
        avant = {"aide-0": {"checked_at": "2026-07-01", "status": "ok"}}
        m = update_manifest(avant, analyses_factices("MAJ_LLM"), {}, AUJOURD_HUI)
        self.assertEqual(m["aide-0"]["checked_at"], "2026-07-01")

    def test_refus_memorise_puis_oublie_quand_l_aide_sort_de_maj_llm(self):
        refus = MajResult(slug="aide-0", etat="echec", raison="deep_diff", empreinte="e1")
        m1 = update_manifest({}, analyses_factices("MAJ_LLM"), {"aide-0": refus}, AUJOURD_HUI)
        self.assertEqual(m1["aide-0"]["maj_refusee"]["empreinte"], "e1")
        m2 = update_manifest(m1, analyses_factices("MAJ_LLM"), {}, AUJOURD_HUI)
        self.assertIn("maj_refusee", m2["aide-0"])
        m3 = update_manifest(m2, analyses_factices("OK"), {}, AUJOURD_HUI)
        self.assertNotIn("maj_refusee", m3["aide-0"])

    def test_rapport_liste_les_pages_rearchivees_sans_retouche(self):
        majs = {
            "aide-0": MajResult(
                slug="aide-0",
                etat="inchange",
                resume="contact modifié, rien dans le mandat",
                snapshots=["2026-08-07.md"],
            )
        }
        texte = build_report(
            analyses_factices("MAJ_LLM"), AUJOURD_HUI, 60.0, majs=majs, mode="complet"
        )
        self.assertIn("ré-archivées sans retouche", texte)
        self.assertIn("2026-08-07.md", texte)


class TestAcquittements(unittest.TestCase):
    """Une échéance dépassée arbitrée par un humain ne ressort plus, tant que la date tient."""

    def _analyses(self) -> dict[str, AideAnalysis]:
        an = AideAnalysis(
            slug="aide-0",
            statut="DATE_PERIMEE_SOURCE_INCHANGEE",
            raisons=["date limite dépassée (2026-05-30) mais source inchangée"],
            date_limite_perimee=date(2026, 5, 30),
        )
        return {"aide-0": an}

    def test_acquitter_puis_se_taire(self):
        from veille_aides import traiter_acquittements

        manifest: dict = {}
        analyses = self._analyses()
        poses = traiter_acquittements(analyses, manifest, nouveaux=["aide-0"])
        self.assertEqual(poses, ["aide-0"])
        self.assertEqual(manifest["aide-0"]["ack"], {"date_perimee": "2026-05-30"})
        self.assertEqual(analyses["aide-0"].statut, "OK")
        self.assertIn("acquittée", analyses["aide-0"].raisons[0])
        # Le run suivant lit l'acquittement au manifeste et se tait de lui-même.
        suivantes = self._analyses()
        self.assertEqual(traiter_acquittements(suivantes, manifest), [])
        self.assertEqual(suivantes["aide-0"].statut, "OK")

    def test_une_nouvelle_date_limite_rallume_l_alerte(self):
        from veille_aides import traiter_acquittements

        manifest = {"aide-0": {"ack": {"date_perimee": "2025-05-30"}}}
        analyses = self._analyses()
        traiter_acquittements(analyses, manifest)
        self.assertEqual(analyses["aide-0"].statut, "DATE_PERIMEE_SOURCE_INCHANGEE")

    def test_un_autre_statut_ne_s_acquitte_pas(self):
        from veille_aides import traiter_acquittements

        manifest: dict = {}
        analyses = analyses_factices("SANS_BASELINE")
        self.assertEqual(traiter_acquittements(analyses, manifest, nouveaux=["aide-0"]), [])
        self.assertNotIn("aide-0", manifest)

    def test_l_acquittement_survit_au_manifeste_suivant(self):
        avant = {"aide-0": {"checked_at": "2026-07-01", "ack": {"date_perimee": "2026-05-30"}}}
        m = update_manifest(avant, analyses_factices("OK"), {}, AUJOURD_HUI)
        self.assertEqual(m["aide-0"]["ack"], {"date_perimee": "2026-05-30"})


class TestEffortDeRaisonnement(unittest.TestCase):
    """Le budget de raisonnement d'OpenRouter est plafonné, sinon 400 s par appel."""

    def test_openrouter_transmet_l_effort_en_extra_body(self):
        from veille_llm import kwargs_openai_compat

        spec = resoudre_modele("or-glm")
        self.assertEqual(spec.effort, "medium")
        kwargs = kwargs_openai_compat(spec, "s", "u", 1000)
        self.assertEqual(kwargs["extra_body"], {"reasoning": {"effort": "medium"}})
        self.assertEqual(kwargs["max_tokens"], 1000)

    def test_modele_hors_registre_via_openrouter_herite_de_l_effort(self):
        spec = resoudre_modele("openrouter:z-ai/glm-5.4-flash")
        self.assertEqual(spec.effort, "medium")

    def test_les_autres_fournisseurs_ne_recoivent_rien(self):
        from veille_llm import kwargs_openai_compat

        for alias in ("ds-flash", "gpt-luna"):
            kwargs = kwargs_openai_compat(resoudre_modele(alias), "s", "u", 1000)
            self.assertNotIn("extra_body", kwargs, alias)

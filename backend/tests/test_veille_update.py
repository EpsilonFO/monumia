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
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import snapshot_source  # noqa: E402
import veille_update  # noqa: E402
from veille_aides import build_report, run_stage_c, update_manifest  # noqa: E402
from veille_analyze import AideAnalysis, UrlVerdict  # noqa: E402
from veille_collect import AideCollect, FetchResult, MonitoredUrl  # noqa: E402
from veille_llm import LLMCall, ModelSpec  # noqa: E402
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
        # valide dont l'édition échoue. On prend ici une section absente du
        # fichier, qui échoue à l'étape « edition ».
        sans_cumul = FICHE.replace("cumul:\n  cumulable: true\n\n", "")
        res, _, faux = self.lancer(
            reponse(
                cumul={"champs": {"cumulable": False}, "quote": "Le taux d'intervention est porté"}
            ),
            MAJ_TAUX,
            contenu=sans_cumul,
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


class TestPlafondAjouts(BaseEtageC):
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

    def test_quelques_ajouts_restent_une_retouche(self):
        res, apres, _ = self.lancer(self._ajouts(2))
        self.assertEqual(res.etat, "applique", res.erreurs)
        self.assertIn("nouvelle-condition-0", apres)
        self.assertIn("nouvelle-condition-1", apres)

    def test_ajouts_massifs_escaladent_sans_rien_ecrire(self):
        # Toutes correctement citées : la validation les laisserait passer. Ce
        # n'est pas leur véracité qui pose problème, c'est ce qu'elles révèlent —
        # une fiche incomplète, donc une ré-ingestion.
        res, apres, _ = self.lancer(self._ajouts(8))
        self.assertEqual(res.etat, "escalade")
        self.assertIn("8 conditions nouvelles", res.raison)
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
                noms = veille_update.rafraichir_snapshots(an, collect)
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

    def test_cle_absente_saute_l_etage_sans_echouer(self):
        analyses = analyses_factices("MAJ_LLM")
        majs = self._lancer(self._args(model="gpt-luna"), analyses)
        if not ModelSpec.cle_presente.fget(self.module.REGISTRE["gpt-luna"]):  # type: ignore[attr-defined]
            self.assertEqual(majs, {})
            self.assertEqual(self.appels, [])
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


if __name__ == "__main__":
    unittest.main()

"""Tests de Jev dans la veille (scripts/veille_arbitre.py, tri des refontes).

Aucun réseau : `ClientDecision` tourne sur un `httpx.MockTransport` qui rend
des probabilités fixées. Ce qui est vérifié n'est pas le jugement de Jev — le
banc d'essai s'en charge (`scripts/veille_benchmark_jev.py`) — mais ce que la
veille en fait : quelles aides lui sont soumises, et ce qu'une note change.

Run from backend/:  uv run pytest tests/test_veille_arbitre.py
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_arbitre  # noqa: E402
from pipeline.decision import ClientDecision  # noqa: E402
from veille_aides import trier_refontes  # noqa: E402
from veille_analyze import AideAnalysis, UrlVerdict  # noqa: E402
from veille_arbitre import Arbitre, Seuils, construire, etat_mandat, seuils  # noqa: E402
from veille_collect import FetchResult, MonitoredUrl  # noqa: E402
from veille_text import normalized_diff  # noqa: E402

from aides_schema import Aide  # noqa: E402

URL = "https://ex.fr/aide"

AIDE = Aide.model_validate(
    {
        "slug": "aide-test",
        "nom": "Aide de test",
        "organisme": "Organisme de test",
        "categorie": "region",
        "type": "subvention",
        "raison": ["restauration_travaux"],
        "description": "Une aide de test.",
        "source": {"url_officielle": URL, "verified_at": "2026-07-01"},
        "financement": {"taux_max": 30},
        "calendrier": {"permanent": False, "date_limite": "2026-12-31"},
        "conditions": [
            {
                "id": "montant-moyen",
                "text": "Les dossiers sélectionnés reçoivent 5 000 € en moyenne.",
                "kind": "info",
                "effect": "info",
                "quote": "5 000 € en moyenne",
            }
        ],
    }
)


class JevFactice:
    """Un `ClientDecision` réel sur un transport factice, qui note chaque état reçu."""

    def __init__(self, touche: float = 0.5, meme_reglement: float = 0.5, statut: int = 200):
        self.touche, self.meme_reglement, self.statut = touche, meme_reglement, statut
        self.etats: list[dict] = []
        self.client = ClientDecision(
            cle="faux",
            url="https://dec.example/",
            tentatives=1,
            transport=httpx.MockTransport(self._repondre),
        )

    def _repondre(self, req: httpx.Request) -> httpx.Response:
        corps = json.loads(req.content)
        self.etats.append(corps["state"])
        if self.statut != 200:
            return httpx.Response(self.statut, text="refusé")
        reponses = {}
        if "touche" in corps["questions"]:
            reponses["touche"] = {"type": "noul", "noul": self.touche}
            reponses["section"] = {
                "type": "choice",
                "choice": "calendrier",
                "probabilities": {"calendrier": 1.0},
            }
        if "meme_reglement" in corps["questions"]:
            reponses["meme_reglement"] = {"type": "noul", "noul": self.meme_reglement}
        return httpx.Response(
            200,
            json={"model": "typesafe/jev-test", "answers": reponses, "usage": {"cost": 0.0005}},
        )

    def arbitre(self, **seuils_) -> Arbitre:
        return Arbitre(client=self.client, seuils=Seuils(**seuils_))


class MuetJournal:
    def __call__(self, message: str = "") -> None:
        pass


def analyse_refonte(statut: str = "ESCALADE_INGESTION", refonte: bool = True) -> AideAnalysis:
    """Une page réécrite de fond en comble : règle 6 de l'étage B."""
    avant = "\n".join(f"Ancienne ligne de règlement numéro {i}." for i in range(20))
    apres = "\n".join(f"Nouvelle présentation du dispositif, bloc {i}." for i in range(20))
    murl = MonitoredUrl(url=URL, role="officielle", baseline_sha="0" * 64, baseline_body=avant)
    res = FetchResult(url=URL, status=200, raw_text=apres, body_md=apres, sha256="1" * 64)
    return AideAnalysis(
        slug="aide-test",
        statut=statut,  # type: ignore[arg-type]
        refonte=refonte,
        urls=[UrlVerdict(murl=murl, result=res, diff=normalized_diff(avant, apres))],
    )


class TestTriDesRefontes(unittest.TestCase):
    def test_refonte_jugee_sure_passe_en_maj_llm_jamais_en_ok(self):
        jev = JevFactice(meme_reglement=0.97)
        analyses = {"aide-test": analyse_refonte()}
        retro = trier_refontes(
            {"aide-test": AIDE}, analyses, jev.arbitre(refonte=0.9), MuetJournal()
        )
        an = analyses["aide-test"]
        self.assertEqual(an.statut, "MAJ_LLM")
        self.assertTrue(an.retrogradee)
        self.assertEqual(len(retro), 1)
        # La page fraîche, pas le diff, est ce que Jev compare à la fiche.
        self.assertIn("Nouvelle présentation", jev.etats[0]["pages"][0]["texte"])
        # La raison ne porte pas la note : elle entre dans l'empreinte du refus.
        self.assertNotIn("p =", an.raisons[-1])

    def test_refonte_douteuse_reste_en_reingestion(self):
        jev = JevFactice(meme_reglement=0.6)
        analyses = {"aide-test": analyse_refonte()}
        trier_refontes({"aide-test": AIDE}, analyses, jev.arbitre(refonte=0.9), MuetJournal())
        self.assertEqual(analyses["aide-test"].statut, "ESCALADE_INGESTION")
        self.assertFalse(analyses["aide-test"].retrogradee)

    def test_page_morte_jamais_soumise_a_jev(self):
        jev = JevFactice(meme_reglement=0.99)
        # Escalade par une autre règle que la 6 : page morte, binaire, contenu effondré.
        analyses = {"aide-test": analyse_refonte(refonte=False)}
        trier_refontes({"aide-test": AIDE}, analyses, jev.arbitre(refonte=0.5), MuetJournal())
        self.assertEqual(jev.etats, [])
        self.assertEqual(analyses["aide-test"].statut, "ESCALADE_INGESTION")

    def test_jev_en_panne_laisse_l_escalade(self):
        jev = JevFactice(statut=401)
        analyses = {"aide-test": analyse_refonte()}
        arbitre = jev.arbitre(refonte=0.5)
        trier_refontes({"aide-test": AIDE}, analyses, arbitre, MuetJournal())
        self.assertEqual(analyses["aide-test"].statut, "ESCALADE_INGESTION")
        self.assertEqual(len(arbitre.pannes), 1)

    def test_sans_seuil_de_refonte_rien_n_est_soumis(self):
        jev = JevFactice(meme_reglement=0.99)
        analyses = {"aide-test": analyse_refonte()}
        trier_refontes({"aide-test": AIDE}, analyses, jev.arbitre(filtre=0.1), MuetJournal())
        self.assertEqual(jev.etats, [])


class TestJugementDuMandat(unittest.TestCase):
    def test_note_section_et_cout(self):
        jev = JevFactice(touche=0.81)
        arbitre = jev.arbitre(garde=0.2)
        j = arbitre.mandat(AIDE, "- 31 décembre 2025\n+ 31 décembre 2026")
        self.assertAlmostEqual(j.p, 0.81)
        self.assertEqual(j.section, "calendrier")
        self.assertEqual(j.note, "p = 0,81")
        self.assertEqual(arbitre.appels, 1)
        self.assertAlmostEqual(arbitre.cout_usd, 0.0005)

    def test_le_resume_n_entre_dans_l_etat_que_s_il_est_donne(self):
        sans = etat_mandat(AIDE, "+ x")
        avec = etat_mandat(AIDE, "+ x", resume="la date limite passe au 31 décembre 2026")
        self.assertNotIn("resume_lecteur", sans)
        self.assertEqual(avec["resume_lecteur"], "la date limite passe au 31 décembre 2026")
        # Ce que la veille a le droit de retoucher, et rien d'autre.
        self.assertEqual(
            sorted(sans["fiche"]), ["calendrier", "conditions", "cumul", "financement", "nom"]
        )
        self.assertEqual(sans["fiche"]["calendrier"]["date_limite"], "2026-12-31")

    def test_diff_tronque_en_caracteres(self):
        etat = etat_mandat(AIDE, "+ " + "x" * (veille_arbitre.MAX_CAR_DIFF + 500))
        self.assertEqual(len(etat["diff"]), veille_arbitre.MAX_CAR_DIFF)


class TestSeuils(unittest.TestCase):
    def test_sans_seuil_jev_ne_joue_pas(self):
        arbitre, motif = construire(Seuils(None, None, None))
        self.assertIsNone(arbitre)
        self.assertIn("banc d'essai", motif)

    def test_cle_absente_jev_ne_joue_pas(self):
        with patch.dict(os.environ, {}, clear=True):
            arbitre, motif = construire(Seuils(filtre=0.1))
        self.assertIsNone(arbitre)
        self.assertIn("OPENROUTER_API_KEY", motif)

    def test_environnement_regle_et_coupe(self):
        env = {"JEV_VEILLE_FILTRE": "0.04", "JEV_VEILLE_GARDE": "off", "JEV_VEILLE_REFONTE": ""}
        with patch.dict(os.environ, env):
            s = seuils()
        self.assertEqual(s.filtre, 0.04)
        self.assertIsNone(s.garde)
        self.assertEqual(s.refonte, veille_arbitre.SEUIL_REFONTE)


if __name__ == "__main__":
    unittest.main()

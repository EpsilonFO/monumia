"""Tests de l'audit d'ontologie de fin de run (scripts/ingestion/ontologie.py).

Quatre propriétés à tenir :
  - le pré-filtre déterministe apparie sur la CLÉ autant que sur la question —
    c'est tout ce qui le sépare de l'inutilité, la mesure du corpus donnant 0,09
    de similarité de question entre deux faits identiques mais reformulés ;
  - les listes calculées (orphelins, polarités) ne viennent JAMAIS du modèle :
    elles sont exactes par construction, et lui laisser la main les rendrait
    fausses sans que rien ne le signale ;
  - une panne du modèle rend un rapport DÉGRADÉ, jamais une exception : le run
    est fini quand l'audit tourne, et il ne modifie rien ;
  - le rapport ne propose que des fusions, il n'en applique aucune.

Run from backend/:  uv run pytest tests/test_ingestion_ontologie.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providall  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402
from ingestion.ontologie import (  # noqa: E402
    Fusion,
    RapportOntologie,
    auditer,
    construire_prompt,
    orphelins,
    paires_suspectes,
    polarites_suspectes,
    rendre,
)
from providall.testing import chat_reply, fake_provider, json_reply  # noqa: E402

from aides_schema import FactDef  # noqa: E402

JOUR = date(2026, 9, 6)


def fait(question: str, **kw) -> FactDef:
    return FactDef.model_validate(
        {"type": "boolean", "scope": "monument", **kw, "question": question}
    )


FACTS = {
    "siege_social_meme_region_que_monument": fait(
        "Le siège social du porteur est-il dans la même région que le monument ?",
        scope="proprietaire",
    ),
    # Approuvé, et proche d'un proposé : le cas le plus rentable à trouver,
    # puisqu'il se résout en réutilisant un fait déjà arbitré.
    "structure_siege_grand_est": fait(
        "Le siège de la structure est-il en Grand Est ?", scope="proprietaire"
    ),
}

# Le cas qui justifie l'appariement sur la clé : deux faits identiques dont les
# questions ne se ressemblent pas du tout (le couple mesuré sur le corpus réel
# vaut 0,09 sur la question et 0,93 sur la clé).
PENDING = {
    "exploitation_atelier_animal": fait(
        "Détenez-vous des animaux d'élevage ?", scope="proprietaire"
    ),
    "exploitation_sau_atelier_animal": fait(
        "Quelle part de votre surface agricole utile est-elle consacrée à un atelier animal, "
        "et cet atelier est-il déclaré à la MSA ?",
        scope="proprietaire",
    ),
    "porteur_siege_grand_est": fait(
        "Le porteur a-t-il son siège en Grand Est ?", scope="proprietaire"
    ),
    "jardin_remarquable": fait("Le jardin est-il labellisé « Jardin remarquable » ?"),
    # Clé volontairement impossible dans le vrai catalogue : les tests d'orphelins
    # passent par `Atelier.dossiers_catalogue`, qui balaie AUSSI `data/aides/`.
    # Sans ça, ils mesureraient l'état du dépôt au lieu de la fonction.
    "zz_fait_que_rien_ne_reference": fait("Question que personne ne pose ?"),
}

REPONSE = {
    "fusions": [
        {
            "garder": "exploitation_sau_atelier_animal",
            "retirer": "exploitation_atelier_animal",
            "verdict": "doublon",
            "motif": "Les deux demandent la détention d'un atelier animal.",
            "prudence": "Le fait gardé porte aussi une part de SAU : relire les prédicats.",
        },
        {
            "garder": "porteur_siege_grand_est",
            "retirer": "siege_social_meme_region_que_monument",
            "verdict": "distincts",
            "motif": "L'un porte une région nommée, l'autre une coïncidence de régions.",
        },
    ],
    "commentaire": "Une seule fusion défendable.",
}


def client() -> providall.Client:
    return providall.Client("ds-pro", api_key="faux", retry=providall.RetryPolicy(retries=0))


class BaseOntologie(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.atelier = atelier_redirige("ex-aide", Path(self._tmp.name), jour=JOUR)
        self._tmp_bis = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_bis.cleanup)
        self.racine_bis = Path(self._tmp_bis.name)

    def ecrire_aide(self, slug: str, fact_id: str) -> None:
        self.atelier.aides_dir.mkdir(parents=True, exist_ok=True)
        (self.atelier.aides_dir / f"{slug}.yaml").write_text(
            f"slug: {slug}\nconditions:\n  - id: c1\n    fact: {fact_id}\n", encoding="utf-8"
        )


class TestPrefiltre(unittest.TestCase):
    def test_apparie_malgre_une_question_totalement_reformulee(self):
        """Le cas que l'appariement sur la seule question rate — donc le cas décisif."""
        paires = paires_suspectes(FACTS, PENDING)
        couples = {tuple(sorted((a, b))) for _s, a, b in paires}
        self.assertIn(("exploitation_atelier_animal", "exploitation_sau_atelier_animal"), couples)

    def test_un_fait_sans_voisin_ne_produit_aucune_paire(self):
        paires = paires_suspectes(FACTS, {"jardin_remarquable": PENDING["jardin_remarquable"]})
        self.assertEqual(paires, [])

    def test_chaque_paire_nest_rendue_quune_fois(self):
        paires = paires_suspectes(FACTS, PENDING)
        couples = [tuple(sorted((a, b))) for _s, a, b in paires]
        self.assertEqual(len(couples), len(set(couples)))

    def test_deux_faits_approuves_ne_sont_jamais_apparies(self):
        """Un fait de facts.yaml a été arbitré par un humain : l'audit d'un run n'y revient pas."""
        approuves = {
            "porteur_siege_grand_est": fait("Le porteur a-t-il son siège en Grand Est ?"),
            "porteur_siege_grand_ouest": fait("Le porteur a-t-il son siège en Grand Ouest ?"),
        }
        self.assertEqual(paires_suspectes(approuves, {}), [])

    def test_triees_du_plus_proche_au_moins_proche(self):
        scores = [s for s, _a, _b in paires_suspectes(FACTS, PENDING)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_la_limite_garde_les_pires(self):
        paires = paires_suspectes(FACTS, PENDING, limite=1)
        self.assertEqual(len(paires), 1)
        self.assertEqual(paires[0][0], max(s for s, _a, _b in paires_suspectes(FACTS, PENDING)))


class TestPolarites(unittest.TestCase):
    def test_cle_affirmative_question_negative(self):
        """Le cas nommé : la clé dit « éligible », la question demande l'inéligibilité."""
        suspects = polarites_suspectes(
            {
                "demande_eligible_france_agrimer": fait(
                    "La demande est-elle non éligible aux aides France AgriMer ?", scope="projet"
                )
            }
        )
        self.assertEqual(suspects, ["demande_eligible_france_agrimer"])

    def test_cle_negative_question_affirmative(self):
        suspects = polarites_suspectes(
            {
                "dgd_sans_cartographie_stations": fait(
                    "Votre forêt dispose-t-elle d'une cartographie des stations forestières ?"
                )
            }
        )
        self.assertEqual(suspects, ["dgd_sans_cartographie_stations"])

    def test_polarites_accordees_non_signalees(self):
        suspects = polarites_suspectes(
            {
                "chauffage_sans_fioul": fait("Le chauffage sera-t-il sans fioul après travaux ?"),
                "jardin_remarquable": PENDING["jardin_remarquable"],
            }
        )
        self.assertEqual(suspects, [])

    def test_une_negation_ailleurs_dans_la_question_ne_suffit_pas(self):
        """Le faux positif qui noierait le rapport : presque toute question en porte une."""
        suspects = polarites_suspectes(
            {
                "effectif_salaries": fait(
                    "Combien de salariés compte la structure (hors dirigeants non rémunérés) ?",
                    type="integer",
                    scope="proprietaire",
                )
            }
        )
        self.assertEqual(suspects, [])


class TestOrphelins(BaseOntologie):
    def test_fait_reference_nest_pas_orphelin(self):
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        self.assertEqual(
            orphelins(PENDING, self.atelier.aides_dir),
            sorted(set(PENDING) - {"jardin_remarquable"}),
        )

    def test_dossier_daides_absent_rend_tout_orphelin(self):
        self.assertEqual(orphelins(PENDING, Path("/n/existe/pas")), sorted(PENDING))

    def test_plusieurs_dossiers_sont_balayes(self):
        """Le banc d'essai en a deux : les aides du run, et le vrai catalogue.

        N'en balayer qu'un ferait passer pour orphelins les 499 faits proposés
        par tout le reste du catalogue — à chaque lint de l'agent, et dans le
        rapport de fin de run.
        """
        autre = self.racine_bis / "aides"
        autre.mkdir(parents=True, exist_ok=True)
        (autre / "ailleurs.yaml").write_text(
            "conditions:\n  - id: c1\n    fact: porteur_siege_grand_est\n", encoding="utf-8"
        )
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        restants = orphelins(PENDING, self.atelier.aides_dir, autre)
        self.assertNotIn("jardin_remarquable", restants)
        self.assertNotIn("porteur_siege_grand_est", restants)
        self.assertIn("zz_fait_que_rien_ne_reference", restants)

    def test_le_banc_dessai_voit_le_vrai_catalogue(self):
        """`dossiers_catalogue` ajoute `data/aides/` dès que l'atelier est redirigé."""
        self.assertEqual(len(self.atelier.dossiers_catalogue), 2)
        self.assertIn(self.atelier.aides_dir, self.atelier.dossiers_catalogue)


class TestAuditer(BaseOntologie):
    def test_rapport_nominal(self):
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        with fake_provider(json_reply(REPONSE)):
            rapport = auditer(self.atelier, FACTS, PENDING, client())
        self.assertEqual(len(rapport.fusions), 2)
        # Une seule fusion à appliquer : la paire « distincts » n'en est pas une.
        self.assertEqual(len(rapport.a_fusionner), 1)
        self.assertEqual(rapport.a_fusionner[0].retirer, "exploitation_atelier_animal")

    def test_les_listes_calculees_ne_viennent_pas_du_modele(self):
        """Le modèle ne peut ni inventer ni omettre un orphelin : ils sont comptés ici."""
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        menteur = {**REPONSE, "orphelins": ["fait_invente"], "polarites_suspectes": ["autre"]}
        with fake_provider(json_reply(menteur)):
            rapport = auditer(self.atelier, FACTS, PENDING, client())
        self.assertNotIn("fait_invente", rapport.orphelins)
        # Référencé par l'aide du run : ce n'est pas un brouillon.
        self.assertNotIn("jardin_remarquable", rapport.orphelins)
        self.assertIn("zz_fait_que_rien_ne_reference", rapport.orphelins)
        self.assertEqual(rapport.polarites_suspectes, [])

    def test_panne_du_modele_donne_un_rapport_degrade(self):
        with fake_provider(chat_reply("ceci n'est pas du JSON")):
            rapport = auditer(self.atelier, FACTS, PENDING, client())
        self.assertEqual(rapport.fusions, [])
        self.assertIn("indisponible", rapport.degrade)
        # Les paires restent nommées : la panne ne doit pas perdre le travail
        # du pré-filtre, qui lui n'a rien coûté.
        self.assertIn("exploitation_atelier_animal", rapport.degrade)

    def test_sans_client_le_prefiltre_tourne_quand_meme(self):
        """`--sans-audit` : aucun appel, mais les listes déterministes restent dues."""
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        rapport = auditer(self.atelier, FACTS, PENDING, None)
        self.assertEqual(rapport.fusions, [])
        self.assertIn("désactivé", rapport.degrade)
        self.assertTrue(rapport.orphelins)

    def test_aucune_paire_aucun_appel(self):
        seul = {"jardin_remarquable": PENDING["jardin_remarquable"]}
        with fake_provider(json_reply(REPONSE)) as faux:
            rapport = auditer(self.atelier, FACTS, seul, client())
        self.assertEqual(faux.bodies, [])
        self.assertIn("Aucune paire", rapport.commentaire)

    def test_le_compteur_est_alimente(self):
        from pipeline.llm import Compteur

        compteur = Compteur()
        with fake_provider(json_reply(REPONSE)):
            auditer(self.atelier, FACTS, PENDING, client(), compteur=compteur)
        self.assertGreaterEqual(compteur.appels, 1)
        self.assertIn("audit_ontologie", compteur.par_etiquette())

    def test_le_compteur_est_alimente_meme_en_panne(self):
        """Une réponse ratée se paie quand même : la compter APRÈS le test d'échec la perdrait."""
        from pipeline.llm import Compteur

        compteur = Compteur()
        with fake_provider(chat_reply("pas du JSON")):
            auditer(self.atelier, FACTS, PENDING, client(), compteur=compteur)
        self.assertGreaterEqual(compteur.appels, 1)

    def test_aucun_fichier_nest_modifie(self):
        self.ecrire_aide("ex-aide", "jardin_remarquable")
        avant = {p: p.read_bytes() for p in Path(self._tmp.name).rglob("*") if p.is_file()}
        with fake_provider(json_reply(REPONSE)):
            auditer(self.atelier, FACTS, PENDING, client())
        apres = {p: p.read_bytes() for p in Path(self._tmp.name).rglob("*") if p.is_file()}
        self.assertEqual(avant, apres)


class TestPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = construire_prompt(paires_suspectes(FACTS, PENDING), FACTS, PENDING)

    def test_distingue_approuve_et_propose(self):
        """Le modèle doit savoir lequel garder à égalité : celui déjà arbitré."""
        self.assertIn("structure_siege_grand_est  [approuvé]", self.prompt)
        self.assertIn("porteur_siege_grand_est  [proposé]", self.prompt)

    def test_porte_la_question_le_type_et_le_scope(self):
        self.assertIn("Détenez-vous des animaux d'élevage ?", self.prompt)
        self.assertIn("scope=proprietaire", self.prompt)

    def test_donne_les_deux_contre_exemples_mesures(self):
        """Les deux bornes du chevauchement, sans quoi le modèle suit le score."""
        self.assertIn("89 %", self.prompt)
        self.assertIn("9 %", self.prompt)

    def test_dit_quil_ny_a_pas_doutil(self):
        self.assertIn("ni outil ni accès au système de fichiers", self.prompt)


class TestRendu(unittest.TestCase):
    def test_dit_que_rien_nest_applique(self):
        rendu = rendre(RapportOntologie())
        self.assertIn("aucun fichier n'a été modifié", rendu)
        self.assertIn("à la main", rendu)

    def test_la_polarite_inversee_est_signalee_a_part(self):
        rapport = RapportOntologie(
            fusions=[
                Fusion(
                    garder="chauffage_sans_fioul_apres_travaux",
                    retirer="chauffage_fioul_apres_travaux",
                    verdict="polarite_inversee",
                    motif="Même critère, polarité opposée.",
                    prudence="Inverser le prédicat des aides du fait retiré.",
                )
            ]
        )
        rendu = rendre(rapport)
        self.assertIn("POLARITÉ INVERSÉE", rendu)
        self.assertIn("Inverser le prédicat", rendu)

    def test_les_distincts_ne_sont_pas_rendus_comme_des_fusions(self):
        rapport = RapportOntologie(
            fusions=[Fusion(garder="a", retirer="b", verdict="distincts", motif="Deux régions.")]
        )
        self.assertIn("Aucune fusion à proposer", rendre(rapport))

    def test_le_mode_degrade_se_lit(self):
        self.assertIn("⚠", rendre(RapportOntologie(degrade="Auditeur indisponible : timeout")))


if __name__ == "__main__":
    unittest.main()

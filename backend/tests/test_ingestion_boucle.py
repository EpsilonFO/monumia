"""Tests de la boucle d'agent (scripts/ingestion/boucle.py).

Aucun appel réseau : le fournisseur est remplacé par `providall.testing.
fake_provider`, qui rejoue des réponses fixées tout en gardant le vrai
`build()`/`parse()` — les corps envoyés sont donc les vrais.

Ce qui est vérifié : les quatre raisons de s'arrêter (fini, sans review,
budget, plafond de tours), l'élagage, et la troncature. Autrement dit, tout ce
qui empêche un run de coûter dix fois son budget ou de rendre la main sans
livrable.

Run from backend/:  uv run pytest tests/test_ingestion_boucle.py
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providall  # noqa: E402
from ingestion.boucle import (  # noqa: E402
    OUTILS_INELAGUABLES,
    TALON,
    JournalMuet,
    Limites,
    elaguer,
    executer,
    tronquer,
)
from pipeline.llm import Compteur  # noqa: E402
from providall import Message  # noqa: E402
from providall.testing import chat_reply, fake_provider, tool_call  # noqa: E402

MODELE = "ds-flash"


def client() -> providall.Client:
    return providall.Client(MODELE, api_key="faux", retry=providall.RetryPolicy(retries=0))


class Atelier:
    """Un jeu d'outils minimal : deux fonctions, dont une qui « écrit » la review."""

    def __init__(self, sortie_longue: bool = False) -> None:
        self.review = False
        self.appels: list[str] = []
        self.sortie_longue = sortie_longue

    def outils(self) -> list[providall.Tool]:
        def lire_snapshot(chemin: str = "x.md") -> str:
            """Lit un snapshot."""
            self.appels.append("lire_snapshot")
            return ("ligne de règlement. " * 500) if self.sortie_longue else "contenu"

        def ecrire_review(markdown: str = "") -> str:
            """Écrit la fiche de review."""
            self.appels.append("ecrire_review")
            self.review = True
            return "Fiche écrite."

        def casser() -> str:
            """Lève systématiquement."""
            raise RuntimeError("boum")

        return [providall.tool(f) for f in (lire_snapshot, ecrire_review, casser)]


class TestArrets(unittest.TestCase):
    def test_trois_tours_puis_termine(self):
        atelier = Atelier()
        reponses = [
            chat_reply(tool_calls=[tool_call("lire_snapshot", {"chemin": "a.md"})]),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## Fiche"})]),
            chat_reply("Ingestion terminée."),
        ]
        with fake_provider(*reponses):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "termine")
        self.assertEqual(resultat.tours, 3)
        self.assertEqual(atelier.appels, ["lire_snapshot", "ecrire_review"])

    def test_sans_review_relance_deux_fois_puis_abandonne(self):
        atelier = Atelier()
        journal = JournalMuet()
        with fake_provider(chat_reply("j'ai fini")):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(max_relances=2),
                journal=journal,
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "sans_review")
        relances = [e for e in journal.evenements if re.search(r"relance \d+/", e)]
        self.assertEqual(len(relances), 2)
        # Les relances sont bien parties dans la conversation.
        self.assertEqual(
            sum(
                1
                for m in resultat.messages
                if m.role == "user" and "ecrire_review" in (m.text or "")
            ),
            2,
        )

    def test_relance_suivie_deffet(self):
        atelier = Atelier()
        with fake_provider(
            chat_reply("j'ai fini"),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## Fiche"})]),
            chat_reply("voilà"),
        ):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "termine")

    def test_plafond_de_tours(self):
        atelier = Atelier()
        with fake_provider(chat_reply(tool_calls=[tool_call("lire_snapshot", {})])):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(max_tours=4),
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "max_tours")
        self.assertEqual(resultat.tours, 4)

    def test_sortie_epuisee_rejoue_le_tour_avec_deux_fois_plus_de_jetons(self):
        """or-glm, 2026-09-09 : 32 000 jetons de sortie partis en raisonnement, réponse vide.

        Élaguer le contexte n'y change rien. On rejoue le même tour avec deux
        fois plus de jetons de sortie, une seule fois, et on garde ce réglage
        pour le reste du run.
        """
        atelier = Atelier()
        vide = providall.EmptyResponseError(
            "contenu vide — budget de sortie épuisé avant la réponse (32000 jetons), "
            "modèle à raisonnement : augmenter max_tokens",
            finish_reason="length",
            provider="openrouter",
        )
        with fake_provider(vide, chat_reply("fini")) as faux:
            resultat = executer(client(), "SYS", "commence", atelier.outils())
        self.assertEqual(resultat.arret, "termine")
        self.assertEqual(faux.calls, 2)
        premier = faux.bodies[0]["max_tokens"]
        self.assertEqual(faux.bodies[1]["max_tokens"], min(premier * 2, 128_000))
        self.assertGreater(faux.bodies[1]["max_tokens"], premier)

    def test_sortie_epuisee_deux_fois_de_suite_est_une_erreur_modele(self):
        atelier = Atelier()
        vide = providall.EmptyResponseError(
            "contenu vide — budget de sortie épuisé avant la réponse (32000 jetons)",
            finish_reason="length",
            provider="openrouter",
        )
        with fake_provider(vide) as faux:
            resultat = executer(client(), "SYS", "commence", atelier.outils())
        self.assertEqual(resultat.arret, "erreur_modele")
        # un sauvetage par manque de sortie, puis l'élagage n'a rien à retirer : on rend la main
        self.assertLessEqual(faux.calls, 3)

    def test_boucle_dappels_identiques_arretee_bien_avant_le_plafond(self):
        """2026-09-09 : 95 tours à relire les mêmes lignes, 12 centimes, deux heures."""
        atelier = Atelier()
        with fake_provider(chat_reply(tool_calls=[tool_call("lire_snapshot", {"chemin": "x.md"})])):
            resultat = executer(
                client(), "SYS", "commence", atelier.outils(), review_ecrite=lambda: atelier.review
            )
        self.assertEqual(resultat.arret, "boucle")
        self.assertEqual(resultat.tours, Limites.appels_identiques_max)
        self.assertIn("rejoué", resultat.motif)
        rappels = [
            m for m in resultat.messages if m.role == "user" and "même appel" in str(m.content)
        ]
        self.assertEqual(len(rappels), 1)

    def test_tours_sans_progres_arretes(self):
        """Des appels tous différents, mais jamais rien qui fasse avancer l'ingestion."""
        atelier = Atelier()
        limites = Limites(
            tours_sans_progres_avertir=4, tours_sans_progres_max=6, appels_identiques_max=10**6
        )
        reponses = [
            chat_reply(tool_calls=[tool_call("lire_snapshot", {"chemin": f"{i}.md"})])
            for i in range(20)
        ]
        with fake_provider(*reponses):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=limites,
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "boucle")
        self.assertEqual(resultat.tours, 6)
        self.assertIn("sans", resultat.motif)

    def test_erreur_transitoire_rejouee_une_fois(self):
        atelier = Atelier()
        transitoire = providall.EmptyResponseError(
            "contenu vide — finish_reason='error' (7646 jetons de sortie facturés)",
            finish_reason="error",
            retryable=True,
            provider="openrouter",
        )
        with fake_provider(transitoire, chat_reply("fini")) as faux:
            resultat = executer(
                client(), "SYS", "commence", atelier.outils(), limites=Limites(pause_relance_s=0.0)
            )
        self.assertEqual(resultat.arret, "termine")
        self.assertEqual(faux.calls, 2)

    def test_erreur_modele_sans_rien_a_elaguer(self):
        atelier = Atelier()
        with fake_provider(providall.ServerError("502", provider="deepseek")):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(pause_relance_s=0.0),
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "erreur_modele")
        self.assertIn("ServerError", resultat.motif)


class TestBudget(unittest.TestCase):
    """Deux chemins, à ne pas confondre.

    `ds-flash` est TARIFÉ au registre providall : c'est le budget en dollars qui
    s'applique. Un modèle hors registre (`zai:glm-5.3-flash`) n'a pas de tarif,
    `cost_usd` y vaut None, et c'est le plafond en jetons d'entrée qui prend le
    relais — exactement la situation de `glm-flash` tant que son tarif n'est pas
    renseigné.
    """

    def test_arret_dur_au_dela_de_125_pourcent(self):
        atelier = Atelier()
        journal = JournalMuet()
        # 10 M jetons d'entrée à 0,28 $/M ≈ 2,80 $, soit 1,9× le budget de 1,50 $.
        with fake_provider(
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})], prompt_tokens=10_000_000)
        ):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(budget_usd=1.5, max_tours=10),
                journal=journal,
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "budget")
        self.assertTrue(any("arrêt dur" in e for e in journal.evenements))

    def test_avertissement_laisse_le_temps_decrire_la_review(self):
        atelier = Atelier()
        # 6 M jetons ≈ 1,68 $ : au-dessus du budget de 1,50 $, sous le seuil dur.
        with fake_provider(
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})], prompt_tokens=6_000_000),
            chat_reply(
                tool_calls=[tool_call("ecrire_review", {"markdown": "## x"})], prompt_tokens=1
            ),
            chat_reply("fini", prompt_tokens=1),
        ):
            resultat = executer(
                client(),
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(budget_usd=1.5),
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "termine")
        self.assertTrue(
            any("BUDGET ÉPUISÉ" in (m.text or "") for m in resultat.messages if m.role == "user")
        )

    def test_tarif_inconnu_bascule_sur_les_jetons(self):
        atelier = Atelier()
        journal = JournalMuet()
        sans_tarif = providall.Client(
            "zai:glm-5.3-flash", api_key="faux", retry=providall.RetryPolicy(retries=0)
        )
        with fake_provider(
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})], prompt_tokens=10_000_000)
        ):
            resultat = executer(
                sans_tarif,
                "SYS",
                "commence",
                atelier.outils(),
                limites=Limites(budget_usd=1.5, budget_tokens_entree=6_000_000, max_tours=10),
                journal=journal,
                review_ecrite=lambda: atelier.review,
            )
        self.assertEqual(resultat.arret, "budget")
        self.assertTrue(resultat.cout_inconnu)
        self.assertIn("jetons", next(e for e in journal.evenements if "arrêt dur" in e))

    def test_le_compteur_recoit_chaque_appel(self):
        atelier = Atelier()
        compteur = Compteur()
        with fake_provider(chat_reply("fini")):
            executer(
                client(),
                "SYS",
                "go",
                atelier.outils(),
                compteur=compteur,
                review_ecrite=lambda: True,
            )
        self.assertEqual(compteur.appels, 1)


class TestOutilsEnEchec(unittest.TestCase):
    def test_une_exception_doutil_est_rendue_au_modele(self):
        atelier = Atelier()
        with fake_provider(
            chat_reply(tool_calls=[tool_call("casser", {})]),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## x"})]),
            chat_reply("fini"),
        ):
            resultat = executer(
                client(), "SYS", "go", atelier.outils(), review_ecrite=lambda: atelier.review
            )
        self.assertEqual(resultat.arret, "termine")
        sorties = [m.content for m in resultat.messages if m.role == "tool"]
        self.assertTrue(any("ERREUR : RuntimeError: boum" in (s or "") for s in sorties))

    def test_outil_inconnu(self):
        atelier = Atelier()
        with fake_provider(
            chat_reply(tool_calls=[tool_call("zorglub", {})]),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## x"})]),
            chat_reply("fini"),
        ):
            resultat = executer(
                client(), "SYS", "go", atelier.outils(), review_ecrite=lambda: atelier.review
            )
        sorties = [m.content for m in resultat.messages if m.role == "tool"]
        self.assertTrue(any("outil inconnu" in (s or "") for s in sorties))


class TestTroncature(unittest.TestCase):
    def test_sortie_tronquee_et_annoncee(self):
        court = tronquer("abc", 10)
        self.assertEqual(court, "abc")
        long = tronquer("x" * 100, 10)
        self.assertTrue(long.startswith("x" * 10))
        self.assertIn("tronquée", long)
        self.assertIn("90", long)

    def test_appliquee_par_la_boucle(self):
        atelier = Atelier(sortie_longue=True)
        with fake_provider(
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})]),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## x"})]),
            chat_reply("fini"),
        ):
            resultat = executer(
                client(),
                "SYS",
                "go",
                atelier.outils(),
                limites=Limites(max_car_sortie=200),
                review_ecrite=lambda: atelier.review,
            )
        sortie = next(m.content for m in resultat.messages if m.role == "tool")
        self.assertLess(len(sortie or ""), 500)


class TestElagage(unittest.TestCase):
    def conversation(self) -> list[Message]:
        return [
            Message(role="system", content="SYS"),
            Message(role="user", content="go"),
            *[
                Message(role="tool", tool_call_id=f"c{i}", name="lire_snapshot", content="x" * 5000)
                for i in range(12)
            ],
            Message(role="assistant", content="réflexion à ne pas toucher"),
            Message(role="tool", tool_call_id="lint", name="lint", content="y" * 5000),
        ]

    def test_garde_les_dernieres_et_les_ineleguables(self):
        conv = self.conversation()
        gagne = elaguer(conv, garder=3)
        self.assertGreater(gagne, 0)
        talons = [m for m in conv if m.content == TALON]
        self.assertEqual(len(talons), 9)
        # Les trois dernières lectures sont intactes…
        lectures = [m for m in conv if m.name == "lire_snapshot" and m.content != TALON]
        self.assertEqual(len(lectures), 3)
        # …le lint aussi, et le message de l'assistant n'a pas bougé.
        lint = next(m for m in conv if m.name == "lint")
        self.assertEqual(len(lint.content or ""), 5000)
        self.assertIn("lint", OUTILS_INELAGUABLES)
        self.assertEqual(conv[-2].content, "réflexion à ne pas toucher")

    def test_les_petites_sorties_sont_laissees(self):
        conv = [
            Message(role="tool", tool_call_id="a", name="lire_snapshot", content="court")
            for _ in range(5)
        ]
        self.assertEqual(elaguer(conv, garder=0), 0)

    def test_declenche_par_le_seuil_de_contexte(self):
        atelier = Atelier(sortie_longue=True)
        journal = JournalMuet()
        with fake_provider(
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})], prompt_tokens=200_000),
            chat_reply(tool_calls=[tool_call("lire_snapshot", {})], prompt_tokens=200_000),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": "## x"})]),
            chat_reply("fini"),
        ):
            executer(
                client(),
                "SYS",
                "go",
                atelier.outils(),
                limites=Limites(seuil_elagage_tokens=110_000, garder_sorties=0, budget_usd=1000.0),
                journal=journal,
                review_ecrite=lambda: atelier.review,
            )
        self.assertTrue(any("élagage" in e for e in journal.evenements), journal.evenements)


if __name__ == "__main__":
    unittest.main()

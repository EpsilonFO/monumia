"""Tests des outils de l'agent d'ingestion (scripts/ingestion/outils.py).

Ce qui compte ici, c'est ce que les outils REFUSENT : un YAML invalide qui
n'écrase rien, un slug qui n'est pas le sien, un chemin qui sort du dossier de
l'aide, une review-moignon. Un modèle faible fera ces erreurs, et c'est le
harnais — pas sa bonne volonté — qui doit les arrêter.

Aucun test ne touche au réseau (`httpx.MockTransport`) ni à `backend/data/`
(atelier redirigé dans un tmpdir).

Run from backend/:  uv run pytest tests/test_ingestion_outils.py
"""

import dataclasses
import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_collect  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402
from ingestion.outils import outils_pour, passage_le_plus_proche  # noqa: E402
from pipeline.web import Fetcheur, reinitialiser_delais  # noqa: E402

from aides_schema import FactDef, load_facts, load_pending_facts  # noqa: E402

JOUR = date(2026, 9, 6)

PAGE = """\
<html><body>
<h1>Jardins en scène</h1>
<p>La Région soutient les programmations artistiques accueillies dans des écrins
paysagers et patrimoniaux. La programmation doit se dérouler dans un parc ou un
jardin ouvert au public.</p>
<p>L'aide est plafonnée à 10 000 euros par structure. Elle peut être portée à
20 000 euros pour une programmation valorisant au moins trois espaces paysagers,
dont un situé en territoire à enjeux.</p>
<p>Les bénéficiaires sont les associations, les collectivités locales, les
établissements publics de coopération intercommunale et les établissements
publics de coopération culturelle. La gratuité de l'accès du public figure
parmi les critères de sélection retenus par le jury régional.</p>
</body></html>
"""

FACTS_YAML = """\
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?
surface_jardin_m2:
  type: integer
  scope: monument
  question: Quelle est la surface du jardin ?
  unit: m²
"""


def aide_yaml(quote: str, *, slug: str = "ex-aide", snapshot: str = "", jour: date = JOUR) -> str:
    return f"""\
slug: {slug}
nom: Aide d'exemple
nom_court: Exemple
organisme: Région d'exemple
categorie: region
type: subvention
description: Une aide pour tester les outils.
source:
  url_officielle: https://example.org/aide
  verified_at: {jour.isoformat()}
  snapshot: {snapshot}
conditions:
  - id: ouvert-au-public
    text: La programmation se déroule dans un jardin ouvert au public.
    kind: user_fact
    effect: gate
    fact: monument_ouvert_au_public
    predicate: {{eq: true}}
    quote: {quote}
"""


class BaseOutils(unittest.TestCase):
    def setUp(self):
        reinitialiser_delais()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        # Ontologie factice : les outils et le `lint` qu'ils appellent doivent
        # lire LA MÊME, sinon le test mesure un désaccord qu'il a lui-même créé.
        facts_path = self.racine / "facts.yaml"
        facts_path.write_text(FACTS_YAML, encoding="utf-8")
        self.atelier = dataclasses.replace(
            atelier_redirige("ex-aide", self.racine, jour=JOUR), facts_path=facts_path
        )
        veille_collect.pdf_to_text.cache_clear()
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        self.facts = load_facts(facts_path)
        self.pending: dict[str, FactDef] = {}
        self.fetcheur = Fetcheur(transport=httpx.MockTransport(self.repondre), delai_s=0.0)
        self.addCleanup(self.fetcheur.close)
        self.outils, self.etat = outils_pour(
            self.atelier,
            facts=dict(self.facts),
            pending=self.pending,
            fetcheur=self.fetcheur,
        )
        self.table = {o.name: o for o in self.outils}

    def repondre(self, request: httpx.Request) -> httpx.Response:
        chemin = request.url.path
        if chemin.endswith(".pdf"):
            return httpx.Response(
                200, content=self.pdf_bytes(), headers={"content-type": "application/pdf"}
            )
        if chemin == "/vide":
            return httpx.Response(
                200,
                text="<html><body><div id=app></div></body></html>",
                headers={"content-type": "text/html"},
            )
        if chemin == "/absent":
            return httpx.Response(404, text="rien ici")
        if chemin.endswith(".docx"):
            return httpx.Response(
                200,
                content=self.docx_bytes(),
                headers={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                },
            )
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})

    def docx_bytes(self) -> bytes:
        """Un .docx authentique : un ZIP portant `word/document.xml`."""
        ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        corps = (
            "<w:p><w:r><w:t>Le demandeur ne doit pas être un établissement "
            "labellisé par l'État.</w:t></w:r></w:p>"
        )
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr(
                "word/document.xml", f"<w:document {ns}><w:body>{corps}</w:body></w:document>"
            )
        return tampon.getvalue()

    def pdf_bytes(self) -> bytes:
        return b"%PDF-1.4\n% faux pdf"

    def appeler(self, nom: str, **kw):
        return self.table[nom].run(kw)


class TestSnapshotEtLecture(BaseOutils):
    def test_snapshotter_puis_lire(self):
        sortie = self.appeler("snapshotter", url="https://example.org/aide")
        self.assertIn("Archivé", sortie)
        self.assertEqual(len(self.atelier.snapshots()), 1)
        lecture = self.appeler("lire_snapshot", chemin=self.atelier.snapshots()[0].name)
        self.assertIn("Jardins en scène", lecture)
        self.assertIn("|", lecture)

    def test_snapshotter_une_page_vide_previent(self):
        sortie = self.appeler("snapshotter", url="https://example.org/vide")
        self.assertIn("SPA", sortie)

    def test_snapshotter_un_docx_le_rend_citable(self):
        """Les règlements d'intervention régionaux sont souvent des .docx.

        Sans conversion, l'archive contenait le ZIP brut : le modèle lisait
        « PK...[Content_Types].xml » et ne pouvait rien en citer. Mesuré sur
        hdf-jardins-en-scene le 2026-09-06 — l'exigence décisive
        `exclusion-etablissement-labellise-etat` était hors de portée, et on
        l'a d'abord imputée au modèle.
        """
        sortie = self.appeler(
            "snapshotter", url="https://example.org/reglement.docx", label="reglement"
        )
        self.assertIn("Archivé", sortie)
        self.assertIn(".docx converti", sortie)
        archive = next(p for p in self.atelier.snapshots() if "reglement" in p.name)
        corps = archive.read_text(encoding="utf-8")
        self.assertIn("établissement labellisé par l'État", corps)
        self.assertNotIn("Content_Types", corps)
        # Et la citation doit se retrouver dans le snapshot pour le lint.
        lecture = self.appeler("chercher_dans_snapshot", motif="labellisé")
        self.assertIn("labellisé", lecture)

    def test_snapshotter_une_page_absente_echoue_sans_ecrire(self):
        sortie = self.appeler("snapshotter", url="https://example.org/absent")
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertEqual(self.atelier.snapshots(), [])

    def test_lire_snapshot_refuse_un_chemin_hors_dossier(self):
        sortie = self.appeler("lire_snapshot", chemin="../../../.env")
        self.assertTrue(sortie.startswith("ERREUR"), sortie)
        self.assertIn("hors du dossier", sortie)

    def test_lire_snapshot_borne_le_nombre_de_lignes(self):
        self.appeler("snapshotter", url="https://example.org/aide")
        nom = self.atelier.snapshots()[0].name
        sortie = self.appeler("lire_snapshot", chemin=nom, offset=0, limit=99999)
        self.assertIn("lignes 0-", sortie)

    def test_lister_snapshots_donne_la_provenance(self):
        self.appeler("snapshotter", url="https://example.org/aide")
        sortie = self.appeler("lister_snapshots")
        self.assertIn("https://example.org/aide", sortie)

    def test_chercher_dans_snapshot(self):
        self.appeler("snapshotter", url="https://example.org/aide")
        sortie = self.appeler("chercher_dans_snapshot", motif="plafonnée")
        self.assertIn("10 000 euros", sortie)
        self.assertIn("Aucune ligne", self.appeler("chercher_dans_snapshot", motif="zorglub"))

    def test_explorer_url_annonce_quil_nest_pas_citable(self):
        sortie = self.appeler("explorer_url", url="https://example.org/aide")
        self.assertIn("NON CITABLE", sortie)
        self.assertEqual(self.atelier.snapshots(), [])


@unittest.skipUnless(shutil.which("pdftotext"), "pdftotext absent")
class TestPdf(BaseOutils):
    def pdf_bytes(self) -> bytes:
        # Un vrai PDF minimal, mais dont le texte extrait sera plus court que
        # PDF_MIN_TEXT : c'est exactement le cas « scan » qu'on veut voir signalé.
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n"
        )

    def test_pdf_illisible_est_signale(self):
        sortie = self.appeler("snapshotter", url="https://example.org/reglement.pdf")
        self.assertIn("scan", sortie.lower())


class TestEcrireAide(BaseOutils):
    def snapshoter(self) -> str:
        self.appeler("snapshotter", url="https://example.org/aide")
        return self.atelier.relatif(self.atelier.snapshots()[0])

    def test_yaml_invalide_necrase_rien(self):
        chemin = self.snapshoter()
        self.appeler("ecrire_aide", yaml_texte=aide_yaml("ouvert au public", snapshot=chemin))
        avant = self.atelier.yaml_path.read_text(encoding="utf-8")
        sortie = self.appeler("ecrire_aide", yaml_texte="slug: [ceci n'est pas: du yaml")
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertEqual(self.atelier.yaml_path.read_text(encoding="utf-8"), avant)

    def test_champ_hors_schema_refuse(self):
        sortie = self.appeler(
            "ecrire_aide", yaml_texte=aide_yaml("ouvert au public") + "champ_invente: 3\n"
        )
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertFalse(self.atelier.yaml_path.exists())

    def test_slug_divergent_refuse(self):
        sortie = self.appeler(
            "ecrire_aide", yaml_texte=aide_yaml("ouvert au public", slug="autre-aide")
        )
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertIn("autre-aide", sortie)
        self.assertFalse(self.atelier.yaml_path.exists())

    def test_quote_exacte_validee(self):
        chemin = self.snapshoter()
        sortie = self.appeler(
            "ecrire_aide",
            yaml_texte=aide_yaml(
                "se dérouler dans un parc ou un jardin ouvert au public", snapshot=chemin
            ),
        )
        self.assertIn("1/1 retrouvées", sortie)
        self.assertNotIn("INTROUVABLE", sortie)

    def test_quote_inventee_signalee_avec_le_texte_le_plus_proche(self):
        chemin = self.snapshoter()
        sortie = self.appeler(
            "ecrire_aide",
            yaml_texte=aide_yaml(
                "se dérouler dans un parc ou un jardin ouvert aux scolaires", snapshot=chemin
            ),
        )
        self.assertIn("INTROUVABLE", sortie)
        self.assertIn("texte le plus proche", sortie)
        self.assertIn("ouvert au public", sortie)

    def test_snapshot_absent_du_yaml_signale(self):
        self.snapshoter()
        sortie = self.appeler("ecrire_aide", yaml_texte=aide_yaml("ouvert au public"))
        self.assertIn("`source.snapshot` est vide", sortie)

    def test_date_de_verification_erronee_signalee(self):
        chemin = self.snapshoter()
        sortie = self.appeler(
            "ecrire_aide",
            yaml_texte=aide_yaml("ouvert au public", snapshot=chemin, jour=date(2020, 1, 1)),
        )
        self.assertIn("verified_at", sortie)


class TestLintEtReview(BaseOutils):
    def test_lint_avant_ecriture(self):
        self.assertIn("ERREUR", self.appeler("lint"))

    def test_lint_dune_aide_correcte(self):
        self.appeler("snapshotter", url="https://example.org/aide")
        chemin = self.atelier.relatif(self.atelier.snapshots()[0])
        self.appeler(
            "ecrire_aide",
            yaml_texte=aide_yaml(
                "se dérouler dans un parc ou un jardin ouvert au public", snapshot=chemin
            ),
        )
        sortie = self.appeler("lint")
        self.assertIn("lint OK", sortie)
        self.assertTrue(self.etat.dernier_lint_ok)

    def test_review_trop_courte_refusee(self):
        sortie = self.appeler("ecrire_review", markdown="## Trop court")
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertFalse(self.etat.review_ecrite)

    def test_review_sans_section_refusee(self):
        sortie = self.appeler("ecrire_review", markdown="x" * 900)
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertFalse(self.etat.review_ecrite)

    def test_review_refusee_si_aide_modifiee_depuis_verification(self):
        """Une fiche ne peut pas conclure sur un rapport de vérification périmé.

        Mesuré le 2026-09-07 : les trois fiches Grand Est annonçaient « tous
        traités » quand une relecture indépendante des fichiers finaux relevait
        encore 9 bloquants. L'agent notait sa propre copie.
        """
        self.appeler("snapshotter", url="https://example.org/aide")
        chemin = self.atelier.relatif(self.atelier.snapshots()[0])
        yaml_texte = aide_yaml(
            "se dérouler dans un parc ou un jardin ouvert au public", snapshot=chemin
        )
        self.appeler("ecrire_aide", yaml_texte=yaml_texte)
        texte = "## Conditions\n\n" + ("Une ligne de fiche de review. " * 40)

        # Sans vérification au dossier, rien à périmer : la fiche passe.
        self.assertIn("Fiche écrite", self.appeler("ecrire_review", markdown=texte))

        # Une vérification a eu lieu, puis l'aide a changé : la fiche est refusée.
        self.etat.verification = object()  # type: ignore[assignment]
        self.appeler("ecrire_aide", yaml_texte=yaml_texte)
        self.assertTrue(self.etat.modifiee_depuis_verification)
        sortie = self.appeler("ecrire_review", markdown=texte)
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertIn("verification_adversariale", sortie)

    def test_review_refusee_si_verificateur_configure_mais_jamais_appele(self):
        """Avec un vérificateur au dossier, pas de fiche sans au moins une vérification.

        Rien ne l'imposait : un agent pouvait écrire l'aide, linter, rédiger la
        fiche et terminer avec « 0 bloquant » sans que le vérificateur ait vu le
        fichier. Le compteur du bilan aurait alors été vide, pas rassurant.
        """
        outils, etat = outils_pour(
            self.atelier,
            facts=dict(self.facts),
            pending=self.pending,
            fetcheur=self.fetcheur,
            client_verif=object(),  # type: ignore[arg-type]  — jamais appelé ici
        )
        table = {o.name: o for o in outils}
        texte = "## Conditions\n\n" + ("Une ligne de fiche de review. " * 40)

        sortie = table["ecrire_review"].run({"markdown": texte})
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertIn("verification_adversariale", sortie)
        self.assertFalse(etat.review_ecrite)

        etat.verification = object()  # type: ignore[assignment]
        self.assertIn("Fiche écrite", table["ecrire_review"].run({"markdown": texte}))
        self.assertTrue(etat.review_ecrite)

    def test_review_valide_ecrite_avec_entete(self):
        texte = "## Conditions\n\n" + ("Une ligne de fiche de review. " * 40)
        sortie = self.appeler("ecrire_review", markdown=texte)
        self.assertIn("Fiche écrite", sortie)
        self.assertTrue(self.etat.review_ecrite)
        contenu = self.atelier.review_path.read_text(encoding="utf-8")
        self.assertIn("<!--", contenu)
        self.assertIn("## Conditions", contenu)


class TestFaits(BaseOutils):
    def test_chercher_puis_detailler(self):
        sortie = self.appeler("chercher_faits", mots="jardin surface")
        self.assertIn("surface_jardin_m2", sortie)
        self.assertIn("integer", self.appeler("detail_fait", fact_id="surface_jardin_m2"))
        self.assertIn("Fait inconnu", self.appeler("detail_fait", fact_id="zorglub"))

    def test_scope_filtre(self):
        self.assertIn(
            "Aucun fait", self.appeler("chercher_faits", mots="jardin", scope="proprietaire")
        )

    def test_proposer_puis_retirer(self):
        """L'aller-retour complet : l'ontologie n'est plus en ajout seul."""
        justif = (
            "Aucun fait existant ne porte le label « Jardin remarquable » : "
            "`monument_ouvert_au_public` ne dit rien du label et `surface_jardin_m2` mesure "
            "une surface, pas une distinction. Le règlement en fait un critère de bonification."
        )
        ajout = self.appeler(
            "proposer_fait",
            fact_id="jardin_remarquable",
            definition_yaml=(
                "type: boolean\nscope: monument\n"
                "question: Le jardin est-il labellisé « Jardin remarquable » ?\n"
            ),
            justification=justif,
        )
        self.assertNotIn("ERREUR", ajout)
        self.assertEqual(self.etat.faits_proposes, ["jardin_remarquable"])
        self.assertIn("jardin_remarquable", self.pending)

        retrait = self.appeler(
            "retirer_fait", fact_id="jardin_remarquable", motif="doublon de surface_jardin_m2"
        )
        self.assertNotIn("ERREUR", retrait)
        # L'état du run ET l'ontologie partagée entre workers suivent le retrait,
        # sans quoi les voisins continueraient de voir un fait effacé.
        self.assertEqual(self.etat.faits_proposes, [])
        self.assertNotIn("jardin_remarquable", self.pending)

    def test_retirer_un_fait_dun_autre_run_refuse(self):
        """La garde qui empêche un worker d'effacer le fait d'un autre."""
        self.atelier.pending_path.write_text(
            "fait_dailleurs:\n  type: boolean\n  scope: monument\n  question: Ailleurs ?\n",
            encoding="utf-8",
        )
        load_pending_facts.cache_clear()
        sortie = self.appeler("retirer_fait", fact_id="fait_dailleurs", motif="je le crois inutile")
        self.assertIn("ERREUR", sortie)
        self.assertIn("fait_dailleurs", load_pending_facts(self.atelier.pending_path))


class TestPassagePlusProche(unittest.TestCase):
    def test_rien_quand_le_document_na_aucun_rapport(self):
        documents = [("a.md", "Le chat dort sur le canapé du salon depuis midi.", "text")]
        self.assertIsNone(
            passage_le_plus_proche("le taux d'intervention est de 80 % des dépenses", documents)
        )

    def test_retrouve_la_ligne_divergente_et_rend_le_texte_brut(self):
        documents = [("a.md", "Le taux d'intervention est de 30 % des dépenses éligibles.", "text")]
        proche = passage_le_plus_proche(
            "Le taux d'intervention est de 80 % des dépenses éligibles.", documents
        )
        self.assertIsNotNone(proche)
        self.assertIn("30 %", proche or "")
        # Texte brut, pas la forme normalisée : sinon le modèle recopierait une
        # citation désaccentuée, donc fausse.
        self.assertIn("dépenses", proche or "")

    def test_retrouve_un_passage_a_cheval_sur_plusieurs_lignes(self):
        documents = [
            (
                "a.md",
                "La programmation doit se dérouler dans un parc ou un\n"
                "jardin ouvert au public, sans interruption.",
                "text",
            )
        ]
        proche = passage_le_plus_proche(
            "se dérouler dans un parc ou un jardin ouvert aux scolaires", documents
        )
        self.assertIsNotNone(proche)
        self.assertIn("ouvert au public", proche or "")


if __name__ == "__main__":
    unittest.main()

"""Ingestion des aides admises (incrément I7) et projection inverse vers la file. Sans réseau ni modèle."""

from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import etat  # noqa: E402
from prospection import collecte  # noqa: E402

from catalogue import ingestion as ing  # noqa: E402
from catalogue import reextraction as rx  # noqa: E402
from catalogue.journal import Evenement, Journal, Vue  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
MODELE = "77-festivals"
JOUR = dt.date(2026, 10, 11)


@pytest.fixture
def depot(tmp_path: Path) -> dict[str, Path]:
    aides = tmp_path / "aides"
    aides.mkdir()
    pending = tmp_path / "facts_pending.yaml"
    shutil.copy(BACKEND / "data" / "facts_pending.yaml", pending)
    return {"tmp": tmp_path, "aides": aides, "sources": tmp_path / "sources", "pending": pending}


def _lanceur(resultat: dict[str, Any], slug_modele: str = MODELE, fait: str | None = None) -> Any:
    def lancer(slug: str, sortie: Path, plafond: float, delai_s: float) -> rx.Lancement:
        assert ing.lire_tache(sortie) is not None
        texte = (BACKEND / "data" / "aides" / f"{slug_modele}.yaml").read_text(encoding="utf-8")
        texte = texte.replace(f"slug: {slug_modele}", f"slug: {slug}")
        if fait:
            texte = texte.replace(
                "conditions:\n",
                f"conditions:\n  - id: neuve\n    text: x\n    kind: user_fact\n    effect: gate\n    fact: {fait}\n    predicate:\n      eq: true\n    quote: x\n",
                1,
            )
            (sortie / "facts_pending.yaml").write_text(
                (BACKEND / "data" / "facts_pending.yaml").read_text(encoding="utf-8")
                + f"\n# proposé\n{fait}:\n  type: boolean\n  scope: projet\n  question: Le projet est-il neuf ?\n",
                encoding="utf-8",
            )
        (sortie / "aides" / f"{slug}.yaml").write_text(texte, encoding="utf-8")
        (sortie / "sources" / slug).mkdir(parents=True)
        (sortie / "sources" / slug / "2026-10-11.md").write_text(
            "---\nurl: https://x.fr\n---\ncorps\n", encoding="utf-8"
        )
        (sortie / "appels.jsonl").write_text('{"cout_usd": 0.1}\n', encoding="utf-8")
        return rx.Lancement(resultat, None, sortie, 1.0)

    return lancer


def _ingerer(depot: dict[str, Path], lanceur: Any, slug: str = "aide-neuve") -> ing.Bilan:
    tache = etat.Tache(
        titre="Aide neuve", url="https://x.fr/aide", territoire="test", statut="valide"
    )
    return ing.ingerer(
        slug,
        tache,
        plafond=1.0,
        delai_s=60,
        jour=JOUR,
        sorties=depot["tmp"] / "sorties",
        aides=depot["aides"],
        sources=depot["sources"],
        pending=depot["pending"],
        rebuts=depot["tmp"] / "rebuts",
        brouillons=depot["tmp"] / "brouillons",
        lanceur=lanceur,
    )


def test_une_aide_acceptee_entre_au_catalogue_avec_ses_instantanes(depot: dict[str, Path]) -> None:
    b = _ingerer(depot, _lanceur({"ok": True}))
    assert b.issue == "acceptee" and b.snapshots == ["2026-10-11.md"]
    assert (depot["aides"] / "aide-neuve.yaml").exists()
    assert [c.sorte for c in b.cases] == ["ingestion-fiche"]


def test_un_fait_neuf_va_en_fin_de_fichier_et_en_case(depot: dict[str, Path]) -> None:
    avant = depot["pending"].read_text(encoding="utf-8")
    b = _ingerer(depot, _lanceur({"ok": True}, fait="fait_tout_neuf_de_test"))
    assert b.faits == ["fait_tout_neuf_de_test"]
    apres = depot["pending"].read_text(encoding="utf-8")
    assert apres.startswith(avant) and apres.rstrip().endswith("question: Le projet est-il neuf ?")
    assert "H-fait" in [c.sorte for c in b.cases]


def test_un_allongement_du_questionnaire_met_l_aide_en_brouillon(depot: dict[str, Path]) -> None:
    b = _ingerer(depot, _lanceur({"ok": True, "cout_questions": "+3 question(s) de tronc (BFC)"}))
    assert b.issue == "brouillon"
    assert not (depot["aides"] / "aide-neuve.yaml").exists()
    assert (depot["tmp"] / "brouillons" / "aide-neuve.yaml").exists()


def test_un_slug_deja_pris_n_ecrase_jamais_l_aide_en_service(depot: dict[str, Path]) -> None:
    (depot["aides"] / "aide-neuve.yaml").write_text("slug: aide-neuve\n", encoding="utf-8")
    b = _ingerer(depot, _lanceur({"ok": True}))
    assert b.issue == "brouillon"
    assert (depot["aides"] / "aide-neuve.yaml").read_text(encoding="utf-8") == "slug: aide-neuve\n"


def test_un_refus_va_en_rebut_jamais_en_yaml_echec(depot: dict[str, Path]) -> None:
    b = _ingerer(depot, _lanceur({"ok": False, "motif_echec": "lint rouge"}))
    assert b.issue == "refusee"
    assert not list(depot["aides"].glob("*.echec"))
    assert (depot["tmp"] / "rebuts" / "aide-neuve" / f"{JOUR.isoformat()}.yaml").exists()


def test_une_panne_n_ecrit_rien(depot: dict[str, Path]) -> None:
    b = _ingerer(depot, _lanceur({"ok": True, "verification_indisponible": "429"}))
    assert (b.issue, b.panne) == ("panne", "verification")
    assert not list(depot["aides"].iterdir())


# ------------------------------------------------------------------ admises et projection


def _entree(url: str, issue: str, titre: str) -> Evenement:
    lu = {
        "titre": titre,
        "destinataire": "proprietaire_gestionnaire",
        "objet": "bien_ou_lieu",
        "famille": "restauration_bati",
    }
    return Evenement(
        "decision",
        "d:" + url[-12:].rjust(12, "0"),
        decision="entree",
        issue=issue,
        cle=f"k-{url}",
        donnees={
            "url": url,
            "territoire": "hauts-de-seine",
            "lu": lu,
            "motif": "hors périmètre" if issue == "ecartee" else "",
        },
    )


def test_seules_les_admises_non_traitees_sont_a_ingerer(tmp_path: Path) -> None:
    j = Journal(tmp_path / "journal")
    aides = tmp_path / "aides"
    aides.mkdir()
    (aides / "aide-c.yaml").write_text("slug: aide-c\n", encoding="utf-8")
    objet = lambda u: "d:" + u[-12:].rjust(12, "0")  # noqa: E731
    j.ajouter_lot(
        [
            _entree("https://x.fr/a", "admise", "Aide A"),
            _entree("https://x.fr/b", "ecartee", "Aide B"),
            _entree("https://x.fr/c", "admise", "Aide C"),
            _entree("https://x.fr/d", "admise", "Aide D"),
            Evenement(
                "decision",
                objet("https://x.fr/c"),
                decision="ingestion",
                issue="acceptee",
                donnees={"slug": "aide-c"},
            ),
            # Acceptée au journal, mais le YAML n'est jamais arrivé (recopie refusée) : elle reste due.
            Evenement(
                "decision",
                objet("https://x.fr/d"),
                decision="ingestion",
                issue="acceptee",
                donnees={"slug": "aide-d"},
            ),
        ]
    )
    admises = ing.admises_a_ingerer(Vue(list(j.lire())), aides, tmp_path / "brouillons")
    assert [a.url for a in admises] == ["https://x.fr/a", "https://x.fr/d"]


def test_la_projection_ne_reecrit_jamais_une_decision_humaine(tmp_path: Path) -> None:
    chemin = tmp_path / "file-attente.yaml"
    etat.ecrire(
        chemin,
        {
            "aide-x": etat.Tache(
                titre="X",
                url="https://x.fr/x",
                territoire="t",
                statut="ignore",
                motif_ignore="écartée à la main",
            )
        },
    )
    ing.projeter_file(
        [
            Evenement(
                "decision",
                "a:aide-x",
                decision="ingestion",
                issue="acceptee",
                donnees={"url": "https://x.fr/x", "slug": "aide-x"},
            )
        ],
        chemin,
    )
    t = etat.charger(chemin)["aide-x"]
    assert t.statut == "ignore" and t.motif_ignore == "écartée à la main"


def test_la_projection_inverse_empeche_l_ancienne_chaine_de_rejuger(tmp_path: Path) -> None:
    chemin = tmp_path / "file-attente.yaml"
    etat.ecrire(chemin, {})
    evenements = [
        _entree("https://x.fr/aide-a", "admise", "Aide A"),
        _entree("https://x.fr/aide-b", "ecartee", "Aide B"),
        _entree("https://x.fr/aide-c", "doute", "Aide C"),
    ]
    ajoutees = ing.projeter_file(evenements, chemin)
    assert len(ajoutees) == 3
    file = etat.charger(chemin)
    statuts = {t.url: t.statut for t in file.values()}
    assert statuts == {
        "https://x.fr/aide-a": "valide",
        "https://x.fr/aide-b": "ignore",
        "https://x.fr/aide-c": "a_valider",
    }
    # L'ancienne collecte ne repropose aucune de ces URL.
    candidats = [collecte.Candidat(url=u) for u in statuts]
    retenus, _, en_file = collecte.dedoublonner(candidats, {}, file)
    assert retenus == [] and len(en_file) == 3
    # Une ingestion faite par la nouvelle chaîne passe la tâche à `ingere` : l'ancienne ne la reprend pas.
    slug_a = next(s for s, t in file.items() if t.url.endswith("aide-a"))
    ing.projeter_file(
        [
            *evenements,
            Evenement(
                "decision",
                "a:" + slug_a,
                decision="ingestion",
                issue="acceptee",
                donnees={"url": "https://x.fr/aide-a", "slug": slug_a},
            ),
        ],
        chemin,
    )
    assert etat.charger(chemin)[slug_a].statut == "ingere"
    assert etat.selectionner(etat.charger(chemin)) == []
    # Relancée, la projection n'ajoute rien.
    assert ing.projeter_file(evenements, chemin) == []


def test_un_doute_admis_par_felix_garde_son_slug_de_file(tmp_path: Path) -> None:
    chemin = tmp_path / "file-attente.yaml"
    etat.ecrire(chemin, {})
    doute = _entree("https://x.fr/aide-d", "doute", "Aide D")
    ing.projeter_file([doute], chemin)
    (slug,) = etat.charger(chemin)
    assert etat.charger(chemin)[slug].statut == "a_valider"
    felix = Evenement(
        "felix", doute.objet, decision="entree-doute", auteur="felix", issue="admettre", cle="f1"
    )
    ing.projeter_file([doute, felix], chemin)
    assert etat.charger(chemin)[slug].statut == "valide"
    assert {t.url: s for s, t in etat.charger(chemin).items() if t.statut == "valide"} == {
        "https://x.fr/aide-d": slug
    }

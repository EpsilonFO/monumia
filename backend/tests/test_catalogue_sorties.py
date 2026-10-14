"""Les sorties du catalogue : une aide que son guide ne liste plus, sans réseau ni modèle."""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from prospection.territoires import Territoire  # noqa: E402

from catalogue import sorties  # noqa: E402
from catalogue.journal import Evenement, Vue  # noqa: E402
from catalogue.sorties import Entree, Listing  # noqa: E402

GUIDE = "https://dept.fr/aides"
JOUR = dt.date(2026, 10, 15)
T = Territoire(nom="Test", type="departement", prefixe_slug="tt", statut="pret", guides=[GUIDE])


@dataclass
class P:
    url: str
    status: int = 200
    url_finale: str = ""
    erreur: str | None = None

    def __post_init__(self) -> None:
        self.url_finale = self.url_finale or self.url


class Fetcheur:
    def __init__(self, pages: dict[str, P] | None = None) -> None:
        self.pages = pages or {}
        self.appels: list[str] = []

    def get(self, url: str) -> P:
        self.appels.append(url)
        return self.pages.get(url, P(url))


def aide(slug: str, url: str, nom: str = "Restauration du patrimoine rural non protégé") -> Any:
    return SimpleNamespace(
        slug=slug,
        nom=nom,
        nom_court=None,
        source=SimpleNamespace(url_officielle=url, formulaire_url=None),
        hard_filters=SimpleNamespace(departements=[], regions=[]),
    )


def listing(*slugs: str, autres: int = 20, nouvelles: tuple[Entree, ...] = ()) -> Listing:
    entrees = [Entree(f"https://dept.fr/aides/{s}", "", s) for s in slugs]
    entrees += [
        Entree(f"https://dept.fr/aides/autre-{i}", f"Autre aide {i}") for i in range(autres)
    ]
    return Listing("tt", entrees + list(nouvelles))


def passe(*listes: Listing) -> list[Evenement]:
    return [
        Evenement(
            "decision",
            "t:tt",
            decision="listing",
            issue="sain",
            donnees={"entrees": len(x.entrees), "presentes": sorted(x.presentes)},
        )
        for x in listes
    ]


def traiter(
    tmp_path: Path,
    actuel: Listing,
    evenements: list[Evenement],
    corpus: dict[str, Any],
    fetcheur: Fetcheur,
    vue: Vue | None = None,
    automatique: bool = True,
) -> tuple[sorties.Bilan, list[Evenement]]:
    consignes: list[Evenement] = []
    b = sorties.traiter(
        actuel,
        territoire=T,
        corpus=corpus,
        evenements=evenements,
        vue=vue or Vue(evenements),
        fetcheur=fetcheur,
        consigner=lambda e: consignes.append(e) or e,
        jour=JOUR,
        automatique=automatique,
        aides_dir=tmp_path / "aides",
        listings=tmp_path / "listings",
        retirees=tmp_path / "retirees",
    )
    return b, consignes


@pytest.fixture
def catalogue(tmp_path: Path) -> dict[str, Any]:
    (tmp_path / "aides").mkdir()
    corpus = {}
    for slug in ("tt-restauration", "tt-jardins"):
        (tmp_path / "aides" / f"{slug}.yaml").write_text(f"slug: {slug}\n", encoding="utf-8")
        corpus[slug] = aide(slug, f"https://dept.fr/aides/{slug}")
    return corpus


# ------------------------------------------------------------------ santé


def test_un_listing_qui_perd_plus_d_un_cinquieme_de_ses_fiches_est_douteux() -> None:
    assert sorties.sante(listing(autres=79), precedent=100) is not None
    assert sorties.sante(listing(autres=80), precedent=100) is None


@pytest.mark.parametrize(
    "note",
    [
        "sitemap injoignable : https://dept.fr/sitemap.xml → HTTP 503",
        "page en erreur : https://dept.fr/aides?page=3 → HTTP 500",
        "arrêt propre : plafond de 300 candidates — 412 trouvées",
        "page vide ou SPA (contenu monté en JavaScript) : https://dept.fr/aides",
    ],
)
def test_une_note_de_panne_de_la_collecte_rend_le_listing_douteux(note: str) -> None:
    x = listing()
    x.notes = [note]
    assert sorties.sante(x, precedent=None) is not None


def test_un_404_au_bout_de_la_pagination_n_est_pas_une_panne() -> None:
    """aube.fr répond 404 après sa dernière page : c'est la fin de la liste."""
    x = listing()
    x.notes = [
        "page en erreur : https://www.aube.fr/guide-des-aides/page/11/ → HTTP 404",
        "page en erreur : https://www.aube.fr/guide-des-aides/page/12/ → HTTP 404",
    ]
    assert sorties.sante(x, precedent=None) is None


def test_un_listing_douteux_n_est_ni_archive_ni_compte(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    avant = passe(listing("tt-restauration"), listing())
    x = listing(autres=2)
    b, consignes = traiter(tmp_path, x, avant, catalogue, Fetcheur())
    assert not b.sain and b.sorties == []
    assert [e.issue for e in consignes] == ["douteux"]
    assert not (tmp_path / "listings").exists()
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists()


# ------------------------------------------------------------------ absences


def test_les_absences_se_comptent_depuis_la_derniere_presence() -> None:
    assert sorties.absences("a", [{"a"}, set(), set()]) == 2
    assert sorties.absences("a", [set(), {"a"}, set()]) == 1
    assert sorties.absences("a", [{"a"}]) == 0
    assert sorties.absences("a", [set(), set()]) is None


def test_une_aide_jamais_listee_n_est_pas_suivie(tmp_path: Path, catalogue: dict[str, Any]) -> None:
    """La DRAC, un dispositif fiscal : aucun guide ne les liste, leur absence ne dit rien."""
    fetcheur = Fetcheur({"https://dept.fr/aides/tt-jardins": P("x", 404)})
    b, _ = traiter(tmp_path, listing(), passe(listing(), listing()), catalogue, fetcheur)
    assert b.suivies == 0 and b.sorties == [] and fetcheur.appels == []


def test_une_seule_absence_ne_declenche_rien(tmp_path: Path, catalogue: dict[str, Any]) -> None:
    fetcheur = Fetcheur()
    b, _ = traiter(tmp_path, listing(), passe(listing("tt-restauration")), catalogue, fetcheur)
    assert b.suivies == 1 and b.sorties == [] and fetcheur.appels == []


# ------------------------------------------------------------------ retrait


def test_absente_deux_fois_et_page_morte_l_aide_est_retiree_sans_case(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    url = "https://dept.fr/aides/tt-restauration"
    avant = passe(listing("tt-restauration", "tt-jardins"), listing("tt-jardins"))
    b, consignes = traiter(
        tmp_path, listing("tt-jardins"), avant, catalogue, Fetcheur({url: P(url, 404)})
    )
    assert [s.slug for s in b.sorties if s.issue == "retiree"] == ["tt-restauration"]
    assert b.cases == []
    assert not (tmp_path / "aides" / "tt-restauration.yaml").exists()
    retiree = (tmp_path / "retirees" / "tt-restauration.yaml").read_text(encoding="utf-8")
    assert retiree.startswith("# Retirée du catalogue le 2026-10-15 : absente du guide tt")
    assert retiree.endswith("slug: tt-restauration\n")
    assert ("a:tt-restauration", "sortie", "retiree") in [
        (e.objet, e.decision, e.issue) for e in consignes
    ]


@pytest.mark.parametrize(
    "page",
    [
        P("u", 200, "https://dept.fr/"),
        P("u", 200, GUIDE + "/"),
        P("u", 301),
        P("u", 410),
    ],
)
def test_ce_qui_compte_comme_page_morte(page: P) -> None:
    assert sorties.page_morte(page, "https://dept.fr/aides/fiche", [GUIDE])[0] is True


@pytest.mark.parametrize("page", [P("u", 403), P("u", 503), P("u", 0, erreur="timeout")])
def test_un_refus_ou_une_panne_n_est_pas_une_page_morte(page: P) -> None:
    assert sorties.page_morte(page, "https://dept.fr/aides/fiche", [GUIDE])[0] is None


def test_page_injoignable_rien_n_est_retire(tmp_path: Path, catalogue: dict[str, Any]) -> None:
    url = "https://dept.fr/aides/tt-restauration"
    avant = passe(listing("tt-restauration"), listing())
    b, _ = traiter(tmp_path, listing(), avant, catalogue, Fetcheur({url: P(url, 503)}))
    assert [s.issue for s in b.sorties] == ["panne"] and b.cases == []
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists()


def test_page_vivante_une_case_et_rien_n_est_retire(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    avant = passe(listing("tt-restauration"), listing())
    b, _ = traiter(tmp_path, listing(), avant, catalogue, Fetcheur())
    assert [c.sorte for c in b.cases] == ["sortie"]
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists()


def test_un_titre_voisin_dans_le_listing_est_un_deplacement_pas_un_retrait(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    url = "https://dept.fr/aides/tt-restauration"
    nouvelle = Entree(
        "https://dept.fr/dispositifs/patrimoine-rural",
        "Restauration du patrimoine rural non protégé",
    )
    avant = passe(listing("tt-restauration"), listing())
    b, _ = traiter(
        tmp_path, listing(nouvelles=(nouvelle,)), avant, catalogue, Fetcheur({url: P(url, 404)})
    )
    assert [s.deplacement for s in b.sorties] == [nouvelle.url]
    assert [c.sorte for c in b.cases] == ["sortie"]
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists()


def test_reglage_case_le_retrait_sur_devient_une_case(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    url = "https://dept.fr/aides/tt-restauration"
    avant = passe(listing("tt-restauration"), listing())
    b, _ = traiter(
        tmp_path, listing(), avant, catalogue, Fetcheur({url: P(url, 404)}), automatique=False
    )
    assert [c.sorte for c in b.cases] == ["sortie"]
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists()


@pytest.mark.parametrize("option,reste", [("retirer", False), ("garder", True)])
def test_la_reponse_de_felix_s_applique_au_passage_suivant(
    tmp_path: Path, catalogue: dict[str, Any], option: str, reste: bool
) -> None:
    avant = passe(listing("tt-restauration"), listing())
    b, _ = traiter(tmp_path, listing(), avant, catalogue, Fetcheur())
    case = b.cases[0]
    felix = Evenement(
        "felix",
        case.objet,
        decision="sortie",
        auteur="felix",
        issue=option,
        donnees={"case": case.id, "etat": case.etat},
    )
    b, _ = traiter(tmp_path, listing(), avant, catalogue, Fetcheur(), vue=Vue([*avant, felix]))
    assert b.cases == []
    assert (tmp_path / "aides" / "tt-restauration.yaml").exists() is reste


# ------------------------------------------------------------------ archive


def test_le_listing_sain_est_archive_trie(tmp_path: Path, catalogue: dict[str, Any]) -> None:
    traiter(tmp_path, listing("tt-jardins", autres=2), [], catalogue, Fetcheur())
    lignes = (tmp_path / "listings" / "tt.jsonl").read_text(encoding="utf-8").splitlines()
    assert lignes == sorted(lignes) and len(lignes) == 3
    assert '"slug": "tt-jardins"' in lignes[-1]


def test_le_premier_listing_sain_ne_fait_que_la_reference(
    tmp_path: Path, catalogue: dict[str, Any]
) -> None:
    fetcheur = Fetcheur()
    b, consignes = traiter(tmp_path, listing(), [], catalogue, fetcheur)
    assert b.sain and b.sorties == [] and fetcheur.appels == []
    assert [(e.objet, e.issue) for e in consignes] == [("t:tt", "sain")]

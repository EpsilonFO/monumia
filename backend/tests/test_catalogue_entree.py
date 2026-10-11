"""L'entrée au catalogue (incrément I6) : la règle de production portée, sans réseau ni modèle."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import decision as pd  # noqa: E402

from catalogue import entree  # noqa: E402
from catalogue.journal import Vue  # noqa: E402
from catalogue.openrouter import Panne  # noqa: E402
from catalogue.registre import charger  # noqa: E402

TEXTE = "\n".join(
    f"Le Département soutient les propriétaires de monuments protégés pour la restauration, ligne {i}."
    for i in range(20)
)


class Jev:
    def __init__(
        self,
        deposable: float,
        destinataire: str = "proprietaire_gestionnaire",
        objet: str = "bien_ou_lieu",
        dispositif: float = 0.9,
    ) -> None:
        self.args = (deposable, destinataire, objet, dispositif)
        self.appels = 0

    def decider(self, etat: Any, questions: Any) -> pd.Decision:
        self.appels += 1
        deposable, destinataire, objet, dispositif = self.args
        if deposable < 0:
            raise Panne("reponse_invalide", "noul vide")
        r = {
            "deposable": pd.Reponse("noul", noul=deposable),
            "dispositif": pd.Reponse("noul", noul=dispositif),
            "destinataire": pd.Reponse("choice", choix=destinataire),
            "objet": pd.Reponse("choice", choix=objet),
            "categorie_ecart": pd.Reponse("choice", choix="objet_hors_lieu"),
        }
        return pd.Decision(r, "typesafe/jev-1.13-20260917", "", 0, 0.0, 0.0, {})


class Lecteur:
    def __init__(
        self,
        destinataire: str,
        objet: str,
        famille: str = "restauration_bati",
        categorie: str | None = None,
    ) -> None:
        self.lu = (destinataire, objet, famille, categorie)
        self.appels = 0

    def try_complete_json(self, modele: Any, prompt: str, *, system: str) -> Any:
        from prospection import lecture

        self.appels += 1
        d, o, f, c = self.lu
        fiche = lecture.LectureFiche.model_construct(
            destinataire=d,
            objet=o,
            famille=f,
            categorie_ecart=c,
            titre="Aide",
            note="",
            slug_propose="aide",
            urls_pdf=[],
            beneficiaires=None,
        )
        return type("Essai", (), {"data": fiche, "response": None})()


def _juger(
    jev: Any,
    lecteur: Any,
    vue: Vue | None = None,
    texte: str = TEXTE,
    url: str = "https://exemple.fr/aide",
    vus: Any = None,
) -> tuple[entree.Jugement, list[Any]]:
    evenements: list[Any] = []
    vue = vue or Vue([])

    def consigner(e: Any) -> Any:
        evenements.append(e)
        vue.prendre(e)
        return e

    page = entree.Page(url, url, texte, [], False, "test")
    j = entree.juger(
        page,
        registre=charger(),
        vue=vue,
        jev=jev,
        lecteur=lecteur,
        modele_lecture="z-ai/glm-5.3-flash",
        consigner=consigner,
        textes_vus=vus,
    )
    return j, evenements


def test_sous_la_bande_basse_la_page_est_ecartee_sans_lecture() -> None:
    lecteur = Lecteur("proprietaire_gestionnaire", "bien_ou_lieu")
    j, evts = _juger(Jev(0.05, objet="hors_lieu"), lecteur)
    assert j.issue == "ecartee" and j.bande == "ecartee" and lecteur.appels == 0
    assert evts[-1].decision == "entree" and evts[-1].cle


@pytest.mark.parametrize(
    ("jev", "lu", "issue"),
    [
        (Jev(0.3), ("proprietaire_gestionnaire", "bien_ou_lieu"), "admise"),
        (Jev(0.3), ("indetermine", "bien_ou_lieu"), "doute"),
        # Au milieu des bandes, un écart du LLM part à un humain (`_appliquer_arbitrage`).
        (Jev(0.3, destinataire="activite_tiers"), ("activite_tiers", "bien_ou_lieu"), "doute"),
        (Jev(0.3), ("proprietaire_gestionnaire", "bien_ou_lieu", "adjacente"), "doute"),
    ],
)
def test_au_milieu_la_lecture_et_la_regle_de_la_file_decident(
    jev: Jev, lu: tuple[str, ...], issue: str
) -> None:
    j, _ = _juger(jev, Lecteur(*lu))
    assert j.issue == issue, j.motif


def test_une_page_portail_n_est_jamais_admise() -> None:
    assert (
        entree.issue_de(
            "proprietaire_gestionnaire",
            "bien_ou_lieu",
            "non_dispositif",
            "restauration_bati",
            "u",
            "t",
            "x",
        )[0]
        == "ecartee"
    )


def test_une_panne_de_jev_n_est_ni_un_ecart_ni_memorisee() -> None:
    vue = Vue([])
    lecteur = Lecteur("proprietaire_gestionnaire", "bien_ou_lieu")
    j, evts = _juger(Jev(-1), lecteur, vue)
    assert j.issue == "panne" and j.panne == "reponse_invalide" and lecteur.appels == 0
    assert [e.type for e in evts] == ["panne"] and vue.par_cle == {}


def test_un_jugement_a_entrees_identiques_est_repris_sans_appel() -> None:
    vue = Vue([])
    _juger(Jev(0.3), Lecteur("proprietaire_gestionnaire", "bien_ou_lieu"), vue)
    jev, lecteur = Jev(0.3), Lecteur("indetermine", "indetermine")
    j, evts = _juger(jev, lecteur, vue)
    assert (
        j.memorise
        and j.issue == "admise"
        and jev.appels == 0
        and lecteur.appels == 0
        and evts == []
    )


def test_une_page_sans_texte_courant_ne_va_a_aucun_decideur() -> None:
    menu = "\n".join(f"* [Rubrique {i}](/rubrique-{i})" for i in range(200))
    jev = Jev(0.9)
    j, evts = _juger(jev, Lecteur("proprietaire_gestionnaire", "bien_ou_lieu"), texte=menu)
    assert j.issue == "panne" and j.panne == "contenu_inexploitable" and jev.appels == 0


def test_un_texte_identique_a_celui_d_une_autre_page_du_site_est_le_gabarit() -> None:
    vus: dict[tuple[str, str], str] = {}
    premier, _ = _juger(
        Jev(0.3),
        Lecteur("proprietaire_gestionnaire", "bien_ou_lieu"),
        url="https://site.fr/a",
        vus=vus,
    )
    second, _ = _juger(
        Jev(0.3),
        Lecteur("proprietaire_gestionnaire", "bien_ou_lieu"),
        url="https://site.fr/b",
        vus=vus,
    )
    assert premier.issue == "admise" and second.panne == "contenu_inexploitable"


def test_la_regle_anti_boucle() -> None:
    assert entree.en_boucle("https://moselle.fr/a/b/a/b/a/fiche")
    assert not entree.en_boucle("https://moselle.fr/aides/patrimoine/restauration")


def test_l_entree_ne_rejuge_pas_une_url_de_la_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Une URL écartée à la main dans la file n'est ni triée ni jugée par la nouvelle chaîne."""
    import json as _json

    from pipeline import etat

    candidats = tmp_path / "candidats.jsonl"
    candidats.write_text(
        _json.dumps({"url": "https://x.fr/ecartee", "titre": "Aide écartée"}) + "\n",
        encoding="utf-8",
    )
    file = {
        "ecartee": etat.Tache(
            titre="X", url="https://x.fr/ecartee", territoire="91", statut="ignore"
        )
    }

    class Tri:
        def try_complete_json(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("aucun tri ne doit partir")

    x = entree.explorer(
        "91",
        registre=charger(),
        vue=Vue([]),
        jev=Jev(0.3),
        client_tri=Tri(),
        lecteur=Lecteur("proprietaire_gestionnaire", "bien_ou_lieu"),
        modele_lecture="m",
        consigner=lambda e: e,
        fetcheur=None,
        candidats_figes=candidats,
        file=file,
    )
    assert x.candidats == 0 and x.deja_juges == 1 and x.jugements == []

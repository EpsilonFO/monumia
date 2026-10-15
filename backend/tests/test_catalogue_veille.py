"""La veille du paquet (incrément I2) : référence du journal, garde, cases, pannes, projection inverse.

Aucun réseau, aucun modèle : un faux client rend des réponses écrites ici, et
les écritures d'instantanés partent dans un dossier temporaire.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_aides  # noqa: E402
import veille_collect  # noqa: E402
from veille_apply import VeilleLLMOutput  # noqa: E402
from veille_collect import AideCollect, FetchResult, MonitoredUrl  # noqa: E402

from aides_schema import load_aide  # noqa: E402
from catalogue import cases, controles, veille  # noqa: E402
from catalogue.budget import Budget  # noqa: E402
from catalogue.journal import Evenement, Journal, Vue  # noqa: E402
from catalogue.openrouter import Avis, Decision, Panne, Reponse  # noqa: E402
from catalogue.registre import charger  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
SLUG = "77-festivals"
URL = (
    "https://www.seine-et-marne.fr/fr/appels-projet-subventions/"
    "festivals-et-manifestations-culturelles-et-artistiques"
)
JOUR = dt.date(2026, 10, 11)
LIGNE = "Dépôt des dossiers jusqu'au 12 février 2027 sur le téléservice."


class FauxClient:
    """Rend, dans l'ordre, les textes du mandat et les notes de la garde ; compte les appels."""

    def __init__(self, textes: list[Any], notes: list[Any]) -> None:
        self.textes, self.notes = list(textes), list(notes)
        self.appels: list[str] = []

    def completer(self, modele: str, messages: list[dict[str, str]], **_: Any) -> Reponse:
        self.appels.append("llm")
        t = self.textes.pop(0)
        if isinstance(t, Exception):
            raise t
        return Reponse(t, None, "z-ai/glm-5.3-flash", "f", 0.001, 100, 10, 0, 1.0)

    def decider(self, modele: str, etat: Any, questions: Any, **_: Any) -> Decision:
        self.appels.append("jev")
        p = self.notes.pop(0)
        if isinstance(p, Exception):
            raise p
        return Decision(
            {
                "touche": Avis("noul", {"true": p, "false": 1 - p}),
                "section": Avis("choice", {"rien": 1.0}, "rien"),
            },
            "typesafe/jev-1.13-20260917",
            0.0004,
            100,
            0.3,
        )


def _corps(fichier: str) -> str:
    texte = (BACKEND / "data" / "sources" / SLUG / fichier).read_text(encoding="utf-8")
    return texte.split("\n---\n", 1)[1] if texte.startswith("---") else texte


@pytest.fixture
def banc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Une aide copiée, ses instantanés copiés, une collecte fabriquée (la page a gagné une ligne)."""
    sources = tmp_path / "sources"
    shutil.copytree(BACKEND / "data" / "sources" / SLUG, sources / SLUG)
    yaml = tmp_path / f"{SLUG}.yaml"
    shutil.copy(BACKEND / "data" / "aides" / f"{SLUG}.yaml", yaml)

    ecrits: list[str] = []

    def faux_rafraichir(an: Any, col: Any, *, jour: dt.date) -> list[str]:
        nom = f"{jour.isoformat()}-reglement.md"
        frais = col.fetched[URL].raw_text
        (sources / SLUG / nom).write_text(
            f"---\nurl: {URL}\nsha256: {hashlib.sha256(frais.encode()).hexdigest()}\n---\n{frais}",
            encoding="utf-8",
        )
        ecrits.append(nom)
        return [nom]

    monkeypatch.setattr(veille, "rafraichir_snapshots", faux_rafraichir)
    return {"tmp": tmp_path, "sources": sources, "yaml": yaml, "ecrits": ecrits}


def _collecte(apres: str) -> dict[str, AideCollect]:
    avant = _corps("2026-10-04-reglement.md")
    murl = MonitoredUrl(url=URL, role="officielle", baseline_body=avant, baseline_sha="x")
    res = FetchResult(
        url=URL,
        status=200,
        raw_text=apres,
        body_md=apres,
        sha256=hashlib.sha256(apres.encode()).hexdigest(),
    )
    return {SLUG: AideCollect(slug=SLUG, urls=[murl], fetched={URL: res})}


def _frais() -> str:
    return _corps("2026-10-04-reglement.md").rstrip() + "\n\n" + LIGNE + "\n"


def _ctx(
    banc: dict[str, Any], client: Any, journal: Journal | None = None, ecrire: bool = True
) -> veille.Contexte:
    j = journal or Journal(banc["tmp"] / "journal")
    return veille.Contexte(
        registre=charger(),
        journal=j,
        vue=Vue(list(j.lire())),
        client=client,
        budget=Budget(1.0),
        run="test",
        aujourd_hui=JOUR,
        blobs=banc["tmp"] / "blobs",
        ecrire=ecrire,
        sources=banc["sources"],
        chemin_yaml=lambda slug: banc["yaml"],
    )


def _sortie(**champs: Any) -> str:
    return json.dumps(
        {"resume": "la date limite change", "conditions": [], **champs}, ensure_ascii=False
    )


def _passer(
    banc: dict[str, Any], client: Any, *, journal: Journal | None = None, ecrire: bool = True
):
    ctx = _ctx(banc, client, journal, ecrire)
    aides = {SLUG: load_aide(banc["yaml"])}
    bilan = veille.passer(
        ctx, aides, _collecte(_frais()), manifeste=banc["tmp"] / "veille-state.yaml"
    )
    return ctx, bilan, bilan.resultats[SLUG]


# ------------------------------------------------------------------ étage C


def test_une_retouche_litterale_s_ecrit_et_fait_avancer_la_reference(banc: dict[str, Any]) -> None:
    sortie = _sortie(calendrier={"champs": {"date_limite": "2027-02-12"}, "quote": LIGNE})
    ctx, bilan, r = _passer(banc, FauxClient([sortie], []))
    assert r.statut == "MAJ_LLM"
    assert r.issue == "retouche", r.raison
    assert "date_limite: 2027-02-12" in banc["yaml"].read_text(encoding="utf-8")
    # La référence avance sur l'instantané écrit, au journal.
    bases = veille.bases_en_vigueur(list(ctx.journal.lire()))
    assert bases[(f"a:{SLUG}", veille_collect.cle_url(URL))]["fichier"] == banc["ecrits"][0]
    # Le bloc `fiche:` parle encore du 13 février 2026 : un résidu, en case.
    assert [c.sorte for c in r.cases] == ["veille-residu"]
    manifeste = veille_aides.load_manifest(banc["tmp"] / "veille-state.yaml")
    assert manifeste[SLUG]["maj"]["champs"] == r.champs


def test_une_date_dont_l_annee_est_deduite_devient_une_case(banc: dict[str, Any]) -> None:
    deduite = _sortie(
        calendrier={"champs": {"date_limite": "2027-02-12"}, "quote": "jusqu'au 12 février 2027"}
    )
    # La page ne porte la date qu'avec l'année : on la retire pour simuler une déduction.
    frais = _frais().replace("12 février 2027", "12 février")
    ctx = _ctx(banc, FauxClient([deduite.replace("12 février 2027", "12 février")], []))
    bilan = veille.passer(ctx, {SLUG: load_aide(banc["yaml"])}, _collecte(frais))
    r = bilan.resultats[SLUG]
    assert r.issue == "case", r.raison
    assert "valeur absente" in r.raison
    assert "2027-02-12" not in banc["yaml"].read_text(encoding="utf-8")
    assert banc["ecrits"] == []


def test_une_retouche_de_texte_de_condition_devient_une_case(banc: dict[str, Any]) -> None:
    aide = load_aide(banc["yaml"])
    cond = aide.conditions[0]
    sortie = _sortie(
        conditions=[{"op": "update", "id": cond.id, "champs": {"text": "Nouveau texte."}}]
    )
    out = VeilleLLMOutput.model_validate_json(sortie)
    assert controles.conditions_protegees(out) == [f"{cond.id}.text"]


@pytest.mark.parametrize(
    ("note", "issue", "avance"),
    [(0.02, "inchange", True), (0.2, "zone_prudente", False), (0.6, "case", False)],
)
def test_la_garde_et_sa_zone_prudente(
    banc: dict[str, Any], note: float, issue: str, avance: bool
) -> None:
    ctx, bilan, r = _passer(banc, FauxClient([_sortie(resume="rien dans le mandat")], [note]))
    assert r.issue == issue
    assert r.garde == note
    assert bool(banc["ecrits"]) is avance
    manifeste = veille_aides.load_manifest(banc["tmp"] / "veille-state.yaml")
    if not avance:
        # Projection inverse : l'ancienne veille garde le changement en attente.
        assert manifeste[SLUG]["maj_refusee"]["etat"] == "suspect"
        assert manifeste[SLUG]["maj_refusee"]["empreinte"]


@pytest.mark.parametrize(
    ("etiquette", "issue", "avance"),
    [("ne touche pas", "inchange", True), ("touche", "case", False)],
)
def test_l_etiquette_mensuelle_fait_sortir_de_la_zone_prudente(
    banc: dict[str, Any], etiquette: str, issue: str, avance: bool
) -> None:
    j = Journal(banc["tmp"] / "journal")
    ctx, _, r = _passer(banc, FauxClient([_sortie(resume="rien")], [0.2]), journal=j)
    assert r.issue == "zone_prudente"
    (garde,) = [e for e in j.lire() if e.decision == "V1-garde"]
    j.ajouter(
        Evenement(
            "decision",
            f"a:{SLUG}",
            decision="V1-etiquette",
            decideur="claude",
            issue=etiquette,
            donnees={"garde": garde.cle},
        )
    )
    _, _, r2 = _passer(banc, FauxClient([], []), journal=j)
    assert r2.issue == issue
    assert bool(banc["ecrits"]) is avance


def test_une_garde_en_panne_laisse_la_reference(banc: dict[str, Any]) -> None:
    ctx, bilan, r = _passer(
        banc, FauxClient([_sortie(resume="rien")], [Panne("reponse_invalide", "noul vide")])
    )
    assert r.issue == "zone_prudente"
    assert r.panne == "reponse_invalide"
    assert banc["ecrits"] == []
    assert any(e.type == "panne" for e in ctx.journal.lire())


def test_une_panne_du_mandat_n_est_pas_un_refus(banc: dict[str, Any]) -> None:
    ctx, bilan, r = _passer(banc, FauxClient([Panne("delai", "240 s")], []))
    assert r.issue == "panne"
    assert banc["ecrits"] == []
    evenements = list(ctx.journal.lire())
    assert not [e for e in evenements if e.type == "decision"]
    manifeste = veille_aides.load_manifest(banc["tmp"] / "veille-state.yaml")
    # Rien n'est mémorisé comme refus : l'ancienne veille le resoumettrait.
    assert "maj_refusee" not in manifeste.get(SLUG, {})


def test_une_decision_a_entrees_identiques_est_reprise_sans_appel(banc: dict[str, Any]) -> None:
    j = Journal(banc["tmp"] / "journal")
    premier = FauxClient([_sortie(resume="rien")], [0.2])
    _passer(banc, premier, journal=j)
    assert premier.appels == ["llm", "jev"]
    second = FauxClient([], [])
    _, _, r = _passer(banc, second, journal=j)
    assert second.appels == []
    assert r.issue == "zone_prudente" and r.memorise


def test_la_reponse_de_felix_fait_avancer_la_reference(banc: dict[str, Any]) -> None:
    j = Journal(banc["tmp"] / "journal")
    _, _, r = _passer(banc, FauxClient([_sortie(resume="rien")], [0.6]), journal=j)
    (case,) = r.cases
    rapport = banc["tmp"] / "2026-10-11-semaine.md"
    texte = "\n".join(case.rendre()).replace("- [ ] `rearchiver`", "- [x] `rearchiver`")
    rapport.write_text(texte, encoding="utf-8")
    vue = Vue(list(j.lire()))
    nouveaux, ambigues = cases.relire([rapport], vue)
    assert len(nouveaux) == 1 and not ambigues
    j.ajouter_lot(nouveaux)
    # Relire le même rapport n'ajoute rien.
    assert cases.relire([rapport], Vue(list(j.lire())))[0] == []
    client = FauxClient([], [])
    _, _, r2 = _passer(banc, client, journal=j)
    assert r2.issue == "rearchivee" and client.appels == []
    assert banc["ecrits"]


def test_une_note_reecrite_sans_citation_n_est_pas_ecrite() -> None:
    """La fausse retouche du rejeu du 2026-10-11 (prix-sesame), réponse enregistrée."""
    out = VeilleLLMOutput.model_validate(
        {
            "resume": "la page annonce 15 lauréats",
            "conditions": [
                {
                    "op": "update",
                    "id": "dotation-20000-euros-editions-2025-2026",
                    "champs": {"notes": "La page indique désormais 15 projets lauréats."},
                }
            ],
        }
    )
    assert controles.notes_non_ancrees(out) == ["dotation-20000-euros-editions-2025-2026.notes"]
    avec_citation = out.model_copy(deep=True)
    assert avec_citation.conditions[0].champs is not None
    avec_citation.conditions[0].champs["quote"] = "15 projets sont lauréats"
    assert controles.notes_non_ancrees(avec_citation) == []


# ------------------------------------------------------------------ référence et cases


def test_la_reference_vient_du_journal_et_non_du_dernier_archive(banc: dict[str, Any]) -> None:
    j = Journal(banc["tmp"] / "journal")
    j.ajouter(
        Evenement(
            "import",
            f"a:{SLUG}",
            decision="base",
            auteur="import",
            donnees={"cle_url": veille_collect.cle_url(URL), "fichier": "2026-06-21-reglement.md"},
        )
    )
    murl = MonitoredUrl(
        url=URL,
        role="officielle",
        baseline_path=banc["sources"] / SLUG / "2026-10-04-reglement.md",
        baseline_body="récent",
        baseline_sha="y",
    )
    col = {SLUG: AideCollect(slug=SLUG, urls=[murl])}
    n = veille.appliquer_bases(col, veille.bases_en_vigueur(list(j.lire())), banc["sources"])
    assert n == 1
    m = col[SLUG].urls[0]
    assert m.baseline_path is not None and m.baseline_path.name == "2026-06-21-reglement.md"
    assert m.baseline_body == _corps("2026-06-21-reglement.md")


def test_une_case_a_deux_choix_coches_n_est_pas_lue() -> None:
    c = cases.Case("veille-echeance", "a:x", "échéance", "2026-01-01", {"a": "A", "b": "B"})
    texte = "\n".join(c.rendre()).replace("- [ ]", "- [x]")
    reponses, ambigues = cases.lire(texte)
    assert reponses == [] and ambigues == [c.id]


def test_valeurs_et_residus() -> None:
    texte = controles.sans_accents("Clôture le 31 mars 2027. Aide de 50 000 €.")
    assert controles.figure("2027-03-31", texte) is True
    assert controles.figure("2026-03-31", texte) is False
    assert controles.figure(50000, texte) is True
    assert controles.figure(True, texte) is None
    out = VeilleLLMOutput.model_validate(
        {"resume": "", "calendrier": {"champs": {"date_limite": "2027-03-31"}, "quote": "x"}}
    )
    ancien = {"calendrier": {"date_limite": dt.date(2026, 3, 31)}}
    assert controles.residus(ancien, out, "date_limite: 2027-03-31\nfiche: le 31 mars 2026") != []
    assert controles.residus(ancien, out, "date_limite: 2027-03-31\n") == []


# ------------------------------------------------------------------ ancienne veille


def test_l_ancienne_veille_refuse_un_passage_reel_quand_la_veille_est_reprise(
    tmp_path: Path,
) -> None:
    registre = (
        (BACKEND / "data" / "catalogue" / "registre.yaml")
        .read_text(encoding="utf-8")
        .replace("  veille: nouvelle", "  veille: ancienne")
    )
    chemin = tmp_path / "registre.yaml"
    chemin.write_text(registre, encoding="utf-8")
    assert veille_aides.veille_reprise(chemin) is None
    chemin.write_text(
        registre.replace("  veille: ancienne", "  veille: nouvelle"), encoding="utf-8"
    )
    assert "nouvelle chaîne" in (veille_aides.veille_reprise(chemin) or "")
    chemin.write_text("version: 9\n", encoding="utf-8")
    assert "illisible" in (veille_aides.veille_reprise(chemin) or "")
    assert veille_aides.veille_reprise(tmp_path / "absent.yaml") is None


def test_le_registre_en_service_donne_la_veille_a_la_nouvelle_chaine() -> None:
    """Depuis I9a, l'ancienne veille refuse un passage réel tant que le registre n'est pas repassé."""
    assert charger().proprietaires["veille"] == "nouvelle"
    assert "nouvelle chaîne" in (veille_aides.veille_reprise() or "")


# ------------------------------------------------------------------ calibrer


def test_le_seuil_bas_laisse_passer_au_plus_le_budget_de_positifs() -> None:
    from catalogue import calibrer

    points = [(0.1, 1), (0.3, 1), (0.05, 0), (0.07, 0), (0.2, 0)]
    s = calibrer.seuil_bas(points, 0.0)
    assert 0.07 < s < 0.1
    assert calibrer.seuil_bas(points, 0.5) > 0.1
    assert calibrer.effectif_minimal(0.10) == 35
    assert calibrer.effectif_minimal(0.05) == 73


def test_les_etalons_livres_de_la_garde_portent_tous_une_note() -> None:
    from catalogue import calibrer

    etalons = calibrer.lire("V1-garde")
    assert len(etalons) == 63 and sum(e.etiquette for e in etalons) == 9
    assert all("typesafe/jev-1.13-20260917" in e.p for e in etalons)
    texte = calibrer.calibrer_v1(charger(), "typesafe/jev-1.13-20260917", None)
    assert "Effectif insuffisant" in texte


def test_une_escalade_que_felix_fait_reextraire_passe_par_la_reextraction(
    banc: dict[str, Any],
) -> None:
    from catalogue import reextraction

    j = Journal(banc["tmp"] / "journal")
    _, _, r = _passer(banc, FauxClient([_sortie(resume="rien")], [0.6]), journal=j)
    (case,) = r.cases
    rapport = banc["tmp"] / "2026-10-11-semaine.md"
    rapport.write_text(
        "\n".join(case.rendre()).replace("- [ ] `reextraire`", "- [x] `reextraire`"),
        encoding="utf-8",
    )
    j.ajouter_lot(cases.relire([rapport], Vue(list(j.lire())))[0])
    appels: list[str] = []

    def refus(slug: str, etat: str) -> reextraction.Bilan:
        appels.append(slug)
        return reextraction.Bilan(slug, "refusee", "lint : erreur neuve", cout_usd=0.1)

    for _ in range(2):
        ctx = _ctx(banc, FauxClient([], []), j)
        ctx.reextraire = refus
        bilan = veille.passer(ctx, {SLUG: load_aide(banc["yaml"])}, _collecte(_frais()))
        r = bilan.resultats[SLUG]
        assert r.issue == "case" and "ré-extraction" in r.raison
    # Le refus est mémorisé pour ce changement : une seule ré-extraction payée.
    assert appels == [SLUG]
    assert [e.issue for e in j.lire() if e.decision == "reextraction"] == ["refusee"]


# ------------------------------------------------------------------ relecture adverse d'I2


def _cocher(banc: dict[str, Any], j: Journal, case: Any, option: str) -> None:
    rapport = banc["tmp"] / f"cases-{case.id}-{option}.md"
    rapport.write_text(
        "\n".join(case.rendre()).replace(f"- [ ] `{option}`", f"- [x] `{option}`"),
        encoding="utf-8",
    )
    j.ajouter_lot(cases.relire([rapport], Vue(list(j.lire())))[0])


def _deduite() -> tuple[str, str]:
    sortie = _sortie(
        calendrier={"champs": {"date_limite": "2027-02-12"}, "quote": "jusqu'au 12 février"}
    )
    return sortie, _frais().replace("12 février 2027", "12 février")


def test_une_proposition_en_attente_ne_repaie_pas_d_appel_et_appliquer_ecrit_ce_que_felix_a_vu(
    banc: dict[str, Any],
) -> None:
    j = Journal(banc["tmp"] / "journal")
    sortie, frais = _deduite()
    client = FauxClient([sortie], [])
    ctx = _ctx(banc, client, j)
    r = veille.passer(ctx, {SLUG: load_aide(banc["yaml"])}, _collecte(frais)).resultats[SLUG]
    (case,) = r.cases
    assert case.sorte == "veille-proposition" and "2027-02-12" in "\n".join(case.contexte)
    # Semaine suivante, sans réponse : aucun appel, la même case.
    second = FauxClient([], [])
    r2 = veille.passer(
        _ctx(banc, second, j), {SLUG: load_aide(banc["yaml"])}, _collecte(frais)
    ).resultats[SLUG]
    assert second.appels == [] and [c.id for c in r2.cases] == [case.id]
    _cocher(banc, j, case, "appliquer")
    troisieme = FauxClient([], [])
    r3 = veille.passer(
        _ctx(banc, troisieme, j), {SLUG: load_aide(banc["yaml"])}, _collecte(frais)
    ).resultats[SLUG]
    assert troisieme.appels == [] and r3.issue == "retouche"
    assert "date_limite: 2027-02-12" in banc["yaml"].read_text(encoding="utf-8")


def test_appliquer_ne_vaut_plus_si_la_fiche_a_change(banc: dict[str, Any]) -> None:
    j = Journal(banc["tmp"] / "journal")
    sortie, frais = _deduite()
    ctx = _ctx(banc, FauxClient([sortie], []), j)
    (case,) = (
        veille.passer(ctx, {SLUG: load_aide(banc["yaml"])}, _collecte(frais)).resultats[SLUG].cases
    )
    _cocher(banc, j, case, "appliquer")
    # Félix retouche la fiche entre-temps : la proposition vue ne vaut plus.
    banc["yaml"].write_text(
        banc["yaml"].read_text(encoding="utf-8") + "\n# retouche\n", encoding="utf-8"
    )
    client = FauxClient([sortie], [])
    r = veille.passer(
        _ctx(banc, client, j), {SLUG: load_aide(banc["yaml"])}, _collecte(frais)
    ).resultats[SLUG]
    assert client.appels == ["llm"] and r.issue == "case"
    assert "2027-02-12" not in banc["yaml"].read_text(encoding="utf-8")


def test_une_panne_de_la_garde_n_entre_pas_au_manifeste_comme_refus(banc: dict[str, Any]) -> None:
    _passer(banc, FauxClient([_sortie(resume="rien")], [Panne("delai", "15 s")]))
    manifeste = veille_aides.load_manifest(banc["tmp"] / "veille-state.yaml")
    assert "maj_refusee" not in manifeste.get(SLUG, {})


def test_une_base_proxy_ne_remplace_pas_une_capture_directe(banc: dict[str, Any]) -> None:
    proxy = banc["sources"] / SLUG / "2026-09-29-presentation.md"
    proxy.write_text(
        f"---\nurl: https://r.jina.ai/{URL}\nsha256: z\n---\ncorps proxy\n", encoding="utf-8"
    )
    murl = MonitoredUrl(url=URL, role="officielle", baseline_body="direct", baseline_sha="y")
    col = {SLUG: AideCollect(slug=SLUG, urls=[murl])}
    bases = {(f"a:{SLUG}", veille_collect.cle_url(URL)): {"fichier": proxy.name}}
    assert veille.appliquer_bases(col, bases, banc["sources"]) == 0
    assert col[SLUG].urls[0].baseline_body == "direct"


def test_une_reponse_tronquee_est_une_panne() -> None:
    import httpx

    from catalogue.openrouter import Client

    corps = {
        "model": "z-ai/glm-5.3-flash",
        "choices": [{"message": {"content": '{"resume": "coup'}, "finish_reason": "length"}],
        "usage": {"cost": 0.01, "completion_tokens": 32000},
    }
    client = Client(
        "cle",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=corps)),
        tentatives=1,
    )
    with pytest.raises(Panne) as exc:
        client.completer("z-ai/glm-5.3-flash", [{"role": "user", "content": "x"}], objet_json=True)
    assert exc.value.classe == "reponse_tronquee"


def test_un_diff_vide_fait_avancer_la_reference_sans_garde(banc: dict[str, Any]) -> None:
    ctx = _ctx(banc, FauxClient([], []))
    res = veille.Resultat(slug=SLUG, statut="MAJ_LLM", issue="ok")
    aide = load_aide(banc["yaml"])
    collects = _collecte(_frais())
    from veille_analyze import analyze_all

    an = analyze_all({SLUG: aide}, collects, today=JOUR)[SLUG]
    maj = veille._garder(ctx, aide, an, collects[SLUG], res, "", "rien", "e", lambda *a, **k: a)
    assert res.issue == "inchange" and ctx.client.appels == [] and maj is not None


def test_une_source_injoignable_ouvre_une_case_par_serie_et_vu_la_tait(
    banc: dict[str, Any],
) -> None:
    """Une source durablement derrière un anti-robot ne rouvre pas sa case chaque semaine."""
    from types import SimpleNamespace

    from catalogue.cases import Reponse

    j = Journal(banc["tmp"] / "journal")
    an = SimpleNamespace(
        statut="ERREUR_HTTP",
        erreurs=[SimpleNamespace(result=SimpleNamespace(status=403))],
        raisons=["HTTP 403"],
        urls=[],
        liens_morts=[],
    )
    aide = SimpleNamespace(slug=SLUG)

    def passage(run: str) -> list[Any]:
        ctx = _ctx(banc, None, j)
        ctx.run = run
        res, _ = veille.traiter(ctx, aide, an, None, list(j.lire()))  # type: ignore[arg-type]
        return res.cases

    assert passage("r1") == []
    (case,) = passage("r2")
    assert case.sorte == "veille-injoignable"
    (encore,) = passage("r3")
    assert encore.etat == case.etat
    j.ajouter(Reponse(case.id, case.sorte, case.objet, case.etat, "vu").evenement("r3"))
    assert passage("r4") == []


PDF = "https://www.seine-et-marne.fr/reglement-festivals.pdf"
FORM = "https://vosdemarches.seine-et-marne.fr/"


def _collecte_liens_morts(*, pdf: int | None = None, form: int | None = None) -> AideCollect:
    """La page officielle inchangée, plus un règlement PDF et le formulaire aux codes donnés."""
    col = _collecte(_corps("2026-10-04-reglement.md"))[SLUG]
    if pdf is not None:
        col.urls.append(MonitoredUrl(url=PDF, role="snapshot", baseline_sha="y", is_binary=True))
        col.fetched[PDF] = FetchResult(url=PDF, status=pdf)
    if form is not None:
        col.urls.append(MonitoredUrl(url=FORM, role="formulaire"))
        col.fetched[FORM] = FetchResult(url=FORM, status=form)
    return col


def _passage_liens(
    banc: dict[str, Any], j: Journal, run: str, col: AideCollect
) -> tuple[veille.Resultat, Any]:
    from veille_analyze import analyze_all

    aide = load_aide(banc["yaml"])
    an = analyze_all({SLUG: aide}, {SLUG: col}, today=JOUR)[SLUG]
    assert an.statut == "OK"  # la page officielle seule décide du statut
    ctx = _ctx(banc, None, j)
    ctx.run = run
    return veille.traiter(ctx, aide, an, col, list(j.lire()))


def test_un_formulaire_mort_deux_passages_de_suite_sort_de_la_fiche(
    banc: dict[str, Any],
) -> None:
    j = Journal(banc["tmp"] / "journal")
    avant = banc["yaml"].read_text(encoding="utf-8")

    res, _ = _passage_liens(banc, j, "2026-10-11-veille-0001", _collecte_liens_morts(form=404))
    assert (res.formulaire, res.cases) == ("constate", [])
    assert banc["yaml"].read_text(encoding="utf-8") == avant

    # Revenu entre-temps : la série repart de zéro.
    _passage_liens(banc, j, "2026-10-18-veille-0002", _collecte_liens_morts(form=200))
    res, _ = _passage_liens(banc, j, "2026-10-25-veille-0003", _collecte_liens_morts(form=410))
    assert res.formulaire == "constate"

    res, _ = _passage_liens(banc, j, "2026-11-01-veille-0004", _collecte_liens_morts(form=410))
    assert (res.issue, res.formulaire, res.cases) == ("ok", "retire", [])
    apres = banc["yaml"].read_text(encoding="utf-8")
    assert "formulaire_url" not in apres
    assert len(apres.splitlines()) == len(avant.splitlines()) - 1
    assert load_aide(banc["yaml"]).source.formulaire_url is None


def test_retirer_formulaire_refuse_ce_qui_n_est_pas_sur() -> None:
    texte = (BACKEND / "data" / "aides" / f"{SLUG}.yaml").read_text(encoding="utf-8")
    assert veille.retirer_formulaire(texte, "https://ailleurs.fr/") is None
    assert veille.retirer_formulaire(texte.replace("  formulaire_url:", "  autre:"), FORM) is None
    assert "formulaire_url" not in (veille.retirer_formulaire(texte, FORM) or "formulaire_url")


def test_une_page_archivee_morte_sans_citation_ne_fait_qu_une_ligne(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(veille, "_citations_de", lambda an, col, url: 0)
    j = Journal(banc["tmp"] / "journal")
    res, _ = _passage_liens(banc, j, "2026-10-11-veille-0001", _collecte_liens_morts(pdf=404))
    assert (res.issue, res.cases, res.pages_mortes) == ("ok", [], [PDF])
    assert any("aucune citation" in ligne for ligne in veille.section(_bilan(res)))


def test_une_page_archivee_morte_citee_est_une_escalade_que_vu_tait(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from catalogue.cases import Reponse

    monkeypatch.setattr(veille, "_citations_de", lambda an, col, url: 3)
    j = Journal(banc["tmp"] / "journal")
    res, maj = _passage_liens(banc, j, "2026-10-11-veille-0001", _collecte_liens_morts(pdf=404))
    (case,) = res.cases
    assert (res.issue, maj) == ("case", None)
    assert case.sorte == "veille-escalade" and set(case.options) == {"reextraire", "vu"}
    assert "3 citation(s)" in case.contexte[0]

    j.ajouter(Reponse(case.id, case.sorte, case.objet, case.etat, "vu").evenement("r1"))
    res, _ = _passage_liens(banc, j, "2026-10-18-veille-0002", _collecte_liens_morts(pdf=404))
    assert (res.issue, res.cases) == ("ok", [])


def test_une_page_archivee_morte_citee_part_en_reextraction_sur_reponse(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from catalogue.cases import Reponse

    monkeypatch.setattr(veille, "_citations_de", lambda an, col, url: 3)
    monkeypatch.setattr(veille, "_avancer", lambda *a, **k: None)
    j = Journal(banc["tmp"] / "journal")
    res, _ = _passage_liens(banc, j, "2026-10-11-veille-0001", _collecte_liens_morts(pdf=404))
    (case,) = res.cases
    j.ajouter(Reponse(case.id, case.sorte, case.objet, case.etat, "reextraire").evenement("r1"))

    appels: list[str] = []

    def reextraire(slug: str, etat: str) -> Any:
        appels.append(etat)
        return SimpleNamespace(
            issue="acceptee",
            raison="",
            cout_usd=0.5,
            duree_s=1.0,
            changements=["conditions"],
            faits=[],
            cases=[],
            panne=None,
            snapshots=[],
        )

    def passage(run: str) -> veille.Resultat:
        from veille_analyze import analyze_all

        aide = load_aide(banc["yaml"])
        col = _collecte_liens_morts(pdf=404)
        an = analyze_all({SLUG: aide}, {SLUG: col}, today=JOUR)[SLUG]
        ctx = _ctx(banc, None, j)
        ctx.run, ctx.reextraire = run, reextraire
        return veille.traiter(ctx, aide, an, col, list(j.lire()))[0]

    assert passage("2026-10-18-veille-0002").issue == "reextraite"
    # Ré-extraite pour ce changement : elle ne repart pas la semaine suivante.
    assert passage("2026-10-25-veille-0003").cases == []
    assert appels == [case.etat]


def _bilan(res: veille.Resultat) -> veille.Bilan:
    return veille.Bilan({res.slug: res}, 0, [], [], 0.0, 0)


# ------------------------------------------------------------------ ré-extractions en parallèle


def _escalades_factices(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch, slugs: list[str]
) -> dict[str, Any]:
    """Des aides que l'analyse escalade toutes, sans page ni modèle derrière."""
    from types import SimpleNamespace

    base = load_aide(banc["yaml"])
    aides = {s: base.model_copy(update={"slug": s}) for s in slugs}
    analyses = {
        s: SimpleNamespace(
            slug=s,
            statut="ESCALADE_INGESTION",
            raisons=["refonte"],
            liens_morts=[],
            date_limite_perimee=None,
        )
        for s in slugs
    }
    monkeypatch.setattr(veille, "analyze_all", lambda *a, **k: analyses)
    monkeypatch.setattr(veille, "empreinte_changement", lambda an: f"etat-{an.slug}")
    monkeypatch.setattr(veille, "garder_frais", lambda *a, **k: {})
    monkeypatch.setattr(veille, "_formulaires", lambda *a, **k: None)
    return aides


def test_les_reextractions_partent_ensemble_et_leur_suite_reste_dans_l_ordre(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from types import SimpleNamespace

    from catalogue import reextraction

    slugs = ["a-premiere", "b-deuxieme", "c-troisieme"]
    aides = _escalades_factices(banc, monkeypatch, slugs)
    # Les trois doivent être en vol EN MÊME TEMPS : en série, la barrière casse.
    barriere = threading.Barrier(3, timeout=10)
    fils: set[str] = set()

    def reextraire(slug: str, etat: str) -> reextraction.Bilan:
        fils.add(threading.current_thread().name)
        barriere.wait()
        return reextraction.Bilan(
            slug, "refusee", "lint : erreur neuve", cout_usd=0.1, durees={"modele": 2.0}
        )

    ctx = _ctx(banc, FauxClient([], []))
    ctx.reextraire, ctx.parallelisme = reextraire, 3
    bilan = veille.passer(ctx, aides, {s: SimpleNamespace(urls=[]) for s in slugs})  # type: ignore[misc]

    assert len(fils) == 3 and threading.current_thread().name not in fils
    assert list(bilan.resultats) == slugs
    for s in slugs:
        r = bilan.resultats[s]
        assert r.issue == "case" and "ré-extraction : refusee" in r.raison
        assert [c.sorte for c in r.cases] == ["veille-escalade"]
    # La suite (journal) se reprend dans l'ordre du passage, depuis le fil principal.
    assert [e.objet for e in ctx.journal.lire() if e.decision == "reextraction"] == [
        f"a:{s}" for s in slugs
    ]
    assert ctx.en_vol == {} and ctx.pool is None
    durees = bilan.chrono.durees
    assert durees["dans l'agent : modele"] == pytest.approx(6.0)
    assert any(k.startswith("ré-extractions, horloge (3 aides") for k in durees)
    assert any(ligne == "### Durées" for ligne in veille.section(bilan))


def test_une_reextraction_en_bug_n_arrete_pas_les_autres(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from catalogue import reextraction

    slugs = ["a-plante", "b-passe"]
    aides = _escalades_factices(banc, monkeypatch, slugs)

    def reextraire(slug: str, etat: str) -> reextraction.Bilan:
        if slug == "a-plante":
            raise RuntimeError("boum")
        return reextraction.Bilan(slug, "refusee", "lint : erreur neuve")

    ctx = _ctx(banc, FauxClient([], []))
    ctx.reextraire, ctx.parallelisme = reextraire, 2
    bilan = veille.passer(ctx, aides, {s: SimpleNamespace(urls=[]) for s in slugs})  # type: ignore[misc]
    assert (bilan.resultats["a-plante"].issue, bilan.resultats["a-plante"].panne) == (
        "panne",
        "bug",
    )
    assert bilan.resultats["b-passe"].issue == "case"


def test_le_chrono_cumule_et_classe_les_etapes() -> None:
    from catalogue.chrono import Chrono, duree_lisible

    c = Chrono()
    c.ajouter("collecte", 125.0)
    c.ajouter("garde", 1.5)
    c.ajouter("garde", 2.5)
    c.fusionner("agent : ", {"modele": 4000.0})
    assert c.lignes() == [
        "- agent : modele : 1 h 06",
        "- collecte : 2 min 05 s",
        "- garde : 4,0 s (2 fois, 2,0 s en moyenne)",
    ]
    assert duree_lisible(59.94) == "59,9 s"


def test_une_aide_en_train_de_sortir_n_est_pas_reextraite(
    banc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    slugs = ["a-sortante", "b-restante"]
    aides = _escalades_factices(banc, monkeypatch, slugs)
    appels: list[str] = []

    def reextraire(slug: str, etat: str) -> Any:
        appels.append(slug)
        from catalogue import reextraction

        return reextraction.Bilan(slug, "refusee", "lint : erreur neuve")

    ctx = _ctx(banc, FauxClient([], []))
    for presentes in (["a-sortante", "b-restante"], ["b-restante"]):
        ctx.journal.ajouter(
            Evenement(
                "decision",
                "t:tt",
                decision="listing",
                issue="sain",
                run="entree",
                donnees={"entrees": 20, "presentes": presentes},
            )
        )
    ctx.reextraire = reextraire
    bilan = veille.passer(ctx, aides, {s: SimpleNamespace(urls=[]) for s in slugs})  # type: ignore[misc]
    assert appels == ["b-restante"]
    r = bilan.resultats["a-sortante"]
    assert r.issue == "sortie_probable" and r.cases == []
    assert "absente du guide tt depuis 1 listing(s)" in r.raison

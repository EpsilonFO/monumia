"""Ré-extraction d'une aide en service (incrément I4) : éditeur par plages, règles de retour, contrat.

Aucun réseau ni modèle : un faux lanceur écrit le YAML et le résultat que
l'agent aurait rendus, dans le dossier de sortie que la ré-extraction prépare.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from aides_schema import charger_yaml  # noqa: E402
from catalogue import reextraction as rx  # noqa: E402
from catalogue.editeur import EditionImpossible, editer  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
AIDES = BACKEND / "data" / "aides"
SLUG = "77-festivals"
JOUR = dt.date(2026, 10, 11)


# ------------------------------------------------------------------ éditeur par plages


def test_l_editeur_rend_le_texte_a_l_octet_quand_rien_ne_change() -> None:
    for p in sorted(AIDES.glob("*.yaml")):
        texte = p.read_text(encoding="utf-8")
        assert editer(texte, charger_yaml(texte)) == texte, p.name


def test_l_editeur_ne_reecrit_que_le_champ_qui_change() -> None:
    texte = (AIDES / f"{SLUG}.yaml").read_text(encoding="utf-8")
    cible = charger_yaml(texte)
    cible["conditions"][0]["notes"] = "Note ajoutée."
    nouveau = editer(texte, cible)
    avant, apres = texte.split("\n"), nouveau.split("\n")
    assert len(apres) == len(avant) + 1
    assert "fiche:" in nouveau and nouveau.count("\n# ") == texte.count("\n# ")
    assert charger_yaml(nouveau)["conditions"][0]["notes"] == "Note ajoutée."


def test_l_editeur_retire_et_ajoute_des_conditions_sans_toucher_aux_autres() -> None:
    texte = (AIDES / "88-restauration-patrimoine.yaml").read_text(encoding="utf-8")
    cible = charger_yaml(texte)
    retiree = cible["conditions"].pop(1)
    cible["conditions"].append(
        {
            "id": "nouvelle-condition",
            "text": "Un texte.",
            "kind": "info",
            "effect": "info",
            "quote": "x",
        }
    )
    nouveau = editer(texte, cible)
    relu = charger_yaml(nouveau)
    assert retiree["id"] not in [c["id"] for c in relu["conditions"]]
    assert relu["conditions"][-1]["id"] == "nouvelle-condition"
    # Les autres conditions sont restées à l'octet : chacune de leurs lignes est là.
    for ligne in texte.split("\n"):
        if retiree["id"] not in ligne and ligne.strip().startswith("- id:"):
            assert ligne in nouveau


def test_l_editeur_refuse_un_changement_d_ordre_des_cles() -> None:
    texte = (AIDES / f"{SLUG}.yaml").read_text(encoding="utf-8")
    cible = dict(reversed(list(charger_yaml(texte).items())))
    cible["nom"] = "autre"
    with pytest.raises(EditionImpossible):
        editer(texte, cible)


# ------------------------------------------------------------------ règles de retour


def _cond(ident: str, quote: str, **k: Any) -> dict[str, Any]:
    return {
        "id": ident,
        "text": f"texte {ident}",
        "kind": "info",
        "effect": "info",
        "quote": quote,
        **k,
    }


BASE = [
    ("base.md", "Phrase A gardée. Phrase B ancienne. Phrase C disparue. Phrase D retirée.", "text")
]
FRAIS = [("frais.md", "Phrase A gardée. Phrase B nouvelle. Date limite le 31 mars 2027.", "text")]


URLS = {"base.md": "https://x.fr/aide", "frais.md": "https://x.fr/aide"}


def _retour(
    anciennes: list[dict[str, Any]],
    proposees: list[dict[str, Any]],
    urls: dict[str, str] = URLS,
    **sections: Any,
) -> rx.Retour:
    ancien = {"slug": "x", "calendrier": {"permanent": False}, "conditions": anciennes}
    agent = {
        "slug": "x",
        "calendrier": sections.get("calendrier", {"permanent": False}),
        "conditions": proposees,
    }
    return rx.retour("x", ancien, agent, BASE, FRAIS, {"fait_connu"}, "e", urls)


def test_une_condition_toujours_citee_reste_a_l_octet_meme_si_l_agent_la_reformule() -> None:
    c = _cond("a", "Phrase A gardée.")
    a = dict(c, text="reformulé")
    r = _retour([c], [a])
    assert r.cible["conditions"] == [c] and r.cases == []


def test_un_passage_change_prend_le_texte_et_la_citation_de_l_agent() -> None:
    c = _cond("b", "Phrase B ancienne.")
    a = dict(c, text="nouveau texte", quote="Phrase B nouvelle.")
    r = _retour([c], [a])
    assert r.cible["conditions"][0]["quote"] == "Phrase B nouvelle."
    assert r.cible["conditions"][0]["text"] == "nouveau texte"


def test_un_passage_change_sur_un_user_fact_devient_une_case() -> None:
    c = _cond(
        "b",
        "Phrase B ancienne.",
        kind="user_fact",
        effect="gate",
        fact="fait_connu",
        predicate={"eq": True},
    )
    a = dict(c, quote="Phrase B nouvelle.")
    r = _retour([c], [a])
    assert r.cible["conditions"] == [c]
    assert [k.sorte for k in r.cases] == ["reextraction-texte"]


def test_une_divergence_de_typage_est_une_case_jamais_une_ecriture() -> None:
    c = _cond("a", "Phrase A gardée.")
    a = dict(c, kind="manual_check", effect="gate")
    r = _retour([c], [a])
    assert r.cible["conditions"] == [c] and [k.sorte for k in r.cases] == ["reextraction-typage"]


def test_un_retrait_n_est_ecrit_que_pour_une_info_dont_la_citation_a_disparu() -> None:
    info = _cond("c", "Phrase C disparue.")
    gate = _cond(
        "d",
        "Phrase D retirée.",
        kind="auto",
        effect="gate",
        field="monument.x",
        predicate={"eq": True},
    )
    endettee = _cond("e", "Phrase jamais archivée.")
    r = _retour([info, gate, endettee], [])
    assert [c["id"] for c in r.cible["conditions"]] == ["d", "e"]
    assert [k.sorte for k in r.cases] == ["reextraction-retrait"]


@pytest.mark.parametrize("en_case", [True, False])
def test_une_condition_nouvelle_s_ajoute_et_son_fait_neuf_devient_une_case_en_mode_case(
    en_case: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("catalogue.registre.faits_neufs_en_case", lambda: en_case)
    a = _cond(
        "f",
        "Phrase B nouvelle.",
        kind="user_fact",
        effect="gate",
        fact="fait_neuf",
        predicate={"eq": True},
    )
    r = _retour([], [a])
    assert [c["id"] for c in r.cible["conditions"]] == ["f"]
    assert r.faits_neufs == ["fait_neuf"]
    assert [k.sorte for k in r.cases] == (["H-fait"] if en_case else [])


def test_une_date_ecrite_telle_quelle_s_ecrit_une_date_deduite_non() -> None:
    r = _retour([], [], calendrier={"permanent": False, "date_limite": "2027-03-31"})
    assert r.cible["calendrier"]["date_limite"] == "2027-03-31"
    r = _retour([], [], calendrier={"permanent": False, "date_limite": "2027-04-30"})
    assert "date_limite" not in r.cible["calendrier"]
    assert [k.sorte for k in r.cases] == ["reextraction-valeur"]


def test_une_condition_neuve_proche_d_une_gardee_devient_une_case() -> None:
    c = _cond("a", "Phrase A gardée.")
    a = _cond("a-bis", "Phrase A gardée et précisée.")
    r = _retour([c], [c, a])
    assert [x["id"] for x in r.cible["conditions"]] == ["a"]
    assert [k.sorte for k in r.cases] == ["reextraction-condition"]


def test_un_retrait_exige_que_le_document_de_la_citation_ait_ete_retelecharge() -> None:
    info = _cond("c", "Phrase C disparue.")
    r = _retour(
        [info], [], urls={"base.md": "https://x.fr/reglement.pdf", "frais.md": "https://x.fr/aide"}
    )
    assert [c["id"] for c in r.cible["conditions"]] == ["c"] and r.cases == []


def test_sans_page_fraiche_le_texte_d_une_condition_ne_bouge_pas() -> None:
    c = _cond("b", "Phrase B ancienne.")
    a = dict(c, text="reformulé", quote="Phrase B nouvelle.")
    ancien = {"slug": "x", "conditions": [c]}
    r = rx.retour("x", ancien, {"slug": "x", "conditions": [a]}, BASE, [], set(), "e", URLS)
    assert r.cible["conditions"] == [c]


def test_une_proposition_n_est_rapprochee_qu_une_fois() -> None:
    c2 = _cond("c2", "Phrase A gardée.")
    c5 = _cond("c5", "Phrase jamais archivée.", kind="discretionary")
    a = _cond("c5", "Phrase A gardée.")
    r = _retour([c2, c5], [a])
    assert r.cible["conditions"] == [c2, c5]


def test_une_condition_neuve_sans_effect_ou_untyped_devient_une_case() -> None:
    sans_effect = {"id": "n1", "text": "x", "kind": "info", "quote": "Phrase B nouvelle."}
    untyped = {
        "id": "n2",
        "text": "y",
        "kind": "untyped",
        "effect": "info",
        "quote": "Date limite le 31 mars 2027.",
    }
    r = _retour([], [sans_effect, untyped])
    assert (
        r.cible["conditions"] == [] and [k.sorte for k in r.cases] == ["reextraction-condition"] * 2
    )


def test_une_section_partielle_ne_perd_rien_et_un_booleen_va_en_case() -> None:
    ancien = {
        "slug": "x",
        "conditions": [],
        "calendrier": {"permanent": False, "date_limite": dt.date(2026, 3, 31)},
        "cumul": {"cumulable": True},
    }
    agent = {
        "slug": "x",
        "conditions": [],
        "calendrier": {"permanent": True},
        "cumul": {"cumulable": False, "exclusions": ["Fonds inventé"]},
    }
    r = rx.retour("x", ancien, agent, BASE, FRAIS, set(), "e", URLS)
    assert r.cible["calendrier"] == ancien["calendrier"] and r.cible["cumul"] == ancien["cumul"]
    assert [k.sorte for k in r.cases] == ["reextraction-valeur", "reextraction-valeur"]


def test_aucun_id_n_est_reattribue() -> None:
    c = _cond("a", "Phrase A gardée.")
    a1 = dict(c)
    a2 = _cond("a", "Phrase B nouvelle.")
    r = _retour([c], [a1, a2])
    assert [x["id"] for x in r.cible["conditions"]] == ["a"]


# ------------------------------------------------------------------ acceptation et faits


def test_l_acceptation_par_ecart_ignore_la_dette_et_voit_l_erreur_neuve() -> None:
    avant = ["x : `calendrier.permanent: true` avec une `date_limite` (2027-01-31) — contradiction"]
    apres = [
        "x : `calendrier.permanent: true` avec une `date_limite` (2028-03-31) — contradiction",
        "x : condition `z` sans `effect`",
    ]
    assert rx.erreurs_nouvelles(avant, apres) == ["x : condition `z` sans `effect`"]


def test_la_cle_d_erreur_distingue_deux_conditions_aux_ids_proches() -> None:
    avant = ["x / critere-1: quote introuvable dans les snapshots « a »"]
    apres = [*avant, "x / critere-2: quote introuvable dans les snapshots « inventée »"]
    assert rx.erreurs_nouvelles(avant, apres) == [apres[1]]


@pytest.mark.parametrize(
    ("resultat", "classe"),
    [
        (
            {"ok": False, "arret": "erreur_modele", "motif_echec": "NetworkError: coupure"},
            "fournisseur",
        ),
        (
            {"ok": False, "arret": "erreur_modele", "motif_echec": "HTTP 402 insufficient credits"},
            "credits",
        ),
        ({"ok": False, "arret": "budget", "motif_echec": "budget"}, "agent_budget"),
        ({"ok": False, "arret": "max_tours"}, "agent_max_tours"),
    ],
)
def test_un_agent_arrete_avant_la_fin_est_une_panne_pas_un_refus(
    resultat: dict[str, Any], classe: str
) -> None:
    assert rx.classer(resultat)[0::2] == ("panne", classe)
    assert (
        rx.classer({"ok": False, "arret": "termine", "motif_echec": "lint rouge"})[0] == "refusee"
    )


def test_les_faits_neufs_s_ajoutent_en_fin_de_fichier_sans_reecriture(tmp_path: Path) -> None:
    cible = tmp_path / "pending.yaml"
    cible.write_text("# en-tête\n\nfait_a:\n  type: boolean\n", encoding="utf-8")
    propose = tmp_path / "propose.yaml"
    propose.write_text(
        "fait_a:\n  type: boolean\n\n# pourquoi\nfait_b:\n  type: boolean\n", encoding="utf-8"
    )
    assert rx.ajouter_faits(["fait_b", "fait_a"], propose, cible) == ["fait_b"]
    texte = cible.read_text(encoding="utf-8")
    assert texte.startswith("# en-tête\n\nfait_a:\n  type: boolean\n")
    assert texte.rstrip().endswith("# pourquoi\nfait_b:\n  type: boolean")


# ------------------------------------------------------------------ bout en bout, faux lanceur


@pytest.fixture
def depot(tmp_path: Path) -> dict[str, Path]:
    aides, sources = tmp_path / "aides", tmp_path / "sources"
    aides.mkdir()
    shutil.copy(AIDES / f"{SLUG}.yaml", aides / f"{SLUG}.yaml")
    # Les instantanés d'avant le jour du test : la page « fraîche » est celle que
    # le lanceur écrit, pas un instantané que la veille aurait archivé ce jour-là.
    shutil.copytree(
        BACKEND / "data" / "sources" / SLUG,
        sources / SLUG,
        ignore=lambda _d, noms: [n for n in noms if n[:10] >= JOUR.isoformat()],
    )
    pending = tmp_path / "facts_pending.yaml"
    shutil.copy(BACKEND / "data" / "facts_pending.yaml", pending)
    return {"tmp": tmp_path, "aides": aides, "sources": sources, "pending": pending}


def _lanceur(resultat: dict[str, Any], modifier: Any = None) -> Any:
    def lancer(slug: str, sortie: Path, plafond: float, delai_s: float) -> rx.Lancement:
        y = sortie / "aides" / f"{slug}.yaml"
        if modifier is not None:
            d = charger_yaml(y.read_text(encoding="utf-8"))
            modifier(d)
            y.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (sortie / "appels.jsonl").write_text(
            json.dumps({"cout_usd": 0.05}) + "\n", encoding="utf-8"
        )
        return rx.Lancement(resultat, None, sortie, 1.0)

    return lancer


def _reextraire(depot: dict[str, Path], lanceur: Any, ecrire: bool = True) -> rx.Bilan:
    return rx.reextraire(
        SLUG,
        plafond=1.0,
        delai_s=60,
        jour=JOUR,
        etat="e",
        sorties=depot["tmp"] / "sorties",
        aides=depot["aides"],
        sources=depot["sources"],
        pending=depot["pending"],
        rebuts=depot["tmp"] / "rebuts",
        ecrire=ecrire,
        lanceur=lanceur,
    )


@pytest.mark.parametrize(
    ("resultat", "issue", "classe"),
    [
        ({"ok": True, "verification_indisponible": "429"}, "panne", "verification"),
        ({"ok": False, "echec_transitoire": True, "motif_echec": "réseau"}, "panne", "fournisseur"),
        ({"ok": True, "panne_contrat": "modele_substitue"}, "panne", "modele_substitue"),
        ({"ok": False, "hors_perimetre": ["metier", "compagnies"]}, "hors_perimetre", None),
    ],
)
def test_une_panne_ou_un_hors_perimetre_laisse_la_version_en_service(
    depot: dict[str, Path], resultat: dict[str, Any], issue: str, classe: str | None
) -> None:
    avant = (depot["aides"] / f"{SLUG}.yaml").read_bytes()
    b = _reextraire(depot, _lanceur(resultat))
    assert (b.issue, b.panne) == (issue, classe)
    assert (depot["aides"] / f"{SLUG}.yaml").read_bytes() == avant
    assert not (depot["tmp"] / "rebuts").exists()


def test_un_refus_range_la_tentative_en_rebut_et_garde_la_version_en_service(
    depot: dict[str, Path],
) -> None:
    avant = (depot["aides"] / f"{SLUG}.yaml").read_bytes()
    b = _reextraire(depot, _lanceur({"ok": False, "motif_echec": "lint rouge"}))
    assert b.issue == "refusee"
    assert (depot["aides"] / f"{SLUG}.yaml").read_bytes() == avant
    assert (depot["tmp"] / "rebuts" / SLUG / f"{JOUR.isoformat()}.yaml").exists()


def test_une_reextraction_identique_n_ecrit_rien(depot: dict[str, Path]) -> None:
    avant = (depot["aides"] / f"{SLUG}.yaml").read_bytes()
    b = _reextraire(depot, _lanceur({"ok": True}))
    assert b.issue == "inchangee" and b.cout_usd == pytest.approx(0.05)
    assert (depot["aides"] / f"{SLUG}.yaml").read_bytes() == avant


def test_une_aide_sans_yaml_en_service_n_est_jamais_reextraite(depot: dict[str, Path]) -> None:
    (depot["aides"] / f"{SLUG}.yaml").unlink()
    b = _reextraire(depot, _lanceur({"ok": True}))
    assert b.issue == "orpheline"


def test_une_echeance_lue_dans_la_page_fraiche_s_ecrit_par_plages(depot: dict[str, Path]) -> None:
    texte = (depot["aides"] / f"{SLUG}.yaml").read_text(encoding="utf-8")

    def nouvelle_echeance(d: dict[str, Any]) -> None:
        d["calendrier"] = {"permanent": False, "date_limite": dt.date(2027, 2, 12)}

    def lanceur(slug: str, sortie: Path, plafond: float, delai_s: float) -> rx.Lancement:
        frais = sortie / "sources" / slug / "2026-10-11-reglement.md"
        frais.write_text(
            "---\nurl: https://exemple.fr\n---\nDépôt jusqu'au 12 février 2027.\n", encoding="utf-8"
        )
        return _lanceur({"ok": True}, nouvelle_echeance)(slug, sortie, plafond, delai_s)

    b = _reextraire(depot, lanceur)
    assert b.issue == "acceptee", b.raison
    nouveau = (depot["aides"] / f"{SLUG}.yaml").read_text(encoding="utf-8")
    assert "date_limite: 2027-02-12" in nouveau and "fiche:" in nouveau
    assert nouveau.split("calendrier:")[0] == texte.split("calendrier:")[0]
    assert b.snapshots == ["2026-10-11-reglement.md"]
    assert "reextraction-fiche" in [c.sorte for c in b.cases]


# ------------------------------------------------------------------ contrat de l'agent


class _Spec:
    alias = "or-glm"


class _Req:
    spec = _Spec()
    label = "ingestion"


class _Usage:
    def __init__(self, cout: float | None) -> None:
        self.cost, self.prompt_tokens, self.completion_tokens, self.model_extra = cout, 10, 5, {}


class _Brut:
    def __init__(self, modele: str, cout: float | None) -> None:
        self.model, self.usage, self.model_extra = modele, _Usage(cout), {}


def test_le_contrat_arrete_l_aide_et_compte_un_cout_inconnu_a_son_plafond(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from providall.providers.openai_compat import ChatCompletionsAdapter

    from catalogue import agent
    from catalogue.registre import charger

    m = charger().modele("extraction")
    reponses = [
        _Brut("z-ai/glm-5.3-flash", None),
        _Brut("autre/modele", 0.001),
        _Brut("z-ai/glm-5.3-flash", 0.001),
    ]
    monkeypatch.setattr(ChatCompletionsAdapter, "send", lambda self, req, body: reponses.pop(0))
    releve = agent.Releve(plafond=10.0, modeles={"or-glm": m}, chemin=tmp_path / "appels.jsonl")
    agent.surveiller(releve)
    corps = {"messages": [{"role": "user", "content": "x" * 300}], "max_tokens": 1000}
    ChatCompletionsAdapter.send(None, _Req(), corps)  # type: ignore[arg-type]
    plafond = agent._plafond_appel(m, corps)
    assert releve.depense == pytest.approx(plafond)
    with pytest.raises(agent.Arret):
        ChatCompletionsAdapter.send(None, _Req(), corps)  # type: ignore[arg-type]
    assert releve.panne == "modele_substitue"
    with pytest.raises(agent.Arret):
        ChatCompletionsAdapter.send(None, _Req(), corps)  # type: ignore[arg-type]
    assert len(reponses) == 1  # le troisième appel n'est jamais parti
    lignes = [
        json.loads(x) for x in (tmp_path / "appels.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert lignes[0]["cout_compte"] == pytest.approx(plafond)
    assert rx.depense(tmp_path) == pytest.approx(plafond + 0.001)


def test_le_plafond_refuse_l_appel_qui_le_depasserait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from providall.providers.openai_compat import ChatCompletionsAdapter

    from catalogue import agent
    from catalogue.registre import charger

    monkeypatch.setattr(
        ChatCompletionsAdapter, "send", lambda self, req, body: pytest.fail("appel parti")
    )
    releve = agent.Releve(
        plafond=0.0001,
        modeles={"or-glm": charger().modele("extraction")},
        chemin=tmp_path / "a.jsonl",
    )
    agent.surveiller(releve)
    with pytest.raises(agent.Arret):
        ChatCompletionsAdapter.send(None, _Req(), {"messages": [], "max_tokens": 32000})  # type: ignore[arg-type]
    assert releve.panne == "budget"


def test_le_groupe_de_l_agent_est_tue_au_delai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    lances: list[Any] = []
    vrai = subprocess.Popen

    def popen(args: Any, **kw: Any) -> Any:
        p = vrai([sys.executable, "-c", "import time; time.sleep(60)"], **kw)
        lances.append(p)
        return p

    monkeypatch.setattr(rx.subprocess, "Popen", popen)
    lancement = rx.lancer("x", tmp_path, 1.0, 0.5)
    assert lancement.panne == "delai" and lancement.resultat is None
    assert lances[0].poll() is not None

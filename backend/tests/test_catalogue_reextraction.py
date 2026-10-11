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


def _retour(
    anciennes: list[dict[str, Any]], proposees: list[dict[str, Any]], **sections: Any
) -> rx.Retour:
    ancien = {"slug": "x", "calendrier": {"permanent": False}, "conditions": anciennes}
    agent = {
        "slug": "x",
        "calendrier": sections.get("calendrier", {"permanent": False}),
        "conditions": proposees,
    }
    return rx.retour("x", ancien, agent, BASE, FRAIS, {"fait_connu"}, "e")


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


def test_une_condition_nouvelle_s_ajoute_et_son_fait_neuf_devient_une_case() -> None:
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
    assert r.faits_neufs == ["fait_neuf"] and [k.sorte for k in r.cases] == ["H-fait"]


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
    assert [k.sorte for k in r.cases] == ["reextraction-proche"]


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
    shutil.copytree(BACKEND / "data" / "sources" / SLUG, sources / SLUG)
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

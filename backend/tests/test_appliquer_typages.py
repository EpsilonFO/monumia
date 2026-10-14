"""Application d'un plan de retypage condition par condition (scripts/appliquer_typages.py).

Ce que ces tests fixent :

  - seules les clés de TYPAGE de la condition visée changent ; `text`, `quote`,
    les commentaires et les autres conditions restent octet pour octet ;
  - `applies_if` n'est touché que si le plan le nomme (`null` le retire) ;
  - une entrée qui ne passe pas le schéma n'écrit rien.

Run from backend/:  uv run pytest tests/test_appliquer_typages.py
"""

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from appliquer_typages import appliquer  # noqa: E402

AIDE = """\
slug: aide-test
nom: Aide de test
organisme: Organisme
description: Une aide de test.
categorie: region
type: subvention
conditions:
# Un commentaire de relecture, à garder.
- id: depot-avant-travaux
  text: Le dossier doit être déposé avant le début des travaux.
  kind: info
  effect: info
  quote: avant le début des travaux
- id: beneficiaires
  text: 'Bénéficiaires : communes.'
  kind: user_fact
  effect: gate
  fact: statut_juridique_porteur
  predicate:
    in: [public_commune]
  applies_if:
    field: monument.proprietaire
    predicate: {in: [public_commune]}
  notes: Une note.
"""

JOUR = date(2026, 10, 14)


def _ecrire(tmp_path: Path) -> Path:
    chemin = tmp_path / "aide-test.yaml"
    chemin.write_text(AIDE, encoding="utf-8")
    return chemin


def test_seule_la_condition_visee_change(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path)
    plan = [
        {
            "ref": "aide-test#depot-avant-travaux",
            "kind": "user_fact",
            "effect": "gate",
            "fact": "etat_travaux",
            "predicate": {"in": ["non_commences", "aucun"]},
            "motif": "test.",
        }
    ]
    ecrits, erreurs = appliquer(plan, aides_dir=tmp_path, ecrire=True, jour=JOUR)
    assert (ecrits, erreurs) == (["aide-test"], [])
    texte = chemin.read_text(encoding="utf-8")
    assert "# Un commentaire de relecture, à garder." in texte
    # La seconde condition est restée octet pour octet.
    assert AIDE[AIDE.index("- id: beneficiaires") :] in texte
    cond = yaml.safe_load(texte)["conditions"][0]
    assert cond["fact"] == "etat_travaux"
    assert cond["predicate"] == {"in": ["non_commences", "aucun"]}
    assert cond["quote"] == "avant le début des travaux"
    assert "Retypé le 2026-10-14" in cond["notes"]


def test_applies_if_garde_sauf_si_le_plan_le_nomme(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path)
    base = {
        "ref": "aide-test#beneficiaires",
        "kind": "user_fact",
        "effect": "gate",
        "fact": "statut_juridique_porteur",
        "predicate": {"in": ["public_commune", "public_epci"]},
        "motif": "test.",
    }
    appliquer([base], aides_dir=tmp_path, ecrire=True, jour=JOUR)
    cond = yaml.safe_load(chemin.read_text(encoding="utf-8"))["conditions"][1]
    assert cond["applies_if"]["field"] == "monument.proprietaire"
    assert cond["notes"].startswith("Une note.")

    appliquer([{**base, "applies_if": None}], aides_dir=tmp_path, ecrire=True, jour=JOUR)
    cond = yaml.safe_load(chemin.read_text(encoding="utf-8"))["conditions"][1]
    assert "applies_if" not in cond


def test_un_typage_refuse_par_le_schema_n_ecrit_rien(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path)
    # user_fact sans prédicat : le schéma le refuse.
    plan = [{"ref": "aide-test#depot-avant-travaux", "kind": "user_fact", "motif": "test."}]
    ecrits, erreurs = appliquer(plan, aides_dir=tmp_path, ecrire=True, jour=JOUR)
    assert ecrits == [] and len(erreurs) == 1
    assert chemin.read_text(encoding="utf-8") == AIDE

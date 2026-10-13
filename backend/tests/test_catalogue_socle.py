"""Le socle du paquet `catalogue` : journal, registre, budget, rejeu."""

from __future__ import annotations

import json
import multiprocessing
import threading
from pathlib import Path

import httpx
import pytest
import yaml

from catalogue.budget import Budget, BudgetEpuise
from catalogue.journal import Evenement, Journal, JournalCorrompu, Vue, cle, empreinte
from catalogue.openrouter import Client, Panne
from catalogue.registre import REGISTRE, charger
from catalogue.rejeu import Enregistreur, empreinte_requete, transport_rejeu

# ------------------------------------------------------------------ journal


def _ecrire_beaucoup(dossier: str, prefixe: str, n: int) -> None:
    j = Journal(Path(dossier))
    for k in range(n):
        j.ajouter(
            Evenement(
                "decision",
                f"d:{prefixe}{k:04d}",
                decision="entree",
                t="2026-10-10T10:00:00+00:00",
                issue="ecarter",
            )
        )


def test_deux_processus_ne_melent_jamais_leurs_lignes(tmp_path: Path) -> None:
    contexte = multiprocessing.get_context("spawn")
    processus = [
        contexte.Process(target=_ecrire_beaucoup, args=(str(tmp_path), p, 200))
        for p in ("aa", "bb")
    ]
    for p in processus:
        p.start()
    for p in processus:
        p.join(timeout=60)
    evenements = list(Journal(tmp_path).lire())
    assert len(evenements) == 400
    assert {e.objet[:4] for e in evenements} == {"d:aa", "d:bb"}


def test_une_derniere_ligne_tronquee_est_ignoree_et_signalee(tmp_path: Path) -> None:
    j = Journal(tmp_path)
    j.ajouter(
        Evenement("decision", "d:000000000001", decision="entree", t="2026-10-10T10:00:00+00:00")
    )
    with (tmp_path / "2026-10.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"type": "decision", "objet": "d:00')
    evenements = list(j.lire())
    assert len(evenements) == 1
    assert j.lignes_ignorees == ["2026-10.jsonl : dernière ligne tronquée"]


def test_une_ligne_illisible_au_milieu_est_une_corruption(tmp_path: Path) -> None:
    (tmp_path / "2026-10.jsonl").write_text(
        "pas du json\n"
        + json.dumps({"type": "decision", "objet": "d:1", "t": "2026-10-10"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(JournalCorrompu):
        list(Journal(tmp_path).lire())


def test_les_mois_se_lisent_dans_l_ordre(tmp_path: Path) -> None:
    j = Journal(tmp_path)
    j.ajouter(Evenement("decision", "d:2", decision="entree", t="2026-11-02T00:00:00+00:00"))
    j.ajouter(Evenement("decision", "d:1", decision="entree", t="2026-10-30T00:00:00+00:00"))
    assert [e.objet for e in j.lire()] == ["d:1", "d:2"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10.jsonl", "2026-11.jsonl"]


def test_un_lot_garde_son_ordre_et_se_range_par_mois(tmp_path: Path) -> None:
    j = Journal(tmp_path)
    ecrits = j.ajouter_lot(
        [
            Evenement("import", "a:x", auteur="import", t="2026-07-02T10:00:00+00:00"),
            Evenement("import", "a:y", auteur="import", t="2026-09-01T10:00:00+00:00"),
            Evenement("import", "a:z", auteur="import", t="2026-07-30T10:00:00+00:00"),
            Evenement("contradiction", "a:x", auteur="import"),
        ]
    )
    assert ecrits[3].t  # horodaté à l'écriture
    assert sorted(p.name for p in tmp_path.iterdir())[:2] == ["2026-07.jsonl", "2026-09.jsonl"]
    assert [e.objet for e in j.lire()][:3] == ["a:x", "a:z", "a:y"]
    assert j.ajouter_lot([]) == []


def test_un_evenement_mal_forme_est_refuse() -> None:
    with pytest.raises(ValueError):
        Evenement("verdict", "d:1")
    with pytest.raises(ValueError):
        Evenement("decision", "slug-sans-prefixe")
    with pytest.raises(ValueError):
        Evenement("decision", "d:1", auteur="claude")


def test_la_memoire_reprend_une_decision_et_felix_prime(tmp_path: Path) -> None:
    j = Journal(tmp_path)
    k = cle("entree", "texte de la page", {"q": 1}, "typesafe/jev-1.13")
    j.ajouter(
        Evenement(
            "decision",
            "d:1",
            decision="entree",
            cle=k,
            issue="ecarter",
            t="2026-10-10T00:00:00+00:00",
        )
    )
    j.ajouter(
        Evenement("panne", "d:2", decision="entree", cle="autre", t="2026-10-10T00:00:01+00:00")
    )
    j.ajouter(
        Evenement(
            "felix",
            "d:1",
            decision="entree",
            auteur="felix",
            issue="admettre",
            t="2026-10-10T00:00:02+00:00",
        )
    )
    vue = Vue(j.lire())
    assert vue.memo(k) is not None and vue.memo(k).issue == "ecarter"  # type: ignore[union-attr]
    assert vue.memo("autre") is None  # une panne ne se mémorise jamais
    assert vue.issue("d:1", "entree") == "admettre"


def test_la_cle_ne_depend_pas_de_l_ordre_des_champs() -> None:
    assert cle({"a": 1, "b": 2}, "x") == cle({"b": 2, "a": 1}, "x")
    assert cle({"a": 1}, "x") != cle({"a": 2}, "x")
    assert len(empreinte("abc")) == 12


# ----------------------------------------------------------------- registre


def test_le_registre_livre_se_charge() -> None:
    r = charger()
    assert r.reglages.doute == "c"
    assert r.reglages.extraction == "agent"
    # Après I9a : la nouvelle chaîne tient veille, prospection et ingestion ; les
    # escalades attendent une case « reextraire » de Félix.
    assert r.proprietaires == {
        "veille": "nouvelle",
        "escalades": "ancienne",
        "prospection": "nouvelle",
        "ingestion": "nouvelle",
    }
    assert r.modele("decision").nom == "typesafe/jev-1.13"


def test_les_seuils_d_entree_valent_pour_les_questions_en_service() -> None:
    """Changer les questions ou la doctrine de Jev rend ses seuils « non calibrés »."""
    import veille_arbitre
    from prospection import arbitre, tri

    r = charger()
    e1 = r.decisions["E1-entree"].empreintes
    assert e1["questions"] == empreinte(
        json.dumps(arbitre.QUESTIONS, sort_keys=True, ensure_ascii=False)
    )
    assert e1["doctrine"] == empreinte(tri.doctrine())
    v1 = r.decisions["V1-garde"]
    assert v1.empreintes["questions"] == empreinte(
        json.dumps(veille_arbitre.QUESTIONS_MANDAT, sort_keys=True, ensure_ascii=False)
    )
    assert v1.seuils["escalade"] == veille_arbitre.SEUIL_GARDE
    assert (r.decisions["E1-entree"].seuils["bas"], r.decisions["E1-entree"].seuils["haut"]) == (
        arbitre.SEUIL_BAS,
        arbitre.SEUIL_HAUT,
    )


def test_un_registre_incoherent_est_refuse(tmp_path: Path) -> None:
    brut = yaml.safe_load(REGISTRE.read_text(encoding="utf-8"))
    brut["decisions"]["E1-entree"]["modele"] = "inconnu"
    chemin = tmp_path / "registre.yaml"
    chemin.write_text(yaml.safe_dump(brut, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError):
        charger(chemin)
    brut = yaml.safe_load(REGISTRE.read_text(encoding="utf-8"))
    del brut["proprietaires"]["veille"]
    chemin.write_text(yaml.safe_dump(brut, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError):
        charger(chemin)


# ------------------------------------------------------------------- budget


def test_le_budget_refuse_ce_qu_il_ne_peut_couvrir() -> None:
    b = Budget(1.0)
    r = b.reserver(0.6, "extraction")
    with pytest.raises(BudgetEpuise):
        b.reserver(0.5, "seconde")
    b.regler(r, 0.2)
    assert b.depense == pytest.approx(0.2)
    b.reserver(0.5, "seconde")


def test_un_cout_inconnu_compte_pour_sa_reservation() -> None:
    b = Budget(1.0)
    r = b.reserver(0.3)
    b.regler(r, None)
    assert b.depense == pytest.approx(0.3)
    assert b.couts_inconnus == 1
    with pytest.raises(ValueError):
        b.regler(r, 0.1)


def test_le_budget_tient_entre_fils() -> None:
    b = Budget(10.0)

    def travail() -> None:
        for _ in range(100):
            b.regler(b.reserver(0.01), 0.005)

    fils = [threading.Thread(target=travail) for _ in range(8)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert b.depense == pytest.approx(8 * 100 * 0.005)
    assert b.reserve == pytest.approx(0.0)


# -------------------------------------------------------------------- rejeu


def test_un_echange_enregistre_se_rejoue_et_l_inconnu_echoue() -> None:
    corps_reponse = {
        "model": "z-ai/glm-5.3-flash",
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "cost": 0.000001},
    }
    enregistreur = Enregistreur(
        httpx.MockTransport(lambda _r: httpx.Response(200, json=corps_reponse))
    )
    client = Client("cle", transport=enregistreur)
    assert client.completer("z-ai/glm-5.3-flash", [{"role": "user", "content": "x"}]).texte == "OK"
    assert len(enregistreur.enregistrements) == 1

    rejoue = Client("cle", transport=transport_rejeu(enregistreur.enregistrements))
    assert rejoue.completer("z-ai/glm-5.3-flash", [{"role": "user", "content": "x"}]).texte == "OK"
    with pytest.raises(Panne) as exc:
        rejoue.completer("z-ai/glm-5.3-flash", [{"role": "user", "content": "autre"}])
    assert exc.value.classe == "requete"


def test_l_empreinte_ignore_l_ordre_des_cles() -> None:
    assert empreinte_requete(b'{"a": 1, "b": 2}') == empreinte_requete(b'{"b": 2, "a": 1}')

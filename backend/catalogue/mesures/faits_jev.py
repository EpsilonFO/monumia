"""F1 et F2 : l'agent d'ingestion contre Jev, sur des étiquettes posées à l'aveugle (I0, M4).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.faits_jev preparer <dossier faits>
    uv run python -m catalogue.mesures.faits_jev jev <dossier faits>
    uv run python -m catalogue.mesures.faits_jev analyser <dossier faits> <etiquettes.json>

Le dossier vient de `catalogue.mesures.faits tirer --voisinage recherche`.

`preparer` écrit `etiquetage/f1.json` et `etiquetage/f2.json`, les conditions
telles que les verront les étiqueteurs : titre de l'aide, `text`, `quote` et,
pour F1, les faits candidats (les 20 voisins de la recherche de l'agent, plus le
fait qu'il a choisi quand ce fait existait déjà et n'en est pas), mêlés dans un
ordre tiré au hasard. Aucun champ ne dit ce qu'a fait l'agent.

`jev` (payant, plafond 0,10 $) pose à Jev, pour chaque condition :
- F1a : un `choice` parmi les 20 voisins, plus « aucun » (ce que verrait Jev en
  production, derrière la même recherche) ;
- F1b : le même parmi les candidats montrés aux étiqueteurs (le choix seul,
  recherche mise à part) ;
- F2 : un `choice` parmi critère, démarche, promesse, information, définitions
  de `TYPING.md` citées.
Sortie dans un sous-dossier neuf jev-<k>/ : reponses.jsonl.

`analyser` compare l'agent et Jev aux étiquettes finales : exactitude, paires
discordantes (McNemar exact), pondération par la probabilité d'inclusion pour
F2. Sortie : analyse.json et analyse.txt dans le dossier.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline import llm
from pipeline.decision import ClientDecision, ErreurDecision, choix

from catalogue.mesures.jeu_e import _lire_jsonl, _sous_dossier_neuf
from catalogue.mesures.stats import ponderee, wilson

GRAINE = 20261015
PLAFOND_USD = 0.10
RESERVE_APPEL_USD = 0.001
AUCUN = "aucun"

NATURES = {
    "critere": (
        "Un critère : ce que le propriétaire a ou n'a pas, et qu'il ne peut pas changer "
        "(statut juridique, protection, localisation, nature du projet, budget, fait passé "
        "et irréversible). Il se demande."
    ),
    "demarche": (
        "Une démarche : ce qu'il peut rendre vrai avant le dépôt (réaliser un audit ou un "
        "diagnostic, recourir à un architecte, adhérer, se référencer). Elle s'annonce, "
        "elle ne se demande pas."
    ),
    "promesse": (
        "Une promesse : ce qu'il signe au dossier (communiquer, créer du contenu, obtenir un "
        "label après travaux, associer les habitants). Jamais une question."
    ),
    "information": (
        "Aucune exigence pour le propriétaire : paramètre financier, modalité de dépôt ou de "
        "versement, pièce du dossier, obligation légale générale, redondance avec un champ "
        "structuré."
    ),
}
TEST_OPERANT = (
    "Test opérant (TYPING.md) : peut-il rendre l'exigence vraie avant le dépôt, par une "
    "démarche ponctuelle, sans changer de statut juridique, d'usage du lieu ni de projet ? "
    "Oui, c'est une démarche. Non, c'est un critère."
)
REGLE_DOUBLON = (
    "Deux faits sont le même fait dès qu'un propriétaire y répondrait toujours pareil. Un "
    "seuil différent n'y change rien (le prédicat le porte), un libellé plus précis non plus. "
    "Ce qui fait deux faits : deux territoires, deux listes officielles distinctes, deux "
    "portées (le bien, le chantier, le porteur), deux critères de polarité opposée."
)


def _candidats(ligne: dict[str, Any]) -> list[dict[str, Any]]:
    """Les 20 voisins, plus le fait existant de l'agent s'il n'en est pas."""
    voisins = [
        {k: v[k] for k in ("cle", "question", "type", "scope", "unit", "options")}
        for v in ligne["voisins"]
    ]
    cles = {v["cle"] for v in voisins}
    agent = ligne.get("fait_agent_definition")
    if not ligne.get("fait_neuf") and agent and agent["cle"] not in cles:
        voisins.append(
            {k: agent.get(k) for k in ("cle", "question", "type", "scope", "unit", "options")}
        )
    return voisins


def _description(c: dict[str, Any]) -> str:
    morceaux = [c["question"], f"({c['type']}, portée {c['scope']}"]
    if c.get("unit"):
        morceaux[-1] += f", unité {c['unit']}"
    morceaux[-1] += ")"
    if c.get("options"):
        morceaux.append(
            "options : "
            + ", ".join(
                o.get("id", str(o)) if isinstance(o, dict) else str(o) for o in c["options"]
            )
        )
    return " ".join(morceaux)


def preparer(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    sortie = dossier / "etiquetage"
    sortie.mkdir(exist_ok=True)
    rng = random.Random(GRAINE)
    f1 = []
    for ligne in _lire_jsonl(dossier / "f1.jsonl"):
        candidats = _candidats(ligne)
        rng.shuffle(candidats)
        f1.append(
            {
                "id": ligne["id"],
                "titre_aide": ligne["titre_aide"],
                "text": ligne["text"],
                "quote": ligne["quote"],
                "candidats": candidats,
            }
        )
    f2 = [
        {"id": x["id"], "titre_aide": x["titre_aide"], "text": x["text"], "quote": x["quote"]}
        for x in _lire_jsonl(dossier / "f2.jsonl")
    ]
    (sortie / "f1.json").write_text(json.dumps(f1, ensure_ascii=False, indent=1), encoding="utf-8")
    (sortie / "f2.json").write_text(json.dumps(f2, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sortie} : F1 {len(f1)} conditions, F2 {len(f2)}")
    return 0


# --------------------------------------------------------------------------
# jev
# --------------------------------------------------------------------------


def _question_f1(candidats: list[dict[str, Any]]) -> dict[str, Any]:
    criteres = {c["cle"]: _description(c) for c in candidats}
    criteres[AUCUN] = (
        "Aucun de ces faits ne pose la question que la condition pose au propriétaire."
    )
    return choix(
        "Parmi ces faits, lequel pose au propriétaire la question que cette condition lui pose ?",
        criteres,
    )


QUESTION_F2 = {
    "nature": choix(
        "Pour le propriétaire du monument, cette condition est-elle un critère, une démarche, "
        "une promesse, ou n'exige-t-elle rien de lui ?",
        NATURES,
    )
}


def _etat(ligne: dict[str, Any], regle: str) -> dict[str, Any]:
    return {
        "regle": regle,
        "condition": {
            "aide": ligne["titre_aide"],
            "texte": ligne["text"],
            "citation": ligne["quote"],
        },
    }


def _decider(
    client: ClientDecision, etat: dict[str, Any], questions: dict[str, Any]
) -> dict[str, Any]:
    for essai in range(2):
        try:
            d = client.decider(etat, questions)
            sortie: dict[str, Any] = {"cout_usd": d.cout_usd, "modele": d.modele}
            for nom, r in d.reponses.items():
                if not r.probabilites:
                    raise ErreurDecision(f"{nom} sans probabilités")
                sortie[nom] = {"choix": r.choix, "probabilites": r.probabilites}
            return sortie
        except ErreurDecision as exc:
            derniere = f"essai {essai + 1} : {exc}"
            time.sleep(3)
    return {"panne": derniere}


def jev(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    sortie = _sous_dossier_neuf(dossier, "jev")
    llm.charger_env()
    client = ClientDecision()
    depense = 0.0
    lignes = 0
    with (sortie / "reponses.jsonl").open("w", encoding="utf-8") as f:
        for ligne in _lire_jsonl(dossier / "f1.jsonl"):
            if depense + 2 * RESERVE_APPEL_USD > PLAFOND_USD:
                print("plafond atteint")
                break
            voisins = [
                {k: v[k] for k in ("cle", "question", "type", "scope", "unit", "options")}
                for v in ligne["voisins"]
            ]
            a = _decider(client, _etat(ligne, REGLE_DOUBLON), {"fait": _question_f1(voisins)})
            b = _decider(
                client, _etat(ligne, REGLE_DOUBLON), {"fait": _question_f1(_candidats(ligne))}
            )
            for nom, r in (("f1a", a), ("f1b", b)):
                depense += r.get("cout_usd") or RESERVE_APPEL_USD
                f.write(
                    json.dumps({"id": ligne["id"], "decision": nom, **r}, ensure_ascii=False) + "\n"
                )
                lignes += 1
        for ligne in _lire_jsonl(dossier / "f2.jsonl"):
            if depense + RESERVE_APPEL_USD > PLAFOND_USD:
                print("plafond atteint")
                break
            r = _decider(client, _etat(ligne, TEST_OPERANT), QUESTION_F2)
            depense += r.get("cout_usd") or RESERVE_APPEL_USD
            f.write(
                json.dumps({"id": ligne["id"], "decision": "f2", **r}, ensure_ascii=False) + "\n"
            )
            lignes += 1
    client.fermer()
    print(f"{sortie} : {lignes} décisions, dépense comptée {depense:.4f} $")
    return 0


# --------------------------------------------------------------------------
# analyser
# --------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> float:
    """p bilatéral du test de McNemar exact sur b et c paires discordantes."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    queue = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * queue)


def _nature_agent(ligne: dict[str, Any]) -> str:
    """Ce que le typage de l'agent dit de la condition, sur les deux natures qui comptent."""
    return (
        "critere" if ligne["kind"] == "user_fact" and ligne["effect"] == "gate" else "non_critere"
    )


def analyser(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    etiquettes = json.loads(Path(args.etiquettes).read_text(encoding="utf-8"))
    f1_lab = {e["id"]: e for e in etiquettes.get("f1", [])}
    f2_lab = {e["id"]: e for e in etiquettes.get("f2", [])}
    reponses: dict[tuple[str, str], dict[str, Any]] = {}
    for chemin in sorted(dossier.glob("jev-*/reponses.jsonl"))[:1]:
        for r in _lire_jsonl(chemin):
            reponses[(r["id"], r["decision"])] = r
    resultat: dict[str, Any] = {}
    texte: list[str] = []

    # F1
    lignes = {x["id"]: x for x in _lire_jsonl(dossier / "f1.jsonl")}
    ids = [i for i in lignes if i in f1_lab]
    exact = {"agent": [], "f1a": [], "f1b": []}
    for i in ids:
        lab = f1_lab[i]
        bons = {lab["choix"], *lab.get("acceptables", [])}
        agent = AUCUN if lignes[i]["fait_neuf"] else lignes[i]["fait_agent"]
        exact["agent"].append(agent in bons)
        for nom in ("f1a", "f1b"):
            r = reponses.get((i, nom), {})
            choix_jev = (r.get("fait") or {}).get("choix")
            exact[nom].append(choix_jev in bons if choix_jev else False)
    resultat["f1"] = {"conditions": len(ids)}
    for nom, v in exact.items():
        k = sum(v)
        resultat["f1"][nom] = wilson(k, len(v)).texte()
    for nom in ("f1a", "f1b"):
        b = sum(1 for a, j in zip(exact["agent"], exact[nom], strict=True) if a and not j)
        c = sum(1 for a, j in zip(exact["agent"], exact[nom], strict=True) if j and not a)
        resultat["f1"][f"agent_contre_{nom}"] = {
            "agent_seul_juste": b,
            "jev_seul_juste": c,
            "p": mcnemar_exact(b, c),
        }
    # Atteignables : le bon fait est parmi les 20 voisins de la recherche, ou c'est
    # « aucun ». Ailleurs, Jev parmi les voisins ne peut pas l'atteindre, et
    # l'écart mesure la recherche, pas le choix (relecture adverse du 2026-10-10).
    atteignables = [
        k
        for k, i in enumerate(ids)
        if f1_lab[i]["choix"] == AUCUN
        or f1_lab[i]["choix"] in {v["cle"] for v in lignes[i]["voisins"]}
    ]
    bloc_att: dict[str, Any] = {"conditions": len(atteignables)}
    for nom in exact:
        bloc_att[nom] = sum(exact[nom][k] for k in atteignables)
    for nom in ("f1a", "f1b"):
        b2 = sum(1 for k in atteignables if exact["agent"][k] and not exact[nom][k])
        c2 = sum(1 for k in atteignables if exact[nom][k] and not exact["agent"][k])
        bloc_att[f"agent_contre_{nom}"] = {
            "agent_seul_juste": b2,
            "jev_seul_juste": c2,
            "p": mcnemar_exact(b2, c2),
        }
    resultat["f1"]["atteignables"] = bloc_att
    resultat["f1"]["etiquettes_aucun"] = sum(1 for i in ids if f1_lab[i]["choix"] == AUCUN)
    resultat["f1"]["agent_fait_neuf_alors_qu_un_existant_convenait"] = sum(
        1 for i in ids if lignes[i]["fait_neuf"] and f1_lab[i]["choix"] != AUCUN
    )
    texte.append(f"F1, {len(ids)} conditions : {json.dumps(resultat['f1'], ensure_ascii=False)}")

    # F2
    lignes2 = {x["id"]: x for x in _lire_jsonl(dossier / "f2.jsonl")}
    ids2 = [i for i in lignes2 if i in f2_lab]
    cas_agent, cas_jev = [], []
    b = c = 0
    for i in ids2:
        verite = "critere" if f2_lab[i]["nature"] == "critere" else "non_critere"
        p = 1.0 / lignes2[i]["p_inclusion"]
        juste_agent = _nature_agent(lignes2[i]) == verite
        r = reponses.get((i, "f2"), {})
        choix_jev = (r.get("nature") or {}).get("choix")
        juste_jev = (
            choix_jev is not None
            and ("critere" if choix_jev == "critere" else "non_critere") == verite
        )
        cas_agent.append((juste_agent, p))
        cas_jev.append((juste_jev, p))
        b += juste_agent and not juste_jev
        c += juste_jev and not juste_agent
    hors_mc = [k for k, i in enumerate(ids2) if lignes2[i]["strate"] != "manual_check"]
    resultat_hors_mc = {
        "agent": ponderee([cas_agent[k] for k in hors_mc]).texte(pondere=True),
        "jev": ponderee([cas_jev[k] for k in hors_mc]).texte(pondere=True),
    }
    resultat["f2"] = {
        "conditions": len(ids2),
        # Un `manual_check` sur un critère n'est pas une erreur par construction
        # (TYPING, arbre, étape 4) : la comparaison binaire se lit sans cette strate.
        "exact_pondere_hors_manual_check": resultat_hors_mc,
        "agent_exact_pondere": ponderee(cas_agent).texte(pondere=True),
        "jev_exact_pondere": ponderee(cas_jev).texte(pondere=True),
        "agent_seul_juste": b,
        "jev_seul_juste": c,
        "p": mcnemar_exact(b, c),
        "natures": {
            n: sum(1 for i in ids2 if f2_lab[i]["nature"] == n) for n in (*NATURES, "indecis")
        },
        "par_strate": {},
    }
    for strate in sorted({lignes2[i]["strate"] for i in ids2}):
        s = [i for i in ids2 if lignes2[i]["strate"] == strate]
        resultat["f2"]["par_strate"][strate] = {
            "conditions": len(s),
            "etiquettes": {n: sum(1 for i in s if f2_lab[i]["nature"] == n) for n in NATURES},
            "agent_juste": sum(
                1
                for i in s
                if _nature_agent(lignes2[i])
                == ("critere" if f2_lab[i]["nature"] == "critere" else "non_critere")
            ),
            "jev_choix": dict(
                Counter(
                    ((reponses.get((i, "f2"), {}).get("nature") or {}).get("choix") or "panne")
                    for i in s
                )
            ),
        }
    # La décision de R : parmi les conditions en gate (`user_fact` + `gate`), celles
    # qui ne sont pas des critères (démarche, promesse, information) écartent à
    # tort. Un `manual_check` sur un critère n'est pas une erreur en soi : TYPING
    # y renvoie un critère qui ne mérite pas de fait neuf (arbre, étape 4).
    gates = [i for i in ids2 if lignes2[i]["strate"] == "user_fact_gate"]
    a_tort = [i for i in gates if f2_lab[i]["nature"] != "critere"]
    # Deux étiquettes « information » portent sur une énumération de bénéficiaires,
    # que TYPING.md (« Les bénéficiaires et le porteur ») type en gate `in` sur
    # `statut_juridique_porteur` : lecture corrigée par la doctrine, donnée à côté.
    doctrine = [i for i in a_tort if lignes2[i].get("fait_agent") != "statut_juridique_porteur"]
    signalees = [
        i
        for i in gates
        if ((reponses.get((i, "f2"), {}).get("nature") or {}).get("choix") or "critere")
        != "critere"
    ]
    resultat["f2"]["gates"] = {
        "conditions": len(gates),
        "gates_a_tort_selon_les_etiquettes": f"{len(a_tort)}/{len(gates)} ; "
        + wilson(len(a_tort), len(gates)).texte(),
        "gates_a_tort_lecture_doctrine": f"{len(doctrine)}/{len(gates)} ; "
        + wilson(len(doctrine), len(gates)).texte(),
        "probabilites_jev_des_gates_a_tort": {
            i: (reponses.get((i, "f2"), {}).get("nature") or {}).get("probabilites") for i in a_tort
        },
        "jev_signale": len(signalees),
        "jev_signale_a_raison": sum(1 for i in signalees if i in a_tort),
        "jev_signale_a_tort": sum(1 for i in signalees if i not in a_tort),
        "gates_a_tort": [
            {"id": i, "nature": f2_lab[i]["nature"], "texte": lignes2[i]["text"][:160]}
            for i in a_tort
        ],
    }
    texte.append(f"F2, {len(ids2)} conditions : {json.dumps(resultat['f2'], ensure_ascii=False)}")
    (dossier / "analyse.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (dossier / "analyse.txt").write_text("\n".join(texte) + "\n", encoding="utf-8")
    print("\n".join(texte))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    for nom, fonction in (("preparer", preparer), ("jev", jev)):
        p = sous.add_parser(nom)
        p.add_argument("dossier")
        p.set_defaults(fonction=fonction)
    p = sous.add_parser("analyser")
    p.add_argument("dossier")
    p.add_argument("etiquettes")
    p.set_defaults(fonction=analyser)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())

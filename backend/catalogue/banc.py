"""La session mensuelle d'étiquetage : exporter des cas à juger à l'aveugle, relire les étiquettes.

    uv run --no-sync python -m catalogue banc V1-garde --preparer <dossier>
    uv run --no-sync python -m catalogue banc V1-garde --lire <fichier.json>

La garde de veille laisse dans sa zone prudente (notes de 0,05 à 0,45) les
« inchangé » qu'elle ne sait pas trancher : la référence n'avance pas, rien ne
se perd, mais personne ne les juge. Une fois par mois, Félix lance une session
Claude Code qui les étiquette (procédure : `docs/refonte-pipeline/planification.md`).

`--preparer` écrit `<dossier>/cas.json` : chaque cas de la zone prudente encore
en attente, avec l'état exact que Jev a vu (fiche, diff, résumé du lecteur),
sans la note de Jev ni son issue, pour un jugement à l'aveugle. `--lire` prend
les étiquettes rendues (`[{"cas": ..., "etiquette": "touche" | "ne touche pas"}]`)
et les ajoute aux étalons de `V1-garde`, avec la note de Jev relue au journal :
la prochaine `calibrer --decision V1-garde` en tient compte.

Les étiquettes ne décident de rien par elles-mêmes : un changement réel reste
dû dans la veille jusqu'à une réponse de Félix ou une ré-extraction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalogue import calibrer
from catalogue.journal import Evenement, Journal
from catalogue.veille import BLOBS

PROVENANCE = "claude-aveugle"


def cas_zone_prudente(evenements: list[Evenement]) -> dict[str, Evenement]:
    """Le dernier jugement de garde de chaque aide, s'il est en zone prudente et que la référence n'a pas avancé depuis."""
    garde: dict[str, Evenement] = {}
    for e in evenements:
        if e.type == "decision" and e.decision == "V1-garde":
            garde[e.objet] = e
        elif (
            e.decision == "base"
            and e.type == "decision"
            and e.objet in garde
            and e.t >= garde[e.objet].t
        ):
            del garde[e.objet]
    return {
        e.cle: e
        for e in garde.values()
        if e.issue == "prudente" and e.cle and e.donnees.get("etat_jev")
    }


def preparer(journal: Journal, dossier: Path, blobs: Path = BLOBS) -> int:
    dossier.mkdir(parents=True, exist_ok=False)
    cas = []
    for cle_cas, e in sorted(cas_zone_prudente(list(journal.lire())).items()):
        blob = blobs / e.donnees["etat_jev"]
        if not blob.exists():
            continue
        cas.append(
            {
                "cas": cle_cas,
                "aide": e.objet.removeprefix("a:"),
                "etat": json.loads(blob.read_text(encoding="utf-8")),
            }
        )
    (dossier / "cas.json").write_text(
        json.dumps(cas, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return len(cas)


def lire(journal: Journal, fichier: Path, blobs: Path = BLOBS) -> int:
    """Ajoute aux étalons de la garde les cas étiquetés ; rend le nombre d'étalons ajoutés."""
    etiquettes: list[dict[str, Any]] = json.loads(fichier.read_text(encoding="utf-8"))
    jugements = {
        e.cle: e
        for e in journal.lire()
        if e.type == "decision" and e.decision == "V1-garde" and e.cle
    }
    chemin = calibrer.ETALONS / "V1-garde.jsonl"
    etalons = calibrer.lire("V1-garde") if chemin.exists() else []
    deja = {e.cas for e in etalons}
    ajoutes = 0
    for x in etiquettes:
        if x["etiquette"] not in ("touche", "ne touche pas") or x["cas"] in deja:
            continue
        e = jugements.get(x["cas"])
        if e is None or not e.modele:
            continue
        etat = json.loads((blobs / e.donnees["etat_jev"]).read_text(encoding="utf-8"))
        etalons.append(
            calibrer.Etalon(
                cas=x["cas"],
                etiquette=int(x["etiquette"] == "touche"),
                provenance=PROVENANCE,
                etat=etat,
                p={e.modele: float(e.donnees["p"])},
            )
        )
        deja.add(x["cas"])
        ajoutes += 1
    if ajoutes:
        calibrer.ecrire("V1-garde", etalons)
        # L'étiquette fait sortir le cas de la zone prudente au passage suivant :
        # « ne touche pas » fait avancer la référence, « touche » ouvre une case.
        journal.ajouter_lot(
            Evenement(
                "decision",
                jugements[x["cas"]].objet,
                decision="V1-etiquette",
                decideur="claude",
                issue=x["etiquette"],
                cle=f"etiquette:{x['cas']}",
                donnees={"garde": x["cas"], "provenance": PROVENANCE},
            )
            for x in etiquettes
            if x["cas"] in jugements and x["cas"] in {e.cas for e in etalons[-ajoutes:]}
        )
    return ajoutes


def commande(decision: str, journal: Path, preparer_dans: Path | None, lire_de: Path | None) -> int:
    if decision != "V1-garde":
        print(f"{decision} : aucun banc branché (seule V1-garde l'est).")
        return 2
    j = Journal(journal)
    if preparer_dans is not None:
        n = preparer(j, preparer_dans)
        print(f"{n} cas à étiqueter : {preparer_dans / 'cas.json'}")
    if lire_de is not None:
        print(f"{lire(j, lire_de)} étalon(s) ajouté(s) à V1-garde")
    return 0

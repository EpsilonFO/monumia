"""L'agent d'ingestion sous contrat (section 5 d'`architecture.md`), côté processus enfant.

    <python> -m catalogue.agent --slug <slug> --sortie <dossier> --plafond <$>

Lancé par `catalogue.reextraction` dans son propre groupe de processus. Il fait
tourner l'agent d'ingestion actuel (`ingestion.worker.ingerer_aide`) sans
changer son code, dans un dossier de sortie que le parent a préparé (copie du
YAML en service et de ses instantanés), et lui impose le contrat :

- **modèles du registre** : extraction et vérification par leur alias
  providall, jamais par les variables `LLM_MODEL_*` ;
- **chaque tentative relevée** (`<sortie>/appels.jsonl`), réussie ou non, avec
  le modèle servi, le fournisseur et le coût facturé par OpenRouter ; un modèle
  servi hors de la liste acceptée arrête l'aide (panne `modele_substitue`) ;
- **plafond dur** : avant chaque appel, le coût relevé plus le coût plafond de
  l'appel (entrée estimée et sortie maximale au tarif du registre) doivent
  tenir sous `--plafond` ; sinon l'aide s'arrête (panne `budget`). Un coût non
  facturé compte pour son plafond ;
- **vérificateur indisponible = panne** : l'agent actuel en fait un reproche
  « mineur » et l'aide passe (25 aides acceptées ainsi) ; ici l'issue est une
  panne `verification`, et rien n'est accepté ;
- **le parent disparu, l'enfant s'arrête** (lecture de `getppid()` chaque
  seconde) ;
- **l'issue est écrite en JSON** (`<sortie>/resultat.json`), jamais lue dans un
  code de sortie, qui vaut 1 aussi bien pour une panne que pour un refus.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from catalogue.registre import Modele, charger


class Arret(RuntimeError):
    """Arrêt imposé par le contrat : budget épuisé ou modèle substitué."""


@dataclasses.dataclass
class Releve:
    plafond: float
    modeles: dict[str, Modele]  # alias providall -> modèle du registre
    chemin: Path
    # Un budget partagé (celui du run) : le plafond borne la somme des deux.
    budget: Any = None
    depense: float = 0.0
    panne: str | None = None
    verification_indisponible: str | None = None

    def __post_init__(self) -> None:
        self._verrou = threading.Lock()

    def ecrire(self, ligne: dict[str, Any]) -> None:
        with self._verrou, self.chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


def _plafond_appel(m: Modele, body: dict[str, Any]) -> float:
    entree = len(json.dumps(body.get("messages") or [], ensure_ascii=False)) // 3
    sortie = int(body.get("max_tokens") or body.get("max_completion_tokens") or 32_000)
    return m.plafond_usd(entree, sortie)


def surveiller(releve: Releve) -> None:
    """Enveloppe l'envoi de providall : budget, modèle servi, coût facturé, trace."""
    from providall.providers.openai_compat import ChatCompletionsAdapter

    envoyer = ChatCompletionsAdapter.send

    def send(self: Any, req: Any, body: dict[str, Any]) -> Any:
        alias = req.spec.alias
        m = releve.modeles.get(alias)
        ligne: dict[str, Any] = {
            "t": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "alias": alias,
            "role": req.label,
        }
        if releve.panne in ("modele_substitue", "budget", "modele_hors_registre"):
            # Le contrat a déjà arrêté l'aide : aucun appel de plus, même de sauvetage.
            ligne.update(arret=releve.panne)
            releve.ecrire(ligne)
            raise Arret(f"aide arrêtée par le contrat ({releve.panne})")
        if m is None:
            releve.panne = releve.panne or "modele_hors_registre"
            ligne.update(arret="modele_hors_registre")
            releve.ecrire(ligne)
            raise Arret(f"modèle hors registre : {alias}")
        plafond = _plafond_appel(m, body)
        autre = (
            (releve.budget.depense + releve.budget.reserve) if releve.budget is not None else 0.0
        )
        if releve.depense + autre + plafond > releve.plafond:
            releve.panne = releve.panne or "budget"
            ligne.update(arret="budget", plafond_appel=plafond)
            releve.ecrire(ligne)
            raise Arret(
                f"budget de l'aide : {releve.depense:.4f} $ + {plafond:.4f} $ > {releve.plafond} $"
            )
        debut = time.monotonic()
        try:
            brut = envoyer(self, req, body)
        except Exception as exc:
            # Une tentative ratée a pu être facturée : elle compte pour son plafond.
            releve.depense += plafond
            ligne.update(erreur=f"{type(exc).__name__}: {str(exc)[:300]}", cout_compte=plafond)
            ligne["duree_s"] = round(time.monotonic() - debut, 2)
            releve.ecrire(ligne)
            raise
        usage = getattr(brut, "usage", None)
        extra = getattr(usage, "model_extra", None) or {}
        cout = getattr(usage, "cost", None)
        if cout is None:
            cout = extra.get("cost")
        servi = getattr(brut, "model", None) or ""
        releve.depense += float(cout) if cout is not None else plafond
        if cout is None:
            ligne["cout_compte"] = plafond
        ligne.update(
            modele_servi=servi,
            fournisseur=(getattr(brut, "model_extra", None) or {}).get("provider"),
            cout_usd=cout,
            jetons_entree=getattr(usage, "prompt_tokens", None),
            jetons_sortie=getattr(usage, "completion_tokens", None),
            duree_s=round(time.monotonic() - debut, 2),
        )
        releve.ecrire(ligne)
        if servi not in m.acceptes:
            releve.panne = releve.panne or "modele_substitue"
            raise Arret(f"modèle servi « {servi} », accepté : {m.acceptes}")
        return brut

    ChatCompletionsAdapter.send = send  # type: ignore[method-assign]


def surveiller_verification(releve: Releve) -> None:
    """Un vérificateur indisponible ne vaut plus vérification : c'est une panne."""
    from ingestion import outils

    verifier = outils.verifier

    def enveloppe(*args: Any, **kwargs: Any) -> Any:
        rapport, rendu = verifier(*args, **kwargs)
        if getattr(rapport, "commentaire", "") == "vérificateur indisponible":
            releve.verification_indisponible = rapport.problemes[0].description[:300]
        return rapport, rendu

    outils.verifier = enveloppe  # type: ignore[assignment]


def lint_par_ecart(sortie: Path, slug: str) -> None:
    """Le lint de fin d'aide de l'agent ne refuse que les erreurs que la ré-extraction introduit.

    Sans cela, une aide qui porte une dette connue (261 citations absentes sur
    77 aides, 218 conditions sans `effect`...) échouerait dans l'agent à chaque
    ré-extraction. Les erreurs de la version en service (`<sortie>/en-service/`)
    sont lues une fois ; une erreur se compare sans les valeurs qu'elle cite.
    """
    import dataclasses as dc

    from ingestion import outils, worker

    from catalogue.reextraction import erreurs_nouvelles

    lint = worker.lancer_lint
    avant: list[str] | None = None

    def enveloppe(slugs: Any, **kwargs: Any) -> Any:
        nonlocal avant
        rapport = lint(slugs, **kwargs)
        if (sortie / "en-service" / f"{slug}.yaml").exists():
            if avant is None:
                avant = list(lint([slug], **{**kwargs, "aides_dir": sortie / "en-service"}).erreurs)
            rapport = dc.replace(rapport, erreurs=erreurs_nouvelles(avant, list(rapport.erreurs)))
        return rapport

    worker.lancer_lint = enveloppe  # type: ignore[assignment]
    # Le lint que l'agent lance lui-même pendant sa boucle : sans l'écart, il
    # verrait la dette connue en erreur et dépenserait à la « corriger ».
    if hasattr(outils, "lancer_lint"):
        outils.lancer_lint = enveloppe  # type: ignore[attr-defined]


def veiller_parent() -> None:
    parent = os.getppid()

    def boucle() -> None:
        while True:
            if os.getppid() != parent:
                os._exit(70)
            time.sleep(1)

    threading.Thread(target=boucle, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m catalogue.agent")
    p.add_argument("--slug", required=True)
    p.add_argument("--sortie", type=Path, required=True)
    p.add_argument("--plafond", type=float, required=True)
    args = p.parse_args(argv)
    veiller_parent()

    from ingerer import _taches_directes
    from ingestion.boucle import Limites
    from ingestion.worker import ConfigIngestion, ContextePartage, ingerer_aide
    from pipeline.llm import charger_env, enregistrer_tarif

    charger_env()
    reg = charger()
    extraction, verification = reg.modele("extraction"), reg.modele("verification")
    assert extraction.alias_providall and verification.alias_providall
    for m in (extraction, verification):
        assert m.alias_providall is not None
        enregistrer_tarif(m.alias_providall, m.prix_entree, m.prix_sortie)
    releve = Releve(
        plafond=args.plafond,
        modeles={
            extraction.alias_providall: extraction,
            verification.alias_providall: verification,
        },
        chemin=args.sortie / "appels.jsonl",
    )
    surveiller(releve)
    surveiller_verification(releve)
    lint_par_ecart(args.sortie, args.slug)

    # Une aide neuve arrive avec sa tâche (`tache.json`, écrite par le parent) ;
    # une ré-extraction prend l'URL du YAML en service copié dans la sortie.
    if (args.sortie / "tache.json").exists():
        from pipeline.etat import Tache

        tache = Tache.model_validate_json((args.sortie / "tache.json").read_text(encoding="utf-8"))
        taches = {args.slug: tache}
    else:
        from aides_schema import load_aide

        url = load_aide(args.sortie / "aides" / f"{args.slug}.yaml").source.url_officielle
        taches = _taches_directes(
            argparse.Namespace(slug=[args.slug], url=[url] if url else [], pdf=[])
        )
    config = ConfigIngestion(
        modele=extraction.alias_providall,
        modele_verif=verification.alias_providall,
        # Le budget de l'agent sur ses seuls tours d'extraction ; le plafond dur
        # du contrat, vérification comprise, est tenu par l'enveloppe.
        limites=Limites(budget_usd=args.plafond / 1.25),
        sortie=args.sortie,
    )
    contexte = ContextePartage.construire(config.atelier(args.slug))
    r = ingerer_aide(args.slug, taches[args.slug], config, contexte=contexte)
    sortie = dataclasses.asdict(r) | {
        "panne_contrat": releve.panne,
        "verification_indisponible": releve.verification_indisponible,
        "depense_relevee": round(releve.depense, 6),
    }
    (args.sortie / "resultat.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

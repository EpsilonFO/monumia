"""L'entrée au catalogue : une page relève-t-elle du catalogue ? (incrément I6, `E1-entree`).

La règle de production est portée dans son état exact, parce qu'aucun
remplaçant ne l'a battue sur le jeu E (`2026-10-10-banc-E.md`) :

1. `C-inexploitable` d'abord : une page sans texte à juger (menus seuls, image
   décodée en texte, coquille de page rendue en JavaScript) n'est soumise à
   aucun décideur ; c'est une panne `contenu_inexploitable`, jamais mémorisée.
   Sur E, 33 pages sur 271 n'avaient rien à juger et arrivaient jusqu'à Jev.
2. Jev, par `prospection.arbitre.arbitrer` (mêmes questions, même état, mêmes
   bandes 0,12 et 0,57), appelé par le client neuf : une réponse sans
   probabilité est une panne, plus une probabilité nulle.
3. Hors de la bande basse, la lecture par le LLM, avec la consigne et le prompt
   de `prospection.lecture`, corrigée par `_appliquer_arbitrage`.
4. Le code décide : `pipeline.etat.motif_non_promotion` (admise si aucun motif),
   écartée si le test du destinataire échoue sans indétermination, sinon doute
   (décision 3 : le doute attend Félix, réglage `doute: c`).

Chaque jugement est au journal (probabilités, lecture, coût, modèle servi) et
se reprend sans appel à entrées identiques ; une panne ne s'y mémorise pas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pipeline import decision as pd
from pipeline import etat
from prospection import arbitre, lecture, tri

from catalogue.budget import Budget
from catalogue.journal import Evenement, Vue, cle, empreinte
from catalogue.openrouter import Client, Panne
from catalogue.registre import BACKEND, Registre

VERSION = "entree@1"
EMPREINTE_QUESTIONS = empreinte(json.dumps(arbitre.QUESTIONS, sort_keys=True, ensure_ascii=False))

# C-inexploitable : en dessous, la page n'a rien à juger. Réglé sur les 33 pages
# sans contenu de E (`mesures/entree_controle.py`, rapport d'I6).
MIN_CARACTERES_UTILES = 400
_LIEN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_BINAIRE = re.compile(r"[\x00-\x08\x0e-\x1f�]")


def caracteres_utiles(texte: str) -> int:
    """Les caractères de texte courant : liens réduits à leur libellé, lignes courtes (menus) ignorées."""
    utiles = 0
    for ligne in texte.splitlines():
        nu = _LIEN.sub(lambda m: m.group(1), ligne).strip(" #*-|>\t")
        if len(nu.split()) >= 8:
            utiles += len(nu)
    return utiles


def inexploitable(
    texte: str, url: str = "", textes_vus: dict[tuple[str, str], str] | None = None
) -> str | None:
    """Le motif pour lequel une page n'a rien à juger, ou `None`.

    `textes_vus` ((hôte, empreinte du texte) -> URL) repère une page dont le texte
    extrait est celui d'une autre URL du même site : le gabarit seul, le contenu
    venant après la troncature (17 des 33 pages sans contenu de E, dont 16 du
    Gers). La première du groupe passe ; les suivantes s'arrêtent.
    """
    if textes_vus is not None and texte.strip():
        from urllib.parse import urlsplit

        cle_texte = (urlsplit(url).netloc.lower(), empreinte(texte))
        premiere = textes_vus.setdefault(cle_texte, url)
        if premiere != url:
            return f"texte identique à celui de {premiere} (gabarit du site seul)"
    if not texte.strip():
        return "page vide"
    if len(_BINAIRE.findall(texte[:5000])) > 50:
        return "contenu binaire décodé comme du texte"
    if caracteres_utiles(texte) < MIN_CARACTERES_UTILES:
        return f"moins de {MIN_CARACTERES_UTILES} caractères de texte courant (menus, liens seuls)"
    return None


class Lecteur(Protocol):
    def try_complete_json(self, modele: Any, prompt: str, *, system: str) -> Any: ...


class JevCompatible:
    """Le client neuf, vu par `prospection.arbitre` comme l'ancien `ClientDecision`."""

    def __init__(self, client: Client, registre: Registre, budget: Budget) -> None:
        self.client, self.m, self.budget = client, registre.modele("decision"), budget

    def decider(self, etat_jev: Any, questions: dict[str, Any]) -> pd.Decision:
        reservation = self.budget.reserver(self.m.plafond_usd(32_000, 0), "entrée Jev")
        cout = None
        try:
            d = self.client.decider(
                self.m.nom,
                etat_jev,
                questions,
                acceptes=self.m.acceptes,
                delai_s=self.m.delai_s,
                role="entree",
            )
            cout = d.cout_usd
        finally:
            self.budget.regler(reservation, cout)
        reponses = {
            nom: pd.Reponse(
                type=a.type,
                choix=a.choix,
                noul=a.probabilites.get("true") if a.type == "noul" else None,
                probabilites=a.probabilites,
            )
            for nom, a in d.avis.items()
        }
        return pd.Decision(reponses, d.modele_servi, "", d.jetons_entree, d.cout_usd, d.duree_s, {})


@dataclass
class Page:
    url: str
    url_finale: str
    texte: str
    documents: list[str]
    est_pdf: bool
    territoire: str
    titre: str = ""


@dataclass
class Jugement:
    url: str
    issue: str  # admise, ecartee, doute, panne
    motif: str = ""
    bande: str | None = None
    arbitrage: dict[str, Any] = field(default_factory=dict)
    lu: dict[str, Any] = field(default_factory=dict)
    panne: str | None = None
    memorise: bool = False


def issue_de(
    destinataire: str,
    objet: str,
    categorie: str | None,
    famille: str | None,
    url: str,
    territoire: str,
    titre: str,
) -> tuple[str, str]:
    """(issue, motif) : la règle de la file, appliquée telle quelle."""
    tache = etat.Tache(
        titre=titre or url,
        url=url,
        territoire=territoire,
        famille=famille,
        destinataire=destinataire,
        objet=objet,
        categorie_ecart=categorie,
    )
    motif = etat.motif_non_promotion(tache)
    if motif is None:
        return "admise", ""
    if not etat.indetermine(destinataire, objet, categorie) and not tache.retenue:
        return "ecartee", motif
    return "doute", motif


def objet_page(url: str) -> str:
    from catalogue.veille_collect import cle_url

    return "d:" + empreinte(cle_url(url))


def juger(
    page: Page,
    *,
    registre: Registre,
    vue: Vue,
    jev: Any,
    lecteur: Lecteur,
    modele_lecture: str,
    consigner: Any,
    textes_vus: dict[tuple[str, str], str] | None = None,
) -> Jugement:
    """Le jugement d'entrée d'une page. Ne lève pas : une panne est une issue technique."""
    texte = page.texte[: lecture.MAX_CAR_PAGE]
    objet = objet_page(page.url)
    if motif := inexploitable(texte, page.url_finale, textes_vus):
        consigner(
            Evenement(
                "panne",
                objet,
                decision="entree",
                issue="contenu_inexploitable",
                donnees={"url": page.url, "motif": motif},
            )
        )
        return Jugement(page.url, "panne", motif, panne="contenu_inexploitable")
    cle_j = cle(
        VERSION,
        page.url_finale,
        empreinte(texte),
        tuple(page.documents),
        empreinte(tri.doctrine()),
        EMPREINTE_QUESTIONS,
        registre.modele("decision").nom,
        modele_lecture,
    )
    if (memo := vue.memo(cle_j)) is not None:
        d = memo.donnees
        return Jugement(
            page.url,
            memo.issue or "doute",
            d.get("motif", ""),
            d.get("bande"),
            d.get("arbitrage", {}),
            d.get("lu", {}),
            memorise=True,
        )
    try:
        a = arbitre.arbitrer(jev, page.url_finale, texte)
    except (Panne, pd.ErreurDecision) as exc:
        classe = exc.classe if isinstance(exc, Panne) else "jev"
        consigner(
            Evenement(
                "panne",
                objet,
                decision="entree",
                decideur="jev",
                issue=classe,
                donnees={"url": page.url, "message": str(exc)[:300]},
            )
        )
        return Jugement(page.url, "panne", str(exc)[:200], panne=classe)
    j = Jugement(page.url, "doute", bande=a.bande, arbitrage=a.en_dict())
    if a.bande == "ecartee":
        j.issue, j.motif = "ecartee", f"écartée par Jev sans lecture ({a.resume()})"
    else:
        prompt = "\n\n".join(
            [
                f"URL : {page.url_finale}",
                "Documents liés depuis cette page (les seuls que tu peux citer dans `urls_pdf`) :\n"
                + ("\n".join(f"  {u}" for u in page.documents) or "  (aucun)"),
                "--- Texte du document PDF ---" if page.est_pdf else "--- Contenu de la page ---",
                texte,
            ]
        )
        essai = lecteur.try_complete_json(lecture.LectureFiche, prompt, system=lecture.consigne())
        if essai.data is None:
            erreur = str(getattr(essai.response, "error", "") or "lecture vide")
            consigner(
                Evenement(
                    "panne",
                    objet,
                    decision="entree",
                    decideur="llm",
                    issue="lecture",
                    donnees={"url": page.url, "message": erreur[:300]},
                )
            )
            return Jugement(page.url, "panne", erreur[:200], a.bande, a.en_dict(), panne="lecture")
        fiche = essai.data
        fiche.urls_pdf = [u for u in fiche.urls_pdf if u in page.documents]
        correction = lecture._appliquer_arbitrage(fiche, a)
        j.lu = {
            "titre": fiche.titre,
            "destinataire": fiche.destinataire,
            "objet": fiche.objet,
            "categorie_ecart": fiche.categorie_ecart,
            "famille": fiche.famille,
            "urls_pdf": fiche.urls_pdf,
            "beneficiaires": fiche.beneficiaires,
            "note": " ".join((fiche.note or "").split())[: lecture.MAX_CAR_NOTE],
            "slug": fiche.slug_propose,
            "correction": correction,
        }
        j.issue, j.motif = issue_de(
            fiche.destinataire,
            fiche.objet,
            fiche.categorie_ecart,
            fiche.famille,
            page.url,
            page.territoire,
            fiche.titre or page.titre,
        )
    consigner(
        Evenement(
            "decision",
            objet,
            decision="entree",
            decideur="jev" if a.bande == "ecartee" else "jev+llm",
            modele=a.modele,
            issue=j.issue,
            cle=cle_j,
            donnees={
                "url": page.url,
                "motif": j.motif,
                "bande": j.bande,
                "arbitrage": j.arbitrage,
                "lu": j.lu,
                "territoire": page.territoire,
            },
        )
    )
    return j


# ------------------------------------------------------------------ un territoire


def en_boucle(url: str) -> bool:
    """Règle anti-boucle : un segment de chemin répété plus de deux fois.

    `collecte.chemin_en_boucle` ne prenait aucune des 24 185 fausses candidates
    de la Moselle ; celle-ci en prend 23 919, et aucune des 9 089 URL des autres
    territoires (mesure M14 du 2026-10-10).
    """
    from collections import Counter
    from urllib.parse import urlsplit

    segments = [s for s in urlsplit(url).path.split("/") if s]
    return any(n > 2 for n in Counter(segments).values())


@dataclass
class Exploration:
    territoire: str
    candidats: int = 0
    en_boucle: int = 0
    deja_juges: int = 0
    plafonnee: bool = False
    tri: dict[str, int] = field(default_factory=dict)
    jugements: list[Jugement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def explorer(
    nom: str,
    *,
    registre: Registre,
    vue: Vue,
    jev: Any,
    client_tri: Any,
    lecteur: Lecteur,
    modele_lecture: str,
    consigner: Any,
    fetcheur: Any,
    client_decouverte: Any = None,
    candidats_figes: Path | None = None,
) -> Exploration:
    """Collecte, anti-boucle, dédoublonnage contre le journal, plafond, tri mémorisé, jugement des pages."""
    from prospection import collecte as collecte_mod
    from prospection.territoires import aides_existantes, charger_territoires

    from aides_schema import AIDES_DIR, load_aide

    t = charger_territoires()[nom]
    corpus = {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}
    x = Exploration(nom)
    # La collecte d'origine, sans son plafond ni la file : le plafond s'applique
    # après la règle anti-boucle et le dédoublonnage contre le journal.
    if candidats_figes is not None:
        # Une liste figée (comparaison de bascule) : la même entrée que l'ancienne chaîne.
        c = collecte_mod.Collecte(candidats=collecte_mod.Collecte.lire(candidats_figes))
    else:
        c = collecte_mod.collecter(
            t, fetcheur, corpus, file=None, client_decouverte=client_decouverte, max_candidats=10**6
        )
    x.notes += c.notes
    candidats = []
    for cand in c.candidats:
        if en_boucle(cand.url):
            x.en_boucle += 1
            continue
        issue = vue.derniere.get((objet_page(cand.url), "entree"))
        tri_fait = vue.derniere.get((objet_page(cand.url), "tri"))
        if (issue is not None and issue.issue in ("admise", "ecartee")) or (
            tri_fait is not None and tri_fait.issue == "ecarter"
        ):
            x.deja_juges += 1
            continue
        candidats.append(cand)
    x.candidats = len(candidats)
    plafond = t.strategie.max_candidats
    if len(candidats) > plafond:
        candidats, x.plafonnee = candidats[:plafond], True
    existantes = aides_existantes(nom, t, corpus)
    systeme = tri.prompt_systeme(t, existantes)
    m_tri = registre.modele("tri").nom

    def cle_tri(cand: Any) -> str:
        texte = " ".join(f"{cand.titre} {cand.extrait}".split()).lower()
        return cle("tri@1", texte, cand.url, empreinte(systeme), m_tri)

    a_trier = [cand for cand in candidats if vue.memo(cle_tri(cand)) is None]
    nouveaux = {r.url: r for r in tri.trier(a_trier, t, existantes, client_tri)} if a_trier else {}
    decisions: dict[str, str] = {}
    for cand in candidats:
        memo = vue.memo(cle_tri(cand))
        if memo is not None:
            decisions[cand.url] = memo.issue or "douteux"
            continue
        r = nouveaux.get(cand.url)
        if r is None:
            continue
        decisions[cand.url] = r.decision
        if r.motif.startswith("lot non trié"):
            # Le tri en panne rend « douteux » : on ouvre la page, mais on ne mémorise pas.
            continue
        consigner(
            Evenement(
                "decision",
                objet_page(cand.url),
                decision="tri",
                decideur="llm",
                modele=m_tri,
                issue=r.decision,
                cle=cle_tri(cand),
                donnees={
                    "url": cand.url,
                    "titre": cand.titre,
                    "motif": r.motif,
                    "famille": r.famille,
                    "territoire": nom,
                },
            )
        )
    from collections import Counter

    x.tri = dict(Counter(decisions.values()))
    textes_vus: dict[tuple[str, str], str] = {}
    for cand in candidats:
        if decisions.get(cand.url) not in ("retenir", "douteux"):
            continue
        page_web = fetcheur.get(cand.url)
        if not page_web.ok:
            consigner(
                Evenement(
                    "panne",
                    objet_page(cand.url),
                    decision="entree",
                    issue="reseau_hote",
                    donnees={"url": cand.url, "erreur": str(page_web.erreur or page_web.status)},
                )
            )
            x.jugements.append(
                Jugement(
                    cand.url, "panne", str(page_web.erreur or page_web.status), panne="reseau_hote"
                )
            )
            continue
        texte, erreur = lecture._texte_a_juger(page_web)
        if erreur is not None:
            consigner(
                Evenement(
                    "panne",
                    objet_page(cand.url),
                    decision="entree",
                    issue="contenu_inexploitable",
                    donnees={"url": cand.url, "motif": erreur},
                )
            )
            x.jugements.append(Jugement(cand.url, "panne", erreur, panne="contenu_inexploitable"))
            continue
        page = Page(
            url=cand.url,
            url_finale=page_web.url_finale,
            texte=texte,
            documents=lecture._documents_lies(page_web, t, cand),
            est_pdf=page_web.est_pdf,
            territoire=nom,
            titre=cand.titre,
        )
        x.jugements.append(
            juger(
                page,
                registre=registre,
                vue=vue,
                jev=jev,
                lecteur=lecteur,
                modele_lecture=modele_lecture,
                consigner=consigner,
                textes_vus=textes_vus,
            )
        )
    return x


# ------------------------------------------------------------------ commande

PLAFOND_CASES = 10  # cases de doute montrées à Félix par run (section 8)


def cases_de_doute(x: Exploration, vue: Vue) -> tuple[list[Any], int]:
    """Les doutes à montrer, plus anciens d'abord, et le nombre de ceux qui attendent au-delà du plafond."""
    from catalogue.cases import Case

    doutes = [j for j in x.jugements if j.issue == "doute"]

    def anciennete(j: Jugement) -> str:
        premier = next(
            (
                e.t
                for e in vue.par_cle.values()
                if e.decision == "entree" and e.donnees.get("url") == j.url
            ),
            "9999",
        )
        return premier

    doutes.sort(key=anciennete)
    cases = []
    for j in doutes[:PLAFOND_CASES]:
        lu = j.lu or {}
        cases.append(
            Case(
                "entree-doute",
                objet_page(j.url),
                f"page à trancher : {lu.get('titre') or j.url}",
                empreinte(json.dumps([j.arbitrage, lu], sort_keys=True, ensure_ascii=False)),
                {
                    "admettre": "elle relève du catalogue : l'ingérer",
                    "ecarter": "elle n'en relève pas",
                },
                (
                    f"<{j.url}>",
                    f"Jev : {j.arbitrage.get('deposable')} (déposable), destinataire {j.arbitrage.get('destinataire')}, objet {j.arbitrage.get('objet')}",
                    f"Lecture : destinataire {lu.get('destinataire')}, objet {lu.get('objet')}, famille {lu.get('famille')}",
                    f"Motif : {j.motif}",
                ),
            )
        )
    return cases, max(0, len(doutes) - PLAFOND_CASES)


def section(x: Exploration, en_attente: int) -> list[str]:
    from collections import Counter

    issues = Counter(j.issue for j in x.jugements)
    lignes = [
        f"Territoire `{x.territoire}` : {x.candidats} candidates nouvelles"
        + (" (plafond atteint)" if x.plafonnee else "")
        + f", {x.en_boucle} écartées par la règle anti-boucle, {x.deja_juges} déjà jugées.",
        f"Tri sur titre : {', '.join(f'{k} {v}' for k, v in sorted(x.tri.items())) or 'rien'}.",
        f"Pages jugées : {', '.join(f'{k} {v}' for k, v in sorted(issues.items())) or 'aucune'}"
        + (
            f" ; {en_attente} doute(s) en attente au-delà des {PLAFOND_CASES} cases"
            if en_attente
            else ""
        )
        + ".",
    ]
    admises = [j for j in x.jugements if j.issue == "admise"]
    if admises:
        lignes += ["", "Admises (à ingérer) :", ""]
        lignes += [f"- {j.lu.get('titre') or j.url} <{j.url}>" for j in admises]
    lignes += [f"- note de collecte : {n}" for n in x.notes]
    return lignes


def commande(
    territoire: str, journal: Path, parties: Path | None, candidats: Path | None = None
) -> int:
    """`python -m catalogue entree --territoire <nom>` : un territoire, de la collecte au jugement."""
    import datetime as dt
    import secrets

    from pipeline.llm import charger_env, client_pour
    from pipeline.web import Fetcheur
    from prospection.territoires import charger_territoires

    from catalogue import agent
    from catalogue.cases import relire
    from catalogue.journal import Journal
    from catalogue.rapport import Rapport, Section, parties_json
    from catalogue.registre import charger

    charger_env()
    reg = charger()
    run = f"{dt.date.today().isoformat()}-entree-{secrets.token_hex(2)}"
    j = Journal(journal)
    vue = Vue(list(j.lire()))
    reponses, _ = relire((BACKEND / "data" / "reviews").glob("*-semaine*.md"), vue, run)
    if reponses:
        j.ajouter_lot(reponses)
        for e in reponses:
            vue.prendre(e)
    budget = Budget(reg.budgets.run.plafond_usd)
    # Le tri et la lecture restent sur providall, enveloppé : modèle servi
    # contrôlé et coût facturé relevé à chaque tentative, sous le budget du run.
    roles = {r: reg.modele(r) for r in ("tri", "lecture")}
    releve = agent.Releve(
        plafond=reg.budgets.run.plafond_usd,
        modeles={m.alias_providall: m for m in roles.values() if m.alias_providall},
        chemin=BACKEND / ".cache" / "catalogue" / "appels" / f"{run}.jsonl",
    )
    releve.chemin.parent.mkdir(parents=True, exist_ok=True)
    agent.surveiller(releve)

    def consigner(e: Evenement) -> Evenement:
        e = j.ajouter(Evenement.depuis_dict({**e.en_dict(), "run": run}))
        vue.prendre(e)
        return e

    t = charger_territoires()[territoire]
    client = Client(journal=BACKEND / ".cache" / "catalogue" / "appels" / f"{run}-jev.jsonl")
    with Fetcheur(entetes=t.entetes) as fetcheur:
        x = explorer(
            territoire,
            registre=reg,
            vue=vue,
            jev=JevCompatible(client, reg, budget),
            client_tri=client_pour("tri", roles["tri"].alias_providall),
            lecteur=client_pour("lecture", roles["lecture"].alias_providall),
            modele_lecture=roles["lecture"].nom,
            consigner=consigner,
            fetcheur=fetcheur,
            client_decouverte=client_pour("decouverte", roles["tri"].alias_providall),
            candidats_figes=candidats,
        )
    cases, en_attente = cases_de_doute(x, vue)
    depense = budget.depense + releve.depense
    entete = [
        f"- Entrée, `{territoire}` : {len(x.jugements)} page(s) jugée(s), {len(cases)} case(s), {depense:.4f} $ relevés."
    ]
    if parties is not None:
        parties.write_text(
            parties_json(
                entete, cases, [Section(f"Entrée : {territoire}", section(x, en_attente))]
            ),
            encoding="utf-8",
        )
    else:
        r = Rapport(dt.date.today(), run)
        r.entete, r.cases, r.sections = (
            entete,
            cases,
            [Section(f"Entrée : {territoire}", section(x, en_attente))],
        )
        print(f"rapport : {r.ecrire(BACKEND / 'data' / 'reviews')}")
    return 0

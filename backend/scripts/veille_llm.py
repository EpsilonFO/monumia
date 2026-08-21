"""
Étage C, première moitié : registre de modèles, adaptateurs, prompt.

UN appel par aide, jamais de boucle agentique. L'outil d'ingestion existant
(`ingest_aide_agent.py`) tourne cinq minutes et brûle des jetons pour UNE
aide ; la veille repasse sur 142 fiches et doit rester bon marché. Tout ce que
le modèle a besoin de savoir est donc mis dans un seul prompt, et sa réponse
est un objet JSON que `veille_apply` valide avant de toucher au moindre
fichier.

Ajouter ou corriger un modèle = une ligne dans `REGISTRE`. C'est délibéré : les
identifiants des fournisseurs tiers bougent, et la seule chose qui doit rester
stable est le reste du pipeline.

Deux familles d'adaptateurs :
  - `anthropic`      : SDK natif. Jamais via une couche compatible OpenAI —
                       elle masque les sorties structurées et le paramétrage
                       du raisonnement, qui diffèrent d'un modèle à l'autre.
  - `openai_compat`  : SDK `openai` pointé sur une autre base_url (DeepSeek,
                       Moonshot, OpenAI). Ces fournisseurs exposent
                       délibérément le protocole d'OpenAI.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import Aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_apply import VeilleLLMOutput

# Les clés vivent dans backend/.env, comme pour `ingest_aide_agent.py`.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

Provider = Literal["anthropic", "openai_compat"]

# Plafond de contenu envoyé par document. Au-delà, on garde le DÉBUT : les
# règlements annoncent leurs conditions et leurs échéances en tête, et la queue
# des pages est faite de pieds de page et de liens.
MAX_CHARS_DOCUMENT = 60_000
MAX_CHARS_DIFF = 12_000

# Fin de la remise de lancement de Claude Sonnet 5 (3,00/15,00 $ ensuite).
FIN_TARIF_INTRO_SONNET = date(2026, 8, 31)


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    provider: Provider
    model_id: str
    env_key: str
    # Prix en dollars par million de jetons.
    prix_in: float
    prix_out: float
    base_url: str | None = None
    # Le fournisseur sait-il contraindre la sortie à un schéma JSON ?
    structured: bool = True
    # Claude Sonnet 5 rejette tout paramètre d'échantillonnage non par défaut
    # (400) — voir la note de migration du SDK Anthropic.
    supports_temperature: bool = True
    # `effort` n'existe pas sur tous les modèles : il ERRORE sur Haiku 4.5.
    effort: str | None = None
    # Budget de sortie. Les modèles à raisonnement le consomment en chaîne de
    # pensée avant d'écrire quoi que ce soit : mesuré, deepseek-v4-flash brûlait
    # 8 000 jetons en `reasoning_content` et rendait un contenu VIDE, avec un
    # `finish_reason: length` pour seul indice.
    max_tokens: int = 16_000
    # Identifiant confirmé auprès du fournisseur ? Les modèles tiers récents
    # sont dans le registre pour que le harnais soit complet, mais leur id
    # reste à confirmer — d'où la colonne du `--list-models`.
    id_verifie: bool = True
    # Les modèles à raisonnement d'OpenAI ont renommé `max_tokens` en
    # `max_completion_tokens` et rejettent l'ancien nom par un 400
    # `unsupported_parameter`. Mesuré sur gpt-5.6-luna le 2026-08-21. Le nom
    # est un attribut du modèle, pas du protocole : il vit donc ici, comme
    # `supports_temperature`.
    budget_sortie_param: str = "max_tokens"
    note: str = ""

    def prix(self, jour: date | None = None) -> tuple[float, float]:
        if self.alias == "sonnet" and (jour or date.today()) <= FIN_TARIF_INTRO_SONNET:
            return 2.00, 10.00
        return self.prix_in, self.prix_out

    @property
    def cle_presente(self) -> bool:
        return bool(os.environ.get(self.env_key))


REGISTRE: dict[str, ModelSpec] = {
    # --- Anthropic (SDK natif) ---------------------------------------------
    "sonnet": ModelSpec(
        alias="sonnet",
        provider="anthropic",
        model_id="claude-sonnet-5",
        env_key="ANTHROPIC_API_KEY",
        prix_in=3.00,
        prix_out=15.00,
        supports_temperature=False,
        effort="medium",
        note="raisonnement adaptatif actif par défaut ; pas de temperature",
    ),
    "haiku": ModelSpec(
        alias="haiku",
        provider="anthropic",
        model_id="claude-haiku-4-5",
        env_key="ANTHROPIC_API_KEY",
        prix_in=1.00,
        prix_out=5.00,
        note="`effort` non supporté sur ce modèle : omis",
    ),
    # --- DeepSeek (protocole OpenAI) ---------------------------------------
    "ds-flash": ModelSpec(
        alias="ds-flash",
        provider="openai_compat",
        model_id="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
        max_tokens=32_000,
        prix_in=0.28,
        prix_out=0.42,
        note="id confirmé : déjà utilisé par ingest_aide_agent.py",
    ),
    "ds-pro": ModelSpec(
        alias="ds-pro",
        provider="openai_compat",
        model_id="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
        max_tokens=32_000,
        prix_in=0.55,
        prix_out=2.20,
        note="id confirmé : défaut de ingest_aide_agent.py (contexte 1M)",
    ),
    # --- OpenAI ------------------------------------------------------------
    "gpt-luna": ModelSpec(
        alias="gpt-luna",
        provider="openai_compat",
        model_id="gpt-5.6-luna",
        env_key="OPENAI_API_KEY",
        budget_sortie_param="max_completion_tokens",
        # Refuse `temperature=0` : « Only the default (1) value is supported ».
        supports_temperature=False,
        prix_in=1.25,
        prix_out=10.00,
        id_verifie=False,
    ),
    "gpt-terra": ModelSpec(
        alias="gpt-terra",
        provider="openai_compat",
        model_id="gpt-5.6-terra",
        env_key="OPENAI_API_KEY",
        budget_sortie_param="max_completion_tokens",
        # Refuse `temperature=0` : « Only the default (1) value is supported ».
        supports_temperature=False,
        prix_in=0.25,
        prix_out=2.00,
        id_verifie=False,
    ),
    # --- Moonshot ----------------------------------------------------------
    "kimi-k2.7": ModelSpec(
        alias="kimi-k2.7",
        provider="openai_compat",
        model_id="kimi-k2.7",
        base_url="https://api.moonshot.ai/v1",
        env_key="MOONSHOT_API_KEY",
        prix_in=0.60,
        prix_out=2.50,
        id_verifie=False,
    ),
    "kimi-k3": ModelSpec(
        alias="kimi-k3",
        provider="openai_compat",
        model_id="kimi-k3",
        base_url="https://api.moonshot.ai/v1",
        env_key="MOONSHOT_API_KEY",
        prix_in=1.00,
        prix_out=4.00,
        id_verifie=False,
    ),
}

# Choisi le 2026-08-21 sur décision produit, PAS sur mesure : le benchmark
# n'a pas encore été rejoué avec OPENAI_API_KEY en place. Le gagnant mesuré du
# 2026-08-06 restait ds-flash (2 faux changements contre 12 pour ds-pro).
#
# Seule observation à ce stade, sur pdl-restauration-mh : gpt-luna coûte 3,16 ¢
# contre 1,10 ¢ pour ds-flash (sortie facturée 10 $/M contre 0,42) et propose le
# MÊME faux changement de taux. Il est en revanche quatre fois plus rapide.
# `veille_benchmark.py --models ds-flash,gpt-luna` tranchera sur `faux chg` ;
# revenir à ds-flash est un changement d'une ligne ici.
#
# AUCUN modèle testé n'atteint le zéro absolu de faux changements visé par le
# plan : sur une source inchangée, les deux proposent encore des retouches de
# citation qui franchissent la validation. La relecture humaine du `git diff`
# reste donc indispensable avant commit, et `--max-llm` garde son sens.
MODELE_DEFAUT = "gpt-luna"


@dataclass
class LLMCall:
    """Retour uniforme, quel que soit le fournisseur."""

    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float | None = None
    model: str = ""
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    # Le fournisseur a répondu, mais sans contenu. Distinct d'une erreur d'API :
    # c'est un raté ponctuel, et le seul cas où réessayer immédiatement a du
    # sens — un 401 ou un 429 échouerait pareil à la seconde tentative.
    reponse_vide: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


# ---------------------------------------------------------------------------
# Schéma de sortie
# ---------------------------------------------------------------------------


def json_schema() -> dict[str, Any]:
    """Schéma JSON de `VeilleLLMOutput`, pour les sorties structurées.

    Dérivé du modèle Pydantic lui-même : le schéma envoyé au fournisseur et
    celui qui valide la réponse ne peuvent pas diverger.
    """
    schema = VeilleLLMOutput.model_json_schema()
    _durcir(schema)
    return schema


def _durcir(noeud: Any) -> None:
    """`additionalProperties: false` partout — exigé par les sorties structurées."""
    if isinstance(noeud, dict):
        if noeud.get("type") == "object" or "properties" in noeud:
            noeud.setdefault("additionalProperties", False)
        for valeur in noeud.values():
            _durcir(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            _durcir(valeur)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM = """Tu mets à jour une fiche d'aide au patrimoine à partir de sa source officielle fraîchement retéléchargée.

Tu ne rends QUE du JSON conforme au schéma. Aucun texte autour.

Règle absolue : chaque `quote` que tu produis doit être un extrait VERBATIM du contenu frais fourni. Elle est vérifiée automatiquement par recherche littérale ; une citation approximative, reformulée ou reconstituée de mémoire fait rejeter toute ta réponse. Si tu ne peux pas citer, ne propose pas le changement.

Ton mandat est étroit — quatre choses seulement :
- `calendrier` : permanent, date_ouverture, date_limite, delai_instruction
- `financement` : montant_min, montant_max, taux_min, taux_max, plancher, base_ttc, assiette
- `cumul` : plafond_public_pct, cumulable, exclusions
- `conditions` : texte, citation, notes, prédicat d'une condition existante ; ou ajout d'une condition nouvelle

Tout le reste (description, démarche, documents requis) ne t'appartient pas : ne le touche pas, même si la source a changé dessus.

Ne signale QUE ce qui a réellement changé dans la source. Une reformulation, une apostrophe différente, un synonyme ne sont pas des changements : omets-les. Une réponse vide est le résultat NORMAL et attendu quand le règlement n'a pas bougé — c'est le cas le plus fréquent, et c'est une bonne réponse.

Ne re-type jamais une condition. Changer `kind`, `effect`, `fact` ou `field` n'est pas de ton ressort : si le fond d'une condition a changé au point d'exiger ça, réponds `changement_majeur: true` avec la raison, et rien d'autre.

Réponds `changement_majeur: true` aussi si la page décrit maintenant un dispositif différent, si l'aide semble supprimée, ou si tu ne reconnais pas le règlement.

Pour une condition dont tu ne retrouves plus la trace dans la source fraîche, utilise `op: "signaler_disparue"` : elle sera annotée pour un humain, jamais supprimée automatiquement.

Une condition ajoutée reste non typée : donne `id`, `text`, `quote`, et `kind: "untyped"` (ou `"info"` s'il s'agit d'une simple modalité sans incidence sur l'éligibilité).

Renseigne TOUJOURS `resume` : une phrase disant ce qui a changé dans la source, ou pourquoi tu ne proposes rien. C'est ce que lira l'humain chargé de relire ton diff."""


def _tronquer(texte: str, limite: int) -> str:
    if len(texte) <= limite:
        return texte
    return texte[:limite] + f"\n\n[… document tronqué à {limite} caractères]"


def build_prompt(
    aide: Aide,
    documents: list[tuple[str, str, str]],
    diff: str,
    *,
    aujourd_hui: date,
) -> str:
    """Prompt utilisateur : l'existant, le frais, et ce qui a bougé entre les deux.

    Seules les sections du mandat sont montrées. Envoyer la fiche entière
    inviterait le modèle à corriger `description` ou `demarche`, qui relèvent
    de `/ingest-aide` — et chaque proposition hors mandat est un aller-retour
    de validation perdu.
    """
    extrait = {
        "slug": aide.slug,
        "nom": aide.nom,
        "organisme": aide.organisme,
        "calendrier": aide.calendrier.model_dump(mode="json", exclude_defaults=False),
        "financement": aide.financement.model_dump(mode="json", exclude_defaults=False),
        "cumul": aide.cumul.model_dump(mode="json", exclude_defaults=False),
        "conditions": [
            {
                k: v
                for k, v in c.model_dump(mode="json").items()
                if k
                in ("id", "text", "kind", "effect", "fact", "field", "predicate", "quote", "notes")
                and v is not None
            }
            for c in aide.conditions
        ],
    }

    blocs = [
        f"Date du jour : {aujourd_hui.isoformat()}",
        "",
        "## Fiche actuelle (sections de ton mandat uniquement)",
        "```json",
        json.dumps(extrait, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Contenu frais de la ou des sources officielles",
    ]
    for nom, contenu, _kind in documents:
        blocs += [f"\n### {nom}", "```", _tronquer(contenu, MAX_CHARS_DOCUMENT), "```"]

    if diff.strip():
        blocs += [
            "",
            "## Ce qui a changé depuis le dernier archivage",
            "Diff indicatif (le bruit de gabarit du site en a été retiré). "
            "La source de vérité reste le contenu frais ci-dessus.",
            "```diff",
            _tronquer(diff, MAX_CHARS_DIFF),
            "```",
        ]

    blocs += [
        "",
        f"Rends le JSON de mise à jour pour `{aide.slug}`. "
        "Si le règlement n'a pas changé sur ton mandat, rends un objet sans "
        "`calendrier`, sans `financement`, sans `cumul` et avec `conditions: []`.",
    ]
    return "\n".join(blocs)


# ---------------------------------------------------------------------------
# Adaptateurs
# ---------------------------------------------------------------------------


def system_pour(spec: ModelSpec) -> str:
    """Prompt système, complété du schéma quand le fournisseur ne le contraint pas.

    `response_format: json_object` (DeepSeek, Moonshot) garantit du JSON valide,
    PAS un JSON conforme. Sans le schéma sous les yeux, le modèle omet des
    champs et invente des clés — mesuré au premier appel réel. Les fournisseurs
    à vraies sorties structurées n'en ont pas besoin : le schéma leur est passé
    dans la requête.
    """
    if spec.provider == "anthropic" and spec.structured:
        return SYSTEM
    return (
        SYSTEM
        + "\n\nTa réponse doit valider ce schéma JSON, sans clé supplémentaire :\n"
        + json.dumps(json_schema(), ensure_ascii=False, indent=1)
    )


def call(
    spec: ModelSpec,
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    timeout: float = 300.0,
) -> LLMCall:
    """Un appel, un retour uniforme. Les erreurs sont rendues, jamais levées.

    Un fournisseur en panne ne doit pas interrompre un passage de veille sur
    142 aides : l'appelant escalade l'aide concernée et continue.
    """
    if not spec.cle_presente:
        return LLMCall(model=spec.alias, error=f"{spec.env_key} absente de l'environnement")
    budget = max_tokens or spec.max_tokens
    debut = time.monotonic()
    try:
        if spec.provider == "anthropic":
            appel = _call_anthropic(spec, system, user, max_tokens=budget, timeout=timeout)
        else:
            appel = _call_openai_compat(spec, system, user, max_tokens=budget, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — toute panne fournisseur est une donnée
        return LLMCall(
            model=spec.alias,
            latency_s=time.monotonic() - debut,
            error=f"{type(exc).__name__}: {exc}",
        )
    appel.latency_s = time.monotonic() - debut
    appel.model = spec.alias
    prix_in, prix_out = spec.prix()
    appel.cost_usd = appel.input_tokens / 1e6 * prix_in + appel.output_tokens / 1e6 * prix_out
    return appel


def _call_anthropic(
    spec: ModelSpec, system: str, user: str, *, max_tokens: int, timeout: float
) -> LLMCall:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ[spec.env_key], timeout=timeout)
    kwargs: dict[str, Any] = {
        "model": spec.model_id,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    # `output_config` porte à la fois le format de sortie et l'effort ; l'effort
    # n'est pas accepté partout (il errore sur Haiku 4.5), d'où le réglage par
    # spec plutôt qu'une valeur globale.
    output_config: dict[str, Any] = {}
    if spec.structured:
        output_config["format"] = {"type": "json_schema", "schema": json_schema()}
    if spec.effort:
        output_config["effort"] = spec.effort
    if output_config:
        kwargs["output_config"] = output_config

    resp = client.messages.create(**kwargs)
    texte = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    refus = resp.stop_reason == "refusal"
    erreur = None
    if refus:
        # Un refus de classificateur est un résultat, pas une exception : il
        # doit apparaître tel quel dans le rapport de benchmark.
        erreur = "refus du modèle (stop_reason=refusal)"
    elif not texte:
        erreur = f"contenu vide — stop_reason={resp.stop_reason!r}"
    return LLMCall(
        text=texte,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        extra={"stop_reason": resp.stop_reason},
        error=erreur,
        # Même règle que côté OpenAI : une troncature se reproduirait.
        reponse_vide=not texte and not refus and resp.stop_reason != "max_tokens",
    )


def _call_openai_compat(
    spec: ModelSpec, system: str, user: str, *, max_tokens: int, timeout: float
) -> LLMCall:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ[spec.env_key], base_url=spec.base_url, timeout=timeout)
    kwargs: dict[str, Any] = {
        "model": spec.model_id,
        spec.budget_sortie_param: max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if spec.structured:
        kwargs["response_format"] = {"type": "json_object"}
    if spec.supports_temperature:
        kwargs["temperature"] = 0

    resp = client.chat.completions.create(**kwargs)
    choix = resp.choices[0]
    usage = resp.usage
    texte = choix.message.content or ""
    erreur = None
    if not texte:
        # Toujours nommer la cause : un « contenu vide » sans explication a
        # coûté un passage de benchmark entier avant qu'on comprenne que le
        # raisonnement avait mangé tout le budget de sortie.
        raison = {
            "length": f"budget de sortie épuisé avant la réponse ({max_tokens} jetons) — "
            "modèle à raisonnement : augmenter `max_tokens` de sa ModelSpec",
            "content_filter": "réponse filtrée par le fournisseur",
        }.get(choix.finish_reason or "", f"finish_reason={choix.finish_reason!r}")
        sortie_utilisee = usage.completion_tokens if usage else 0
        erreur = f"contenu vide — {raison} ({sortie_utilisee} jetons de sortie facturés)"
    return LLMCall(
        text=texte,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        extra={"finish_reason": choix.finish_reason},
        error=erreur,
        # `length` et `content_filter` se reproduiraient à l'identique : ce sont
        # des causes, pas des ratés. Seul le vide inexpliqué mérite une relance.
        reponse_vide=not texte and choix.finish_reason not in ("length", "content_filter"),
    )


# ---------------------------------------------------------------------------
# Inspection du registre
# ---------------------------------------------------------------------------


def modeles_disponibles() -> list[ModelSpec]:
    return [s for s in REGISTRE.values() if s.cle_presente]


def table_registre() -> str:
    lignes = [
        f"{'alias':<11} {'fournisseur':<14} {'identifiant':<20} {'$/Mtok in/out':>14} "
        f"{'clé':<5} {'id vérifié':<11} note",
        "-" * 110,
    ]
    for spec in REGISTRE.values():
        prix_in, prix_out = spec.prix()
        lignes.append(
            f"{spec.alias:<11} {spec.provider:<14} {spec.model_id:<20} "
            f"{prix_in:>6.2f}/{prix_out:<7.2f} "
            f"{'oui' if spec.cle_presente else 'NON':<5} "
            f"{'oui' if spec.id_verifie else 'À VÉRIFIER':<11} {spec.note}"
        )
    return "\n".join(lignes)


if __name__ == "__main__":
    print(table_registre())

"""
Étage C, première moitié : registre de modèles, adaptateurs, prompt.

UN appel par aide, jamais de boucle agentique. L'agent d'ingestion
(`scripts/ingerer.py`) tourne plusieurs minutes et brûle des jetons pour UNE
aide ; la veille repasse sur 142 fiches et doit rester bon marché. Tout ce que
le modèle a besoin de savoir est donc mis dans un seul prompt, et sa réponse
est un objet JSON que `veille_apply` valide avant de toucher au moindre
fichier.

Trois niveaux, du plus stable au plus volatil :
  - `FOURNISSEURS` : protocole, base_url, nom de la clé. Neuf entrées, qui ne
                     bougent pas d'une année sur l'autre.
  - `REGISTRE`     : un modèle = une ligne (alias, fournisseur, identifiant).
  - `MODELE_DEFAUT`: le modèle utilisé partout, réglable sans toucher au code
                     par `VEILLE_MODEL` dans backend/.env.

Un modèle qui vient de sortir n'a même pas besoin d'entrer au registre :
`VEILLE_MODEL=glm:glm-5.4-flash` suffit (cf. `resoudre_modele`). C'est
délibéré — les identifiants des fournisseurs tiers bougent tous les mois, et
la seule chose qui doit rester stable est le reste du pipeline.

Deux familles d'adaptateurs :
  - `anthropic`      : SDK natif. Jamais via une couche compatible OpenAI —
                       elle masque les sorties structurées et le paramétrage
                       du raisonnement, qui diffèrent d'un modèle à l'autre.
  - `openai_compat`  : SDK `openai` pointé sur une autre base_url. Les huit
                       autres fournisseurs (OpenAI, Gemini, Grok, Kimi, GLM,
                       Mistral, DeepSeek, OpenRouter) exposent le protocole
                       d'OpenAI.
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
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import Aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_apply import VeilleLLMOutput

# Les clés vivent dans backend/.env, comme pour le pipeline d'ingestion, et
# `.env.local` (gitignoré) prime — même ordre que db.py et les autres scripts.
# Ne charger que `.env.local` masquait toutes les clés de `.env` : le registre
# annonçait `DEEPSEEK_API_KEY` absente alors qu'elle était posée.
_BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND / ".env")
load_dotenv(_BACKEND / ".env.local", override=True)

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
    # Prix en dollars par million de jetons. Zéro = tarif non renseigné, pas
    # gratuit : `call()` rend alors `cost_usd=None` plutôt qu'un 0,00 $ faux.
    prix_in: float = 0.0
    prix_out: float = 0.0
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
    # Clé de `FOURNISSEURS` d'où viennent protocole, base_url et env_key.
    # Purement documentaire ici : c'est ce qu'affiche `--list-models`.
    fournisseur: str = ""
    note: str = ""

    def prix(self, jour: date | None = None) -> tuple[float, float]:
        if self.alias == "sonnet" and (jour or date.today()) <= FIN_TARIF_INTRO_SONNET:
            return 2.00, 10.00
        return self.prix_in, self.prix_out

    @property
    def cle_presente(self) -> bool:
        return bool(os.environ.get(self.env_key))

    @property
    def tarif_connu(self) -> bool:
        return self.prix_in > 0 or self.prix_out > 0


# ---------------------------------------------------------------------------
# Fournisseurs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fournisseur:
    """Ce qui tient au fournisseur et jamais au modèle : protocole, adresse, clé.

    Séparé de `ModelSpec` parce que rien là-dedans ne bouge quand un modèle est
    remplacé par le suivant. Inscrire `glm-5.4-flash` l'an prochain ne doit
    demander qu'un identifiant — pas de recopier une base_url qu'on se trompera
    à saisir, ni de retrouver le nom exact de la variable d'environnement.

    Les neuf fournisseurs parlent le protocole d'OpenAI, sauf Anthropic : son
    SDK natif est le seul à exposer les sorties structurées et le réglage du
    raisonnement, que la couche de compatibilité masque.
    """

    protocole: Provider
    env_key: str
    base_url: str | None = None
    # Réglages hérités par tous les modèles du fournisseur ; le REGISTRE les
    # surcharge modèle par modèle quand l'un d'eux se comporte autrement.
    structured: bool = True
    supports_temperature: bool = True
    budget_sortie_param: str = "max_tokens"
    max_tokens: int = 16_000
    # Effort de raisonnement (`low`/`medium`/`high`), quand le fournisseur sait le
    # régler. Anthropic : `output_config.effort`. OpenRouter : `reasoning.effort`,
    # transmis au modèle routé. Ailleurs : ignoré.
    effort: str | None = None
    note: str = ""


FOURNISSEURS: dict[str, Fournisseur] = {
    "anthropic": Fournisseur("anthropic", "ANTHROPIC_API_KEY"),
    "openai": Fournisseur(
        "openai_compat",
        "OPENAI_API_KEY",
        # Les modèles à raisonnement d'OpenAI ont renommé `max_tokens` et
        # refusent `temperature=0` (« Only the default (1) value is supported »).
        budget_sortie_param="max_completion_tokens",
        supports_temperature=False,
    ),
    "gemini": Fournisseur(
        "openai_compat",
        "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "grok": Fournisseur("openai_compat", "XAI_API_KEY", "https://api.x.ai/v1"),
    "kimi": Fournisseur("openai_compat", "MOONSHOT_API_KEY", "https://api.moonshot.ai/v1"),
    "glm": Fournisseur("openai_compat", "ZAI_API_KEY", "https://api.z.ai/api/paas/v4"),
    "mistral": Fournisseur("openai_compat", "MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
    "deepseek": Fournisseur(
        "openai_compat",
        "DEEPSEEK_API_KEY",
        "https://api.deepseek.com",
        # Mesuré : deepseek-v4-flash brûlait 8 000 jetons de `reasoning_content`
        # avant d'écrire, et rendait un contenu VIDE.
        max_tokens=32_000,
    ),
    # Passerelle, pas éditeur : une seule clé pour joindre les modèles des
    # autres. Utile pour essayer un fournisseur sans ouvrir un compte chez lui,
    # au prix d'un identifiant préfixé de l'éditeur (`z-ai/…`, `moonshotai/…`).
    "openrouter": Fournisseur(
        "openai_compat",
        "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1",
        # `response_format` est transmis tel quel au modèle routé, et ceux qui
        # ne le connaissent pas répondent 400. On ne le pose donc pas : pour
        # tout `openai_compat`, `system_pour` met de toute façon le schéma dans
        # le prompt système, seule la contrainte dure est perdue.
        structured=False,
        # Même raison que DeepSeek : la passerelle sert surtout des modèles à
        # raisonnement, qui consomment leur budget de sortie avant d'écrire.
        max_tokens=32_000,
        # Mesuré le 2026-09-01 sur l'audit de `sauvegarde-art-francais` (7 000
        # tokens de prompt) avec glm-5.3-flash. Sans réglage : 25 270 tokens de
        # sortie et 405 s par appel — un benchmark de dix appels passait pour
        # bloqué. Avec un effort explicite, sur la fiche intacte puis amputée
        # d'une condition (`veille_benchmark_audit.py`) :
        #   low     10-12 s   11 critères relevés, 0 faux, retrait retrouvé
        #   medium  10-19 s   12 critères relevés, 0 faux, retrait retrouvé
        #   high    31-62 s   14 critères relevés, 2 FAUX manquants (modalités)
        # `medium` : même rappel que `low` pour un relevé un peu plus fourni,
        # sans la sur-lecture de `high`. Désactiver le raisonnement est refusé
        # par le fournisseur (400).
        effort="medium",
        note="passerelle : identifiant préfixé de l'éditeur, tarif propre à chaque modèle",
    ),
}


def _spec(alias: str, fournisseur: str, model_id: str, **surcharges: Any) -> ModelSpec:
    """Un modèle = son alias, son fournisseur, son identifiant. Le reste est hérité."""
    f = FOURNISSEURS[fournisseur]
    champs: dict[str, Any] = {
        "provider": f.protocole,
        "env_key": f.env_key,
        "base_url": f.base_url,
        "structured": f.structured,
        "supports_temperature": f.supports_temperature,
        "budget_sortie_param": f.budget_sortie_param,
        "max_tokens": f.max_tokens,
        "effort": f.effort,
        "note": f.note,
    }
    champs.update(surcharges)
    return ModelSpec(alias=alias, model_id=model_id, fournisseur=fournisseur, **champs)


# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------
#
# Ajouter un modèle = une ligne. `id_verifie=False` signale un identifiant
# recopié d'une annonce et jamais confirmé auprès du fournisseur ; `--list-models`
# le rappelle. Un tarif laissé à zéro veut dire « pas renseigné » : le coût
# rapporté sera vide plutôt que faussement nul.

REGISTRE: dict[str, ModelSpec] = {
    # --- Anthropic (SDK natif) ---------------------------------------------
    "sonnet": _spec(
        "sonnet",
        "anthropic",
        "claude-sonnet-5",
        prix_in=3.00,
        prix_out=15.00,
        supports_temperature=False,
        effort="medium",
        note="raisonnement adaptatif actif par défaut ; pas de temperature",
    ),
    "haiku": _spec(
        "haiku",
        "anthropic",
        "claude-haiku-4-5",
        prix_in=1.00,
        prix_out=5.00,
        note="`effort` non supporté sur ce modèle : omis",
    ),
    # --- DeepSeek ----------------------------------------------------------
    "ds-flash": _spec(
        "ds-flash",
        "deepseek",
        "deepseek-v4-flash",
        prix_in=0.28,
        prix_out=0.42,
        note="id confirmé : utilisé en production sur le catalogue",
    ),
    "ds-pro": _spec(
        "ds-pro",
        "deepseek",
        "deepseek-v4-pro",
        prix_in=0.55,
        prix_out=2.20,
        note="id confirmé : modèle de vérification adversariale (contexte 1M)",
    ),
    # --- OpenAI ------------------------------------------------------------
    "gpt-luna": _spec(
        "gpt-luna", "openai", "gpt-5.6-luna", prix_in=1.25, prix_out=10.00, id_verifie=False
    ),
    "gpt-terra": _spec(
        "gpt-terra", "openai", "gpt-5.6-terra", prix_in=0.25, prix_out=2.00, id_verifie=False
    ),
    # --- Z.ai / GLM --------------------------------------------------------
    "glm-flash": _spec(
        "glm-flash",
        "glm",
        "glm-5.3-flash",
        id_verifie=False,
        note="tarif à renseigner après confirmation chez z.ai",
    ),
    "glm": _spec("glm", "glm", "glm-5.3", id_verifie=False, note="tarif à renseigner"),
    # --- Google ------------------------------------------------------------
    "gemini-flash": _spec(
        "gemini-flash", "gemini", "gemini-3-flash", id_verifie=False, note="tarif à renseigner"
    ),
    "gemini-pro": _spec(
        "gemini-pro", "gemini", "gemini-3-pro", id_verifie=False, note="tarif à renseigner"
    ),
    # --- xAI ---------------------------------------------------------------
    "grok-fast": _spec(
        "grok-fast", "grok", "grok-4-fast", id_verifie=False, note="tarif à renseigner"
    ),
    "grok": _spec("grok", "grok", "grok-4", id_verifie=False, note="tarif à renseigner"),
    # --- Moonshot ----------------------------------------------------------
    "kimi-k2.7": _spec(
        "kimi-k2.7", "kimi", "kimi-k2.7", prix_in=0.60, prix_out=2.50, id_verifie=False
    ),
    "kimi-k3": _spec("kimi-k3", "kimi", "kimi-k3", prix_in=1.00, prix_out=4.00, id_verifie=False),
    # --- Mistral -----------------------------------------------------------
    "mistral": _spec(
        "mistral",
        "mistral",
        "mistral-large-latest",
        id_verifie=False,
        note="alias glissant côté Mistral ; tarif à renseigner",
    ),
    "mistral-medium": _spec(
        "mistral-medium",
        "mistral",
        "mistral-medium-latest",
        id_verifie=False,
        note="tarif à renseigner",
    ),
    # --- OpenRouter (mêmes modèles, une seule clé) -------------------------
    # Deux exemples, pas une liste à tenir à jour : la passerelle en sert des
    # centaines, et `VEILLE_MODEL=openrouter:<éditeur>/<modèle>` en atteint
    # n'importe lequel sans écrire une ligne ici. Les identifiants exacts se
    # relèvent sur openrouter.ai/models.
    "or-glm": _spec(
        "or-glm",
        "openrouter",
        "z-ai/glm-5.3-flash",
        prix_in=0.07,
        prix_out=0.25,
        structured=True,
        note="id, tarif et response_format relevés sur /api/v1/models le 2026-08-28",
    ),
    "or-kimi": _spec(
        "or-kimi",
        "openrouter",
        "moonshotai/kimi-k2.6",
        prix_in=0.95,
        prix_out=4.00,
        structured=True,
        note="k2.7 n'existe pas chez OpenRouter (seul k2.7-code) ; relevé le 2026-08-28",
    ),
}


def resoudre_modele(nom: str) -> ModelSpec:
    """Alias du registre, ou `fournisseur:identifiant` pour un modèle non inscrit.

    La seconde forme existe pour la raison qui fait vivre ce fichier : les
    fournisseurs sortent un modèle par mois, et attendre une entrée de registre
    pour l'essayer n'aurait pas de sens. `VEILLE_MODEL=glm:glm-5.4-flash` dans
    backend/.env suffit — protocole, base_url et nom de clé viennent du
    fournisseur, l'identifiant est pris tel quel, et le tarif reste inconnu.
    """
    nom = nom.strip()
    if nom in REGISTRE:
        return REGISTRE[nom]
    if ":" in nom:
        fournisseur, _, model_id = nom.partition(":")
        fournisseur, model_id = fournisseur.strip(), model_id.strip()
        if fournisseur not in FOURNISSEURS:
            raise KeyError(
                f"fournisseur inconnu : {fournisseur!r} — connus : "
                + ", ".join(sorted(FOURNISSEURS))
            )
        if not model_id:
            raise KeyError(f"identifiant de modèle vide dans {nom!r}")
        return _spec(
            nom,
            fournisseur,
            model_id,
            id_verifie=False,
            note="hors registre : identifiant et tarif non vérifiés",
        )
    raise KeyError(
        f"modèle inconnu : {nom!r}\n"
        f"  alias du registre : {', '.join(sorted(REGISTRE))}\n"
        f"  ou `fournisseur:identifiant` parmi : {', '.join(sorted(FOURNISSEURS))}"
    )


# ---------------------------------------------------------------------------
# LE point unique où se règle le modèle
# ---------------------------------------------------------------------------
#
# Les trois étages qui appellent un LLM — `veille_aides.py`, `veille_audit.py`,
# `veille_typage.py` — prennent leur défaut ici et nulle part ailleurs ;
# `--model` ne sert plus qu'à un essai ponctuel.
#
# Deux façons de le changer, dans cet ordre de priorité :
#   1. `VEILLE_MODEL=glm-flash` dans backend/.env — aucun code à toucher, et
#      `VEILLE_MODEL=glm:glm-5.4-flash` marche aussi pour un modèle qui vient
#      de sortir et qui n'est pas encore au registre ;
#   2. la valeur ci-dessous, qui est le défaut du dépôt.
#
# Historique de la décision : gpt-luna avait été retenu le 2026-08-21 sur
# décision produit, PAS sur mesure. Le seul gagnant mesuré (2026-08-06) reste
# ds-flash — 2 faux changements contre 12 pour ds-pro — et sur
# pdl-restauration-mh gpt-luna coûtait 3,16 ¢ contre 1,10 ¢ pour ds-flash,
# pour le MÊME faux changement de taux. `veille_benchmark.py --models
# ds-flash,glm-flash,gpt-luna` reste à rejouer pour trancher.
#
# AUCUN modèle testé n'atteint le zéro absolu de faux changements visé par le
# plan : la relecture humaine du `git diff` reste indispensable avant commit,
# et `--max-llm` garde son sens.
MODELE_DEFAUT = os.environ.get("VEILLE_MODEL", "").strip() or "glm-flash"


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


def json_schema(modele: type[BaseModel] = VeilleLLMOutput) -> dict[str, Any]:
    """Schéma JSON du modèle de sortie, pour les sorties structurées.

    Dérivé du modèle Pydantic lui-même : le schéma envoyé au fournisseur et
    celui qui valide la réponse ne peuvent pas diverger.

    Paramétré par le modèle depuis que `veille_audit.py` passe sa propre sortie
    par les mêmes adaptateurs — sans quoi un appel d'audit se verrait contraint
    au schéma de la veille, et sa réponse rejetée avant même d'être lue.
    """
    schema = modele.model_json_schema()
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
- `calendrier` :
  - `date_ouverture`, `date_limite` : dates ISO (AAAA-MM-JJ) de la session de dépôt en cours ou à venir.
  - `permanent` : `true` seulement pour un dépôt au fil de l'eau, sans échéance. Une `date_limite` exige `permanent: false` : pose les deux ensemble, sinon l'échéance est ignorée.
  - `delai_instruction` : texte court, tel que la source le donne.
- `financement` :
  - `montant_min`, `montant_max` : bornes en euros de l'AIDE versée.
  - `taux_min`, `taux_max` : taux d'aide en pourcentage, de 0 à 100 (40 pour 40 %).
  - `plancher` : seuil minimal de DÉPENSES éligibles en deçà duquel le projet n'est pas aidé (« dépense subventionnable minimale : 5 000 € »). Ce n'est JAMAIS le minimum de l'aide, qui va dans `montant_min`.
  - `base_ttc` : `true` si les montants s'entendent TTC, `false` s'ils sont HT.
  - `assiette` : les dépenses sur lesquelles s'applique le taux, en texte fidèle à la source.
- `cumul` :
  - `plafond_public_pct` : plafond du cumul des aides publiques, en % du coût du projet.
  - `cumulable` : `false` si le dispositif ne se cumule avec aucune autre aide.
  - `exclusions` : dispositifs nommément non cumulables, tels que la source les cite.
- `conditions` : texte, citation, notes, prédicat d'une condition existante.

Tout le reste (description, démarche, documents requis) ne t'appartient pas : ne le touche pas, même si la source a changé dessus.

Ne signale QUE ce qui a réellement changé dans la source. Une reformulation, une apostrophe différente, un synonyme ne sont pas des changements : omets-les. Une réponse vide est le résultat NORMAL et attendu quand le règlement n'a pas bougé — c'est le cas le plus fréquent, et c'est une bonne réponse.

Ne re-type jamais une condition. Changer `kind`, `effect`, `fact` ou `field` n'est pas de ton ressort : si le fond d'une condition a changé au point d'exiger ça, réponds `changement_majeur: true` avec la raison, et rien d'autre.

Réponds `changement_majeur: true` aussi si la page décrit maintenant un dispositif différent, si l'aide semble supprimée, ou si tu ne reconnais pas le règlement.

Une condition qui APPARAÎT dans la source (une exigence nouvelle, un critère, une exclusion), ou qui en DISPARAÎT, est le changement le plus important que tu puisses trouver. Signale-le, sans rien proposer d'autre à côté : l'aide entière sera ré-ingérée, et rien de ta réponse ne sera écrit dans la fiche.
- Condition nouvelle : `op: "add"`, avec `id`, `text` et `quote` (la phrase nouvelle, citée verbatim du contenu frais).
- Condition dont tu ne retrouves plus la trace : `op: "signaler_disparue"` avec son `id`.
Une simple reformulation d'une condition existante n'est ni l'un ni l'autre.

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


def system_pour(
    spec: ModelSpec,
    system: str = SYSTEM,
    modele: type[BaseModel] = VeilleLLMOutput,
) -> str:
    """Prompt système, complété du schéma quand le fournisseur ne le contraint pas.

    `response_format: json_object` (DeepSeek, Moonshot) garantit du JSON valide,
    PAS un JSON conforme. Sans le schéma sous les yeux, le modèle omet des
    champs et invente des clés — mesuré au premier appel réel. Les fournisseurs
    à vraies sorties structurées n'en ont pas besoin : le schéma leur est passé
    dans la requête.
    """
    if spec.provider == "anthropic" and spec.structured:
        return system
    return (
        system
        + "\n\nTa réponse doit valider ce schéma JSON, sans clé supplémentaire :\n"
        + json.dumps(json_schema(modele), ensure_ascii=False, indent=1)
    )


def call(
    spec: ModelSpec,
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    timeout: float = 300.0,
    schema: dict[str, Any] | None = None,
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
            appel = _call_anthropic(
                spec, system, user, max_tokens=budget, timeout=timeout, schema=schema
            )
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
    if spec.tarif_connu:
        prix_in, prix_out = spec.prix()
        appel.cost_usd = appel.input_tokens / 1e6 * prix_in + appel.output_tokens / 1e6 * prix_out
    return appel


def _call_anthropic(
    spec: ModelSpec,
    system: str,
    user: str,
    *,
    max_tokens: int,
    timeout: float,
    schema: dict[str, Any] | None = None,
) -> LLMCall:
    import anthropic

    # `max_retries=1` et non le défaut du SDK (2) : un appel qui expire est
    # rejoué en silence par le client, et trois délais de cinq minutes bout à
    # bout passent pour un blocage. Les étages gèrent déjà leur propre relance.
    client = anthropic.Anthropic(api_key=os.environ[spec.env_key], timeout=timeout, max_retries=1)
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
        output_config["format"] = {"type": "json_schema", "schema": schema or json_schema()}
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


def kwargs_openai_compat(
    spec: ModelSpec, system: str, user: str, max_tokens: int
) -> dict[str, Any]:
    """Arguments de `chat.completions.create`, isolés pour être testables sans réseau."""
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
    if spec.effort and spec.fournisseur == "openrouter":
        # Paramètre unifié d'OpenRouter, hors schéma OpenAI : passe par
        # `extra_body`. Sans lui, un modèle à raisonnement dépense son budget de
        # sortie en chaîne de pensée : 400 s par appel, mesuré (voir le registre).
        kwargs["extra_body"] = {"reasoning": {"effort": spec.effort}}
    return kwargs


def _call_openai_compat(
    spec: ModelSpec, system: str, user: str, *, max_tokens: int, timeout: float
) -> LLMCall:
    from openai import OpenAI

    # Même règle que côté Anthropic : une seule relance du SDK, pas deux.
    client = OpenAI(
        api_key=os.environ[spec.env_key], base_url=spec.base_url, timeout=timeout, max_retries=1
    )
    resp = client.chat.completions.create(**kwargs_openai_compat(spec, system, user, max_tokens))
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
        f"modèle par défaut : {MODELE_DEFAUT}"
        + ("  (via VEILLE_MODEL)" if os.environ.get("VEILLE_MODEL", "").strip() else ""),
        "",
        f"{'alias':<15} {'fournisseur':<10} {'identifiant':<22} {'$/Mtok in/out':>14} "
        f"{'clé':<5} {'id vérifié':<11} note",
        "-" * 118,
    ]
    for spec in REGISTRE.values():
        prix_in, prix_out = spec.prix()
        tarif = f"{prix_in:>6.2f}/{prix_out:<7.2f}" if spec.tarif_connu else f"{'?':>6}/{'?':<7}"
        lignes.append(
            f"{spec.alias:<15} {spec.fournisseur or spec.provider:<10} {spec.model_id:<22} "
            f"{tarif} "
            f"{'oui' if spec.cle_presente else 'NON':<5} "
            f"{'oui' if spec.id_verifie else 'À VÉRIFIER':<11} {spec.note}"
        )
    lignes += [
        "",
        "Variables d'environnement attendues, une par fournisseur (backend/.env) :",
        "  " + "   ".join(f"{nom}={f.env_key}" for nom, f in FOURNISSEURS.items()),
        "",
        "Changer de modèle : VEILLE_MODEL=<alias> dans backend/.env, ou",
        "VEILLE_MODEL=<fournisseur>:<identifiant> pour un modèle hors registre",
        "(ex. VEILLE_MODEL=glm:glm-5.4-flash, ou VEILLE_MODEL=openrouter:z-ai/glm-4.6",
        "pour passer par la passerelle).",
    ]
    return "\n".join(lignes)


if __name__ == "__main__":
    print(table_registre())

prompt_1 = """
Tu es un expert en financement du patrimoine bâti en France.

Voici le profil d'un monument :
{monument_profile}

Voici les conditions d'éligibilité détaillées de l'aide "{aide_nom}" :
{conditions_detail}

Évalue si ce monument est éligible à cette aide en te basant UNIQUEMENT sur les informations fournies.

Réponds en JSON strict avec ce format :
{{
  "eligible": true ou false,
  "explication": "Explication en 1-2 phrases de ta conclusion",
  "incertitudes": ["Liste des points qui ne peuvent pas être vérifiés avec les infos disponibles"]
}}

Si tu manques d'informations pour conclure, mets eligible à true (bénéfice du doute) et liste les incertitudes.
"""

prompt_2 = """
Tu es un expert en financement du patrimoine bâti en France, appliquant une analyse rigoureuse et critique.

Profil du monument à évaluer :
{monument_profile}

Conditions d'éligibilité de l'aide "{aide_nom}" :
{conditions_detail}

Analyse ce dossier de manière STRICTE. Pour chaque critère d'éligibilité, vérifie si le monument le satisfait complètement. Sois sceptique face aux ambiguïtés : en cas de doute, considère que le critère n'est pas clairement satisfait.

Réponds en JSON strict avec ce format :
{{
  "eligible": true ou false,
  "explication": "Explication en 1-2 phrases détaillant les critères satisfaits ou non",
  "incertitudes": ["Liste des critères ambigus ou non vérifiables"]
}}

Sois particulièrement rigoureux : mets eligible à false si des doutes subsistent sur les critères essentiels. Cependant, si tous les critères essentiels sont clairement satisfaits, mets eligible à true même s'il y a des incertitudes mineures.
"""

prompt_3 = """
Tu es un expert en financement du patrimoine bâti en France.

Monument :
{monument_profile}

Aide "{aide_nom}" - Conditions d'éligibilité :
{conditions_detail}

Procède par élimination. Identifie d'abord les critères qui rendent INÉLIGIBLE un monument (les disqualifiants). Si le monument présente l'une de ces caractéristiques, il ne peut pas être éligible. Ensuite, vérifie si tous les critères positifs requis sont présents.

Réponds en JSON strict avec ce format :
{{
  "eligible": true ou false,
  "explication": "Explication en 1-2 phrases synthétisant les critères disqualifiants ou les critères positifs manquants",
  "incertitudes": ["Liste des informations manquantes pour confirmer l'éligibilité"]
}}

Si un critère disqualifiant est clairement présent, mets eligible à false, même avec d'autres éléments positifs.
"""

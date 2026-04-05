prompt_1 = """
Tu es un expert en financement du patrimoine bâti en France.

Voici le profil d'un monument :
{monument_profile}

Voici les conditions d'éligibilité détaillées de l'aide "{aide_nom}" :
{conditions_detail}

Ta mission : identifier uniquement les conditions d'éligibilité qui sont CLAIREMENT et EXPLICITEMENT non respectées par ce monument, c'est-à-dire quand une condition requiert quelque chose que le profil contredit formellement.

Si une condition n'est pas mentionnée dans le profil (ex: ouverture au public, usage commercial, etc.), ne la considère PAS comme non respectée — liste-la dans les incertitudes.

Réponds en JSON strict avec ce format :
{{
  "eligible": true ou false,
  "explication": "Explication en 1-2 phrases de ta conclusion",
  "incertitudes": ["Liste des conditions qui ne peuvent pas être vérifiées faute d'informations"]
}}

Règle stricte : mets eligible à false UNIQUEMENT si le profil contient une information qui contredit explicitement une condition requise (ex: protection requise = classé, mais le monument est inscrit). Dans tous les autres cas de doute, mets eligible à true et liste les incertitudes.
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

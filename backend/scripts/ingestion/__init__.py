"""Agent d'ingestion d'une aide : le skill `/ingest-aide`, mais payé à l'API.

Le prompt système EST `.claude/skills/ingest-aide/SKILL.md`, chargé tel quel :
la doctrine ne vit qu'à un endroit, et une modification du skill change le
pipeline le jour même. Ce package n'ajoute que le harnais — des outils bornés
au slug, une boucle qui tient un budget, et des post-contrôles déterministes
qui refusent de laisser passer une aide que le lint n'accepte pas.

Ce que l'agent ne fait JAMAIS, quel que soit son verdict : `git add`, un commit,
`load_aides_yaml.py`. Ce sont les commandes qu'on rend à l'utilisateur.
"""

"""Socle commun du pipeline de prospection et d'ingestion.

Quatre briques sans dépendance métier, partagées par `prospecter.py` et
`ingerer.py` :

  - `verrou`  : écriture concurrente sûre (facts_pending.yaml, file d'attente)
  - `etat`    : la file d'attente des aides à ingérer, un fichier YAML par slug
  - `web`     : un fetcheur poli, qui sait franchir les WAF connus
  - `llm`     : résolution du modèle par rôle et comptage du coût

Rien ici ne connaît le schéma des aides : c'est ce qui permet de tester chaque
brique sans charger les 130 YAML du catalogue.
"""

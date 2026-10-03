"""Prospection : d'un territoire à une liste d'URL candidates, en trois étages.

  collecte → tri → lecture → fiche

Le premier étage n'appelle aucun modèle (sauf sur un site inconnu), le second
trie au kilo, le troisième ouvre les fiches retenues. Séparer les trois permet
de rejouer le tri sans retélécharger, et de tester chaque étage sans réseau.
"""

"""Recherche de communes pour l'autocomplétion (création de projet, onboarding).

Ce qui est couvert : la normalisation de la saisie (accents, séparateurs,
métacaractères ILIKE) et l'ordre des résultats — les noms qui COMMENCENT par la
saisie avant ceux qui la CONTIENNENT. Le fake enregistre les motifs reçus, seul
moyen de vérifier qu'on n'envoie jamais un `%` venu de l'utilisateur.
"""

import unittest

from routers.communes import _tokens, search_communes


def _commune(nom: str, matching: str | None = None) -> dict:
    return {
        "code_insee": nom[:5].lower(),
        "nom_commune": nom,
        "nom_commune_matching": matching or nom.lower(),
        "departement": "Essonne",
        "departement_num": "91",
        "region": "Île-de-France",
        "arrondissement": None,
        "population": 1500,
    }


class _Resp:
    def __init__(self, data):
        self.data = data


class _Table:
    """Table `communes` en mémoire : filtre ILIKE réduit aux motifs qu'on émet."""

    def __init__(self, rows: list[dict], patterns: list[str]):
        self._rows = rows
        self._patterns = patterns
        self._pattern = ""
        self._limit = None

    def select(self, *a, **k):
        return self

    def ilike(self, column, pattern):
        assert column == "nom_commune_matching"
        self._pattern = pattern
        self._patterns.append(pattern)
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        prefix = not self._pattern.startswith("%")
        needle = self._pattern.strip("%")
        parts = needle.split("%")
        matched = []
        for row in sorted(self._rows, key=lambda r: r["nom_commune"]):
            name = row["nom_commune_matching"]
            pos = 0
            ok = True
            for i, part in enumerate(parts):
                found = name.find(part, pos)
                if found < 0 or (prefix and i == 0 and found != 0):
                    ok = False
                    break
                pos = found + len(part)
            if ok:
                matched.append(row)
        return _Resp(matched[: self._limit])


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows
        self.patterns: list[str] = []

    def table(self, name):
        assert name == "communes"
        return _Table(self._rows, self.patterns)


ROWS = [
    _commune("Gomené", "gomene"),
    _commune("Gometz-la-Ville", "gometz-la-ville"),
    _commune("Gometz-le-Châtel", "gometz-le-chatel"),
    _commune("Colleville-Montgomery", "colleville-montgomery"),
    _commune("Trégomeur", "tregomeur"),
    _commune("Saint-Jean-aux-Bois", "saint-jean-aux-bois"),
]


class TokenTests(unittest.TestCase):
    def test_accents_et_casse_normalises(self):
        self.assertEqual(_tokens("Gométz"), ["gometz"])

    def test_separateurs_donnent_des_tokens(self):
        self.assertEqual(_tokens("saint jean"), ["saint", "jean"])
        self.assertEqual(_tokens("Saint-Jean"), ["saint", "jean"])
        self.assertEqual(_tokens("l'Aigle"), ["l", "aigle"])

    def test_metacaracteres_ilike_ecartes(self):
        """`%` et `_` ne doivent jamais atteindre le motif : rien d'injectable."""
        self.assertEqual(_tokens("%gome_"), ["gome"])


class SearchTests(unittest.TestCase):
    def _search(self, q, limit=10):
        sb = _FakeSupabase(ROWS)
        return [r["nom"] for r in search_communes(q=q, limit=limit, supabase=sb)], sb.patterns

    def test_prefixes_avant_contenus(self):
        noms, _ = self._search("gome")
        self.assertEqual(
            noms,
            [
                "Gomené",
                "Gometz-la-Ville",
                "Gometz-le-Châtel",
                "Colleville-Montgomery",
                "Trégomeur",
            ],
        )

    def test_deuxieme_requete_evitee_quand_les_prefixes_suffisent(self):
        _, patterns = self._search("gome", limit=2)
        self.assertEqual(patterns, ["gome%"])

    def test_separateur_indifferent(self):
        noms, _ = self._search("saint jean")
        self.assertEqual(noms, ["Saint-Jean-aux-Bois"])

    def test_saisie_sans_lettre_ne_requete_pas(self):
        sb = _FakeSupabase(ROWS)
        self.assertEqual(search_communes(q="%%", limit=10, supabase=sb), [])
        self.assertEqual(sb.patterns, [])

    def test_forme_de_sortie(self):
        sb = _FakeSupabase([_commune("Gomené", "gomene")])
        row = search_communes(q="gomene", limit=5, supabase=sb)[0]
        self.assertEqual(
            row,
            {
                "codeInsee": "gomen",
                "nom": "Gomené",
                "departement": "Essonne",
                "codeDepartement": "91",
                "region": "Île-de-France",
                "arrondissement": None,
                "population": 1500,
            },
        )


if __name__ == "__main__":
    unittest.main()

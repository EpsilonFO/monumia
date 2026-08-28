"""Photo de profil du monument : pose, remplacement, retrait, lien signé.

Le bucket est privé : les photos sont stockées sous « <user_id>/… » et ne
s'affichent que via un lien signé posé à la lecture. Ces tests couvrent le
câblage des endpoints ; le contrôle d'accès lui-même est couvert par les tests
de require_project_access.
"""

import unittest

from fastapi import HTTPException

from routers.monuments import (
    PhotoProfilRequest,
    remove_photo_profil,
    set_photo_profil,
    sign_photos,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Table:
    """Le vrai client rend un dict après single(), une liste sinon."""

    def __init__(self, row, updates):
        self._row = row
        self._updates = updates
        self._single = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def update(self, payload):
        self._updates.append(payload)
        return self

    def execute(self):
        if self._single:
            return _Resp(self._row)
        return _Resp([] if self._row is None else [self._row])


class _Bucket:
    def __init__(self, removed):
        self._removed = removed

    def create_signed_urls(self, paths, expires_in):
        return [{"path": p, "signedURL": f"https://x/sign/{p}?token=abc"} for p in paths]

    def remove(self, paths):
        self._removed.extend(paths)


class _Storage:
    def __init__(self, removed):
        self._removed = removed

    def from_(self, bucket):
        return _Bucket(self._removed)


class _FakeSupabase:
    """Le propriétaire du monument passe require_project_access par le repli
    « user_id du monument » — inutile de modéliser project_members."""

    def __init__(self, monument):
        self._monument = monument
        self.updates: list[dict] = []
        self.removed: list[str] = []
        self.storage = _Storage(self.removed)

    def table(self, name):
        return _Table(self._monument if name == "monuments" else None, self.updates)


def _monument(photos):
    return {"id": "m1", "user_id": "u1", "photos": photos}


class SetPhotoProfilTests(unittest.TestCase):
    def test_pose_la_photo_en_tete_avec_lien_signe(self):
        fake = _FakeSupabase(_monument([]))
        out = set_photo_profil(
            "m1", PhotoProfilRequest(url="u1/photo.jpg"), user_id="u1", supabase=fake
        )
        self.assertEqual(out["type"], "profil")
        self.assertEqual(out["url"], "u1/photo.jpg")
        self.assertIn("u1/photo.jpg", out["signed_url"])
        self.assertEqual(fake.updates[0]["photos"][0]["url"], "u1/photo.jpg")

    def test_remplace_lancienne_et_efface_son_fichier(self):
        fake = _FakeSupabase(
            _monument(
                [
                    {"id": "p0", "url": "u1/vieille.jpg", "type": "profil", "legende": ""},
                    {"id": "p1", "url": "u1/facade.jpg", "type": "facade", "legende": ""},
                ]
            )
        )
        set_photo_profil("m1", PhotoProfilRequest(url="u1/neuve.jpg"), user_id="u1", supabase=fake)
        photos = fake.updates[0]["photos"]
        # Une seule photo de profil, en tête ; la façade reste dans la galerie.
        self.assertEqual([p["type"] for p in photos], ["profil", "facade"])
        self.assertEqual(photos[0]["url"], "u1/neuve.jpg")
        self.assertEqual(fake.removed, ["u1/vieille.jpg"])

    def test_refuse_le_dossier_dun_autre_utilisateur(self):
        fake = _FakeSupabase(_monument([]))
        with self.assertRaises(HTTPException) as ctx:
            set_photo_profil(
                "m1", PhotoProfilRequest(url="u2/photo.jpg"), user_id="u1", supabase=fake
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_refuse_une_url_absolue(self):
        fake = _FakeSupabase(_monument([]))
        with self.assertRaises(HTTPException) as ctx:
            set_photo_profil(
                "m1",
                PhotoProfilRequest(url="https://evil/x.jpg"),
                user_id="u1",
                supabase=fake,
            )
        self.assertEqual(ctx.exception.status_code, 400)


class RemovePhotoProfilTests(unittest.TestCase):
    def test_retire_la_photo_et_son_fichier(self):
        fake = _FakeSupabase(
            _monument([{"id": "p0", "url": "u1/photo.jpg", "type": "profil", "legende": ""}])
        )
        remove_photo_profil("m1", user_id="u1", supabase=fake)
        self.assertEqual(fake.updates[0]["photos"], [])
        self.assertEqual(fake.removed, ["u1/photo.jpg"])

    def test_404_sans_photo_de_profil(self):
        fake = _FakeSupabase(_monument([]))
        with self.assertRaises(HTTPException) as ctx:
            remove_photo_profil("m1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 404)


class SignPhotosTests(unittest.TestCase):
    def test_signe_en_place_sans_toucher_aux_url_absolues(self):
        fake = _FakeSupabase(_monument([]))
        monuments = [
            {"photos": [{"url": "u1/a.jpg"}, {"url": "https://cdn/x.jpg"}]},
            {"photos": None},
        ]
        sign_photos(fake, monuments)
        self.assertIn("u1/a.jpg", monuments[0]["photos"][0]["signed_url"])
        self.assertNotIn("signed_url", monuments[0]["photos"][1])


if __name__ == "__main__":
    unittest.main()

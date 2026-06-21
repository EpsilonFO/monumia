"""Politique de mot de passe à l'inscription : au moins 8 caractères et 1 chiffre."""

import unittest

from fastapi import HTTPException

from routers.auth import _validate_password


class PasswordPolicyTests(unittest.TestCase):
    def test_accepts_8_chars_with_digit(self):
        _validate_password("abcdefg1")  # ne lève pas

    def test_rejects_too_short(self):
        with self.assertRaises(HTTPException) as ctx:
            _validate_password("abc123")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_no_digit(self):
        with self.assertRaises(HTTPException) as ctx:
            _validate_password("abcdefgh")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_accepts_long_with_digit(self):
        _validate_password("motdepasse2026")


if __name__ == "__main__":
    unittest.main()

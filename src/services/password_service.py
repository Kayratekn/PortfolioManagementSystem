from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


class PasswordService:
    algorithm = "pbkdf2_sha256"
    iterations = 100_000
    salt_size = 16

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = secrets.token_bytes(cls.salt_size)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.iterations,
        )
        encoded_salt = base64.b64encode(salt).decode("utf-8")
        encoded_hash = base64.b64encode(password_hash).decode("utf-8")
        return f"{cls.algorithm}${cls.iterations}${encoded_salt}${encoded_hash}"

    @classmethod
    def verify_password(cls, password: str, hashed_password: str) -> bool:
        try:
            algorithm, iteration_text, encoded_salt, encoded_hash = hashed_password.split("$", maxsplit=3)
        except ValueError:
            return False

        if algorithm != cls.algorithm:
            return False

        try:
            iterations = int(iteration_text)
            salt = base64.b64decode(encoded_salt.encode("utf-8"))
            stored_hash = base64.b64decode(encoded_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(computed_hash, stored_hash)

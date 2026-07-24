from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any


class TokenService:
    def __init__(
        self,
        secret_key: str,
        issuer: str,
        access_token_expire_minutes: int = 60,
    ) -> None:
        self.secret_key = secret_key
        self.issuer = issuer
        self.access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(self, subject: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": subject,
            "iss": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self.access_token_expire_minutes)).timestamp()),
        }
        header = {"alg": "HS256", "typ": "JWT"}
        return self._encode_token(header, payload)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            header_segment, payload_segment, signature_segment = token.split(".")
        except ValueError as error:
            raise ValueError("Invalid token format.") from error

        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        expected_signature = self._sign(signing_input)
        actual_signature = self._base64url_decode(signature_segment)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid token signature.")

        payload = json.loads(self._base64url_decode(payload_segment).decode("utf-8"))
        if payload.get("iss") != self.issuer:
            raise ValueError("Invalid token issuer.")

        expiration = payload.get("exp")
        if not isinstance(expiration, int):
            raise ValueError("Invalid token expiration.")

        if expiration < int(datetime.now(UTC).timestamp()):
            raise ValueError("Token expired.")

        return payload

    def _encode_token(self, header: dict[str, Any], payload: dict[str, Any]) -> str:
        encoded_header = self._base64url_encode(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        encoded_payload = self._base64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        encoded_signature = self._base64url_encode(self._sign(signing_input))
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def _sign(self, data: bytes) -> bytes:
        return hmac.new(
            self.secret_key.encode("utf-8"),
            data,
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _base64url_encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _base64url_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))

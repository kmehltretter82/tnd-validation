"""Mint a short-lived, repository-scoped GitHub App installation token.

Used by ``orchestrator.merge_lane`` inside the ``tnd-merge`` environment so the
serialized merge workflow authenticates as the dedicated GitHub App without
adding third-party Actions or persisting credentials on disk.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

APP_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
API_BASE = "https://api.github.com"
MAX_KEY_BYTES = 64 * 1024
MAX_API_BYTES = 256 * 1024


class GitHubAppError(RuntimeError):
    """Failed to mint a repository-scoped GitHub App installation token."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_rs256(signing_input: bytes, private_key_pem: str) -> bytes:
    raw_key = private_key_pem.strip().encode("utf-8")
    if (
        not 64 <= len(raw_key) <= MAX_KEY_BYTES
        or b"\0" in raw_key
        or not raw_key.startswith(b"-----BEGIN ")
        or b"PRIVATE KEY-----" not in raw_key
    ):
        raise GitHubAppError("GitHub App private key is missing or malformed")
    with tempfile.TemporaryDirectory(prefix="tnd-app-key-") as directory:
        key_path = Path(directory) / "app.pem"
        fd = os.open(
            key_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw_key + b"\n")
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(key_path)],
                input=signing_input,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise GitHubAppError("openssl failed to sign GitHub App JWT") from error
        finally:
            with contextlib.suppress(OSError):
                key_path.unlink()
    if result.returncode != 0 or not result.stdout:
        raise GitHubAppError("openssl rejected the GitHub App private key")
    return result.stdout


def build_app_jwt(
    app_id: str, private_key_pem: str, *, now: int | None = None,
) -> str:
    """Create a 9-minute RS256 JWT for the given GitHub App ID."""
    if not isinstance(app_id, str) or not APP_ID.fullmatch(app_id):
        raise GitHubAppError("GitHub App ID must be a positive integer")
    issued = int(time.time()) if now is None else int(now)
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {"iat": issued - 60, "exp": issued + 540, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64url(_sign_rs256(signing_input, private_key_pem))
    return f"{header}.{payload}.{signature}"


def _api_json(
    method: str,
    url: str,
    bearer_jwt: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {bearer_jwt}",
            "User-Agent": "tndlib-merge-lane",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_API_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise GitHubAppError(
            f"GitHub App API {method} {url} failed with HTTP {error.code}"
        ) from error
    except (OSError, urllib.error.URLError) as error:
        raise GitHubAppError(f"GitHub App API {method} {url} transport failed") from error
    if len(raw) > MAX_API_BYTES:
        raise GitHubAppError("GitHub App API response exceeded size limit")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise GitHubAppError("GitHub App API returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise GitHubAppError("GitHub App API response is not a JSON object")
    return parsed


def mint_installation_token(
    repo: str,
    app_id: str,
    private_key_pem: str,
    *,
    api_base: str = API_BASE,
) -> str:
    """Mint an installation token scoped to ``repo`` alone."""
    if (
        not isinstance(repo, str)
        or not REPOSITORY.fullmatch(repo)
        or any(part in {".", ".."} for part in repo.split("/"))
    ):
        raise GitHubAppError("invalid repository name for GitHub App token")
    jwt_token = build_app_jwt(app_id, private_key_pem)
    installation = _api_json("GET", f"{api_base}/repos/{repo}/installation", jwt_token)
    installation_id = installation.get("id")
    reported_app_id = installation.get("app_id")
    if (
        isinstance(installation_id, bool)
        or not isinstance(installation_id, int)
        or installation_id < 1
        or isinstance(reported_app_id, bool)
        or reported_app_id != int(app_id)
    ):
        raise GitHubAppError(
            "GitHub App installation metadata does not match the configured App ID"
        )
    repo_name = repo.split("/", 1)[1]
    token_response = _api_json(
        "POST",
        f"{api_base}/app/installations/{installation_id}/access_tokens",
        jwt_token,
        payload={"repositories": [repo_name]},
    )
    token = token_response.get("token")
    if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
        raise GitHubAppError("GitHub App API did not return a valid installation token")
    return token

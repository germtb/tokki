"""Load environment variables for e2e tests."""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Load agent's .env (MOONSHOT_API_KEY, etc.)
_agent_env = Path(__file__).resolve().parents[3] / "agents" / "toolcall" / ".env"
load_dotenv(_agent_env)

# Load test-specific .env (MCP vars for local server testing)
_test_env = Path(__file__).resolve().parent / ".env"
load_dotenv(_test_env)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt(signing_key: str, username: str) -> str:
    """Generate a minimal HMAC-SHA256 JWT with sub claim."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": username,
                "ctn": f"persona__{username}__test",
                "iat": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
    )
    msg = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(signing_key.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


# If MCP_SIGNING_KEY and TOKKI_MCP_USER are set, generate a valid JWT
# so that MCP tests can authenticate with the server.
_signing_key = os.environ.get("MCP_SIGNING_KEY")
_mcp_user = os.environ.get("TOKKI_MCP_USER")
if _signing_key and _mcp_user:
    os.environ["TOKKI_MCP_TOKEN"] = _make_jwt(_signing_key, _mcp_user)

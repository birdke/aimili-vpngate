#!/usr/bin/env python3
"""A restricted, cached relay for the public VPNGate CSV API.

This is deliberately not a general-purpose HTTP proxy. It exposes only the
VPNGate CSV endpoint and requires a bearer token.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import threading
import time
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from vpngate_api import VPNGateAPIResponseError, build_api_request_headers, validate_vpngate_csv


DEFAULT_UPSTREAM = "https://www.vpngate.net/api/iphone/"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if minimum <= value <= maximum else default


RELAY_HOST = os.environ.get("VPNGATE_RELAY_HOST", "127.0.0.1")
RELAY_PORT = env_int("VPNGATE_RELAY_PORT", 8790, 1, 65535)
RELAY_TOKEN = os.environ.get("VPNGATE_RELAY_TOKEN", "").strip()
ALLOWED_IPS = {
    item.strip()
    for item in os.environ.get("VPNGATE_RELAY_ALLOWED_IPS", "").split(",")
    if item.strip()
}
UPSTREAM_URL = os.environ.get("VPNGATE_RELAY_UPSTREAM", DEFAULT_UPSTREAM).strip() or DEFAULT_UPSTREAM
CACHE_TTL_SECONDS = env_int("VPNGATE_RELAY_CACHE_TTL", 600, 30, 86400)
STALE_TTL_SECONDS = env_int("VPNGATE_RELAY_STALE_TTL", 86400, CACHE_TTL_SECONDS, 604800)
UPSTREAM_TIMEOUT_SECONDS = env_int("VPNGATE_RELAY_TIMEOUT", 30, 3, 120)


def normalize_ip(value: str) -> str:
    if value.startswith("::ffff:"):
        return value[7:]
    return value


class RelayCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._body = b""
        self._fetched_at = 0.0
        self._node_count = 0
        self._last_error = ""

    def status(self) -> dict[str, Any]:
        age = max(0, int(time.time() - self._fetched_at)) if self._fetched_at else None
        return {
            "ok": bool(self._body),
            "cached": bool(self._body),
            "cache_age_seconds": age,
            "node_count": self._node_count,
            "last_error": self._last_error,
        }

    def _fetch_upstream(self) -> tuple[bytes, int]:
        request = urllib.request.Request(
            UPSTREAM_URL,
            headers=build_api_request_headers("Mozilla/5.0 aimilivpn-api-relay/1.0"),
        )
        with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("VPNGate API response exceeded the 10 MiB limit")
        text = body.decode("utf-8", errors="replace")
        node_count = validate_vpngate_csv(text)
        return body, node_count

    def get(self) -> tuple[bytes, int, bool]:
        now = time.time()
        if self._body and now - self._fetched_at < CACHE_TTL_SECONDS:
            return self._body, self._node_count, True

        with self._lock:
            now = time.time()
            if self._body and now - self._fetched_at < CACHE_TTL_SECONDS:
                return self._body, self._node_count, True
            try:
                body, node_count = self._fetch_upstream()
            except Exception as exc:
                self._last_error = str(exc)
                if self._body and now - self._fetched_at < STALE_TTL_SECONDS:
                    return self._body, self._node_count, True
                raise
            self._body = body
            self._node_count = node_count
            self._fetched_at = time.time()
            self._last_error = ""
            return body, node_count, False


CACHE = RelayCache()


class RelayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "AimiliVPNRelay/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {normalize_ip(self.client_address[0])} {fmt % args}", flush=True)

    def _client_allowed(self) -> bool:
        client_ip = normalize_ip(self.client_address[0])
        return client_ip in {"127.0.0.1", "::1"} or not ALLOWED_IPS or client_ip in ALLOWED_IPS

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {RELAY_TOKEN}"
        return bool(RELAY_TOKEN) and hmac.compare_digest(supplied, expected)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if not self._client_allowed():
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "source IP is not allowed"})
            return

        if path == "/healthz":
            self._send_json(HTTPStatus.OK, CACHE.status())
            return

        if path not in ("/api/iphone", "/api/iphone/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid relay token"})
            return

        try:
            body, node_count, cache_hit = CACHE.get()
        except VPNGateAPIResponseError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"upstream request failed: {exc}"})
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", f"private, max-age={CACHE_TTL_SECONDS}")
        self.send_header("X-AimiliVPN-Cache", "HIT" if cache_hit else "MISS")
        self.send_header("X-AimiliVPN-Nodes", str(node_count))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    if not RELAY_TOKEN:
        raise SystemExit("VPNGATE_RELAY_TOKEN must be set")
    if "\r" in RELAY_TOKEN or "\n" in RELAY_TOKEN:
        raise SystemExit("VPNGATE_RELAY_TOKEN must not contain line breaks")
    if not UPSTREAM_URL.startswith("https://"):
        raise SystemExit("VPNGATE_RELAY_UPSTREAM must use HTTPS")

    if "--check" in sys.argv[1:]:
        body, node_count, _ = CACHE.get()
        print(f"VPNGate API OK: {node_count} nodes, {len(body)} bytes")
        return

    server = RelayHTTPServer((RELAY_HOST, RELAY_PORT), Handler)
    print(
        f"AimiliVPN API relay listening on {RELAY_HOST}:{RELAY_PORT}; "
        f"cache={CACHE_TTL_SECONDS}s; allowlist={len(ALLOWED_IPS)} IP(s)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

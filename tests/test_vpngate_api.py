from __future__ import annotations

import threading
import time
import unittest
import urllib.error
import urllib.request

import vpngate_api_relay as relay
from vpngate_api import VPNGateAPIResponseError, build_api_request_headers, parse_vpngate_csv


HEADER = (
    "#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,NumVpnSessions,"
    "Uptime,TotalUsers,TotalTraffic,LogType,Operator,Message,OpenVPN_ConfigData_Base64"
)
VALID_TEXT = "\n".join(
    [
        "*vpn_servers",
        HEADER,
        "vpn1,192.0.2.1,1,2,3,Japan,JP,4,5,6,7,2weeks,owner,,Y29uZmln",
        "*",
    ]
)


class ParseVPNGateCSVTests(unittest.TestCase):
    def test_parses_valid_response(self) -> None:
        rows = parse_vpngate_csv(VALID_TEXT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["IP"], "192.0.2.1")

    def test_rejects_html_success_page(self) -> None:
        with self.assertRaisesRegex(VPNGateAPIResponseError, "ERR_API_HTML_RESPONSE"):
            parse_vpngate_csv("\n<!DOCTYPE html><html><body></body></html>")

    def test_rejects_missing_header(self) -> None:
        with self.assertRaisesRegex(VPNGateAPIResponseError, "ERR_API_INVALID_RESPONSE"):
            parse_vpngate_csv("*vpn_servers\nnot,a,vpngate,header\n*")

    def test_rejects_header_without_nodes(self) -> None:
        with self.assertRaisesRegex(VPNGateAPIResponseError, "ERR_API_NO_NODES"):
            parse_vpngate_csv(f"*vpn_servers\n{HEADER}\n*")

    def test_builds_bearer_header_and_rejects_line_breaks(self) -> None:
        headers = build_api_request_headers("test-agent", "test-token")
        self.assertEqual(headers["Authorization"], "Bearer test-token")
        with self.assertRaises(ValueError):
            build_api_request_headers("test-agent", "bad\ntoken")


class RelayHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_token = relay.RELAY_TOKEN
        self.old_allowed_ips = relay.ALLOWED_IPS
        self.old_cache = relay.CACHE
        relay.RELAY_TOKEN = "test-relay-token"
        relay.ALLOWED_IPS = {"198.51.100.20"}
        relay.CACHE = relay.RelayCache()
        relay.CACHE._body = VALID_TEXT.encode("utf-8")
        relay.CACHE._node_count = 1
        relay.CACHE._fetched_at = time.time()
        self.server = relay.RelayHTTPServer(("127.0.0.1", 0), relay.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/iphone/"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        relay.RELAY_TOKEN = self.old_token
        relay.ALLOWED_IPS = self.old_allowed_ips
        relay.CACHE = self.old_cache

    def test_requires_bearer_token(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url, timeout=2)
        try:
            self.assertEqual(caught.exception.code, 401)
        finally:
            caught.exception.close()

    def test_serves_cached_csv_with_token(self) -> None:
        request = urllib.request.Request(
            self.url,
            headers={"Authorization": "Bearer test-relay-token"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.headers["X-AimiliVPN-Cache"], "HIT")
            self.assertEqual(response.headers["X-AimiliVPN-Nodes"], "1")
        self.assertEqual(body, VALID_TEXT)

if __name__ == "__main__":
    unittest.main()

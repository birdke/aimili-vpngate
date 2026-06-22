from __future__ import annotations

import os
import unittest
from unittest import mock

import vpn_utils


class UpstreamProxySettingsTests(unittest.TestCase):
    def test_normalizes_http_settings(self) -> None:
        settings = vpn_utils.normalize_upstream_proxy_settings(
            {
                "enabled": True,
                "type": "HTTP",
                "host": "proxy.example.com",
                "port": "3128",
                "username": "user",
                "password": "secret",
                "use_for_openvpn": False,
            }
        )
        self.assertEqual(settings["type"], "http")
        self.assertEqual(settings["port"], 3128)
        self.assertEqual(settings["password"], "secret")

    def test_rejects_invalid_enabled_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须填写主机"):
            vpn_utils.normalize_upstream_proxy_settings({"enabled": True, "type": "socks", "port": 1080})
        with self.assertRaisesRegex(ValueError, "必须同时填写用户名"):
            vpn_utils.normalize_upstream_proxy_settings(
                {"enabled": True, "type": "http", "host": "127.0.0.1", "port": 8080, "password": "secret"}
            )

    def test_web_proxy_defaults_to_api_only(self) -> None:
        settings = vpn_utils.normalize_upstream_proxy_settings(
            {"enabled": True, "type": "socks", "host": "127.0.0.1", "port": 1080}
        )
        with mock.patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.9:9999"}, clear=True), mock.patch.object(
            vpn_utils, "load_upstream_proxy_settings", return_value=settings
        ):
            self.assertEqual(vpn_utils.get_upstream_proxy("api"), ("socks", "127.0.0.1", 1080))
            self.assertEqual(vpn_utils.get_upstream_proxy("openvpn"), (None, None, None))

    def test_explicit_environment_proxy_takes_precedence(self) -> None:
        settings = vpn_utils.normalize_upstream_proxy_settings(
            {"enabled": True, "type": "http", "host": "web-proxy", "port": 8080}
        )
        with mock.patch.dict(
            os.environ,
            {"OPENVPN_UPSTREAM_SOCKS": "socks5://env-user:env-pass@127.0.0.2:1081"},
            clear=True,
        ), mock.patch.object(vpn_utils, "load_upstream_proxy_settings", return_value=settings):
            self.assertEqual(vpn_utils.get_upstream_proxy("api"), ("socks", "127.0.0.2", 1081))
            self.assertEqual(vpn_utils.get_upstream_proxy_auth("api"), ("env-user", "env-pass"))

    def test_status_never_returns_password(self) -> None:
        settings = vpn_utils.normalize_upstream_proxy_settings(
            {
                "enabled": True,
                "type": "http",
                "host": "proxy.example.com",
                "port": 8080,
                "username": "user",
                "password": "top-secret",
            }
        )
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            vpn_utils, "load_upstream_proxy_settings", return_value=settings
        ):
            status = vpn_utils.get_upstream_proxy_status()
        self.assertTrue(status["password_set"])
        self.assertNotIn("password", status)


if __name__ == "__main__":
    unittest.main()

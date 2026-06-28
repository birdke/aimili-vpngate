from __future__ import annotations

import os
import unittest
from unittest import mock

import vpn_utils


class TunInterfaceSettingsTests(unittest.TestCase):
    def test_default_interface_avoids_common_tun0_conflict(self) -> None:
        self.assertEqual(vpn_utils.normalize_tun_interface_name(""), "aimili0")

    def test_accepts_safe_linux_interface_names(self) -> None:
        self.assertEqual(vpn_utils.normalize_tun_interface_name("aimili1"), "aimili1")
        self.assertEqual(vpn_utils.normalize_tun_interface_name("vpn_gate.1"), "vpn_gate.1")

    def test_rejects_unsafe_or_too_long_names(self) -> None:
        for value in ("bad/name", "bad:name", "-bad", "default", "a" * 16):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    vpn_utils.normalize_tun_interface_name(value)

    def test_environment_override(self) -> None:
        with mock.patch.dict(os.environ, {"VPNGATE_TUN_INTERFACE": "aimili9"}, clear=True):
            self.assertEqual(vpn_utils.get_tun_interface_from_env(), "aimili9")


if __name__ == "__main__":
    unittest.main()

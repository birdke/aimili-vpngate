from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

# Importing the manager initializes Web settings; keep them outside the checkout.
_original_getaddrinfo = socket.getaddrinfo
with tempfile.TemporaryDirectory() as _import_dir:
    with mock.patch.dict(os.environ, {"VPNGATE_DATA_DIR": _import_dir}):
        import vpngate_manager as manager
socket.getaddrinfo = _original_getaddrinfo


class ManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.data_dir = Path(temp.name)
        self.config_dir = self.data_dir / "configs"
        self.config_dir.mkdir()
        for name, value in {
            "DATA_DIR": self.data_dir,
            "CONFIG_DIR": self.config_dir,
            "NODES_FILE": self.data_dir / "nodes.json",
            "STATE_FILE": self.data_dir / "state.json",
            "AUTH_FILE": self.data_dir / "auth.txt",
            "BLACKLIST_FILE": self.data_dir / "blacklist.json",
            "active_openvpn_node_id": "old",
            "active_openvpn_process": mock.Mock(),
            "is_connecting": False,
            "connection_lock": threading.RLock(),
            "maintenance_lock": threading.Lock(),
            "recovery_lock": threading.Lock(),
            "PROXY_CHECK_FAILURE_THRESHOLD": 2,
        }.items():
            self.patch(manager, name, value)
        manager.active_openvpn_process.poll.return_value = None
        self.patch(manager, "cleanup_policy_routing", mock.Mock())
        self.patch(manager, "stop_process", mock.Mock())
        self.patch(manager, "log_to_json", mock.Mock())
        self.patch(manager.vpn_utils, "ping_latency_ms", mock.Mock(return_value=10))
        self.save_config()
        self.save_nodes()

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def save_config(self, **updates) -> None:
        config = manager.load_ui_config()
        config.update(updates)
        manager.write_json(self.data_dir / "ui_auth.json", config)

    def save_nodes(self) -> None:
        manager.write_json(manager.NODES_FILE, [
            {"id": node_id, "active": node_id == "old", "probe_status": "available",
             "latency_ms": latency, "config_file": str(self.config_dir / f"{node_id}.ovpn"),
             "config_text": "client\n", "ip": "192.0.2.1", "remote_port": 443}
            for node_id, latency in (("old", 5), ("bad", 10), ("good", 20))
        ])


class ProxyHealthTests(ManagerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.patch(manager.socket, "socket", mock.Mock())
        self.patch(manager, "get_vpn_interface", mock.Mock(return_value="lo"))
        self.patch(manager.sys, "platform", "linux")
        self.patch(manager.Path, "exists", mock.Mock(return_value=True))

    def test_http_ip_service_cannot_hide_https_failure(self) -> None:
        request = self.patch(manager, "curl_through_local_proxy", mock.Mock(return_value=None))
        self.assertFalse(manager.check_proxy_health()["ok"])
        self.assertEqual([c.args[0] for c in request.call_args_list], list(manager.PROXY_HEALTH_URLS))
        self.assertTrue(all(url.startswith("https://") for url in manager.PROXY_HEALTH_URLS))

    def test_secondary_https_target_and_optional_ip_lookup(self) -> None:
        self.patch(manager, "curl_through_local_proxy", mock.Mock(side_effect=[None, ("", 80, 200), None, None]))
        self.assertEqual(manager.check_proxy_health(), {"ok": True, "ip": "-", "latency_ms": 80})

    def test_rejects_html_as_exit_ip(self) -> None:
        self.patch(manager, "curl_through_local_proxy", mock.Mock(side_effect=[
            ("", 12, 204), ("<html>error</html>", 30, 200), ("2001:db8::1", 25, 200),
        ]))
        self.assertEqual(manager.check_proxy_health()["ip"], "2001:db8::1")

    def test_redirect_is_not_a_successful_probe(self) -> None:
        self.patch(manager, "curl_through_local_proxy", mock.Mock(return_value=("", 10, 302)))
        self.assertFalse(manager.check_proxy_health()["ok"])

    def test_curl_forces_proxy_despite_no_proxy_and_disables_curlrc(self) -> None:
        self.patch(manager, "LOCAL_PROXY_HOST", "127.0.0.1")
        self.patch(manager.proxy_server, "get_proxy_credentials", mock.Mock(return_value=("user", "pass")))
        run = self.patch(manager.subprocess, "run", mock.Mock(return_value=subprocess.CompletedProcess([], 0, "\n0.125 204", "")))
        self.assertEqual(manager.curl_through_local_proxy("https://example.com"), ("", 125, 204))
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["curl", "--disable"])
        self.assertEqual(command[command.index("--noproxy") + 1], "")
        self.assertEqual(command[command.index("--proto") + 1], "=https")
        self.assertEqual(command[command.index("--proxy-user") + 1], "user:pass")
        self.assertTrue(command[command.index("--proxy") + 1].startswith("socks5h://"))


class ProxyRecoveryTests(ManagerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.health = self.patch(manager, "check_proxy_health", mock.Mock(return_value={"ok": False, "error": "HTTPS timed out"}))
        self.switch = self.patch(manager, "auto_switch_node", mock.Mock())
        self.monitor = manager.ProxyHealthMonitor()

    def test_live_process_with_dead_traffic_switches_after_two_failures(self) -> None:
        self.monitor.check_once()
        self.switch.assert_not_called()
        self.assertFalse(manager.get_state()["proxy_ok"])
        self.monitor.check_once()
        self.switch.assert_called_once()
        self.assertIn("old", manager.load_blacklist())
        self.assertEqual(manager.read_nodes()[0]["probe_status"], "unavailable")

    def test_success_resets_failure_count(self) -> None:
        self.monitor.check_once()
        self.health.return_value = {"ok": True, "ip": "192.0.2.2", "latency_ms": 30}
        self.monitor.check_once()
        self.health.return_value = {"ok": False, "error": "temporary timeout"}
        self.monitor.check_once()
        self.switch.assert_not_called()
        self.assertEqual(self.monitor.failures, 1)

    def test_fixed_ip_reconnects_same_node(self) -> None:
        self.save_config(routing_mode="fixed_ip", fixed_node_id="old")
        connect = self.patch(manager, "connect_node", mock.Mock())
        self.monitor.check_once()
        self.monitor.check_once()
        connect.assert_called_once_with("old")
        self.switch.assert_not_called()
        self.assertNotIn("old", manager.load_blacklist())

    def test_fixed_ip_retries_after_failed_reconnect_clears_active_id(self) -> None:
        self.save_config(routing_mode="fixed_ip", fixed_node_id="old")
        manager.active_openvpn_process = None
        manager.active_openvpn_node_id = ""
        connect = self.patch(manager, "connect_node", mock.Mock())
        self.monitor.check_once()
        connect.assert_called_once_with("old")

    def test_dead_process_recovers_immediately(self) -> None:
        manager.active_openvpn_process.poll.return_value = 1
        self.monitor.check_once()
        self.health.assert_not_called()
        self.switch.assert_called_once()

    def test_no_active_node_still_attempts_recovery(self) -> None:
        manager.active_openvpn_node_id = ""
        manager.active_openvpn_process = None
        self.monitor.check_once()
        self.switch.assert_called_once()

    def test_disabled_connection_does_not_reconnect(self) -> None:
        self.save_config(connection_enabled=False)
        self.monitor.check_once()
        self.health.assert_not_called()
        self.switch.assert_not_called()

    def test_stale_result_does_not_blacklist_reconnected_same_node(self) -> None:
        def reconnect_during_check():
            manager.active_openvpn_process = mock.Mock()
            manager.active_openvpn_process.poll.return_value = None
            return {"ok": False, "error": "old request timed out"}
        self.health.side_effect = reconnect_during_check
        self.monitor.check_once()
        self.switch.assert_not_called()
        self.assertEqual(manager.load_blacklist(), {})
        self.assertEqual(self.monitor.failures, 0)

    def test_maintenance_does_not_suspend_health_checks(self) -> None:
        nodes = manager.read_nodes()
        self.patch(manager, "fetch_candidates", mock.Mock(return_value=nodes))
        self.monitor.failures = 1
        self.monitor.connection = (manager.active_openvpn_node_id, manager.active_openvpn_process)
        def test_nodes(node_ids):
            self.assertTrue(manager.maintenance_lock.locked())
            self.assertFalse(manager.is_connecting)
            self.monitor.check_once()
            return []
        self.patch(manager, "test_multiple_nodes", mock.Mock(side_effect=test_nodes))
        manager.maintain_valid_nodes()
        self.switch.assert_called_once()

    def test_check_does_not_compete_with_connection_in_another_thread(self) -> None:
        acquired = threading.Event()
        release = threading.Event()
        def connect_in_progress():
            with manager.connection_lock:
                acquired.set()
                release.wait(5)
        worker = threading.Thread(target=connect_in_progress)
        worker.start()
        try:
            self.assertTrue(acquired.wait(2))
            self.monitor.check_once()
            self.switch.assert_not_called()
            self.assertEqual(manager.load_blacklist(), {})
        finally:
            release.set()
            worker.join(2)

    def test_delayed_refill_leaves_an_already_restored_connection_alone(self) -> None:
        maintain = self.patch(manager, "maintain_valid_nodes", mock.Mock())
        manager.recover_missing_connection()
        maintain.assert_not_called()
        self.switch.assert_not_called()
        self.assertEqual(manager.active_openvpn_node_id, "old")

    def test_delayed_refill_does_not_switch_connection_restored_during_maintenance(self) -> None:
        manager.active_openvpn_node_id = ""
        manager.active_openvpn_process = None
        def restore_connection(**kwargs):
            manager.active_openvpn_node_id = "good"
            manager.active_openvpn_process = mock.Mock()
            manager.active_openvpn_process.poll.return_value = None
        self.patch(manager, "maintain_valid_nodes", mock.Mock(side_effect=restore_connection))
        manager.recover_missing_connection()
        self.switch.assert_not_called()
        self.assertEqual(manager.active_openvpn_node_id, "good")

    def test_delayed_refill_retries_when_still_disconnected(self) -> None:
        manager.active_openvpn_node_id = ""
        manager.active_openvpn_process = None
        maintain = self.patch(manager, "maintain_valid_nodes", mock.Mock())
        manager.recover_missing_connection()
        maintain.assert_called_once_with(force=False)
        self.switch.assert_called_once()

    def test_delayed_refill_respects_manual_disconnect(self) -> None:
        manager.active_openvpn_node_id = ""
        manager.active_openvpn_process = None
        self.save_config(connection_enabled=False)
        maintain = self.patch(manager, "maintain_valid_nodes", mock.Mock())
        manager.recover_missing_connection()
        maintain.assert_not_called()
        self.switch.assert_not_called()


class ConnectionValidationTests(ManagerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.patch(manager, "setup_policy_routing", mock.Mock())
        self.processes = [mock.Mock(), mock.Mock()]
        for process in self.processes:
            process.poll.return_value = None
        self.patch(manager, "run_openvpn_until_ready", mock.Mock(side_effect=[
            (True, "initialized", process) for process in self.processes
        ]))

    def test_initialized_tunnel_with_failed_https_is_not_connected(self) -> None:
        self.patch(manager, "check_proxy_health", mock.Mock(return_value={"ok": False, "error": "no Internet"}))
        with self.assertRaisesRegex(RuntimeError, "HTTPS 出口检测失败"):
            manager.connect_node("bad")
        self.assertEqual(manager.active_openvpn_node_id, "")
        self.assertIsNone(manager.active_openvpn_process)
        self.assertFalse(manager.is_connecting)
        self.assertFalse(manager.get_state()["proxy_ok"])
        self.assertIn("bad", manager.load_blacklist())
        self.assertFalse(any(n.get("active") for n in manager.read_nodes()))

    def test_fixed_ip_config_survives_failed_https_and_missing_api_entry(self) -> None:
        self.save_config(routing_mode="fixed_ip", fixed_node_id="old")
        manager.run_openvpn_until_ready.side_effect = None
        manager.run_openvpn_until_ready.return_value = (True, "initialized", self.processes[0])
        health = self.patch(manager, "check_proxy_health", mock.Mock(return_value={"ok": False, "error": "no Internet"}))
        with self.assertRaises(RuntimeError):
            manager.connect_node("old")
        self.assertNotIn("old", manager.load_blacklist())

        candidates = [n for n in manager.read_nodes() if n["id"] != "old"]
        self.patch(manager, "fetch_candidates", mock.Mock(return_value=candidates))
        self.patch(manager, "test_multiple_nodes", mock.Mock(return_value=[]))
        manager.maintain_valid_nodes()
        self.assertIn("old", {n["id"] for n in manager.read_nodes()})
        self.assertNotIn("old", manager.load_blacklist())
        self.assertEqual(manager.active_openvpn_node_id, "")

        health.return_value = {"ok": True, "ip": "192.0.2.2", "latency_ms": 10}
        manager.ProxyHealthMonitor().check_once()
        self.assertEqual(manager.active_openvpn_node_id, "old")
        self.assertTrue(manager.get_state()["proxy_ok"])

    def test_fixed_ip_handshake_failure_is_not_blacklisted(self) -> None:
        self.save_config(routing_mode="fixed_ip", fixed_node_id="old")
        manager.run_openvpn_until_ready.side_effect = None
        manager.run_openvpn_until_ready.return_value = (False, "TLS timeout", None)
        with self.assertRaisesRegex(RuntimeError, "TLS timeout"):
            manager.connect_node("old")
        self.assertNotIn("old", manager.load_blacklist())
        self.assertEqual(manager.load_ui_config()["fixed_node_id"], "old")

    def test_failover_skips_initialized_but_unusable_candidate(self) -> None:
        health = self.patch(manager, "check_proxy_health", mock.Mock(side_effect=[
            {"ok": False, "error": "no Internet"},
            {"ok": True, "ip": "192.0.2.2", "latency_ms": 15},
        ]))
        manager.mark_node_unavailable("old", "watchdog detected failed traffic")
        manager.auto_switch_node()
        self.assertEqual(manager.active_openvpn_node_id, "good")
        self.assertTrue(manager.get_state()["proxy_ok"])
        self.assertIn("bad", manager.load_blacklist())
        self.assertEqual(health.call_count, 2)

    def test_blacklist_is_respected_even_if_background_test_marks_available(self) -> None:
        manager.mark_node_unavailable("bad", "failed real traffic")
        nodes = manager.read_nodes()
        next(n for n in nodes if n["id"] == "bad")["probe_status"] = "available"
        manager.write_json(manager.NODES_FILE, nodes)
        connect = self.patch(manager, "connect_node", mock.Mock())
        manager.auto_switch_node()
        connect.assert_called_once_with("good")

    def test_only_one_node_refill_worker_is_scheduled(self) -> None:
        manager.write_json(manager.NODES_FILE, [])
        thread = self.patch(manager.threading, "Thread", mock.Mock())
        try:
            manager.auto_switch_node()
            manager.auto_switch_node()
            thread.assert_called_once()
            thread.return_value.start.assert_called_once()
        finally:
            if manager.recovery_lock.locked():
                manager.recovery_lock.release()


if __name__ == "__main__":
    unittest.main()

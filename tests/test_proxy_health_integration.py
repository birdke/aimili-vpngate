from __future__ import annotations

import os
import shutil
import socket
import socketserver
import ssl
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from test_proxy_health import ManagerTestCase, manager


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("openssl") and shutil.which("curl"),
                     "Requires Linux, curl and openssl")
class HTTPSRecoveryIntegrationTests(ManagerTestCase):
    def setUp(self) -> None:
        super().setUp()
        certificate = self.data_dir / "certificate.pem"
        key = self.data_dir / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout", str(key), "-out", str(certificate),
        ], check=True, capture_output=True, timeout=15)

        class HTTPSHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = b"192.0.2.25" if self.path == "/ip" else b""
                self.send_response(503 if self.path == "/unavailable" else 200 if body else 204)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                pass

        self.https_server = ThreadingHTTPServer(("127.0.0.1", 0), HTTPSHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(certificate), str(key))
        self.https_server.socket = context.wrap_socket(self.https_server.socket, server_side=True)
        self.start_server(self.https_server)
        self.https_url = f"https://localhost:{self.https_server.server_port}"

        class ProxyHandler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                manager.proxy_server.proxy_client(self.request, self.client_address)

        class ProxyServer(socketserver.ThreadingTCPServer):
            daemon_threads = True

        self.proxy = ProxyServer(("127.0.0.1", 0), ProxyHandler)
        self.start_server(self.proxy)
        self.traffic_blocked = False
        self.real_create_connection = socket.create_connection

        def tunnel_connection(address, timeout=20):
            if self.traffic_blocked:
                raise OSError("Simulated tunnel with no outbound traffic")
            return self.real_create_connection(address, timeout=2)

        self.patch(manager.proxy_server, "create_connection", mock.Mock(side_effect=tunnel_connection))
        self.patch(manager.proxy_server, "get_proxy_credentials", mock.Mock(return_value=(None, None)))
        self.patch(manager, "LOCAL_PROXY_HOST", "127.0.0.1")
        self.patch(manager, "LOCAL_PROXY_PORT", self.proxy.server_address[1])
        self.patch(manager, "get_vpn_interface", mock.Mock(return_value="lo"))
        self.patch(manager, "PROXY_CHECK_TIMEOUT_SECONDS", 2)
        self.patch(manager, "PROXY_HEALTH_URLS", (self.https_url + "/primary", self.https_url + "/secondary"))
        self.patch(manager, "PROXY_IP_URLS", (self.https_url + "/ip",))
        env = mock.patch.dict(os.environ, {"CURL_CA_BUNDLE": str(certificate), "NO_PROXY": "*", "no_proxy": "*"})
        env.start()
        self.addCleanup(env.stop)

    def start_server(self, server) -> None:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def stop_server():
            server.shutdown()
            server.server_close()
            worker.join(2)
        self.addCleanup(stop_server)

    def test_live_process_dead_traffic_recovers_through_real_socks_and_tls(self) -> None:
        monitor = manager.ProxyHealthMonitor()
        monitor.check_once()
        self.assertTrue(manager.get_state()["proxy_ok"])
        self.assertEqual(manager.get_state()["proxy_ip"], "192.0.2.25")

        self.traffic_blocked = True
        self.patch(manager, "setup_policy_routing", mock.Mock())
        def initialize_tunnel(config_file, **kwargs):
            self.traffic_blocked = Path(config_file).stem != "good"
            process = mock.Mock()
            process.poll.return_value = None
            return True, "Initialization Sequence Completed", process
        startup = self.patch(manager, "run_openvpn_until_ready", mock.Mock(side_effect=initialize_tunnel))

        monitor.check_once()
        self.assertIsNone(manager.active_openvpn_process.poll())
        self.assertEqual(manager.active_openvpn_node_id, "old")
        self.assertFalse(manager.get_state()["proxy_ok"])
        startup.assert_not_called()

        monitor.check_once()
        self.assertEqual(manager.active_openvpn_node_id, "good")
        self.assertTrue(manager.get_state()["proxy_ok"])
        self.assertEqual(manager.get_state()["proxy_ip"], "192.0.2.25")
        self.assertEqual([Path(c.args[0]).stem for c in startup.call_args_list], ["bad", "good"])
        self.assertEqual(set(manager.load_blacklist()), {"old", "bad"})

    def test_no_proxy_environment_cannot_hide_broken_proxy(self) -> None:
        self.traffic_blocked = True
        self.assertFalse(manager.check_proxy_health()["ok"])

    def test_ip_lookup_outage_does_not_reject_working_https(self) -> None:
        self.patch(manager, "PROXY_IP_URLS", (self.https_url + "/unavailable",))
        result = manager.check_proxy_health()
        self.assertTrue(result["ok"])
        self.assertEqual(result["ip"], "-")


if __name__ == "__main__":
    unittest.main()

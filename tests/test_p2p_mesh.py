"""
Standard library unit tests for Kora AI Peer-to-Peer Local Team Mesh.
"""

import time
import unittest
from core.orchestration.p2p_mesh import LocalTeamMesh, MeshPeer


class TestLocalTeamMesh(unittest.TestCase):
    def test_local_advertisement(self):
        mesh = LocalTeamMesh(node_name="macbook-pro", port=7420, vram_mb=16384)
        ad = mesh.get_local_advertisement()

        self.assertTrue(ad["node_id"].startswith("kora_"))
        self.assertEqual(ad["hostname"], "macbook-pro")
        self.assertEqual(ad["port"], 7420)
        self.assertEqual(ad["vram_mb"], 16384)
        self.assertEqual(ad["service_type"], "_kora-agent._tcp.local.")

    def test_peer_registration_and_heartbeat(self):
        mesh = LocalTeamMesh()
        peer = mesh.register_peer(
            node_id="peer_mac_studio",
            hostname="studio.local",
            lan_ip="192.168.1.150",
            port=7420,
            available_vram_mb=32768,
            active_tasks=1,
            tailscale_ip="100.64.0.5",
        )

        self.assertEqual(peer.hostname, "studio.local")
        self.assertEqual(peer.tailscale_ip, "100.64.0.5")
        self.assertTrue(peer.is_alive())

        # Test heartbeat expiration
        peer.last_heartbeat = time.time() - 30.0
        self.assertFalse(peer.is_alive(timeout_sec=10.0))

    def test_task_routing_to_highest_capacity_peer(self):
        mesh = LocalTeamMesh()

        # Register two peers: one with 8GB VRAM, one with 24GB VRAM
        mesh.register_peer(
            node_id="laptop_small",
            hostname="thinkpad.local",
            lan_ip="192.168.1.101",
            port=7420,
            available_vram_mb=8192,
            active_tasks=0,
        )
        mesh.register_peer(
            node_id="desktop_heavy",
            hostname="mac-studio.local",
            lan_ip="192.168.1.102",
            port=7420,
            available_vram_mb=24576,
            active_tasks=1,
        )

        # A task requiring 14GB VRAM should route to desktop_heavy
        best_worker = mesh.route_task(min_vram_mb=14000)
        self.assertIsNotNone(best_worker)
        self.assertEqual(best_worker.node_id, "desktop_heavy")
        self.assertEqual(best_worker.hostname, "mac-studio.local")


if __name__ == "__main__":
    unittest.main()

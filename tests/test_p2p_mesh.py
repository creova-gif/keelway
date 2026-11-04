"""
Standard library unit tests for Keelway Peer-to-Peer Local Team Mesh.
"""

import time
import unittest
from core.orchestration.p2p_mesh import LocalTeamMesh, MeshPeer


"""
Standard library unit tests for Keelway Peer-to-Peer Local Team Mesh.
"""

import tempfile
import time
import unittest
from pathlib import Path
from core.orchestration.p2p_mesh import LocalTeamMesh, MeshPeer, get_shared_mesh


class TestLocalTeamMesh(unittest.TestCase):
    def test_local_advertisement(self):
        mesh = LocalTeamMesh(node_name="macbook-pro", port=7420, vram_mb=16384)
        ad = mesh.get_local_advertisement()

        self.assertTrue(ad["node_id"].startswith("keelway_"))
        self.assertEqual(ad["hostname"], "macbook-pro")
        self.assertEqual(ad["port"], 7420)
        self.assertEqual(ad["vram_mb"], 16384)
        self.assertEqual(ad["service_type"], "_keelway-agent._tcp.local.")

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

    def test_total_pooled_vram_and_active_peers(self):
        mesh = LocalTeamMesh(vram_mb=8192)
        mesh.register_peer("peer_a", "peer-a.local", "192.168.1.2", 7420, 16384)
        mesh.register_peer("peer_b", "peer-b.local", "192.168.1.3", 7420, 32768)

        self.assertEqual(len(mesh.active_peers()), 2)
        self.assertEqual(mesh.total_pooled_vram_mb(), 8192 + 16384 + 32768)

    def test_prune_expired_peers(self):
        mesh = LocalTeamMesh()
        p1 = mesh.register_peer("peer_alive", "alive.local", "192.168.1.2", 7420, 8192)
        p2 = mesh.register_peer("peer_dead", "dead.local", "192.168.1.3", 7420, 8192)
        p2.last_heartbeat = time.time() - 60.0

        pruned = mesh.prune_expired_peers(timeout_sec=30.0)
        self.assertEqual(pruned, 1)
        self.assertIn("peer_alive", mesh.peers)
        self.assertNotIn("peer_dead", mesh.peers)

    def test_task_delegation_and_execution(self):
        mesh = LocalTeamMesh(node_name="local-worker", vram_mb=8192)
        mesh.register_peer("gpu_server", "gpu.local", "192.168.1.50", 7420, 49152)

        # Delegation routes to high-capacity peer
        receipt = mesh.delegate_task("Train AST Embedding", min_vram_mb=32000)
        self.assertEqual(receipt.status, "delegated")
        self.assertEqual(receipt.target_node_id, "gpu_server")
        self.assertTrue(len(receipt.signature) > 20)

        # Fallback to local node when no peer satisfies heavy requirement but allow_local_fallback=True
        local_receipt = mesh.delegate_task("Local Linting", min_vram_mb=60000, allow_local_fallback=True)
        self.assertEqual(local_receipt.status, "local_fallback")
        self.assertEqual(local_receipt.target_node_id, mesh.node_id)

        # Execution of local task
        executed = mesh.execute_task(local_receipt)
        self.assertEqual(executed.status, "completed")
        self.assertIsNotNone(executed.completed_at)
        self.assertGreaterEqual(executed.duration_ms, 0.0)

    def test_save_and_load_peers(self):
        with tempfile.TemporaryDirectory() as td:
            store_file = Path(td) / "peers.json"
            mesh1 = LocalTeamMesh()
            mesh1.register_peer("p1", "h1.local", "192.168.1.10", 7420, 16384)
            mesh1.register_peer("p2", "h2.local", "192.168.1.11", 7420, 32768, tailscale_ip="100.64.0.1")
            mesh1.save_peers(store_file)

            mesh2 = LocalTeamMesh()
            loaded = mesh2.load_peers(store_file)
            self.assertEqual(loaded, 2)
            self.assertIn("p1", mesh2.peers)
            self.assertEqual(mesh2.peers["p2"].tailscale_ip, "100.64.0.1")

    def test_shared_mesh_singleton(self):
        m1 = get_shared_mesh()
        m2 = get_shared_mesh()
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main()

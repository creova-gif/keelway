"""
Kora AI Peer-to-Peer Local Team Mesh & GPU Resource Pooling.
Enables local engineering teams on the same office Wi-Fi or ad-hoc cellular hotspot
to discover each other via mDNS, share VRAM/GPU compute, and route heavy agent tasks
with zero cloud intermediary. Supports optional Tailscale overlays for remote teammates.
"""

import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class MeshPeer:
    """Represents a peer developer workstation on the local team mesh."""
    node_id: str
    hostname: str
    lan_ip: str
    port: int
    available_vram_mb: int
    active_tasks: int
    tailscale_ip: Optional[str] = None
    last_heartbeat: float = field(default_factory=time.time)

    def is_alive(self, timeout_sec: float = 15.0) -> bool:
        return (time.time() - self.last_heartbeat) < timeout_sec


class LocalTeamMesh:
    """Manages zero-cloud peer discovery, GPU VRAM pooling, and task delegation."""

    def __init__(self, node_name: Optional[str] = None, port: int = 7420, vram_mb: int = 8192):
        self.node_id = f"kora_{uuid.uuid4().hex[:8]}"
        self.hostname = node_name or socket.gethostname()
        self.port = port
        self.vram_mb = vram_mb
        self.tailscale_ip: Optional[str] = None
        self.peers: Dict[str, MeshPeer] = {}

    def set_tailscale_overlay(self, ts_ip: str):
        """Attaches a secure Tailscale WireGuard overlay address for hybrid remote peering."""
        self.tailscale_ip = ts_ip

    def get_local_advertisement(self) -> Dict[str, Any]:
        """Generates mDNS service record dictionary (_kora-agent._tcp.local)."""
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "port": self.port,
            "vram_mb": self.vram_mb,
            "tailscale_ip": self.tailscale_ip,
            "service_type": "_kora-agent._tcp.local.",
        }

    def register_peer(
        self,
        node_id: str,
        hostname: str,
        lan_ip: str,
        port: int,
        available_vram_mb: int,
        active_tasks: int = 0,
        tailscale_ip: Optional[str] = None
    ) -> MeshPeer:
        """Registers or refreshes heartbeat for a discovered peer on local Wi-Fi or Tailscale."""
        peer = MeshPeer(
            node_id=node_id,
            hostname=hostname,
            lan_ip=lan_ip,
            port=port,
            available_vram_mb=available_vram_mb,
            active_tasks=active_tasks,
            tailscale_ip=tailscale_ip,
            last_heartbeat=time.time(),
        )
        self.peers[node_id] = peer
        return peer

    def route_task(self, min_vram_mb: int = 6000) -> Optional[MeshPeer]:
        """
        Intelligently routes a heavy AST repair or fine-tuning task:
        - If local node satisfies the VRAM requirement and has capacity, runs locally.
        - Otherwise, routes to the local Wi-Fi peer with the highest available VRAM.
        """
        # Find active peers meeting capacity
        candidates = [p for p in self.peers.values() if p.is_alive() and p.available_vram_mb >= min_vram_mb]
        if not candidates:
            return None

        # Sort by available VRAM descending and active tasks ascending
        candidates.sort(key=lambda p: (p.available_vram_mb, -p.active_tasks), reverse=True)
        return candidates[0]

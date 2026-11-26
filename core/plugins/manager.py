"""
Keelway Plugin Lifecycle Manager.
Discovers, installs, activates, and verifies plugins and their underlying MCP server processes.
"""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.plugins.manifest import PluginManifest
from core.orchestration.mcp_client import MCPClient, MCPClientManager


@dataclass
class PluginRecord:
    manifest: PluginManifest
    install_dir: str
    status: str = "INSTALLED"  # "INSTALLED" | "ACTIVE" | "DISABLED" | "ERROR"
    loaded_at: Optional[float] = None
    active_tools: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.manifest.name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "author": self.manifest.author,
            "status": self.status,
            "install_dir": self.install_dir,
            "loaded_at": self.loaded_at,
            "active_tools": self.active_tools,
            "error": self.error,
            "digest_sha256": self.manifest.digest_sha256,
        }


class PluginManager:
    """Manages the full lifecycle of Keelway plugins and external MCP tool bindings."""

    def __init__(self, plugins_dir: Optional[Path] = None, mcp_manager: Optional[MCPClientManager] = None):
        self.plugins_dir = Path(plugins_dir or ".keelway/plugins").resolve()
        self.mcp_manager = mcp_manager or MCPClientManager()
        self.installed_plugins: Dict[str, PluginRecord] = {}

    def discover_plugins(self) -> List[PluginRecord]:
        """Scan plugins directory for valid plugin manifests."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        discovered: List[PluginRecord] = []

        for item in self.plugins_dir.iterdir():
            manifest_file = item / "plugin.json" if item.is_dir() else (item if item.suffix == ".json" else None)
            if manifest_file and manifest_file.exists():
                try:
                    manifest = PluginManifest.load_file(manifest_file)
                    record = PluginRecord(
                        manifest=manifest,
                        install_dir=str(manifest_file.parent),
                        status="INSTALLED",
                    )
                    self.installed_plugins[manifest.name] = record
                    discovered.append(record)
                except Exception:
                    pass
        return discovered

    async def install_plugin(
        self,
        source: Union[PluginManifest, Path, Dict[str, Any]],
        activate: bool = True,
    ) -> PluginRecord:
        """Install a plugin from manifest, directory, or JSON file."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(source, PluginManifest):
            manifest = source
        elif isinstance(source, dict):
            manifest = PluginManifest.from_dict(source)
        else:
            path = Path(source).resolve()
            if path.is_file():
                manifest = PluginManifest.load_file(path)
            elif path.is_dir() and (path / "plugin.json").exists():
                manifest = PluginManifest.load_file(path / "plugin.json")
            else:
                raise ValueError(f"Invalid plugin source: '{source}'")

        target_dir = self.plugins_dir / manifest.name
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / "plugin.json"
        manifest_path.write_text(manifest.to_json(indent=2), encoding="utf-8")

        record = PluginRecord(
            manifest=manifest,
            install_dir=str(target_dir),
            status="INSTALLED",
        )
        self.installed_plugins[manifest.name] = record

        if activate:
            await self.activate_plugin(manifest.name)

        return self.installed_plugins[manifest.name]

    async def activate_plugin(self, plugin_name: str) -> PluginRecord:
        """Start declared MCP servers for the plugin and register its tools."""
        if plugin_name not in self.installed_plugins:
            self.discover_plugins()

        if plugin_name not in self.installed_plugins:
            raise KeyError(f"Plugin '{plugin_name}' is not installed.")

        record = self.installed_plugins[plugin_name]
        tools_discovered: List[str] = []

        try:
            for srv_name, srv_conf in record.manifest.mcp_servers.items():
                client_id = f"{plugin_name}__{srv_name}"
                cmd = srv_conf.get("command")
                args = srv_conf.get("args", [])
                env = srv_conf.get("env", {})
                cwd = srv_conf.get("cwd") or record.install_dir

                client = MCPClient(
                    server_id=client_id,
                    command=cmd,
                    args=args,
                    env=env,
                    cwd=cwd,
                )
                tools = await self.mcp_manager.connect_client(client)
                tools_discovered.extend([t.name for t in tools])

            record.status = "ACTIVE"
            record.active_tools = tools_discovered
            record.loaded_at = time.time()
            record.error = None
        except Exception as exc:
            record.status = "ERROR"
            record.error = str(exc)

        return record

    async def deactivate_plugin(self, plugin_name: str) -> PluginRecord:
        """Stop declared MCP server processes for the plugin."""
        if plugin_name not in self.installed_plugins:
            raise KeyError(f"Plugin '{plugin_name}' is not installed.")

        record = self.installed_plugins[plugin_name]
        for srv_name in record.manifest.mcp_servers.keys():
            client_id = f"{plugin_name}__{srv_name}"
            client = await self.mcp_manager.get_client(client_id)
            if client:
                await client.disconnect()

        record.status = "DISABLED"
        record.active_tools.clear()
        return record

    async def uninstall_plugin(self, plugin_name: str) -> bool:
        """Deactivate and delete plugin from disk."""
        if plugin_name in self.installed_plugins:
            await self.deactivate_plugin(plugin_name)
            record = self.installed_plugins.pop(plugin_name)
            target = Path(record.install_dir)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            return True
        return False

    def list_plugins(self) -> List[Dict[str, Any]]:
        self.discover_plugins()
        return [p.to_dict() for p in self.installed_plugins.values()]

    def mount_all_active_plugins(self, agent_loop: Any) -> int:
        """Mount all active plugin tools into an agent loop instance."""
        return self.mcp_manager.mount_tools_into_agent_loop(agent_loop, prefix_server=True)

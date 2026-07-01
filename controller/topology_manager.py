"""
Topology Manager for LLM-NetAuto-SDN.

Uses NetworkX to maintain an in-memory graph representation
of the SDN network topology for path computation and visualization.
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

import networkx as nx
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class NetworkDevice:
    """Represents a network device (switch)."""
    id: str
    name: str
    type: str = "switch"
    available: bool = True
    protocol: str = "OF_13"
    manufacturer: str = "Open vSwitch"
    hw_version: str = "2.17.0"
    sw_version: str = "2.17.0"
    serial_number: str = ""
    chassis_id: str = ""
    ports: List[Dict[str, Any]] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)

    def to_onos_format(self) -> Dict[str, Any]:
        """Convert to ONOS REST API format."""
        return {
            "id": self.id,
            "type": self.type.upper(),
            "available": self.available,
            "role": "MASTER",
            "mfr": self.manufacturer,
            "hw": self.hw_version,
            "sw": self.sw_version,
            "serial": self.serial_number,
            "chassisId": self.chassis_id or self.id.replace("of:", ""),
            "annotations": self.annotations
        }


@dataclass
class NetworkHost:
    """Represents a network host."""
    id: str
    mac: str
    ip_addresses: List[str] = field(default_factory=list)
    vlan: str = "-1"
    inner_vlan: str = "-1"
    outer_tpid: str = "unknown"
    configured: bool = False
    suspended: bool = False
    location_device: str = ""
    location_port: int = 0
    name: str = ""

    def to_onos_format(self) -> Dict[str, Any]:
        """Convert to ONOS REST API format."""
        return {
            "id": f"{self.mac}/{self.vlan}",
            "mac": self.mac,
            "vlan": self.vlan,
            "innerVlan": self.inner_vlan,
            "outerTpid": self.outer_tpid,
            "configured": self.configured,
            "suspended": self.suspended,
            "ipAddresses": self.ip_addresses,
            "locations": [{
                "elementId": self.location_device,
                "port": str(self.location_port)
            }]
        }


@dataclass
class NetworkLink:
    """Represents a network link."""
    src_device: str
    src_port: int
    dst_device: str
    dst_port: int
    type: str = "DIRECT"
    state: str = "ACTIVE"
    bandwidth: int = 10  # Mbps
    delay: int = 5  # ms

    def to_onos_format(self) -> Dict[str, Any]:
        """Convert to ONOS REST API format."""
        return {
            "src": {
                "device": self.src_device,
                "port": str(self.src_port)
            },
            "dst": {
                "device": self.dst_device,
                "port": str(self.dst_port)
            },
            "type": self.type,
            "state": self.state,
            "annotations": {
                "bandwidth": str(self.bandwidth),
                "delay": str(self.delay)
            }
        }


class TopologyManager:
    """
    Manages network topology using NetworkX.

    Provides graph operations for path computation,
    topology analysis, and visualization preparation.
    """

    def __init__(self):
        """Initialize topology manager with empty graph."""
        self._graph = nx.Graph()
        self._devices: Dict[str, NetworkDevice] = {}
        self._hosts: Dict[str, NetworkHost] = {}
        self._links: Dict[Tuple[str, str], NetworkLink] = {}
        self._last_update: Optional[datetime] = None
        logger.info("TopologyManager initialized")

    # ==========================================
    # Device Management
    # ==========================================

    def add_device(self, device: NetworkDevice) -> None:
        """Add a device to the topology."""
        self._devices[device.id] = device
        self._graph.add_node(
            device.id,
            type="switch",
            name=device.name,
            available=device.available,
            data=device
        )
        self._last_update = datetime.now()
        logger.debug(f"Added device: {device.id}")

    def remove_device(self, device_id: str) -> bool:
        """Remove a device from the topology."""
        if device_id in self._devices:
            del self._devices[device_id]
            self._graph.remove_node(device_id)
            self._last_update = datetime.now()
            logger.debug(f"Removed device: {device_id}")
            return True
        return False

    def get_device(self, device_id: str) -> Optional[NetworkDevice]:
        """Get a device by ID."""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[NetworkDevice]:
        """Get all devices."""
        return list(self._devices.values())

    def get_device_by_name(self, name: str) -> Optional[NetworkDevice]:
        """Get device by human-readable name (e.g., s1)."""
        for device in self._devices.values():
            if device.name == name:
                return device
        return None

    # ==========================================
    # Host Management
    # ==========================================

    def add_host(self, host: NetworkHost) -> None:
        """Add a host to the topology."""
        self._hosts[host.id] = host
        self._graph.add_node(
            host.id,
            type="host",
            name=host.name,
            mac=host.mac,
            ips=host.ip_addresses,
            data=host
        )
        # Connect host to its switch
        if host.location_device:
            self._graph.add_edge(
                host.id,
                host.location_device,
                type="host_link",
                port=host.location_port
            )
        self._last_update = datetime.now()
        logger.debug(f"Added host: {host.id}")

    def remove_host(self, host_id: str) -> bool:
        """Remove a host from the topology."""
        if host_id in self._hosts:
            del self._hosts[host_id]
            self._graph.remove_node(host_id)
            self._last_update = datetime.now()
            logger.debug(f"Removed host: {host_id}")
            return True
        return False

    def get_host(self, host_id: str) -> Optional[NetworkHost]:
        """Get a host by ID."""
        return self._hosts.get(host_id)

    def get_host_by_ip(self, ip: str) -> Optional[NetworkHost]:
        """Get host by IP address."""
        for host in self._hosts.values():
            if ip in host.ip_addresses:
                return host
        return None

    def get_host_by_mac(self, mac: str) -> Optional[NetworkHost]:
        """Get host by MAC address."""
        for host in self._hosts.values():
            if host.mac.lower() == mac.lower():
                return host
        return None

    def get_host_by_name(self, name: str) -> Optional[NetworkHost]:
        """Get host by human-readable name (e.g., h1)."""
        for host in self._hosts.values():
            if host.name == name:
                return host
        return None

    def get_all_hosts(self) -> List[NetworkHost]:
        """Get all hosts."""
        return list(self._hosts.values())

    # ==========================================
    # Link Management
    # ==========================================

    def add_link(self, link: NetworkLink) -> None:
        """Add a link to the topology."""
        key = (min(link.src_device, link.dst_device),
               max(link.src_device, link.dst_device))
        self._links[key] = link
        self._graph.add_edge(
            link.src_device,
            link.dst_device,
            type="switch_link",
            src_port=link.src_port,
            dst_port=link.dst_port,
            bandwidth=link.bandwidth,
            delay=link.delay,
            state=link.state,
            data=link
        )
        self._last_update = datetime.now()
        logger.debug(f"Added link: {link.src_device} <-> {link.dst_device}")

    def remove_link(self, src_device: str, dst_device: str) -> bool:
        """Remove a link from the topology."""
        key = (min(src_device, dst_device), max(src_device, dst_device))
        if key in self._links:
            del self._links[key]
            self._graph.remove_edge(src_device, dst_device)
            self._last_update = datetime.now()
            logger.debug(f"Removed link: {src_device} <-> {dst_device}")
            return True
        return False

    def set_link_state(
        self,
        src_device: str,
        dst_device: str,
        state: str
    ) -> bool:
        """Set link state (ACTIVE/INACTIVE)."""
        key = (min(src_device, dst_device), max(src_device, dst_device))
        if key in self._links:
            self._links[key].state = state
            if self._graph.has_edge(src_device, dst_device):
                self._graph[src_device][dst_device]["state"] = state
            self._last_update = datetime.now()
            logger.info(f"Link {src_device} <-> {dst_device}: {state}")
            return True
        return False

    def get_link(
        self,
        src_device: str,
        dst_device: str
    ) -> Optional[NetworkLink]:
        """Get a link by endpoints."""
        key = (min(src_device, dst_device), max(src_device, dst_device))
        return self._links.get(key)

    def get_all_links(self) -> List[NetworkLink]:
        """Get all links."""
        return list(self._links.values())

    def get_active_links(self) -> List[NetworkLink]:
        """Get only active links."""
        return [l for l in self._links.values() if l.state == "ACTIVE"]

    # ==========================================
    # Path Computation
    # ==========================================

    def get_shortest_path(
        self,
        src: str,
        dst: str
    ) -> List[str]:
        """
        Get shortest path between two nodes.

        Args:
            src: Source node ID (device or host)
            dst: Destination node ID (device or host)

        Returns:
            List of node IDs in the path
        """
        try:
            # Only consider active links
            active_graph = nx.Graph()
            for u, v, data in self._graph.edges(data=True):
                if data.get("type") == "host_link":
                    active_graph.add_edge(u, v, **data)
                elif data.get("state", "ACTIVE") == "ACTIVE":
                    active_graph.add_edge(u, v, **data)

            for node, data in self._graph.nodes(data=True):
                if node not in active_graph:
                    active_graph.add_node(node, **data)

            return nx.shortest_path(active_graph, src, dst)
        except nx.NetworkXNoPath:
            logger.warning(f"No path found: {src} -> {dst}")
            return []
        except nx.NodeNotFound as e:
            logger.warning(f"Node not found in path search: {e}")
            return []

    def get_all_paths(
        self,
        src: str,
        dst: str,
        max_paths: int = 5
    ) -> List[List[str]]:
        """
        Get all simple paths between two nodes.

        Args:
            src: Source node ID
            dst: Destination node ID
            max_paths: Maximum number of paths to return

        Returns:
            List of paths (each path is a list of node IDs)
        """
        try:
            paths = list(nx.all_simple_paths(
                self._graph, src, dst, cutoff=10
            ))
            return paths[:max_paths]
        except nx.NodeNotFound:
            return []

    def get_switches_on_path(
        self,
        src_host: str,
        dst_host: str
    ) -> List[str]:
        """
        Get switches on the path between two hosts.

        Args:
            src_host: Source host ID or name
            dst_host: Destination host ID or name

        Returns:
            List of switch device IDs
        """
        # Resolve host names to IDs
        src = self._resolve_host(src_host)
        dst = self._resolve_host(dst_host)

        if not src or not dst:
            return []

        path = self.get_shortest_path(src, dst)
        return [
            node for node in path
            if node in self._devices
        ]

    def _resolve_host(self, identifier: str) -> Optional[str]:
        """Resolve host identifier to host ID."""
        # Direct ID
        if identifier in self._hosts:
            return identifier

        # By name
        host = self.get_host_by_name(identifier)
        if host:
            return host.id

        # By IP
        host = self.get_host_by_ip(identifier)
        if host:
            return host.id

        # By MAC
        host = self.get_host_by_mac(identifier)
        if host:
            return host.id

        return None

    # ==========================================
    # Topology Analysis
    # ==========================================

    def get_neighbors(self, node_id: str) -> List[str]:
        """Get neighbors of a node."""
        if node_id in self._graph:
            return list(self._graph.neighbors(node_id))
        return []

    def get_connected_hosts(self, device_id: str) -> List[NetworkHost]:
        """Get hosts connected to a device."""
        hosts = []
        for host in self._hosts.values():
            if host.location_device == device_id:
                hosts.append(host)
        return hosts

    def is_connected(self) -> bool:
        """Check if the network is fully connected."""
        if not self._graph.nodes():
            return False
        # Only check switch connectivity
        switch_graph = self._graph.subgraph(self._devices.keys())
        return nx.is_connected(switch_graph)

    def get_network_diameter(self) -> int:
        """Get the network diameter (longest shortest path)."""
        try:
            switch_graph = self._graph.subgraph(self._devices.keys())
            if switch_graph.nodes():
                return nx.diameter(switch_graph)
        except nx.NetworkXError:
            pass
        return 0

    def get_node_centrality(self) -> Dict[str, float]:
        """Get betweenness centrality for switches."""
        switch_graph = self._graph.subgraph(self._devices.keys())
        if switch_graph.nodes():
            return nx.betweenness_centrality(switch_graph)
        return {}

    # ==========================================
    # Topology Export
    # ==========================================

    def to_onos_format(self) -> Dict[str, Any]:
        """Export topology in ONOS REST API format."""
        return {
            "devices": [d.to_onos_format() for d in self._devices.values()],
            "hosts": [h.to_onos_format() for h in self._hosts.values()],
            "links": [l.to_onos_format() for l in self._links.values()]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export topology as dictionary."""
        return {
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "type": d.type,
                    "available": d.available
                }
                for d in self._devices.values()
            ],
            "hosts": [
                {
                    "id": h.id,
                    "name": h.name,
                    "mac": h.mac,
                    "ips": h.ip_addresses,
                    "device": h.location_device,
                    "port": h.location_port
                }
                for h in self._hosts.values()
            ],
            "links": [
                {
                    "src": l.src_device,
                    "dst": l.dst_device,
                    "state": l.state,
                    "bandwidth": l.bandwidth,
                    "delay": l.delay
                }
                for l in self._links.values()
            ],
            "stats": {
                "device_count": len(self._devices),
                "host_count": len(self._hosts),
                "link_count": len(self._links),
                "connected": self.is_connected(),
                "diameter": self.get_network_diameter()
            }
        }

    def to_pyvis_data(self) -> Dict[str, Any]:
        """
        Export topology data for pyvis visualization.

        Returns:
            Dictionary with nodes and edges for pyvis
        """
        nodes = []
        edges = []

        # Add switch nodes
        for device in self._devices.values():
            nodes.append({
                "id": device.id,
                "label": device.name,
                "title": (
                    f"Device: {device.id}\n"
                    f"Type: {device.type}\n"
                    f"Status: {'Available' if device.available else 'Down'}"
                ),
                "group": "switch",
                "size": 30,
                "color": "#2196F3" if device.available else "#F44336"
            })

        # Add host nodes
        for host in self._hosts.values():
            nodes.append({
                "id": host.id,
                "label": host.name or host.mac[:8],
                "title": (
                    f"Host: {host.name}\n"
                    f"MAC: {host.mac}\n"
                    f"IPs: {', '.join(host.ip_addresses)}\n"
                    f"Connected to: {host.location_device}:{host.location_port}"
                ),
                "group": "host",
                "size": 20,
                "color": "#4CAF50"
            })

        # Add switch-to-switch links
        for link in self._links.values():
            edges.append({
                "from": link.src_device,
                "to": link.dst_device,
                "title": (
                    f"Bandwidth: {link.bandwidth} Mbps\n"
                    f"Delay: {link.delay} ms\n"
                    f"State: {link.state}"
                ),
                "width": 3,
                "color": "#666" if link.state == "ACTIVE" else "#F44336",
                "dashes": link.state != "ACTIVE"
            })

        # Add host-to-switch links
        for host in self._hosts.values():
            if host.location_device:
                edges.append({
                    "from": host.id,
                    "to": host.location_device,
                    "title": f"Port: {host.location_port}",
                    "width": 1,
                    "color": "#90CAF9"
                })

        return {"nodes": nodes, "edges": edges}

    # ==========================================
    # Topology Management
    # ==========================================

    def clear(self) -> None:
        """Clear the entire topology."""
        self._graph.clear()
        self._devices.clear()
        self._hosts.clear()
        self._links.clear()
        self._last_update = datetime.now()
        logger.info("Topology cleared")

    def update_from_onos(self, onos_data: Dict[str, Any]) -> None:
        """
        Update topology from ONOS REST API response.

        Args:
            onos_data: Dictionary with devices, hosts, links from ONOS
        """
        # Clear existing data
        self.clear()

        # Add devices
        for device_data in onos_data.get("devices", []):
            device = NetworkDevice(
                id=device_data.get("id", ""),
                name=device_data.get("id", "").replace("of:", "s"),
                type=device_data.get("type", "SWITCH").lower(),
                available=device_data.get("available", True),
                manufacturer=device_data.get("mfr", "Unknown"),
                hw_version=device_data.get("hw", ""),
                sw_version=device_data.get("sw", ""),
                chassis_id=device_data.get("chassisId", "")
            )
            self.add_device(device)

        # Add hosts
        for host_data in onos_data.get("hosts", []):
            locations = host_data.get("locations", [])
            location = locations[0] if locations else {}
            host = NetworkHost(
                id=host_data.get("id", ""),
                mac=host_data.get("mac", ""),
                ip_addresses=host_data.get("ipAddresses", []),
                vlan=host_data.get("vlan", "-1"),
                location_device=location.get("elementId", ""),
                location_port=int(location.get("port", 0))
            )
            self.add_host(host)

        # Add links
        for link_data in onos_data.get("links", []):
            src = link_data.get("src", {})
            dst = link_data.get("dst", {})
            link = NetworkLink(
                src_device=src.get("device", ""),
                src_port=int(src.get("port", 0)),
                dst_device=dst.get("device", ""),
                dst_port=int(dst.get("port", 0)),
                type=link_data.get("type", "DIRECT"),
                state=link_data.get("state", "ACTIVE")
            )
            self.add_link(link)

        logger.info(
            f"Topology updated: {len(self._devices)} devices, "
            f"{len(self._hosts)} hosts, {len(self._links)} links"
        )

    @property
    def last_update(self) -> Optional[datetime]:
        """Get last topology update timestamp."""
        return self._last_update


# Singleton instance
_topology_instance: Optional[TopologyManager] = None


def get_topology_manager() -> TopologyManager:
    """Get or create the global topology manager instance."""
    global _topology_instance
    if _topology_instance is None:
        _topology_instance = TopologyManager()
    return _topology_instance


if __name__ == "__main__":
    # Test topology manager
    manager = TopologyManager()

    # Create test topology
    print("\n=== TopologyManager Test ===\n")

    # Add switches
    for i in range(1, 4):
        device = NetworkDevice(
            id=f"of:000000000000000{i}",
            name=f"s{i}",
            type="switch"
        )
        manager.add_device(device)
        print(f"Added switch: {device.name}")

    # Add hosts
    for i in range(1, 7):
        switch_num = (i - 1) // 2 + 1
        port = (i - 1) % 2 + 1
        host = NetworkHost(
            id=f"00:00:00:00:00:0{i}/-1",
            mac=f"00:00:00:00:00:0{i}",
            ip_addresses=[f"10.0.0.{i}"],
            name=f"h{i}",
            location_device=f"of:000000000000000{switch_num}",
            location_port=port
        )
        manager.add_host(host)
        print(f"Added host: {host.name} ({host.ip_addresses[0]})")

    # Add links
    links = [
        (1, 2, 3, 3),
        (2, 3, 3, 3),
        (1, 3, 4, 4)
    ]
    for s1, s2, p1, p2 in links:
        link = NetworkLink(
            src_device=f"of:000000000000000{s1}",
            src_port=p1,
            dst_device=f"of:000000000000000{s2}",
            dst_port=p2
        )
        manager.add_link(link)
        print(f"Added link: s{s1} <-> s{s2}")

    print(f"\nTopology connected: {manager.is_connected()}")
    print(f"Network diameter: {manager.get_network_diameter()}")

    # Test path finding
    path = manager.get_shortest_path(
        "00:00:00:00:00:01/-1",
        "00:00:00:00:00:04/-1"
    )
    print(f"\nPath h1 -> h4: {path}")

    switches = manager.get_switches_on_path("h1", "h4")
    print(f"Switches on path: {switches}")

"""
Simulated Topology for LLM-NetAuto-SDN.

Pure Python network topology simulation that mirrors
the Mininet topology for demo mode operation.
"""

import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SimulatedHost:
    """Simulated network host."""
    name: str
    ip: str
    mac: str
    switch: str
    port: int


@dataclass
class SimulatedSwitch:
    """Simulated network switch."""
    name: str
    dpid: str
    device_id: str
    ports: Dict[int, str] = field(default_factory=dict)


@dataclass
class SimulatedLink:
    """Simulated network link."""
    src_switch: str
    src_port: int
    dst_switch: str
    dst_port: int
    bandwidth: int = 10  # Mbps
    delay: int = 5  # ms
    state: str = "up"


class SimulatedTopology:
    """
    Pure Python topology simulation.

    Mirrors the real Mininet topology for demo mode.
    Provides the same data structures as ONOS REST API.
    """

    def __init__(self):
        """Initialize simulated topology."""
        self._hosts: Dict[str, SimulatedHost] = {}
        self._switches: Dict[str, SimulatedSwitch] = {}
        self._links: List[SimulatedLink] = []

        self._create_default_topology()

        logger.info(
            f"SimulatedTopology initialized: "
            f"{len(self._switches)} switches, {len(self._hosts)} hosts"
        )

    def _create_default_topology(self) -> None:
        """Create the default 3-switch, 6-host topology."""
        # Create switches
        for i in range(1, 4):
            dpid = f"000000000000000{i}"
            self._switches[f"s{i}"] = SimulatedSwitch(
                name=f"s{i}",
                dpid=dpid,
                device_id=f"of:{dpid}",
                ports={
                    1: "host",
                    2: "host",
                    3: "switch",
                    4: "switch"
                }
            )

        # Create hosts
        host_configs = [
            ("h1", "10.0.0.1", "00:00:00:00:00:01", "s1", 1),
            ("h2", "10.0.0.2", "00:00:00:00:00:02", "s1", 2),
            ("h3", "10.0.0.3", "00:00:00:00:00:03", "s2", 1),
            ("h4", "10.0.0.4", "00:00:00:00:00:04", "s2", 2),
            ("h5", "10.0.0.5", "00:00:00:00:00:05", "s3", 1),
            ("h6", "10.0.0.6", "00:00:00:00:00:06", "s3", 2),
        ]

        for name, ip, mac, switch, port in host_configs:
            self._hosts[name] = SimulatedHost(
                name=name,
                ip=ip,
                mac=mac,
                switch=switch,
                port=port
            )

        # Create switch-to-switch links (triangle)
        self._links = [
            SimulatedLink("s1", 3, "s2", 3, 10, 5),
            SimulatedLink("s2", 4, "s3", 3, 10, 5),
            SimulatedLink("s1", 4, "s3", 4, 10, 5),
        ]

    # ==========================================
    # Host Operations
    # ==========================================

    def get_hosts(self) -> List[Dict[str, Any]]:
        """Get all hosts in ONOS format."""
        return [
            {
                "id": f"{h.mac}/-1",
                "mac": h.mac,
                "vlan": "-1",
                "innerVlan": "-1",
                "outerTpid": "unknown",
                "configured": False,
                "suspended": False,
                "ipAddresses": [h.ip],
                "locations": [
                    {
                        "elementId": self._switches[h.switch].device_id,
                        "port": str(h.port)
                    }
                ],
                "name": h.name
            }
            for h in self._hosts.values()
        ]

    def get_host(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get host by name, IP, or MAC."""
        for host in self._hosts.values():
            if identifier in [host.name, host.ip, host.mac]:
                switch = self._switches[host.switch]
                return {
                    "id": f"{host.mac}/-1",
                    "mac": host.mac,
                    "vlan": "-1",
                    "ipAddresses": [host.ip],
                    "locations": [{
                        "elementId": switch.device_id,
                        "port": str(host.port)
                    }],
                    "name": host.name
                }
        return None

    def resolve_host(self, identifier: str) -> Optional[Tuple[str, str, str]]:
        """Resolve host identifier to (name, ip, mac)."""
        for host in self._hosts.values():
            if identifier.lower() in [
                host.name.lower(),
                host.ip,
                host.mac.lower()
            ]:
                return host.name, host.ip, host.mac
        return None

    # ==========================================
    # Switch/Device Operations
    # ==========================================

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices in ONOS format."""
        return [
            {
                "id": s.device_id,
                "type": "SWITCH",
                "available": True,
                "role": "MASTER",
                "mfr": "Open vSwitch",
                "hw": "2.17.0",
                "sw": "2.17.0",
                "serial": "None",
                "chassisId": s.dpid,
                "annotations": {
                    "managementAddress": f"127.0.0.{i+1}",
                    "protocol": "OF_13",
                    "name": s.name
                }
            }
            for i, s in enumerate(self._switches.values())
        ]

    def get_device(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get device by name or device ID."""
        for switch in self._switches.values():
            if identifier in [switch.name, switch.device_id]:
                return {
                    "id": switch.device_id,
                    "type": "SWITCH",
                    "available": True,
                    "role": "MASTER",
                    "mfr": "Open vSwitch",
                    "hw": "2.17.0",
                    "sw": "2.17.0",
                    "chassisId": switch.dpid,
                    "annotations": {
                        "name": switch.name,
                        "protocol": "OF_13"
                    }
                }
        return None

    def resolve_device(self, identifier: str) -> Optional[str]:
        """Resolve device identifier to device ID."""
        for switch in self._switches.values():
            if identifier.lower() in [
                switch.name.lower(),
                switch.device_id.lower()
            ]:
                return switch.device_id
        return None

    # ==========================================
    # Link Operations
    # ==========================================

    def get_links(self) -> List[Dict[str, Any]]:
        """Get all links in ONOS format."""
        links = []
        for link in self._links:
            src_switch = self._switches[link.src_switch]
            dst_switch = self._switches[link.dst_switch]

            # Forward link
            links.append({
                "src": {
                    "device": src_switch.device_id,
                    "port": str(link.src_port)
                },
                "dst": {
                    "device": dst_switch.device_id,
                    "port": str(link.dst_port)
                },
                "type": "DIRECT",
                "state": "ACTIVE" if link.state == "up" else "INACTIVE",
                "annotations": {
                    "bandwidth": str(link.bandwidth),
                    "delay": str(link.delay)
                }
            })

            # Reverse link
            links.append({
                "src": {
                    "device": dst_switch.device_id,
                    "port": str(link.dst_port)
                },
                "dst": {
                    "device": src_switch.device_id,
                    "port": str(link.src_port)
                },
                "type": "DIRECT",
                "state": "ACTIVE" if link.state == "up" else "INACTIVE",
                "annotations": {}
            })

        return links

    def set_link_state(
        self,
        switch1: str,
        switch2: str,
        state: str
    ) -> bool:
        """Set link state between two switches."""
        sw1 = self.resolve_device(switch1)
        sw2 = self.resolve_device(switch2)

        for link in self._links:
            src = self._switches[link.src_switch].device_id
            dst = self._switches[link.dst_switch].device_id

            if (sw1 in [src, dst]) and (sw2 in [src, dst]):
                link.state = state
                logger.info(f"Link {switch1} <-> {switch2}: {state}")
                return True

        return False

    # ==========================================
    # Topology Export
    # ==========================================

    def get_topology(self) -> Dict[str, Any]:
        """Get complete topology in ONOS format."""
        return {
            "devices": self.get_devices(),
            "hosts": self.get_hosts(),
            "links": self.get_links()
        }

    def get_topology_for_llm(self) -> Dict[str, Any]:
        """Get topology in simplified format for LLM context."""
        return {
            "devices": [
                {
                    "id": s.device_id,
                    "name": s.name,
                    "type": "switch"
                }
                for s in self._switches.values()
            ],
            "hosts": [
                {
                    "name": h.name,
                    "ip": h.ip,
                    "mac": h.mac,
                    "device": self._switches[h.switch].device_id,
                    "port": h.port
                }
                for h in self._hosts.values()
            ],
            "links": [
                {
                    "src": self._switches[l.src_switch].name,
                    "dst": self._switches[l.dst_switch].name,
                    "src_device": self._switches[l.src_switch].device_id,
                    "dst_device": self._switches[l.dst_switch].device_id,
                    "bandwidth": l.bandwidth,
                    "delay": l.delay,
                    "state": l.state
                }
                for l in self._links
            ]
        }

    def get_path(self, src: str, dst: str) -> List[str]:
        """Get path between two entities (hosts or switches)."""
        # Simple path finding for triangle topology
        # In production, use proper shortest path algorithm

        src_resolved = self.resolve_host(src) or self.resolve_device(src)
        dst_resolved = self.resolve_host(dst) or self.resolve_device(dst)

        if not src_resolved or not dst_resolved:
            return []

        # For hosts, get their connected switches
        src_switch = None
        dst_switch = None

        if isinstance(src_resolved, tuple):
            # It's a host
            for h in self._hosts.values():
                if h.name == src_resolved[0]:
                    src_switch = h.switch
        else:
            for s in self._switches.values():
                if s.device_id == src_resolved:
                    src_switch = s.name

        if isinstance(dst_resolved, tuple):
            for h in self._hosts.values():
                if h.name == dst_resolved[0]:
                    dst_switch = h.switch
        else:
            for s in self._switches.values():
                if s.device_id == dst_resolved:
                    dst_switch = s.name

        if not src_switch or not dst_switch:
            return []

        if src_switch == dst_switch:
            return [self._switches[src_switch].device_id]

        # All switches in triangle are 1 hop apart
        return [
            self._switches[src_switch].device_id,
            self._switches[dst_switch].device_id
        ]


# Singleton instance
_topology_instance: Optional[SimulatedTopology] = None


def get_simulated_topology() -> SimulatedTopology:
    """Get or create the global simulated topology instance."""
    global _topology_instance
    if _topology_instance is None:
        _topology_instance = SimulatedTopology()
    return _topology_instance


if __name__ == "__main__":
    # Test simulated topology
    import json

    print("\n=== Simulated Topology Test ===\n")

    topo = SimulatedTopology()

    # Get devices
    print("Devices:")
    for device in topo.get_devices():
        print(f"  {device['annotations']['name']}: {device['id']}")

    # Get hosts
    print("\nHosts:")
    for host in topo.get_hosts():
        print(f"  {host['name']}: {host['ipAddresses'][0]} "
              f"({host['locations'][0]['elementId']})")

    # Get links
    print("\nLinks (forward only):")
    seen = set()
    for link in topo.get_links():
        key = tuple(sorted([link['src']['device'], link['dst']['device']]))
        if key not in seen:
            print(f"  {link['src']['device']} <-> {link['dst']['device']}")
            seen.add(key)

    # Test resolution
    print("\nResolution tests:")
    print(f"  h1 -> {topo.resolve_host('h1')}")
    print(f"  10.0.0.3 -> {topo.resolve_host('10.0.0.3')}")
    print(f"  s1 -> {topo.resolve_device('s1')}")

    # Get path
    print("\nPath h1 -> h4:")
    path = topo.get_path("h1", "h4")
    print(f"  {' -> '.join(path)}")

    # LLM format
    print("\nTopology for LLM:")
    print(json.dumps(topo.get_topology_for_llm(), indent=2))

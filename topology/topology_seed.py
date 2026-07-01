"""
Topology Seed for LLM-NetAuto-SDN (live mode only).

Seeds ChromaDB with live ONOS topology information for RAG-based
intent enrichment.  If ONOS is not yet reachable the seed falls back
to a purely calculated expected topology derived from
TOPO_SWITCHES / TOPO_HOSTS_PER_SWITCH.
"""

import os
import json
import sys
from typing import Any, Dict, List, Optional

from loguru import logger
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


class TopologySeed:
    """
    Seeds ChromaDB vector database with network topology context.

    Topology data is always fetched from ONOS (live). If ONOS is
    unavailable the expected topology is computed from env-var config
    (TOPO_SWITCHES, TOPO_HOSTS_PER_SWITCH).
    """

    def get_topology_data(self) -> Dict[str, Any]:
        """
        Return topology data in LLM-friendly format.

        Tries ONOS first; falls back to calculated expected topology.
        """
        try:
            return self._get_onos_topology()
        except Exception as e:
            logger.warning(f"Could not fetch ONOS topology for seeding: {e} — using expected topology")
            return self._get_expected_topology()

    # ------------------------------------------------------------------
    # Data sources
    # ------------------------------------------------------------------

    def _get_onos_topology(self) -> Dict[str, Any]:
        """Fetch live topology from ONOS controller."""
        from controller.onos_client import get_onos_client

        client = get_onos_client()
        if not client.health_check():
            raise RuntimeError("ONOS not reachable")

        devices = client.get_devices()
        hosts = client.get_hosts()
        links = client.get_links()

        if not devices:
            raise RuntimeError("ONOS returned 0 devices")

        return {
            "devices": [
                {
                    "id": d.get("id", ""),
                    "name": d.get("annotations", {}).get("name", d.get("id", "")),
                    "type": d.get("type", "switch").lower(),
                    "available": d.get("available", True),
                }
                for d in devices
            ],
            "hosts": [
                {
                    "name": h.get("name") or f"h{i + 1}",
                    "ip": (h.get("ipAddresses", []) or [""])[0],
                    "mac": h.get("mac", ""),
                    "device": (h.get("locations", [{}]) or [{}])[0].get("elementId", ""),
                    "port": int((h.get("locations", [{}]) or [{}])[0].get("port", 0)),
                }
                for i, h in enumerate(hosts)
            ],
            "links": [
                {
                    "src": ll.get("src", {}).get("device", ""),
                    "dst": ll.get("dst", {}).get("device", ""),
                    "state": ll.get("state", "ACTIVE"),
                }
                for ll in links
            ],
        }

    def _get_expected_topology(self) -> Dict[str, Any]:
        """
        Return the topology we expect based on TOPO_SWITCHES /
        TOPO_HOSTS_PER_SWITCH without needing a live ONOS connection.
        """
        from topology.mininet_topo import build_expected_topology

        topo = build_expected_topology()
        return {
            "devices": [
                {"id": sw["device_id"], "name": sw["name"], "type": "switch", "available": True}
                for sw in topo["switches"]
            ],
            "hosts": [
                {
                    "name": h["name"],
                    "ip": h["ip"],
                    "mac": h["mac"],
                    "device": h["device_id"],
                    "port": h["port"],
                }
                for h in topo["hosts"]
            ],
            "links": topo["links"],
        }

    # ------------------------------------------------------------------
    # RAG seeding
    # ------------------------------------------------------------------

    def seed_rag(self, topology_data: Optional[Dict] = None) -> bool:
        """
        Seed the RAG engine with topology data.

        Args:
            topology_data: Optional pre-fetched topology; fetched if None.

        Returns:
            True if seeding succeeded.
        """
        from llm.rag_engine import get_rag_engine

        if topology_data is None:
            topology_data = self.get_topology_data()

        rag = get_rag_engine()

        logger.info(
            f"Seeding RAG with {len(topology_data.get('devices', []))} devices, "
            f"{len(topology_data.get('hosts', []))} hosts, "
            f"{len(topology_data.get('links', []))} links"
        )

        return rag.seed_topology(topology_data)

    # ------------------------------------------------------------------
    # Document generation
    # ------------------------------------------------------------------

    def create_seed_documents(
        self,
        topology_data: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create documents ready for ChromaDB insertion.

        Args:
            topology_data: Optional pre-fetched topology.

        Returns:
            List of document dicts with ``type`` and ``text`` keys.
        """
        if topology_data is None:
            topology_data = self.get_topology_data()

        documents: List[Dict[str, Any]] = []

        # ── Device documents ───────────────────────────────────────────
        for device in topology_data.get("devices", []):
            documents.append({
                "type": "device",
                "id": device.get("id", ""),
                "name": device.get("name", ""),
                "text": (
                    f"Network switch {device.get('name', '')} "
                    f"with device ID {device.get('id', '')}. "
                    f"Type: {device.get('type', 'switch')}."
                ),
            })

        # ── Host documents ─────────────────────────────────────────────
        for host in topology_data.get("hosts", []):
            documents.append({
                "type": "host",
                "name": host.get("name", ""),
                "ip": host.get("ip", ""),
                "mac": host.get("mac", ""),
                "text": (
                    f"Network host {host.get('name', '')} "
                    f"with IP address {host.get('ip', '')} "
                    f"and MAC address {host.get('mac', '')}. "
                    f"Connected to switch {host.get('device', '')} "
                    f"on port {host.get('port', 0)}."
                ),
            })

        # ── Link documents ─────────────────────────────────────────────
        for link in topology_data.get("links", []):
            documents.append({
                "type": "link",
                "src": link.get("src", ""),
                "dst": link.get("dst", ""),
                "text": (
                    f"Network link between {link.get('src', '')} "
                    f"and {link.get('dst', '')}. "
                    f"State: {link.get('state', 'ACTIVE')}."
                ),
            })

        # ── Dynamic host/switch name → device-ID mappings ─────────────
        # Generated from the topology data itself so they always match
        # the current TOPO_SWITCHES / TOPO_HOSTS_PER_SWITCH config.
        for host in topology_data.get("hosts", []):
            name = host.get("name", "")
            ip = host.get("ip", "")
            mac = host.get("mac", "")
            if name and ip and mac:
                documents.append({
                    "type": "mapping",
                    "text": (
                        f"{name} refers to host with IP {ip} and MAC {mac}"
                    ),
                })

        for device in topology_data.get("devices", []):
            name = device.get("name", "")
            did = device.get("id", "")
            if name and did:
                documents.append({
                    "type": "mapping",
                    "text": f"{name} refers to switch with device ID {did}",
                })

        # ── Protocol knowledge (static) ────────────────────────────────
        documents.extend([
            {"type": "mapping", "text": "HTTP uses TCP port 80"},
            {"type": "mapping", "text": "HTTPS uses TCP port 443"},
            {"type": "mapping", "text": "SSH uses TCP port 22"},
            {"type": "mapping", "text": "VoIP and SIP use UDP port 5060"},
            {"type": "mapping", "text": "ICMP is IP protocol 1, used for ping"},
            {"type": "mapping", "text": "TCP is IP protocol 6"},
            {"type": "mapping", "text": "UDP is IP protocol 17"},
        ])

        return documents

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_topology_json(self, filepath: str = None) -> str:
        """Export topology to JSON file."""
        if filepath is None:
            filepath = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "topology.json",
            )

        topology_data = self.get_topology_data()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(topology_data, f, indent=2)

        logger.info(f"Topology exported to {filepath}")
        return filepath


# ---------------------------------------------------------------------------
# Convenience function kept for backward compatibility
# ---------------------------------------------------------------------------

def seed_topology() -> bool:
    """Seed topology data into RAG and export JSON."""
    logger.info("Starting topology seeding…")
    seeder = TopologySeed()
    topology_data = seeder.get_topology_data()
    logger.info(
        f"Topology: {len(topology_data['devices'])} devices, "
        f"{len(topology_data['hosts'])} hosts"
    )
    success = seeder.seed_rag(topology_data)
    if success:
        logger.info("RAG seeding completed successfully")
    else:
        logger.error("RAG seeding failed")
    seeder.export_topology_json()
    return success


if __name__ == "__main__":
    print("\n=== Topology Seeding ===\n")
    success = seed_topology()
    print(f"\nSeeding {'succeeded' if success else 'failed'}")

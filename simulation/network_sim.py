"""
Network Simulator for LLM-NetAuto-SDN.

Fully simulates ONOS REST API responses in memory.
All responses are ONOS-compatible JSON format.
"""

import os
import time
import random
import uuid
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SimulatedFlow:
    """Represents a simulated flow rule."""
    flow_id: str
    device_id: str
    table_id: int = 0
    priority: int = 40000
    selector: Dict = field(default_factory=dict)
    treatment: Dict = field(default_factory=dict)
    app_id: str = "org.onosproject.cli"
    state: str = "ADDED"
    bytes_count: int = 0
    packets_count: int = 0
    duration_seconds: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SimulatedIntent:
    """Represents a simulated intent."""
    key: str
    app_id: str
    intent_type: str
    priority: int
    state: str = "INSTALLED"
    src: str = ""
    dst: str = ""
    selector: Dict = field(default_factory=dict)
    treatment: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SimulatedAnomaly:
    """Represents an active anomaly."""
    anomaly_id: str
    device_id: str
    anomaly_type: str
    duration_seconds: int
    started_at: datetime
    multiplier: float = 10.0


class NetworkSimulator:
    """
    Simulates ONOS REST API and network state.

    Provides in-memory simulation of:
    - 3 switches with flow tables
    - 6 hosts with IPs and MACs
    - Triangle topology links
    - Port statistics
    - Flow and intent management
    """

    def __init__(self):
        """Initialize network simulator."""
        self._lock = threading.Lock()

        # Network state
        self._devices: Dict[str, Dict] = {}
        self._hosts: Dict[str, Dict] = {}
        self._links: Dict[str, Dict] = {}
        self._flow_tables: Dict[str, Dict[str, SimulatedFlow]] = {}
        self._intents: Dict[str, SimulatedIntent] = {}
        self._port_stats: Dict[str, Dict[int, Dict]] = {}
        self._link_states: Dict[Tuple[str, str], str] = {}

        # Anomalies
        self._active_anomalies: Dict[str, SimulatedAnomaly] = {}

        # Flow ID counter
        self._flow_counter = 1000

        # Initialize topology
        self._initialize_topology()

        logger.info("NetworkSimulator initialized with 3 switches, 6 hosts")

    def _initialize_topology(self) -> None:
        """Initialize the simulated network topology."""
        # Create 3 switches
        for i in range(1, 4):
            device_id = f"of:000000000000000{i}"
            self._devices[device_id] = {
                "id": device_id,
                "type": "SWITCH",
                "available": True,
                "role": "MASTER",
                "mfr": "Open vSwitch",
                "hw": "2.17.0",
                "sw": "2.17.0",
                "serial": f"None",
                "chassisId": f"000000000000000{i}",
                "annotations": {
                    "managementAddress": f"127.0.0.{i}",
                    "protocol": "OF_13",
                    "name": f"s{i}"
                }
            }
            # Initialize flow table
            self._flow_tables[device_id] = {}
            # Initialize port stats
            self._port_stats[device_id] = {}
            for port in range(1, 6):
                self._port_stats[device_id][port] = {
                    "port": port,
                    "packetsReceived": random.randint(10000, 100000),
                    "packetsSent": random.randint(10000, 100000),
                    "bytesReceived": random.randint(1000000, 10000000),
                    "bytesSent": random.randint(1000000, 10000000),
                    "packetsRxDropped": random.randint(0, 100),
                    "packetsTxDropped": random.randint(0, 50),
                    "packetsRxErrors": random.randint(0, 10),
                    "packetsTxErrors": random.randint(0, 5),
                    "durationSec": random.randint(1000, 10000)
                }

        # Create 6 hosts (2 per switch)
        host_configs = [
            (1, 1, "s1", 1),  # h1 on s1 port 1
            (2, 1, "s1", 2),  # h2 on s1 port 2
            (3, 2, "s2", 1),  # h3 on s2 port 1
            (4, 2, "s2", 2),  # h4 on s2 port 2
            (5, 3, "s3", 1),  # h5 on s3 port 1
            (6, 3, "s3", 2),  # h6 on s3 port 2
        ]

        for host_num, switch_num, switch_name, port in host_configs:
            mac = f"00:00:00:00:00:0{host_num}"
            ip = f"10.0.0.{host_num}"
            device_id = f"of:000000000000000{switch_num}"

            self._hosts[mac] = {
                "id": f"{mac}/-1",
                "mac": mac,
                "vlan": "-1",
                "innerVlan": "-1",
                "outerTpid": "unknown",
                "configured": False,
                "suspended": False,
                "ipAddresses": [ip],
                "locations": [
                    {
                        "elementId": device_id,
                        "port": str(port)
                    }
                ],
                "name": f"h{host_num}"
            }

        # Create triangle links between switches
        link_configs = [
            (1, 3, 2, 3),  # s1:3 <-> s2:3
            (2, 3, 3, 3),  # s2:3 <-> s3:3
            (1, 4, 3, 4),  # s1:4 <-> s3:4
        ]

        for src_sw, src_port, dst_sw, dst_port in link_configs:
            src_device = f"of:000000000000000{src_sw}"
            dst_device = f"of:000000000000000{dst_sw}"

            # Forward link
            link_id = f"{src_device}/{src_port}-{dst_device}/{dst_port}"
            self._links[link_id] = {
                "src": {
                    "device": src_device,
                    "port": str(src_port)
                },
                "dst": {
                    "device": dst_device,
                    "port": str(dst_port)
                },
                "type": "DIRECT",
                "state": "ACTIVE",
                "annotations": {}
            }
            self._link_states[(src_device, dst_device)] = "ACTIVE"

            # Reverse link
            rev_link_id = f"{dst_device}/{dst_port}-{src_device}/{src_port}"
            self._links[rev_link_id] = {
                "src": {
                    "device": dst_device,
                    "port": str(dst_port)
                },
                "dst": {
                    "device": src_device,
                    "port": str(src_port)
                },
                "type": "DIRECT",
                "state": "ACTIVE",
                "annotations": {}
            }
            self._link_states[(dst_device, src_device)] = "ACTIVE"

    # ==========================================
    # Device Operations
    # ==========================================

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices."""
        with self._lock:
            return list(self._devices.values())

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID."""
        with self._lock:
            return self._devices.get(device_id)

    # ==========================================
    # Host Operations
    # ==========================================

    def get_hosts(self) -> List[Dict[str, Any]]:
        """Get all hosts."""
        with self._lock:
            return list(self._hosts.values())

    def get_host(self, mac: str) -> Optional[Dict[str, Any]]:
        """Get host by MAC."""
        with self._lock:
            return self._hosts.get(mac)

    def get_host_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get host by IP address."""
        with self._lock:
            for host in self._hosts.values():
                if ip in host.get("ipAddresses", []):
                    return host
            return None

    def get_host_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get host by name (h1, h2, etc.)."""
        with self._lock:
            for host in self._hosts.values():
                if host.get("name", "").lower() == name.lower():
                    return host
            return None

    # ==========================================
    # Link Operations
    # ==========================================

    def get_links(self) -> List[Dict[str, Any]]:
        """Get all links."""
        with self._lock:
            return list(self._links.values())

    def bring_link_down(self, device1: str, device2: str) -> bool:
        """Bring a link down."""
        with self._lock:
            updated = False
            for link_id, link in self._links.items():
                src = link["src"]["device"]
                dst = link["dst"]["device"]
                if (src == device1 and dst == device2) or \
                   (src == device2 and dst == device1):
                    link["state"] = "INACTIVE"
                    updated = True

            if updated:
                self._link_states[(device1, device2)] = "INACTIVE"
                self._link_states[(device2, device1)] = "INACTIVE"
                logger.info(f"Link down: {device1} <-> {device2}")

            return updated

    def bring_link_up(self, device1: str, device2: str) -> bool:
        """Bring a link up."""
        with self._lock:
            updated = False
            for link_id, link in self._links.items():
                src = link["src"]["device"]
                dst = link["dst"]["device"]
                if (src == device1 and dst == device2) or \
                   (src == device2 and dst == device1):
                    link["state"] = "ACTIVE"
                    updated = True

            if updated:
                self._link_states[(device1, device2)] = "ACTIVE"
                self._link_states[(device2, device1)] = "ACTIVE"
                logger.info(f"Link up: {device1} <-> {device2}")

            return updated

    # ==========================================
    # Flow Operations
    # ==========================================

    def install_flow(
        self,
        device_id: str,
        flow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Install a flow rule.

        Args:
            device_id: Target device
            flow_json: Flow rule specification

        Returns:
            Installation result
        """
        # Simulate 50-200ms delay
        time.sleep(random.uniform(0.05, 0.2))

        with self._lock:
            if device_id not in self._devices:
                return {"error": f"Device {device_id} not found"}

            self._flow_counter += 1
            flow_id = str(self._flow_counter)

            flow = SimulatedFlow(
                flow_id=flow_id,
                device_id=device_id,
                priority=flow_json.get("priority", 40000),
                selector=flow_json.get("selector", {}),
                treatment=flow_json.get("treatment", {}),
                app_id=flow_json.get("appId", "org.onosproject.cli")
            )

            self._flow_tables[device_id][flow_id] = flow

            logger.debug(f"Installed flow {flow_id} on {device_id}")

            return {
                "flowId": flow_id,
                "deviceId": device_id,
                "state": "ADDED"
            }

    def delete_flow(self, device_id: str, flow_id: str) -> bool:
        """Delete a flow rule."""
        with self._lock:
            if device_id in self._flow_tables:
                if flow_id in self._flow_tables[device_id]:
                    del self._flow_tables[device_id][flow_id]
                    logger.debug(f"Deleted flow {flow_id} from {device_id}")
                    return True
            return False

    def get_flows(
        self,
        device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get flow rules."""
        with self._lock:
            flows = []

            devices = [device_id] if device_id else self._devices.keys()

            for did in devices:
                if did in self._flow_tables:
                    for flow in self._flow_tables[did].values():
                        # Update counters
                        flow.bytes_count += random.randint(1000, 10000)
                        flow.packets_count += random.randint(10, 100)
                        flow.duration_seconds += 1

                        flows.append({
                            "id": flow.flow_id,
                            "deviceId": flow.device_id,
                            "tableId": flow.table_id,
                            "priority": flow.priority,
                            "state": flow.state,
                            "selector": flow.selector,
                            "treatment": flow.treatment,
                            "appId": flow.app_id,
                            "bytes": flow.bytes_count,
                            "packets": flow.packets_count,
                            "life": flow.duration_seconds
                        })

            return flows

    def clear_flows(self, device_id: str, app_id: str = None) -> int:
        """Clear flows on a device."""
        with self._lock:
            if device_id not in self._flow_tables:
                return 0

            if app_id:
                # Clear only flows from specific app
                to_delete = [
                    fid for fid, f in self._flow_tables[device_id].items()
                    if f.app_id == app_id
                ]
            else:
                to_delete = list(self._flow_tables[device_id].keys())

            for fid in to_delete:
                del self._flow_tables[device_id][fid]

            return len(to_delete)

    # ==========================================
    # Intent Operations
    # ==========================================

    def install_intent(
        self,
        intent_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Install an intent."""
        # Simulate processing delay
        time.sleep(random.uniform(0.1, 0.3))

        with self._lock:
            key = intent_json.get("key", f"intent-{uuid.uuid4().hex[:8]}")
            app_id = intent_json.get("appId", "org.onosproject.cli")

            intent = SimulatedIntent(
                key=key,
                app_id=app_id,
                intent_type=intent_json.get("type", "HostToHostIntent"),
                priority=intent_json.get("priority", 40000),
                src=intent_json.get("one", ""),
                dst=intent_json.get("two", ""),
                selector=intent_json.get("selector", {}),
                treatment=intent_json.get("treatment", {})
            )

            self._intents[f"{app_id}/{key}"] = intent

            logger.debug(f"Installed intent: {key}")

            return {
                "key": key,
                "appId": app_id,
                "state": "INSTALLED"
            }

    def delete_intent(self, app_id: str, key: str) -> bool:
        """Delete an intent."""
        with self._lock:
            intent_id = f"{app_id}/{key}"
            if intent_id in self._intents:
                del self._intents[intent_id]
                logger.debug(f"Deleted intent: {key}")
                return True
            return False

    def get_intents(self) -> List[Dict[str, Any]]:
        """Get all intents."""
        with self._lock:
            return [
                {
                    "key": i.key,
                    "appId": i.app_id,
                    "type": i.intent_type,
                    "priority": i.priority,
                    "state": i.state,
                    "one": i.src,
                    "two": i.dst
                }
                for i in self._intents.values()
            ]

    # ==========================================
    # Statistics Operations
    # ==========================================

    def get_port_stats(
        self,
        device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get port statistics."""
        with self._lock:
            stats = []
            devices = [device_id] if device_id else self._devices.keys()

            for did in devices:
                if did in self._port_stats:
                    device_stats = []
                    for port, port_stat in self._port_stats[did].items():
                        # Update stats with random traffic
                        self._update_port_stats(did, port)
                        device_stats.append(port_stat.copy())

                    stats.append({
                        "device": did,
                        "ports": device_stats
                    })

            return stats

    def _update_port_stats(self, device_id: str, port: int) -> None:
        """Update port statistics with simulated traffic."""
        stats = self._port_stats[device_id][port]

        # Check for anomalies affecting this device
        multiplier = 1.0
        drop_rate = 0.001
        for anomaly in self._active_anomalies.values():
            if anomaly.device_id == device_id:
                elapsed = (datetime.now() - anomaly.started_at).total_seconds()
                if elapsed < anomaly.duration_seconds:
                    if anomaly.anomaly_type in ["traffic_spike", "ddos_sim"]:
                        multiplier = anomaly.multiplier
                    elif anomaly.anomaly_type == "packet_drop":
                        drop_rate = 0.30
                    elif anomaly.anomaly_type == "bandwidth_hog":
                        multiplier = anomaly.multiplier if port == 1 else 0.5

        # Base traffic increments
        base_rx = int(random.randint(5000, 15000) * multiplier)
        base_tx = int(random.randint(4500, 14000) * multiplier)
        base_pkt_rx = int(random.randint(50, 150) * multiplier)
        base_pkt_tx = int(random.randint(45, 140) * multiplier)

        stats["bytesReceived"] += base_rx
        stats["bytesSent"] += base_tx
        stats["packetsReceived"] += base_pkt_rx
        stats["packetsSent"] += base_pkt_tx
        stats["packetsRxDropped"] += int(base_pkt_rx * drop_rate)
        stats["durationSec"] += 1

    # ==========================================
    # Anomaly Operations
    # ==========================================

    def trigger_anomaly(
        self,
        device_id: str,
        anomaly_type: str,
        duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Trigger an anomaly on a device.

        Args:
            device_id: Target device
            anomaly_type: Type of anomaly
            duration_seconds: How long to maintain anomaly

        Returns:
            Anomaly details
        """
        multipliers = {
            "traffic_spike": 10.0,
            "ddos_sim": 100.0,
            "bandwidth_hog": 50.0,
            "packet_drop": 1.0,
            "port_flap": 1.0
        }

        with self._lock:
            anomaly_id = f"anomaly-{uuid.uuid4().hex[:8]}"
            anomaly = SimulatedAnomaly(
                anomaly_id=anomaly_id,
                device_id=device_id,
                anomaly_type=anomaly_type,
                duration_seconds=duration_seconds,
                started_at=datetime.now(),
                multiplier=multipliers.get(anomaly_type, 10.0)
            )
            self._active_anomalies[anomaly_id] = anomaly

            logger.warning(
                f"Triggered {anomaly_type} on {device_id} "
                f"for {duration_seconds}s"
            )

            return {
                "anomaly_id": anomaly_id,
                "device_id": device_id,
                "type": anomaly_type,
                "duration": duration_seconds,
                "started_at": anomaly.started_at.isoformat()
            }

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Resolve an anomaly."""
        with self._lock:
            if anomaly_id in self._active_anomalies:
                del self._active_anomalies[anomaly_id]
                logger.info(f"Resolved anomaly: {anomaly_id}")
                return True
            return False

    def resolve_all_anomalies(self) -> int:
        """Resolve all active anomalies."""
        with self._lock:
            count = len(self._active_anomalies)
            self._active_anomalies.clear()
            logger.info(f"Resolved {count} anomalies")
            return count

    def get_active_anomalies(self) -> List[Dict[str, Any]]:
        """Get all active anomalies."""
        with self._lock:
            now = datetime.now()
            active = []

            for anomaly in list(self._active_anomalies.values()):
                elapsed = (now - anomaly.started_at).total_seconds()
                remaining = anomaly.duration_seconds - elapsed

                if remaining > 0:
                    active.append({
                        "anomaly_id": anomaly.anomaly_id,
                        "device_id": anomaly.device_id,
                        "type": anomaly.anomaly_type,
                        "remaining_seconds": int(remaining),
                        "started_at": anomaly.started_at.isoformat()
                    })
                else:
                    # Auto-expire
                    del self._active_anomalies[anomaly.anomaly_id]

            return active

    # ==========================================
    # Topology Operations
    # ==========================================

    def get_topology(self) -> Dict[str, Any]:
        """Get complete topology."""
        with self._lock:
            return {
                "devices": list(self._devices.values()),
                "hosts": list(self._hosts.values()),
                "links": list(self._links.values())
            }

    def get_topology_summary(self) -> Dict[str, Any]:
        """Get topology summary."""
        with self._lock:
            flows_count = sum(
                len(flows) for flows in self._flow_tables.values()
            )
            active_links = sum(
                1 for link in self._links.values()
                if link["state"] == "ACTIVE"
            )

            return {
                "device_count": len(self._devices),
                "host_count": len(self._hosts),
                "link_count": len(self._links),
                "active_links": active_links // 2,  # Bidirectional
                "flow_count": flows_count,
                "intent_count": len(self._intents),
                "anomaly_count": len(self._active_anomalies)
            }

    # ==========================================
    # Network State
    # ==========================================

    def get_network_state(self) -> Dict[str, Any]:
        """Get complete network state snapshot."""
        with self._lock:
            return {
                "devices": list(self._devices.values()),
                "hosts": list(self._hosts.values()),
                "links": list(self._links.values()),
                "flows": self.get_flows(),
                "intents": self.get_intents(),
                "anomalies": self.get_active_anomalies(),
                "timestamp": datetime.now().isoformat()
            }

    def reset(self) -> None:
        """Reset to initial state."""
        with self._lock:
            self._flow_tables = {did: {} for did in self._devices}
            self._intents.clear()
            self._active_anomalies.clear()
            self._flow_counter = 1000

            # Reset link states
            for link in self._links.values():
                link["state"] = "ACTIVE"

            logger.info("Network simulator reset to initial state")


# Singleton instance
_simulator_instance: Optional[NetworkSimulator] = None


def get_network_simulator() -> NetworkSimulator:
    """Get or create the global network simulator instance."""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = NetworkSimulator()
    return _simulator_instance


if __name__ == "__main__":
    # Test network simulator
    print("\n=== Network Simulator Test ===\n")

    sim = NetworkSimulator()

    print("Devices:")
    for device in sim.get_devices():
        print(f"  {device['id']} - {device['annotations'].get('name')}")

    print("\nHosts:")
    for host in sim.get_hosts():
        print(f"  {host['name']}: {host['mac']} - {host['ipAddresses']}")

    print("\nLinks:")
    for link in sim.get_links()[:3]:  # First 3 (forward only)
        print(f"  {link['src']['device']}:{link['src']['port']} -> "
              f"{link['dst']['device']}:{link['dst']['port']}")

    # Install a flow
    print("\nInstalling flow...")
    result = sim.install_flow("of:0000000000000001", {
        "priority": 50000,
        "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": 2048}]},
        "treatment": {"instructions": []}
    })
    print(f"  Result: {result}")

    # Trigger anomaly
    print("\nTriggering anomaly...")
    anomaly = sim.trigger_anomaly("of:0000000000000001", "traffic_spike", 60)
    print(f"  Anomaly: {anomaly}")

    # Get summary
    print("\nTopology Summary:")
    summary = sim.get_topology_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

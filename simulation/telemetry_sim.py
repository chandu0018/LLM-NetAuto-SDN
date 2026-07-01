"""
Telemetry Simulator for LLM-NetAuto-SDN.

Generates realistic network telemetry data with
traffic profiles, time variations, and anomaly injection.
"""

import os
import random
import math
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TrafficProfile:
    """Traffic profile for a device."""
    base_rx_mbps: float
    base_tx_mbps: float
    base_drop_rate: float
    variation: float = 0.2  # ±20%


@dataclass
class InjectedAnomaly:
    """Represents an injected anomaly."""
    anomaly_id: str
    device_id: str
    anomaly_type: str
    started_at: datetime
    duration_seconds: int
    multiplier: float


class TelemetrySimulator:
    """
    Simulates realistic network telemetry.

    Features:
    - Per-device traffic profiles
    - Time-based variation (business hours vs night)
    - Random spikes
    - Anomaly injection
    """

    # Default traffic profiles per switch
    DEFAULT_PROFILES = {
        "of:0000000000000001": TrafficProfile(
            base_rx_mbps=5.0, base_tx_mbps=4.8, base_drop_rate=0.001
        ),
        "of:0000000000000002": TrafficProfile(
            base_rx_mbps=3.0, base_tx_mbps=2.9, base_drop_rate=0.0005
        ),
        "of:0000000000000003": TrafficProfile(
            base_rx_mbps=4.0, base_tx_mbps=3.8, base_drop_rate=0.0008
        ),
    }

    def __init__(self):
        """Initialize telemetry simulator."""
        self._lock = threading.Lock()
        self._profiles: Dict[str, TrafficProfile] = dict(self.DEFAULT_PROFILES)
        self._anomalies: Dict[str, InjectedAnomaly] = {}
        self._counters: Dict[str, Dict[int, Dict[str, int]]] = {}
        self._anomaly_counter = 0

        # Initialize counters for each device and port
        for device_id in self._profiles.keys():
            self._counters[device_id] = {}
            for port in range(1, 6):
                self._counters[device_id][port] = {
                    "bytes_rx": random.randint(10000000, 100000000),
                    "bytes_tx": random.randint(10000000, 100000000),
                    "packets_rx": random.randint(100000, 1000000),
                    "packets_tx": random.randint(100000, 1000000),
                    "packets_rx_dropped": random.randint(100, 1000),
                    "packets_tx_dropped": random.randint(50, 500),
                    "packets_rx_errors": random.randint(0, 50),
                    "packets_tx_errors": random.randint(0, 30),
                }

        logger.info("TelemetrySimulator initialized")

    def get_port_stats(
        self,
        device_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get port statistics for a device.

        Args:
            device_id: Device ID

        Returns:
            List of port statistics in ONOS format
        """
        with self._lock:
            if device_id not in self._counters:
                return []

            # Get current time factors
            time_multiplier = self._get_time_multiplier()
            spike_factor = self._get_spike_factor()

            # Get anomaly multipliers
            anomaly_mult, drop_mult = self._get_anomaly_multipliers(device_id)

            profile = self._profiles.get(
                device_id,
                TrafficProfile(3.0, 2.8, 0.001)
            )

            ports = []
            for port, counters in self._counters[device_id].items():
                # Calculate increment with variance
                base_mult = time_multiplier * spike_factor

                # Add Gaussian noise
                noise = random.gauss(1.0, profile.variation)
                noise = max(0.5, min(1.5, noise))  # Clamp

                # Calculate bytes increment (convert Mbps to bytes per poll)
                poll_interval = float(os.getenv("TELEMETRY_POLL_INTERVAL", "5"))
                bytes_per_poll = (profile.base_rx_mbps * 1024 * 1024 / 8) * poll_interval

                rx_increment = int(bytes_per_poll * base_mult * noise * anomaly_mult)
                tx_increment = int(
                    (profile.base_tx_mbps / profile.base_rx_mbps) *
                    bytes_per_poll * base_mult * noise * anomaly_mult
                )

                # Update counters
                counters["bytes_rx"] += rx_increment
                counters["bytes_tx"] += tx_increment
                counters["packets_rx"] += rx_increment // 500  # ~500 bytes/packet
                counters["packets_tx"] += tx_increment // 500

                # Calculate drops based on drop rate
                effective_drop_rate = profile.base_drop_rate * drop_mult
                dropped = int(counters["packets_rx"] * effective_drop_rate * 0.001)
                counters["packets_rx_dropped"] += dropped

                ports.append({
                    "port": port,
                    "packetsReceived": counters["packets_rx"],
                    "packetsSent": counters["packets_tx"],
                    "bytesReceived": counters["bytes_rx"],
                    "bytesSent": counters["bytes_tx"],
                    "packetsRxDropped": counters["packets_rx_dropped"],
                    "packetsTxDropped": counters["packets_tx_dropped"],
                    "packetsRxErrors": counters["packets_rx_errors"],
                    "packetsTxErrors": counters["packets_tx_errors"],
                    "durationSec": random.randint(10000, 50000)
                })

            return ports

    def get_telemetry_snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get telemetry snapshot for all devices.

        Returns:
            Dictionary mapping device IDs to port stats
        """
        snapshot = {}
        for device_id in self._profiles.keys():
            snapshot[device_id] = self.get_port_stats(device_id)
        return snapshot

    def get_device_metrics(self, device_id: str) -> Dict[str, float]:
        """
        Get aggregated metrics for a device.

        Args:
            device_id: Device ID

        Returns:
            Dictionary with aggregated metrics
        """
        port_stats = self.get_port_stats(device_id)
        if not port_stats:
            return {}

        total_rx = sum(p["bytesReceived"] for p in port_stats)
        total_tx = sum(p["bytesSent"] for p in port_stats)
        total_pkt_rx = sum(p["packetsReceived"] for p in port_stats)
        total_dropped = sum(p["packetsRxDropped"] for p in port_stats)

        poll_interval = float(os.getenv("TELEMETRY_POLL_INTERVAL", "5"))

        return {
            "bytes_rx_total": total_rx,
            "bytes_tx_total": total_tx,
            "bytes_rx_rate": total_rx / poll_interval,
            "bytes_tx_rate": total_tx / poll_interval,
            "packets_rx_rate": total_pkt_rx / poll_interval,
            "drop_rate": total_dropped / max(total_pkt_rx, 1),
            "error_rate": sum(p["packetsRxErrors"] for p in port_stats) / max(total_pkt_rx, 1)
        }

    def inject_anomaly(
        self,
        device_id: str,
        anomaly_type: str,
        duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Inject an anomaly.

        Args:
            device_id: Target device
            anomaly_type: Type of anomaly
            duration_seconds: Duration

        Returns:
            Anomaly details
        """
        multipliers = {
            "traffic_spike": (10.0, 1.0),    # 10x traffic, normal drops
            "ddos_sim": (100.0, 1.0),        # 100x traffic
            "packet_drop": (1.0, 300.0),     # Normal traffic, 30% drops
            "bandwidth_hog": (50.0, 1.0),    # 50x traffic
            "port_flap": (1.0, 5.0),         # Moderate drops
        }

        traffic_mult, drop_mult = multipliers.get(anomaly_type, (10.0, 1.0))

        with self._lock:
            self._anomaly_counter += 1
            anomaly_id = f"anomaly-{self._anomaly_counter:04d}"

            anomaly = InjectedAnomaly(
                anomaly_id=anomaly_id,
                device_id=device_id,
                anomaly_type=anomaly_type,
                started_at=datetime.now(),
                duration_seconds=duration_seconds,
                multiplier=traffic_mult
            )

            self._anomalies[anomaly_id] = anomaly

            logger.warning(
                f"Injected {anomaly_type} on {device_id} "
                f"(mult={traffic_mult}x, duration={duration_seconds}s)"
            )

            return {
                "anomaly_id": anomaly_id,
                "device_id": device_id,
                "type": anomaly_type,
                "duration": duration_seconds,
                "traffic_multiplier": traffic_mult,
                "drop_multiplier": drop_mult,
                "started_at": anomaly.started_at.isoformat()
            }

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Resolve an anomaly."""
        with self._lock:
            if anomaly_id in self._anomalies:
                del self._anomalies[anomaly_id]
                logger.info(f"Resolved anomaly: {anomaly_id}")
                return True
            return False

    def resolve_all_anomalies(self) -> int:
        """Resolve all anomalies."""
        with self._lock:
            count = len(self._anomalies)
            self._anomalies.clear()
            return count

    def get_active_anomalies(self) -> List[Dict[str, Any]]:
        """Get all active anomalies."""
        with self._lock:
            now = datetime.now()
            active = []

            expired_ids = []
            for anomaly_id, anomaly in self._anomalies.items():
                elapsed = (now - anomaly.started_at).total_seconds()
                remaining = anomaly.duration_seconds - elapsed

                if remaining > 0:
                    active.append({
                        "anomaly_id": anomaly.anomaly_id,
                        "device_id": anomaly.device_id,
                        "type": anomaly.anomaly_type,
                        "remaining_seconds": int(remaining),
                        "multiplier": anomaly.multiplier,
                        "started_at": anomaly.started_at.isoformat()
                    })
                else:
                    expired_ids.append(anomaly_id)

            # Clean up expired
            for aid in expired_ids:
                del self._anomalies[aid]

            return active

    def set_traffic_scenario(self, scenario: str) -> None:
        """
        Set traffic scenario.

        Args:
            scenario: Scenario name (normal, peak, low, asymmetric)
        """
        with self._lock:
            if scenario == "normal":
                self._profiles = dict(self.DEFAULT_PROFILES)
            elif scenario == "peak":
                for device_id in self._profiles:
                    self._profiles[device_id] = TrafficProfile(
                        base_rx_mbps=self._profiles[device_id].base_rx_mbps * 2,
                        base_tx_mbps=self._profiles[device_id].base_tx_mbps * 2,
                        base_drop_rate=self._profiles[device_id].base_drop_rate * 1.5
                    )
            elif scenario == "low":
                for device_id in self._profiles:
                    self._profiles[device_id] = TrafficProfile(
                        base_rx_mbps=self._profiles[device_id].base_rx_mbps * 0.3,
                        base_tx_mbps=self._profiles[device_id].base_tx_mbps * 0.3,
                        base_drop_rate=self._profiles[device_id].base_drop_rate * 0.5
                    )
            elif scenario == "asymmetric":
                # s1 overloaded, others low
                self._profiles["of:0000000000000001"] = TrafficProfile(
                    base_rx_mbps=15.0, base_tx_mbps=14.0, base_drop_rate=0.005
                )
                self._profiles["of:0000000000000002"] = TrafficProfile(
                    base_rx_mbps=1.0, base_tx_mbps=0.9, base_drop_rate=0.0002
                )
                self._profiles["of:0000000000000003"] = TrafficProfile(
                    base_rx_mbps=1.5, base_tx_mbps=1.4, base_drop_rate=0.0003
                )

            logger.info(f"Traffic scenario set to: {scenario}")

    def _get_time_multiplier(self) -> float:
        """Get traffic multiplier based on time of day."""
        hour = datetime.now().hour

        # Business hours (9am-6pm): 1.5x
        if 9 <= hour < 18:
            return 1.5
        # Evening (6pm-10pm): 1.2x
        elif 18 <= hour < 22:
            return 1.2
        # Night (10pm-6am): 0.3x
        elif hour >= 22 or hour < 6:
            return 0.3
        # Early morning (6am-9am): 0.8x
        else:
            return 0.8

    def _get_spike_factor(self) -> float:
        """Get random spike factor."""
        # 5% chance of a spike
        if random.random() < 0.05:
            return random.uniform(1.5, 2.5)
        return random.uniform(0.9, 1.1)

    def _get_anomaly_multipliers(
        self,
        device_id: str
    ) -> Tuple[float, float]:
        """Get anomaly multipliers for a device."""
        traffic_mult = 1.0
        drop_mult = 1.0

        now = datetime.now()
        for anomaly in self._anomalies.values():
            if anomaly.device_id == device_id:
                elapsed = (now - anomaly.started_at).total_seconds()
                if elapsed < anomaly.duration_seconds:
                    if anomaly.anomaly_type in ["traffic_spike", "ddos_sim", "bandwidth_hog"]:
                        traffic_mult = max(traffic_mult, anomaly.multiplier)
                    elif anomaly.anomaly_type == "packet_drop":
                        drop_mult = 300.0
                    elif anomaly.anomaly_type == "port_flap":
                        drop_mult = max(drop_mult, 5.0)

        return traffic_mult, drop_mult


# Singleton instance
_simulator_instance: Optional[TelemetrySimulator] = None


def get_telemetry_simulator() -> TelemetrySimulator:
    """Get or create the global telemetry simulator instance."""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = TelemetrySimulator()
    return _simulator_instance


if __name__ == "__main__":
    # Test telemetry simulator
    print("\n=== Telemetry Simulator Test ===\n")

    sim = TelemetrySimulator()

    # Get baseline stats
    print("Baseline stats for s1:")
    stats = sim.get_port_stats("of:0000000000000001")
    for port in stats[:2]:  # First 2 ports
        print(f"  Port {port['port']}: "
              f"RX={port['bytesReceived']:,} bytes, "
              f"Drops={port['packetsRxDropped']}")

    # Inject anomaly
    print("\nInjecting traffic spike...")
    anomaly = sim.inject_anomaly(
        "of:0000000000000001",
        "traffic_spike",
        duration_seconds=30
    )
    print(f"  Anomaly ID: {anomaly['anomaly_id']}")

    # Get stats during anomaly
    print("\nStats during anomaly:")
    stats = sim.get_port_stats("of:0000000000000001")
    for port in stats[:2]:
        print(f"  Port {port['port']}: "
              f"RX={port['bytesReceived']:,} bytes, "
              f"Drops={port['packetsRxDropped']}")

    # Get active anomalies
    print(f"\nActive anomalies: {len(sim.get_active_anomalies())}")

    # Aggregate metrics
    print("\nAggregate metrics for s1:")
    metrics = sim.get_device_metrics("of:0000000000000001")
    for key, value in metrics.items():
        print(f"  {key}: {value:,.2f}")

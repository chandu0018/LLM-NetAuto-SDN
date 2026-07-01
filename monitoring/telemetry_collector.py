"""
Telemetry Collector for LLM-NetAuto-SDN.

Polls ONOS or simulation for network statistics
and maintains a rolling history for analysis.
"""

import os
import time
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import deque

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class TelemetryCollector:
    """
    Collects network telemetry from ONOS or simulation.

    Features:
    - Polls every N seconds (configurable)
    - Maintains rolling history per device
    - Thread-safe operations
    - Calculates rates from deltas
    """

    def __init__(self, max_samples: int = 500):
        """
        Initialize telemetry collector.

        Args:
            max_samples: Maximum samples to keep per device
        """
        self._poll_interval = int(os.getenv("TELEMETRY_POLL_INTERVAL", "5"))
        self._max_samples = max_samples

        self._lock = threading.Lock()
        self._history: Dict[str, deque] = {}
        self._latest: Dict[str, Dict] = {}
        self._active_anomalies: Dict[str, Dict] = {}
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_poll: Optional[datetime] = None

        # ONOS source only (live mode)
        self._onos_client = None
        self._initialize_sources()

        logger.info(
            f"TelemetryCollector initialized "
            f"(interval={self._poll_interval}s, max_samples={max_samples})"
        )

    def _initialize_sources(self) -> None:
        """Initialize ONOS data source."""
        try:
            from controller.onos_client import get_onos_client
            self._onos_client = get_onos_client()
            logger.info("Telemetry source: ONOS live mode")
        except Exception as e:
            logger.error(f"Could not initialize ONOS client for telemetry: {e}")

    def start(self) -> None:
        """Start the polling thread."""
        if self._running:
            return

        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True
        )
        self._poll_thread.start()
        logger.info("TelemetryCollector started")

    def stop(self) -> None:
        """Stop the polling thread."""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        logger.info("TelemetryCollector stopped")

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                self._collect()
            except Exception as e:
                logger.error(f"Telemetry collection error: {e}")

            time.sleep(self._poll_interval)

    def _collect(self) -> None:
        """Collect telemetry from source."""
        now = datetime.now()

        stats = self._collect_from_onos()

        with self._lock:
            for device_id, device_stats in stats.items():
                # Initialize history if needed
                if device_id not in self._history:
                    self._history[device_id] = deque(maxlen=self._max_samples)

                # Calculate rates
                rates = self._calculate_rates(device_id, device_stats)

                # Check for active manual anomaly injection
                active_anomaly = self._active_anomalies.get(device_id)
                if active_anomaly:
                    # Check if expired
                    elapsed = (now - active_anomaly["start"]).total_seconds()
                    if elapsed > active_anomaly["duration"]:
                        logger.info(f"Manual anomaly expired on {device_id}")
                        del self._active_anomalies[device_id]
                    else:
                        atype = active_anomaly["type"]
                        # Inject anomalous rates
                        if atype == "packet_drop":
                            rates["drop_rate"] = 0.18
                        elif atype == "error_spike":
                            rates["error_rate"] = 0.08
                        elif atype == "traffic_spike":
                            rates["bytes_rx_rate"] = 85.0 * 1e6
                            rates["bytes_tx_rate"] = 80.0 * 1e6
                            rates["packets_rx_rate"] = 95000.0
                        elif atype == "ddos_sim":
                            rates["bytes_rx_rate"] = 90.0 * 1e6
                            rates["bytes_tx_rate"] = 1.5 * 1e6
                            rates["packets_rx_rate"] = 110000.0
                        elif atype == "bandwidth_hog":
                            rates["bytes_tx_rate"] = 65.0 * 1e6
                            rates["bytes_rx_rate"] = 5.0 * 1e6
                        logger.debug(f"Injected anomaly '{atype}' on {device_id}")

                # Create sample
                sample = {
                    "timestamp": now.isoformat(),
                    "device_id": device_id,
                    "raw": device_stats,
                    "rates": rates
                }

                # Store
                self._history[device_id].append(sample)
                self._latest[device_id] = sample

            self._last_poll = now

    def _collect_from_onos(self) -> Dict[str, Dict]:
        """Collect from ONOS controller (live mode only)."""
        stats = {}
        if not self._onos_client:
            logger.error("ONOS client not available — no telemetry collected")
            return stats
        try:
            port_stats = self._onos_client.get_port_stats()
            for device_stats in port_stats:
                device_id = device_stats.get("device", "")
                ports = device_stats.get("ports", [])
                if device_id:
                    stats[device_id] = self._aggregate_port_stats(ports)
        except Exception as e:
            logger.error(f"Failed to collect telemetry from ONOS: {e}")
        if not stats:
            logger.warning("ONOS returned no port statistics — check that Mininet is running and switches are connected")
        return stats

    def _aggregate_port_stats(
        self,
        ports: List[Dict]
    ) -> Dict[str, Any]:
        """Aggregate port statistics for a device."""
        total = {
            "bytes_rx": 0,
            "bytes_tx": 0,
            "packets_rx": 0,
            "packets_tx": 0,
            "packets_rx_dropped": 0,
            "packets_tx_dropped": 0,
            "packets_rx_errors": 0,
            "packets_tx_errors": 0,
            "port_count": len(ports)
        }

        for port in ports:
            total["bytes_rx"] += port.get("bytesReceived", 0)
            total["bytes_tx"] += port.get("bytesSent", 0)
            total["packets_rx"] += port.get("packetsReceived", 0)
            total["packets_tx"] += port.get("packetsSent", 0)
            total["packets_rx_dropped"] += port.get("packetsRxDropped", 0)
            total["packets_tx_dropped"] += port.get("packetsTxDropped", 0)
            total["packets_rx_errors"] += port.get("packetsRxErrors", 0)
            total["packets_tx_errors"] += port.get("packetsTxErrors", 0)

        return total

    def _calculate_rates(
        self,
        device_id: str,
        current_stats: Dict
    ) -> Dict[str, float]:
        """Calculate rates from current and previous stats."""
        rates = {
            "bytes_rx_rate": 0.0,
            "bytes_tx_rate": 0.0,
            "packets_rx_rate": 0.0,
            "packets_tx_rate": 0.0,
            "drop_rate": 0.0,
            "error_rate": 0.0
        }

        if device_id not in self._latest:
            return rates

        prev = self._latest[device_id].get("raw", {})
        interval = self._poll_interval

        # Calculate deltas
        bytes_rx_delta = current_stats["bytes_rx"] - prev.get("bytes_rx", 0)
        bytes_tx_delta = current_stats["bytes_tx"] - prev.get("bytes_tx", 0)
        packets_rx_delta = current_stats["packets_rx"] - prev.get("packets_rx", 0)
        packets_tx_delta = current_stats["packets_tx"] - prev.get("packets_tx", 0)
        dropped_delta = (
            current_stats["packets_rx_dropped"] -
            prev.get("packets_rx_dropped", 0)
        )
        errors_delta = (
            current_stats["packets_rx_errors"] -
            prev.get("packets_rx_errors", 0)
        )

        # Calculate rates
        if interval > 0:
            rates["bytes_rx_rate"] = max(0, bytes_rx_delta / interval)
            rates["bytes_tx_rate"] = max(0, bytes_tx_delta / interval)
            rates["packets_rx_rate"] = max(0, packets_rx_delta / interval)
            rates["packets_tx_rate"] = max(0, packets_tx_delta / interval)

        # Drop rate as percentage
        if packets_rx_delta > 0:
            rates["drop_rate"] = dropped_delta / packets_rx_delta
        else:
            rates["drop_rate"] = 0.0

        # Error rate
        if packets_rx_delta > 0:
            rates["error_rate"] = errors_delta / packets_rx_delta

        return rates

    # ==========================================
    # Public API
    # ==========================================

    def get_latest(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get latest telemetry.

        Args:
            device_id: Optional specific device

        Returns:
            Latest telemetry sample(s)
        """
        with self._lock:
            if device_id:
                return self._latest.get(device_id, {})
            return dict(self._latest)

    def get_history(
        self,
        device_id: str,
        n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get history for a device.

        Args:
            device_id: Device ID
            n: Number of samples (None = all)

        Returns:
            List of telemetry samples
        """
        with self._lock:
            if device_id not in self._history:
                return []

            history = list(self._history[device_id])
            if n:
                return history[-n:]
            return history

    def get_all_history(self) -> Dict[str, List[Dict]]:
        """Get history for all devices."""
        with self._lock:
            return {
                did: list(hist)
                for did, hist in self._history.items()
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics."""
        with self._lock:
            return {
                "devices_monitored": len(self._history),
                "total_samples": sum(
                    len(h) for h in self._history.values()
                ),
                "max_samples_per_device": self._max_samples,
                "poll_interval": self._poll_interval,
                "running": self._running,
                "last_poll": (
                    self._last_poll.isoformat() if self._last_poll else None
                )
            }

    def collect_now(self) -> Dict[str, Dict]:
        """Force immediate collection."""
        self._collect()
        return self.get_latest()

    def inject_anomaly(self, device_id: str, anomaly_type: str, duration_seconds: int = 60) -> None:
        """Inject a manual anomaly on a device."""
        with self._lock:
            self._active_anomalies[device_id] = {
                "type": anomaly_type,
                "start": datetime.now(),
                "duration": duration_seconds
            }
        logger.warning(f"Injected manual anomaly of type '{anomaly_type}' on '{device_id}' for {duration_seconds}s")

    def resolve_anomalies(self) -> None:
        """Resolve and clear all manually injected anomalies."""
        with self._lock:
            self._active_anomalies.clear()
        logger.info("Cleared all manual anomaly injections")

    @property
    def is_running(self) -> bool:
        """Check if collector is running."""
        return self._running


# Singleton instance
_collector_instance: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get or create the global telemetry collector instance."""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = TelemetryCollector()
    return _collector_instance


if __name__ == "__main__":
    # Test telemetry collector
    print("\n=== Telemetry Collector Test ===\n")

    collector = TelemetryCollector()
    collector.start()

    print("Collecting telemetry...")
    time.sleep(6)  # Wait for 1+ poll cycles

    print("\nLatest telemetry:")
    latest = collector.get_latest()
    for device_id, data in latest.items():
        print(f"\n{device_id}:")
        if data.get("rates"):
            for key, value in data["rates"].items():
                print(f"  {key}: {value:,.2f}")

    print("\nStatistics:")
    stats = collector.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    collector.stop()

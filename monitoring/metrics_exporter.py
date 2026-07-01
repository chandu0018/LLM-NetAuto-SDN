"""
Metrics Exporter for LLM-NetAuto-SDN.

Exports Prometheus metrics for monitoring integration.
"""

import os
import threading
from typing import Any, Dict, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        start_http_server, REGISTRY
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed")

load_dotenv()


class MetricsExporter:
    """
    Prometheus metrics exporter.

    Exposes SDN metrics on configurable port for
    Prometheus scraping.
    """

    def __init__(self, port: int = None):
        """
        Initialize metrics exporter.

        Args:
            port: HTTP port for metrics endpoint
        """
        self._port = port or int(os.getenv("METRICS_EXPORTER_PORT", "9091"))
        self._server_started = False
        self._lock = threading.Lock()

        # Initialize metrics if prometheus available
        self._metrics = {}
        if PROMETHEUS_AVAILABLE:
            self._initialize_metrics()

        logger.info(f"MetricsExporter initialized (port={self._port})")

    def _initialize_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        # Traffic metrics
        self._metrics["bytes_rx"] = Gauge(
            "sdn_bytes_rx_total",
            "Total bytes received",
            ["device", "port"]
        )
        self._metrics["bytes_tx"] = Gauge(
            "sdn_bytes_tx_total",
            "Total bytes transmitted",
            ["device", "port"]
        )
        self._metrics["packets_rx"] = Gauge(
            "sdn_packets_rx_total",
            "Total packets received",
            ["device", "port"]
        )
        self._metrics["packets_dropped"] = Gauge(
            "sdn_packets_dropped_total",
            "Total packets dropped",
            ["device", "port"]
        )

        # Anomaly metrics
        self._metrics["anomaly_count"] = Counter(
            "sdn_anomaly_count",
            "Number of anomalies detected",
            ["device", "type"]
        )
        self._metrics["anomaly_score"] = Gauge(
            "sdn_anomaly_score",
            "Current anomaly score",
            ["device"]
        )

        # Intent metrics
        self._metrics["intent_success"] = Counter(
            "sdn_intent_success_total",
            "Successful intent deployments"
        )
        self._metrics["intent_failure"] = Counter(
            "sdn_intent_failure_total",
            "Failed intent deployments"
        )

        # Remediation metrics
        self._metrics["remediation_count"] = Counter(
            "sdn_remediation_total",
            "Total remediations performed",
            ["device", "type"]
        )

        # LLM metrics
        self._metrics["llm_latency"] = Histogram(
            "sdn_llm_latency_seconds",
            "LLM processing latency",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )

        # System metrics
        self._metrics["flow_count"] = Gauge(
            "sdn_flow_count",
            "Number of flow rules",
            ["device"]
        )
        self._metrics["intent_count"] = Gauge(
            "sdn_intent_count",
            "Number of active intents"
        )
        self._metrics["alert_count"] = Gauge(
            "sdn_alert_count",
            "Number of active alerts",
            ["severity"]
        )

    def start(self) -> bool:
        """Start the HTTP metrics server."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Cannot start metrics server - prometheus_client not available")
            return False

        if self._server_started:
            return True

        try:
            start_http_server(self._port)
            self._server_started = True
            logger.info(f"Metrics server started on port {self._port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            return False

    # ==========================================
    # Traffic Metrics
    # ==========================================

    def update_traffic_metrics(
        self,
        device_id: str,
        port: int,
        bytes_rx: int,
        bytes_tx: int,
        packets_rx: int,
        packets_dropped: int
    ) -> None:
        """Update traffic metrics for a port."""
        if not PROMETHEUS_AVAILABLE:
            return

        with self._lock:
            self._metrics["bytes_rx"].labels(
                device=device_id, port=str(port)
            ).set(bytes_rx)
            self._metrics["bytes_tx"].labels(
                device=device_id, port=str(port)
            ).set(bytes_tx)
            self._metrics["packets_rx"].labels(
                device=device_id, port=str(port)
            ).set(packets_rx)
            self._metrics["packets_dropped"].labels(
                device=device_id, port=str(port)
            ).set(packets_dropped)

    def update_from_port_stats(
        self,
        device_id: str,
        port_stats: list
    ) -> None:
        """Update metrics from ONOS port stats."""
        if not PROMETHEUS_AVAILABLE:
            return

        for port_stat in port_stats:
            port = port_stat.get("port", 0)
            self.update_traffic_metrics(
                device_id=device_id,
                port=port,
                bytes_rx=port_stat.get("bytesReceived", 0),
                bytes_tx=port_stat.get("bytesSent", 0),
                packets_rx=port_stat.get("packetsReceived", 0),
                packets_dropped=port_stat.get("packetsRxDropped", 0)
            )

    # ==========================================
    # Anomaly Metrics
    # ==========================================

    def record_anomaly(
        self,
        device_id: str,
        anomaly_type: str,
        score: float
    ) -> None:
        """Record an anomaly detection."""
        if not PROMETHEUS_AVAILABLE:
            return

        with self._lock:
            self._metrics["anomaly_count"].labels(
                device=device_id, type=anomaly_type
            ).inc()
            self._metrics["anomaly_score"].labels(
                device=device_id
            ).set(score)

    def update_anomaly_score(
        self,
        device_id: str,
        score: float
    ) -> None:
        """Update anomaly score for a device."""
        if not PROMETHEUS_AVAILABLE:
            return

        with self._lock:
            self._metrics["anomaly_score"].labels(
                device=device_id
            ).set(score)

    # ==========================================
    # Intent Metrics
    # ==========================================

    def record_intent_success(self) -> None:
        """Record successful intent deployment."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["intent_success"].inc()

    def record_intent_failure(self) -> None:
        """Record failed intent deployment."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["intent_failure"].inc()

    # ==========================================
    # Remediation Metrics
    # ==========================================

    def record_remediation(
        self,
        device_id: str,
        remediation_type: str
    ) -> None:
        """Record a remediation action."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["remediation_count"].labels(
            device=device_id, type=remediation_type
        ).inc()

    # ==========================================
    # LLM Metrics
    # ==========================================

    def record_llm_latency(self, latency_seconds: float) -> None:
        """Record LLM processing latency."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["llm_latency"].observe(latency_seconds)

    # ==========================================
    # System Metrics
    # ==========================================

    def update_flow_count(self, device_id: str, count: int) -> None:
        """Update flow count for a device."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["flow_count"].labels(device=device_id).set(count)

    def update_intent_count(self, count: int) -> None:
        """Update total intent count."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["intent_count"].set(count)

    def update_alert_count(self, severity: str, count: int) -> None:
        """Update alert count by severity."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["alert_count"].labels(severity=severity).set(count)

    # ==========================================
    # Status
    # ==========================================

    def get_status(self) -> Dict[str, Any]:
        """Get exporter status."""
        return {
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "server_started": self._server_started,
            "port": self._port,
            "metrics_count": len(self._metrics)
        }


# Singleton instance
_exporter_instance: Optional[MetricsExporter] = None


def get_metrics_exporter() -> MetricsExporter:
    """Get or create the global metrics exporter instance."""
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = MetricsExporter()
    return _exporter_instance


if __name__ == "__main__":
    # Test metrics exporter
    print("\n=== Metrics Exporter Test ===\n")

    exporter = MetricsExporter()

    print(f"Prometheus available: {PROMETHEUS_AVAILABLE}")
    print(f"Status: {exporter.get_status()}")

    if PROMETHEUS_AVAILABLE:
        # Update some metrics
        exporter.update_traffic_metrics(
            device_id="of:0000000000000001",
            port=1,
            bytes_rx=10000000,
            bytes_tx=9000000,
            packets_rx=100000,
            packets_dropped=100
        )
        exporter.record_anomaly("of:0000000000000001", "traffic_spike", -0.8)
        exporter.record_intent_success()
        exporter.record_llm_latency(1.5)

        print("Metrics updated successfully")

        # Start server
        if exporter.start():
            print(f"\nMetrics available at http://localhost:{exporter._port}/metrics")
            print("Press Ctrl+C to stop...")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopped")

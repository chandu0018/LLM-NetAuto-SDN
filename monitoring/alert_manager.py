"""
Alert Manager for LLM-NetAuto-SDN.

Threshold-based alerting system for network events.
"""

import os
import threading
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a network alert."""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    device_id: str
    metric: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AlertManager:
    """
    Threshold-based alert management system.

    Features:
    - Configurable thresholds
    - Multiple severity levels
    - Alert deduplication
    - Alert acknowledgment
    - Alert history
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        "drop_rate": {
            "warning": 0.02,      # 2%
            "critical": 0.05,     # 5%
            "message": "High packet drop rate"
        },
        "bytes_rx_rate": {
            "warning": 50e6,      # 50 MB/s
            "critical": 100e6,    # 100 MB/s
            "message": "Bandwidth spike detected"
        },
        "bytes_tx_rate": {
            "warning": 50e6,
            "critical": 100e6,
            "message": "High egress traffic"
        },
        "error_rate": {
            "warning": 0.005,     # 0.5%
            "critical": 0.01,     # 1%
            "message": "High error rate"
        },
        "device_down": {
            "critical": 1,
            "message": "Device unreachable"
        }
    }

    def __init__(self, max_history: int = 200):
        """
        Initialize alert manager.

        Args:
            max_history: Maximum alerts to keep
        """
        self._lock = threading.Lock()
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._alert_history: deque = deque(maxlen=max_history)
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_counter = 0
        self._subscribers: List[Callable[[Alert], None]] = []

        logger.info("AlertManager initialized")

    def check_thresholds(
        self,
        device_id: str,
        metrics: Dict[str, float]
    ) -> List[Alert]:
        """
        Check metrics against thresholds.

        Args:
            device_id: Device ID
            metrics: Metric name -> value mapping

        Returns:
            List of triggered alerts
        """
        alerts = []

        with self._lock:
            for metric, value in metrics.items():
                if metric not in self._thresholds:
                    continue

                config = self._thresholds[metric]

                # Check critical threshold
                if "critical" in config and value >= config["critical"]:
                    alert = self._create_alert(
                        device_id=device_id,
                        metric=metric,
                        value=value,
                        threshold=config["critical"],
                        severity=AlertSeverity.CRITICAL,
                        message=config.get("message", f"High {metric}")
                    )
                    if alert:
                        alerts.append(alert)

                # Check warning threshold
                elif "warning" in config and value >= config["warning"]:
                    alert = self._create_alert(
                        device_id=device_id,
                        metric=metric,
                        value=value,
                        threshold=config["warning"],
                        severity=AlertSeverity.WARNING,
                        message=config.get("message", f"Elevated {metric}")
                    )
                    if alert:
                        alerts.append(alert)

        return alerts

    def _create_alert(
        self,
        device_id: str,
        metric: str,
        value: float,
        threshold: float,
        severity: AlertSeverity,
        message: str
    ) -> Optional[Alert]:
        """Create an alert with deduplication."""
        # Dedup key
        dedup_key = f"{device_id}_{metric}_{severity.value}"

        # Check if similar alert already active
        if dedup_key in self._active_alerts:
            existing = self._active_alerts[dedup_key]
            if not existing.resolved:
                # Update value
                existing.value = value
                existing.timestamp = datetime.now()
                return None

        # Create new alert
        self._alert_counter += 1
        alert = Alert(
            alert_id=f"alert-{self._alert_counter:05d}",
            severity=severity,
            title=f"{message} on {device_id}",
            message=(
                f"{metric} = {self._format_value(metric, value)} "
                f"(threshold: {self._format_value(metric, threshold)})"
            ),
            device_id=device_id,
            metric=metric,
            value=value,
            threshold=threshold
        )

        self._active_alerts[dedup_key] = alert
        self._alert_history.append(alert)

        # Notify subscribers
        self._notify_subscribers(alert)

        logger.warning(
            f"Alert [{alert.severity.value}]: {alert.title} - {alert.message}"
        )

        return alert

    def _format_value(self, metric: str, value: float) -> str:
        """Format metric value for display."""
        if "rate" in metric and "bytes" in metric:
            if value >= 1e9:
                return f"{value/1e9:.2f} GB/s"
            elif value >= 1e6:
                return f"{value/1e6:.2f} MB/s"
            elif value >= 1e3:
                return f"{value/1e3:.2f} KB/s"
            return f"{value:.2f} B/s"
        elif "rate" in metric:
            return f"{value*100:.2f}%"
        return f"{value:.2f}"

    def _notify_subscribers(self, alert: Alert) -> None:
        """Notify all subscribers of an alert."""
        for callback in self._subscribers:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    # ==========================================
    # Public API
    # ==========================================

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) alerts."""
        with self._lock:
            return [
                self._alert_to_dict(alert)
                for alert in self._active_alerts.values()
                if not alert.resolved
            ]

    def get_alert_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get alert history."""
        with self._lock:
            history = list(self._alert_history)
            if limit:
                history = history[-limit:]
            return [self._alert_to_dict(a) for a in history]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            for alert in self._active_alerts.values():
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    logger.info(f"Alert acknowledged: {alert_id}")
                    return True
            return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._lock:
            for alert in self._active_alerts.values():
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    logger.info(f"Alert resolved: {alert_id}")
                    return True
            return False

    def resolve_by_device(self, device_id: str) -> int:
        """Resolve all alerts for a device."""
        with self._lock:
            count = 0
            for alert in self._active_alerts.values():
                if alert.device_id == device_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    count += 1
            return count

    def clear_resolved(self) -> int:
        """Clear resolved alerts from active list."""
        with self._lock:
            to_remove = [
                k for k, v in self._active_alerts.items()
                if v.resolved
            ]
            for key in to_remove:
                del self._active_alerts[key]
            return len(to_remove)

    def subscribe(
        self,
        callback: Callable[[Alert], None]
    ) -> None:
        """Subscribe to alert notifications."""
        self._subscribers.append(callback)

    def unsubscribe(
        self,
        callback: Callable[[Alert], None]
    ) -> bool:
        """Unsubscribe from alert notifications."""
        try:
            self._subscribers.remove(callback)
            return True
        except ValueError:
            return False

    def set_threshold(
        self,
        metric: str,
        warning: Optional[float] = None,
        critical: Optional[float] = None,
        message: Optional[str] = None
    ) -> None:
        """Update threshold for a metric."""
        with self._lock:
            if metric not in self._thresholds:
                self._thresholds[metric] = {}

            if warning is not None:
                self._thresholds[metric]["warning"] = warning
            if critical is not None:
                self._thresholds[metric]["critical"] = critical
            if message is not None:
                self._thresholds[metric]["message"] = message

    def get_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured thresholds."""
        with self._lock:
            return dict(self._thresholds)

    def reset_all(self) -> None:
        """Clear active alerts and alert history."""
        with self._lock:
            self._active_alerts.clear()
            self._alert_history.clear()
            self._alert_counter = 0
        logger.info("AlertManager reset completed")

    def _alert_to_dict(self, alert: Alert) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": alert.alert_id,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "device_id": alert.device_id,
            "metric": alert.metric,
            "value": alert.value,
            "threshold": alert.threshold,
            "timestamp": alert.timestamp.isoformat(),
            "acknowledged": alert.acknowledged,
            "resolved": alert.resolved,
            "resolved_at": (
                alert.resolved_at.isoformat()
                if alert.resolved_at else None
            )
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            active = [a for a in self._active_alerts.values() if not a.resolved]
            critical = sum(
                1 for a in active if a.severity == AlertSeverity.CRITICAL
            )
            warning = sum(
                1 for a in active if a.severity == AlertSeverity.WARNING
            )

            return {
                "active_alerts": len(active),
                "critical_count": critical,
                "warning_count": warning,
                "total_history": len(self._alert_history),
                "subscribers": len(self._subscribers)
            }


# Singleton instance
_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AlertManager()
    return _manager_instance


if __name__ == "__main__":
    # Test alert manager
    print("\n=== Alert Manager Test ===\n")

    manager = AlertManager()

    # Subscribe to alerts
    def alert_callback(alert: Alert):
        print(f"  [CALLBACK] {alert.severity.value}: {alert.title}")

    manager.subscribe(alert_callback)

    # Check thresholds with normal values
    print("Normal values - no alerts expected:")
    alerts = manager.check_thresholds("of:0000000000000001", {
        "drop_rate": 0.001,
        "bytes_rx_rate": 5e6,
        "error_rate": 0.0001
    })
    print(f"  Alerts: {len(alerts)}")

    # Check with warning level
    print("\nWarning level:")
    alerts = manager.check_thresholds("of:0000000000000001", {
        "drop_rate": 0.03,  # 3% > 2% warning
        "bytes_rx_rate": 60e6  # 60 MB/s > 50 MB/s warning
    })
    print(f"  Alerts: {len(alerts)}")

    # Check with critical level
    print("\nCritical level:")
    alerts = manager.check_thresholds("of:0000000000000002", {
        "drop_rate": 0.10,  # 10% > 5% critical
    })
    print(f"  Alerts: {len(alerts)}")

    # Get active alerts
    print("\nActive alerts:")
    for alert in manager.get_active_alerts():
        print(f"  [{alert['severity']}] {alert['title']}")

    # Acknowledge an alert
    print("\nAcknowledging first alert...")
    active = manager.get_active_alerts()
    if active:
        manager.acknowledge_alert(active[0]["alert_id"])

    # Statistics
    print("\nStatistics:")
    stats = manager.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

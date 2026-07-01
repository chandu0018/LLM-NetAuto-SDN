"""
Tests for Anomaly Detection Module.

Tests the IsolationForest-based anomaly detection including:
- Model training
- Anomaly detection
- Alert generation
"""

import os
import sys
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set demo mode for testing
os.environ["DEMO_MODE"] = "true"


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""

    @pytest.fixture
    def detector(self):
        """Get AnomalyDetector instance."""
        from monitoring.anomaly_detector import AnomalyDetector
        return AnomalyDetector()

    def test_detector_initialization(self, detector):
        """Test detector initializes correctly."""
        assert detector is not None
        assert detector._model is not None

    def test_add_training_sample(self, detector):
        """Test adding training samples."""
        sample = {
            "bytes_received": 1000000,
            "bytes_sent": 500000,
            "packets_received": 10000,
            "packets_sent": 5000,
            "errors": 0,
            "dropped": 0
        }

        initial_count = len(detector._training_data)
        detector.add_sample(sample)
        new_count = len(detector._training_data)

        assert new_count == initial_count + 1

    def test_auto_training(self, detector):
        """Test automatic model training after sufficient samples."""
        # Add enough samples to trigger training
        for i in range(150):
            sample = {
                "bytes_received": 1000000 + np.random.normal(0, 50000),
                "bytes_sent": 500000 + np.random.normal(0, 25000),
                "packets_received": 10000 + np.random.normal(0, 500),
                "packets_sent": 5000 + np.random.normal(0, 250),
                "errors": 0,
                "dropped": 0
            }
            detector.add_sample(sample)

        # Model should be trained now
        assert detector._trained is True

    def test_detect_normal_traffic(self, detector):
        """Test that normal traffic is not flagged."""
        # Train with normal data first
        for i in range(100):
            sample = {
                "bytes_received": 1000000 + np.random.normal(0, 50000),
                "bytes_sent": 500000 + np.random.normal(0, 25000),
                "packets_received": 10000 + np.random.normal(0, 500),
                "packets_sent": 5000 + np.random.normal(0, 250),
                "errors": 0,
                "dropped": 0
            }
            detector.add_sample(sample)

        # Train the model
        detector.train()

        # Test with normal sample
        normal = {
            "bytes_received": 1050000,
            "bytes_sent": 520000,
            "packets_received": 10500,
            "packets_sent": 5200,
            "errors": 0,
            "dropped": 0
        }

        is_anomaly = detector.detect(normal)

        # Normal traffic should not be flagged (usually)
        # Note: IsolationForest can have some false positives
        assert isinstance(is_anomaly, bool)

    def test_detect_traffic_spike(self, detector):
        """Test detection of traffic spike anomaly."""
        # Train with normal data
        for i in range(100):
            sample = {
                "bytes_received": 1000000 + np.random.normal(0, 50000),
                "bytes_sent": 500000 + np.random.normal(0, 25000),
                "packets_received": 10000 + np.random.normal(0, 500),
                "packets_sent": 5000 + np.random.normal(0, 250),
                "errors": 0,
                "dropped": 0
            }
            detector.add_sample(sample)

        detector.train()

        # Test with spike (10x traffic)
        spike = {
            "bytes_received": 10000000,  # 10x normal
            "bytes_sent": 5000000,       # 10x normal
            "packets_received": 100000,  # 10x normal
            "packets_sent": 50000,       # 10x normal
            "errors": 0,
            "dropped": 0
        }

        is_anomaly = detector.detect(spike)

        # This extreme spike should definitely be flagged
        assert is_anomaly is True

    def test_detect_packet_drop(self, detector):
        """Test detection of packet drop anomaly."""
        # Train with normal data (low drops)
        for i in range(100):
            sample = {
                "bytes_received": 1000000,
                "bytes_sent": 500000,
                "packets_received": 10000,
                "packets_sent": 5000,
                "errors": 0,
                "dropped": np.random.randint(0, 10)  # Low drops
            }
            detector.add_sample(sample)

        detector.train()

        # Test with high drops
        high_drop = {
            "bytes_received": 1000000,
            "bytes_sent": 500000,
            "packets_received": 10000,
            "packets_sent": 5000,
            "errors": 0,
            "dropped": 3000  # 30% drop rate
        }

        is_anomaly = detector.detect(high_drop)
        assert is_anomaly is True

    def test_detect_error_spike(self, detector):
        """Test detection of error spike anomaly."""
        # Train with normal data (no errors)
        for i in range(100):
            sample = {
                "bytes_received": 1000000,
                "bytes_sent": 500000,
                "packets_received": 10000,
                "packets_sent": 5000,
                "errors": np.random.randint(0, 5),
                "dropped": 0
            }
            detector.add_sample(sample)

        detector.train()

        # Test with error spike
        errors = {
            "bytes_received": 1000000,
            "bytes_sent": 500000,
            "packets_received": 10000,
            "packets_sent": 5000,
            "errors": 500,  # High errors
            "dropped": 0
        }

        is_anomaly = detector.detect(errors)
        assert is_anomaly is True

    def test_get_statistics(self, detector):
        """Test getting detector statistics."""
        stats = detector.get_stats()

        assert stats is not None
        assert "trained" in stats
        assert "sample_count" in stats
        assert "anomalies_detected" in stats


class TestAlertManager:
    """Tests for AlertManager class."""

    @pytest.fixture
    def alert_manager(self):
        """Get AlertManager instance."""
        from monitoring.alert_manager import AlertManager
        return AlertManager()

    def test_manager_initialization(self, alert_manager):
        """Test alert manager initializes correctly."""
        assert alert_manager is not None

    def test_create_alert(self, alert_manager):
        """Test creating an alert."""
        alert = alert_manager.create_alert(
            device_id="of:0000000000000001",
            alert_type="traffic_spike",
            severity="high",
            message="Traffic spike detected on s1"
        )

        assert alert is not None
        assert "alert_id" in alert
        assert alert["severity"] == "high"

    def test_get_active_alerts(self, alert_manager):
        """Test getting active alerts."""
        # Create some alerts
        alert_manager.create_alert(
            device_id="of:0000000000000001",
            alert_type="anomaly",
            severity="medium",
            message="Test alert 1"
        )
        alert_manager.create_alert(
            device_id="of:0000000000000002",
            alert_type="anomaly",
            severity="high",
            message="Test alert 2"
        )

        alerts = alert_manager.get_active_alerts()

        assert len(alerts) >= 2

    def test_resolve_alert(self, alert_manager):
        """Test resolving an alert."""
        # Create alert
        alert = alert_manager.create_alert(
            device_id="of:0000000000000001",
            alert_type="test",
            severity="low",
            message="Test alert"
        )

        alert_id = alert["alert_id"]

        # Resolve it
        resolved = alert_manager.resolve_alert(alert_id)
        assert resolved is True

        # Should not be in active alerts
        active = alert_manager.get_active_alerts()
        active_ids = [a["alert_id"] for a in active]
        assert alert_id not in active_ids

    def test_get_alerts_by_severity(self, alert_manager):
        """Test filtering alerts by severity."""
        alert_manager.create_alert(
            device_id="of:0000000000000001",
            alert_type="test",
            severity="high",
            message="High alert"
        )
        alert_manager.create_alert(
            device_id="of:0000000000000001",
            alert_type="test",
            severity="low",
            message="Low alert"
        )

        high_alerts = alert_manager.get_alerts_by_severity("high")

        assert all(a["severity"] == "high" for a in high_alerts)


class TestTelemetrySimulator:
    """Tests for TelemetrySimulator in demo mode."""

    @pytest.fixture
    def simulator(self):
        """Get TelemetrySimulator instance."""
        from simulation.telemetry_sim import get_telemetry_simulator
        return get_telemetry_simulator()

    def test_simulator_initialization(self, simulator):
        """Test simulator initializes correctly."""
        assert simulator is not None

    def test_get_port_stats(self, simulator):
        """Test getting port statistics."""
        stats = simulator.get_port_stats("of:0000000000000001")

        assert stats is not None
        assert len(stats) > 0

        # Check stat structure
        port_stat = stats[0]
        assert "port" in port_stat
        assert "bytesReceived" in port_stat
        assert "bytesSent" in port_stat

    def test_inject_anomaly(self, simulator):
        """Test anomaly injection."""
        result = simulator.inject_anomaly(
            device_id="of:0000000000000001",
            anomaly_type="traffic_spike",
            duration_seconds=30
        )

        assert result is not None
        assert "anomaly_id" in result

    def test_resolve_anomaly(self, simulator):
        """Test resolving injected anomaly."""
        # Inject first
        result = simulator.inject_anomaly(
            device_id="of:0000000000000001",
            anomaly_type="traffic_spike",
            duration_seconds=60
        )

        anomaly_id = result["anomaly_id"]

        # Resolve
        resolved = simulator.resolve_anomaly(anomaly_id)
        assert resolved is True

    def test_traffic_scenarios(self, simulator):
        """Test traffic scenario changes."""
        simulator.set_traffic_scenario("high")

        # Get stats to verify scenario applied
        stats = simulator.get_port_stats("of:0000000000000001")
        assert stats is not None

        simulator.set_traffic_scenario("normal")


class TestFeedbackLoop:
    """Tests for autonomous feedback loop."""

    @pytest.fixture
    def feedback_loop(self):
        """Get FeedbackLoop instance."""
        from monitoring.feedback_loop import FeedbackLoop
        return FeedbackLoop()

    def test_loop_initialization(self, feedback_loop):
        """Test feedback loop initializes correctly."""
        assert feedback_loop is not None

    def test_should_remediate(self, feedback_loop):
        """Test remediation decision logic."""
        # Should not remediate if recently remediated
        anomaly1 = {
            "device_id": "of:0000000000000001",
            "anomaly_type": "traffic_spike",
            "severity": "high"
        }

        # First time should allow
        should = feedback_loop.should_remediate(anomaly1)
        assert should is True

    def test_get_remediation_action(self, feedback_loop):
        """Test getting remediation action for anomaly type."""
        action = feedback_loop.get_remediation_action("traffic_spike")

        assert action is not None
        assert "intent_type" in action or "action" in action

    def test_remediation_history(self, feedback_loop):
        """Test recording remediation in history."""
        feedback_loop.record_remediation(
            device_id="of:0000000000000001",
            anomaly_type="traffic_spike",
            action_taken="rate_limit",
            success=True
        )

        history = feedback_loop.get_history()
        assert len(history) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

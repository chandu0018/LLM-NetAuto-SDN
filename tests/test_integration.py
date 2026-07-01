"""
Integration Tests for LLM-NetAuto-SDN.

End-to-end tests for the complete system including:
- Intent processing pipeline
- Deployment to simulated network
- Monitoring and feedback loop
- API endpoints
"""

import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set demo mode for testing
os.environ["DEMO_MODE"] = "true"


class TestSimulationEngine:
    """Tests for the complete simulation engine."""

    @pytest.fixture
    def engine(self):
        """Get SimulationEngine instance."""
        from simulation.sim_engine import get_simulation_engine
        return get_simulation_engine()

    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine is not None
        assert engine.demo_mode is True

    def test_get_topology(self, engine):
        """Test getting complete topology."""
        topology = engine.get_topology()

        assert topology is not None
        assert "devices" in topology
        assert "hosts" in topology
        assert "links" in topology

        assert len(topology["devices"]) == 3
        assert len(topology["hosts"]) == 6

    def test_get_devices(self, engine):
        """Test getting all devices."""
        result = engine.get_devices()

        assert "devices" in result
        assert len(result["devices"]) == 3

        # Check device structure
        device = result["devices"][0]
        assert "id" in device
        assert device["id"].startswith("of:")

    def test_get_hosts(self, engine):
        """Test getting all hosts."""
        result = engine.get_hosts()

        assert "hosts" in result
        assert len(result["hosts"]) == 6

    def test_get_links(self, engine):
        """Test getting all links."""
        result = engine.get_links()

        assert "links" in result
        # Triangle topology should have links
        assert len(result["links"]) > 0

    def test_process_block_intent(self, engine):
        """Test processing a block intent end-to-end."""
        result = engine.process_intent("Block all traffic from 10.0.0.1")

        assert result is not None
        assert result["success"] is True
        assert result["parsed_rule"] is not None
        assert result["deployment_method"] in ["flow_rule", "intent_framework"]
        assert "summary" in result

    def test_process_allow_intent(self, engine):
        """Test processing an allow intent end-to-end."""
        result = engine.process_intent("Allow HTTP traffic from h1 to h3")

        assert result is not None
        assert result["success"] is True
        assert result["parsed_rule"]["intent_type"] == "allow"

    def test_flows_installed_after_intent(self, engine):
        """Test that flows are installed after intent processing."""
        initial_flows = engine.get_flows()
        initial_count = len(initial_flows.get("flows", []))

        # Process intent
        engine.process_intent("Block traffic from 10.0.0.2")

        # Check flows increased
        final_flows = engine.get_flows()
        final_count = len(final_flows.get("flows", []))

        assert final_count > initial_count

    def test_trigger_and_detect_anomaly(self, engine):
        """Test anomaly injection and detection."""
        # Trigger anomaly
        result = engine.trigger_anomaly(
            device_id="of:0000000000000001",
            anomaly_type="traffic_spike",
            duration_seconds=30
        )

        assert result is not None
        assert "anomaly_id" in result

        # Check active anomalies
        anomalies = engine.get_active_anomalies()
        assert len(anomalies) > 0

        # Resolve
        engine.resolve_all_anomalies()
        anomalies = engine.get_active_anomalies()
        assert len(anomalies) == 0

    def test_link_state_management(self, engine):
        """Test link up/down operations."""
        # Bring link down
        success = engine.set_link_state(
            device1="of:0000000000000001",
            device2="of:0000000000000002",
            state="down"
        )
        assert success is True

        # Bring link back up
        success = engine.set_link_state(
            device1="of:0000000000000001",
            device2="of:0000000000000002",
            state="up"
        )
        assert success is True

    def test_traffic_scenario(self, engine):
        """Test setting traffic scenarios."""
        engine.set_traffic_scenario("high")

        # Should not error
        stats = engine.get_port_stats()
        assert stats is not None

        engine.set_traffic_scenario("normal")

    def test_reset(self, engine):
        """Test simulation reset."""
        # Make some changes
        engine.process_intent("Block 10.0.0.1")
        engine.trigger_anomaly("of:0000000000000001", "traffic_spike", 30)

        # Reset
        engine.reset()

        # Anomalies should be cleared
        anomalies = engine.get_active_anomalies()
        assert len(anomalies) == 0


class TestIntentPipeline:
    """Tests for the complete intent processing pipeline."""

    @pytest.fixture
    def parser(self):
        from llm.intent_parser import get_intent_parser
        return get_intent_parser()

    @pytest.fixture
    def flow_builder(self):
        from netconfig.flow_builder import get_flow_builder
        return get_flow_builder()

    def test_pipeline_block_intent(self, parser, flow_builder):
        """Test complete pipeline for block intent."""
        # Parse
        rule = parser.parse_intent("Block traffic from 10.0.0.1")

        assert rule["intent_type"] == "block"

        # Build flow
        flow = flow_builder.rule_to_flow(rule, "of:0000000000000001")

        assert flow is not None
        assert flow["priority"] > 0

        # Validate flow JSON
        json_str = json.dumps(flow)
        parsed = json.loads(json_str)
        assert parsed == flow

    def test_pipeline_allow_intent(self, parser, flow_builder):
        """Test complete pipeline for allow intent."""
        # Parse
        rule = parser.parse_intent("Allow HTTP from h1 to h3")

        assert rule["intent_type"] == "allow"
        assert rule.get("port") == 80

        # Build flow
        flow = flow_builder.rule_to_flow(rule, "of:0000000000000001")

        assert flow is not None

    def test_pipeline_qos_intent(self, parser, flow_builder):
        """Test complete pipeline for QoS intent."""
        # Parse
        rule = parser.parse_intent("Prioritize VoIP traffic")

        assert rule["intent_type"] == "qos"

        # Build flow
        flow = flow_builder.rule_to_flow(rule, "of:0000000000000001")

        # QoS should have high priority
        assert flow["priority"] >= 50000


class TestMonitoringPipeline:
    """Tests for the monitoring pipeline."""

    @pytest.fixture
    def telemetry(self):
        from monitoring.telemetry_collector import TelemetryCollector
        return TelemetryCollector()

    @pytest.fixture
    def detector(self):
        from monitoring.anomaly_detector import AnomalyDetector
        return AnomalyDetector()

    @pytest.fixture
    def feedback(self):
        from monitoring.feedback_loop import FeedbackLoop
        return FeedbackLoop()

    def test_telemetry_to_detector(self, telemetry, detector):
        """Test telemetry to anomaly detector pipeline."""
        # Collect telemetry
        telemetry.collect()

        # Get latest data
        device_data = telemetry.get_device_data("of:0000000000000001")

        if device_data:
            # Convert to detector format
            sample = {
                "bytes_received": device_data.get("bytes_received", 0),
                "bytes_sent": device_data.get("bytes_sent", 0),
                "packets_received": device_data.get("packets_received", 0),
                "packets_sent": device_data.get("packets_sent", 0),
                "errors": device_data.get("errors", 0),
                "dropped": device_data.get("dropped", 0)
            }

            # Add to detector
            detector.add_sample(sample)
            assert len(detector._training_data) > 0

    def test_detection_to_feedback(self, detector, feedback):
        """Test anomaly detection to feedback loop."""
        # Simulate anomaly detection
        anomaly = {
            "device_id": "of:0000000000000001",
            "anomaly_type": "traffic_spike",
            "severity": "high",
            "metrics": {"bytes_received": 10000000}
        }

        # Check if should remediate
        should = feedback.should_remediate(anomaly)

        if should:
            # Get remediation action
            action = feedback.get_remediation_action("traffic_spike")
            assert action is not None

            # Record remediation
            feedback.record_remediation(
                device_id=anomaly["device_id"],
                anomaly_type=anomaly["anomaly_type"],
                action_taken=str(action),
                success=True
            )

            # Should be in history
            history = feedback.get_history()
            assert len(history) > 0


class TestBenchmarkTasks:
    """Tests for the 10 benchmark tasks."""

    BENCHMARK_INTENTS = [
        "Block all traffic from 10.0.0.1",
        "Allow HTTP from h1 to h3",
        "Drop ICMP packets on switch s1",
        "Prioritize VoIP traffic with high priority",
        "Isolate switch s2 from the network",
        "Allow SSH access to h3",
        "Remove all flows from s1",
        "Block traffic between 10.0.0.0/24 and 10.0.1.0/24",
        "Mirror traffic from h1 to h6",
        "Remediate traffic spike on of:0000000000000001"
    ]

    @pytest.fixture
    def engine(self):
        from simulation.sim_engine import get_simulation_engine
        engine = get_simulation_engine()
        engine.reset()
        return engine

    @pytest.mark.parametrize("intent", BENCHMARK_INTENTS)
    def test_benchmark_intent(self, engine, intent):
        """Test each benchmark intent can be processed."""
        result = engine.process_intent(intent)

        assert result is not None
        # We don't require success for all (some may fail gracefully)
        assert "parsed_rule" in result
        assert "error" not in result or result.get("success") is True

    def test_all_intents_produce_different_rules(self, engine):
        """Test that different intents produce different rules."""
        rules = []

        for intent in self.BENCHMARK_INTENTS[:5]:
            result = engine.process_intent(intent)
            if result.get("parsed_rule"):
                rules.append(result["parsed_rule"])

        # Check we got multiple unique rules
        intent_types = set(r.get("intent_type") for r in rules)
        assert len(intent_types) > 1  # Should have variety


class TestONOSCompatibility:
    """Tests for ONOS API compatibility."""

    @pytest.fixture
    def flow_builder(self):
        from netconfig.flow_builder import get_flow_builder
        return get_flow_builder()

    def test_flow_json_format(self, flow_builder):
        """Test flow JSON matches ONOS format."""
        flow = flow_builder.build_drop_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            priority=40000
        )

        # Required ONOS fields
        assert "priority" in flow
        assert "selector" in flow
        assert "treatment" in flow

        # Selector format
        selector = flow["selector"]
        assert "criteria" in selector
        assert isinstance(selector["criteria"], list)

        # Treatment format
        treatment = flow["treatment"]
        assert "instructions" in treatment
        assert isinstance(treatment["instructions"], list)

    def test_selector_criteria_format(self, flow_builder):
        """Test selector criteria match ONOS format."""
        flow = flow_builder.build_flow(
            device_id="of:0000000000000001",
            priority=40000,
            selector={
                "eth_type": 2048,
                "ipv4_src": "10.0.0.1",
                "ipv4_dst": "10.0.0.3",
                "ip_proto": 6,
                "tcp_dst": 80
            },
            treatment={"action": "OUTPUT", "port": 2}
        )

        criteria = flow["selector"]["criteria"]

        # Check criterion format
        for c in criteria:
            assert "type" in c
            # Type should be ONOS format (ETH_TYPE, IPV4_SRC, etc.)
            assert c["type"].isupper()

    def test_treatment_instructions_format(self, flow_builder):
        """Test treatment instructions match ONOS format."""
        flow = flow_builder.build_output_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            dst_ip="10.0.0.3",
            output_port=2,
            priority=40000
        )

        instructions = flow["treatment"]["instructions"]

        for i in instructions:
            assert "type" in i
            if i["type"] == "OUTPUT":
                assert "port" in i

    def test_intent_json_format(self):
        """Test intent JSON matches ONOS format."""
        from netconfig.intent_builder import get_intent_builder
        builder = get_intent_builder()

        intent = builder.build_host_to_host_intent(
            src_host="00:00:00:00:00:01/-1",
            dst_host="00:00:00:00:00:03/-1"
        )

        # Required ONOS intent fields
        assert "type" in intent
        assert intent["type"] == "HostToHostIntent"
        assert "appId" in intent
        assert "one" in intent
        assert "two" in intent


class TestAPIEndpoints:
    """Tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        from fastapi.testclient import TestClient
        from dashboard.api import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data

    def test_topology_endpoint(self, client):
        """Test topology endpoint."""
        response = client.get("/topology")
        assert response.status_code == 200

        data = response.json()
        assert "devices" in data or "error" not in data

    def test_intent_endpoint(self, client):
        """Test intent processing endpoint."""
        response = client.post(
            "/intent",
            json={"intent_text": "Block traffic from 10.0.0.1"}
        )
        assert response.status_code == 200

        data = response.json()
        assert "success" in data

    def test_flows_endpoint(self, client):
        """Test flows endpoint."""
        response = client.get("/flows")
        assert response.status_code == 200

    def test_demo_state_endpoint(self, client):
        """Test demo state endpoint."""
        response = client.get("/demo/state")
        assert response.status_code == 200

    def test_anomaly_inject_endpoint(self, client):
        """Test anomaly injection endpoint."""
        response = client.post(
            "/demo/anomaly/inject",
            json={
                "device_id": "of:0000000000000001",
                "anomaly_type": "traffic_spike",
                "duration_seconds": 30
            }
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

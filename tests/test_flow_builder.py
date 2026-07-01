"""
Tests for Flow Builder Module.

Tests the ONOS flow rule JSON generation including:
- Selector building
- Treatment building
- Complete flow assembly
- Intent building
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set demo mode for testing
os.environ["DEMO_MODE"] = "true"


class TestFlowBuilder:
    """Tests for FlowBuilder class."""

    @pytest.fixture
    def builder(self):
        """Get FlowBuilder instance."""
        from netconfig.flow_builder import get_flow_builder
        return get_flow_builder()

    def test_builder_initialization(self, builder):
        """Test builder initializes correctly."""
        assert builder is not None

    def test_build_basic_flow(self, builder):
        """Test building a basic flow rule."""
        flow = builder.build_flow(
            device_id="of:0000000000000001",
            priority=40000,
            selector={"ipv4_src": "10.0.0.1"},
            treatment={"action": "DROP"}
        )

        assert flow is not None
        assert "priority" in flow
        assert flow["priority"] == 40000
        assert "selector" in flow
        assert "treatment" in flow

    def test_build_drop_flow(self, builder):
        """Test building a DROP flow."""
        flow = builder.build_drop_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            priority=40000
        )

        assert flow is not None
        assert flow["priority"] == 40000

        # Check selector has IPV4_SRC
        selector = flow.get("selector", {})
        criteria = selector.get("criteria", [])

        has_ipv4_src = any(
            c.get("type") == "IPV4_SRC"
            for c in criteria
        )
        assert has_ipv4_src

        # Check treatment is empty (DROP)
        treatment = flow.get("treatment", {})
        instructions = treatment.get("instructions", [])
        # DROP has no instructions
        assert len(instructions) == 0 or instructions == []

    def test_build_output_flow(self, builder):
        """Test building an OUTPUT flow."""
        flow = builder.build_output_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            dst_ip="10.0.0.3",
            output_port=2,
            priority=40000
        )

        assert flow is not None

        # Check treatment has OUTPUT
        treatment = flow.get("treatment", {})
        instructions = treatment.get("instructions", [])

        has_output = any(
            i.get("type") == "OUTPUT"
            for i in instructions
        )
        assert has_output

    def test_build_tcp_flow(self, builder):
        """Test building TCP protocol flow."""
        flow = builder.build_flow(
            device_id="of:0000000000000001",
            priority=40000,
            selector={
                "ipv4_src": "10.0.0.1",
                "ipv4_dst": "10.0.0.3",
                "ip_proto": 6,
                "tcp_dst": 80
            },
            treatment={"action": "OUTPUT", "port": 2}
        )

        assert flow is not None

        # Verify TCP criteria
        selector = flow.get("selector", {})
        criteria = selector.get("criteria", [])

        has_tcp_proto = any(
            c.get("type") == "IP_PROTO" and c.get("protocol") == 6
            for c in criteria
        )
        has_tcp_port = any(
            c.get("type") == "TCP_DST"
            for c in criteria
        )

        assert has_tcp_proto
        assert has_tcp_port

    def test_build_udp_flow(self, builder):
        """Test building UDP protocol flow."""
        flow = builder.build_flow(
            device_id="of:0000000000000001",
            priority=40000,
            selector={
                "ip_proto": 17,
                "udp_dst": 5060
            },
            treatment={"action": "OUTPUT", "port": "NORMAL"}
        )

        assert flow is not None

        selector = flow.get("selector", {})
        criteria = selector.get("criteria", [])

        has_udp_proto = any(
            c.get("type") == "IP_PROTO" and c.get("protocol") == 17
            for c in criteria
        )
        assert has_udp_proto

    def test_build_icmp_flow(self, builder):
        """Test building ICMP protocol flow."""
        flow = builder.build_flow(
            device_id="of:0000000000000001",
            priority=40000,
            selector={"ip_proto": 1},
            treatment={"action": "DROP"}
        )

        assert flow is not None

        selector = flow.get("selector", {})
        criteria = selector.get("criteria", [])

        has_icmp_proto = any(
            c.get("type") == "IP_PROTO" and c.get("protocol") == 1
            for c in criteria
        )
        assert has_icmp_proto

    def test_build_selector(self, builder):
        """Test selector building directly."""
        selector = builder.build_selector(
            eth_type=2048,
            ipv4_src="10.0.0.1",
            ipv4_dst="10.0.0.3"
        )

        assert selector is not None
        assert "criteria" in selector

        criteria = selector["criteria"]
        assert len(criteria) >= 2

    def test_build_treatment_drop(self, builder):
        """Test DROP treatment building."""
        treatment = builder.build_treatment(action="DROP")

        assert treatment is not None
        assert "instructions" in treatment
        # DROP has empty instructions
        assert treatment["instructions"] == []

    def test_build_treatment_output(self, builder):
        """Test OUTPUT treatment building."""
        treatment = builder.build_treatment(action="OUTPUT", port=2)

        assert treatment is not None
        assert "instructions" in treatment

        has_output = any(
            i.get("type") == "OUTPUT"
            for i in treatment["instructions"]
        )
        assert has_output

    def test_build_treatment_controller(self, builder):
        """Test CONTROLLER treatment building."""
        treatment = builder.build_treatment(action="CONTROLLER")

        assert treatment is not None

        has_controller = any(
            i.get("type") == "OUTPUT" and i.get("port") == "CONTROLLER"
            for i in treatment["instructions"]
        )
        assert has_controller

    def test_flow_has_required_fields(self, builder):
        """Test that flows have all required ONOS fields."""
        flow = builder.build_drop_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            priority=40000
        )

        required_fields = ["priority", "selector", "treatment"]
        for field in required_fields:
            assert field in flow, f"Missing required field: {field}"

    def test_flow_app_id_present(self, builder):
        """Test that flows have appId."""
        flow = builder.build_drop_flow(
            device_id="of:0000000000000001",
            src_ip="10.0.0.1",
            priority=40000
        )

        assert "appId" in flow
        assert flow["appId"] is not None


class TestIntentBuilder:
    """Tests for IntentBuilder class."""

    @pytest.fixture
    def builder(self):
        """Get IntentBuilder instance."""
        from netconfig.intent_builder import get_intent_builder
        return get_intent_builder()

    def test_builder_initialization(self, builder):
        """Test builder initializes correctly."""
        assert builder is not None

    def test_build_host_to_host_intent(self, builder):
        """Test building HostToHostIntent."""
        intent = builder.build_host_to_host_intent(
            src_host="00:00:00:00:00:01/-1",
            dst_host="00:00:00:00:00:03/-1",
            priority=100
        )

        assert intent is not None
        assert intent.get("type") == "HostToHostIntent"
        assert "one" in intent
        assert "two" in intent

    def test_build_point_to_point_intent(self, builder):
        """Test building PointToPointIntent."""
        intent = builder.build_point_to_point_intent(
            ingress_device="of:0000000000000001",
            ingress_port=1,
            egress_device="of:0000000000000002",
            egress_port=2
        )

        assert intent is not None
        assert intent.get("type") == "PointToPointIntent"
        assert "ingressPoint" in intent
        assert "egressPoint" in intent

    def test_build_multi_point_intent(self, builder):
        """Test building MultiPointToSinglePointIntent."""
        intent = builder.build_multi_point_intent(
            ingress_points=[
                {"device": "of:0000000000000001", "port": 1},
                {"device": "of:0000000000000002", "port": 1}
            ],
            egress_device="of:0000000000000003",
            egress_port=1
        )

        assert intent is not None

    def test_intent_has_app_id(self, builder):
        """Test that intents have appId."""
        intent = builder.build_host_to_host_intent(
            src_host="00:00:00:00:00:01/-1",
            dst_host="00:00:00:00:00:03/-1"
        )

        assert "appId" in intent

    def test_intent_has_key(self, builder):
        """Test that intents have unique key."""
        intent = builder.build_host_to_host_intent(
            src_host="00:00:00:00:00:01/-1",
            dst_host="00:00:00:00:00:03/-1"
        )

        assert "key" in intent
        assert intent["key"] is not None


class TestRuleToFlow:
    """Tests for converting parsed rules to flows."""

    @pytest.fixture
    def builder(self):
        from netconfig.flow_builder import get_flow_builder
        return get_flow_builder()

    def test_rule_to_flow_block(self, builder):
        """Test converting block rule to flow."""
        rule = {
            "intent_type": "block",
            "src_host": "10.0.0.1",
            "action": "DROP",
            "priority": 40000
        }

        flow = builder.rule_to_flow(rule, "of:0000000000000001")

        assert flow is not None
        assert flow["priority"] == 40000

    def test_rule_to_flow_allow(self, builder):
        """Test converting allow rule to flow."""
        rule = {
            "intent_type": "allow",
            "src_host": "10.0.0.1",
            "dst_host": "10.0.0.3",
            "protocol": "tcp",
            "port": 80,
            "action": "OUTPUT",
            "priority": 40000
        }

        flow = builder.rule_to_flow(rule, "of:0000000000000001")

        assert flow is not None

        # Should have OUTPUT treatment
        treatment = flow.get("treatment", {})
        instructions = treatment.get("instructions", [])
        assert len(instructions) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

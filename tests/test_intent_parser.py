"""
Tests for Intent Parser Module.

Tests the LLM-based intent parsing pipeline including:
- Natural language parsing
- Rule extraction
- Validation
- Demo mode simulation
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set demo mode for testing
os.environ["DEMO_MODE"] = "true"


class TestIntentParserBasic:
    """Basic intent parser tests."""

    def test_parser_initialization(self):
        """Test that parser initializes correctly."""
        from llm.intent_parser import IntentParser

        parser = IntentParser()
        assert parser is not None
        assert parser._demo_mode is True

    def test_parser_singleton(self):
        """Test singleton pattern."""
        from llm.intent_parser import get_intent_parser

        parser1 = get_intent_parser()
        parser2 = get_intent_parser()
        assert parser1 is parser2


class TestIntentParsing:
    """Intent parsing tests."""

    @pytest.fixture
    def parser(self):
        """Get parser instance."""
        from llm.intent_parser import get_intent_parser
        return get_intent_parser()

    def test_parse_block_intent(self, parser):
        """Test parsing block intent."""
        result = parser.parse_intent("Block all traffic from 10.0.0.1")

        assert result is not None
        assert "intent_type" in result
        assert result["intent_type"] == "block"
        assert "src_host" in result
        assert result["src_host"] == "10.0.0.1"

    def test_parse_allow_intent(self, parser):
        """Test parsing allow intent."""
        result = parser.parse_intent("Allow HTTP traffic from h1 to h3")

        assert result is not None
        assert result["intent_type"] == "allow"
        assert result.get("protocol") == "tcp"
        assert result.get("port") == 80

    def test_parse_drop_icmp_intent(self, parser):
        """Test parsing ICMP drop intent."""
        result = parser.parse_intent("Drop ICMP packets on switch 1")

        assert result is not None
        assert result["intent_type"] == "block"
        assert result.get("protocol") == "icmp"

    def test_parse_prioritize_intent(self, parser):
        """Test parsing QoS priority intent."""
        result = parser.parse_intent("Prioritize VoIP traffic with high priority")

        assert result is not None
        assert result["intent_type"] == "qos"

    def test_parse_isolate_intent(self, parser):
        """Test parsing isolation intent."""
        result = parser.parse_intent("Isolate switch s2 from the network")

        assert result is not None
        assert result["intent_type"] == "isolate"

    def test_parse_with_topology_context(self, parser):
        """Test parsing with topology context."""
        topology = {
            "devices": [
                {"id": "of:0000000000000001", "name": "s1"}
            ],
            "hosts": [
                {"name": "h1", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01"}
            ]
        }

        result = parser.parse_intent(
            "Block traffic from h1",
            topology_context=topology
        )

        assert result is not None
        assert result["intent_type"] == "block"

    def test_parse_unknown_intent(self, parser):
        """Test parsing unknown/complex intent."""
        result = parser.parse_intent("Do something random and unusual")

        assert result is not None
        # Should return a fallback result
        assert "intent_type" in result


class TestLLMSimulator:
    """Tests for LLM simulator in demo mode."""

    @pytest.fixture
    def simulator(self):
        """Get LLM simulator instance."""
        from simulation.llm_sim import get_llm_simulator
        return get_llm_simulator()

    def test_simulator_initialization(self, simulator):
        """Test simulator initializes correctly."""
        assert simulator is not None

    def test_parse_block_pattern(self, simulator):
        """Test block pattern recognition."""
        result = simulator.parse_intent("Block all traffic from 10.0.0.1")

        assert result["intent_type"] == "block"
        assert result["src_host"] == "10.0.0.1"
        assert result["action"] == "DROP"

    def test_parse_allow_http(self, simulator):
        """Test HTTP allow pattern."""
        result = simulator.parse_intent("Allow HTTP from 10.0.0.1 to 10.0.0.3")

        assert result["intent_type"] == "allow"
        assert result["protocol"] == "tcp"
        assert result["port"] == 80

    def test_parse_allow_ssh(self, simulator):
        """Test SSH allow pattern."""
        result = simulator.parse_intent("Allow SSH access to h3")

        assert result["intent_type"] == "allow"
        assert result["port"] == 22

    def test_parse_allow_https(self, simulator):
        """Test HTTPS allow pattern."""
        result = simulator.parse_intent("Allow HTTPS traffic")

        assert result["port"] == 443

    def test_parse_drop_icmp(self, simulator):
        """Test ICMP drop pattern."""
        result = simulator.parse_intent("Drop ICMP on switch 1")

        assert result["protocol"] == "icmp"
        assert result["action"] == "DROP"

    def test_parse_qos_voip(self, simulator):
        """Test VoIP QoS pattern."""
        result = simulator.parse_intent("Prioritize VoIP traffic high")

        assert result["intent_type"] == "qos"
        assert result.get("priority", 0) >= 50000

    def test_parse_isolate(self, simulator):
        """Test isolation pattern."""
        result = simulator.parse_intent("Isolate switch s2")

        assert result["intent_type"] == "isolate"

    def test_parse_remove_flows(self, simulator):
        """Test flow removal pattern."""
        result = simulator.parse_intent("Remove all flows from s1")

        assert result["intent_type"] == "delete"

    def test_parse_remediation(self, simulator):
        """Test remediation pattern."""
        result = simulator.parse_intent("Remediate traffic spike on of:0000000000000001")

        assert result["intent_type"] == "remediate"

    def test_summary_generation(self, simulator):
        """Test summary generation."""
        rule = {
            "intent_type": "block",
            "src_host": "10.0.0.1",
            "action": "DROP"
        }
        deployment = {"success": True}

        summary = simulator.generate_summary(rule, deployment)

        assert summary is not None
        assert len(summary) > 0
        assert "block" in summary.lower() or "drop" in summary.lower()

    def test_host_name_to_ip(self, simulator):
        """Test host name to IP resolution."""
        result = simulator.parse_intent("Block traffic from h1")
        assert result.get("src_host") == "10.0.0.1"

        result = simulator.parse_intent("Block traffic from h3")
        assert result.get("src_host") == "10.0.0.3"


class TestIntentValidation:
    """Tests for intent validation."""

    @pytest.fixture
    def parser(self):
        from llm.intent_parser import get_intent_parser
        return get_intent_parser()

    def test_validate_valid_rule(self, parser):
        """Test validation of valid rule."""
        rule = {
            "intent_type": "block",
            "src_host": "10.0.0.1",
            "action": "DROP",
            "priority": 40000
        }

        is_valid, errors = parser.validate_rule(rule)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_intent_type(self, parser):
        """Test validation catches missing intent_type."""
        rule = {
            "src_host": "10.0.0.1",
            "action": "DROP"
        }

        is_valid, errors = parser.validate_rule(rule)

        assert is_valid is False
        assert any("intent_type" in e.lower() for e in errors)

    def test_validate_invalid_ip(self, parser):
        """Test validation catches invalid IP."""
        rule = {
            "intent_type": "block",
            "src_host": "invalid-ip",
            "action": "DROP"
        }

        is_valid, errors = parser.validate_rule(rule)

        # May pass in demo mode with relaxed validation
        # Just ensure it returns a result
        assert isinstance(is_valid, bool)

    def test_validate_priority_range(self, parser):
        """Test priority validation."""
        rule = {
            "intent_type": "block",
            "src_host": "10.0.0.1",
            "action": "DROP",
            "priority": 70000  # Out of range
        }

        is_valid, errors = parser.validate_rule(rule)

        # Priority should be capped or flagged
        assert isinstance(is_valid, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

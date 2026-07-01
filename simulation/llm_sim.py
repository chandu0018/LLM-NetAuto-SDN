"""
LLM Simulator for LLM-NetAuto-SDN.

Rule-based intent parser that simulates LLM behavior.
No external LLM service required for demo mode.
"""

import os
import re
import time
import random
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class LLMSimulator:
    """
    Rule-based LLM simulator for demo mode.

    Provides pattern matching-based intent parsing that
    mimics LLM behavior without requiring Ollama.
    """

    # Host name to details mapping
    HOST_MAP = {
        "h1": {"ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "device": "of:0000000000000001", "port": 1},
        "h2": {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "device": "of:0000000000000001", "port": 2},
        "h3": {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "device": "of:0000000000000002", "port": 1},
        "h4": {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "device": "of:0000000000000002", "port": 2},
        "h5": {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "device": "of:0000000000000003", "port": 1},
        "h6": {"ip": "10.0.0.6", "mac": "00:00:00:00:00:06", "device": "of:0000000000000003", "port": 2},
    }

    # Switch name to device ID mapping
    SWITCH_MAP = {
        "s1": "of:0000000000000001",
        "s2": "of:0000000000000002",
        "s3": "of:0000000000000003",
    }

    # Protocol patterns
    PROTOCOL_PATTERNS = {
        r"\bhttp\b": ("tcp", 80),
        r"\bhttps\b": ("tcp", 443),
        r"\bssh\b": ("tcp", 22),
        r"\btelnet\b": ("tcp", 23),
        r"\bftp\b": ("tcp", 21),
        r"\bdns\b": ("udp", 53),
        r"\bdhcp\b": ("udp", 67),
        r"\bvoip\b": ("udp", 5060),
        r"\bsip\b": ("udp", 5060),
        r"\brtp\b": ("udp", 5004),
        r"\bicmp\b": ("icmp", None),
        r"\bping\b": ("icmp", None),
        r"\btcp\b": ("tcp", None),
        r"\budp\b": ("udp", None),
    }

    def __init__(self):
        """Initialize LLM simulator."""
        self._min_delay = int(os.getenv("SIM_LLM_MIN_DELAY_MS", "800"))
        self._max_delay = int(os.getenv("SIM_LLM_MAX_DELAY_MS", "2500"))
        logger.info("LLMSimulator initialized")

    def invoke(self, prompt: str) -> str:
        """
        Simulate LLM invocation.

        Args:
            prompt: Input prompt

        Returns:
            Simulated response
        """
        # Simulate processing latency
        self._simulate_latency()

        # Try to detect what kind of response is expected
        if "parse" in prompt.lower() or "intent" in prompt.lower():
            return self._generate_parse_response(prompt)
        elif "validate" in prompt.lower():
            return self._generate_validation_response(prompt)
        elif "summar" in prompt.lower():
            return self._generate_summary_response(prompt)
        elif "remediat" in prompt.lower():
            return self._generate_remediation_response(prompt)
        else:
            return self._generate_default_response(prompt)

    def parse_intent(self, intent: str) -> Dict[str, Any]:
        """
        Parse natural language intent to structured rule.

        Args:
            intent: Natural language intent

        Returns:
            Parsed rule dictionary
        """
        self._simulate_latency()

        intent_lower = intent.lower()

        # Default rule structure
        rule = {
            "intent_type": "allow",
            "action": "add",
            "src_host": None,
            "dst_host": None,
            "src_device": None,
            "dst_device": None,
            "in_port": None,
            "out_port": None,
            "protocol": None,
            "port": None,
            "priority": 40000,
            "bandwidth_limit_mbps": None,
            "use_intent_framework": False,
            "target_all_switches": False,
            "vlan_id": None,
            "eth_type": "0x0800",
            "ip_proto": None,
            "queue_id": None
        }

        # Detect intent type
        if self._contains_any(intent_lower, ["block", "drop", "deny", "reject"]):
            rule["intent_type"] = "block"
            rule["priority"] = 50000
        elif self._contains_any(intent_lower, ["allow", "permit", "accept"]):
            rule["intent_type"] = "allow"
            rule["priority"] = 40000
        elif self._contains_any(intent_lower, ["prioritize", "priority", "qos"]):
            rule["intent_type"] = "prioritize"
            rule["priority"] = 60000
            rule["queue_id"] = 1
        elif self._contains_any(intent_lower, ["isolate", "quarantine"]):
            rule["intent_type"] = "isolate"
            rule["priority"] = 65000
        elif self._contains_any(intent_lower, ["mirror", "monitor", "copy"]):
            rule["intent_type"] = "mirror"
            rule["priority"] = 30000
            rule["out_port"] = 5
        elif self._contains_any(intent_lower, ["rate", "limit", "throttle", "bandwidth"]):
            rule["intent_type"] = "rate_limit"
            rule["priority"] = 45000
            # Extract rate limit value
            rate_match = re.search(r"(\d+)\s*(?:mbps|mb|mbit)", intent_lower)
            if rate_match:
                rule["bandwidth_limit_mbps"] = int(rate_match.group(1))
            else:
                rule["bandwidth_limit_mbps"] = 10
        elif self._contains_any(intent_lower, ["reroute", "redirect", "forward"]):
            rule["intent_type"] = "reroute"
            rule["priority"] = 55000

        # Detect action
        if self._contains_any(intent_lower, ["remove", "delete", "clear", "revoke"]):
            rule["action"] = "remove"

        # Extract source/destination hosts
        rule["src_host"], rule["dst_host"] = self._extract_hosts(intent_lower)

        # Extract protocol and port
        rule["protocol"], rule["port"] = self._extract_protocol(intent_lower)

        # Set IP proto
        if rule["protocol"] == "icmp":
            rule["ip_proto"] = 1
        elif rule["protocol"] == "tcp":
            rule["ip_proto"] = 6
        elif rule["protocol"] == "udp":
            rule["ip_proto"] = 17

        # Extract devices
        rule["src_device"], rule["dst_device"] = self._extract_devices(intent_lower)

        # Determine if should target all switches
        if self._contains_any(intent_lower, ["all switch", "every switch", "all devices", "network wide"]):
            rule["target_all_switches"] = True

        # Determine if should use intent framework
        # Use intent framework for:
        # 1. Host-to-host intents (allow, reroute)
        # 2. Block/Isolate intents with hosts
        # 3. Prioritize intents with hosts
        intent_type = rule.get("intent_type")
        src_host = rule.get("src_host")
        dst_host = rule.get("dst_host")
        
        if intent_type in ["allow", "reroute"] and src_host and dst_host and not rule.get("src_device"):
            # Standard host-to-host intents
            rule["use_intent_framework"] = True
        elif intent_type in ["block", "isolate"] and src_host:
            # Block/isolate intents with at least a source
            rule["use_intent_framework"] = True
        elif intent_type == "prioritize" and src_host and dst_host:
            # Prioritize intents with both source and destination
            rule["use_intent_framework"] = True

        return rule

    def generate_remediation(
        self,
        anomaly: Dict[str, Any],
        current_flows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate remediation action for an anomaly.

        Args:
            anomaly: Anomaly details
            current_flows: Current flows on device

        Returns:
            Remediation action with rule
        """
        self._simulate_latency()

        anomaly_type = anomaly.get("type", "unknown")
        device_id = anomaly.get("device_id", "of:0000000000000001")

        # Map anomaly type to remediation action
        remediations = {
            "traffic_spike": {
                "action_type": "rate_limit",
                "rule": {
                    "intent_type": "rate_limit",
                    "action": "add",
                    "src_device": device_id,
                    "bandwidth_limit_mbps": 50,
                    "priority": 55000,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Rate limiting to reduce traffic spike impact",
                "expected_outcome": "Traffic reduced to 50 Mbps limit",
                "rollback_after_seconds": 300
            },
            "ddos_sim": {
                "action_type": "block",
                "rule": {
                    "intent_type": "block",
                    "action": "add",
                    "src_device": device_id,
                    "in_port": 1,
                    "priority": 60000,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Blocking suspicious high-volume traffic",
                "expected_outcome": "DDoS traffic blocked at ingress",
                "rollback_after_seconds": 600
            },
            "packet_drop": {
                "action_type": "prioritize",
                "rule": {
                    "intent_type": "prioritize",
                    "action": "add",
                    "src_device": device_id,
                    "priority": 60000,
                    "queue_id": 0,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Prioritizing traffic to reduce drops",
                "expected_outcome": "Important traffic prioritized",
                "rollback_after_seconds": 180
            },
            "bandwidth_hog": {
                "action_type": "rate_limit",
                "rule": {
                    "intent_type": "rate_limit",
                    "action": "add",
                    "src_device": device_id,
                    "in_port": 1,
                    "bandwidth_limit_mbps": 20,
                    "priority": 55000,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Limiting bandwidth hog to ensure fair share",
                "expected_outcome": "Traffic from source limited to 20 Mbps",
                "rollback_after_seconds": 300
            },
            "port_flap": {
                "action_type": "isolate",
                "rule": {
                    "intent_type": "isolate",
                    "action": "add",
                    "src_device": device_id,
                    "in_port": 3,
                    "priority": 65000,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Isolating flapping port to prevent instability",
                "expected_outcome": "Flapping port isolated from network",
                "rollback_after_seconds": 120
            }
        }

        return remediations.get(anomaly_type, {
            "action_type": "rate_limit",
            "rule": {
                "intent_type": "rate_limit",
                "action": "add",
                "src_device": device_id,
                "bandwidth_limit_mbps": 50,
                "priority": 55000
            },
            "reason": f"Default remediation for {anomaly_type}",
            "expected_outcome": "Traffic normalized",
            "rollback_after_seconds": 300
        })

    def generate_summary(
        self,
        rule: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        """
        Generate plain English summary.

        Args:
            rule: Applied rule
            result: Deployment result

        Returns:
            Summary string
        """
        intent_type = rule.get("intent_type", "configure")
        action = rule.get("action", "add")
        src = rule.get("src_host") or rule.get("src_device") or "any"
        dst = rule.get("dst_host") or rule.get("dst_device") or "any"
        protocol = rule.get("protocol") or "all traffic"
        success = result.get("success", False)

        status = "has been" if success else "could not be"

        if intent_type == "block":
            if rule.get("target_all_switches"):
                return (
                    f"All traffic from {src} ({protocol}) {status} blocked "
                    f"across all switches in the network."
                )
            return f"Traffic from {src} to {dst} ({protocol}) {status} blocked."

        elif intent_type == "allow":
            port = rule.get("port")
            port_str = f" port {port}" if port else ""
            return (
                f"{protocol.upper()}{port_str} traffic from {src} to {dst} "
                f"{status} allowed."
            )

        elif intent_type == "prioritize":
            return (
                f"Traffic from {src} to {dst} {status} prioritized "
                f"with queue {rule.get('queue_id', 1)}."
            )

        elif intent_type == "isolate":
            return f"Device {src} {status} isolated from the network."

        elif intent_type == "mirror":
            return (
                f"Traffic on {src} {status} mirrored to "
                f"port {rule.get('out_port', 5)} for monitoring."
            )

        elif intent_type == "rate_limit":
            limit = rule.get("bandwidth_limit_mbps", 10)
            return f"Traffic from {src} {status} rate-limited to {limit} Mbps."

        elif intent_type == "reroute":
            return f"Traffic from {src} to {dst} {status} rerouted."

        else:
            return f"Network rule {status} configured."

    # ==========================================
    # Private Helper Methods
    # ==========================================

    def _simulate_latency(self) -> None:
        """Simulate LLM processing latency."""
        delay_ms = random.randint(self._min_delay, self._max_delay)
        time.sleep(delay_ms / 1000.0)

    def _contains_any(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords."""
        return any(kw in text for kw in keywords)

    def _extract_hosts(self, intent: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract source and destination hosts from intent."""
        src_host = None
        dst_host = None

        # Check for host names
        for host_name in self.HOST_MAP.keys():
            if host_name in intent:
                host_info = self.HOST_MAP[host_name]
                # Determine if source or destination based on position
                if "from" in intent:
                    from_idx = intent.find("from")
                    host_idx = intent.find(host_name)
                    if host_idx > from_idx and (src_host is None or host_idx < intent.find(src_host)):
                        src_host = host_info["ip"]
                    elif "to" in intent:
                        to_idx = intent.find("to")
                        if host_idx > to_idx:
                            dst_host = host_info["ip"]

                if src_host is None:
                    src_host = host_info["ip"]
                elif dst_host is None and host_info["ip"] != src_host:
                    dst_host = host_info["ip"]

        # Check for IP addresses
        ip_pattern = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
        ips = re.findall(ip_pattern, intent)
        for ip in ips:
            if src_host is None:
                src_host = ip
            elif dst_host is None and ip != src_host:
                dst_host = ip

        return src_host, dst_host

    def _extract_devices(self, intent: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract device IDs from intent."""
        src_device = None
        dst_device = None

        # Check for switch names
        for switch_name, device_id in self.SWITCH_MAP.items():
            if switch_name in intent:
                if src_device is None:
                    src_device = device_id
                elif dst_device is None:
                    dst_device = device_id

        # Check for device IDs directly
        device_pattern = r"of:\w+"
        devices = re.findall(device_pattern, intent)
        for device in devices:
            if src_device is None:
                src_device = device
            elif dst_device is None:
                dst_device = device

        return src_device, dst_device

    def _extract_protocol(self, intent: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract protocol and port from intent."""
        # Check protocol patterns
        for pattern, (protocol, port) in self.PROTOCOL_PATTERNS.items():
            if re.search(pattern, intent, re.IGNORECASE):
                # Try to extract explicit port
                port_match = re.search(r"\bport\s*(\d+)\b", intent)
                if port_match:
                    return protocol, int(port_match.group(1))
                return protocol, port

        # Check for explicit port number
        port_match = re.search(r"\bport\s*(\d+)\b", intent)
        if port_match:
            return "tcp", int(port_match.group(1))

        return None, None

    def _generate_parse_response(self, prompt: str) -> str:
        """Generate a parsing response."""
        # Extract intent from prompt
        intent_match = re.search(
            r"(?:intent|parse)[:\s]+(.+?)(?:\n|$)",
            prompt,
            re.IGNORECASE
        )
        if intent_match:
            intent = intent_match.group(1)
        else:
            intent = prompt

        rule = self.parse_intent(intent)
        return json.dumps(rule)

    def _generate_validation_response(self, prompt: str) -> str:
        """Generate a validation response."""
        return json.dumps({
            "valid": True,
            "issues": [],
            "warnings": [],
            "corrected_rule": None
        })

    def _generate_summary_response(self, prompt: str) -> str:
        """Generate a summary response."""
        return "Network configuration applied successfully."

    def _generate_remediation_response(self, prompt: str) -> str:
        """Generate a remediation response."""
        anomaly_type = "traffic_spike"
        if "ddos" in prompt.lower():
            anomaly_type = "ddos_sim"
        elif "drop" in prompt.lower():
            anomaly_type = "packet_drop"
        elif "bandwidth" in prompt.lower():
            anomaly_type = "bandwidth_hog"

        result = self.generate_remediation(
            {"type": anomaly_type, "device_id": "of:0000000000000001"},
            []
        )
        return json.dumps(result)

    def _generate_default_response(self, prompt: str) -> str:
        """Generate a default response."""
        return "I understand your request. Processing..."


# Singleton instance
_simulator_instance: Optional[LLMSimulator] = None


def get_llm_simulator() -> LLMSimulator:
    """Get or create the global LLM simulator instance."""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = LLMSimulator()
    return _simulator_instance


if __name__ == "__main__":
    # Test LLM simulator
    print("\n=== LLM Simulator Test ===\n")

    sim = LLMSimulator()

    test_intents = [
        "Block all traffic from 10.0.0.1",
        "Allow only HTTP traffic from h1 to h3",
        "Drop all ICMP packets on all switches",
        "Prioritize VoIP traffic on UDP port 5060",
        "Rate limit h5 to 10 Mbps",
        "Isolate switch s2 from the network",
        "Mirror all traffic on s1 to port 5",
        "Remove the block rule for h1"
    ]

    for intent in test_intents:
        print(f"\nIntent: {intent}")
        result = sim.parse_intent(intent)
        print(f"  Type: {result['intent_type']}")
        print(f"  Action: {result['action']}")
        print(f"  Source: {result['src_host'] or result['src_device']}")
        print(f"  Dest: {result['dst_host'] or result['dst_device']}")
        print(f"  Protocol: {result['protocol']}")
        print(f"  Port: {result['port']}")
        print(f"  Priority: {result['priority']}")

    # Test remediation
    print("\n--- Remediation Test ---")
    anomaly = {"type": "traffic_spike", "device_id": "of:0000000000000001"}
    remediation = sim.generate_remediation(anomaly, [])
    print(f"Anomaly: {anomaly['type']}")
    print(f"Action: {remediation['action_type']}")
    print(f"Reason: {remediation['reason']}")

    # Test summary
    print("\n--- Summary Test ---")
    rule = {"intent_type": "block", "src_host": "10.0.0.1", "protocol": "all"}
    summary = sim.generate_summary(rule, {"success": True})
    print(f"Summary: {summary}")

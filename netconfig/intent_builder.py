"""
Intent Builder for LLM-NetAuto-SDN.

Converts parsed intent rules to ONOS Intent Framework JSON.
Uses ONOS host-to-host and point-to-point intents.
"""

import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class IntentBuilder:
    """
    Builds ONOS Intent Framework JSON from parsed rules.

    Supports:
    - HostToHostIntent: Traffic between two hosts
    - PointToPointIntent: Traffic between two connection points
    - MultiPointToSinglePointIntent: Aggregation intents
    - SinglePointToMultiPointIntent: Broadcast intents
    """

    def __init__(self, app_id: str = None):
        """
        Initialize intent builder.

        Args:
            app_id: ONOS application ID for intents
        """
        self._app_id = app_id or os.getenv(
            "ONOS_APP_ID",
            "org.onosproject.cli"
        )
        logger.info(f"IntentBuilder initialized with app_id: {self._app_id}")

    def build_intent(
        self,
        parsed_rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build ONOS intent JSON from parsed rule.

        Args:
            parsed_rule: Parsed intent rule from LLM
            topology: Optional topology data for resolution

        Returns:
            ONOS Intent JSON or None if cannot build
        """
        intent_type = parsed_rule.get("intent_type", "")
        action = parsed_rule.get("action", "add")

        if action == "remove":
            logger.info("Remove action - no intent to build")
            return None

        # Route to appropriate builder
        if intent_type == "block":
            return self._build_block_intent(parsed_rule, topology)
        elif intent_type == "allow":
            return self._build_allow_intent(parsed_rule, topology)
        elif intent_type == "prioritize":
            return self._build_prioritize_intent(parsed_rule, topology)
        elif intent_type == "reroute":
            return self._build_reroute_intent(parsed_rule, topology)
        elif intent_type == "isolate":
            return self._build_isolate_intent(parsed_rule, topology)
        elif intent_type == "rate_limit":
            return self._build_rate_limit_intent(parsed_rule, topology)
        else:
            # Default to host-to-host
            return self._build_host_to_host_intent(parsed_rule, topology)

    def _build_host_to_host_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a HostToHostIntent."""
        src_host = rule.get("src_host")
        dst_host = rule.get("dst_host")

        # Resolve to MAC addresses if needed
        src_mac = self._resolve_to_mac(src_host, topology)
        dst_mac = self._resolve_to_mac(dst_host, topology)

        if not src_mac or not dst_mac:
            logger.warning(
                f"Cannot resolve hosts: src={src_host}, dst={dst_host}"
            )
            return None

        intent_key = self._generate_key()

        intent = {
            "type": "HostToHostIntent",
            "appId": self._app_id,
            "key": intent_key,
            "priority": rule.get("priority", 40000),
            "one": f"{src_mac}/-1",
            "two": f"{dst_mac}/-1"
        }

        # Add traffic selector if protocol specified
        selector = self._build_selector(rule)
        if selector:
            intent["selector"] = selector

        # Add treatment for prioritization
        treatment = self._build_treatment(rule)
        if treatment:
            intent["treatment"] = treatment

        return intent

    def _build_block_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build a blocking intent.

        Uses PointToPointIntent with DROP treatment.
        """
        # For blocking, we typically add flow rules directly
        # But can also use intents with high priority and no actions

        src_host = rule.get("src_host")
        src_device = rule.get("src_device")

        intent_key = self._generate_key()

        # Build point-to-point intent
        intent = {
            "type": "PointToPointIntent",
            "appId": self._app_id,
            "key": intent_key,
            "priority": rule.get("priority", 50000),
        }

        # Add selector
        selector = self._build_selector(rule)
        if selector:
            intent["selector"] = selector

        # No treatment = DROP
        intent["treatment"] = {"instructions": []}

        # If we have device info, use it
        if src_device:
            intent["ingressPoint"] = {
                "device": src_device,
                "port": str(rule.get("in_port", 1))
            }

        return intent

    def _build_allow_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build an allow/permit intent."""
        # Similar to host-to-host but with specific protocol
        return self._build_host_to_host_intent(rule, topology)

    def _build_prioritize_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a prioritization intent with QoS."""
        intent = self._build_host_to_host_intent(rule, topology)
        if intent:
            # Set high priority
            intent["priority"] = rule.get("priority", 60000)

            # Add QoS treatment
            intent["treatment"] = {
                "instructions": [
                    {
                        "type": "QUEUE",
                        "queueId": rule.get("queue_id", 1)
                    }
                ]
            }

        return intent

    def _build_reroute_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a reroute intent with path constraints."""
        intent = self._build_host_to_host_intent(rule, topology)
        if intent:
            # Add path constraints if waypoints specified
            waypoints = rule.get("waypoints", [])
            if waypoints:
                intent["constraints"] = [
                    {
                        "type": "WaypointConstraint",
                        "waypoints": waypoints
                    }
                ]

        return intent

    def _build_isolate_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build an isolation intent.

        Blocks all traffic to/from a device or host.
        """
        target = rule.get("src_host") or rule.get("src_device")
        intent_key = self._generate_key()

        # For isolation, we need multiple intents or use flow rules
        intent = {
            "type": "PointToPointIntent",
            "appId": self._app_id,
            "key": intent_key,
            "priority": 65000,  # Highest priority for isolation
            "treatment": {"instructions": []}  # DROP
        }

        if target:
            # Add selector for target
            intent["selector"] = {
                "criteria": [
                    {
                        "type": "ETH_SRC",
                        "mac": self._resolve_to_mac(target, topology) or target
                    }
                ]
            }

        return intent

    def _build_rate_limit_intent(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build a rate limiting intent.

        Uses meter instruction for bandwidth limiting.
        """
        intent = self._build_host_to_host_intent(rule, topology)
        if intent:
            limit_mbps = rule.get("bandwidth_limit_mbps", 10)

            intent["treatment"] = {
                "instructions": [
                    {
                        "type": "METER",
                        "meterId": 1  # Meter must be pre-configured
                    }
                ]
            }

            # Add meter configuration annotation
            intent["annotations"] = intent.get("annotations", {})
            intent["annotations"]["rate_limit_mbps"] = str(limit_mbps)

        return intent

    def _build_selector(self, rule: Dict[str, Any]) -> Optional[Dict]:
        """Build traffic selector criteria."""
        criteria = []

        # Ethernet type (default to IPv4)
        eth_type = rule.get("eth_type", "0x0800")
        criteria.append({
            "type": "ETH_TYPE",
            "ethType": eth_type
        })

        # Source host (MAC or IP)
        src_host = rule.get("src_host")
        if src_host:
            if self._is_mac(src_host):
                criteria.append({
                    "type": "ETH_SRC",
                    "mac": src_host
                })
            elif self._is_ip(src_host):
                criteria.append({
                    "type": "IPV4_SRC",
                    "ip": f"{src_host}/32"
                })

        # Destination host
        dst_host = rule.get("dst_host")
        if dst_host:
            if self._is_mac(dst_host):
                criteria.append({
                    "type": "ETH_DST",
                    "mac": dst_host
                })
            elif self._is_ip(dst_host):
                criteria.append({
                    "type": "IPV4_DST",
                    "ip": f"{dst_host}/32"
                })

        # IP Protocol
        protocol = rule.get("protocol")
        ip_proto = rule.get("ip_proto")

        if protocol == "icmp" or ip_proto == 1:
            criteria.append({
                "type": "IP_PROTO",
                "protocol": 1
            })
        elif protocol == "tcp" or ip_proto == 6:
            criteria.append({
                "type": "IP_PROTO",
                "protocol": 6
            })
            # TCP port
            port = rule.get("port")
            if port:
                criteria.append({
                    "type": "TCP_DST",
                    "tcpPort": port
                })
        elif protocol == "udp" or ip_proto == 17:
            criteria.append({
                "type": "IP_PROTO",
                "protocol": 17
            })
            # UDP port
            port = rule.get("port")
            if port:
                criteria.append({
                    "type": "UDP_DST",
                    "udpPort": port
                })

        return {"criteria": criteria} if criteria else None

    def _build_treatment(self, rule: Dict[str, Any]) -> Optional[Dict]:
        """Build traffic treatment instructions."""
        instructions = []

        # Output action
        out_port = rule.get("out_port")
        if out_port:
            instructions.append({
                "type": "OUTPUT",
                "port": str(out_port)
            })

        # Queue for QoS
        queue_id = rule.get("queue_id")
        if queue_id:
            instructions.append({
                "type": "QUEUE",
                "queueId": queue_id
            })

        # VLAN modification
        vlan_id = rule.get("vlan_id")
        if vlan_id:
            instructions.append({
                "type": "L2MODIFICATION",
                "subtype": "VLAN_ID",
                "vlanId": vlan_id
            })

        return {"instructions": instructions} if instructions else None

    def _resolve_to_mac(
        self,
        identifier: str,
        topology: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Resolve identifier to MAC address."""
        if not identifier:
            return None

        # Already a MAC
        if self._is_mac(identifier):
            return identifier

        if not topology:
            return None

        # Search hosts
        for host in topology.get("hosts", []):
            # Match by name
            if host.get("name", "").lower() == identifier.lower():
                return host.get("mac")

            # Match by IP (handle both "ip" string and "ips" array formats)
            ip_list = []
            if host.get("ip"):
                ip_list.append(host.get("ip"))
            if host.get("ips"):
                ip_list.extend(host.get("ips", []))
            if host.get("ipAddresses"):
                ip_list.extend(host.get("ipAddresses", []))
            
            if identifier in ip_list:
                return host.get("mac")


    def _is_mac(self, value: str) -> bool:
        """Check if value is a MAC address."""
        if not value:
            return False
        parts = value.split(":")
        return len(parts) == 6 and all(len(p) == 2 for p in parts)

    def _is_ip(self, value: str) -> bool:
        """Check if value is an IP address."""
        if not value:
            return False
        parts = value.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    def _generate_key(self) -> str:
        """Generate unique intent key."""
        return f"llm-netauto-{uuid.uuid4().hex[:8]}"


# Singleton instance
_builder_instance: Optional[IntentBuilder] = None


def get_intent_builder() -> IntentBuilder:
    """Get or create the global intent builder instance."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = IntentBuilder()
    return _builder_instance


if __name__ == "__main__":
    # Test intent builder
    print("\n=== Intent Builder Test ===\n")

    builder = IntentBuilder()

    # Test topology
    topology = {
        "hosts": [
            {"name": "h1", "mac": "00:00:00:00:00:01", "ips": ["10.0.0.1"]},
            {"name": "h2", "mac": "00:00:00:00:00:02", "ips": ["10.0.0.2"]},
            {"name": "h3", "mac": "00:00:00:00:00:03", "ips": ["10.0.0.3"]}
        ]
    }

    # Test rules
    test_rules = [
        {
            "intent_type": "allow",
            "action": "add",
            "src_host": "h1",
            "dst_host": "h3",
            "protocol": "tcp",
            "port": 80,
            "priority": 40000
        },
        {
            "intent_type": "block",
            "action": "add",
            "src_host": "10.0.0.1",
            "dst_host": None,
            "protocol": "all",
            "priority": 50000
        },
        {
            "intent_type": "prioritize",
            "action": "add",
            "src_host": "h1",
            "dst_host": "h2",
            "protocol": "udp",
            "port": 5060,
            "priority": 60000
        }
    ]

    import json
    for rule in test_rules:
        print(f"\n--- Rule: {rule['intent_type']} ---")
        intent = builder.build_intent(rule, topology)
        if intent:
            print(json.dumps(intent, indent=2))
        else:
            print("No intent generated")

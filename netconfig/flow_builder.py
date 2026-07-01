"""
Flow Builder for LLM-NetAuto-SDN.

Converts parsed intent rules to ONOS Flow Rule JSON.
Generates per-switch OpenFlow flow rules.
"""

import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class FlowBuilder:
    """
    Builds ONOS Flow Rule JSON from parsed rules.

    Unlike intents, flow rules are installed directly on
    specific switches and provide fine-grained control.
    """

    def __init__(self, app_id: str = None):
        """
        Initialize flow builder.

        Args:
            app_id: ONOS application ID for flows
        """
        self._app_id = app_id or os.getenv(
            "ONOS_APP_ID",
            "org.onosproject.cli"
        )
        # Default table ID
        self._table_id = 0

        logger.info(f"FlowBuilder initialized with app_id: {self._app_id}")

    def build_flows(
        self,
        parsed_rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build ONOS flow rules from parsed rule.

        Args:
            parsed_rule: Parsed intent rule from LLM
            topology: Optional topology data for switch resolution

        Returns:
            List of ONOS Flow Rule JSONs (one per switch)
        """
        flows = []

        intent_type = parsed_rule.get("intent_type", "")
        action = parsed_rule.get("action", "add")

        if action == "remove":
            logger.info("Remove action - returning empty flow list")
            return []

        # Determine target switches
        target_switches = self._get_target_switches(parsed_rule, topology)

        # Build flow for each switch
        for device_id in target_switches:
            flow = self._build_single_flow(parsed_rule, device_id, topology)
            if flow:
                flows.append(flow)

        return flows

    def build_single_flow(
        self,
        parsed_rule: Dict[str, Any],
        device_id: str,
        topology: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build a single flow rule for a specific device.

        Args:
            parsed_rule: Parsed rule
            device_id: Target device ID
            topology: Topology data

        Returns:
            ONOS Flow Rule JSON
        """
        return self._build_single_flow(parsed_rule, device_id, topology)

    def _build_single_flow(
        self,
        rule: Dict[str, Any],
        device_id: str,
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a single flow rule."""
        intent_type = rule.get("intent_type", "allow")

        flow = {
            "priority": rule.get("priority", 40000),
            "timeout": rule.get("timeout", 0),  # 0 = permanent
            "isPermanent": rule.get("timeout", 0) == 0,
            "deviceId": device_id,
            "tableId": self._table_id,
            "appId": self._app_id
        }

        # Build selector (match criteria)
        selector = self._build_selector(rule, topology)
        if selector:
            flow["selector"] = selector

        # Build treatment (actions) based on intent type
        treatment = self._build_treatment(intent_type, rule, device_id, topology)
        flow["treatment"] = treatment

        return flow

    def _resolve_device_id(self, name: str, topology: Optional[Dict[str, Any]]) -> str:
        """Resolve short switch name (e.g. s1) or dpid to a full ONOS DPID."""
        if not name:
            return name
        if name.startswith("of:"):
            return name
        # Try to find matching device in topology annotations
        if topology and "devices" in topology:
            for d in topology["devices"]:
                d_id = d.get("id", "")
                d_name = d.get("annotations", {}).get("name", "")
                if name.lower() == d_name.lower() or name.lower() == d_id.lower():
                    return d_id
        # Fallback to standard mapping format of:000000000000000X
        import re
        m = re.search(r"s(\d+)", name.lower())
        if m:
            num = int(m.group(1))
            return f"of:{num:016x}"
        return name

    def _get_target_switches(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Determine which switches the rule should apply to."""
        switches = []

        # Explicit device
        src_device = rule.get("src_device")
        if src_device:
            resolved_src = self._resolve_device_id(src_device, topology)
            if resolved_src:
                switches.append(resolved_src)

        dst_device = rule.get("dst_device")
        if dst_device:
            resolved_dst = self._resolve_device_id(dst_device, topology)
            if resolved_dst and resolved_dst not in switches:
                switches.append(resolved_dst)

        # Target all switches
        if rule.get("target_all_switches", False) and topology:
            for device in topology.get("devices", []):
                device_id = device.get("id", "")
                if device_id and device_id not in switches:
                    switches.append(device_id)

        # If no switches yet, try to find based on hosts
        if not switches and topology:
            src_host = rule.get("src_host")
            dst_host = rule.get("dst_host")

            # Find switch connected to source host
            src_switch = self._find_host_switch(src_host, topology)
            if src_switch:
                switches.append(src_switch)

            # Find switch connected to destination host
            dst_switch = self._find_host_switch(dst_host, topology)
            if dst_switch and dst_switch not in switches:
                switches.append(dst_switch)

        # Fallback: all switches if still none
        if not switches and topology:
            switches = [
                d.get("id") for d in topology.get("devices", [])
                if d.get("id")
            ]

        return switches

    def _find_host_switch(
        self,
        host_identifier: str,
        topology: Dict[str, Any]
    ) -> Optional[str]:
        """Find the switch a host is connected to."""
        if not host_identifier:
            return None

        for host in topology.get("hosts", []):
            # Match by name
            if host.get("name", "").lower() == host_identifier.lower():
                return host.get("location_device") or host.get("device")

            # Match by IP
            ips = host.get("ips", host.get("ipAddresses", []))
            if host_identifier in ips:
                return host.get("location_device") or host.get("device")

            # Match by MAC
            if host.get("mac", "").lower() == host_identifier.lower():
                return host.get("location_device") or host.get("device")

        return None

    def _build_selector(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build flow selector (match criteria)."""
        criteria = []

        # Ethernet Type (IPv4 by default)
        eth_type = rule.get("eth_type", "0x0800")
        if eth_type:
            # Convert hex string to int
            if isinstance(eth_type, str) and eth_type.startswith("0x"):
                eth_type = int(eth_type, 16)
            criteria.append({
                "type": "ETH_TYPE",
                "ethType": eth_type
            })

        # In Port
        in_port = rule.get("in_port")
        if in_port:
            criteria.append({
                "type": "IN_PORT",
                "port": str(in_port)
            })

        # Source MAC/IP
        src_host = rule.get("src_host")
        if src_host:
            # Try to resolve to MAC first
            src_mac = self._resolve_to_mac(src_host, topology)
            if src_mac:
                criteria.append({
                    "type": "ETH_SRC",
                    "mac": src_mac
                })
            elif self._is_ip(src_host):
                criteria.append({
                    "type": "IPV4_SRC",
                    "ip": f"{src_host}/32"
                })
            elif "/" in str(src_host):  # Subnet
                criteria.append({
                    "type": "IPV4_SRC",
                    "ip": src_host
                })

        # Destination MAC/IP
        dst_host = rule.get("dst_host")
        if dst_host:
            dst_mac = self._resolve_to_mac(dst_host, topology)
            if dst_mac:
                criteria.append({
                    "type": "ETH_DST",
                    "mac": dst_mac
                })
            elif self._is_ip(dst_host):
                criteria.append({
                    "type": "IPV4_DST",
                    "ip": f"{dst_host}/32"
                })
            elif "/" in str(dst_host):
                criteria.append({
                    "type": "IPV4_DST",
                    "ip": dst_host
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
            # TCP Port
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
            # UDP Port
            port = rule.get("port")
            if port:
                criteria.append({
                    "type": "UDP_DST",
                    "udpPort": port
                })

        # VLAN
        vlan_id = rule.get("vlan_id")
        if vlan_id:
            criteria.append({
                "type": "VLAN_VID",
                "vlanId": vlan_id
            })

        return {"criteria": criteria}

    def _build_treatment(
        self,
        intent_type: str,
        rule: Dict[str, Any],
        device_id: str,
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build flow treatment (actions)."""
        instructions = []

        if intent_type == "block":
            # DROP = empty instructions
            return {"instructions": []}

        elif intent_type == "allow":
            # FORWARD to output port
            out_port = rule.get("out_port")
            if out_port:
                instructions.append({
                    "type": "OUTPUT",
                    "port": str(out_port)
                })
            else:
                # Use CONTROLLER to let controller decide
                instructions.append({
                    "type": "OUTPUT",
                    "port": "CONTROLLER"
                })

        elif intent_type == "prioritize":
            # Queue for QoS
            queue_id = rule.get("queue_id", 1)
            instructions.append({
                "type": "QUEUE",
                "queueId": queue_id
            })
            # Also output
            out_port = rule.get("out_port")
            if out_port:
                instructions.append({
                    "type": "OUTPUT",
                    "port": str(out_port)
                })
            else:
                instructions.append({
                    "type": "OUTPUT",
                    "port": "NORMAL"
                })

        elif intent_type == "mirror":
            # Mirror to monitoring port
            mirror_port = rule.get("out_port", 5)
            instructions.append({
                "type": "OUTPUT",
                "port": str(mirror_port)
            })
            # Also forward normally
            instructions.append({
                "type": "OUTPUT",
                "port": "NORMAL"
            })

        elif intent_type == "rate_limit":
            # Meter for rate limiting
            meter_id = rule.get("meter_id", 1)
            instructions.append({
                "type": "METER",
                "meterId": meter_id
            })
            instructions.append({
                "type": "OUTPUT",
                "port": "NORMAL"
            })

        elif intent_type == "isolate":
            # DROP everything
            return {"instructions": []}

        elif intent_type == "reroute":
            # Output to specific port for rerouting
            out_port = rule.get("out_port")
            if out_port:
                instructions.append({
                    "type": "OUTPUT",
                    "port": str(out_port)
                })

        else:
            # Default: NORMAL forwarding
            instructions.append({
                "type": "OUTPUT",
                "port": "NORMAL"
            })

        return {"instructions": instructions}

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

        for host in topology.get("hosts", []):
            if host.get("name", "").lower() == identifier.lower():
                return host.get("mac")
            ips = host.get("ips", host.get("ipAddresses", []))
            if identifier in ips:
                return host.get("mac")

        return None

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

    def build_delete_flow(
        self,
        device_id: str,
        flow_id: str
    ) -> Dict[str, Any]:
        """
        Build a flow delete request.

        Args:
            device_id: Target device
            flow_id: Flow to delete

        Returns:
            Delete request dict
        """
        return {
            "deviceId": device_id,
            "flowId": flow_id
        }

    def build_clear_flows(
        self,
        device_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build requests to clear all custom flows.

        Args:
            device_ids: List of device IDs

        Returns:
            List of clear requests
        """
        return [
            {"deviceId": did, "clear_custom": True}
            for did in device_ids
        ]


# Singleton instance
_builder_instance: Optional[FlowBuilder] = None


def get_flow_builder() -> FlowBuilder:
    """Get or create the global flow builder instance."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = FlowBuilder()
    return _builder_instance


if __name__ == "__main__":
    # Test flow builder
    print("\n=== Flow Builder Test ===\n")

    builder = FlowBuilder()

    # Test topology
    topology = {
        "devices": [
            {"id": "of:0000000000000001", "name": "s1"},
            {"id": "of:0000000000000002", "name": "s2"},
            {"id": "of:0000000000000003", "name": "s3"}
        ],
        "hosts": [
            {"name": "h1", "mac": "00:00:00:00:00:01",
             "ips": ["10.0.0.1"], "device": "of:0000000000000001"},
            {"name": "h2", "mac": "00:00:00:00:00:02",
             "ips": ["10.0.0.2"], "device": "of:0000000000000001"},
            {"name": "h3", "mac": "00:00:00:00:00:03",
             "ips": ["10.0.0.3"], "device": "of:0000000000000002"},
            {"name": "h4", "mac": "00:00:00:00:00:04",
             "ips": ["10.0.0.4"], "device": "of:0000000000000002"}
        ]
    }

    # Test rules
    test_rules = [
        {
            "intent_type": "block",
            "action": "add",
            "src_host": "10.0.0.1",
            "target_all_switches": True,
            "priority": 50000
        },
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
            "intent_type": "mirror",
            "action": "add",
            "src_device": "of:0000000000000001",
            "out_port": 5,
            "priority": 30000
        }
    ]

    import json
    for rule in test_rules:
        print(f"\n--- Rule: {rule['intent_type']} ---")
        flows = builder.build_flows(rule, topology)
        for i, flow in enumerate(flows):
            print(f"\nFlow {i + 1}:")
            print(json.dumps(flow, indent=2))

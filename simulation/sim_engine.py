"""
Simulation Engine for LLM-NetAuto-SDN.

Main controller that orchestrates all simulation components
for demo mode operation without external services.
"""

import os
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

from .network_sim import NetworkSimulator, get_network_simulator
from .llm_sim import LLMSimulator, get_llm_simulator
from .telemetry_sim import TelemetrySimulator, get_telemetry_simulator

load_dotenv()


class SimulationEngine:
    """
    Main simulation controller for demo mode.

    Orchestrates:
    - NetworkSimulator: ONOS API simulation
    - LLMSimulator: Intent parsing without Ollama
    - TelemetrySimulator: Realistic traffic generation
    """

    def __init__(self):
        """Initialize simulation engine."""
        self._demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        self._lock = threading.Lock()

        # Initialize components
        self._network_sim = get_network_simulator()
        self._llm_sim = get_llm_simulator()
        self._telemetry_sim = get_telemetry_simulator()

        self._initialized = True
        self._start_time = datetime.now()

        logger.info(
            f"SimulationEngine initialized (demo_mode={self._demo_mode})"
        )

    @property
    def demo_mode(self) -> bool:
        """Check if in demo mode."""
        return self._demo_mode

    @property
    def network(self) -> NetworkSimulator:
        """Get network simulator."""
        return self._network_sim

    @property
    def llm(self) -> LLMSimulator:
        """Get LLM simulator."""
        return self._llm_sim

    @property
    def telemetry(self) -> TelemetrySimulator:
        """Get telemetry simulator."""
        return self._telemetry_sim

    # ==========================================
    # ONOS-Compatible API Methods
    # ==========================================

    def get_topology(self) -> Dict[str, Any]:
        """Get complete network topology."""
        return self._network_sim.get_topology()

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all network devices."""
        devices = self._network_sim.get_devices()
        return {"devices": devices}

    def get_hosts(self) -> List[Dict[str, Any]]:
        """Get all network hosts."""
        hosts = self._network_sim.get_hosts()
        return {"hosts": hosts}

    def get_links(self) -> List[Dict[str, Any]]:
        """Get all network links."""
        links = self._network_sim.get_links()
        return {"links": links}

    def get_flows(
        self,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get flow rules."""
        flows = self._network_sim.get_flows(device_id)
        return {"flows": flows}

    def post_flow(
        self,
        device_id: str,
        flow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Install a flow rule."""
        return self._network_sim.install_flow(device_id, flow_json)

    def delete_flow(self, device_id: str, flow_id: str) -> bool:
        """Delete a flow rule."""
        return self._network_sim.delete_flow(device_id, flow_id)

    def get_intents(self) -> Dict[str, Any]:
        """Get all intents."""
        intents = self._network_sim.get_intents()
        return {"intents": intents}

    def post_intent(self, intent_json: Dict[str, Any]) -> Dict[str, Any]:
        """Install an intent."""
        return self._network_sim.install_intent(intent_json)

    def delete_intent(self, app_id: str, key: str) -> bool:
        """Delete an intent."""
        return self._network_sim.delete_intent(app_id, key)

    def get_port_stats(
        self,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get port statistics."""
        if device_id:
            ports = self._telemetry_sim.get_port_stats(device_id)
            return {"statistics": [{"device": device_id, "ports": ports}]}
        else:
            stats = []
            for did in ["of:0000000000000001", "of:0000000000000002",
                        "of:0000000000000003"]:
                ports = self._telemetry_sim.get_port_stats(did)
                stats.append({"device": did, "ports": ports})
            return {"statistics": stats}

    # ==========================================
    # Intent Processing
    # ==========================================

    def process_intent(
        self,
        intent_text: str
    ) -> Dict[str, Any]:
        """
        Process a natural language intent.

        Args:
            intent_text: Natural language intent

        Returns:
            Processing result with rule, deployment, summary
        """
        import time
        start_time = time.time()

        result = {
            "success": False,
            "intent": intent_text,
            "parsed_rule": None,
            "deployment_method": "simulated",
            "response": None,
            "summary": "",
            "latency_ms": 0,
            "mode": "demo",
            "error": None
        }

        try:
            # Parse intent with LLM simulator
            parsed_rule = self._llm_sim.parse_intent(intent_text)
            result["parsed_rule"] = parsed_rule

            # Deploy based on rule type
            if parsed_rule.get("use_intent_framework", False):
                # Deploy as intent
                intent_json = self._build_intent_json(parsed_rule)
                response = self._network_sim.install_intent(intent_json)
                result["deployment_method"] = "intent_framework"
            else:
                # Deploy as flow rules
                flow_json = self._build_flow_json(parsed_rule)
                devices = self._get_target_devices(parsed_rule)
                responses = []
                for device_id in devices:
                    r = self._network_sim.install_flow(device_id, flow_json)
                    responses.append(r)
                response = responses[0] if len(responses) == 1 else responses
                result["deployment_method"] = "flow_rule"

            result["response"] = response
            result["success"] = True

            # Generate summary
            result["summary"] = self._llm_sim.generate_summary(
                parsed_rule,
                {"success": True}
            )

        except Exception as e:
            logger.error(f"Intent processing failed: {e}")
            result["error"] = str(e)

        result["latency_ms"] = (time.time() - start_time) * 1000
        return result

    def _build_intent_json(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Build ONOS intent JSON from rule."""
        return {
            "type": "HostToHostIntent",
            "appId": "org.onosproject.cli",
            "key": f"llm-{datetime.now().strftime('%H%M%S')}",
            "priority": rule.get("priority", 40000),
            "one": f"{rule.get('src_host', 'any')}/-1",
            "two": f"{rule.get('dst_host', 'any')}/-1"
        }

    def _build_flow_json(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Build ONOS flow JSON from rule."""
        flow = {
            "priority": rule.get("priority", 40000),
            "timeout": 0,
            "isPermanent": True,
            "appId": "org.onosproject.cli"
        }

        # Build selector
        criteria = [{"type": "ETH_TYPE", "ethType": 2048}]

        src = rule.get("src_host")
        if src:
            criteria.append({"type": "IPV4_SRC", "ip": f"{src}/32"})

        dst = rule.get("dst_host")
        if dst:
            criteria.append({"type": "IPV4_DST", "ip": f"{dst}/32"})

        protocol = rule.get("protocol")
        if protocol == "icmp":
            criteria.append({"type": "IP_PROTO", "protocol": 1})
        elif protocol == "tcp":
            criteria.append({"type": "IP_PROTO", "protocol": 6})
            port = rule.get("port")
            if port:
                criteria.append({"type": "TCP_DST", "tcpPort": port})
        elif protocol == "udp":
            criteria.append({"type": "IP_PROTO", "protocol": 17})
            port = rule.get("port")
            if port:
                criteria.append({"type": "UDP_DST", "udpPort": port})

        flow["selector"] = {"criteria": criteria}

        # Build treatment
        intent_type = rule.get("intent_type", "allow")
        if intent_type == "block":
            flow["treatment"] = {"instructions": []}
        else:
            flow["treatment"] = {
                "instructions": [{"type": "OUTPUT", "port": "NORMAL"}]
            }

        return flow

    def _get_target_devices(self, rule: Dict[str, Any]) -> List[str]:
        """Get target devices for a rule."""
        devices = []

        if rule.get("src_device"):
            devices.append(rule["src_device"])
        if rule.get("dst_device") and rule["dst_device"] not in devices:
            devices.append(rule["dst_device"])

        if rule.get("target_all_switches") or not devices:
            devices = ["of:0000000000000001", "of:0000000000000002",
                       "of:0000000000000003"]

        return devices

    # ==========================================
    # Anomaly Management
    # ==========================================

    def trigger_anomaly(
        self,
        device_id: str,
        anomaly_type: str,
        duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """Trigger an anomaly."""
        # Trigger in both simulators
        net_result = self._network_sim.trigger_anomaly(
            device_id, anomaly_type, duration_seconds
        )
        tel_result = self._telemetry_sim.inject_anomaly(
            device_id, anomaly_type, duration_seconds
        )

        return {
            **net_result,
            "telemetry_anomaly_id": tel_result["anomaly_id"]
        }

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Resolve an anomaly."""
        net_resolved = self._network_sim.resolve_anomaly(anomaly_id)
        tel_resolved = self._telemetry_sim.resolve_anomaly(anomaly_id)
        return net_resolved or tel_resolved

    def resolve_all_anomalies(self) -> Dict[str, int]:
        """Resolve all anomalies."""
        net_count = self._network_sim.resolve_all_anomalies()
        tel_count = self._telemetry_sim.resolve_all_anomalies()
        return {
            "network_anomalies_resolved": net_count,
            "telemetry_anomalies_resolved": tel_count
        }

    def get_active_anomalies(self) -> List[Dict[str, Any]]:
        """Get all active anomalies."""
        return self._network_sim.get_active_anomalies()

    # ==========================================
    # Link Management
    # ==========================================

    def set_link_state(
        self,
        device1: str,
        device2: str,
        state: str
    ) -> bool:
        """Set link state."""
        if state == "down":
            return self._network_sim.bring_link_down(device1, device2)
        else:
            return self._network_sim.bring_link_up(device1, device2)

    # ==========================================
    # Traffic Scenarios
    # ==========================================

    def set_traffic_scenario(self, scenario: str) -> None:
        """Set traffic scenario."""
        self._telemetry_sim.set_traffic_scenario(scenario)

    # ==========================================
    # State Management
    # ==========================================

    def get_simulation_state(self) -> Dict[str, Any]:
        """Get complete simulation state."""
        return {
            "demo_mode": self._demo_mode,
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "network": self._network_sim.get_topology_summary(),
            "anomalies": self.get_active_anomalies(),
            "timestamp": datetime.now().isoformat()
        }

    def reset(self) -> None:
        """Reset simulation to initial state."""
        self._network_sim.reset()
        self._telemetry_sim.resolve_all_anomalies()
        self._start_time = datetime.now()
        logger.info("Simulation engine reset")

    def health_check(self) -> bool:
        """Check simulation engine health."""
        return self._initialized


# Singleton instance
_engine_instance: Optional[SimulationEngine] = None


def get_simulation_engine() -> SimulationEngine:
    """Get or create the global simulation engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SimulationEngine()
    return _engine_instance


if __name__ == "__main__":
    # Test simulation engine
    print("\n=== Simulation Engine Test ===\n")

    engine = SimulationEngine()

    print(f"Demo mode: {engine.demo_mode}")
    print(f"Health: {engine.health_check()}")

    # Get topology
    topo = engine.get_topology()
    print(f"\nDevices: {len(topo['devices'])}")
    print(f"Hosts: {len(topo['hosts'])}")
    print(f"Links: {len(topo['links'])}")

    # Process intent
    print("\n--- Processing Intent ---")
    result = engine.process_intent("Block all traffic from 10.0.0.1")
    print(f"Success: {result['success']}")
    print(f"Method: {result['deployment_method']}")
    print(f"Latency: {result['latency_ms']:.1f} ms")
    print(f"Summary: {result['summary']}")

    # Check flows
    flows = engine.get_flows()
    print(f"\nTotal flows: {len(flows['flows'])}")

    # Trigger anomaly
    print("\n--- Triggering Anomaly ---")
    anomaly = engine.trigger_anomaly(
        "of:0000000000000001",
        "traffic_spike",
        30
    )
    print(f"Anomaly: {anomaly}")

    # Get state
    state = engine.get_simulation_state()
    print(f"\nUptime: {state['uptime_seconds']:.1f}s")
    print(f"Active anomalies: {len(state['anomalies'])}")

"""
Feedback Loop for LLM-NetAuto-SDN.

Autonomous remediation system that monitors for anomalies
and deploys corrective actions automatically.
"""

import os
import time
import threading
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Remediation:
    """Represents a remediation action."""
    remediation_id: str
    device_id: str
    anomaly_type: str
    anomaly_score: float
    action_type: str
    rule: Dict[str, Any]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    rolled_back: bool = False
    rolled_back_at: Optional[datetime] = None


class FeedbackLoop:
    """
    Autonomous network remediation system.

    Features:
    - Monitors telemetry for anomalies
    - Generates corrective rules using LLM
    - Deploys rules automatically
    - Tracks remediation history
    - Per-device cooldown
    """

    def __init__(self):
        """Initialize feedback loop (live-only mode)."""
        self._check_interval = 10  # seconds
        self._cooldown = int(os.getenv("REMEDIATION_COOLDOWN", "30"))

        self._lock = threading.Lock()
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

        # State
        self._remediation_history: deque = deque(maxlen=100)
        self._last_remediation: Dict[str, datetime] = {}
        self._remediation_counter = 0

        # Components (lazy initialization)
        self._telemetry_collector = None
        self._anomaly_detector = None
        self._intent_parser = None
        self._onos_client = None
        self._rag_engine = None
        self._metrics_exporter = None

        logger.info(
            f"FeedbackLoop initialized "
            f"(interval={self._check_interval}s, cooldown={self._cooldown}s)"
        )

    def _initialize_components(self) -> None:
        """Lazy initialize components."""
        if self._telemetry_collector is not None:
            return

        from .telemetry_collector import get_telemetry_collector
        from .anomaly_detector import get_anomaly_detector
        from .metrics_exporter import get_metrics_exporter
        from llm.intent_parser import get_intent_parser
        from llm.rag_engine import get_rag_engine
        from controller.onos_client import get_onos_client

        self._telemetry_collector = get_telemetry_collector()
        self._anomaly_detector = get_anomaly_detector()
        self._intent_parser = get_intent_parser()
        self._rag_engine = get_rag_engine()
        self._metrics_exporter = get_metrics_exporter()
        self._onos_client = get_onos_client()

    def start(self) -> None:
        """Start the feedback loop."""
        if self._running:
            return

        self._initialize_components()

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self._thread.start()
        logger.info("FeedbackLoop started")

    def stop(self) -> None:
        """Stop the feedback loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=15)
        logger.info("FeedbackLoop stopped")

    def pause(self) -> None:
        """Pause the feedback loop."""
        self._paused = True
        logger.info("FeedbackLoop paused")

    def resume(self) -> None:
        """Resume the feedback loop."""
        self._paused = False
        logger.info("FeedbackLoop resumed")

    def _loop(self) -> None:
        """Main feedback loop."""
        while self._running:
            if not self._paused:
                try:
                    self._check_and_remediate()
                except Exception as e:
                    logger.error(f"Feedback loop error: {e}")

            time.sleep(self._check_interval)

    def _check_and_remediate(self) -> None:
        """Check for anomalies and remediate if needed."""
        # Get latest telemetry
        latest = self._telemetry_collector.get_latest()

        for device_id, sample in latest.items():
            # Check cooldown
            if self._in_cooldown(device_id):
                continue

            # Add sample to detector
            result = self._anomaly_detector.add_sample(sample)

            if result and result.get("is_anomaly"):
                self._handle_anomaly(device_id, result)

    def _in_cooldown(self, device_id: str) -> bool:
        """Check if device is in remediation cooldown."""
        with self._lock:
            last = self._last_remediation.get(device_id)
            if last is None:
                return False

            elapsed = (datetime.now() - last).total_seconds()
            return elapsed < self._cooldown

    def _handle_anomaly(
        self,
        device_id: str,
        anomaly: Dict[str, Any]
    ) -> None:
        """Handle a detected anomaly."""
        logger.warning(
            f"Handling anomaly on {device_id}: "
            f"type={anomaly.get('type')}, score={anomaly.get('score'):.3f}"
        )

        # Get current flows from ONOS
        flows = self._onos_client.get_flows(device_id) if self._onos_client else []

        # Generate remediation using LLM
        remediation_action = self._intent_parser.generate_remediation(
            anomaly={
                "device_id": device_id,
                "type": anomaly.get("type", "unknown"),
                "score": anomaly.get("score", 0),
                "timestamp": anomaly.get("timestamp")
            },
            current_flows=flows,
            traffic_stats=anomaly.get("features", {})
        )

        if not remediation_action:
            logger.warning("Could not generate remediation")
            return

        # Deploy the corrective rule
        success = self._deploy_remediation(device_id, remediation_action)

        # Record remediation
        self._record_remediation(device_id, anomaly, remediation_action, success)

        # Update metrics
        if self._metrics_exporter:
            self._metrics_exporter.record_remediation(
                device_id,
                remediation_action.get("action_type", "unknown")
            )

        # Index in RAG for future reference
        if self._rag_engine:
            self._rag_engine.index_remediation(
                anomaly=anomaly,
                action=remediation_action,
                result={"success": success}
            )

    def _deploy_remediation(
        self,
        device_id: str,
        action: Dict[str, Any]
    ) -> bool:
        """Deploy remediation rule."""
        rule = action.get("rule", {})
        if not rule:
            return False

        try:
            # Build flow JSON
            flow_json = self._build_flow_from_rule(rule, device_id)

            # Deploy to ONOS
            if self._onos_client is None:
                logger.error("ONOS client not available for remediation deployment")
                return False
            result = self._onos_client.post_flow(device_id, flow_json)

            success = result and not result.get("error")

            logger.info(
                f"Remediation deployed on {device_id}: "
                f"action={action.get('action_type')}, success={success}"
            )

            return success

        except Exception as e:
            logger.error(f"Failed to deploy remediation: {e}")
            return False

    def _build_flow_from_rule(
        self,
        rule: Dict[str, Any],
        device_id: str
    ) -> Dict[str, Any]:
        """Build ONOS flow JSON from rule."""
        flow = {
            "priority": rule.get("priority", 55000),
            "timeout": 0,
            "isPermanent": True,
            "deviceId": device_id,
            "appId": "org.onosproject.cli"
        }

        # Build selector
        criteria = [{"type": "ETH_TYPE", "ethType": 2048}]

        if rule.get("in_port"):
            criteria.append({
                "type": "IN_PORT",
                "port": str(rule["in_port"])
            })

        if rule.get("src_host"):
            criteria.append({
                "type": "IPV4_SRC",
                "ip": f"{rule['src_host']}/32"
            })

        flow["selector"] = {"criteria": criteria}

        # Build treatment based on intent type
        intent_type = rule.get("intent_type", "rate_limit")

        if intent_type in ["block", "isolate"]:
            flow["treatment"] = {"instructions": []}
        elif intent_type == "rate_limit":
            flow["treatment"] = {
                "instructions": [
                    {"type": "METER", "meterId": 1},
                    {"type": "OUTPUT", "port": "NORMAL"}
                ]
            }
        elif intent_type == "prioritize":
            flow["treatment"] = {
                "instructions": [
                    {"type": "QUEUE", "queueId": rule.get("queue_id", 0)},
                    {"type": "OUTPUT", "port": "NORMAL"}
                ]
            }
        else:
            flow["treatment"] = {
                "instructions": [{"type": "OUTPUT", "port": "NORMAL"}]
            }

        return flow

    def _record_remediation(
        self,
        device_id: str,
        anomaly: Dict[str, Any],
        action: Dict[str, Any],
        success: bool
    ) -> None:
        """Record a remediation in history."""
        with self._lock:
            self._remediation_counter += 1

            remediation = Remediation(
                remediation_id=f"rem-{self._remediation_counter:05d}",
                device_id=device_id,
                anomaly_type=anomaly.get("type", "unknown"),
                anomaly_score=anomaly.get("score", 0),
                action_type=action.get("action_type", "unknown"),
                rule=action.get("rule", {}),
                success=success
            )

            self._remediation_history.append(remediation)
            self._last_remediation[device_id] = datetime.now()

    # ==========================================
    # Public API
    # ==========================================

    def get_remediations(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get remediation history."""
        with self._lock:
            history = list(self._remediation_history)
            if limit:
                history = history[-limit:]

            return [
                {
                    "remediation_id": r.remediation_id,
                    "device_id": r.device_id,
                    "anomaly_type": r.anomaly_type,
                    "anomaly_score": r.anomaly_score,
                    "action_type": r.action_type,
                    "rule": r.rule,
                    "success": r.success,
                    "timestamp": r.timestamp.isoformat(),
                    "rolled_back": r.rolled_back
                }
                for r in history
            ]

    def trigger_manual_remediation(
        self,
        device_id: str,
        anomaly_type: str
    ) -> Dict[str, Any]:
        """Manually trigger remediation for testing."""
        self._initialize_components()

        anomaly = {
            "type": anomaly_type,
            "score": -1.0,
            "timestamp": datetime.now().isoformat(),
            "device_id": device_id
        }

        # Get flows from ONOS
        flows = self._onos_client.get_flows(device_id) if self._onos_client else []

        # Generate remediation
        action = self._intent_parser.generate_remediation(anomaly, flows)

        if not action:
            return {"success": False, "error": "Could not generate remediation"}

        # Deploy
        success = self._deploy_remediation(device_id, action)
        self._record_remediation(device_id, anomaly, action, success)

        return {
            "success": success,
            "action": action
        }

    def is_running(self) -> bool:
        """Check if feedback loop is running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if feedback loop is paused."""
        return self._paused

    def reset_all(self) -> None:
        """Clear remediation history and cooldowns."""
        with self._lock:
            self._remediation_history.clear()
            self._last_remediation.clear()
            self._remediation_counter = 0
        logger.info("FeedbackLoop reset completed")

    def get_status(self) -> Dict[str, Any]:
        """Get feedback loop status."""
        with self._lock:
            return {
                "running": self._running,
                "paused": self._paused,
                "check_interval": self._check_interval,
                "cooldown_seconds": self._cooldown,
                "total_remediations": len(self._remediation_history),
                "devices_in_cooldown": [
                    did for did, t in self._last_remediation.items()
                    if (datetime.now() - t).total_seconds() < self._cooldown
                ]
            }


# Singleton instance
_loop_instance: Optional[FeedbackLoop] = None


def get_feedback_loop() -> FeedbackLoop:
    """Get or create the global feedback loop instance."""
    global _loop_instance
    if _loop_instance is None:
        _loop_instance = FeedbackLoop()
    return _loop_instance


if __name__ == "__main__":
    # Test feedback loop
    print("\n=== Feedback Loop Test ===\n")

    loop = FeedbackLoop()

    print(f"Status: {loop.get_status()}")

    # Test manual remediation
    print("\nTriggering manual remediation...")
    result = loop.trigger_manual_remediation(
        "of:0000000000000001",
        "traffic_spike"
    )
    print(f"Success: {result.get('success')}")
    if result.get("action"):
        print(f"Action type: {result['action'].get('action_type')}")

    # Get history
    print("\nRemediation history:")
    for r in loop.get_remediations():
        print(f"  [{r['timestamp']}] {r['device_id']}: "
              f"{r['anomaly_type']} -> {r['action_type']} "
              f"({'OK' if r['success'] else 'FAILED'})")

"""
FastAPI Backend for LLM-NetAuto-SDN.

REST API for the SDN automation system.
Base URL: http://127.0.0.1:8000
"""

import os
import sys
import time
import threading
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

import json


# ==========================================
# Pydantic Models
# ==========================================

class IntentRequest(BaseModel):
    """Request model for intent submission."""
    intent: str = Field(..., description="Natural language intent")
    validate: bool = Field(True, description="Validate before deploy")


class IntentResponse(BaseModel):
    """Response model for intent submission."""
    success: bool
    intent: str
    parsed_rule: Optional[Dict] = None
    deployment_method: str = ""
    onos_response: Optional[Any] = None
    latency_ms: float = 0.0
    summary: str = ""
    validation: Optional[Dict] = None
    similar_past_intents: List[Dict] = []
    mode: str = "demo"
    error: Optional[str] = None


class FlowRequest(BaseModel):
    """Request for manual flow deployment."""
    device_id: str
    priority: int = 40000
    match: Dict = Field(default_factory=dict)
    action: str = "DROP"


class AnomalyRequest(BaseModel):
    """Request to inject anomaly."""
    device_id: str
    anomaly_type: str
    duration_seconds: int = 60


class LinkRequest(BaseModel):
    """Request to change link state."""
    device1: str
    device2: str
    state: str = "down"


class TrafficRequest(BaseModel):
    """Request to change traffic scenario."""
    scenario: str = "normal"


class TopologyConfigRequest(BaseModel):
    """Request to update topology configuration."""
    n_switches: int = Field(..., ge=2, le=8, description="Number of OVS switches (2-8)")
    hosts_per_switch: int = Field(..., ge=1, le=4, description="Hosts per switch (1-4)")
    launch_mininet: bool = Field(False, description="Launch Mininet after saving config")
    controller_ip: str = Field("127.0.0.1", description="ONOS controller IP")
    controller_port: int = Field(6653, description="ONOS OpenFlow port")



# ==========================================
# Global State
# ==========================================

class AppState:
    """Application state container."""

    def __init__(self):
        self.demo_mode = False
        self.started_at = datetime.now()

        # Intent history tracking (in-memory per-session only)
        self._history_lock = threading.Lock()
        self.intent_history = []

        # Components (lazy loaded)
        self._onos_client = None
        self._intent_parser = None
        self._rag_engine = None
        self._telemetry_collector = None
        self._anomaly_detector = None
        self._alert_manager = None
        self._feedback_loop = None
        self._metrics_exporter = None
        self._intent_builder = None
        self._flow_builder = None
        self._topology = None
        self._onos_available_flag = False
        self._initialized = False

    @property
    def _onos_available(self) -> bool:
        """Check if ONOS is reachable and has active devices."""
        if self._onos_client is None:
            return False
        try:
            if self._onos_client.health_check():
                devices = self._onos_client.get_devices()
                if devices:
                    self._onos_available_flag = True
                    return True
        except Exception:
            pass
        return getattr(self, '_onos_available_flag', False)

    @_onos_available.setter
    def _onos_available(self, value: bool):
        self._onos_available_flag = value

    @property
    def onos_available(self) -> bool:
        """Check if ONOS is reachable."""
        if self._onos_client is None:
            return False
        try:
            return self._onos_client.health_check()
        except Exception:
            return False

    def _get_devices(self):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_devices() or []
        except Exception:
            return []

    def _get_hosts(self):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_hosts() or []
        except Exception:
            return []

    def _get_links(self):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_links() or []
        except Exception:
            return []

    def _get_flows(self, device_id=None):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_flows(device_id) or []
        except Exception:
            return []

    def _get_intents(self):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_intents() or []
        except Exception:
            return []

    def _post_intent(self, intent_json):
        if not self._onos_client:
            return {"error": "ONOS not connected"}
        try:
            return self._onos_client.post_intent(intent_json)
        except Exception as e:
            return {"error": str(e)}

    def _post_flow(self, device_id, flow_json):
        if not self._onos_client:
            return {"error": "ONOS not connected"}
        try:
            return self._onos_client.post_flow(device_id, flow_json)
        except Exception as e:
            return {"error": str(e)}

    def _get_port_stats(self, device_id=None):
        if not self._onos_client:
            return []
        try:
            return self._onos_client.get_port_stats(device_id) or []
        except Exception:
            return []

    def initialize(self):
        """Initialize all components (live mode only)."""
        if self._initialized:
            return
        logger.info("Initializing app components (live mode)")

        # Connect to real ONOS
        try:
            from controller.onos_client import get_onos_client
            self._onos_client = get_onos_client()
            self._onos_available = self._onos_client.health_check()
            if self._onos_available:
                devices = self._onos_client.get_devices()
                if not devices:
                    logger.warning("ONOS is connected but has 0 devices. Mininet is likely offline.")
                else:
                    logger.info("ONOS controller connected with active devices")
            else:
                logger.warning("ONOS not reachable — telemetry and anomaly detection will be inactive")
        except Exception as e:
            logger.warning(f"Could not initialize ONOS client: {e}")
            self._onos_available = False

        from llm.intent_parser import get_intent_parser
        from llm.rag_engine import get_rag_engine
        from monitoring.telemetry_collector import get_telemetry_collector
        from monitoring.anomaly_detector import get_anomaly_detector
        from monitoring.alert_manager import get_alert_manager
        from monitoring.feedback_loop import get_feedback_loop
        from monitoring.metrics_exporter import get_metrics_exporter
        from netconfig.intent_builder import get_intent_builder
        from netconfig.flow_builder import get_flow_builder
        from controller.topology_manager import get_topology_manager

        self._intent_parser = get_intent_parser()
        self._rag_engine = get_rag_engine()
        self._telemetry_collector = get_telemetry_collector()
        self._anomaly_detector = get_anomaly_detector()
        self._alert_manager = get_alert_manager()
        self._feedback_loop = get_feedback_loop()
        self._metrics_exporter = get_metrics_exporter()
        self._intent_builder = get_intent_builder()
        self._flow_builder = get_flow_builder()
        self._topology = get_topology_manager()

        # Populate topology manager from ONOS if available
        if self._onos_available:
            try:
                self._topology.update_from_onos({
                    "devices": self._onos_client.get_devices(),
                    "hosts": self._onos_client.get_hosts(),
                    "links": self._onos_client.get_links()
                })
            except Exception:
                pass

        # Seed RAG
        try:
            from topology.topology_seed import TopologySeed
            seeder = TopologySeed()
            seeder.seed_rag()
        except Exception as e:
            logger.warning(f"RAG seeding failed: {e}")

        # Start background services
        self._telemetry_collector.start()
        self._feedback_loop.start()

        self._initialized = True
        logger.info(f"App initialization complete (ONOS={'connected' if self._onos_available else 'unreachable'})")

    def _load_intent_history(self) -> None:
        self.intent_history = []

    def _save_intent_history(self) -> None:
        return


# Global state
state = AppState()


def ensure_initialized():
    """Ensure state is initialized."""
    if not state._initialized:
        state.initialize()


# ==========================================
# FastAPI App
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    state.initialize()
    yield
    # Shutdown
    if state._telemetry_collector:
        state._telemetry_collector.stop()
    if state._feedback_loop:
        state._feedback_loop.stop()


app = FastAPI(
    title="LLM-NetAuto REST API",
    description="REST API for LLM-Based Network Automation with Real-Time Monitoring in SDN",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Health Endpoints
# ==========================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "demo_mode": state.demo_mode,
        "uptime_seconds": (datetime.now() - state.started_at).total_seconds(),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/metrics/summary")
async def metrics_summary():
    """Get metrics summary."""
    telemetry_stats = {}
    if state._telemetry_collector:
        telemetry_stats = state._telemetry_collector.get_statistics()

    anomaly_status = {}
    if state._anomaly_detector:
        anomaly_status = state._anomaly_detector.get_status()

    alert_stats = {}
    if state._alert_manager:
        alert_stats = state._alert_manager.get_statistics()

    return {
        "telemetry": telemetry_stats,
        "anomaly_detector": anomaly_status,
        "alerts": alert_stats,
        "timestamp": datetime.now().isoformat()
    }


# ==========================================
# Intent Endpoints
# ==========================================

@app.post("/intent", response_model=IntentResponse)
async def submit_intent(request: IntentRequest):
    """Submit a natural language intent."""
    ensure_initialized()
    start_time = time.time()
    import uuid

    history_id = uuid.uuid4().hex
    pending_history = {
        "id": history_id,
        "timestamp": datetime.now().isoformat(),
        "intent": request.intent,
        "intent_type": "processing",
        "success": False,
        "latency_ms": 0.0,
        "deployment_method": "pending",
        "summary": "Processing intent...",
        "deployment_time": None,
        "affected_devices": [],
        "onos_app_id": None,
        "onos_key": None,
        "onos_response": None,
        "status": "processing"
    }

    with state._history_lock:
        state.intent_history.insert(0, pending_history)
        if len(state.intent_history) > 100:
            state.intent_history = state.intent_history[:100]

    try:
        # Get topology in a format suitable for the LLM
        devices = state._get_devices()
        hosts = state._get_hosts()
        links = state._get_links()

        # Build simplified topology for LLM
        topology = {
            "devices": [
                {"id": d.get("id"), "name": d.get("annotations", {}).get("name", d.get("id"))}
                for d in devices
            ],
            "hosts": [
                {
                    "name": h.get("name") or h.get("id", ""),
                    "ip": (h.get("ipAddresses") or [None])[0],
                    "ips": h.get("ipAddresses", []),
                    "mac": h.get("mac"),
                    "device": (h.get("locations") or [{}])[0].get("elementId"),
                    "port": int((h.get("locations") or [{}])[0].get("port") or 0)
                }
                for h in hosts
            ],
            "links": [
                {
                    "src": (l.get("src") or {}).get("device"),
                    "dst": (l.get("dst") or {}).get("device"),
                    "src_device": (l.get("src") or {}).get("device"),
                    "dst_device": (l.get("dst") or {}).get("device"),
                    "bandwidth": int((l.get("annotations") or {}).get("bandwidth", 0) or 0),
                    "delay": int((l.get("annotations") or {}).get("delay", 0) or 0),
                    "state": l.get("state", "ACTIVE")
                }
                for l in links
            ]
        }

        # Parse intent
        result = state._intent_parser.parse_intent(request.intent, topology)

        # Deploy if successful
        deployment_response = None
        deployment_method = "none"

        if result.get("success") and result.get("parsed_rule"):
            rule = result["parsed_rule"]

            # Force block, isolate, rate_limit, prioritize, and mirror intents to use direct Flow Rules.
            # Direct switch-level OpenFlow rules are much more robust and support drops, queues, limits, and mirrors.
            if rule.get("intent_type") in ["block", "isolate", "rate_limit", "prioritize", "mirror"]:
                rule["use_intent_framework"] = False

            if rule.get("action") == "remove" and rule.get("intent_type") == "clear_all":
                # Clear all custom intents and flows
                await clear_intent_history(delete_onos=True)
                deployment_method = "clear_all"
                deployment_response = {"status": "success", "message": "Cleared all rules"}
            elif rule.get("use_intent_framework"):
                # Build and deploy intent
                intent_json = state._intent_builder.build_intent(rule, topology)
                if intent_json:
                    deployment_response = state._post_intent(intent_json)
                    deployment_method = "intent_framework"
            else:
                # Build and deploy flow rules
                flows = state._flow_builder.build_flows(rule, topology)
                if flows:
                    responses = []
                    for flow in flows:
                        device_id = flow.get("deviceId", "of:0000000000000001")
                        r = state._post_flow(device_id, flow)
                        responses.append(r)
                    deployment_response = responses
                    deployment_method = "flow_rule"

        # Get similar intents from RAG
        similar = state._rag_engine.get_similar_intents(request.intent, n=3)

        # Index successful intent
        if result.get("success"):
            state._rag_engine.index_intent(
                request.intent,
                result.get("parsed_rule", {}),
                {"success": True}
            )
            if state._metrics_exporter:
                state._metrics_exporter.record_intent_success()
        else:
            if state._metrics_exporter:
                state._metrics_exporter.record_intent_failure()

        latency = (time.time() - start_time) * 1000

        if state._metrics_exporter:
            state._metrics_exporter.record_llm_latency(latency / 1000)

        response = IntentResponse(
            success=result.get("success", False),
            intent=request.intent,
            parsed_rule=result.get("parsed_rule"),
            deployment_method=deployment_method,
            onos_response=deployment_response,
            latency_ms=latency,
            summary=result.get("summary", ""),
            validation=result.get("validation"),
            similar_past_intents=similar,
            mode="live",
            error=result.get("error")
        )

        # Update the pending history entry in-place so the submitted intent is visible immediately.
        try:
            hist_entry = pending_history
            parsed_rule_data = result.get("parsed_rule", {}) or {}
            hist_entry.update({
                "timestamp": hist_entry.get("timestamp") or datetime.now().isoformat(),
                "intent_type": parsed_rule_data.get("intent_type") or hist_entry.get("intent_type"),
                "success": response.success,
                "latency_ms": response.latency_ms,
                "deployment_method": response.deployment_method,
                "summary": response.summary or hist_entry.get("summary"),
                "deployment_time": datetime.now().isoformat() if response.success else None,
                "affected_devices": hist_entry.get("affected_devices", []),
                "onos_app_id": None,
                "onos_key": None,
                "onos_response": response.onos_response,
                "status": "completed" if response.success else "failed",
                "src": parsed_rule_data.get("src_host") or parsed_rule_data.get("src_device") or "",
                "dst": parsed_rule_data.get("dst_host") or parsed_rule_data.get("dst_device") or ""
            })

            # If an intent JSON had a key, record it
            if isinstance(deployment_response, dict):
                hist_entry["onos_response"] = deployment_response
                key = deployment_response.get("key") or deployment_response.get("intentId") or deployment_response.get("id")
                if key:
                    hist_entry["onos_key"] = key
                    app_id_val = deployment_response.get("appId")
                    if not app_id_val and state._onos_client:
                        app_id_val = state._onos_client.config.app_id
                    hist_entry["onos_app_id"] = app_id_val or "org.onosproject.cli"

            # If flows were installed record affected devices
            if isinstance(deployment_response, list):
                devs = set()
                for r in deployment_response:
                    if isinstance(r, dict):
                        d = r.get("deviceId") or r.get("device")
                        if d:
                            devs.add(d)
                hist_entry["affected_devices"] = list(devs)

            # If parsed rule contains host src/dst, try to resolve switches on path
            try:
                parsed = result.get("parsed_rule", {}) or {}
                src = parsed.get("src_host") or parsed.get("src_device")
                dst = parsed.get("dst_host") or parsed.get("dst_device")
                if src and dst:
                    # use topology manager to compute switches on path
                    try:
                        switches = state._topology.get_switches_on_path(src, dst)
                        hist_entry["affected_devices"].extend(switches)
                    except Exception:
                        pass
            except Exception:
                pass

            # Ensure the pending history entry remains the latest item.
            with state._history_lock:
                for idx, item in enumerate(state.intent_history):
                    if item.get("id") == history_id:
                        state.intent_history[idx] = hist_entry
                        break

        except Exception as e:
            logger.warning(f"Failed to record intent history: {e}")
            # Fallback: ensure at least a minimal history entry is stored
            try:
                fallback = {
                    "id": history_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": request.intent,
                    "success": bool(result.get("success", False)),
                    "latency_ms": latency,
                    "summary": result.get("summary", ""),
                    "deployment_method": deployment_method,
                    "affected_devices": [],
                    "status": "completed" if result.get("success", False) else "failed"
                }
                with state._history_lock:
                    for idx, item in enumerate(state.intent_history):
                        if item.get("id") == history_id:
                            state.intent_history[idx] = fallback
                            break
            except Exception:
                logger.exception("Failed to write fallback history entry")

        return response

    except Exception as e:
        logger.error(f"Intent processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/intents")
async def get_intents():
    """Get all intents (enriched with affected devices when possible)."""
    ensure_initialized()
    intents = state._get_intents()

    # Add custom flow rule intents from history so they are displayed as active intents
    custom_intents = []
    with state._history_lock:
        for h in state.intent_history:
            if h.get("success") and h.get("deployment_method") == "flow_rule":
                # Avoid duplicates
                if any(it.get("key") == h.get("id") for it in intents):
                    continue
                custom_intents.append({
                    "key": h.get("id"),
                    "appId": h.get("onos_app_id") or "org.onosproject.llm",
                    "type": h.get("intent_type") or "FlowRuleIntent",
                    "priority": 100,
                    "state": "INSTALLED",
                    "one": h.get("src") or h.get("intent"),
                    "two": h.get("dst") or "",
                    "affected_devices": h.get("affected_devices") or []
                })

    all_intents = list(intents) + custom_intents
    enriched = []
    for it in all_intents:
        try:
            item = dict(it) if isinstance(it, dict) else {}
            if not item:
                continue
            # Attempt to compute affected devices from host-to-host intents
            affected = item.get("affected_devices") or []
            one = item.get("one") or item.get("src") or item.get("ingressPoint")
            two = item.get("two") or item.get("dst") or item.get("egressPoint")

            def resolve_to_switch(val):
                if not val:
                    return None
                if isinstance(val, dict):
                    return val.get("device")
                if isinstance(val, str) and "/" in val:
                    mac = val.split("/")[0]
                    try:
                        h = state._topology.get_host_by_mac(mac)
                        if h:
                            return h.location_device
                    except Exception:
                        pass
                return None

            s1 = resolve_to_switch(one)
            s2 = resolve_to_switch(two)
            if s1 and s2:
                try:
                    path_switches = state._topology.get_shortest_path(s1, s2)
                    affected.extend([p for p in path_switches if p in [d.id for d in state._topology.get_all_devices()]])
                except Exception:
                    pass

            item["affected_devices"] = list(set(affected))
            enriched.append(item)
        except Exception:
            if isinstance(it, dict):
                enriched.append(it)

    return {"intents": enriched}


@app.delete("/intent/history/{hist_id}")
async def delete_intent_history(hist_id: str):
    """Delete an entry from intent history and remove any deployed intent or flow rules from ONOS."""
    ensure_initialized()
    removed = None
    with state._history_lock:
        for i, e in enumerate(list(state.intent_history)):
            if e.get("id") == hist_id:
                removed = state.intent_history.pop(i)
                break

    if removed:
        # If it references flow rules or an intent, try to remove them from backend
        try:
            if removed.get("deployment_method") == "flow_rule":
                responses = removed.get("onos_response")
                if isinstance(responses, list):
                    for resp in responses:
                        if isinstance(resp, dict):
                            dev_id = resp.get("deviceId") or resp.get("device")
                            flow_id = resp.get("id") or resp.get("flowId")
                            if dev_id and flow_id:
                                try:
                                    if state._onos_available and state._onos_client:
                                        state._onos_client.delete_flow(dev_id, flow_id)
                                    elif state._network_sim:
                                        state._network_sim.delete_flow(dev_id, flow_id)
                                except Exception as ex:
                                    logger.warning(f"Failed to delete flow {flow_id} on {dev_id}: {ex}")
            else:
                app_id = None
                key = None
                if isinstance(removed.get("onos_response"), dict):
                    app_id = removed["onos_response"].get("appId")
                    key = removed["onos_response"].get("key")
                app_id = app_id or removed.get("onos_app_id")
                key = key or removed.get("onos_key")
                if app_id and key:
                    if state._onos_available and state._onos_client:
                        state._onos_client.delete_intent(app_id, key)
                    elif state._network_sim:
                        state._network_sim.delete_intent(app_id, key)
        except Exception:
            logger.warning("Failed to delete remote elements for history entry")
        return {"success": True, "deleted": removed}
    
    return {"success": False, "error": "History entry not found"}


@app.delete("/intent/history")
async def clear_intent_history(delete_onos: bool = True):
    """Clear in-memory intent history. Optionally delete corresponding ONOS intents and flow rules."""
    ensure_initialized()
    entries = []
    with state._history_lock:
        entries = list(state.intent_history)
        state.intent_history = []

    if delete_onos:
        for e in entries:
            try:
                if e.get("deployment_method") == "flow_rule":
                    responses = e.get("onos_response")
                    if isinstance(responses, list):
                        for resp in responses:
                            if isinstance(resp, dict):
                                dev_id = resp.get("deviceId") or resp.get("device")
                                flow_id = resp.get("id") or resp.get("flowId")
                                if dev_id and flow_id:
                                    try:
                                        if state._onos_available and state._onos_client:
                                            state._onos_client.delete_flow(dev_id, flow_id)
                                        elif state._network_sim:
                                            state._network_sim.delete_flow(dev_id, flow_id)
                                    except Exception as ex:
                                        logger.warning(f"Failed to delete flow {flow_id} on {dev_id}: {ex}")
                else:
                    app_id = None
                    key = None
                    if isinstance(e.get("onos_response"), dict):
                        app_id = e["onos_response"].get("appId")
                        key = e["onos_response"].get("key")
                    app_id = app_id or e.get("onos_app_id")
                    key = key or e.get("onos_key")
                    if app_id and key:
                        if state._onos_available and state._onos_client:
                            state._onos_client.delete_intent(app_id, key)
                        elif state._network_sim:
                            state._network_sim.delete_intent(app_id, key)
            except Exception:
                continue

    return {"success": True, "cleared": len(entries)}


@app.get("/intent/history")
async def get_intent_history(limit: int = 50):
    """Get recent intent submission history (newest first)."""
    ensure_initialized()
    with state._history_lock:
        return {"history": state.intent_history[:limit]}
@app.delete("/intent/{app_id}/{key}")
async def delete_intent(app_id: str, key: str):
    """Delete an intent and remove related history entries."""
    ensure_initialized()
    success = False

    # Find history entry matching this key
    target_hist = None
    with state._history_lock:
        for h in state.intent_history:
            if h.get("id") == key or h.get("onos_key") == key:
                target_hist = h
                break

    if target_hist:
        success = True
        # If it was deployed using direct flow rules, delete them!
        if target_hist.get("deployment_method") == "flow_rule":
            responses = target_hist.get("onos_response")
            if isinstance(responses, list):
                for resp in responses:
                    if isinstance(resp, dict):
                        dev_id = resp.get("deviceId") or resp.get("device")
                        flow_id = resp.get("id") or resp.get("flowId")
                        if dev_id and flow_id:
                            try:
                                if state._onos_available and state._onos_client:
                                    state._onos_client.delete_flow(dev_id, flow_id)
                                elif state._network_sim:
                                    state._network_sim.delete_flow(dev_id, flow_id)
                            except Exception as e:
                                logger.warning(f"Failed to delete flow {flow_id} on {dev_id}: {e}")
        # If deployed via intent framework, delete intent
        elif target_hist.get("deployment_method") == "intent_framework":
            onos_key = target_hist.get("onos_key")
            onos_app = target_hist.get("onos_app_id") or app_id
            if onos_key:
                try:
                    if state._onos_available and state._onos_client:
                        state._onos_client.delete_intent(onos_app, onos_key)
                    elif state._network_sim:
                        state._network_sim.delete_intent(onos_app, onos_key)
                except Exception as e:
                    logger.warning(f"Failed to delete intent {onos_key}: {e}")

        # Remove from history
        with state._history_lock:
            state.intent_history = [h for h in state.intent_history if h.get("id") != key and h.get("onos_key") != key]
    else:
        # Fallback to standard ONOS/sim deletion
        if state._onos_available and state._onos_client:
            success = state._onos_client.delete_intent(app_id, key)
        elif state._network_sim:
            success = state._network_sim.delete_intent(app_id, key)

        # Remove any matching history items
        with state._history_lock:
            state.intent_history = [h for h in state.intent_history if not (
                (h.get("onos_key") and h.get("onos_key") == key) or
                (isinstance(h.get("onos_response"), dict) and h["onos_response"].get("key") == key)
            )]

    return {"success": success}


@app.post("/intent/clear-all")
async def clear_all_intents():
    """Delete all user intents, flow rules, and submission history to start clean."""
    ensure_initialized()
    
    # 1. Clear intent history in state
    with state._history_lock:
        state.intent_history.clear()
    
    # 2. Get and delete all intents from ONOS
    if state._onos_available and state._onos_client:
        try:
            intents = state._onos_client.get_intents()
            for intent in intents:
                key = intent.get("key")
                app_id = intent.get("appId")
                if key and app_id:
                    state._onos_client.delete_intent(app_id, key)
        except Exception as e:
            logger.warning(f"Error clearing ONOS intents: {e}")
            
        # 3. Delete flows by application ID
        try:
            state._onos_client.delete_flows_by_app("org.onosproject.cli")
            state._onos_client.delete_flows_by_app("org.onosproject.llm")
            state._onos_client.delete_flows_by_app("org.onosproject.rest")
        except Exception as e:
            logger.warning(f"Error clearing app flows: {e}")
            
    return {"success": True, "message": "All flows, intents, and submission history cleared successfully"}


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []



@app.post("/copilot/chat")
async def copilot_chat(request: ChatRequest):
    """AI Copilot chat: uses intelligent pattern-based responder first, LLM fallback for open-ended."""
    ensure_initialized()

    # 1. Fetch live network state
    devices = state._get_devices()
    hosts = state._get_hosts()
    links = state._get_links()
    alerts = state._alert_manager.get_active_alerts() if state._alert_manager else []
    anomalies = state._anomaly_detector.get_anomaly_history() if state._anomaly_detector else []

    response = None

    # 2. Try context-enriched LLM first for highly personalized and accurate conversational replies
    if state._intent_parser and state._intent_parser._llm:
        try:
            avail_switches = [f"s{d.get('id','').split(':')[-1].lstrip('0') or '0'} ({'🟢 Available' if d.get('available') else '🔴 Unavailable'})" for d in devices]
            host_connections = [
                f"{h.get('ipAddresses',['N/A'])[0]} (MAC: {h.get('mac','')}) ➡️ s{h.get('locations',[{}])[0].get('elementId','').split(':')[-1].lstrip('0') or 'N/A'}"
                for h in hosts
            ]
            active_links = []
            for l in links:
                src_dev = l.get('src',{}).get('device','')
                dst_dev = l.get('dst',{}).get('device','')
                if src_dev and dst_dev:
                    src_num = src_dev.split(':')[-1].lstrip('0') or '0'
                    dst_num = dst_dev.split(':')[-1].lstrip('0') or '0'
                    active_links.append(f"s{src_num} ➡️ s{dst_num}")
            
            alerts_str = ", ".join(f"[{a.get('severity','INFO')}] {a.get('title','')}" for a in alerts) if alerts else "No active alerts (Network Healthy 🟢)"
            anoms_str = f"{len(anomalies)} anomalies detected today" if anomalies else "No anomalies detected"

            ctx = (
                f"LIVE NETWORK TELEMETRY CONTEXT:\n"
                f"- Active Switches ({len([d for d in devices if d.get('available')])}): {', '.join(avail_switches) if avail_switches else 'None'}\n"
                f"- Hosts Discovered ({len(hosts)}): {', '.join(host_connections) if host_connections else 'None'}\n"
                f"- Topology Links ({len(links)}): {', '.join(active_links) if active_links else 'None'}\n"
                f"- Alert Manager active alerts: {alerts_str}\n"
                f"- Anomaly Detector state: {anoms_str}\n"
            )

            # Build conversation history
            history_str = ""
            if request.history:
                for msg in request.history[-6:]:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    history_str += f"{role}: {msg.get('content')}\n"

            prompt = (
                f"You are an SDN AI Copilot, a highly intelligent conversational network assistant for LLM-NetAuto-SDN.\n"
                f"You have live access to the network state. Use the following dynamic system status to answer the user's question accurately.\n\n"
                f"{ctx}\n\n"
                f"Guidelines:\n"
                f"1. Be precise, concise, and specific. If the user asks which hosts are connected to a specific switch (e.g. s3), list only the hosts connected to s3 based on the context.\n"
                f"2. If asked how to isolate a switch (e.g. s2), tell them they can submit 'Isolate switch s2' or 'Isolate switch s2 from the network' in the Intent Control panel to block all traffic traversing s2.\n"
                f"3. Maintain a helpful, professional, and friendly technical tone.\n\n"
                f"{history_str}"
                f"User: {request.message}\n"
                f"Assistant:"
            )

            llm_resp = state._intent_parser._invoke_llm(prompt, timeout=20)
            if llm_resp and llm_resp.strip():
                response = llm_resp.strip()
        except Exception as e:
            logger.warning(f"AI Copilot LLM execution failed, falling back to pattern-based responder: {e}")

    # 3. Pattern-based Fallback if LLM is offline or fails
    if response is None:
        msg_lower = request.message.lower()
        import re
        ip_match = re.search(r"10\.0\.0\.\d+", msg_lower)
        target_ip = ip_match.group(0) if ip_match else None

        # --- Specific host IP query ---
        if target_ip:
            h = next((x for x in hosts if target_ip in x.get("ipAddresses", [])), None)
            if h:
                loc = h.get("locations", [{}])[0]
                sw_id = loc.get("elementId", "")
                sw_num = sw_id.split(":")[-1].lstrip("0") or "0" if sw_id else "N/A"
                port = loc.get("port", "N/A")
                response = (
                    f"👥 **Host {target_ip}**:\n\n"
                    f"- **MAC**: `{h.get('mac', 'N/A')}`\n"
                    f"- **Switch**: **s{sw_num}** (`{sw_id}`) Port **{port}**\n"
                    f"- **Status**: Active 🟢"
                )
            else:
                response = f"⚠️ Host **{target_ip}** not found. {len(hosts)} hosts discovered. Run `pingall` in Mininet to trigger discovery."

        # --- Switch query ---
        elif any(w in msg_lower for w in ["switch", "device"]):
            target_sw = None
            for i in range(1, 20):
                if f"s{i}" in msg_lower or f"switch {i}" in msg_lower:
                    target_sw = f"of:{'0' * (16 - len(str(i)))}{i}"
                    break
            if target_sw:
                dev = next((d for d in devices if d.get("id") == target_sw), None)
                if dev:
                    sw_num = target_sw.split(":")[-1].lstrip("0") or "0"
                    sw_hosts = [h for h in hosts if any(loc.get("elementId") == target_sw for loc in h.get("locations", []))]
                    host_list = ", ".join(h.get("ipAddresses", ["N/A"])[0] for h in sw_hosts) or "None"
                    response = (
                        f"🖥️ **Switch s{sw_num}**:\n\n"
                        f"- **ID**: `{dev.get('id')}`\n"
                        f"- **Status**: {'Available 🟢' if dev.get('available') else 'Unavailable 🔴'}\n"
                        f"- **HW/SW**: `{dev.get('hw', 'OVS')} / {dev.get('sw', 'N/A')}`\n"
                        f"- **Hosts** ({len(sw_hosts)}): {host_list}"
                    )
                else:
                    response = f"⚠️ Switch `{target_sw}` not found in ONOS."
            else:
                avail = [d for d in devices if d.get("available")]
                response = f"🖥️ **{len(avail)} available switches** (of {len(devices)} total):\n\n" + "\n".join(
                    f"- **s{d.get('id','').split(':')[-1].lstrip('0') or '0'}**: {'🟢' if d.get('available') else '🔴'}"
                    for d in devices
                )

        # --- Host listing ---
        elif "host" in msg_lower:
            if hosts:
                response = f"👥 **{len(hosts)} Hosts**:\n\n" + "\n".join(
                    f"- **{h.get('ipAddresses',['N/A'])[0]}** (MAC: `{h.get('mac','')}`) → s{h.get('locations',[{}])[0].get('elementId','').split(':')[-1].lstrip('0') or 'N/A'}"
                    for h in hosts
                )
            else:
                response = "👥 No hosts discovered. Run `pingall` in Mininet."

        # --- Flow rules ---
        elif "flow" in msg_lower or "rule" in msg_lower:
            response = (
                "⚙️ **Flow Rules**:\n\n"
                "1. 🔒 **System Flows** (`org.onosproject.core`/`fwd`): Auto-installed for LLDP, ARP, forwarding.\n"
                "2. 👤 **Custom Flows** (`org.onosproject.cli`/`rest`): Your policies from Intent Control.\n\n"
                "Use the **Flow Manager** filter to toggle between them!"
            )

        # --- Examples / how-to ---
        elif any(w in msg_lower for w in ["example", "command", "how to", "help"]):
            response = (
                "💡 **Intent Examples** (use on Intent Control page):\n\n"
                "- *\"Block all traffic from 10.0.0.1\"*\n"
                "- *\"Allow only HTTP traffic from h1 to h3\"*\n"
                "- *\"Drop all ICMP packets on all switches\"*\n"
                "- *\"Rate limit h5 to 10 Mbps\"*\n"
                "- *\"Isolate switch s2\"*\n"
                "- *\"Remove all custom flow rules\"*"
            )

        # --- Policy / intent ---
        elif any(w in msg_lower for w in ["block", "allow", "isolate", "limit", "policy", "intent"]):
            response = (
                "🛡️ **Policy Configuration**:\n\n"
                "1. **Manual**: Use **Intent Control** page with natural language\n"
                "2. **Automatic**: Anomaly detection auto-mitigates threats\n\n"
                "Example: *\"Block all traffic from 10.0.0.5\"*"
            )

        # --- ONOS / controller ---
        elif any(w in msg_lower for w in ["onos", "controller", "mininet", "openflow"]):
            response = (
                "🎮 **SDN Infrastructure**:\n\n"
                "- **ONOS**: SDN controller with REST API for topology/intent management\n"
                "- **Mininet**: Network emulator simulating switches & hosts\n"
                "- **OpenFlow 1.3**: Protocol between switches and controller"
            )

        # --- Alerts / health ---
        elif any(w in msg_lower for w in ["alert", "health", "anomal"]):
            if not alerts:
                response = f"🟢 **Network Healthy**: 0 active alerts, {len(anomalies)} anomalies detected today."
            else:
                response = "🚨 **Alerts**:\n\n" + "\n".join(f"- [{a.get('severity')}] {a.get('title')}" for a in alerts)

        # --- Topology / status / overview ---
        elif any(w in msg_lower for w in ["topology", "network", "status", "overview", "summary", "how many"]):
            avail = [d for d in devices if d.get("available")]
            response = (
                f"📊 **Network Summary**:\n\n"
                f"- 🖥️ {len(avail)} Active Switches\n"
                f"- 👥 {len(hosts)} Hosts\n"
                f"- 🔗 {len(links)} Links\n"
                f"- 🚨 {len(alerts)} Alerts"
            )

        # --- About project ---
        elif any(w in msg_lower for w in ["what is", "explain", "about", "project"]):
            response = (
                "📚 **LLM-NetAuto-SDN**: LLM-based network automation with real-time monitoring.\n\n"
                "- 🧠 LLM translates natural language → OpenFlow rules\n"
                "- 📊 Real-time telemetry from ONOS\n"
                "- 🤖 ML anomaly detection + self-healing"
            )

        # --- Hard Fallback ---
        if response is None:
            response = (
                f"👋 I can help with: switches, hosts, flows, alerts, policies, and more.\n"
                f"Currently: {len([d for d in devices if d.get('available')])} switches, {len(hosts)} hosts active."
            )

    return {"response": response}




# ==========================================
# Flow Endpoints
# ==========================================

@app.get("/flows")
async def get_flows(device_id: Optional[str] = None):
    """Get all flow rules."""
    ensure_initialized()
    flows = state._get_flows(device_id)
    return {"flows": flows}


@app.get("/flows/{device_id}")
async def get_device_flows(device_id: str):
    """Get flows for a specific device."""
    ensure_initialized()
    flows = state._get_flows(device_id)
    return {"flows": flows}


@app.delete("/flow/{device_id}/{flow_id}")
async def delete_flow(device_id: str, flow_id: str):
    """Delete a flow rule."""
    ensure_initialized()
    if state._onos_available and state._onos_client:
        success = state._onos_client.delete_flow(device_id, flow_id)
    elif state._network_sim:
        success = state._network_sim.delete_flow(device_id, flow_id)
    else:
        success = False
    return {"success": success}


# ==========================================
# Topology Endpoints
# ==========================================

@app.get("/topology")
async def get_topology():
    """Get complete network topology."""
    ensure_initialized()
    return {
        "devices": state._get_devices(),
        "hosts": state._get_hosts(),
        "links": state._get_links()
    }


@app.get("/devices")
async def get_devices():
    """Get all network devices."""
    ensure_initialized()
    return {"devices": state._get_devices()}


@app.get("/hosts")
async def get_hosts():
    """Get all network hosts."""
    ensure_initialized()
    return {"hosts": state._get_hosts()}


@app.get("/links")
async def get_links():
    """Get all network links."""
    ensure_initialized()
    return {"links": state._get_links()}


# ==========================================
# Topology Configuration Endpoints
# ==========================================

@app.get("/topology/config")
async def get_topology_config():
    """
    Get current topology configuration (switches + hosts/switch).
    Values come from environment variables TOPO_SWITCHES and TOPO_HOSTS_PER_SWITCH.
    """
    return {
        "n_switches": int(os.getenv("TOPO_SWITCHES", "3")),
        "hosts_per_switch": int(os.getenv("TOPO_HOSTS_PER_SWITCH", "2")),
        "total_hosts": int(os.getenv("TOPO_SWITCHES", "3")) * int(os.getenv("TOPO_HOSTS_PER_SWITCH", "2")),
    }


@app.post("/topology/config")
async def set_topology_config(request: TopologyConfigRequest, background_tasks: BackgroundTasks):
    """
    Update topology configuration and optionally launch Mininet.

    Saves TOPO_SWITCHES and TOPO_HOSTS_PER_SWITCH to the .env file so the
    values persist across restarts. If ``launch_mininet`` is true a new
    Mininet process is started in the background via sudo.
    """
    import re
    import subprocess

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

    def _update_env(key: str, value: str) -> None:
        """Update or append a key=value line in the .env file."""
        if not os.path.exists(env_path):
            with open(env_path, "a") as f:
                f.write(f"\n{key}={value}\n")
            return
        with open(env_path, "r") as f:
            content = f.read()
        pattern = re.compile(rf"^{re.escape(key)}=.*", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{key}={value}", content)
        else:
            content += f"\n{key}={value}\n"
        with open(env_path, "w") as f:
            f.write(content)

    # Clamp and validate
    n = max(2, min(8, request.n_switches))
    hps = max(1, min(4, request.hosts_per_switch))

    # Persist to .env
    _update_env("TOPO_SWITCHES", str(n))
    _update_env("TOPO_HOSTS_PER_SWITCH", str(hps))

    # Also update current process environment so other components pick it up
    os.environ["TOPO_SWITCHES"] = str(n)
    os.environ["TOPO_HOSTS_PER_SWITCH"] = str(hps)

    logger.info(f"Topology config updated: {n} switches, {hps} hosts/switch")

    launch_status = "not_requested"
    if request.launch_mininet:
        def _launch_mininet():
            """Kill existing Mininet and start a new one (password injected via stdin)."""
            sudo_pw = os.getenv("SUDO_PASSWORD", "")
            pw_bytes = f"{sudo_pw}\n".encode() if sudo_pw else None

            try:
                # Forcefully terminate any previous Mininet script process to avoid port/controller conflicts
                kill_proc = subprocess.Popen(
                    ["sudo", "-S", "pkill", "-9", "-f", "mininet_topo.py"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                kill_proc.communicate(input=pw_bytes, timeout=5)

                # Clean up any existing Mininet state (inject password)
                clean_proc = subprocess.Popen(
                    ["sudo", "-S", "mn", "-c"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                clean_proc.communicate(input=pw_bytes, timeout=15)

                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                topo_script = os.path.join(project_root, "topology", "mininet_topo.py")
                log_path = os.path.join(project_root, "logs", "mininet.log")

                cmd = [
                    "sudo", "-S", "python3", topo_script,
                    f"--n-switches={n}",
                    f"--hosts-per-switch={hps}",
                    f"--controller-ip={request.controller_ip}",
                    f"--controller-port={request.controller_port}",
                    "--no-cli",
                ]
                logger.info(f"Launching Mininet: {' '.join(cmd)}")

                log_file = open(log_path, "w")
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=log_file,
                    stderr=log_file,
                )
                # Inject password then close stdin so sudo proceeds
                if pw_bytes:
                    proc.stdin.write(pw_bytes)
                    proc.stdin.flush()
                proc.stdin.close()

                # Write PID for status checks
                pid_file = os.path.join(project_root, "mininet.pid")
                with open(pid_file, "w") as pf:
                    pf.write(str(proc.pid))
                logger.info(f"Mininet launched with PID {proc.pid}")
            except Exception as e:
                logger.error(f"Failed to launch Mininet: {e}")

        background_tasks.add_task(_launch_mininet)
        launch_status = "launching"

    return {
        "success": True,
        "n_switches": n,
        "hosts_per_switch": hps,
        "total_hosts": n * hps,
        "mininet_status": launch_status,
    }


@app.get("/topology/mininet-status")
async def get_mininet_status():
    """Check whether a Mininet process is currently running."""
    import subprocess

    # Check PID file first
    pid_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "mininet.pid"
    )
    pid = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
        except Exception:
            pid = None

    running = False
    if pid:
        try:
            result = subprocess.run(["kill", "-0", str(pid)], capture_output=True)
            running = result.returncode == 0
        except Exception:
            running = False

    # Also check by process name as fallback
    if not running:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "mininet_topo.py"],
                capture_output=True, text=True
            )
            running = result.returncode == 0
        except Exception:
            pass

    return {
        "running": running,
        "pid": pid if running else None,
        "n_switches": int(os.getenv("TOPO_SWITCHES", "3")),
        "hosts_per_switch": int(os.getenv("TOPO_HOSTS_PER_SWITCH", "2")),
    }


@app.get("/stats")
async def get_stats():
    """Get all port statistics."""
    ensure_initialized()
    stats = state._get_port_stats()
    return {"statistics": stats}


@app.get("/stats/{device_id}")
async def get_device_stats(device_id: str):
    """Get stats for a specific device."""
    ensure_initialized()
    stats = state._get_port_stats(device_id)
    return {"statistics": stats}


@app.get("/telemetry/history/{device_id}")
async def get_telemetry_history(device_id: str, n: int = 60):
    """Get telemetry history for a device."""
    history = state._telemetry_collector.get_history(device_id, n)
    return {"device_id": device_id, "history": history}


@app.get("/anomalies")
async def get_anomalies():
    """Get anomaly detector status and history."""
    status = state._anomaly_detector.get_status()
    history = state._anomaly_detector.get_anomaly_history(limit=50)
    return {"status": status, "history": history}


@app.get("/alerts")
async def get_alerts():
    """Get active alerts."""
    active = state._alert_manager.get_active_alerts()
    history = state._alert_manager.get_alert_history(limit=50)
    return {"active": active, "history": history}


@app.get("/remediations")
async def get_remediations():
    """Get remediation history."""
    status = state._feedback_loop.get_status()
    history = state._feedback_loop.get_remediations(limit=50)
    return {"status": status, "history": history}


# ==========================================
# RAG Endpoints
# ==========================================

@app.get("/rag/stats")
async def get_rag_stats():
    """Get RAG engine statistics."""
    return state._rag_engine.get_stats()


@app.post("/rag/seed")
async def seed_rag():
    """Re-seed RAG with current topology."""
    from topology.topology_seed import TopologySeed
    seeder = TopologySeed()
    success = seeder.seed_rag()
    return {"success": success}


@app.get("/rag/similar")
async def get_similar_intents(intent: str = Query(...)):
    """Get similar past intents."""
    similar = state._rag_engine.get_similar_intents(intent, n=5)
    return {"intent": intent, "similar": similar}


# ==========================================
# Comparison Endpoints
# ==========================================

@app.get("/comparison/results")
async def get_comparison_results():
    """Get benchmark comparison results."""
    from comparison.benchmark import Benchmark
    benchmark = Benchmark()
    results = benchmark.load_results()
    return results or {"error": "No benchmark results available"}


@app.post("/comparison/run")
async def run_benchmark(background_tasks: BackgroundTasks):
    """Run benchmark comparison."""
    from comparison.benchmark import Benchmark

    def run():
        benchmark = Benchmark()
        benchmark.run_all()

    background_tasks.add_task(run)
    return {"status": "Benchmark started in background"}


@app.post("/comparison/manual/flow")
async def manual_flow_deploy(request: FlowRequest):
    """Simulate manual flow deployment for comparison."""
    from comparison.traditional_simulator import get_traditional_config_manager

    manager = get_traditional_config_manager()
    task = manager.simulate_add_flow(
        request.device_id,
        request.match,
        request.action,
        request.priority
    )

    return {
        "task_id": task.task_id,
        "total_time": task.total_time,
        "steps": len(task.steps),
        "errors": task.errors
    }


# ==========================================
# Demo/Simulation Endpoints (disabled — live mode only)
# ==========================================

@app.post("/demo/anomaly")
async def inject_anomaly(request: AnomalyRequest):
    """Inject a manual anomaly into telemetry collection to test detection and self-healing."""
    ensure_initialized()
    if not state._telemetry_collector:
        raise HTTPException(500, "Telemetry collector is not running.")
    
    state._telemetry_collector.inject_anomaly(
        device_id=request.device_id,
        anomaly_type=request.anomaly_type,
        duration_seconds=request.duration_seconds
    )
    return {"success": True, "message": f"Injected '{request.anomaly_type}' on '{request.device_id}'"}


# Alias for /demo/anomaly
@app.post("/demo/anomaly/inject")
async def inject_anomaly_alias(request: AnomalyRequest):
    return await inject_anomaly(request)


@app.post("/demo/resolve")
async def resolve_anomalies():
    """Clear all manually injected anomalies from telemetry collection, alerts, detector, and remediations."""
    ensure_initialized()
    if not state._telemetry_collector:
        raise HTTPException(500, "Telemetry collector is not running.")
    
    state._telemetry_collector.resolve_anomalies()
    
    if state._anomaly_detector:
        state._anomaly_detector.clear_history()
        
    if state._alert_manager:
        state._alert_manager.reset_all()
        
    if state._feedback_loop:
        state._feedback_loop.reset_all()
        
    return {"success": True, "message": "All injected anomalies and alerts cleared"}


# Alias for /demo/resolve
@app.post("/demo/anomaly/resolve-all")
async def resolve_anomalies_alias():
    return await resolve_anomalies()


@app.post("/demo/traffic")
async def set_traffic(request: TrafficRequest):
    """Demo endpoints removed."""
    raise HTTPException(400, "Demo endpoints removed; live-only mode enabled")


# Alias for /demo/traffic
@app.post("/demo/scenario")
async def set_scenario(request: TrafficRequest):
    """Demo endpoints removed."""
    raise HTTPException(400, "Demo endpoints removed; live-only mode enabled")


@app.post("/demo/link")
async def set_link(request: LinkRequest):
    """Demo endpoints removed."""
    raise HTTPException(400, "Demo endpoints removed; live-only mode enabled")


@app.get("/demo/state")
async def get_demo_state():
    """Demo endpoints removed."""
    raise HTTPException(400, "Demo endpoints removed; live-only mode enabled")


@app.post("/demo/reset")
async def reset_demo():
    """Demo endpoints removed."""
    raise HTTPException(400, "Demo endpoints removed; live-only mode enabled")


# ==========================================
# Telemetry Traffic Generator (QoS/Telemetry Demonstration)
# ==========================================

@app.post("/topology/generate-traffic")
async def generate_live_traffic():
    """Dynamically trigger real ping traffic crossing all switches using host network namespaces."""
    ensure_initialized()
    try:
        import subprocess
        import re

        pids = {}
        # List all bash processes matching mininet:h
        ps_out = subprocess.check_output(["ps", "aux"]).decode()
        for line in ps_out.splitlines():
            if "mininet:h" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    match = re.search(r"mininet:h(\d+)", line)
                    if match:
                        h_num = int(match.group(1))
                        pids[h_num] = pid

        if not pids:
            return {
                "success": False, 
                "error": "No active Mininet hosts discovered. Please verify Mininet is running."
            }

        # Dynamically pair each host with another host on the opposite side of the ring
        # to ensure perfect cross-switch traffic regardless of topology size (3 switches, 10 switches, etc.)
        sorted_hosts = sorted(pids.keys())
        n_hosts = len(sorted_hosts)

        if n_hosts < 2:
            return {
                "success": False,
                "error": f"Discovered only {n_hosts} active host(s). Traffic generation requires at least 2 hosts."
            }

        pairs = []
        step = n_hosts // 2
        # Pair each host with its polar opposite in the ring
        for i in range(n_hosts):
            src = sorted_hosts[i]
            dst = sorted_hosts[(i + step) % n_hosts]
            if src != dst:
                pairs.append((src, dst))

        started = []
        for src, dst in pairs:
            src_pid = pids.get(src)
            if src_pid:
                # Execute ping inside host namespace in the background (15 pings)
                cmd = ["sudo", "nsenter", "-t", src_pid, "-n", "ping", "-c", "15", f"10.0.0.{dst}"]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                started.append(f"h{src}➡️h{dst}")

        return {
            "success": True,
            "message": f"⚡ Traffic generation triggered! Pings running in background: {', '.join(started)}",
            "pairs": started
        }
    except Exception as e:
        logger.error(f"Failed to generate live traffic: {e}")
        return {"success": False, "error": str(e)}


@app.post("/topology/stop-traffic")
async def stop_live_traffic():
    """Stop all background ping and iperf traffic processes instantly."""
    ensure_initialized()
    try:
        import subprocess
        # Terminate all active ping and iperf processes in host namespaces
        subprocess.run(["sudo", "pkill", "-f", "ping"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", "iperf"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "message": "🛑 Background traffic stopped successfully!"}
    except Exception as e:
        logger.error(f"Failed to stop traffic: {e}")
        return {"success": False, "error": str(e)}


# ==========================================
# Feedback Loop Control
# ==========================================

@app.post("/feedback/pause")
async def pause_feedback():
    """Pause feedback loop."""
    state._feedback_loop.pause()
    return {"status": "paused"}


@app.post("/feedback/resume")
async def resume_feedback():
    """Resume feedback loop."""
    state._feedback_loop.resume()
    return {"status": "resumed"}


@app.get("/feedback/status")
async def feedback_status():
    """Get feedback loop status."""
    return state._feedback_loop.get_status()


# ==========================================
# Main
# ==========================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))

    logger.info(f"Starting LLM-NetAuto REST API on {host}:{port}")

    uvicorn.run(
        "dashboard.api:app",
        host=host,
        port=port,
        reload=os.getenv("FASTAPI_RELOAD", "true").lower() == "true"
    )

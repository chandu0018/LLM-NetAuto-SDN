"""
Intent Parser for LLM-NetAuto-SDN.

Implements a 5-stage LangChain LCEL pipeline for parsing
natural language intents into ONOS-compatible configurations.
"""

import os
import json
import re
import time
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

from .prompt_templates import PromptTemplates
from .rag_engine import get_rag_engine

load_dotenv()


class IntentParser:
    """
    LLM-based Intent Parser using LangChain LCEL.

    Pipeline stages:
    1. Topology Context Enrichment
    2. Intent Parsing to JSON
    3. Rule Validation
    4. Auto-correction (if needed)
    5. Result Summarization

    In DEMO_MODE, uses LLMSimulator instead of Ollama.
    """

    def __init__(self):
        """Initialize intent parser (live-only)."""
        # Enforce live-only operation (no demo simulator)
        self._demo_mode = False
        self._ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self._ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
        self._timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))

        self._rag_engine = get_rag_engine()
        self._llm = None
        self._chain = None

        # Try to initialize real LLM; do NOT fall back to simulator
        try:
            self._initialize_llm()
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")

        logger.info("IntentParser initialized (live-only mode)")

    def _initialize_llm(self) -> None:
        """Initialize Ollama LLM for live mode."""
        try:
            from langchain_ollama import OllamaLLM

            self._llm = OllamaLLM(
                model=self._ollama_model,
                base_url=self._ollama_host,
                temperature=0.1,
                timeout=self._timeout
            )

            # Defer LLM verification to request time so backend startup stays fast.
            logger.info(f"Configured Ollama client: {self._ollama_model}")

        except ImportError as e:
            logger.error("langchain-ollama not installed: cannot run live LLM")
            raise
        except Exception as e:
            logger.error(f"Ollama not available: {e}")
            raise

    def _initialize_simulator(self) -> None:
        """Initialize LLM simulator for demo mode."""
        from simulation.llm_sim import LLMSimulator
        self._llm_simulator = LLMSimulator()
        logger.info("Using LLM simulator (demo mode)")

    def _invoke_llm(self, prompt: str, timeout: int = None) -> str:
        """
        Invoke LLM or simulator.

        Args:
            prompt: Prompt string
            timeout: Optional override timeout in seconds

        Returns:
            LLM response string
        """
        if self._llm is None:
            raise RuntimeError("LLM backend not available. Install/configure Ollama and set OLLAMA_HOST.")

        effective_timeout = timeout if timeout is not None else self._timeout
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._llm.invoke, prompt)
        try:
            result = future.result(timeout=effective_timeout)
            executor.shutdown(wait=False)
            return result
        except concurrent.futures.TimeoutError as e:
            executor.shutdown(wait=False)
            raise RuntimeError(f"LLM request timed out after {effective_timeout}s") from e

    # ==========================================
    # Main Parse Method
    # ==========================================

    def parse_intent(
        self,
        user_input: str,
        topology: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse natural language intent through 5-stage pipeline.

        Args:
            user_input: Natural language intent
            topology: Optional topology data (from ONOS or sim)

        Returns:
            Complete parsing result with rule, validation, summary
        """
        start_time = time.time()
        result = {
            "success": False,
            "original_intent": user_input,
            "enriched_intent": "",
            "parsed_rule": None,
            "validation": {"valid": False, "issues": []},
            "corrected_rule": None,
            "summary": "",
            "latency_ms": 0,
            "stages_completed": [],
            "error": None
        }

        try:
            # Stage 1: Topology Context Enrichment
            logger.debug("Stage 1: Enriching intent with topology context")
            enriched = self._stage1_enrich_context(user_input, topology)
            result["enriched_intent"] = enriched
            result["stages_completed"].append("context_enrichment")

            # Stage 2: Intent Parsing
            logger.debug("Stage 2: Parsing intent to JSON")
            parsed_rule = self._stage2_parse_intent(enriched)
            if not parsed_rule:
                result["error"] = "Failed to parse intent"
                return result
            result["parsed_rule"] = parsed_rule
            result["stages_completed"].append("intent_parsing")

            # Stage 3: Validation
            logger.debug("Stage 3: Validating rule")
            validation = self._stage3_validate_rule(parsed_rule, topology)
            result["validation"] = validation
            result["stages_completed"].append("validation")

            # Stage 4: Auto-correction (if needed)
            if not validation.get("valid", False):
                logger.debug("Stage 4: Auto-correcting rule")
                corrected = self._stage4_correct_rule(
                    parsed_rule,
                    validation.get("issues", []),
                    topology
                )
                if corrected:
                    result["corrected_rule"] = corrected
                    result["parsed_rule"] = corrected
                    # Re-validate
                    result["validation"] = self._stage3_validate_rule(
                        corrected, topology
                    )
                result["stages_completed"].append("correction")

            # Stage 5: Summarization
            logger.debug("Stage 5: Generating summary")
            summary = self._stage5_summarize(
                user_input,
                result["parsed_rule"],
                {"success": result["validation"].get("valid", False)}
            )
            result["summary"] = summary
            result["stages_completed"].append("summarization")

            # Final success check
            result["success"] = result["validation"].get("valid", False)

        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            result["error"] = str(e)

        result["latency_ms"] = (time.time() - start_time) * 1000
        return result

    # ==========================================
    # Pipeline Stages
    # ==========================================

    def _stage1_enrich_context(
        self,
        user_input: str,
        topology: Optional[Dict[str, Any]]
    ) -> str:
        """
        Stage 1: Enrich intent with topology context.

        Uses RAG to add device IDs, host IPs, MACs, ports.
        """
        try:
            rag_context = self._rag_engine.query_topology(user_input)
        except Exception as e:
            logger.warning(f"RAG topology query failed: {e}")
            rag_context = "No relevant topology information found."

        if topology:
            devices = json.dumps(topology.get("devices", []), indent=2)
            hosts = json.dumps(topology.get("hosts", []), indent=2)
            links = json.dumps(topology.get("links", []), indent=2)
        else:
            devices = "[]"
            hosts = "[]"
            links = "[]"

        # Skip LLM for context enrichment — simple enrichment is fast and sufficient
        # (LLM enrichment is non-critical and too slow on CPU-only machines)
        return self._simple_enrich(user_input, topology)

    def _simple_enrich(
        self,
        user_input: str,
        topology: Optional[Dict[str, Any]]
    ) -> str:
        """Simple rule-based enrichment for demo mode."""
        enriched = user_input

        if not topology:
            return enriched

        # Map host names to IPs
        host_map = {}
        for host in topology.get("hosts", []):
            name = host.get("name", "")
            ips = host.get("ips", host.get("ipAddresses", []))
            mac = host.get("mac", "")
            if name and ips:
                host_map[name.lower()] = {
                    "ip": ips[0],
                    "mac": mac
                }

        # Replace host names with details
        for name, info in host_map.items():
            if name in enriched.lower():
                enriched += f" ({name}={info['ip']}, mac={info['mac']})"

        return enriched

    def _stage2_parse_intent(self, enriched_intent: str) -> Optional[Dict]:
        """
        Stage 2: Parse enriched intent to JSON.

        Returns structured rule dict.
        """
        prompt = PromptTemplates.INTENT_PARSE_PROMPT.format(
            enriched_intent=enriched_intent
        )

        try:
            response = self._invoke_llm(prompt, timeout=15)
            parsed = self._extract_json(response)
            if parsed:
                # Safeguard: if user explicitly requested mirroring, ensure it is classified as mirror
                if parsed.get("intent_type") != "mirror" and "mirror" in enriched_intent.lower():
                    logger.warning("LLM misclassified mirror intent, falling back to rule-based parser")
                    return self._fallback_parse_intent(enriched_intent)
                logger.debug("Stage 2: LLM parse succeeded")
                return parsed
        except Exception as e:
            logger.warning(f"Stage 2 LLM parse failed (using rule-based fallback): {e}")

        return self._fallback_parse_intent(enriched_intent)

    def _stage3_validate_rule(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Stage 3: Validate rule against topology.

        Returns validation result dict.
        """
        if not topology:
            topology = {"devices": [], "hosts": [], "links": []}

        # Use fast rule-based validation directly — LLM validation too slow on CPU
        return self._simple_validate(rule, topology)

    def _simple_validate(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple rule-based validation for demo mode."""
        issues = []
        warnings = []

        # Check required fields
        if not rule.get("intent_type"):
            issues.append("Missing intent_type")

        # Check priority range
        priority = rule.get("priority", 40000)
        if priority < 1 or priority > 65535:
            issues.append(f"Invalid priority {priority}, must be 1-65535")

        # Validate hosts if topology provided
        if topology:
            host_names = set()
            host_ips = set()
            for host in topology.get("hosts", []):
                host_names.add(host.get("name", "").lower())
                for ip in host.get("ips", host.get("ipAddresses", [])):
                    host_ips.add(ip)

            src = rule.get("src_host", "")
            if src and src.lower() not in host_names and src not in host_ips:
                if not src.startswith("10.0.") and src != "null":
                    warnings.append(f"Unknown source host: {src}")

            dst = rule.get("dst_host", "")
            if dst and dst.lower() not in host_names and dst not in host_ips:
                if not dst.startswith("10.0.") and dst != "null":
                    warnings.append(f"Unknown destination host: {dst}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "corrected_rule": None
        }

    def _stage4_correct_rule(
        self,
        rule: Dict[str, Any],
        issues: List[str],
        topology: Optional[Dict[str, Any]]
    ) -> Optional[Dict]:
        """
        Stage 4: Auto-correct invalid rule.

        Returns corrected rule dict or None.
        """
        if not issues:
            return None

        if not topology:
            topology = {"devices": [], "hosts": [], "links": []}

        # Use fast rule-based correction directly
        corrected = rule.copy()
        priority = corrected.get("priority", 40000)
        if priority < 1:
            corrected["priority"] = 40000
        elif priority > 65535:
            corrected["priority"] = 65535
        return corrected

    def _stage5_summarize(
        self,
        original_intent: str,
        rule: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        """
        Stage 5: Generate plain English summary.

        Returns summary string.
        """
        # Use fast rule-based summary directly
        return self._generate_simple_summary(original_intent, rule, result)

    def _generate_simple_summary(
        self,
        intent: str,
        rule: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        """Generate simple summary for demo mode."""
        intent_type = rule.get("intent_type", "configure")
        action = rule.get("action", "add")
        src = rule.get("src_host", "any")
        dst = rule.get("dst_host", "any")
        protocol = rule.get("protocol", "all")
        success = result.get("success", False)

        status = "will be" if success else "could not be"

        if intent_type == "clear_all" or (intent_type == "all" and action == "remove"):
            return f"All custom flow rules and intents {'have been' if success else 'could not be'} removed from the network."
        elif intent_type == "block":
            return (
                f"Traffic from {src} to {dst} ({protocol}) {status} blocked. "
                f"Rule priority: {rule.get('priority', 50000)}."
            )
        elif intent_type == "allow":
            return (
                f"Traffic from {src} to {dst} ({protocol}) {status} allowed. "
                f"Rule priority: {rule.get('priority', 40000)}."
            )
        elif intent_type == "rate_limit":
            limit = rule.get("bandwidth_limit_mbps", "unspecified")
            return (
                f"Traffic from {src} {status} rate-limited to {limit} Mbps."
            )
        elif intent_type == "prioritize":
            return (
                f"Traffic from {src} to {dst} {status} prioritized "
                f"with high priority ({rule.get('priority', 60000)})."
            )
        elif intent_type == "isolate":
            device = rule.get("src_device", src)
            return f"Device {device} {status} isolated from the network."
        elif intent_type == "mirror":
            return (
                f"Traffic on {rule.get('src_device', 'device')} "
                f"{status} mirrored for monitoring."
            )
        else:
            return (
                f"Network {intent_type} rule {status} configured for "
                f"{src} to {dst}."
            )

    def _fallback_parse_intent(
        self,
        enriched_intent: str,
        topology: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fast deterministic parser for common intent phrases."""
        text = (enriched_intent or "").lower()
        rule: Dict[str, Any] = {
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
            "use_intent_framework": True,
            "target_all_switches": False,
            "vlan_id": None,
            "eth_type": "0x0800",
            "ip_proto": None,
            "queue_id": None,
        }

        if any(word in text for word in ["block", "drop", "deny"]):
            rule["intent_type"] = "block"
            rule["priority"] = 50000
            rule["use_intent_framework"] = False
            rule["target_all_switches"] = True
        elif any(word in text for word in ["isolate"]):
            rule["intent_type"] = "isolate"
            rule["priority"] = 65000
            rule["use_intent_framework"] = False
            rule["target_all_switches"] = True
        elif any(word in text for word in ["prioritize", "qos", "priority"]):
            rule["intent_type"] = "prioritize"
            rule["priority"] = 60000
        elif any(word in text for word in ["rate limit", "limit"]):
            rule["intent_type"] = "rate_limit"
            rule["priority"] = 55000
        elif any(word in text for word in ["mirror"]):
            rule["intent_type"] = "mirror"
            rule["priority"] = 45000
            rule["use_intent_framework"] = False

        if any(word in text for word in ["remove all", "clear all", "delete all", "remove custom flow"]):
            rule["intent_type"] = "clear_all"
            rule["action"] = "remove"
            rule["use_intent_framework"] = False
            return rule

        if "http" in text:
            rule["protocol"] = "tcp"
            rule["port"] = 80
            rule["ip_proto"] = 6
        elif "ssh" in text:
            rule["protocol"] = "tcp"
            rule["port"] = 22
            rule["ip_proto"] = 6
        elif "icmp" in text:
            rule["protocol"] = "icmp"
            rule["ip_proto"] = 1
        elif "voip" in text or "sip" in text:
            rule["protocol"] = "udp"
            rule["port"] = 5060
            rule["ip_proto"] = 17

        rate = re.search(r"(\d+)\s*mbps", text)
        if rate:
            rule["bandwidth_limit_mbps"] = int(rate.group(1))

        # Parse simple source/destination forms.
        from_to = re.search(r"from\s+([\w\.:-]+)\s+to\s+([\w\.:-]+)", text)
        if from_to:
            rule["src_host"] = from_to.group(1)
            rule["dst_host"] = from_to.group(2)

        # Generic host token fallback.
        if not rule["src_host"]:
            hosts = re.findall(r"\b(?:h\d+|10\.\d+\.\d+\.\d+|[0-9a-f]{2}(?::[0-9a-f]{2}){5})\b", text)
            if hosts:
                rule["src_host"] = hosts[0]
                if len(hosts) > 1:
                    rule["dst_host"] = hosts[1]

        # Mirror switch and port extraction
        if rule["intent_type"] == "mirror":
            dev_match = re.search(r"\b(s\d+)\b", text)
            if dev_match:
                rule["src_device"] = dev_match.group(1)
            port_match = re.search(r"port\s+(\d+)", text)
            if port_match:
                rule["out_port"] = int(port_match.group(1))

        return rule

    # ==========================================
    # Validation Helper
    # ==========================================

    def validate_rule(
        self,
        rule: Dict[str, Any],
        topology: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate a rule without full pipeline.

        Args:
            rule: Rule to validate
            topology: Topology data

        Returns:
            Validation result
        """
        return self._stage3_validate_rule(rule, topology)

    # ==========================================
    # Summarization Helper
    # ==========================================

    def summarize_result(
        self,
        rule: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        """
        Generate summary for a deployed rule.

        Args:
            rule: Deployed rule
            result: Deployment result

        Returns:
            Summary string
        """
        return self._stage5_summarize("", rule, result)

    # ==========================================
    # Remediation Generation
    # ==========================================

    def generate_remediation(
        self,
        anomaly: Dict[str, Any],
        current_flows: List[Dict[str, Any]],
        traffic_stats: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate remediation rule for an anomaly.

        Args:
            anomaly: Anomaly details
            current_flows: Current flow rules on device
            traffic_stats: Current traffic statistics

        Returns:
            Remediation action with rule
        """
        # Get similar past remediations
        try:
            past = self._rag_engine.get_similar_remediations(anomaly, n=3)
        except Exception:
            past = []

        try:
            prompt = PromptTemplates.REMEDIATION_PROMPT.format(
                anomaly_details=json.dumps(anomaly, indent=2),
                device_id=anomaly.get("device_id", "unknown"),
                anomaly_type=anomaly.get("type", "unknown"),
                anomaly_score=anomaly.get("score", 0),
                timestamp=anomaly.get("timestamp", datetime.now().isoformat()),
                traffic_stats=json.dumps(traffic_stats or {}, indent=2),
                current_flows=json.dumps(current_flows[:10], indent=2),
                past_remediations=json.dumps(past, indent=2)
            )

            response = self._invoke_llm(prompt)
            result = self._extract_json(response)

            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"LLM remediation generation failed, using default: {e}")
            return {
                "action_type": "rate_limit",
                "rule": {
                    "intent_type": "rate_limit",
                    "action": "add",
                    "src_device": anomaly.get("device_id"),
                    "bandwidth_limit_mbps": 50,
                    "priority": 55000,
                    "use_intent_framework": False,
                    "target_all_switches": False
                },
                "reason": "Default rate limiting due to anomaly",
                "expected_outcome": "Reduce traffic spike impact",
                "rollback_after_seconds": 300
            }

        return result

    # ==========================================
    # Utility Methods
    # ==========================================

    def _extract_json(self, text: str) -> Optional[Dict]:
        """
        Extract JSON from LLM response.

        Handles responses with markdown code blocks or plain JSON.
        """
        if not text:
            return None

        # Try direct JSON parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        json_match = re.search(
            r'```(?:json)?\s*([\s\S]*?)\s*```',
            text
        )
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object pattern
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not extract JSON from: {text[:200]}...")
        return None

    def is_llm_available(self) -> bool:
        """Check if LLM (Ollama) is available."""
        if self._demo_mode:
            return True
        try:
            if self._llm:
                self._llm.invoke("ping")
                return True
        except Exception:
            pass
        return False

    @property
    def demo_mode(self) -> bool:
        """Check if running in demo mode."""
        return self._demo_mode


# Singleton instance
_parser_instance: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """Get or create the global intent parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = IntentParser()
    return _parser_instance


if __name__ == "__main__":
    # Test intent parser
    print("\n=== Intent Parser Test ===\n")

    parser = IntentParser()
    print(f"Demo mode: {parser.demo_mode}")
    print(f"LLM available: {parser.is_llm_available()}")

    # Test topology
    test_topology = {
        "devices": [
            {"id": "of:0000000000000001", "name": "s1", "type": "switch"},
            {"id": "of:0000000000000002", "name": "s2", "type": "switch"},
            {"id": "of:0000000000000003", "name": "s3", "type": "switch"}
        ],
        "hosts": [
            {"name": "h1", "mac": "00:00:00:00:00:01", "ips": ["10.0.0.1"]},
            {"name": "h2", "mac": "00:00:00:00:00:02", "ips": ["10.0.0.2"]},
            {"name": "h3", "mac": "00:00:00:00:00:03", "ips": ["10.0.0.3"]},
            {"name": "h4", "mac": "00:00:00:00:00:04", "ips": ["10.0.0.4"]}
        ],
        "links": [
            {"src": "s1", "dst": "s2"},
            {"src": "s2", "dst": "s3"},
            {"src": "s1", "dst": "s3"}
        ]
    }

    # Test intents
    test_intents = [
        "Block all traffic from 10.0.0.1",
        "Allow only HTTP traffic from h1 to h3",
        "Drop all ICMP packets on all switches",
        "Prioritize VoIP traffic on UDP port 5060"
    ]

    for intent in test_intents:
        print(f"\n--- Testing: {intent} ---")
        result = parser.parse_intent(intent, test_topology)
        print(f"Success: {result['success']}")
        print(f"Latency: {result['latency_ms']:.1f} ms")
        print(f"Type: {result['parsed_rule'].get('intent_type', 'unknown')}")
        print(f"Summary: {result['summary']}")
        if result['validation'].get('issues'):
            print(f"Issues: {result['validation']['issues']}")

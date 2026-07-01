"""
Prompt Templates for LLM-NetAuto-SDN.

Contains all LangChain prompt templates for intent parsing,
validation, correction, summarization, and remediation.
"""

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage


class PromptTemplates:
    """
    Collection of prompt templates for the LLM pipeline.

    Templates:
    1. TOPOLOGY_CONTEXT_PROMPT - Enriches intent with topology info
    2. INTENT_PARSE_PROMPT - Parses intent to structured JSON
    3. VALIDATION_PROMPT - Validates rule against topology
    4. CORRECTION_PROMPT - Auto-corrects invalid rules
    5. SUMMARIZATION_PROMPT - Generates plain English summary
    6. REMEDIATION_PROMPT - Generates corrective rules for anomalies
    """

    # ==========================================================
    # 1. TOPOLOGY CONTEXT PROMPT
    # ==========================================================
    TOPOLOGY_CONTEXT_PROMPT = PromptTemplate(
        template="""You are a network topology expert. Given the user's network intent and the current topology information, enrich the intent with specific device IDs, host IPs, MACs, and port numbers.

Current Network Topology:
{topology_context}

Available Devices (Switches):
{devices}

Available Hosts:
{hosts}

Network Links:
{links}

User Intent: {user_intent}

Provide an enriched version of the intent that includes:
1. Specific device IDs (e.g., of:0000000000000001)
2. Host IP addresses (e.g., 10.0.0.1)
3. Host MAC addresses (e.g., 00:00:00:00:00:01)
4. Port numbers where relevant
5. Any implicit information that can be inferred from the topology

Enriched Intent:""",
        input_variables=[
            "topology_context",
            "devices",
            "hosts",
            "links",
            "user_intent"
        ]
    )

    # ==========================================================
    # 2. INTENT PARSE PROMPT
    # ==========================================================
    INTENT_PARSE_PROMPT = PromptTemplate(
        template="""You are an SDN network intent parser. Parse the following network intent into a structured JSON format that can be used to configure an OpenFlow SDN network via ONOS controller.

Network Intent: {enriched_intent}

Available Intent Types:
- block: Block/drop all traffic matching criteria
- allow: Allow specific traffic (whitelist)
- prioritize: Set higher priority for matching traffic
- reroute: Change traffic path
- isolate: Isolate a device or host from the network
- mirror: Mirror traffic to a monitoring port
- rate_limit: Limit bandwidth for matching traffic
- monitor: Mark traffic for monitoring/logging

Parse the intent and respond with ONLY a valid JSON object (no explanation, no markdown code blocks), following this exact structure:
{{
    "intent_type": "block|allow|prioritize|reroute|isolate|mirror|rate_limit|monitor",
    "action": "add|remove",
    "src_host": "hostname|IP|MAC|subnet|null",
    "dst_host": "hostname|IP|MAC|null",
    "src_device": "of:device_id|null",
    "dst_device": "of:device_id|null",
    "in_port": port_number_or_null,
    "out_port": port_number_or_null,
    "protocol": "tcp|udp|icmp|all|null",
    "port": tcp_udp_port_number_or_null,
    "priority": priority_100_to_65535,
    "bandwidth_limit_mbps": mbps_or_null,
    "use_intent_framework": true_or_false,
    "target_all_switches": true_or_false,
    "vlan_id": vlan_id_or_null,
    "eth_type": "0x0800|0x0806|null",
    "ip_proto": ip_protocol_number_or_null,
    "queue_id": queue_id_or_null
}}

Important Rules:
1. If blocking specific hosts, set target_all_switches to true
2. For host-to-host intents, use_intent_framework should be true
3. Default priority is 40000 for allow, 50000 for block
4. Protocol "all" means match any protocol
5. For ICMP, set ip_proto to 1
6. For TCP, set ip_proto to 6
7. For UDP, set ip_proto to 17
8. "remove" action deletes existing rules matching the criteria

JSON Output:""",
        input_variables=["enriched_intent"]
    )

    # ==========================================================
    # 3. VALIDATION PROMPT
    # ==========================================================
    VALIDATION_PROMPT = PromptTemplate(
        template="""You are an SDN rule validator. Validate the following parsed rule against the live network topology.

Parsed Rule:
{parsed_rule}

Current Network Topology:
Devices: {devices}
Hosts: {hosts}
Links: {links}

Validation Checks:
1. Source/destination hosts exist in topology
2. Source/destination devices exist in topology
3. Specified ports are valid
4. Path between endpoints exists (for host-to-host rules)
5. Protocol and port combination is valid
6. Priority value is within valid range (1-65535)
7. Rate limits are reasonable (1-10000 Mbps)

Respond with ONLY a valid JSON object (no explanation, no markdown code blocks):
{{
    "valid": true_or_false,
    "issues": ["list of issues found, empty if valid"],
    "warnings": ["list of warnings, non-blocking issues"],
    "corrected_rule": null_or_corrected_json_object
}}

If the rule is valid, set valid to true and issues to empty array.
If the rule has fixable issues, provide corrected_rule with fixes.
If the rule has unfixable issues, set valid to false and explain in issues.

JSON Output:""",
        input_variables=["parsed_rule", "devices", "hosts", "links"]
    )

    # ==========================================================
    # 4. CORRECTION PROMPT
    # ==========================================================
    CORRECTION_PROMPT = PromptTemplate(
        template="""You are an SDN rule correction expert. The following rule failed validation. Auto-correct it based on the issues and topology.

Original Rule:
{original_rule}

Validation Issues:
{issues}

Current Network Topology:
Devices: {devices}
Hosts: {hosts}
Links: {links}

Apply the following corrections:
1. Replace invalid device IDs with closest valid ones
2. Fix invalid IP addresses to match known hosts
3. Correct invalid port numbers
4. Adjust priority to valid range if needed
5. Fix protocol/port mismatches

Respond with ONLY the corrected JSON rule (no explanation, same format as original):""",
        input_variables=["original_rule", "issues", "devices", "hosts", "links"]
    )

    # ==========================================================
    # 5. SUMMARIZATION PROMPT
    # ==========================================================
    SUMMARIZATION_PROMPT = PromptTemplate(
        template="""You are a network operations assistant. Summarize the following network configuration action in plain English for the operator.

Original Intent: {original_intent}

Parsed Configuration:
{parsed_rule}

Deployment Result:
{deployment_result}

Provide a concise, technical summary (2-3 sentences) that explains:
1. What action was taken
2. What network elements were affected
3. The expected outcome

Keep the language professional but accessible.

Summary:""",
        input_variables=["original_intent", "parsed_rule", "deployment_result"]
    )

    # ==========================================================
    # 6. REMEDIATION PROMPT
    # ==========================================================
    REMEDIATION_PROMPT = PromptTemplate(
        template="""You are an autonomous SDN remediation system. An anomaly has been detected and you must generate a corrective rule.

Anomaly Details:
{anomaly_details}

Affected Device: {device_id}
Anomaly Type: {anomaly_type}
Anomaly Score: {anomaly_score}
Timestamp: {timestamp}

Current Traffic Statistics:
{traffic_stats}

Current Flow Rules on Device:
{current_flows}

Recent Similar Remediations:
{past_remediations}

Based on the anomaly type, generate an appropriate corrective action:

For "traffic_spike" or "ddos_sim":
- Add rate limiting rules
- Prioritize legitimate traffic
- Consider blocking suspicious sources

For "packet_drop":
- Check for overloaded paths
- Consider rerouting traffic
- Verify QoS settings

For "bandwidth_hog":
- Apply rate limiting to heavy users
- Ensure fair bandwidth distribution

For "port_flap":
- Consider link isolation
- Implement dampening

Respond with ONLY a valid JSON object (no explanation, no markdown code blocks):
{{
    "action_type": "rate_limit|block|reroute|prioritize|isolate",
    "rule": {{
        "intent_type": "...",
        "action": "add",
        "src_host": "...",
        "dst_host": "...",
        "src_device": "...",
        "priority": 55000,
        "bandwidth_limit_mbps": null_or_value,
        "use_intent_framework": false,
        "target_all_switches": false
    }},
    "reason": "brief explanation of why this action was chosen",
    "expected_outcome": "what this action should accomplish",
    "rollback_after_seconds": null_or_timeout_value
}}

JSON Output:""",
        input_variables=[
            "anomaly_details",
            "device_id",
            "anomaly_type",
            "anomaly_score",
            "timestamp",
            "traffic_stats",
            "current_flows",
            "past_remediations"
        ]
    )

    # ==========================================================
    # Chat-style prompts using ChatPromptTemplate
    # ==========================================================

    @classmethod
    def get_chat_intent_prompt(cls) -> ChatPromptTemplate:
        """Get chat-style prompt for intent parsing."""
        return ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert SDN network intent parser for the ONOS controller.
Your job is to convert natural language network intents into structured JSON configurations.
Always respond with valid JSON only, no explanations or markdown."""),
            HumanMessage(content="""Parse this network intent: {intent}

Topology context: {topology}

Respond with JSON in this format:
{{
    "intent_type": "block|allow|prioritize|reroute|isolate|mirror|rate_limit|monitor",
    "action": "add|remove",
    "src_host": "...",
    "dst_host": "...",
    "protocol": "tcp|udp|icmp|all|null",
    "port": number_or_null,
    "priority": number,
    "use_intent_framework": boolean,
    "target_all_switches": boolean
}}""")
        ])

    @classmethod
    def get_chat_remediation_prompt(cls) -> ChatPromptTemplate:
        """Get chat-style prompt for anomaly remediation."""
        return ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an autonomous SDN remediation system.
When anomalies are detected, you generate corrective network rules.
Always respond with valid JSON only, no explanations."""),
            HumanMessage(content="""Anomaly detected:
Type: {anomaly_type}
Device: {device_id}
Score: {score}
Stats: {stats}

Generate a corrective rule as JSON.""")
        ])

    # ==========================================================
    # Template Getters
    # ==========================================================

    @classmethod
    def get_topology_context_template(cls) -> PromptTemplate:
        """Get topology context enrichment template."""
        return cls.TOPOLOGY_CONTEXT_PROMPT

    @classmethod
    def get_intent_parse_template(cls) -> PromptTemplate:
        """Get intent parsing template."""
        return cls.INTENT_PARSE_PROMPT

    @classmethod
    def get_validation_template(cls) -> PromptTemplate:
        """Get rule validation template."""
        return cls.VALIDATION_PROMPT

    @classmethod
    def get_correction_template(cls) -> PromptTemplate:
        """Get rule correction template."""
        return cls.CORRECTION_PROMPT

    @classmethod
    def get_summarization_template(cls) -> PromptTemplate:
        """Get result summarization template."""
        return cls.SUMMARIZATION_PROMPT

    @classmethod
    def get_remediation_template(cls) -> PromptTemplate:
        """Get anomaly remediation template."""
        return cls.REMEDIATION_PROMPT


# Convenience function to get all templates
def get_all_templates() -> dict:
    """Return all prompt templates as a dictionary."""
    return {
        "topology_context": PromptTemplates.TOPOLOGY_CONTEXT_PROMPT,
        "intent_parse": PromptTemplates.INTENT_PARSE_PROMPT,
        "validation": PromptTemplates.VALIDATION_PROMPT,
        "correction": PromptTemplates.CORRECTION_PROMPT,
        "summarization": PromptTemplates.SUMMARIZATION_PROMPT,
        "remediation": PromptTemplates.REMEDIATION_PROMPT
    }


if __name__ == "__main__":
    # Test prompt templates
    print("\n=== Prompt Templates Test ===\n")

    templates = get_all_templates()
    for name, template in templates.items():
        print(f"{name}:")
        print(f"  Input variables: {template.input_variables}")
        print(f"  Template length: {len(template.template)} chars")
        print()

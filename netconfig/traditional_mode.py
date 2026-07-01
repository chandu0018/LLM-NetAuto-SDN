"""
Traditional Mode Configuration for LLM-NetAuto-SDN.

Simulates traditional manual CLI-based SDN configuration
for comparison with LLM-based automation.
"""

import os
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ConfigurationStep:
    """Represents a single configuration step."""
    step_number: int
    description: str
    command: str
    duration_seconds: float
    success: bool = True
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConfigurationTask:
    """Represents a complete configuration task."""
    task_id: str
    task_name: str
    steps: List[ConfigurationStep] = field(default_factory=list)
    total_time_seconds: float = 0.0
    success: bool = True
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TraditionalMode:
    """
    Simulates traditional manual SDN configuration.

    Provides step-by-step configuration workflow that requires
    expert knowledge and manual interaction.
    """

    # Average time per step type (in seconds)
    STEP_TIMES = {
        "lookup": 15,       # Looking up documentation
        "identify": 20,     # Identifying device IDs
        "build_json": 45,   # Manually building JSON
        "verify": 30,       # Verifying command/config
        "execute": 10,      # Executing API call
        "confirm": 15,      # Confirming result
        "debug": 60,        # Debugging errors
        "rollback": 30      # Rolling back failed config
    }

    # Error probability per step type
    ERROR_RATES = {
        "lookup": 0.02,
        "identify": 0.10,
        "build_json": 0.20,  # JSON errors common
        "verify": 0.05,
        "execute": 0.08,
        "confirm": 0.03,
        "debug": 0.05,
        "rollback": 0.10
    }

    def __init__(self):
        """Initialize traditional mode simulator."""
        self._tasks: Dict[str, ConfigurationTask] = {}
        self._current_task: Optional[ConfigurationTask] = None
        logger.info("TraditionalMode simulator initialized")

    def start_task(self, task_name: str) -> ConfigurationTask:
        """
        Start a new configuration task.

        Args:
            task_name: Name of the task

        Returns:
            ConfigurationTask object
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task = ConfigurationTask(
            task_id=task_id,
            task_name=task_name,
            started_at=datetime.now()
        )
        self._tasks[task_id] = task
        self._current_task = task
        logger.info(f"Started traditional config task: {task_name}")
        return task

    def add_step(
        self,
        description: str,
        command: str,
        step_type: str = "execute"
    ) -> ConfigurationStep:
        """
        Add and simulate a configuration step.

        Args:
            description: Step description
            command: Command or action to execute
            step_type: Type of step for timing/error calculation

        Returns:
            ConfigurationStep with timing and status
        """
        if not self._current_task:
            raise ValueError("No active task. Call start_task first.")

        step_number = len(self._current_task.steps) + 1

        # Calculate time with variance
        base_time = self.STEP_TIMES.get(step_type, 20)
        variance = random.uniform(0.7, 1.5)
        duration = base_time * variance

        # Check for error
        error_rate = self.ERROR_RATES.get(step_type, 0.10)
        success = random.random() > error_rate
        error = None

        if not success:
            error = self._generate_error(step_type)
            # Add debug time for errors
            duration += self.STEP_TIMES["debug"]
            self._current_task.errors.append(error)

        step = ConfigurationStep(
            step_number=step_number,
            description=description,
            command=command,
            duration_seconds=duration,
            success=success,
            error=error
        )

        self._current_task.steps.append(step)
        self._current_task.total_time_seconds += duration

        if not success:
            self._current_task.success = False

        return step

    def complete_task(self) -> ConfigurationTask:
        """
        Complete the current task.

        Returns:
            Completed ConfigurationTask
        """
        if not self._current_task:
            raise ValueError("No active task.")

        self._current_task.completed_at = datetime.now()

        task = self._current_task
        self._current_task = None

        logger.info(
            f"Completed task: {task.task_name} "
            f"({task.total_time_seconds:.1f}s, "
            f"{len(task.steps)} steps, "
            f"{len(task.errors)} errors)"
        )

        return task

    def simulate_block_host(
        self,
        host_ip: str,
        switches: List[str]
    ) -> ConfigurationTask:
        """
        Simulate blocking traffic from a host.

        Args:
            host_ip: IP address to block
            switches: List of switch IDs

        Returns:
            ConfigurationTask with all steps
        """
        self.start_task(f"Block traffic from {host_ip}")

        # Step 1: Look up OpenFlow DROP action
        self.add_step(
            "Look up OpenFlow DROP action syntax",
            "man ovs-ofctl; Google 'OpenFlow drop action'",
            "lookup"
        )

        # Step 2: Identify switches
        self.add_step(
            "Identify all switches in the network",
            "curl -u onos:rocks http://localhost:8181/onos/v1/devices",
            "identify"
        )

        # Step 3-N: Configure each switch
        for switch in switches:
            # Build JSON
            self.add_step(
                f"Build flow JSON for {switch}",
                f"vi /tmp/flow_{switch}.json",
                "build_json"
            )

            # Verify JSON
            self.add_step(
                f"Verify JSON syntax for {switch}",
                f"jq . /tmp/flow_{switch}.json",
                "verify"
            )

            # Execute
            self.add_step(
                f"POST flow rule to {switch}",
                f"curl -X POST -u onos:rocks -d @/tmp/flow_{switch}.json "
                f"http://localhost:8181/onos/v1/flows/{switch}",
                "execute"
            )

            # Confirm
            self.add_step(
                f"Verify flow installed on {switch}",
                f"curl -u onos:rocks "
                f"http://localhost:8181/onos/v1/flows/{switch}",
                "confirm"
            )

        return self.complete_task()

    def simulate_allow_protocol(
        self,
        src: str,
        dst: str,
        protocol: str,
        port: int,
        switches: List[str]
    ) -> ConfigurationTask:
        """
        Simulate allowing specific protocol between hosts.

        Args:
            src: Source host
            dst: Destination host
            protocol: Protocol (tcp/udp)
            port: Port number
            switches: Affected switches

        Returns:
            ConfigurationTask
        """
        self.start_task(
            f"Allow {protocol.upper()} port {port} from {src} to {dst}"
        )

        # Look up protocol numbers
        self.add_step(
            f"Look up IP protocol number for {protocol}",
            "grep {protocol} /etc/protocols",
            "lookup"
        )

        # Find host MACs
        self.add_step(
            "Retrieve host MAC addresses",
            "curl -u onos:rocks http://localhost:8181/onos/v1/hosts",
            "identify"
        )

        # Find path
        self.add_step(
            f"Calculate path from {src} to {dst}",
            "Analyze topology links manually",
            "identify"
        )

        # Configure each switch on path
        for switch in switches:
            self.add_step(
                f"Build {protocol.upper()} allow rule JSON for {switch}",
                f"vi /tmp/allow_{switch}.json",
                "build_json"
            )

            self.add_step(
                f"POST allow rule to {switch}",
                f"curl -X POST ...",
                "execute"
            )

        # Test connectivity
        self.add_step(
            "Test connectivity with ping/curl",
            f"ping {dst}; curl {dst}:{port}",
            "confirm"
        )

        return self.complete_task()

    def simulate_remediation(
        self,
        anomaly_type: str,
        device_id: str
    ) -> ConfigurationTask:
        """
        Simulate manual anomaly remediation.

        Args:
            anomaly_type: Type of anomaly
            device_id: Affected device

        Returns:
            ConfigurationTask
        """
        self.start_task(f"Remediate {anomaly_type} on {device_id}")

        # Notice anomaly
        self.add_step(
            "Notice anomaly via monitoring",
            "Check Grafana dashboard / receive alert",
            "identify"
        )

        # SSH to investigate
        self.add_step(
            "SSH to controller for investigation",
            "ssh admin@controller",
            "identify"
        )

        # Identify problem flows
        self.add_step(
            "Identify problematic flows",
            f"curl -u onos:rocks .../flows/{device_id} | jq '...'",
            "identify"
        )

        # Analyze traffic
        self.add_step(
            "Analyze traffic statistics",
            f"curl -u onos:rocks .../statistics/ports/{device_id}",
            "identify"
        )

        # Research solution
        self.add_step(
            "Research remediation approach",
            "Google 'SDN {} remediation'".format(anomaly_type),
            "lookup"
        )

        # Build corrective rule
        self.add_step(
            "Build corrective flow rule",
            "vi /tmp/remediation.json",
            "build_json"
        )

        # Deploy rule
        self.add_step(
            "Deploy corrective rule",
            f"curl -X POST ... flows/{device_id}",
            "execute"
        )

        # Monitor for improvement
        self.add_step(
            "Monitor for 5 minutes to verify fix",
            "watch -n 5 'curl ... statistics'",
            "confirm"
        )

        # Document
        self.add_step(
            "Document remediation in ticketing system",
            "Update JIRA ticket with resolution",
            "confirm"
        )

        return self.complete_task()

    def _generate_error(self, step_type: str) -> str:
        """Generate realistic error message for step type."""
        errors = {
            "lookup": [
                "Documentation outdated",
                "Conflicting information found",
                "Command syntax differs from documentation"
            ],
            "identify": [
                "Device ID format incorrect",
                "Host not found in topology",
                "Multiple devices with similar names"
            ],
            "build_json": [
                "Invalid JSON syntax",
                "Missing required field",
                "Incorrect field type",
                "Malformed MAC address",
                "Invalid IP address format"
            ],
            "verify": [
                "Syntax check failed",
                "Schema validation error"
            ],
            "execute": [
                "Connection refused",
                "Authentication failed",
                "HTTP 400 Bad Request",
                "HTTP 500 Internal Server Error",
                "Timeout waiting for response"
            ],
            "confirm": [
                "Flow not found after install",
                "Unexpected flow state",
                "Connectivity test failed"
            ],
            "debug": [
                "Root cause unclear",
                "Log correlation difficult"
            ],
            "rollback": [
                "Previous state unknown",
                "Partial rollback only"
            ]
        }

        return random.choice(errors.get(step_type, ["Unknown error"]))

    def get_task(self, task_id: str) -> Optional[ConfigurationTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[ConfigurationTask]:
        """Get all completed tasks."""
        return list(self._tasks.values())

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        tasks = self.get_all_tasks()

        if not tasks:
            return {
                "total_tasks": 0,
                "total_time_seconds": 0,
                "avg_time_per_task": 0,
                "total_steps": 0,
                "total_errors": 0,
                "success_rate": 0,
                "avg_steps_per_task": 0
            }

        total_time = sum(t.total_time_seconds for t in tasks)
        total_steps = sum(len(t.steps) for t in tasks)
        total_errors = sum(len(t.errors) for t in tasks)
        successful = sum(1 for t in tasks if t.success)

        return {
            "total_tasks": len(tasks),
            "total_time_seconds": total_time,
            "avg_time_per_task": total_time / len(tasks),
            "total_steps": total_steps,
            "total_errors": total_errors,
            "success_rate": successful / len(tasks) if tasks else 0,
            "avg_steps_per_task": total_steps / len(tasks) if tasks else 0,
            "error_rate": total_errors / total_steps if total_steps else 0
        }

    def clear_history(self) -> None:
        """Clear all task history."""
        self._tasks.clear()
        self._current_task = None


# Singleton instance
_mode_instance: Optional[TraditionalMode] = None


def get_traditional_mode() -> TraditionalMode:
    """Get or create the global traditional mode instance."""
    global _mode_instance
    if _mode_instance is None:
        _mode_instance = TraditionalMode()
    return _mode_instance


if __name__ == "__main__":
    # Test traditional mode
    print("\n=== Traditional Mode Test ===\n")

    mode = TraditionalMode()

    # Simulate blocking a host
    switches = [
        "of:0000000000000001",
        "of:0000000000000002",
        "of:0000000000000003"
    ]

    task1 = mode.simulate_block_host("10.0.0.1", switches)
    print(f"\nTask: {task1.task_name}")
    print(f"Steps: {len(task1.steps)}")
    print(f"Time: {task1.total_time_seconds:.1f} seconds")
    print(f"Errors: {len(task1.errors)}")
    print(f"Success: {task1.success}")

    # Simulate remediation
    task2 = mode.simulate_remediation(
        "traffic_spike",
        "of:0000000000000001"
    )
    print(f"\nTask: {task2.task_name}")
    print(f"Steps: {len(task2.steps)}")
    print(f"Time: {task2.total_time_seconds:.1f} seconds")
    print(f"Errors: {len(task2.errors)}")

    # Statistics
    stats = mode.get_statistics()
    print("\n=== Statistics ===")
    print(f"Total tasks: {stats['total_tasks']}")
    print(f"Total time: {stats['total_time_seconds']:.1f}s")
    print(f"Avg time/task: {stats['avg_time_per_task']:.1f}s")
    print(f"Total steps: {stats['total_steps']}")
    print(f"Total errors: {stats['total_errors']}")
    print(f"Success rate: {stats['success_rate']:.1%}")

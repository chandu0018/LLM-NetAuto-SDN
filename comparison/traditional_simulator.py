"""
Traditional Configuration Simulator for LLM-NetAuto-SDN.

Simulates manual CLI-based SDN configuration for research comparison.
"""

import os
import time
import random
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ManualStep:
    """A step in manual configuration."""
    step_number: int
    description: str
    category: str  # lookup, identify, build, execute, verify
    base_time: float  # seconds
    error_rate: float
    actual_time: float = 0.0
    error_occurred: bool = False
    error_description: str = ""


@dataclass
class ManualTask:
    """Complete manual configuration task."""
    task_id: str
    description: str
    steps: List[ManualStep] = field(default_factory=list)
    total_time: float = 0.0
    errors: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TraditionalConfigManager:
    """
    Simulates traditional manual SDN configuration.

    Used for research comparison against LLM-based approach.
    Records time, steps, and error metrics.
    """

    # Step category configurations
    STEP_CONFIGS = {
        "lookup": {
            "base_time": 20,
            "variance": 0.5,
            "error_rate": 0.05
        },
        "identify": {
            "base_time": 30,
            "variance": 0.4,
            "error_rate": 0.10
        },
        "build": {
            "base_time": 60,
            "variance": 0.6,
            "error_rate": 0.20
        },
        "execute": {
            "base_time": 15,
            "variance": 0.3,
            "error_rate": 0.08
        },
        "verify": {
            "base_time": 25,
            "variance": 0.4,
            "error_rate": 0.05
        },
        "debug": {
            "base_time": 120,
            "variance": 0.8,
            "error_rate": 0.10
        }
    }

    # Common errors by category
    ERRORS = {
        "lookup": [
            "Documentation outdated",
            "Multiple conflicting references",
            "Wrong protocol documentation"
        ],
        "identify": [
            "Wrong device ID format",
            "Host not in ARP table",
            "Stale topology data"
        ],
        "build": [
            "Invalid JSON syntax",
            "Missing required field",
            "Wrong match type",
            "Invalid port number",
            "Malformed MAC address"
        ],
        "execute": [
            "Connection timeout",
            "Authentication failed",
            "HTTP 400 Bad Request",
            "Device busy"
        ],
        "verify": [
            "Rule not installed",
            "Wrong traffic matched",
            "Connectivity test failed"
        ]
    }

    def __init__(self):
        """Initialize traditional config manager."""
        self._tasks: Dict[str, ManualTask] = {}
        self._current_task: Optional[ManualTask] = None
        self._task_counter = 0

        logger.info("TraditionalConfigManager initialized")

    def start_task(self, description: str) -> ManualTask:
        """Start a new configuration task."""
        self._task_counter += 1
        task_id = f"manual-{self._task_counter:04d}"

        task = ManualTask(
            task_id=task_id,
            description=description,
            started_at=datetime.now()
        )

        self._current_task = task
        self._tasks[task_id] = task

        logger.info(f"Started manual task: {description}")
        return task

    def add_step(
        self,
        description: str,
        category: str = "execute"
    ) -> ManualStep:
        """
        Add and simulate a configuration step.

        Args:
            description: Step description
            category: Step category for timing

        Returns:
            Completed step with metrics
        """
        if not self._current_task:
            raise ValueError("No active task")

        config = self.STEP_CONFIGS.get(category, self.STEP_CONFIGS["execute"])

        # Calculate time with variance
        variance = random.uniform(1 - config["variance"], 1 + config["variance"])
        actual_time = config["base_time"] * variance

        # Check for error
        error_occurred = random.random() < config["error_rate"]
        error_description = ""

        if error_occurred:
            # Add debug time
            debug_config = self.STEP_CONFIGS["debug"]
            debug_variance = random.uniform(
                1 - debug_config["variance"],
                1 + debug_config["variance"]
            )
            actual_time += debug_config["base_time"] * debug_variance

            # Get error description
            errors = self.ERRORS.get(category, ["Unknown error"])
            error_description = random.choice(errors)

        step = ManualStep(
            step_number=len(self._current_task.steps) + 1,
            description=description,
            category=category,
            base_time=config["base_time"],
            error_rate=config["error_rate"],
            actual_time=actual_time,
            error_occurred=error_occurred,
            error_description=error_description
        )

        self._current_task.steps.append(step)
        self._current_task.total_time += actual_time
        if error_occurred:
            self._current_task.errors += 1

        return step

    def complete_task(self) -> ManualTask:
        """Complete current task."""
        if not self._current_task:
            raise ValueError("No active task")

        self._current_task.completed_at = datetime.now()
        task = self._current_task
        self._current_task = None

        logger.info(
            f"Completed task: {task.description} "
            f"({task.total_time:.1f}s, {len(task.steps)} steps, "
            f"{task.errors} errors)"
        )

        return task

    # ==========================================
    # Pre-defined Task Simulations
    # ==========================================

    def simulate_add_flow(
        self,
        device_id: str,
        match: Dict[str, Any],
        action: str,
        priority: int
    ) -> ManualTask:
        """Simulate manually adding a flow rule."""
        self.start_task(f"Add flow to {device_id}")

        # Steps for manual flow addition
        self.add_step("Look up OpenFlow flow format", "lookup")
        self.add_step(f"Identify device {device_id}", "identify")
        self.add_step("Build flow match JSON", "build")
        self.add_step("Build flow action JSON", "build")
        self.add_step("Construct complete flow rule", "build")
        self.add_step("POST flow via REST API", "execute")
        self.add_step("Verify flow installed", "verify")

        return self.complete_task()

    def simulate_delete_flow(
        self,
        device_id: str,
        flow_id: str
    ) -> ManualTask:
        """Simulate manually deleting a flow rule."""
        self.start_task(f"Delete flow {flow_id} from {device_id}")

        self.add_step("Find flow ID in flow table", "identify")
        self.add_step("DELETE flow via REST API", "execute")
        self.add_step("Verify flow removed", "verify")

        return self.complete_task()

    def simulate_block_host(
        self,
        host_ip: str,
        all_switches: bool = True
    ) -> ManualTask:
        """Simulate blocking traffic from a host."""
        self.start_task(f"Block traffic from {host_ip}")

        self.add_step("Look up DROP action syntax", "lookup")
        self.add_step(f"Identify host {host_ip}", "identify")

        if all_switches:
            for i in range(1, 4):
                self.add_step(f"Find device ID for s{i}", "identify")
                self.add_step(f"Build DROP flow for s{i}", "build")
                self.add_step(f"POST flow to s{i}", "execute")

        self.add_step("Verify block is effective", "verify")

        return self.complete_task()

    def simulate_allow_protocol(
        self,
        src: str,
        dst: str,
        protocol: str,
        port: int
    ) -> ManualTask:
        """Simulate allowing specific protocol between hosts."""
        self.start_task(f"Allow {protocol}:{port} from {src} to {dst}")

        self.add_step(f"Look up {protocol} protocol number", "lookup")
        self.add_step(f"Find MAC/IP of {src}", "identify")
        self.add_step(f"Find MAC/IP of {dst}", "identify")
        self.add_step("Determine path between hosts", "identify")

        # For each switch on path
        for i in range(2):
            self.add_step(f"Build {protocol} allow flow", "build")
            self.add_step("POST flow rule", "execute")

        self.add_step("Test connectivity", "verify")

        return self.complete_task()

    def simulate_remediation(
        self,
        device_id: str,
        anomaly_type: str
    ) -> ManualTask:
        """Simulate manual anomaly remediation."""
        self.start_task(f"Remediate {anomaly_type} on {device_id}")

        self.add_step("Notice anomaly in monitoring", "identify")
        self.add_step("SSH to controller", "execute")
        self.add_step("Get flows from device", "identify")
        self.add_step("Analyze traffic statistics", "identify")
        self.add_step("Research remediation approach", "lookup")
        self.add_step("Build corrective rule", "build")
        self.add_step("Deploy corrective rule", "execute")
        self.add_step("Monitor for improvement", "verify")
        self.add_step("Verify fix", "verify")
        self.add_step("Document resolution", "execute")

        return self.complete_task()

    # ==========================================
    # Statistics
    # ==========================================

    def get_task(self, task_id: str) -> Optional[ManualTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[ManualTask]:
        """Get all completed tasks."""
        return [t for t in self._tasks.values() if t.completed_at]

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        tasks = self.get_all_tasks()

        if not tasks:
            return {
                "total_tasks": 0,
                "total_time": 0,
                "avg_time": 0,
                "total_steps": 0,
                "total_errors": 0,
                "error_rate": 0
            }

        total_time = sum(t.total_time for t in tasks)
        total_steps = sum(len(t.steps) for t in tasks)
        total_errors = sum(t.errors for t in tasks)

        return {
            "total_tasks": len(tasks),
            "total_time": total_time,
            "avg_time": total_time / len(tasks),
            "total_steps": total_steps,
            "avg_steps": total_steps / len(tasks),
            "total_errors": total_errors,
            "error_rate": total_errors / max(total_steps, 1),
            "tasks": [
                {
                    "id": t.task_id,
                    "description": t.description,
                    "time": t.total_time,
                    "steps": len(t.steps),
                    "errors": t.errors
                }
                for t in tasks
            ]
        }

    def compare_with_llm(
        self,
        llm_time: float,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        Compare manual task with LLM execution.

        Args:
            llm_time: LLM execution time in seconds
            task_id: Specific task to compare (latest if None)

        Returns:
            Comparison metrics
        """
        if task_id:
            task = self.get_task(task_id)
        else:
            tasks = self.get_all_tasks()
            task = tasks[-1] if tasks else None

        if not task:
            return {"error": "No task to compare"}

        return {
            "task": task.description,
            "manual": {
                "time": task.total_time,
                "steps": len(task.steps),
                "errors": task.errors,
                "expertise": "High"
            },
            "llm": {
                "time": llm_time,
                "steps": 1,
                "errors": 0,
                "expertise": "None"
            },
            "improvement": {
                "time_reduction": (
                    (task.total_time - llm_time) / task.total_time * 100
                ),
                "steps_reduction": (
                    (len(task.steps) - 1) / len(task.steps) * 100
                ),
                "time_saved": task.total_time - llm_time
            }
        }


# Singleton instance
_manager_instance: Optional[TraditionalConfigManager] = None


def get_traditional_config_manager() -> TraditionalConfigManager:
    """Get or create the global manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TraditionalConfigManager()
    return _manager_instance


if __name__ == "__main__":
    # Test traditional config manager
    import json

    print("\n=== Traditional Config Manager Test ===\n")

    manager = TraditionalConfigManager()

    # Simulate blocking a host
    task1 = manager.simulate_block_host("10.0.0.1")
    print(f"Task 1: {task1.description}")
    print(f"  Time: {task1.total_time:.1f}s")
    print(f"  Steps: {len(task1.steps)}")
    print(f"  Errors: {task1.errors}")

    # Simulate allowing protocol
    task2 = manager.simulate_allow_protocol("h1", "h3", "tcp", 80)
    print(f"\nTask 2: {task2.description}")
    print(f"  Time: {task2.total_time:.1f}s")
    print(f"  Steps: {len(task2.steps)}")
    print(f"  Errors: {task2.errors}")

    # Simulate remediation
    task3 = manager.simulate_remediation("of:0000000000000001", "traffic_spike")
    print(f"\nTask 3: {task3.description}")
    print(f"  Time: {task3.total_time:.1f}s")
    print(f"  Steps: {len(task3.steps)}")
    print(f"  Errors: {task3.errors}")

    # Statistics
    print("\n=== Statistics ===")
    stats = manager.get_statistics()
    print(f"Total tasks: {stats['total_tasks']}")
    print(f"Total time: {stats['total_time']:.1f}s")
    print(f"Avg time: {stats['avg_time']:.1f}s")
    print(f"Total steps: {stats['total_steps']}")
    print(f"Total errors: {stats['total_errors']}")
    print(f"Error rate: {stats['error_rate']:.1%}")

    # Compare with hypothetical LLM time
    print("\n=== Comparison with LLM ===")
    comparison = manager.compare_with_llm(1.5)
    print(json.dumps(comparison, indent=2))

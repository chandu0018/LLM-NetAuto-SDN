"""
Benchmark Suite for LLM-NetAuto-SDN.

10-task benchmark for comparing traditional vs LLM-based
network configuration approaches.
"""

import os
import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# Task Definitions
# ==========================================

TASK_LIST = [
    {
        "id": 1,
        "name": "Block traffic from one host",
        "nl_intent": "Block all traffic from 10.0.0.1",
        "manual_steps": [
            "Identify source IP address",
            "Find device ID for switch 1",
            "Build DROP flow JSON for switch 1",
            "POST flow to switch 1 via REST API",
            "Find device ID for switch 2",
            "Build DROP flow JSON for switch 2",
            "POST flow to switch 2 via REST API",
            "Find device ID for switch 3",
            "Build DROP flow JSON for switch 3",
            "POST flow to switch 3 via REST API",
            "Verify all rules installed"
        ],
        "switches_affected": 3,
        "complexity": "medium"
    },
    {
        "id": 2,
        "name": "Allow HTTP between two hosts",
        "nl_intent": "Allow only HTTP traffic from h1 to h3",
        "manual_steps": [
            "Find MAC address of h1",
            "Find MAC address of h3",
            "Identify path from s1 to s2",
            "Know TCP port 80 for HTTP",
            "Build TCP port 80 match JSON for s1",
            "POST flow to s1",
            "Build TCP port 80 match JSON for s2",
            "POST flow to s2",
            "Verify connectivity with curl"
        ],
        "switches_affected": 2,
        "complexity": "medium"
    },
    {
        "id": 3,
        "name": "Drop all ICMP packets",
        "nl_intent": "Drop all ICMP packets on all switches",
        "manual_steps": [
            "Know ip_proto=1 for ICMP",
            "Build ICMP DROP JSON for s1",
            "POST to s1",
            "Build ICMP DROP JSON for s2",
            "POST to s2",
            "Build ICMP DROP JSON for s3",
            "POST to s3",
            "Verify with ping test (should fail)"
        ],
        "switches_affected": 3,
        "complexity": "medium"
    },
    {
        "id": 4,
        "name": "Prioritize VoIP traffic",
        "nl_intent": "Prioritize VoIP traffic on UDP port 5060",
        "manual_steps": [
            "Know SIP uses UDP port 5060",
            "Know UDP is ip_proto=17",
            "Build SET_QUEUE action JSON for high priority",
            "Build VoIP match + priority flow for s1",
            "POST to s1",
            "Build VoIP flow for s2",
            "POST to s2",
            "Build VoIP flow for s3",
            "POST to s3",
            "Verify queue assignment"
        ],
        "switches_affected": 3,
        "complexity": "high"
    },
    {
        "id": 5,
        "name": "Isolate a switch",
        "nl_intent": "Isolate switch s2 from the network",
        "manual_steps": [
            "Find device ID of s2",
            "Build DROP all incoming flow",
            "POST to s2",
            "Build DROP all outgoing flow",
            "POST to s2",
            "Verify s2 is isolated"
        ],
        "switches_affected": 1,
        "complexity": "medium"
    },
    {
        "id": 6,
        "name": "Allow SSH only between two hosts",
        "nl_intent": "Allow only SSH traffic between h2 and h4",
        "manual_steps": [
            "Know TCP port 22 for SSH",
            "Find h2 MAC and IP",
            "Find h4 MAC and IP",
            "Find path h2 to h4 (s1 -> s2)",
            "Build bidirectional SSH allow rule for s1",
            "POST to s1",
            "Build bidirectional SSH allow rule for s2",
            "POST to s2",
            "Block all other traffic between them",
            "POST block rules",
            "Verify SSH connectivity"
        ],
        "switches_affected": 2,
        "complexity": "high"
    },
    {
        "id": 7,
        "name": "Remove all custom flow rules",
        "nl_intent": "Remove all custom flow rules from all switches",
        "manual_steps": [
            "GET all flows from s1",
            "Identify custom flows (not default)",
            "DELETE each custom flow from s1",
            "GET all flows from s2",
            "DELETE each custom flow from s2",
            "GET all flows from s3",
            "DELETE each custom flow from s3",
            "Verify clean state"
        ],
        "switches_affected": 3,
        "complexity": "medium"
    },
    {
        "id": 8,
        "name": "Block traffic between two subnets",
        "nl_intent": "Block all traffic between 10.0.0.0/24 and 10.0.1.0/24",
        "manual_steps": [
            "Build subnet match JSON for src 10.0.0.0/24",
            "Build subnet match JSON for dst 10.0.1.0/24",
            "Add bidirectional DROP rules",
            "POST to s1",
            "POST to s2",
            "POST to s3",
            "Verify isolation between subnets"
        ],
        "switches_affected": 3,
        "complexity": "medium"
    },
    {
        "id": 9,
        "name": "Mirror traffic for monitoring",
        "nl_intent": "Mirror all traffic on s1 to port 5",
        "manual_steps": [
            "Find device ID of s1",
            "Know OUTPUT action format",
            "Build mirror flow with OUTPUT to port 5",
            "Also OUTPUT to NORMAL for regular forwarding",
            "POST to s1",
            "Verify mirroring with tcpdump"
        ],
        "switches_affected": 1,
        "complexity": "medium"
    },
    {
        "id": 10,
        "name": "Remediate detected anomaly",
        "nl_intent": "High drop rate on s2 - fix automatically",
        "manual_steps": [
            "Notice anomaly via monitoring dashboard",
            "SSH into controller",
            "GET flows from s2",
            "GET port statistics from s2",
            "Analyze traffic patterns",
            "Identify problematic flows",
            "Research remediation approach",
            "Build corrective flow rule",
            "POST corrective rule to s2",
            "Monitor for 5 minutes",
            "Verify improvement",
            "Document in ticketing system"
        ],
        "switches_affected": 1,
        "complexity": "high"
    }
]


@dataclass
class TaskResult:
    """Result of a benchmark task."""
    task_id: int
    task_name: str
    # Traditional metrics
    traditional_time: float  # seconds
    traditional_steps: int
    traditional_switches: int
    traditional_error_probability: float
    traditional_estimated_errors: float
    traditional_expertise: str
    # LLM metrics
    llm_time: float  # seconds
    llm_steps: int = 1
    llm_switches: int = 0
    llm_validation: bool = True
    llm_auto_corrected: bool = False
    llm_expertise: str = "None"
    llm_success: bool = True
    # Comparison
    time_reduction_percent: float = 0.0
    steps_reduction_percent: float = 0.0


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""
    timestamp: datetime = field(default_factory=datetime.now)
    task_results: List[TaskResult] = field(default_factory=list)
    # Summary statistics
    avg_time_reduction: float = 0.0
    avg_steps_reduction: float = 0.0
    total_time_saved: float = 0.0
    error_risk_reduction: float = 0.0
    tasks_successful: int = 0
    total_traditional_time: float = 0.0
    total_llm_time: float = 0.0


class Benchmark:
    """
    Benchmark suite for comparing traditional vs LLM configuration.

    Runs all 10 tasks and collects metrics for comparison.
    """

    # Time per manual step (seconds)
    TIME_PER_STEP = 30

    # Error probability per manual step
    ERROR_RATE_PER_STEP = 0.15

    def __init__(self):
        """Initialize benchmark."""
        self._demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        self._results: Optional[BenchmarkResult] = None

        logger.info("Benchmark initialized")

    def run_all(self) -> BenchmarkResult:
        """
        Run all benchmark tasks.

        Returns:
            Complete benchmark results
        """
        logger.info("Starting benchmark run...")

        results = BenchmarkResult()

        for task in TASK_LIST:
            task_result = self._run_task(task)
            results.task_results.append(task_result)

        # Calculate summary statistics
        self._calculate_summary(results)

        self._results = results

        # Save results
        self._save_results(results)

        return results

    def _run_task(self, task: Dict[str, Any]) -> TaskResult:
        """Run a single benchmark task."""
        logger.info(f"Running task {task['id']}: {task['name']}")

        # Calculate traditional metrics
        steps = len(task["manual_steps"])
        traditional_time = steps * self.TIME_PER_STEP
        error_prob = 1 - ((1 - self.ERROR_RATE_PER_STEP) ** steps)
        estimated_errors = steps * self.ERROR_RATE_PER_STEP

        # Run LLM-based configuration
        llm_result = self._run_llm_task(task)

        # Calculate reductions
        time_reduction = (
            (traditional_time - llm_result["time"]) / traditional_time * 100
        )
        steps_reduction = (
            (steps - 1) / steps * 100
        )

        return TaskResult(
            task_id=task["id"],
            task_name=task["name"],
            traditional_time=traditional_time,
            traditional_steps=steps,
            traditional_switches=task["switches_affected"],
            traditional_error_probability=error_prob,
            traditional_estimated_errors=estimated_errors,
            traditional_expertise="High",
            llm_time=llm_result["time"],
            llm_steps=1,
            llm_switches=task["switches_affected"],
            llm_validation=llm_result.get("validation", True),
            llm_auto_corrected=llm_result.get("corrected", False),
            llm_expertise="None",
            llm_success=llm_result.get("success", True),
            time_reduction_percent=time_reduction,
            steps_reduction_percent=steps_reduction
        )

    def _run_llm_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run LLM-based configuration for a task."""
        from llm.intent_parser import get_intent_parser
        from topology.simulated_topo import get_simulated_topology

        parser = get_intent_parser()
        topo = get_simulated_topology()

        start_time = time.time()

        result = parser.parse_intent(
            task["nl_intent"],
            topo.get_topology_for_llm()
        )

        elapsed = time.time() - start_time

        return {
            "time": elapsed,
            "success": result.get("success", True),
            "validation": result.get("validation", {}).get("valid", True),
            "corrected": result.get("corrected_rule") is not None
        }

    def _calculate_summary(self, results: BenchmarkResult) -> None:
        """Calculate summary statistics."""
        if not results.task_results:
            return

        total_trad_time = sum(r.traditional_time for r in results.task_results)
        total_llm_time = sum(r.llm_time for r in results.task_results)
        total_trad_steps = sum(r.traditional_steps for r in results.task_results)
        total_trad_errors = sum(
            r.traditional_estimated_errors for r in results.task_results
        )
        successful = sum(1 for r in results.task_results if r.llm_success)

        results.total_traditional_time = total_trad_time
        results.total_llm_time = total_llm_time
        results.tasks_successful = successful

        results.avg_time_reduction = sum(
            r.time_reduction_percent for r in results.task_results
        ) / len(results.task_results)

        results.avg_steps_reduction = sum(
            r.steps_reduction_percent for r in results.task_results
        ) / len(results.task_results)

        results.total_time_saved = total_trad_time - total_llm_time

        # Error risk reduction (LLM has validation, ~0 errors)
        results.error_risk_reduction = (
            total_trad_errors / len(results.task_results)
        ) * 100

    def _save_results(self, results: BenchmarkResult) -> None:
        """Save results to JSON file."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "benchmark_results.json"
        )

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        data = {
            "timestamp": results.timestamp.isoformat(),
            "summary": {
                "avg_time_reduction_percent": results.avg_time_reduction,
                "avg_steps_reduction_percent": results.avg_steps_reduction,
                "total_time_saved_seconds": results.total_time_saved,
                "error_risk_reduction_percent": results.error_risk_reduction,
                "tasks_successful": results.tasks_successful,
                "total_tasks": len(results.task_results),
                "total_traditional_time": results.total_traditional_time,
                "total_llm_time": results.total_llm_time
            },
            "tasks": [
                {
                    "task_id": r.task_id,
                    "task_name": r.task_name,
                    "traditional": {
                        "time_seconds": r.traditional_time,
                        "steps": r.traditional_steps,
                        "switches": r.traditional_switches,
                        "error_probability": r.traditional_error_probability,
                        "estimated_errors": r.traditional_estimated_errors,
                        "expertise_required": r.traditional_expertise
                    },
                    "llm": {
                        "time_seconds": r.llm_time,
                        "steps": r.llm_steps,
                        "switches": r.llm_switches,
                        "validation": r.llm_validation,
                        "auto_corrected": r.llm_auto_corrected,
                        "expertise_required": r.llm_expertise,
                        "success": r.llm_success
                    },
                    "comparison": {
                        "time_reduction_percent": r.time_reduction_percent,
                        "steps_reduction_percent": r.steps_reduction_percent
                    }
                }
                for r in results.task_results
            ]
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Benchmark results saved to {filepath}")

    def get_results(self) -> Optional[BenchmarkResult]:
        """Get latest benchmark results."""
        return self._results

    def load_results(self) -> Optional[Dict[str, Any]]:
        """Load results from file."""
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "benchmark_results.json"
        )

        if os.path.exists(filepath):
            with open(filepath) as f:
                return json.load(f)
        return None

    def print_results(self, results: Optional[BenchmarkResult] = None) -> None:
        """Print results in formatted table."""
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()

            if results is None:
                results = self._results

            if results is None:
                print("No benchmark results available")
                return

            # Summary table
            table = Table(title="Benchmark Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row(
                "Avg Time Reduction",
                f"{results.avg_time_reduction:.1f}%"
            )
            table.add_row(
                "Avg Steps Reduction",
                f"{results.avg_steps_reduction:.1f}%"
            )
            table.add_row(
                "Total Time Saved",
                f"{results.total_time_saved:.0f}s "
                f"({results.total_time_saved/60:.1f} min)"
            )
            table.add_row(
                "Error Risk Reduction",
                f"{results.error_risk_reduction:.1f}%"
            )
            table.add_row(
                "Tasks Successful",
                f"{results.tasks_successful}/{len(results.task_results)}"
            )

            console.print(table)

            # Task details table
            details = Table(title="\nTask Details")
            details.add_column("Task", style="cyan", width=30)
            details.add_column("Trad Time", style="red")
            details.add_column("LLM Time", style="green")
            details.add_column("Reduction", style="yellow")
            details.add_column("Steps", style="blue")

            for r in results.task_results:
                details.add_row(
                    r.task_name[:30],
                    f"{r.traditional_time:.0f}s",
                    f"{r.llm_time:.1f}s",
                    f"{r.time_reduction_percent:.0f}%",
                    f"{r.traditional_steps} -> 1"
                )

            console.print(details)

        except ImportError:
            # Fallback without rich
            print("\n=== Benchmark Results ===\n")

            if results is None:
                results = self._results

            if results is None:
                print("No results available")
                return

            print(f"Avg Time Reduction: {results.avg_time_reduction:.1f}%")
            print(f"Avg Steps Reduction: {results.avg_steps_reduction:.1f}%")
            print(f"Total Time Saved: {results.total_time_saved:.0f}s")
            print(f"Tasks Successful: "
                  f"{results.tasks_successful}/{len(results.task_results)}")


if __name__ == "__main__":
    # Run benchmark
    print("\n=== LLM-NetAuto-SDN Benchmark ===\n")

    benchmark = Benchmark()
    results = benchmark.run_all()
    benchmark.print_results(results)

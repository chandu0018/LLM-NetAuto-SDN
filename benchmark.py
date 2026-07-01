#!/usr/bin/env python3
"""
Benchmark Runner for LLM-NetAuto-SDN.

Runs the 10-task benchmark suite comparing traditional
vs LLM-based SDN configuration approaches.
"""

import os
import sys
import json
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def run_benchmark():
    """Run the complete benchmark suite."""
    from comparison.benchmark import Benchmark, TASK_LIST
    from simulation.sim_engine import get_simulation_engine
    from comparison.traditional_simulator import get_traditional_config_manager

    print("\n" + "=" * 60)
    print("  LLM-NetAuto-SDN Benchmark Suite")
    print("=" * 60)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DEMO' if os.getenv('DEMO_MODE', 'true').lower() == 'true' else 'LIVE'}")
    print(f"Tasks: {len(TASK_LIST)}")
    print("\n" + "-" * 60)

    # Initialize components
    engine = get_simulation_engine()
    benchmark = Benchmark()
    trad_manager = get_traditional_config_manager()

    results = []
    total_trad_time = 0
    total_llm_time = 0

    for i, task in enumerate(TASK_LIST, 1):
        print(f"\n[{i}/{len(TASK_LIST)}] {task['name']}")
        print(f"    Intent: \"{task['intent']}\"")

        # Reset simulation
        engine.reset()

        # Run LLM approach
        llm_start = time.time()
        llm_result = engine.process_intent(task["intent"])
        llm_time = time.time() - llm_start

        # Run traditional approach (simulated)
        trad_task = None
        if task.get("traditional_method"):
            method = task["traditional_method"]
            if method == "block_host":
                trad_task = trad_manager.simulate_block_host(
                    task.get("params", {}).get("host_ip", "10.0.0.1")
                )
            elif method == "allow_protocol":
                params = task.get("params", {})
                trad_task = trad_manager.simulate_allow_protocol(
                    params.get("src", "h1"),
                    params.get("dst", "h3"),
                    params.get("protocol", "tcp"),
                    params.get("port", 80)
                )
            elif method == "remediation":
                params = task.get("params", {})
                trad_task = trad_manager.simulate_remediation(
                    params.get("device_id", "of:0000000000000001"),
                    params.get("anomaly_type", "traffic_spike")
                )
            else:
                # Default simulation
                trad_task = trad_manager.simulate_block_host("10.0.0.1")

        trad_time = trad_task.total_time if trad_task else task.get("expected_trad_time", 300)
        trad_steps = len(trad_task.steps) if trad_task else task.get("expected_trad_steps", 10)

        # Calculate metrics
        time_reduction = ((trad_time - llm_time) / trad_time * 100) if trad_time > 0 else 0
        steps_reduction = ((trad_steps - 1) / trad_steps * 100) if trad_steps > 0 else 0

        result = {
            "task_id": i,
            "task_name": task["name"],
            "intent": task["intent"],
            "llm_success": llm_result.get("success", False),
            "llm_time_seconds": llm_time,
            "llm_latency_ms": llm_result.get("latency_ms", 0),
            "traditional_time_seconds": trad_time,
            "traditional_steps": trad_steps,
            "traditional_errors": trad_task.errors if trad_task else 0,
            "time_reduction_percent": time_reduction,
            "steps_reduction_percent": steps_reduction,
            "time_saved_seconds": trad_time - llm_time
        }
        results.append(result)

        total_trad_time += trad_time
        total_llm_time += llm_time

        # Print result
        status = "✓" if llm_result.get("success", False) else "✗"
        print(f"    {status} LLM: {llm_time:.2f}s | Traditional: {trad_time:.1f}s | "
              f"Reduction: {time_reduction:.1f}%")

    # Calculate summary
    successful = sum(1 for r in results if r["llm_success"])
    avg_time_reduction = sum(r["time_reduction_percent"] for r in results) / len(results)
    avg_steps_reduction = sum(r["steps_reduction_percent"] for r in results) / len(results)
    total_time_saved = total_trad_time - total_llm_time

    summary = {
        "total_tasks": len(results),
        "successful_tasks": successful,
        "success_rate": successful / len(results) * 100,
        "total_traditional_time_seconds": total_trad_time,
        "total_llm_time_seconds": total_llm_time,
        "total_time_saved_seconds": total_time_saved,
        "avg_time_reduction_percent": avg_time_reduction,
        "avg_steps_reduction_percent": avg_steps_reduction,
        "timestamp": datetime.now().isoformat()
    }

    # Print summary
    print("\n" + "=" * 60)
    print("  BENCHMARK RESULTS")
    print("=" * 60)
    print(f"\n  Tasks Completed: {successful}/{len(results)} ({summary['success_rate']:.0f}%)")
    print(f"\n  Traditional Approach:")
    print(f"    Total Time: {total_trad_time:.1f} seconds ({total_trad_time/60:.1f} minutes)")
    print(f"\n  LLM-NetAuto Approach:")
    print(f"    Total Time: {total_llm_time:.2f} seconds")
    print(f"\n  Improvements:")
    print(f"    Time Reduction: {avg_time_reduction:.1f}%")
    print(f"    Steps Reduction: {avg_steps_reduction:.1f}%")
    print(f"    Total Time Saved: {total_time_saved:.1f} seconds ({total_time_saved/60:.1f} minutes)")
    print("\n" + "=" * 60)

    # Save results
    output = {
        "summary": summary,
        "tasks": results
    }

    output_file = f"data/benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("data", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print("=" * 60 + "\n")

    return output


if __name__ == "__main__":
    run_benchmark()

"""Comparison module for traditional vs LLM benchmarking."""

from .benchmark import Benchmark, TASK_LIST
from .traditional_simulator import TraditionalConfigManager

__all__ = ["Benchmark", "TASK_LIST", "TraditionalConfigManager"]

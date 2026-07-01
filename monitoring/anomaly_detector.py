"""
Anomaly Detector for LLM-NetAuto-SDN.

Uses IsolationForest for unsupervised anomaly detection
on network telemetry data.
"""

import os
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque

import numpy as np
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class AnomalyDetector:
    """
    Network anomaly detector using IsolationForest.

    Features:
    - Auto-trains on first N samples
    - Detects anomalies in real-time
    - Tracks anomaly history
    - Supports retraining
    """

    # Feature names for detection
    FEATURES = [
        "bytes_rx_rate",
        "bytes_tx_rate",
        "packets_rx_rate",
        "drop_rate",
        "error_rate"
    ]

    def __init__(self, contamination: float = None):
        """
        Initialize anomaly detector.

        Args:
            contamination: Expected anomaly ratio (default from env)
        """
        self._contamination = contamination or float(
            os.getenv("ANOMALY_CONTAMINATION", "0.05")
        )
        self._threshold = float(os.getenv("ANOMALY_THRESHOLD", "-0.5"))
        self._min_samples_for_training = 100

        self._lock = threading.Lock()
        self._model = None
        self._is_trained = False
        self._training_data: List[np.ndarray] = []
        self._anomaly_history: deque = deque(maxlen=200)

        self._initialize_model()
        self._preseed_baseline_data()

        logger.info(
            f"AnomalyDetector initialized "
            f"(contamination={self._contamination})"
        )

    def _preseed_baseline_data(self) -> None:
        """Preseed the detector with normal baseline data so it is immediately trained."""
        import random
        logger.info("Pre-seeding anomaly detector with baseline normal data...")
        for _ in range(120):
            sample = {
                "timestamp": datetime.now().isoformat(),
                "device_id": "of:0000000000000001",
                "rates": {
                    "bytes_rx_rate": random.gauss(5e6, 1e6),
                    "bytes_tx_rate": random.gauss(4e6, 1e6),
                    "packets_rx_rate": random.gauss(10000, 2000),
                    "drop_rate": max(0.0, random.gauss(0.001, 0.0005)),
                    "error_rate": max(0.0, random.gauss(0.0001, 0.00005))
                }
            }
            self.add_sample(sample)

    def _initialize_model(self) -> None:
        """Initialize the IsolationForest model."""
        try:
            from sklearn.ensemble import IsolationForest

            self._model = IsolationForest(
                contamination=self._contamination,
                n_estimators=100,
                max_samples="auto",
                random_state=42,
                n_jobs=-1
            )
            logger.debug("IsolationForest model created")
        except ImportError:
            logger.error("scikit-learn not installed")
            self._model = None

    def add_sample(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Add a telemetry sample for detection.

        Args:
            sample: Telemetry sample with rates

        Returns:
            Anomaly result if detected, None otherwise
        """
        if self._model is None:
            return None

        with self._lock:
            # Extract features
            features = self._extract_features(sample)
            if features is None:
                return None

            # Add to training data if not yet trained
            if not self._is_trained:
                self._training_data.append(features)

                # Auto-train when enough samples
                if len(self._training_data) >= self._min_samples_for_training:
                    self._train()

                return None

            # Classify
            return self._classify(features, sample)

    def _extract_features(
        self,
        sample: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Extract feature vector from sample."""
        rates = sample.get("rates", {})
        if not rates:
            return None

        features = []
        for f in self.FEATURES:
            val = rates.get(f, 0.0)
            # Normalize large values
            if f.endswith("_rate") and "bytes" in f:
                val = val / 1e6  # Scale to MB/s
            features.append(val)

        return np.array(features)

    def _train(self) -> None:
        """Train the model on collected data."""
        if len(self._training_data) < self._min_samples_for_training:
            logger.warning("Not enough samples for training")
            return

        try:
            X = np.array(self._training_data)
            self._model.fit(X)
            self._is_trained = True
            logger.info(
                f"AnomalyDetector trained on {len(self._training_data)} samples"
            )
        except Exception as e:
            logger.error(f"Training failed: {e}")

    def _classify(
        self,
        features: np.ndarray,
        sample: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Classify a sample."""
        try:
            # Get anomaly score (-1 = anomaly, 1 = normal)
            score = self._model.score_samples([features])[0]
            prediction = self._model.predict([features])[0]

            is_anomaly = bool(prediction == -1 or score < self._threshold)
            anomaly_type = "unknown"
            if is_anomaly:
                anomaly_type = self._determine_anomaly_type(features)
                if anomaly_type == "unknown":
                    is_anomaly = False

            result = {
                "timestamp": sample.get("timestamp", datetime.now().isoformat()),
                "device_id": sample.get("device_id", "unknown"),
                "score": float(score),
                "is_anomaly": is_anomaly,
                "features": {
                    self.FEATURES[i]: float(features[i])
                    for i in range(len(self.FEATURES))
                }
            }

            if is_anomaly:
                # Determine anomaly type based on features
                result["type"] = anomaly_type
                self._anomaly_history.append(result)
                logger.warning(
                    f"Anomaly detected on {result['device_id']}: "
                    f"score={score:.3f}, type={result['type']}"
                )

            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return None

    def _determine_anomaly_type(self, features: np.ndarray) -> str:
        """Determine the type of anomaly based on features."""
        # Index: bytes_rx(0), bytes_tx(1), packets_rx(2), drop(3), error(4)

        # High drop rate
        if features[3] > 0.05:  # >5% drops
            return "packet_drop"

        # High error rate
        if features[4] > 0.01:  # >1% errors
            return "error_spike"

        # Traffic spike (high byte rates)
        if features[0] > 50 or features[1] > 50:  # >50 MB/s
            return "traffic_spike"

        # Asymmetric traffic (might be DDoS)
        if features[0] > 10 * max(features[1], 0.1):
            return "ddos_sim"

        # Bandwidth hog
        if features[1] > 20:  # High TX
            return "bandwidth_hog"

        return "unknown"

    # ==========================================
    # Public API
    # ==========================================

    def classify(self, sample: Dict[str, Any]) -> str:
        """
        Classify a single sample.

        Args:
            sample: Telemetry sample

        Returns:
            "normal" or "anomaly"
        """
        result = self.add_sample(sample)
        if result and result.get("is_anomaly"):
            return "anomaly"
        return "normal"

    def get_score(self, sample: Dict[str, Any]) -> float:
        """
        Get anomaly score for a sample.

        Args:
            sample: Telemetry sample

        Returns:
            Anomaly score (lower = more anomalous)
        """
        if not self._is_trained or self._model is None:
            return 0.0

        with self._lock:
            features = self._extract_features(sample)
            if features is None:
                return 0.0

            try:
                return float(self._model.score_samples([features])[0])
            except Exception:
                return 0.0

    def retrain(self, samples: List[Dict[str, Any]]) -> bool:
        """
        Retrain model with new samples.

        Args:
            samples: List of telemetry samples

        Returns:
            True if training succeeded
        """
        with self._lock:
            self._training_data = []
            for sample in samples:
                features = self._extract_features(sample)
                if features is not None:
                    self._training_data.append(features)

            if len(self._training_data) >= self._min_samples_for_training:
                self._train()
                return True
            return False

    def get_anomaly_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get anomaly history.

        Args:
            limit: Maximum entries to return

        Returns:
            List of anomaly records
        """
        with self._lock:
            history = list(self._anomaly_history)
            if limit:
                return history[-limit:]
            return history

    def is_trained(self) -> bool:
        """Check if model is trained."""
        return self._is_trained

    def get_status(self) -> Dict[str, Any]:
        """Get detector status."""
        with self._lock:
            return {
                "is_trained": self._is_trained,
                "training_samples": len(self._training_data),
                "min_samples_required": self._min_samples_for_training,
                "contamination": self._contamination,
                "threshold": self._threshold,
                "anomalies_detected": len(self._anomaly_history),
                "model_type": "IsolationForest"
            }

    def reset(self) -> None:
        """Reset detector to untrained state."""
        with self._lock:
            self._training_data = []
            self._is_trained = False
            self._anomaly_history.clear()
            self._initialize_model()
            logger.info("AnomalyDetector reset")

    def clear_history(self) -> None:
        """Clear anomaly detection history only, without resetting trained state."""
        with self._lock:
            self._anomaly_history.clear()
        logger.info("AnomalyDetector history cleared")


# Singleton instance
_detector_instance: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create the global anomaly detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AnomalyDetector()
    return _detector_instance


if __name__ == "__main__":
    # Test anomaly detector
    import random

    print("\n=== Anomaly Detector Test ===\n")

    detector = AnomalyDetector()

    # Generate normal training data
    print("Generating training data...")
    for i in range(150):
        sample = {
            "timestamp": datetime.now().isoformat(),
            "device_id": "of:0000000000000001",
            "rates": {
                "bytes_rx_rate": random.gauss(5e6, 1e6),  # ~5 MB/s
                "bytes_tx_rate": random.gauss(4e6, 1e6),  # ~4 MB/s
                "packets_rx_rate": random.gauss(10000, 2000),
                "drop_rate": random.gauss(0.001, 0.0005),
                "error_rate": random.gauss(0.0001, 0.00005)
            }
        }
        detector.add_sample(sample)

    print(f"Is trained: {detector.is_trained()}")

    # Test with normal sample
    print("\nTesting normal sample...")
    normal = {
        "timestamp": datetime.now().isoformat(),
        "device_id": "of:0000000000000001",
        "rates": {
            "bytes_rx_rate": 5e6,
            "bytes_tx_rate": 4e6,
            "packets_rx_rate": 10000,
            "drop_rate": 0.001,
            "error_rate": 0.0001
        }
    }
    result = detector.add_sample(normal)
    print(f"  Score: {result.get('score', 0):.3f}")
    print(f"  Is anomaly: {result.get('is_anomaly', False)}")

    # Test with anomaly (traffic spike)
    print("\nTesting anomaly (traffic spike)...")
    anomaly = {
        "timestamp": datetime.now().isoformat(),
        "device_id": "of:0000000000000001",
        "rates": {
            "bytes_rx_rate": 100e6,  # 100 MB/s (20x normal)
            "bytes_tx_rate": 4e6,
            "packets_rx_rate": 200000,
            "drop_rate": 0.001,
            "error_rate": 0.0001
        }
    }
    result = detector.add_sample(anomaly)
    print(f"  Score: {result.get('score', 0):.3f}")
    print(f"  Is anomaly: {result.get('is_anomaly', False)}")
    print(f"  Type: {result.get('type', 'unknown')}")

    # Test with anomaly (packet drops)
    print("\nTesting anomaly (packet drops)...")
    anomaly2 = {
        "timestamp": datetime.now().isoformat(),
        "device_id": "of:0000000000000001",
        "rates": {
            "bytes_rx_rate": 5e6,
            "bytes_tx_rate": 4e6,
            "packets_rx_rate": 10000,
            "drop_rate": 0.15,  # 15% drops
            "error_rate": 0.0001
        }
    }
    result = detector.add_sample(anomaly2)
    print(f"  Score: {result.get('score', 0):.3f}")
    print(f"  Is anomaly: {result.get('is_anomaly', False)}")
    print(f"  Type: {result.get('type', 'unknown')}")

    print("\nStatus:")
    status = detector.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

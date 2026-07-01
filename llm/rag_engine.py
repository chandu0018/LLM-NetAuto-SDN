"""
RAG Engine for LLM-NetAuto-SDN.

Provides vector database functionality using ChromaDB for
semantic search over topology, intents, and remediations.
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class NumPyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def safe_json_dumps(obj: Any) -> str:
    """Safely dump JSON using custom encoder."""
    return json.dumps(obj, cls=NumPyEncoder)


class RAGEngine:
    """
    RAG (Retrieval-Augmented Generation) Engine using ChromaDB.

    Collections:
    - topology: Device, host, link information
    - intents: Successfully deployed intents
    - remediations: Past anomaly + remediation pairs

    In DEMO_MODE, falls back to in-memory dict if ChromaDB unavailable.
    """

    def __init__(self):
        """Initialize RAG engine with ChromaDB or fallback."""
        self._demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        self._chromadb_host = os.getenv("CHROMADB_HOST", "127.0.0.1")
        self._chromadb_port = int(os.getenv("CHROMADB_PORT", "8001"))
        self._persist_path = os.getenv(
            "CHROMADB_PERSIST_PATH",
            "./data/chromadb"
        )

        self._client = None
        self._collections: Dict[str, Any] = {}
        self._fallback_store: Dict[str, List[Dict]] = {
            "topology": [],
            "intents": [],
            "remediations": []
        }
        self._use_fallback = False

        self._initialize_chromadb()

    def _initialize_chromadb(self) -> None:
        """Initialize ChromaDB client and collections."""
        try:
            import chromadb
            from chromadb.config import Settings

            # Try HTTP client first (for Docker ChromaDB)
            try:
                self._client = chromadb.HttpClient(
                    host=self._chromadb_host,
                    port=self._chromadb_port
                )
                # Test connection
                self._client.heartbeat()
                logger.info(
                    f"Connected to ChromaDB HTTP: "
                    f"{self._chromadb_host}:{self._chromadb_port}"
                )
            except Exception:
                # Fall back to persistent client
                logger.info(
                    "ChromaDB HTTP not available, using persistent client"
                )
                self._client = chromadb.PersistentClient(
                    path=self._persist_path,
                    settings=Settings(anonymized_telemetry=False)
                )

            # Create or get collections
            self._collections["topology"] = self._client.get_or_create_collection(
                name="topology",
                metadata={"description": "Network topology information"}
            )
            self._collections["intents"] = self._client.get_or_create_collection(
                name="intents",
                metadata={"description": "Deployed network intents"}
            )
            self._collections["remediations"] = self._client.get_or_create_collection(
                name="remediations",
                metadata={"description": "Anomaly remediation history"}
            )

            logger.info("ChromaDB collections initialized")

        except ImportError:
            logger.warning("ChromaDB not installed, using fallback store")
            self._use_fallback = True
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}")
            self._use_fallback = True

    def _is_available(self) -> bool:
        """Check if ChromaDB is available."""
        return not self._use_fallback and self._client is not None

    # ==========================================
    # Topology Collection
    # ==========================================

    def seed_topology(self, topology_data: Dict[str, Any]) -> bool:
        """
        Seed the topology collection with network data.

        Args:
            topology_data: Dictionary with devices, hosts, links

        Returns:
            True if seeding succeeded
        """
        try:
            documents = []
            metadatas = []
            ids = []

            # Process devices
            for device in topology_data.get("devices", []):
                doc = safe_json_dumps(device)
                device_id = device.get("id", f"device_{len(documents)}")
                documents.append(
                    f"Network switch {device_id}. "
                    f"Name: {device.get('name', 'unknown')}. "
                    f"Type: {device.get('type', 'switch')}. "
                    f"Available: {device.get('available', True)}."
                )
                metadatas.append({
                    "type": "device",
                    "entity_id": device_id,
                    "raw_data": doc
                })
                ids.append(f"device_{device_id}")

            # Process hosts
            for host in topology_data.get("hosts", []):
                doc = safe_json_dumps(host)
                host_id = host.get("id", f"host_{len(documents)}")
                ips = ", ".join(host.get("ipAddresses", host.get("ips", [])))
                mac = host.get("mac", "unknown")
                location = host.get("location_device", host.get("device", ""))
                port = host.get("location_port", host.get("port", 0))

                documents.append(
                    f"Network host {host.get('name', host_id)}. "
                    f"MAC address: {mac}. IP addresses: {ips}. "
                    f"Connected to switch {location} on port {port}."
                )
                metadatas.append({
                    "type": "host",
                    "entity_id": host_id,
                    "mac": mac,
                    "ips": ips,
                    "raw_data": doc
                })
                ids.append(f"host_{mac}")

            # Process links
            for i, link in enumerate(topology_data.get("links", [])):
                doc = safe_json_dumps(link)
                src = link.get("src_device", link.get("src", ""))
                dst = link.get("dst_device", link.get("dst", ""))

                documents.append(
                    f"Network link between {src} and {dst}. "
                    f"State: {link.get('state', 'ACTIVE')}. "
                    f"Bandwidth: {link.get('bandwidth', 10)} Mbps."
                )
                metadatas.append({
                    "type": "link",
                    "src": src,
                    "dst": dst,
                    "raw_data": doc
                })
                ids.append(f"link_{src}_{dst}")

            if not documents:
                logger.warning("No topology data to seed")
                return False

            if self._is_available():
                # Clear existing topology
                collection = self._collections["topology"]
                existing = collection.get()
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])

                # Add new data
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Seeded topology with {len(documents)} documents")
            else:
                # Fallback store
                self._fallback_store["topology"] = [
                    {"id": ids[i], "document": documents[i], "metadata": metadatas[i]}
                    for i in range(len(documents))
                ]
                logger.info(
                    f"Seeded fallback topology store with {len(documents)} items"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to seed topology: {e}")
            return False

    def query_topology(
        self,
        user_intent: str,
        n_results: int = 5
    ) -> str:
        """
        Query topology for relevant context.

        Args:
            user_intent: Natural language intent
            n_results: Number of results to return

        Returns:
            Concatenated relevant topology information
        """
        try:
            if self._is_available():
                collection = self._collections["topology"]
                results = collection.query(
                    query_texts=[user_intent],
                    n_results=n_results
                )

                if results and results["documents"]:
                    return "\n".join(results["documents"][0])
            else:
                # Simple keyword matching for fallback
                matches = []
                intent_lower = user_intent.lower()
                for item in self._fallback_store["topology"]:
                    doc = item["document"].lower()
                    # Check for keyword matches
                    keywords = ["h1", "h2", "h3", "h4", "h5", "h6",
                               "s1", "s2", "s3", "10.0.0", "block",
                               "allow", "switch", "host"]
                    for keyword in keywords:
                        if keyword in intent_lower and keyword in doc:
                            matches.append(item["document"])
                            break

                if matches:
                    return "\n".join(matches[:n_results])

            return "No relevant topology information found."

        except Exception as e:
            logger.error(f"Failed to query topology: {e}")
            return "Error querying topology."

    # ==========================================
    # Intents Collection
    # ==========================================

    def index_intent(
        self,
        intent: str,
        rule: Dict[str, Any],
        result: Dict[str, Any]
    ) -> bool:
        """
        Index a successfully deployed intent.

        Args:
            intent: Original natural language intent
            rule: Parsed rule JSON
            result: Deployment result

        Returns:
            True if indexing succeeded
        """
        try:
            timestamp = datetime.now().isoformat()
            doc_id = f"intent_{timestamp}"

            document = (
                f"Intent: {intent}. "
                f"Type: {rule.get('intent_type', 'unknown')}. "
                f"Action: {rule.get('action', 'add')}. "
                f"Source: {rule.get('src_host', 'any')}. "
                f"Destination: {rule.get('dst_host', 'any')}. "
                f"Protocol: {rule.get('protocol', 'all')}."
            )

            metadata = {
                "timestamp": timestamp,
                "intent_type": rule.get("intent_type", "unknown"),
                "success": result.get("success", False),
                "raw_intent": intent,
                "raw_rule": safe_json_dumps(rule),
                "raw_result": safe_json_dumps(result)
            }

            if self._is_available():
                self._collections["intents"].add(
                    documents=[document],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
            else:
                self._fallback_store["intents"].append({
                    "id": doc_id,
                    "document": document,
                    "metadata": metadata
                })

            logger.debug(f"Indexed intent: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index intent: {e}")
            return False

    def get_similar_intents(
        self,
        intent: str,
        n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get similar past intents.

        Args:
            intent: Intent to match
            n: Number of results

        Returns:
            List of similar intent records
        """
        try:
            if self._is_available():
                collection = self._collections["intents"]
                results = collection.query(
                    query_texts=[intent],
                    n_results=n
                )

                if results and results["metadatas"]:
                    return [
                        {
                            "intent": m.get("raw_intent", ""),
                            "type": m.get("intent_type", ""),
                            "timestamp": m.get("timestamp", ""),
                            "success": m.get("success", False)
                        }
                        for m in results["metadatas"][0]
                    ]
            else:
                # Return recent from fallback
                recent = sorted(
                    self._fallback_store["intents"],
                    key=lambda x: x["metadata"].get("timestamp", ""),
                    reverse=True
                )[:n]

                return [
                    {
                        "intent": item["metadata"].get("raw_intent", ""),
                        "type": item["metadata"].get("intent_type", ""),
                        "timestamp": item["metadata"].get("timestamp", ""),
                        "success": item["metadata"].get("success", False)
                    }
                    for item in recent
                ]

            return []

        except Exception as e:
            logger.error(f"Failed to get similar intents: {e}")
            return []

    # ==========================================
    # Remediations Collection
    # ==========================================

    def index_remediation(
        self,
        anomaly: Dict[str, Any],
        action: Dict[str, Any],
        result: Dict[str, Any]
    ) -> bool:
        """
        Index a remediation action.

        Args:
            anomaly: Anomaly details
            action: Remediation action taken
            result: Outcome of the action

        Returns:
            True if indexing succeeded
        """
        try:
            timestamp = datetime.now().isoformat()
            doc_id = f"remediation_{timestamp}"

            document = (
                f"Anomaly on device {anomaly.get('device_id', 'unknown')}. "
                f"Type: {anomaly.get('type', 'unknown')}. "
                f"Score: {anomaly.get('score', 0)}. "
                f"Action taken: {action.get('action_type', 'unknown')}. "
                f"Result: {'Success' if result.get('success') else 'Failed'}."
            )

            metadata = {
                "timestamp": timestamp,
                "device_id": anomaly.get("device_id", ""),
                "anomaly_type": anomaly.get("type", ""),
                "action_type": action.get("action_type", ""),
                "success": result.get("success", False),
                "raw_anomaly": safe_json_dumps(anomaly),
                "raw_action": safe_json_dumps(action),
                "raw_result": safe_json_dumps(result)
            }

            if self._is_available():
                self._collections["remediations"].add(
                    documents=[document],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
            else:
                self._fallback_store["remediations"].append({
                    "id": doc_id,
                    "document": document,
                    "metadata": metadata
                })

            logger.debug(f"Indexed remediation: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index remediation: {e}")
            return False

    def get_similar_remediations(
        self,
        anomaly: Dict[str, Any],
        n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get similar past remediations.

        Args:
            anomaly: Current anomaly details
            n: Number of results

        Returns:
            List of similar remediation records
        """
        try:
            query = (
                f"Anomaly type {anomaly.get('type', '')} "
                f"on device {anomaly.get('device_id', '')}"
            )

            if self._is_available():
                collection = self._collections["remediations"]
                results = collection.query(
                    query_texts=[query],
                    n_results=n
                )

                if results and results["metadatas"]:
                    return [
                        {
                            "device_id": m.get("device_id", ""),
                            "anomaly_type": m.get("anomaly_type", ""),
                            "action_type": m.get("action_type", ""),
                            "success": m.get("success", False),
                            "timestamp": m.get("timestamp", "")
                        }
                        for m in results["metadatas"][0]
                    ]
            else:
                # Filter by anomaly type in fallback
                matching = [
                    item for item in self._fallback_store["remediations"]
                    if item["metadata"].get("anomaly_type") == anomaly.get("type")
                ][:n]

                return [
                    {
                        "device_id": item["metadata"].get("device_id", ""),
                        "anomaly_type": item["metadata"].get("anomaly_type", ""),
                        "action_type": item["metadata"].get("action_type", ""),
                        "success": item["metadata"].get("success", False),
                        "timestamp": item["metadata"].get("timestamp", "")
                    }
                    for item in matching
                ]

            return []

        except Exception as e:
            logger.error(f"Failed to get similar remediations: {e}")
            return []

    # ==========================================
    # Collection Management
    # ==========================================

    def clear_collection(self, name: str) -> bool:
        """
        Clear all documents from a collection.

        Args:
            name: Collection name (topology, intents, remediations)

        Returns:
            True if cleared successfully
        """
        try:
            if self._is_available() and name in self._collections:
                collection = self._collections[name]
                existing = collection.get()
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
                logger.info(f"Cleared collection: {name}")
                return True
            elif name in self._fallback_store:
                self._fallback_store[name] = []
                logger.info(f"Cleared fallback store: {name}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to clear collection {name}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about all collections.

        Returns:
            Dictionary with collection sizes and status
        """
        stats = {
            "chromadb_available": self._is_available(),
            "using_fallback": self._use_fallback,
            "collections": {}
        }

        try:
            if self._is_available():
                for name, collection in self._collections.items():
                    count = collection.count()
                    stats["collections"][name] = {
                        "count": count,
                        "type": "chromadb"
                    }
            else:
                for name, store in self._fallback_store.items():
                    stats["collections"][name] = {
                        "count": len(store),
                        "type": "fallback"
                    }

        except Exception as e:
            logger.error(f"Failed to get RAG stats: {e}")
            stats["error"] = str(e)

        return stats

    def health_check(self) -> bool:
        """Check if RAG engine is healthy."""
        try:
            if self._is_available():
                self._client.heartbeat()
                return True
            return True  # Fallback is always "healthy"
        except Exception:
            return False


# Singleton instance
_rag_instance: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get or create the global RAG engine instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGEngine()
    return _rag_instance


if __name__ == "__main__":
    # Test RAG engine
    print("\n=== RAG Engine Test ===\n")

    engine = RAGEngine()

    # Check stats
    stats = engine.get_stats()
    print(f"ChromaDB available: {stats['chromadb_available']}")
    print(f"Using fallback: {stats['using_fallback']}")

    # Test topology seeding
    test_topology = {
        "devices": [
            {"id": "of:0000000000000001", "name": "s1", "type": "switch"},
            {"id": "of:0000000000000002", "name": "s2", "type": "switch"}
        ],
        "hosts": [
            {"id": "h1", "name": "h1", "mac": "00:00:00:00:00:01",
             "ips": ["10.0.0.1"], "device": "of:0000000000000001", "port": 1},
            {"id": "h2", "name": "h2", "mac": "00:00:00:00:00:02",
             "ips": ["10.0.0.2"], "device": "of:0000000000000001", "port": 2}
        ],
        "links": [
            {"src": "of:0000000000000001", "dst": "of:0000000000000002",
             "state": "ACTIVE", "bandwidth": 10}
        ]
    }

    print("\nSeeding topology...")
    engine.seed_topology(test_topology)

    # Query topology
    print("\nQuerying for 'block h1':")
    result = engine.query_topology("block traffic from h1")
    print(result)

    # Test intent indexing
    print("\nIndexing test intent...")
    engine.index_intent(
        intent="Block all traffic from 10.0.0.1",
        rule={"intent_type": "block", "src_host": "10.0.0.1"},
        result={"success": True}
    )

    # Get similar intents
    print("\nGetting similar intents:")
    similar = engine.get_similar_intents("block traffic from host")
    for s in similar:
        print(f"  - {s}")

    # Final stats
    print("\nFinal stats:")
    final_stats = engine.get_stats()
    for name, info in final_stats["collections"].items():
        print(f"  {name}: {info['count']} documents ({info['type']})")

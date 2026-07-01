"""
ONOS REST API Client for LLM-NetAuto-SDN.

Provides a comprehensive interface to ONOS SDN controller REST API.
All methods handle exceptions gracefully and never raise to caller.
"""

import os
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import requests
from requests.auth import HTTPBasicAuth
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ONOSConfig:
    """ONOS connection configuration."""
    host: str = os.getenv("ONOS_HOST", "127.0.0.1")
    port: int = int(os.getenv("ONOS_PORT", "8181"))
    user: str = os.getenv("ONOS_USER", "onos")
    password: str = os.getenv("ONOS_PASSWORD", "rocks")
    app_id: str = os.getenv("ONOS_APP_ID", "org.onosproject.cli")
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/onos/v1"


class ONOSClient:
    """
    ONOS REST API Client.

    Provides methods for topology, intents, flows, statistics,
    and application management. All methods return empty dict/list
    on failure instead of raising exceptions.
    """

    def __init__(self, config: Optional[ONOSConfig] = None):
        """Initialize ONOS client with configuration."""
        self.config = config or ONOSConfig()
        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(
            self.config.user,
            self.config.password
        )
        self._session.headers.update({
            "Accept": "application/json"
        })
        logger.info(
            f"ONOS client initialized: {self.config.base_url}"
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Make HTTP request to ONOS with retry logic.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Request body for POST
            params: Query parameters

        Returns:
            Response JSON or None on failure
        """
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.config.max_retries):
            try:
                # Add Content-Type only for POST requests
                headers = {}
                if method == "POST":
                    headers["Content-Type"] = "application/json"

                response = self._session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout
                )

                if response.status_code == 204:
                    return {"success": True}

                if response.status_code >= 400:
                    logger.warning(
                        f"ONOS API error: {response.status_code} - "
                        f"{response.text[:200]}"
                    )
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                        continue
                    return None

                # Extract Flow ID and Device ID from Location header if present in 201/202 responses
                location = response.headers.get("Location")
                if location and response.status_code in [201, 202]:
                    parts = location.rstrip("/").split("/")
                    if len(parts) >= 2:
                        flow_id = parts[-1]
                        device_id = parts[-2]
                        if device_id.startswith("of:") or ":" in device_id:
                            return {
                                "success": True,
                                "id": flow_id,
                                "flowId": flow_id,
                                "deviceId": device_id,
                                "device": device_id
                            }
                        else:
                            return {
                                "success": True,
                                "id": flow_id,
                                "flowId": flow_id
                            }

                if response.text:
                    return response.json()
                return {"success": True}

            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"ONOS connection error (attempt {attempt + 1}): {e}"
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
            except requests.exceptions.Timeout:
                logger.warning(
                    f"ONOS request timeout (attempt {attempt + 1})"
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
            except requests.exceptions.RequestException as e:
                logger.error(f"ONOS request failed: {e}")
                return None
            except ValueError as e:
                logger.error(f"ONOS JSON decode error: {e}")
                return None

        return None

    # ==========================================
    # Health Check
    # ==========================================

    def health_check(self) -> bool:
        """
        Check if ONOS controller is reachable.

        Returns:
            True if ONOS is healthy, False otherwise
        """
        try:
            response = self._request("GET", "/cluster")
            return response is not None
        except Exception as e:
            logger.warning(f"ONOS health check failed: {e}")
            return False

    # ==========================================
    # Topology Methods
    # ==========================================

    def get_topology(self) -> Dict[str, Any]:
        """
        Get complete network topology.

        Returns:
            Topology dict with devices, links, clusters
        """
        result = self._request("GET", "/topology")
        if result is None:
            logger.warning("Failed to get topology from ONOS")
            return {}
        return result

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Get all network devices (switches).

        Returns:
            List of device dictionaries
        """
        result = self._request("GET", "/devices")
        if result is None:
            logger.warning("Failed to get devices from ONOS")
            return []
        return result.get("devices", [])

    def get_device(self, device_id: str) -> Dict[str, Any]:
        """
        Get specific device by ID.

        Args:
            device_id: Device identifier (e.g., of:0000000000000001)

        Returns:
            Device dictionary or empty dict
        """
        result = self._request("GET", f"/devices/{device_id}")
        if result is None:
            return {}
        return result

    def get_hosts(self) -> List[Dict[str, Any]]:
        """
        Get all hosts in the network.

        Returns:
            List of host dictionaries with MAC, IP, location
        """
        result = self._request("GET", "/hosts")
        if result is None:
            logger.warning("Failed to get hosts from ONOS")
            return []
        return result.get("hosts", [])

    def get_host(self, host_id: str) -> Dict[str, Any]:
        """
        Get specific host by MAC/VLAN ID.

        Args:
            host_id: Host identifier (MAC/VLAN format)

        Returns:
            Host dictionary or empty dict
        """
        result = self._request("GET", f"/hosts/{host_id}")
        if result is None:
            return {}
        return result

    def get_links(self) -> List[Dict[str, Any]]:
        """
        Get all network links.

        Returns:
            List of link dictionaries with src/dst
        """
        result = self._request("GET", "/links")
        if result is None:
            logger.warning("Failed to get links from ONOS")
            return []
        return result.get("links", [])

    def get_ports(self, device_id: str) -> List[Dict[str, Any]]:
        """
        Get ports for a specific device.

        Args:
            device_id: Device identifier

        Returns:
            List of port dictionaries
        """
        result = self._request("GET", f"/devices/{device_id}/ports")
        if result is None:
            return []
        return result.get("ports", [])

    # ==========================================
    # Intent Methods
    # ==========================================

    def post_intent(self, intent_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit an intent to ONOS.

        Args:
            intent_json: Intent specification in ONOS format

        Returns:
            Response with intent key or error
        """
        result = self._request("POST", "/intents", data=intent_json)
        if result is None:
            logger.error("Failed to post intent to ONOS")
            return {"error": "Failed to submit intent"}
        logger.info(f"Intent submitted successfully: {result}")
        return result

    def get_intents(self) -> List[Dict[str, Any]]:
        """
        Get all intents.

        Returns:
            List of intent dictionaries
        """
        result = self._request("GET", "/intents")
        if result is None:
            logger.warning("Failed to get intents from ONOS")
            return []
        return result.get("intents", [])

    def get_intent(self, app_id: str, key: str) -> Dict[str, Any]:
        """
        Get specific intent by app ID and key.

        Args:
            app_id: Application ID that created the intent
            key: Intent key

        Returns:
            Intent dictionary or empty dict
        """
        result = self._request("GET", f"/intents/{app_id}/{key}")
        if result is None:
            return {}
        return result

    def delete_intent(self, app_id: str, key: str) -> bool:
        """
        Delete an intent.

        Args:
            app_id: Application ID that created the intent
            key: Intent key

        Returns:
            True if deleted successfully
        """
        result = self._request("DELETE", f"/intents/{app_id}/{key}")
        if result is None:
            logger.error(f"Failed to delete intent {app_id}/{key}")
            return False
        logger.info(f"Intent deleted: {app_id}/{key}")
        return True

    # ==========================================
    # Flow Methods
    # ==========================================

    def post_flow(
        self,
        device_id: str,
        flow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Install a flow rule on a device.

        Args:
            device_id: Target device ID
            flow_json: Flow rule specification

        Returns:
            Response with flow ID or error
        """
        # Do NOT wrap in flows array when posting to /flows/{device_id}!
        # ONOS /flows/{device_id} endpoint expects a single flow rule directly.
        result = self._request(
            "POST",
            f"/flows/{device_id}",
            data=flow_json
        )
        if result is None:
            logger.error(f"Failed to post flow to device {device_id}")
            return {"error": "Failed to install flow"}
        logger.info(f"Flow installed on {device_id}")
        return result

    def get_flows(
        self,
        device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get flow rules, optionally filtered by device.

        Args:
            device_id: Optional device ID filter

        Returns:
            List of flow rule dictionaries
        """
        endpoint = f"/flows/{device_id}" if device_id else "/flows"
        result = self._request("GET", endpoint)
        if result is None:
            logger.warning("Failed to get flows from ONOS")
            return []
        return result.get("flows", [])

    def get_flow(self, device_id: str, flow_id: str) -> Dict[str, Any]:
        """
        Get specific flow by device and flow ID.

        Args:
            device_id: Device identifier
            flow_id: Flow rule identifier

        Returns:
            Flow dictionary or empty dict
        """
        result = self._request("GET", f"/flows/{device_id}/{flow_id}")
        if result is None:
            return {}
        return result

    def delete_flow(self, device_id: str, flow_id: str) -> bool:
        """
        Delete a flow rule.

        Args:
            device_id: Device identifier
            flow_id: Flow rule identifier

        Returns:
            True if deleted successfully
        """
        result = self._request("DELETE", f"/flows/{device_id}/{flow_id}")
        if result is None:
            logger.error(f"Failed to delete flow {flow_id} from {device_id}")
            return False
        logger.info(f"Flow deleted: {device_id}/{flow_id}")
        return True

    def delete_flows_by_app(self, app_id: str) -> bool:
        """
        Delete all flows created by an application.

        Args:
            app_id: Application identifier

        Returns:
            True if deleted successfully
        """
        result = self._request("DELETE", f"/flows/application/{app_id}")
        if result is None:
            return False
        logger.info(f"Flows deleted for app: {app_id}")
        return True

    # ==========================================
    # Statistics Methods
    # ==========================================

    def get_port_stats(
        self,
        device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get port statistics.

        Args:
            device_id: Optional device ID filter

        Returns:
            List of port statistics dictionaries
        """
        endpoint = (
            f"/statistics/ports/{device_id}"
            if device_id
            else "/statistics/ports"
        )
        result = self._request("GET", endpoint)
        if result is None:
            logger.warning("Failed to get port statistics from ONOS")
            return []
        return result.get("statistics", [])

    def get_flow_stats(
        self,
        device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get flow statistics.

        Args:
            device_id: Optional device ID filter

        Returns:
            List of flow statistics dictionaries
        """
        endpoint = (
            f"/statistics/flows/{device_id}"
            if device_id
            else "/statistics/flows"
        )
        result = self._request("GET", endpoint)
        if result is None:
            logger.warning("Failed to get flow statistics from ONOS")
            return []
        return result.get("statistics", [])

    def get_device_stats(self) -> List[Dict[str, Any]]:
        """
        Get device-level statistics.

        Returns:
            List of device statistics
        """
        devices = self.get_devices()
        stats = []
        for device in devices:
            device_id = device.get("id", "")
            port_stats = self.get_port_stats(device_id)
            stats.append({
                "device_id": device_id,
                "port_stats": port_stats
            })
        return stats

    def get_table_stats(self, device_id: str) -> List[Dict[str, Any]]:
        """
        Get flow table statistics for a device.

        Args:
            device_id: Device identifier

        Returns:
            List of table statistics
        """
        result = self._request(
            "GET",
            f"/statistics/flows/tables/{device_id}"
        )
        if result is None:
            return []
        return result.get("statistics", [])

    # ==========================================
    # Application Methods
    # ==========================================

    def get_apps(self) -> List[Dict[str, Any]]:
        """
        Get all installed applications.

        Returns:
            List of application dictionaries
        """
        result = self._request("GET", "/applications")
        if result is None:
            logger.warning("Failed to get applications from ONOS")
            return []
        return result.get("applications", [])

    def get_app(self, app_id: str) -> Dict[str, Any]:
        """
        Get specific application by ID.

        Args:
            app_id: Application identifier

        Returns:
            Application dictionary or empty dict
        """
        result = self._request("GET", f"/applications/{app_id}")
        if result is None:
            return {}
        return result

    def activate_app(self, app_id: str) -> bool:
        """
        Activate an application.

        Args:
            app_id: Application identifier

        Returns:
            True if activated successfully
        """
        result = self._request("POST", f"/applications/{app_id}/active")
        if result is None:
            logger.error(f"Failed to activate app: {app_id}")
            return False
        logger.info(f"Application activated: {app_id}")
        return True

    def deactivate_app(self, app_id: str) -> bool:
        """
        Deactivate an application.

        Args:
            app_id: Application identifier

        Returns:
            True if deactivated successfully
        """
        result = self._request("DELETE", f"/applications/{app_id}/active")
        if result is None:
            logger.error(f"Failed to deactivate app: {app_id}")
            return False
        logger.info(f"Application deactivated: {app_id}")
        return True

    # ==========================================
    # Cluster Methods
    # ==========================================

    def get_cluster(self) -> Dict[str, Any]:
        """
        Get cluster information.

        Returns:
            Cluster information dictionary
        """
        result = self._request("GET", "/cluster")
        if result is None:
            return {}
        return result

    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """
        Get cluster node information.

        Returns:
            List of cluster node dictionaries
        """
        result = self._request("GET", "/cluster/nodes")
        if result is None:
            return []
        return result.get("nodes", [])

    # ==========================================
    # Utility Methods
    # ==========================================

    def get_topology_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the network topology.

        Returns:
            Summary with counts and status
        """
        devices = self.get_devices()
        hosts = self.get_hosts()
        links = self.get_links()
        intents = self.get_intents()
        flows = self.get_flows()

        return {
            "device_count": len(devices),
            "host_count": len(hosts),
            "link_count": len(links),
            "intent_count": len(intents),
            "flow_count": len(flows),
            "devices": devices,
            "hosts": hosts,
            "links": links,
            "controller_healthy": self.health_check()
        }

    def close(self):
        """Close the HTTP session."""
        self._session.close()
        logger.info("ONOS client session closed")


# Singleton instance for global access
_client_instance: Optional[ONOSClient] = None


def get_onos_client() -> ONOSClient:
    """Get or create the global ONOS client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ONOSClient()
    return _client_instance


if __name__ == "__main__":
    # Test ONOS client
    client = ONOSClient()

    print("\n=== ONOS Client Test ===\n")

    if client.health_check():
        print("ONOS Controller: CONNECTED")

        print("\nDevices:")
        for device in client.get_devices():
            print(f"  - {device.get('id')}: {device.get('type')}")

        print("\nHosts:")
        for host in client.get_hosts():
            print(f"  - {host.get('mac')}: {host.get('ipAddresses')}")

        print("\nLinks:")
        for link in client.get_links():
            src = link.get("src", {})
            dst = link.get("dst", {})
            print(f"  - {src.get('device')}:{src.get('port')} -> "
                  f"{dst.get('device')}:{dst.get('port')}")
    else:
        print("ONOS Controller: NOT REACHABLE")
        print("Make sure ONOS is running on "
              f"{client.config.host}:{client.config.port}")

    client.close()

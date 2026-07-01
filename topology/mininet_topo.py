#!/usr/bin/env python3
"""
Mininet Topology for LLM-NetAuto-SDN.

Fully dynamic topology: number of switches and hosts per switch are
configurable via CLI arguments or environment variables.

Run with sudo:
    sudo python3 topology/mininet_topo.py
    sudo python3 topology/mininet_topo.py --n-switches 4 --hosts-per-switch 3

Topology pattern (ring):
    Each switch connects to the next; last wraps back to first.
    Each switch has ``hosts_per_switch`` hosts on its first N ports.

    N=3, hps=2:
        h1  h2       h3  h4       h5  h6
         \\  /          \\  /          \\  /
          s1 --------- s2 --------- s3
            \\___________________________/
"""

import os
import sys
import time
import argparse
from typing import TYPE_CHECKING, List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from mininet.net import Mininet
    from mininet.node import RemoteController, OVSSwitch
    from mininet.link import TCLink
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info, error
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False
    # Provide stubs so the module can be imported without Mininet
    Mininet = None          # type: ignore[assignment,misc]
    RemoteController = None # type: ignore[assignment]
    OVSSwitch = None        # type: ignore[assignment]
    TCLink = None           # type: ignore[assignment]
    CLI = None              # type: ignore[assignment]
    def setLogLevel(*a, **kw): pass  # type: ignore[misc]
    def info(*a, **kw): pass         # type: ignore[misc]
    def error(*a, **kw): pass        # type: ignore[misc]
    print("WARNING: Mininet not installed. Install with: sudo apt install mininet")



def _dpid_for(switch_index: int) -> str:
    """Return a zero-padded DPID string for switch index (1-based)."""
    return f"{switch_index:016d}"


class LLMNetAutoTopology:
    """
    Dynamic SDN topology for LLM-NetAuto-SDN.

    Parameters
    ----------
    n_switches : int
        Number of OVS switches to create (2–8).
    hosts_per_switch : int
        Number of hosts to attach to each switch (1–4).
    controller_ip : str
        IP of the ONOS/OpenFlow controller.
    controller_port : int
        TCP port of the controller (OpenFlow).
    """

    def __init__(
        self,
        n_switches: int = None,
        hosts_per_switch: int = None,
        controller_ip: str = "127.0.0.1",
        controller_port: int = 6653,
    ):
        # Read from env if not provided explicitly
        self.n_switches = int(
            n_switches if n_switches is not None
            else os.getenv("TOPO_SWITCHES", "3")
        )
        self.hosts_per_switch = int(
            hosts_per_switch if hosts_per_switch is not None
            else os.getenv("TOPO_HOSTS_PER_SWITCH", "2")
        )
        # Clamp to safe ranges
        self.n_switches = max(2, min(8, self.n_switches))
        self.hosts_per_switch = max(1, min(4, self.hosts_per_switch))

        self.controller_ip = controller_ip
        self.controller_port = controller_port
        self.net: Optional[Mininet] = None

        # Will be populated after create_topology()
        self.switches: List = []
        self.hosts: List = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_topology(self) -> Optional[object]:
        """Create and return the Mininet network (does NOT start it)."""
        info(
            f"*** Creating dynamic topology: "
            f"{self.n_switches} switches × {self.hosts_per_switch} hosts/switch "
            f"= {self.n_switches * self.hosts_per_switch} total hosts ***\n"
        )

        self.net = Mininet(
            controller=RemoteController,
            switch=OVSSwitch,
            link=TCLink,
        )

        # Controller
        info(f"*** Adding controller at {self.controller_ip}:{self.controller_port}\n")
        self.net.addController(
            "c0",
            controller=RemoteController,
            ip=self.controller_ip,
            port=self.controller_port,
        )

        # Switches
        info(f"*** Adding {self.n_switches} switches\n")
        self.switches = []
        for i in range(1, self.n_switches + 1):
            sw = self.net.addSwitch(
                f"s{i}",
                cls=OVSSwitch,
                protocols="OpenFlow13",
                dpid=_dpid_for(i),
            )
            self.switches.append(sw)

        # Hosts (sequential IPs across all switches)
        info(
            f"*** Adding {self.n_switches * self.hosts_per_switch} hosts "
            f"({self.hosts_per_switch} per switch)\n"
        )
        self.hosts = []
        host_index = 1  # global host counter → determines IP & MAC
        for sw_i, sw in enumerate(self.switches):
            for h_j in range(1, self.hosts_per_switch + 1):
                ip = f"10.0.0.{host_index}/24"
                mac = f"00:00:00:00:00:{host_index:02x}"
                h = self.net.addHost(
                    f"h{host_index}",
                    ip=ip,
                    mac=mac,
                )
                self.hosts.append(h)
                # Connect host to switch; hosts take ports 1..hosts_per_switch
                self.net.addLink(h, sw, port1=0, port2=h_j)
                host_index += 1

        # Switch–switch links in a ring
        info(f"*** Adding ring links between {self.n_switches} switches\n")
        # Inter-switch ports start right after host ports
        isw_base_port = self.hosts_per_switch + 1
        for i in range(self.n_switches):
            src = self.switches[i]
            dst = self.switches[(i + 1) % self.n_switches]
            # Each switch uses two inter-switch port slots:
            #   slot (i+1): outgoing to next switch
            #   slot (i+2): incoming from previous switch  (other side uses matching slot)
            port_src = isw_base_port + i
            port_dst = isw_base_port + ((i + self.n_switches - 1) % self.n_switches)
            self.net.addLink(src, dst, port1=port_src, port2=port_dst, bw=10, delay="5ms")

        return self.net

    def start(self) -> None:
        """Create (if needed) and start the network."""
        if not self.net:
            self.create_topology()

        info("*** Starting network\n")
        self.net.start()

        info("*** Enforcing OpenFlow 1.3 on all switches\n")
        for sw in self.net.switches:
            sw.cmd(f"ovs-vsctl set bridge {sw.name} protocols=OpenFlow13")

        info("*** Waiting for controller connection (5s)…\n")
        time.sleep(5)

        self._print_topology_info()

        info("\n*** Testing connectivity\n")
        self.net.pingAll()

    def stop(self) -> None:
        """Stop the network."""
        if self.net:
            info("\n*** Stopping network\n")
            self.net.stop()

    def cli(self) -> None:
        """Drop into Mininet CLI."""
        if self.net:
            info("\n*** Starting CLI (type 'exit' to quit)\n")
            CLI(self.net)

    # ------------------------------------------------------------------
    # Traffic & anomaly helpers
    # ------------------------------------------------------------------

    def start_traffic_generation(self) -> None:
        """Start background iperf traffic between random host pairs."""
        info("\n*** Starting background traffic generation\n")
        total_hosts = len(self.hosts)
        if total_hosts < 2:
            info("  Not enough hosts for traffic generation\n")
            return

        # Start iperf servers on all but the first host
        for h in self.hosts[1:]:
            h.cmd("iperf -s -u &")
            h.cmd("iperf -s &")

        time.sleep(1)

        # Generate traffic from first host → second
        pairs = [
            (self.hosts[i], self.hosts[(i + 1) % total_hosts])
            for i in range(0, total_hosts, 2)
            if i + 1 < total_hosts
        ]

        for src, dst in pairs:
            info(f"  {src.name} → {dst.name}: TCP 2 Mbps\n")
            src.cmd(f"iperf -c {dst.IP()} -b 2M -t 3600 &")

    def generate_anomaly_traffic(
        self,
        host_name: str,
        target_ip: str,
        mbps: int,
        duration: int = 60,
    ) -> None:
        """Generate anomaly traffic from a host."""
        host = self.net.get(host_name)
        if host:
            info(
                f"\n*** Anomaly traffic: {host_name} → {target_ip} "
                f"@ {mbps} Mbps for {duration}s\n"
            )
            host.cmd(f"iperf -c {target_ip} -u -b {mbps}M -t {duration} &")

    def trigger_link_failure(
        self,
        switch1: str,
        switch2: str,
        duration: int = 30,
    ) -> None:
        """Bring a link down then back up."""
        info(f"\n*** Link failure: {switch1} ↔ {switch2}\n")
        self.net.configLinkStatus(switch1, switch2, "down")
        time.sleep(duration)
        info(f"*** Restoring link: {switch1} ↔ {switch2}\n")
        self.net.configLinkStatus(switch1, switch2, "up")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _print_topology_info(self) -> None:
        info("\n=== Topology Summary ===\n")
        info(f"  Switches : {self.n_switches}\n")
        info(f"  Hosts    : {self.n_switches * self.hosts_per_switch} "
             f"({self.hosts_per_switch}/switch)\n")
        info("\nSwitches:\n")
        for sw in self.net.switches:
            info(f"  {sw.name}: dpid={sw.dpid}, device_id=of:{sw.dpid}\n")
        info("\nHosts:\n")
        for h in self.net.hosts:
            info(f"  {h.name}: IP={h.IP()}, MAC={h.MAC()}\n")
        info("\nLinks:\n")
        for link in self.net.links:
            info(f"  {link.intf1} ↔ {link.intf2}\n")

    def get_topology_summary(self) -> dict:
        """Return a plain-dict summary (no Mininet objects)."""
        sw_list = []
        for i, sw in enumerate(self.switches, 1):
            sw_list.append({
                "name": f"s{i}",
                "dpid": _dpid_for(i),
                "device_id": f"of:{_dpid_for(i)}",
            })
        host_list = []
        for idx, h in enumerate(self.hosts, 1):
            sw_idx = (idx - 1) // self.hosts_per_switch + 1
            host_list.append({
                "name": f"h{idx}",
                "ip": f"10.0.0.{idx}",
                "mac": f"00:00:00:00:00:{idx:02x}",
                "switch": f"s{sw_idx}",
                "device_id": f"of:{_dpid_for(sw_idx)}",
            })
        return {
            "n_switches": self.n_switches,
            "hosts_per_switch": self.hosts_per_switch,
            "total_hosts": self.n_switches * self.hosts_per_switch,
            "switches": sw_list,
            "hosts": host_list,
        }


# ---------------------------------------------------------------------------
# Module-level helper used by other parts of the codebase
# ---------------------------------------------------------------------------

def get_topology_config() -> dict:
    """Return the current topology config from env."""
    return {
        "n_switches": int(os.getenv("TOPO_SWITCHES", "3")),
        "hosts_per_switch": int(os.getenv("TOPO_HOSTS_PER_SWITCH", "2")),
    }


def build_expected_topology(
    n_switches: int = None,
    hosts_per_switch: int = None,
) -> dict:
    """
    Return a dict describing the expected ONOS device IDs, host IPs, and
    ring links for a topology with the given parameters.  Useful for
    topology_seed and validation without needing Mininet.
    """
    n = int(n_switches or os.getenv("TOPO_SWITCHES", "3"))
    hps = int(hosts_per_switch or os.getenv("TOPO_HOSTS_PER_SWITCH", "2"))
    n = max(2, min(8, n))
    hps = max(1, min(4, hps))

    switches = [
        {
            "name": f"s{i}",
            "device_id": f"of:{_dpid_for(i)}",
        }
        for i in range(1, n + 1)
    ]

    hosts = []
    for sw_i in range(1, n + 1):
        for h_j in range(1, hps + 1):
            idx = (sw_i - 1) * hps + h_j
            hosts.append({
                "name": f"h{idx}",
                "ip": f"10.0.0.{idx}",
                "mac": f"00:00:00:00:00:{idx:02x}",
                "switch": f"s{sw_i}",
                "device_id": f"of:{_dpid_for(sw_i)}",
                "port": h_j,
            })

    links = []
    for i in range(n):
        src = switches[i]["device_id"]
        dst = switches[(i + 1) % n]["device_id"]
        links.append({"src": src, "dst": dst})

    return {
        "n_switches": n,
        "hosts_per_switch": hps,
        "switches": switches,
        "hosts": hosts,
        "links": links,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LLM-NetAuto-SDN Dynamic Mininet Topology"
    )
    parser.add_argument(
        "--n-switches", type=int,
        default=int(os.getenv("TOPO_SWITCHES", "3")),
        help="Number of OVS switches (2–8, default: 3)"
    )
    parser.add_argument(
        "--hosts-per-switch", type=int,
        default=int(os.getenv("TOPO_HOSTS_PER_SWITCH", "2")),
        help="Hosts per switch (1–4, default: 2)"
    )
    parser.add_argument(
        "--controller-ip", default="127.0.0.1",
        help="ONOS controller IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--controller-port", type=int, default=6653,
        help="ONOS OpenFlow port (default: 6653)"
    )
    parser.add_argument(
        "--traffic", action="store_true",
        help="Start background traffic generation after boot"
    )
    parser.add_argument(
        "--no-cli", action="store_true",
        help="Skip interactive CLI (useful for scripting)"
    )

    args = parser.parse_args()

    if not MININET_AVAILABLE:
        print("ERROR: Mininet not available. Install with: sudo apt install mininet openvswitch-switch")
        sys.exit(1)

    setLogLevel("info")

    topo = LLMNetAutoTopology(
        n_switches=args.n_switches,
        hosts_per_switch=args.hosts_per_switch,
        controller_ip=args.controller_ip,
        controller_port=args.controller_port,
    )

    try:
        topo.start()
        if args.traffic:
            topo.start_traffic_generation()
        if args.no_cli:
            # Daemon mode: keep the network alive until killed
            import signal as _signal
            import threading

            def _auto_ping():
                # Wait 12 seconds for switches to fully connect and install basic rules
                time.sleep(12)
                info("\n*** Auto-Ping: Registering all hosts in ONOS controller... ***\n")
                try:
                    topo.net.pingAll()
                    info("*** Auto-Ping complete! All hosts should now be visible. ***\n")
                except Exception as ex:
                    error(f"Auto-Ping failed: {ex}\n")

            ping_thread = threading.Thread(target=_auto_ping, daemon=True)
            ping_thread.start()

            info("\n*** Running in daemon mode — send SIGTERM or SIGINT to stop ***\n")
            _signal.pause()
        else:
            topo.cli()
    except KeyboardInterrupt:
        info("\n*** Interrupted\n")
    finally:
        topo.stop()


if __name__ == "__main__":
    main()

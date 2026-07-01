#!/usr/bin/env python3
"""
Enhanced Production Mininet Topology for LLM-NetAuto-SDN.

Features:
- 5 interconnected switches in a mesh topology
- 15 hosts (3 per switch) for comprehensive testing
- Automatic ARP triggering for ONOS host discovery
- OpenFlow 1.3 support
- High-performance configuration
"""

import os
import sys
import time
import subprocess
import threading
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSSwitch, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink
from mininet.topo import Topo


class LLMNetAutoEnhancedTopo(Topo):
    """
    Enhanced production topology for LLM-NetAuto-SDN.

    5 switches with 3 hosts per switch = 15 hosts total
    Mesh topology between switches for redundancy
    """

    def build(self):
        """Build the network topology."""
        info('*** Creating enhanced production topology\n')

        # Add 5 switches with OpenFlow 1.3
        switches = []
        for i in range(1, 6):
            dpid = f'000000000000000{i}'
            s = self.addSwitch(
                f's{i}',
                dpid=dpid,
                cls=OVSSwitch,
                protocols='OpenFlow13'
            )
            switches.append(s)
            info(f'  Added switch s{i} (DPID: {dpid})\n')

        # Add 15 hosts (3 per switch)
        hosts = []
        host_id = 1
        for switch_idx, switch in enumerate(switches, start=1):
            for h_per_switch in range(3):
                host_name = f'h{host_id}'
                host_ip = f'10.0.{switch_idx}.{h_per_switch + 1}/24'
                host_mac = f'00:00:00:00:{'0' * (2 if switch_idx < 10 else '')}{switch_idx}:{host_id:02x}'

                h = self.addHost(
                    host_name,
                    ip=host_ip,
                    mac=host_mac,
                    cls=Host
                )
                hosts.append((h, switch, host_name))
                info(f'  Added host {host_name} ({host_ip})\n')
                host_id += 1

        # Create mesh connections between switches (high bandwidth)
        info('*** Creating mesh backbone links\n')
        for i in range(len(switches)):
            for j in range(i + 1, len(switches)):
                self.addLink(
                    switches[i],
                    switches[j],
                    bw=1000,
                    delay='5ms',
                    loss=0
                )
                info(f'  Added link: s{i+1} <-> s{j+1}\n')

        # Connect hosts to switches
        info('*** Connecting hosts to switches\n')
        for idx, (host, switch, host_name) in enumerate(hosts):
            self.addLink(
                host,
                switch,
                bw=100,
                delay='1ms',
                loss=0
            )
            switch_idx = idx // 3 + 1
            info(f'  Connected {host_name} to s{switch_idx}\n')

        info('*** Enhanced topology created successfully\n')


def trigger_host_discovery(net):
    """
    Trigger ARP discovery for all hosts.
    This ensures ONOS discovers the hosts via ARP packets.
    """
    info('*** Triggering host discovery via ARP\n')

    try:
        # Get all hosts
        for host in net.hosts:
            # Generate ARP traffic by pinging the gateway (switch)
            info(f'  Pinging from {host.name}...\n')
            host.cmd('arping -c 1 10.0.0.1 > /dev/null 2>&1 &')

        time.sleep(2)

        # Run pingall to ensure all hosts are discovered
        info('*** Running pingall for host discovery\n')
        result = net.pingAll(timeout='2')
        time.sleep(3)

        info('*** Host discovery triggered\n')
    except Exception as e:
        error(f'Error triggering host discovery: {e}\n')


def verify_onos_connectivity(onos_host, onos_port):
    """Verify ONOS is accessible."""
    import requests
    try:
        r = requests.get(
            f"http://{onos_host}:{onos_port}/onos/v1/cluster",
            auth=('onos', 'rocks'),
            timeout=5
        )
        if r.status_code == 200:
            info(f'✓ ONOS is accessible at {onos_host}:{onos_port}\n')
            return True
        else:
            error(f'✗ ONOS returned {r.status_code}\n')
            return False
    except Exception as e:
        error(f'✗ Cannot reach ONOS: {e}\n')
        return False


def configure_mininet_for_production():
    """Configure system for production deployment."""
    info('*** Configuring Mininet for production\n')

    try:
        subprocess.run(['sysctl', '-w', 'net.ipv4.tcp_nodelay=1'],
                      check=False, capture_output=True)
        subprocess.run(['sysctl', '-w', 'net.core.somaxconn=4096'],
                      check=False, capture_output=True)
    except Exception as e:
        error(f'Configuration warning: {e}\n')

    info('✓ Mininet configured for production\n')


def start_production_network():
    """Start the network in interactive mode."""
    setLogLevel('info')

    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_OF_PORT', '6653'))

    info(f'\n*** LLM-NetAuto-SDN Enhanced Production Deployment\n')
    info(f'*** ONOS Controller: {onos_ip}:{onos_port}\n')

    # Verify ONOS
    info('*** Verifying ONOS connectivity...\n')
    if not verify_onos_connectivity(onos_ip, 8181):
        error('✗ ONOS is not responding. Please start ONOS first.\n')
        return False

    # Configure system
    configure_mininet_for_production()

    # Create and start network
    topo = LLMNetAutoEnhancedTopo()
    info('*** Creating Mininet network\n')

    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name,
            ip=onos_ip,
            port=onos_port,
            protocols='OpenFlow13'
        ),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        build=False
    )

    info('*** Starting network\n')
    net.build()
    net.start()

    info('*** Network started. Waiting for ONOS topology discovery...\n')
    time.sleep(10)

    # Trigger host discovery
    trigger_host_discovery(net)

    # Verify topology discovery
    info('*** Verifying topology discovery\n')
    import requests

    for attempt in range(30):
        try:
            r = requests.get(
                f"http://{onos_ip}:8181/onos/v1/devices",
                auth=('onos', 'rocks'),
                timeout=5
            )
            if r.status_code == 200:
                devices = r.json().get('devices', [])
                hosts = r.json().get('hosts', []) if 'hosts' in r.json() else []
                if len(devices) >= 5:
                    info(f'✓ ONOS discovered {len(devices)} devices\n')
                    break
        except:
            pass
        time.sleep(1)

    # Get final topology stats
    try:
        r = requests.get(
            f"http://{onos_ip}:8181/onos/v1/devices",
            auth=('onos', 'rocks'),
            timeout=5
        )
        topo_data = r.json()
        devices = topo_data.get('devices', [])

        # Check hosts
        r_hosts = requests.get(
            f"http://{onos_ip}:8181/onos/v1/hosts",
            auth=('onos', 'rocks'),
            timeout=5
        )
        hosts_data = r_hosts.json()
        hosts_list = hosts_data.get('hosts', [])

        info('\n*** Network Topology Information:\n')
        info(f'Switches discovered: {len(devices)} (expected: 5)\n')
        info(f'Hosts discovered: {len(hosts_list)} (expected: 15)\n')

        for device in devices[:5]:
            info(f'  - {device.get("id")}: {device.get("humanReadableLastUpdate")}\n')

        if hosts_list:
            info(f'\nHosts discovered:\n')
            for host in hosts_list[:10]:
                info(f'  - {host.get("id")}: {host.get("ipAddresses", [])}\n')
    except Exception as e:
        error(f'Error getting topology stats: {e}\n')

    info('\n*** Network is ready!\n')
    info('*** Commands:\n')
    info('  - pingall: Test all-to-all connectivity\n')
    info('  - iperf: Test bandwidth\n')
    info('  - dump: Show network state\n')
    info('  - exit: Stop network\n\n')

    # Start CLI
    CLI(net)

    info('*** Stopping network\n')
    net.stop()
    return True


def start_background():
    """Start network in background (no CLI)."""
    setLogLevel('warning')

    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_OF_PORT', '6653'))

    # Verify ONOS
    if not verify_onos_connectivity(onos_ip, 8181):
        print('✗ ONOS not accessible')
        return False

    configure_mininet_for_production()

    topo = LLMNetAutoEnhancedTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name, ip=onos_ip, port=onos_port, protocols='OpenFlow13'
        ),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        build=False
    )

    print('Starting enhanced network...')
    net.build()
    net.start()

    print('Waiting for ONOS topology discovery...')
    time.sleep(10)

    # Trigger host discovery in background thread
    def discover_hosts():
        time.sleep(2)
        trigger_host_discovery(net)

    discovery_thread = threading.Thread(target=discover_hosts, daemon=True)
    discovery_thread.start()

    # Monitor topology discovery
    print('Monitoring topology discovery...')
    import requests

    for i in range(40):
        try:
            r = requests.get(
                f"http://{onos_ip}:8181/onos/v1/devices",
                auth=('onos', 'rocks'),
                timeout=5
            )
            if r.status_code == 200:
                devices = r.json().get('devices', [])
                r_hosts = requests.get(
                    f"http://{onos_ip}:8181/onos/v1/hosts",
                    auth=('onos', 'rocks'),
                    timeout=5
                )
                hosts_data = r_hosts.json()
                hosts_list = hosts_data.get('hosts', [])

                if len(devices) >= 5 and i > 10:
                    print(f'✓ Network ready with {len(devices)} switches and {len(hosts_list)} hosts')
                    break
        except:
            pass
        time.sleep(1)

    print('')
    print('╔════════════════════════════════════════════════════════════════╗')
    print('║      Enhanced Mininet Network Started Successfully            ║')
    print('╚════════════════════════════════════════════════════════════════╝')
    print(f'Switches: {len(net.switches)}')
    print(f'Hosts: {len(net.hosts)}')
    print(f'Links: {len(net.links)}')
    print('')
    print('Network will stay up. Press Ctrl+C to stop.')
    print('')

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print('\nStopping network...')
        net.stop()
        print('Network stopped.')
        return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'background':
            start_background()
        else:
            print('Usage:')
            print('  python3 enhanced_topology.py           # Interactive mode')
            print('  python3 enhanced_topology.py background # Background mode')
    else:
        start_production_network()

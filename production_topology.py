#!/usr/bin/env python3
"""
Production Mininet Topology for LLM-NetAuto-SDN.

Optimized for real deployment with proper OpenFlow configuration.
Topology: 3-switch linear topology with 6 hosts for testing intent deployment.
"""

import os
import sys
import time
import subprocess
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink
from mininet.topo import Topo


class ProductionNetAutoTopo(Topo):
    """
    Production topology for LLM-NetAuto-SDN.

    3 switches with 2 hosts per switch for a total of 6 hosts.
    All switches configured with DPID for ONOS compatibility.
    """

    def build(self):
        """Build the network topology."""
        info('*** Creating production topology\n')

        # Add switches with proper OpenFlow configuration
        # DPID format: 0000000000000XXX (last 3 digits as switch number)
        s1 = self.addSwitch(
            's1',
            dpid='0000000000000001',
            cls=OVSSwitch,
            protocols='OpenFlow13'
        )
        s2 = self.addSwitch(
            's2',
            dpid='0000000000000002',
            cls=OVSSwitch,
            protocols='OpenFlow13'
        )
        s3 = self.addSwitch(
            's3',
            dpid='0000000000000003',
            cls=OVSSwitch,
            protocols='OpenFlow13'
        )

        # Add hosts with MAC addresses for consistency
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06')

        # Add backbone links with high bandwidth
        info('*** Adding backbone links\n')
        self.addLink(s1, s2, bw=1000, delay='5ms')
        self.addLink(s2, s3, bw=1000, delay='5ms')

        # Add host links with lower bandwidth
        info('*** Adding host links\n')
        self.addLink(h1, s1, bw=100, delay='1ms')
        self.addLink(h2, s1, bw=100, delay='1ms')
        self.addLink(h3, s2, bw=100, delay='1ms')
        self.addLink(h4, s2, bw=100, delay='1ms')
        self.addLink(h5, s3, bw=100, delay='1ms')
        self.addLink(h6, s3, bw=100, delay='1ms')

        info('*** Topology created successfully\n')


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
    """Configure Mininet settings for production."""
    info('*** Configuring Mininet for production\n')

    # Disable TCP nagle algorithm for better performance
    subprocess.run(['sysctl', '-w', 'net.ipv4.tcp_nodelay=1'], check=False)

    # Increase open file limit
    subprocess.run(['ulimit', '-n', '4096'], check=False)

    info('✓ Mininet configured\n')


def start_production_network():
    """Start the network in production mode."""
    setLogLevel('info')

    # Get ONOS configuration from environment
    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_OF_PORT', '6653'))

    info(f'\n*** LLM-NetAuto-SDN Production Deployment\n')
    info(f'*** ONOS Controller: {onos_ip}:{onos_port}\n')

    # Verify ONOS before starting
    info('*** Verifying ONOS connectivity...\n')
    if not verify_onos_connectivity(onos_ip, 8181):
        error('✗ ONOS is not responding. Please start ONOS first.\n')
        return False

    # Configure system
    configure_mininet_for_production()

    # Create topology
    topo = ProductionNetAutoTopo()

    # Create network with remote ONOS controller
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

    # Start the network
    info('*** Starting network\n')
    net.build()
    net.start()

    info('*** Network started. Waiting for ONOS topology discovery...\n')
    time.sleep(10)

    # Verify topology discovery
    info('*** Verifying topology discovery\n')
    for i in range(30):
        try:
            import requests
            r = requests.get(
                f"http://{onos_ip}:8181/onos/v1/devices",
                auth=('onos', 'rocks'),
                timeout=5
            )
            if r.status_code == 200:
                devices = r.json().get('devices', [])
                if len(devices) >= 3:
                    info(f'✓ ONOS discovered {len(devices)} devices\n')
                    break
        except:
            pass
        time.sleep(1)

    # Test connectivity
    info('*** Testing connectivity\n')
    result = net.pingAll(timeout='2')

    # Display topology information
    info('\n*** Network Topology Information:\n')
    info(f'Switches: {len(net.switches)}\n')
    for switch in net.switches:
        info(f'  - {switch.name}: DPID {switch.dpid}\n')

    info(f'Hosts: {len(net.hosts)}\n')
    for host in net.hosts:
        info(f'  - {host.name}: IP {host.IP()}\n')

    info(f'Links: {len(net.links)}\n')

    # Start CLI for interactive testing
    info('\n*** Mininet is ready!\n')
    info('*** Available commands:\n')
    info('  - pingall: Test all-to-all connectivity\n')
    info('  - iperf: Test bandwidth\n')
    info('  - dump: Show network state\n')
    info('  - py: Execute Python\n')
    info('  - exit: Stop network\n\n')

    # Keep network running
    CLI(net)

    info('*** Stopping network\n')
    net.stop()
    return True


def start_background():
    """Start network in background mode (no CLI)."""
    setLogLevel('warning')

    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_OF_PORT', '6653'))

    # Verify ONOS
    if not verify_onos_connectivity(onos_ip, 8181):
        print('✗ ONOS not accessible')
        return False

    topo = ProductionNetAutoTopo()
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

    print('Starting network...')
    net.build()
    net.start()

    print('Waiting for ONOS topology discovery...')
    time.sleep(15)

    # Verify discovery
    for i in range(30):
        try:
            import requests
            r = requests.get(
                f"http://{onos_ip}:8181/onos/v1/devices",
                auth=('onos', 'rocks'),
                timeout=5
            )
            if r.status_code == 200:
                devices = r.json().get('devices', [])
                if len(devices) >= 3:
                    print(f'✓ Network ready with {len(devices)} devices')
                    break
        except:
            pass
        time.sleep(1)

    print('')
    print('╔════════════════════════════════════════════════════════════════╗')
    print('║         Mininet Network Started Successfully                  ║')
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


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'background':
            start_background()
        else:
            print('Usage:')
            print('  python3 production_topology.py           # Interactive mode (CLI)')
            print('  python3 production_topology.py background # Background mode')
    else:
        start_production_network()

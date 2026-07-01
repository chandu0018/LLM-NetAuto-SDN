#!/usr/bin/env python3
"""
Mininet Topology for LLM-NetAuto-SDN.

Creates a 3-switch linear topology with hosts connected to ONOS controller.
This topology matches the simulated topology used in demo mode.
"""

import os
import sys
import time
from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.topo import Topo


class LLMNetAutoTopo(Topo):
    """
    Custom topology for LLM-NetAuto-SDN.

    Topology:
    h1 --- s1 --- s2 --- s3 --- h6
    |             |             |
    h2            h3            h5
                  |
                  h4
    """

    def build(self):
        """Build the topology."""
        info('*** Creating topology\n')

        # Add switches
        s1 = self.addSwitch('s1', dpid='0000000000000001')
        s2 = self.addSwitch('s2', dpid='0000000000000002')
        s3 = self.addSwitch('s3', dpid='0000000000000003')

        # Add hosts with specific IPs
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06')

        # Add links between switches (backbone)
        self.addLink(s1, s2, bw=1000, delay='5ms')
        self.addLink(s2, s3, bw=1000, delay='5ms')

        # Add host links
        self.addLink(h1, s1, bw=100, delay='1ms')
        self.addLink(h2, s1, bw=100, delay='1ms')
        self.addLink(h3, s2, bw=100, delay='1ms')
        self.addLink(h4, s2, bw=100, delay='1ms')
        self.addLink(h5, s3, bw=100, delay='1ms')
        self.addLink(h6, s3, bw=100, delay='1ms')

        info('*** Topology created\n')


def start_network():
    """Start the Mininet network with ONOS controller."""
    setLogLevel('info')

    # ONOS controller configuration
    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_PORT', '6653'))

    info(f'*** Connecting to ONOS controller at {onos_ip}:{onos_port}\n')

    # Create topology
    topo = LLMNetAutoTopo()

    # Create network with remote ONOS controller
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name, ip=onos_ip, port=onos_port
        ),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True
    )

    info('*** Starting network\n')
    net.start()

    # Wait for topology discovery
    info('*** Waiting for topology discovery...\n')
    time.sleep(10)

    # Test connectivity
    info('*** Testing connectivity\n')
    net.pingAll(timeout='1')

    # Show topology information
    info('*** Network topology:\n')
    for switch in net.switches:
        info(f'Switch {switch.name}: DPID {switch.dpid}\n')

    for host in net.hosts:
        info(f'Host {host.name}: IP {host.IP()} MAC {host.MAC()}\n')

    info('*** Network ready! Starting CLI...\n')
    info('*** Use "pingall" to test connectivity\n')
    info('*** Use "exit" to stop the network\n')

    # Start CLI
    CLI(net)

    info('*** Stopping network\n')
    net.stop()


def start_persistent():
    """Start network and keep it running without CLI."""
    setLogLevel('info')

    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_PORT', '6653'))

    info(f'*** Connecting to ONOS controller at {onos_ip}:{onos_port}\n')

    topo = LLMNetAutoTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name, ip=onos_ip, port=onos_port
        ),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True
    )

    info('*** Starting network\n')
    net.start()

    info('*** Waiting for topology discovery...\n')
    time.sleep(15)

    info('*** Testing connectivity\n')
    result = net.pingAll(timeout='2')

    info('*** Network topology:\n')
    for switch in net.switches:
        info(f'Switch {switch.name}: DPID {switch.dpid}\n')

    for host in net.hosts:
        info(f'Host {host.name}: IP {host.IP()} MAC {host.MAC()}\n')

    info('*** Network ready and persistent!\n')
    info('*** Connectivity test result: %s\n' % ('PASSED' if result == 0 else 'FAILED'))
    info('*** Network will stay up. Press Ctrl+C to stop.\n')

    try:
        # Keep network running
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        info('*** Stopping network\n')
        net.stop()


def quick_test():
    """Quick test without CLI for automated testing."""
    setLogLevel('warning')

    onos_ip = os.getenv('ONOS_HOST', '127.0.0.1')
    onos_port = int(os.getenv('ONOS_PORT', '6653'))

    topo = LLMNetAutoTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name, ip=onos_ip, port=onos_port
        ),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True
    )

    print('Starting network...')
    net.start()

    print('Waiting for topology discovery...')
    time.sleep(15)

    print('Testing connectivity...')
    result = net.pingAll(timeout='2')

    print(f'Network topology:')
    print(f'Switches: {len(net.switches)}')
    print(f'Hosts: {len(net.hosts)}')
    print(f'Links: {len(net.links)}')

    print('Stopping network...')
    net.stop()

    return result


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            # Quick test mode
            result = quick_test()
            print(f'Connectivity test: {"PASSED" if result == 0 else "FAILED"}')
        elif sys.argv[1] == 'persistent':
            # Persistent mode (for background)
            start_persistent()
        else:
            print("Usage:")
            print("  python3 mininet_topology.py          # Interactive mode with CLI")
            print("  python3 mininet_topology.py test     # Quick test mode")
            print("  python3 mininet_topology.py persistent # Persistent background mode")
    else:
        # Interactive mode
        start_network()
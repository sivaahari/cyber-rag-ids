"""
generate_sample_pcap.py
-----------------------
Generate a small sample .pcap file with mixed normal and attack traffic
using Scapy. Use this to test the /upload/pcap endpoint.

Run:
    python scripts/generate_sample_pcap.py

Output:
    scripts/sample_traffic.pcap  (~50 packets)
"""

import sys
from pathlib import Path

try:
    from scapy.all import (
        IP, TCP, UDP, ICMP, Raw, Ether,
        wrpcap, RandShort,
    )
except ImportError:
    print("ERROR: Scapy not installed.")
    print("  Install: pip install scapy")
    print("  Windows: also install Npcap from https://npcap.com")
    sys.exit(1)

OUTPUT = Path(__file__).parent / "sample_traffic.pcap"
packets = []


def add_normal_http():
    """Simulate normal HTTP GET request."""
    pkt = (
        Ether() /
        IP(src="192.168.1.100", dst="93.184.216.34") /
        TCP(sport=RandShort(), dport=80, flags="S") /
        Raw(load=b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
    )
    packets.append(pkt)


def add_syn_flood(n=10):
    """Simulate SYN flood from single source to web server."""
    for i in range(n):
        pkt = (
            Ether() /
            IP(src=f"10.0.0.{i % 254 + 1}", dst="192.168.1.10") /
            TCP(sport=RandShort(), dport=80, flags="S")
        )
        packets.append(pkt)


def add_port_scan():
    """Simulate sequential port scan."""
    for port in [21, 22, 23, 25, 53, 80, 110, 443, 3306, 8080]:
        pkt = (
            Ether() /
            IP(src="172.16.0.1", dst="192.168.1.10") /
            TCP(sport=RandShort(), dport=port, flags="S")
        )
        packets.append(pkt)


def add_udp_traffic():
    """Normal DNS queries."""
    for _ in range(5):
        pkt = (
            Ether() /
            IP(src="192.168.1.50", dst="8.8.8.8") /
            UDP(sport=RandShort(), dport=53) /
            Raw(load=b"\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        )
        packets.append(pkt)


def add_icmp_ping():
    """Normal ICMP ping."""
    for i in range(3):
        pkt = (
            Ether() /
            IP(src="192.168.1.1", dst="192.168.1.100") /
            ICMP()
        )
        packets.append(pkt)


def add_brute_force_ssh():
    """SSH brute force — many connections to port 22."""
    for _ in range(8):
        pkt = (
            Ether() /
            IP(src="185.220.101.45", dst="192.168.1.10") /
            TCP(sport=RandShort(), dport=22, flags="S")
        )
        packets.append(pkt)


def main():
    print("Generating sample PCAP...")

    # Normal traffic:
    for _ in range(5): add_normal_http()
    add_udp_traffic()
    add_icmp_ping()

    # Attack traffic:
    add_syn_flood(n=10)
    add_port_scan()
    add_brute_force_ssh()

    # More normal:
    for _ in range(5): add_normal_http()

    print(f"  Total packets: {len(packets)}")
    wrpcap(str(OUTPUT), packets)
    print(f"  Saved: {OUTPUT}")
    print()
    print("Test with:")
    print(f"  Upload in the frontend: http://localhost:3000/upload")
    print(f"  Or via API:")
    print(f'  $f = Get-Item "{OUTPUT}"')
    print(f'  Invoke-RestMethod -Uri http://localhost:8000/upload/pcap -Method POST -Form @{{file=$f}}')


if __name__ == "__main__":
    main()

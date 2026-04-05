# Incident Response Procedures

## Immediate Response (First 15 Minutes)
1. **Identify:** Confirm the alert is not a false positive
2. **Contain:** Isolate affected systems from network
3. **Preserve:** Capture memory dumps, packet captures, logs
4. **Notify:** Alert security team and management per escalation policy

## Evidence Collection
- Packet captures (full PCAP with tcpdump/Wireshark)
- System logs (/var/log/syslog, Windows Event Log)
- Network flow data (NetFlow, IPFIX)
- Firewall and IDS/IPS logs
- Memory forensics (Volatility framework)

## Network Forensics Steps
1. Preserve chain of custody for all evidence
2. Export NetFlow data for anomalous time window
3. Analyze TCP/IP headers for attack signatures
4. Correlate with threat intelligence feeds
5. Identify patient zero and attack vector
6. Map lateral movement paths

## Post-Incident Analysis
- Root cause analysis (RCA) document
- Timeline reconstruction
- Impact assessment (data exfiltration, downtime, affected systems)
- Lessons learned and security improvements
- Update IDS signatures and firewall rules
- Threat hunt for similar indicators across environment

## Reporting Requirements
- Regulatory bodies (GDPR 72hr, HIPAA, PCI-DSS)
- Law enforcement (if criminal activity)
- Customers/stakeholders (per breach notification laws)
- Cyber insurance carrier

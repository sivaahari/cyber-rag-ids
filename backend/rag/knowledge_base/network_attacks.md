# Network Attack Types and Detection

## DDoS (Distributed Denial of Service)
DDoS attacks overwhelm target systems with traffic from multiple sources.
**Indicators:** High packet rate from multiple IPs, SYN flood patterns, UDP flood,
ICMP flood. **Detection:** Flow duration < 1s with high byte count, packet count
spikes > 1000 packets/second from single source.
**Mitigation:** Rate limiting, blackhole routing, CDN scrubbing, BGP flowspec.

## Port Scanning
Systematic probing of network ports to find open services.
**Types:** TCP SYN scan (stealth), TCP connect scan, UDP scan, NULL/FIN/Xmas scans.
**Indicators:** Sequential port access, low TTL values, RST responses, 
single source to many destination ports. Flow packet count typically 1-3.
**Mitigation:** Firewall ACLs, port knocking, intrusion prevention systems.

## Brute Force Attacks
Repeated authentication attempts to guess credentials.
**Indicators:** Multiple failed login attempts, rapid connection attempts to port 22 (SSH),
port 3389 (RDP), port 21 (FTP). High connection rate to single port from single IP.
**Mitigation:** Account lockout, MFA, fail2ban, CAPTCHAs, IP whitelisting.

## SQL Injection
Inserting malicious SQL into application queries.
**Network indicators:** Unusual payload sizes in HTTP POST to web apps,
repeated requests with different parameters. HTTP 500 responses.
**Mitigation:** Parameterized queries, WAF, input validation, stored procedures.

## Man-in-the-Middle (MITM)
Intercepting communications between two parties.
**Types:** ARP spoofing, SSL stripping, DNS spoofing.
**Indicators:** ARP table anomalies, unexpected certificate changes, duplicate MAC/IP pairs.
**Mitigation:** Encryption (TLS 1.3), certificate pinning, DNSSEC, dynamic ARP inspection.

## Botnet C2 Communication
Compromised hosts communicating with command-and-control servers.
**Indicators:** Beaconing traffic (regular time intervals), unusual outbound connections,
DNS queries to newly registered domains, encrypted traffic on non-standard ports.
**Mitigation:** DNS filtering, network segmentation, egress filtering, threat intel feeds.

## Ransomware Network Behavior
Ransomware spreading and communicating over networks.
**Indicators:** SMB lateral movement (port 445), rapid file access patterns,
C2 beaconing, unusual encryption-related traffic.
**Mitigation:** Network segmentation, SMB signing, endpoint protection, offline backups.

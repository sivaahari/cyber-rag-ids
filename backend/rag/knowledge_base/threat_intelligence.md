# Threat Intelligence & IOC Reference

## Indicators of Compromise (IOCs)

### Network IOCs
- **Suspicious IP ranges:** Known Tor exit nodes, VPN endpoints, bulletproof hosting
- **Domain generation algorithms (DGA):** Randomly generated hostnames for C2
- **Beaconing patterns:** Regular outbound connections (every 60/300/3600s)
- **Unusual ports:** C2 on 4444, 8443, 1337, 31337, 6666
- **Large DNS TTL anomalies:** Fast-flux DNS for C2 resilience

### Host-Based IOCs
- New scheduled tasks or services created
- Modifications to system files or registry
- New user accounts, especially admin-level
- Unusual parent-child process relationships (cmd.exe spawned by browser)
- LOLBins: legitimate tools abused (powershell, certutil, mshta, rundll32)

### File-Based IOCs
- MD5/SHA256 hash of known malware samples
- Strings: base64-encoded commands, hardcoded C2 URLs
- Packed/obfuscated executables (high entropy sections)
- Timestomping (file timestamps don't match creation time)

## MITRE ATT&CK Framework (Key Tactics)

| Tactic              | ID    | Common Techniques                        |
|---------------------|-------|------------------------------------------|
| Initial Access      | TA0001| Phishing (T1566), Exploit Public App (T1190) |
| Execution           | TA0002| PowerShell (T1059.001), WMI (T1047)     |
| Persistence         | TA0003| Registry Run Keys (T1547), Cron (T1053) |
| Privilege Escalation| TA0004| Sudo (T1548), Token Impersonation (T1134)|
| Defense Evasion     | TA0005| Obfuscation (T1027), Masquerading (T1036)|
| Credential Access   | TA0006| Brute Force (T1110), Mimikatz (T1003)   |
| Discovery           | TA0007| Network Scan (T1046), System Info (T1082)|
| Lateral Movement    | TA0008| Pass the Hash (T1550), SMB (T1021.002)  |
| Collection          | TA0009| Keylogging (T1056), Screen Capture      |
| C2                  | TA0011| HTTP (T1071.001), DNS Tunneling (T1071.004)|
| Exfiltration        | TA0010| Exfil over C2 (T1041), Cloud Storage   |
| Impact              | TA0040| Ransomware (T1486), Wiper (T1485)       |

## Threat Actor Profiles

### Nation-State APTs
- Long dwell time (months to years)
- Custom malware, zero-day exploits
- Targeted spear-phishing campaigns
- Focus: espionage, IP theft, critical infrastructure

### Cybercriminal Groups
- Ransomware-as-a-Service (RaaS) model
- Initial access brokers sell footholds
- Double extortion: encrypt + threaten to leak data
- Focus: financial gain

### Hacktivists
- DDoS attacks, website defacement
- Data dumps of sensitive information
- Politically motivated
- Often opportunistic, less sophisticated

## Threat Hunting Queries (Sigma-style)

### Detect Port Scanning
flow.dst_port_unique_count > 100 AND
flow.src_ip = SAME AND
flow.time_window = 60s AND
flow.packets_per_flow < 3

### Detect Beaconing
flow.dst_ip = SAME AND
flow.interval_std_dev < 5s AND
flow.occurrence_count > 50 AND
flow.bytes_per_flow < 500

### Detect Data Exfiltration
flow.dst_bytes > 100MB AND
flow.dst_ip NOT IN trusted_ranges AND
flow.protocol IN [DNS, HTTPS] AND
flow.time = after_hours

## Recommended Threat Intel Feeds
- **Free:** AlienVault OTX, MISP, Abuse.ch, Feodo Tracker
- **Commercial:** Recorded Future, CrowdStrike Falcon, Mandiant Advantage
- **Gov:** CISA KEV (Known Exploited Vulnerabilities), FBI IC3

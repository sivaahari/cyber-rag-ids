# IDS Alert Interpretation Guide

## Alert Severity Levels
- **CRITICAL (Score > 0.9):** Immediate response required. Active exploitation likely.
- **HIGH (Score 0.75-0.9):** Investigate within 1 hour. Strong anomaly indicators.
- **MEDIUM (Score 0.5-0.75):** Review within 24 hours. Possible reconnaissance.
- **LOW (Score < 0.5):** Normal monitoring. Baseline deviation within acceptable range.

## Key Network Flow Features Explained
- **Flow Duration:** Time from first to last packet. Very short = scan, Very long = persistent connection.
- **Packet Length Mean:** Average packet size. Unusually high = data exfiltration. Very low = control traffic.
- **Flow Bytes/s:** Data rate. Spikes indicate DoS or bulk transfer.
- **Fwd/Bwd Packet Ratio:** Imbalance indicates unidirectional attack traffic.
- **SYN Flag Count:** High count with low ACK = SYN flood DoS.
- **PSH+ACK Flags:** Normal data transfer. Unusual ratio may indicate tunnel.
- **Init_Win_bytes:** TCP window size. Zero = DoS tool signature.

## Response Playbooks

### For DDoS Detection:
1. Identify source IPs from flow data
2. Implement upstream rate limiting or null routing
3. Contact ISP for BGP blackhole if volumetric
4. Enable scrubbing center if available
5. Document attack vectors for post-incident analysis

### For Port Scan Detection:
1. Block scanning source IP temporarily
2. Review what services were discovered (open ports)
3. Assess if any vulnerable services were exposed
4. Check if scan preceded exploitation attempt
5. Add scanner IP to threat intel watchlist

### For Brute Force Detection:
1. Block source IP immediately
2. Reset credentials for targeted accounts
3. Enable MFA if not already active
4. Review logs for successful logins from same IP
5. Check for lateral movement post-compromise

## MITRE ATT&CK Mapping
- Discovery → T1046 (Network Service Scanning)
- Initial Access → T1190 (Exploit Public-Facing App)
- Credential Access → T1110 (Brute Force)
- Command & Control → T1071 (App Layer Protocol)
- Exfiltration → T1041 (Exfil Over C2 Channel)

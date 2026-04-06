# Network Protocol Security Reference

## TCP/IP Security Vulnerabilities

### SYN Flood (DoS)
**Protocol:** TCP  
**Mechanism:** Attacker sends many SYN packets without completing handshake,
exhausting server connection table.  
**NSL-KDD Indicators:** `serror_rate` > 0.8, `dst_host_serror_rate` > 0.5,
`flag=S0`, high `count` with low `logged_in`.  
**Mitigation:** SYN cookies, TCP half-open connection limits, rate limiting
on SYN packets at firewall.

### TCP Session Hijacking
**Protocol:** TCP  
**Mechanism:** Attacker predicts TCP sequence numbers and injects packets
into an established session.  
**Indicators:** Unexpected RST packets, sequence number anomalies,
duplicate ACKs.  
**Mitigation:** TLS encryption, IPSec, randomised initial sequence numbers.

### UDP Amplification (DDoS)
**Protocol:** UDP  
**Mechanism:** Attacker spoofs victim IP and sends small requests to
UDP services that return large responses (DNS, NTP, Memcached).  
**NSL-KDD Indicators:** `protocol_type=udp`, extremely high `dst_bytes`,
`src_bytes` very small, `service=domain` or `ntp_u`.  
**Mitigation:** BCP38 (ingress filtering), rate limiting DNS/NTP responses,
disable unused UDP services.

## Common Service Vulnerabilities by Port

### SSH (Port 22)
- Brute force via `num_failed_logins` > 5
- Default credentials
- Weak key algorithms (RSA < 2048 bit)
**Detection:** High `count` to port 22, incremental `num_failed_logins`,
same source IP.
**Fix:** Key-based auth only, fail2ban, port knocking, non-standard port.

### HTTP/HTTPS (Ports 80/443)
- SQL injection via abnormal `src_bytes` in POST requests
- Directory traversal in URL paths
- SSRF targeting internal services
**Detection:** Unusually large `src_bytes`, high error rates,
requests to `/admin`, `/../` patterns in payload.

### FTP (Ports 20/21)
- Anonymous login (`is_guest_login=1`)
- Cleartext credential sniffing
- Bounce attacks using PORT command
**Detection:** `service=ftp`, `is_guest_login=1`, `logged_in=0` with
repeated attempts.

### DNS (Port 53)
- DNS tunnelling (C2 over DNS TXT/CNAME records)
- DNS cache poisoning
- DNS amplification for DDoS
**Detection:** Unusually long DNS query names, high query rate,
large TXT record responses, `service=domain_u`.

## Firewall Rules Best Practice
1. Default-deny all inbound
2. Allow only necessary services (allowlist model)
3. Stateful inspection for TCP sessions
4. Log all denied connections
5. Egress filtering to prevent data exfiltration
6. Separate DMZ for public-facing services
7. Micro-segmentation for internal zones

## Zero Trust Network Architecture
- Never trust, always verify
- Least-privilege access per request
- Continuous monitoring and validation
- Encrypt all traffic (East-West + North-South)
- Device posture assessment before access

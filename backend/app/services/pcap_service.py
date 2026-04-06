"""
pcap_service.py
---------------
Handles uploaded PCAP and CSV files:
  - CSV: parse rows directly into NetworkFlowFeatures
  - PCAP: extract flow-level features from raw packets using Scapy

Both return List[NetworkFlowFeatures] ready for LSTM batch inference.
"""

import io
import csv
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger

from app.core.exceptions import FeatureExtractionError, UnsupportedFileTypeError
from app.schemas.models import NetworkFlowFeatures

# Max file sizes:
MAX_CSV_SIZE_MB  = 50
MAX_PCAP_SIZE_MB = 100

# NSL-KDD numeric columns we extract from CSV uploads:
CSV_NUMERIC_COLS = [
    "duration", "src_bytes", "dst_bytes", "land", "wrong_fragment",
    "urgent", "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]


def parse_csv(content: bytes, filename: str) -> List[NetworkFlowFeatures]:
    """
    Parse an uploaded CSV file into a list of NetworkFlowFeatures.

    Supports:
      - NSL-KDD format (with or without header row)
      - Any CSV with matching column names
      - Missing columns filled with 0.0

    Args:
        content:  Raw file bytes
        filename: Original filename (for logging)

    Returns:
        List of NetworkFlowFeatures (one per row)
    """
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_CSV_SIZE_MB:
        raise FeatureExtractionError(
            f"CSV too large: {size_mb:.1f} MB (max {MAX_CSV_SIZE_MB} MB)"
        )

    logger.info(f"Parsing CSV: {filename} ({size_mb:.2f} MB)")

    try:
        # Try to read with pandas — handles both header/no-header:
        text = content.decode("utf-8", errors="replace")
        df   = pd.read_csv(io.StringIO(text))

        # If first column looks like NSL-KDD (numeric duration), no header:
        try:
            float(df.columns[0])
            # No header — assign NSL-KDD column names:
            from app.services.lstm_service import NUMERIC_FEATURES
            nsl_cols = [
                "duration", "protocol_type", "service", "flag",
                "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
                "hot", "num_failed_logins", "logged_in", "num_compromised",
                "root_shell", "su_attempted", "num_root", "num_file_creations",
                "num_shells", "num_access_files", "num_outbound_cmds",
                "is_host_login", "is_guest_login", "count", "srv_count",
                "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
                "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
                "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
                "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
                "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
                "dst_host_srv_serror_rate", "dst_host_rerror_rate",
                "dst_host_srv_rerror_rate", "label", "difficulty_level",
            ]
            df.columns = nsl_cols[:len(df.columns)]
        except (ValueError, TypeError):
            pass   # Has a proper header row

        # Drop label columns if present:
        df = df.drop(columns=["label", "difficulty_level"], errors="ignore")

        # Normalise column names:
        df.columns = [c.strip().lower() for c in df.columns]

    except Exception as e:
        raise FeatureExtractionError(f"Failed to parse CSV: {e}") from e

    flows: List[NetworkFlowFeatures] = []
    for i, row in df.iterrows():
        try:
            kwargs = {}
            # Categorical:
            kwargs["protocol_type"] = str(row.get("protocol_type", "tcp")).strip().lower()
            kwargs["service"]       = str(row.get("service", "http")).strip().lower()
            kwargs["flag"]          = str(row.get("flag", "SF")).strip().upper()

            # Numeric — fill missing with 0.0:
            for col in CSV_NUMERIC_COLS:
                raw = row.get(col, 0)
                try:
                    kwargs[col] = float(raw)
                except (ValueError, TypeError):
                    kwargs[col] = 0.0

            flows.append(NetworkFlowFeatures(**kwargs))

        except Exception as e:
            logger.warning(f"  Skipping row {i}: {e}")
            continue

    if not flows:
        raise FeatureExtractionError("No valid rows could be parsed from the CSV.")

    logger.info(f"  Parsed {len(flows)} flows from {filename}")
    return flows


def parse_pcap(content: bytes, filename: str) -> List[NetworkFlowFeatures]:
    """
    Extract network flow features from a PCAP file using Scapy.

    Feature extraction is simplified (not full CIC-FlowMeter), but produces
    the key fields the LSTM uses. Each TCP/UDP flow → one NetworkFlowFeatures.

    Args:
        content:  Raw PCAP bytes
        filename: Original filename

    Returns:
        List of NetworkFlowFeatures (one per packet, simplified)
    """
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_PCAP_SIZE_MB:
        raise FeatureExtractionError(
            f"PCAP too large: {size_mb:.1f} MB (max {MAX_PCAP_SIZE_MB} MB)"
        )

    logger.info(f"Parsing PCAP: {filename} ({size_mb:.2f} MB)")

    try:
        from scapy.all import rdpcap, IP, TCP, UDP, ICMP
        from scapy.utils import PcapReader
    except ImportError as e:
        raise FeatureExtractionError(
            "Scapy not installed or Npcap missing. "
            "Install Npcap from https://npcap.com and pip install scapy"
        ) from e

    try:
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        packets = rdpcap(tmp_path)
        os.unlink(tmp_path)

    except Exception as e:
        raise FeatureExtractionError(f"Failed to read PCAP: {e}") from e

    flows: List[NetworkFlowFeatures] = []
    skipped = 0

    for pkt in packets:
        try:
            if not pkt.haslayer(IP):
                skipped += 1
                continue

            ip = pkt[IP]

            # ── Protocol ──────────────────────────────────────────
            if pkt.haslayer(TCP):
                proto = "tcp"
                layer = pkt[TCP]
                src_port = layer.sport
                dst_port = layer.dport
                # Extract TCP flags:
                flags_int = int(layer.flags)
                syn = int(bool(flags_int & 0x02))
                ack = int(bool(flags_int & 0x10))
                fin = int(bool(flags_int & 0x01))
                rst = int(bool(flags_int & 0x04))
                # Determine flag label:
                if syn and not ack:
                    flag = "S0"
                elif syn and ack:
                    flag = "SF"
                elif rst:
                    flag = "REJ"
                elif fin:
                    flag = "SF"
                else:
                    flag = "OTH"
            elif pkt.haslayer(UDP):
                proto    = "udp"
                layer    = pkt[UDP]
                src_port = layer.sport
                dst_port = layer.dport
                flag     = "SF"
            elif pkt.haslayer(ICMP):
                proto    = "icmp"
                src_port = 0
                dst_port = 0
                flag     = "SF"
            else:
                skipped += 1
                continue

            # ── Service (port → service name) ─────────────────────
            service = _port_to_service(dst_port, proto)

            # ── Payload sizes ─────────────────────────────────────
            src_bytes = len(pkt)
            dst_bytes = 0   # Not available from single packet

            # ── Build feature object ──────────────────────────────
            flow = NetworkFlowFeatures(
                duration=0.0,            # single packet = no duration
                protocol_type=proto,
                service=service,
                flag=flag,
                src_bytes=float(src_bytes),
                dst_bytes=float(dst_bytes),
                land=int(ip.src == ip.dst),
                wrong_fragment=0.0,
                urgent=0.0,
                hot=0.0,
                num_failed_logins=0.0,
                logged_in=0,
                num_compromised=0.0,
                root_shell=0.0,
                num_root=0.0,
                num_file_creations=0.0,
                num_shells=0.0,
                num_access_files=0.0,
                is_guest_login=0,
                count=1.0,
                srv_count=1.0,
                serror_rate=float(syn and not ack if proto == "tcp" else 0),
                srv_serror_rate=0.0,
                rerror_rate=float(rst if proto == "tcp" else 0),
                srv_rerror_rate=0.0,
                same_srv_rate=1.0,
                diff_srv_rate=0.0,
                srv_diff_host_rate=0.0,
                dst_host_count=1.0,
                dst_host_srv_count=1.0,
                dst_host_same_srv_rate=1.0,
                dst_host_diff_srv_rate=0.0,
                dst_host_same_src_port_rate=0.0,
                dst_host_srv_diff_host_rate=0.0,
                dst_host_serror_rate=0.0,
                dst_host_srv_serror_rate=0.0,
                dst_host_rerror_rate=0.0,
                dst_host_srv_rerror_rate=0.0,
            )
            flows.append(flow)

        except Exception as e:
            logger.debug(f"  Skipping packet: {e}")
            skipped += 1

    logger.info(
        f"  PCAP parsed: {len(flows)} flows extracted, {skipped} packets skipped"
    )

    if not flows:
        raise FeatureExtractionError(
            "No IP packets could be parsed. Is this a valid PCAP file?"
        )

    return flows


def _port_to_service(port: int, proto: str) -> str:
    """Map well-known ports to NSL-KDD service names."""
    port_map = {
        20: "ftp_data", 21: "ftp",   22: "ssh",    23: "telnet",
        25: "smtp",     53: "domain", 69: "tftp_u", 80: "http",
        110: "pop_3",  119: "nntp",  123: "ntp_u", 143: "imap4",
        194: "IRC",    389: "ldap",  443: "http_443",
        445: "netbios_ssn", 514: "shell", 515: "printer",
        587: "smtp",   993: "imap4", 995: "pop_3",
        3306: "sql_net", 8080: "http", 8443: "http_443",
    }
    if proto == "icmp":
        return "eco_i"
    return port_map.get(port, "other")

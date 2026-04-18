#!/usr/bin/env python3
# rev: 2 — external TLS certificate probe for all exposed services
"""Probe TLS certificates from the controller for each configured service.

Reads a JSON manifest from argv[1] and prints a formatted table showing issuer,
subject CN, validity dates, days to expiry, and pass/warn/fail status.

Target schema (list of objects):
  label         human-readable name
  connect_host  IP address or hostname to connect to (lab: use service IP)
  port          TCP port
  sni           TLS SNI / server_name presented during handshake
  protocol      https | smtps | imaps | smtp_starttls
  skip_verify   true = do not enforce cert chain validation (lab/Origin/snake-oil)

Strict mode runs openssl s_client with -verify and -verify_return_error, and treats a
non-zero Verify return code as failure (self-signed, wrong CA, etc.).

Exit code: 0 if all pass (or warn-only), 1 if any fail/error.
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from typing import Optional

WARN_DAYS = 30

# Match CN value from both OpenSSL 3.x ("CN = foo") and LibreSSL ("/CN=foo") DNs.
_CN_RE = re.compile(r'(?:^|[,/])\s*CN\s*=\s*([^,\n/]+)', re.IGNORECASE)
# Match O (organisation) value from DN.
_O_RE = re.compile(r'(?:^|[,/])\s*O\s*=\s*([^,\n/]+)', re.IGNORECASE)
# openssl s_client prints: "Verify return code: 0 (ok)" or "Verify return code: 18 (self signed certificate)"
_VERIFY_RETURN_RE = re.compile(rb"Verify return code:\s*(\d+)", re.IGNORECASE)


def _cn(dn: str) -> str:
    m = _CN_RE.search(dn)
    return m.group(1).strip() if m else dn.strip()


def _org(dn: str) -> str:
    m = _O_RE.search(dn)
    if m:
        return m.group(1).strip()
    return _cn(dn)


def _parse_openssl_date(s: str) -> Optional[datetime.datetime]:
    s = s.strip()
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z"):
        try:
            return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None


def _verify_return_code(stderr: bytes, stdout: bytes) -> Optional[int]:
    """Parse OpenSSL's verification result (0 = trusted chain)."""
    for blob in (stderr, stdout):
        m = _VERIFY_RETURN_RE.search(blob)
        if m:
            return int(m.group(1))
    return None


def _s_client(connect_host: str, port: int, sni: str, protocol: str, strict: bool) -> tuple[bytes, bytes, int]:
    cmd = [
        "openssl", "s_client",
        "-connect", f"{connect_host}:{port}",
        "-servername", sni,
    ]
    if protocol == "smtp_starttls":
        cmd += ["-starttls", "smtp"]
    if strict:
        # -verify_return_error only applies when peer verification is enabled; without -verify,
        # s_client completes the handshake with exit 0 even for self-signed / untrusted certs.
        cmd += ["-verify", "10", "-verify_return_error"]
    try:
        r = subprocess.run(cmd, input=b"\n", capture_output=True, timeout=15)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return b"", b"timed out", -1
    except FileNotFoundError:
        print("ERROR: openssl binary not found in PATH.", file=sys.stderr)
        sys.exit(2)


def _parse_cert(pem_bytes: bytes) -> Optional[dict]:
    r = subprocess.run(
        ["openssl", "x509", "-noout", "-subject", "-issuer", "-dates"],
        input=pem_bytes,
        capture_output=True,
        timeout=5,
    )
    if r.returncode != 0:
        return None
    text = r.stdout.decode("utf-8", errors="replace")

    def _grab(pattern: str) -> str:
        m = re.search(pattern, text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    return {
        "subject_dn": _grab(r"^subject=(.+)$"),
        "issuer_dn": _grab(r"^issuer=(.+)$"),
        "not_before": _parse_openssl_date(_grab(r"^notBefore=(.+)$")),
        "not_after": _parse_openssl_date(_grab(r"^notAfter=(.+)$")),
    }


def probe(target: dict) -> dict:
    label = target["label"]
    connect_host = target["connect_host"]
    port = int(target["port"])
    sni = target["sni"]
    protocol = target["protocol"]
    skip_verify = bool(target.get("skip_verify", False))
    strict = not skip_verify

    out = {
        "label": label,
        "connect": f"{connect_host}:{port}",
        "protocol": protocol,
        "subject_cn": "?",
        "issuer_org": "?",
        "not_before": None,
        "not_after": None,
        "days_left": None,
        "status": "FAIL",
        "note": "",
    }

    stdout, stderr, rc = _s_client(connect_host, port, sni, protocol, strict)
    verify_code = _verify_return_code(stderr, stdout)

    if rc == -1:
        out["note"] = "timeout"
        return out

    chain_ok = True
    if strict:
        if verify_code is not None and verify_code != 0:
            chain_ok = False
            out["note"] = f"verify return code {verify_code}"
        elif verify_code is None and rc != 0:
            chain_ok = False
            out["note"] = "chain verify failed"
        elif rc != 0:
            chain_ok = False
            out["note"] = out["note"] or "handshake failed"

    cert = _parse_cert(stdout)
    if cert is None:
        out["note"] = out["note"] or "no cert / connect error"
        out["status"] = "FAIL"
        return out

    out["subject_cn"] = _cn(cert["subject_dn"]) or cert["subject_dn"]
    out["issuer_org"] = _org(cert["issuer_dn"]) or cert["issuer_dn"]
    out["not_before"] = cert["not_before"]
    out["not_after"] = cert["not_after"]

    now = datetime.datetime.now(datetime.timezone.utc)
    if cert["not_after"]:
        delta = cert["not_after"] - now
        out["days_left"] = delta.days
        if delta.days < 0:
            out["status"] = "EXPIRED"
            out["note"] = out["note"] or "expired"
        elif delta.days < WARN_DAYS:
            out["status"] = "WARN"
        else:
            out["status"] = "OK"
    else:
        out["status"] = "OK"

    if strict and not chain_ok:
        out["status"] = "FAIL"

    return out


def _fmt_dt(dt: Optional[datetime.datetime]) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "?"


def _trunc(s: str, w: int) -> str:
    s = str(s)
    return (s[: w - 1] + "…") if len(s) > w else s


def _print_table(rows: list[dict]) -> None:
    cols = [
        ("label",      "LABEL",        32),
        ("connect",    "CONNECT",       21),
        ("protocol",   "PROTO",          9),
        ("subject_cn", "SUBJECT CN",    28),
        ("issuer_org", "ISSUER",        28),
        ("not_before", "NOT BEFORE",    11),
        ("not_after",  "NOT AFTER",     11),
        ("days_left",  "DAYS LEFT",      9),
        ("status",     "STATUS",         7),
        ("note",       "NOTE",          20),
    ]
    sep = "  "

    def fmtval(row: dict, key: str, w: int) -> str:
        v = row.get(key)
        if key in ("not_before", "not_after"):
            v = _fmt_dt(v)
        elif v is None:
            v = "?"
        return _trunc(str(v), w).ljust(w)

    header = sep.join(h.ljust(w) for _, h, w in cols)
    rule = sep.join("-" * w for _, _, w in cols)
    print(header)
    print(rule)
    for row in rows:
        print(sep.join(fmtval(row, k, w) for k, _, w in cols))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: tls_verify.py <manifest.json>", file=sys.stderr)
        return 2

    with open(sys.argv[1]) as fh:
        targets = json.load(fh)

    results = []
    for t in targets:
        lbl = t["label"]
        ch = t["connect_host"]
        p = t["port"]
        print(f"  probing {lbl} ({ch}:{p}) ...", file=sys.stderr)
        results.append(probe(t))

    print()
    _print_table(results)
    print()

    failed = [r for r in results if r["status"] == "FAIL"]
    warned = [r for r in results if r["status"] in ("WARN", "EXPIRED")]

    summary_lines = []
    if failed:
        summary_lines.append(
            f"FAILED ({len(failed)}): " + ", ".join(r["label"] for r in failed)
        )
    if warned:
        summary_lines.append(
            f"WARN ({len(warned)}): " + ", ".join(r["label"] for r in warned)
        )
    if not failed and not warned:
        summary_lines.append(f"All {len(results)} targets OK.")

    for line in summary_lines:
        print(line)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
